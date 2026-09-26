"""
Incident Decision Orchestrator
Coordinates the end-to-end multi-agent pipeline deterministically:
Intake -> Location -> Live Data Extraction -> ML Risk Prediction ->
Priority Ranking -> Resource Shortage Audit -> Constrained Allocation ->
Response Plan Generation -> Team Matching -> OpenStreetMap Geospatial Mapping.
"""
import logging
from database import get_db
from models import Incident, Zone, ZoneFeature, ResourceInventory, ResourceAllocation, AuditLog, DataSnapshot
from agents.incident_agent import IncidentAgent
from agents.data_agent import DataAgent
from agents.risk_agent import RiskAgent
from agents.decision_agent import DecisionAgent
from agents.resource_agent import ResourceAgent
from agents.response_agent import ResponsePlanningAgent
from agents.communication_agent import CommunicationAgent
from services.data_service import DataIntelligenceService

logger = logging.getLogger(__name__)

class IncidentOrchestrator:
    def __init__(self):
        self.incident_agent = IncidentAgent()
        self.data_agent = DataAgent()
        self.risk_agent = RiskAgent()
        self.decision_agent = DecisionAgent()
        self.resource_agent = ResourceAgent()
        self.response_agent = ResponsePlanningAgent()
        self.comm_agent = CommunicationAgent()
        self.data_service = DataIntelligenceService()

    def process_incident(self, disaster_type, location_str, severity_notes=None, custom_resources=None):
        """
        Executes the entire multi-agent workflow deterministically.
        """
        logger.info(f"Starting orchestration for: {disaster_type} at '{location_str}'")

        # 1. Incident Intelligence (Normalization & DB Initialization)
        incident_data, normalized_loc = self.incident_agent.create_incident(
            disaster_type=disaster_type,
            location_str=location_str,
            severity_notes=severity_notes
        )
        incident_db_id = incident_data['id']
        incident_code = incident_data['incident_id']
        center_lat = normalized_loc['latitude']
        center_lon = normalized_loc['longitude']

        # 2. Live Data Intelligence & Snapshot Telemetry
        telemetry = self.data_service.get_incident_telemetry(center_lat, center_lon)
        zones_telemetry, weather = self.data_agent.generate_zone_telemetry(normalized_loc)

        # 3. Risk Prediction (Trained LightGBM Model Inference)
        evaluated_zones = self.risk_agent.evaluate_zones(zones_telemetry)

        # 4. Zone Prioritization (Transparent Normalized Scoring)
        prioritized_zones = self.decision_agent.prioritize_zones(evaluated_zones)

        # 5. Resource Management (Shortage Audit & Largest Remainder Constrained Allocation)
        allocated_zones, inventory_totals = self.resource_agent.allocate_all_resources(
            prioritized_zones, inventory_pool=custom_resources
        )
        shortage_audit = inventory_totals.get('shortage_audit', {'has_shortage': False, 'shortages': {}})

        # 6. Response Planning (Tactical Orders & Decision Card)
        response_plan, decision_card = self.response_agent.build_response_plan(
            incident_db_id, incident_code, allocated_zones
        )
        if shortage_audit.get('has_shortage'):
            decision_card['shortage_alert'] = shortage_audit.get('summary')

        # 7. Dynamically generate and synchronize localized rescue teams for this location
        from services.location_service import LocationService
        from models import RescueTeam
        loc_svc = LocationService()
        localized_raw_teams = loc_svc.get_localized_rescue_teams(normalized_loc)
        
        with get_db() as session:
            # Clear previous teams and seed localized teams for current location
            session.query(RescueTeam).delete()
            for t in localized_raw_teams:
                team = RescueTeam(
                    team_id=t["team_id"],
                    name=t["name"],
                    organization=t["organization"],
                    team_type=t["team_type"],
                    base_location=t["base_location"],
                    latitude=t["latitude"],
                    longitude=t["longitude"],
                    phone=t["phone"],
                    sms_number=t["sms_number"],
                    email=t["email"],
                    capabilities=t["capabilities"],
                    status=t["status"],
                    available=True,
                    assigned_incident_id=incident_db_id,
                    assigned_zone_name=decision_card.get('primary_full_name', 'Primary Sector'),
                    acknowledgement_status="STANDBY"
                )
                session.add(team)
            session.flush()

        registered_teams = self.comm_agent.get_registered_teams(incident_db_id)

        # 8. Persist Snapshots, Zones, Features, Inventory, Allocations in PostgreSQL
        with get_db() as session:
            inc = session.query(Incident).filter_by(id=incident_db_id).first()
            if inc:
                inc.has_shortage = shortage_audit.get('has_shortage', False)

            # Persist Telemetry Snapshots
            for src in telemetry.get("sources", []):
                snap = DataSnapshot(
                    incident_id=incident_db_id,
                    source=src["source"],
                    data_type=src["data_type"],
                    value=src["value"],
                    confidence=src["confidence"]
                )
                session.add(snap)

            # Save Inventory
            inv_rec = ResourceInventory(
                incident_id=incident_db_id,
                boats_available=inventory_totals.get('total_boats', 50),
                rescue_teams_available=inventory_totals.get('total_rescue_teams', 18),
                ambulances_available=inventory_totals.get('total_ambulances', 24),
                medical_kits_available=inventory_totals.get('total_medical', 5000),
                food_packets_available=inventory_totals.get('total_food', 12000),
                water_units_available=inventory_totals.get('total_water', 10000),
                shelters_available=inventory_totals.get('total_shelters', 400)
            )
            session.add(inv_rec)

            for z in allocated_zones:
                zone_rec = Zone(
                    incident_id=incident_db_id,
                    zone_code=z.get('code', z.get('id')),
                    zone_name=z.get('name'),
                    sector_type=z.get('sector_type'),
                    coordinates=z.get('coordinates'),
                    latitude=z.get('latitude', center_lat),
                    longitude=z.get('longitude', center_lon),
                    population=z.get('population'),
                    vulnerability=z.get('vulnerability'),
                    urgency=z.get('urgency'),
                    flood_probability=z.get('risk_score'),
                    risk_level=z.get('risk_level', 'MODERATE'),
                    priority_score=z.get('priority_score'),
                    action_level=z.get('action_tier', 'MONITOR')
                )
                session.add(zone_rec)
                session.flush()

                # Save 20 Features
                feats_rec = ZoneFeature.from_feats_dict(zone_rec.id, z.get('feats', {}))
                session.add(feats_rec)

                # Save Allocations
                alloc_dict = z.get('allocations', {})
                alloc_rec = ResourceAllocation(
                    incident_id=incident_db_id,
                    zone_id=zone_rec.id,
                    boats_allocated=alloc_dict.get('boats', {}).get('count', 0),
                    rescue_teams_allocated=alloc_dict.get('rescue_teams', {}).get('count', 0),
                    ambulances_allocated=alloc_dict.get('ambulances', {}).get('count', 0),
                    medical_kits_allocated=alloc_dict.get('medical', {}).get('count', 0),
                    food_packets_allocated=alloc_dict.get('food', {}).get('count', 0),
                    water_units_allocated=alloc_dict.get('water', {}).get('count', 0),
                    shelters_allocated=alloc_dict.get('shelters', {}).get('count', 0)
                )
                session.add(alloc_rec)

            # Record completion in audit log
            audit = AuditLog(
                incident_id=incident_db_id,
                action="Multi-Zone Assessment Completed",
                actor="Incident Orchestrator",
                details=f"Evaluated {len(allocated_zones)} operational sectors. Priority #1: {allocated_zones[0]['name']} (Flood Risk: {allocated_zones[0]['risk_pct']}%)."
            )
            session.add(audit)

        logger.info(f"Orchestration completed successfully for {incident_code}.")
        return {
            "success": True,
            "incident": incident_data,
            "normalized_location": normalized_loc,
            "weather": weather,
            "telemetry_sources": telemetry.get("sources", []),
            "shortage_audit": shortage_audit,
            "decision_card": decision_card,
            "response_plan": response_plan,
            "zones": allocated_zones,
            "totals": inventory_totals,
            "rescue_teams": registered_teams
        }

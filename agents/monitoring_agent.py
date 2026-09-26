"""
Continuous Monitoring Agent
Tracks active incidents, re-evaluates hydrologic shifts, detects risk escalations,
and generates revised response plans requiring human approval before dispatch.
"""
from datetime import datetime, timezone
import logging
from database import get_db
from models import Incident, Zone, ZoneFeature, AuditLog
from agents.risk_agent import RiskAgent
from agents.decision_agent import DecisionAgent
from agents.resource_agent import ResourceAgent

logger = logging.getLogger(__name__)

class MonitoringAgent:
    def __init__(self):
        self.risk_agent = RiskAgent()
        self.decision_agent = DecisionAgent()
        self.resource_agent = ResourceAgent()

    def simulate_weather_escalation(self, incident_db_id, rainfall_surge_mm=45.0, dam_discharge_active=True):
        """
        Simulates an environmental shift (e.g. cloudburst / emergency dam release),
        reassesses risk, and computes delta resource recommendations.
        """
        with get_db() as session:
            incident = session.query(Incident).filter_by(id=incident_db_id).first()
            if not incident:
                raise ValueError(f"Incident #{incident_db_id} not found.")

            zones = session.query(Zone).filter_by(incident_id=incident_db_id).all()
            if not zones:
                raise ValueError("No zones recorded for this incident.")

            reassessed_zones = []
            for z in zones:
                z_feats = z.features.to_feats_dict() if z.features else {}
                
                # Apply environmental shift
                z_feats['MonsoonIntensity'] = min(15.0, z_feats.get('MonsoonIntensity', 8.0) + (rainfall_surge_mm / 15.0))
                if dam_discharge_active and ("Valley" in z.zone_name or "Confluence" in z.zone_name):
                    z_feats['DamsQuality'] = min(15.0, z_feats.get('DamsQuality', 8.0) + 4.0)
                    z_feats['TopographyDrainage'] = min(15.0, z_feats.get('TopographyDrainage', 6.0) + 3.0)

                # Predict new risk
                new_risk = self.risk_agent.predict_risk(z_feats)
                prev_risk = z.flood_probability

                zone_dict = {
                    'id': z.zone_code or f"zone_{z.id}",
                    'name': z.zone_name,
                    'short_name': z.zone_name.split('(')[0].strip(),
                    'population': z.population,
                    'vulnerability': z.vulnerability,
                    'urgency': min(1.0, z.urgency + 0.15),
                    'risk_score': new_risk,
                    'risk_pct': round(new_risk * 100, 1),
                    'prev_risk_pct': round(prev_risk * 100, 1),
                    'risk_delta': round((new_risk - prev_risk) * 100, 1),
                    'feats': z_feats
                }
                reassessed_zones.append(zone_dict)

            # Evaluate risk level & re-prioritize zones
            evaluated_zones = self.risk_agent.evaluate_zones(reassessed_zones)
            prioritized = self.decision_agent.prioritize_zones(evaluated_zones)
            allocated_zones, totals = self.resource_agent.allocate_all_resources(prioritized)

            # Identify any escalated zone
            escalated_zone = None
            for pz in allocated_zones:
                if pz.get('risk_delta', 0) >= 10.0 or pz['priority_rank'] == 1:
                    escalated_zone = pz
                    break

            delta_summary = {
                "headline": f"⚠️ SIGNIFICANT RISK ESCALATION IN {escalated_zone['short_name'].upper()}" if escalated_zone else "Environmental conditions shift detected.",
                "explanation": (
                    f"Rainfall surge of +{rainfall_surge_mm:.0f}mm and active reservoir discharge raised "
                    f"{escalated_zone['short_name']}'s predicted flood risk from {escalated_zone.get('prev_risk_pct', 0)}% to {escalated_zone['risk_pct']}%. "
                    f"Recommended delta allocation: +{max(2, int(escalated_zone['allocations']['boats']['count'] * 0.3))} rescue boats and "
                    f"+{max(1, int(escalated_zone['allocations']['rescue_teams']['count'] * 0.3))} teams. Human approval required before re-dispatch."
                ),
                "escalated_zone": escalated_zone['short_name'] if escalated_zone else None,
                "reallocated_zones": allocated_zones
            }

            # Record monitoring event in dedicated table
            from models import MonitoringEvent
            mon_evt = MonitoringEvent(
                incident_id=incident.id,
                event_type="CLOUDBURST_DAM_SURGE",
                old_value=f"{escalated_zone.get('prev_risk_pct', 0)}%" if escalated_zone else "70%",
                new_value=f"{escalated_zone['risk_pct']}%" if escalated_zone else "85%",
                details=delta_summary['explanation']
            )
            session.add(mon_evt)

            # Record monitoring audit entry
            audit = AuditLog(
                incident_id=incident.id,
                action="Hydrologic Escalation Detected",
                actor="Continuous Monitoring Agent",
                details=f"Environmental shift simulated (+{rainfall_surge_mm}mm). Reassessed risk across {len(reassessed_zones)} zones."
            )
            session.add(audit)

            logger.info(f"Monitoring Agent reassessed Incident #{incident.id}: {delta_summary['headline']}")
            return delta_summary

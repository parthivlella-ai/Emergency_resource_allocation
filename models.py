from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, Float, String, DateTime, ForeignKey, Index, Text, Boolean
)
from sqlalchemy.orm import relationship
from database import Base

class Incident(Base):
    __tablename__ = 'incidents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(50), unique=True, nullable=False, index=True) # e.g. INC-2026-001
    disaster_type = Column(String(50), nullable=False, default='Flood')
    location = Column(String(200), nullable=False)
    normalized_location = Column(String(250), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    status = Column(String(50), nullable=False, default='AWAITING_APPROVAL') # ACTIVE, AWAITING_APPROVAL, DISPATCHED, RESOLVED
    overall_risk = Column(String(50), nullable=True, default='CRITICAL')
    severity_notes = Column(Text, nullable=True)
    has_shortage = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    zones = relationship('Zone', back_populates='incident', cascade='all, delete-orphan')
    inventory = relationship('ResourceInventory', back_populates='incident', uselist=False, cascade='all, delete-orphan')
    allocations = relationship('ResourceAllocation', back_populates='incident', cascade='all, delete-orphan')
    response_plans = relationship('ResponsePlan', back_populates='incident', cascade='all, delete-orphan')
    communications = relationship('CommunicationLog', back_populates='incident', cascade='all, delete-orphan')
    audit_logs = relationship('AuditLog', back_populates='incident', cascade='all, delete-orphan')
    data_snapshots = relationship('DataSnapshot', back_populates='incident', cascade='all, delete-orphan')
    monitoring_events = relationship('MonitoringEvent', back_populates='incident', cascade='all, delete-orphan')
    assigned_teams = relationship('RescueTeam', back_populates='assigned_incident')

    __table_args__ = (
        Index('idx_incident_created_at', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'incident_id': self.incident_id,
            'disaster_type': self.disaster_type,
            'location': self.location,
            'normalized_location': self.normalized_location or self.location,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'status': self.status,
            'overall_risk': self.overall_risk,
            'severity_notes': self.severity_notes,
            'has_shortage': self.has_shortage,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC') if self.updated_at else None
        }

class DataSnapshot(Base):
    __tablename__ = 'data_snapshots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False, index=True)
    source = Column(String(100), nullable=False) # e.g. Open-Meteo Live API, OSM Nominatim, Topography Service
    data_type = Column(String(100), nullable=False) # e.g. Rainfall (24h), Elevation, Wind Speed, Population
    value = Column(String(100), nullable=False)
    unit = Column(String(50), nullable=True)
    confidence = Column(String(100), default='HIGH - VERIFIED LIVE SENSOR')
    retrieved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    metadata_json = Column(Text, nullable=True)

    incident = relationship('Incident', back_populates='data_snapshots')

    def to_dict(self):
        return {
            'id': self.id,
            'incident_id': self.incident_id,
            'source': self.source,
            'data_type': self.data_type,
            'value': self.value,
            'unit': self.unit,
            'confidence': self.confidence,
            'retrieved_at': self.retrieved_at.strftime('%H:%M:%S UTC') if self.retrieved_at else None,
            'metadata': self.metadata_json
        }

class Zone(Base):
    __tablename__ = 'zones'

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False, index=True)
    zone_code = Column(String(30), nullable=True) # e.g. ZONE A
    zone_name = Column(String(150), nullable=False)
    sector_type = Column(String(100), nullable=True)
    coordinates = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    population = Column(Integer, nullable=False, default=100000)
    vulnerability = Column(Float, nullable=False, default=0.65) # 0.05 - 1.0
    urgency = Column(Float, nullable=False, default=0.65) # 0.05 - 1.0
    flood_probability = Column(Float, nullable=False, default=0.50) # ML prediction
    risk_level = Column(String(50), nullable=False, default='MODERATE') # CRITICAL, HIGH, MODERATE, LOW
    priority_score = Column(Float, nullable=False, default=0.50)
    action_level = Column(String(100), nullable=False, default='MONITOR')
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    incident = relationship('Incident', back_populates='zones')
    features = relationship('ZoneFeature', back_populates='zone', uselist=False, cascade='all, delete-orphan')
    allocations = relationship('ResourceAllocation', back_populates='zone', cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_zone_priority', 'incident_id', 'priority_score'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'incident_id': self.incident_id,
            'zone_code': self.zone_code,
            'zone_name': self.zone_name,
            'sector_type': self.sector_type,
            'coordinates': self.coordinates,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'population': self.population,
            'vulnerability': self.vulnerability,
            'urgency': self.urgency,
            'flood_probability': round(self.flood_probability, 4),
            'risk_pct': round(self.flood_probability * 100, 1),
            'risk_level': self.risk_level,
            'priority_score': round(self.priority_score, 4),
            'action_level': self.action_level,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if self.created_at else None,
            'features': self.features.to_feats_dict() if self.features else {}
        }

class ZoneFeature(Base):
    __tablename__ = 'zone_features'

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_id = Column(Integer, ForeignKey('zones.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)

    # Category A: Environment & Climate
    monsoon_precipitation_intensity = Column(Float, nullable=False, default=7.0)
    climate_anomaly_impact = Column(Float, nullable=False, default=7.0)
    topography_runoff_slope = Column(Float, nullable=False, default=7.0)
    wetland_mangrove_loss = Column(Float, nullable=False, default=7.0)
    deforestation_rate = Column(Float, nullable=False, default=7.0)

    # Category B: Hydrology & Infrastructure
    stormwater_drainage_capacity = Column(Float, nullable=False, default=7.0)
    dam_reservoir_integrity = Column(Float, nullable=False, default=7.0)
    deteriorating_infrastructure = Column(Float, nullable=False, default=7.0)
    river_channel_management = Column(Float, nullable=False, default=7.0)
    inadequate_master_planning = Column(Float, nullable=False, default=7.0)

    # Category C: Community & Governance
    population_vulnerability = Column(Float, nullable=False, default=7.0)
    urban_impervious_density = Column(Float, nullable=False, default=7.0)
    agricultural_soil_practices = Column(Float, nullable=False, default=7.0)
    disaster_preparedness_deficit = Column(Float, nullable=False, default=7.0)
    floodplain_encroachments = Column(Float, nullable=False, default=7.0)

    # Category D: Watershed & Geotechnical
    riverbed_siltation = Column(Float, nullable=False, default=7.0)
    coastal_surge_vulnerability = Column(Float, nullable=False, default=7.0)
    landslide_debris_risk = Column(Float, nullable=False, default=7.0)
    watershed_retention_health = Column(Float, nullable=False, default=7.0)
    institutional_policy_delay = Column(Float, nullable=False, default=7.0)

    # Relationships
    zone = relationship('Zone', back_populates='features')

    def to_feats_dict(self):
        return {
            'MonsoonIntensity': self.monsoon_precipitation_intensity,
            'ClimateChange': self.climate_anomaly_impact,
            'TopographyDrainage': self.topography_runoff_slope,
            'WetlandLoss': self.wetland_mangrove_loss,
            'Deforestation': self.deforestation_rate,
            'DrainageSystems': self.stormwater_drainage_capacity,
            'DamsQuality': self.dam_reservoir_integrity,
            'DeterioratingInfrastructure': self.deteriorating_infrastructure,
            'RiverManagement': self.river_channel_management,
            'InadequatePlanning': self.inadequate_master_planning,
            'PopulationScore': self.population_vulnerability,
            'Urbanization': self.urban_impervious_density,
            'AgriculturalPractices': self.agricultural_soil_practices,
            'IneffectiveDisasterPreparedness': self.disaster_preparedness_deficit,
            'Encroachments': self.floodplain_encroachments,
            'Siltation': self.riverbed_siltation,
            'CoastalVulnerability': self.coastal_surge_vulnerability,
            'Landslides': self.landslide_debris_risk,
            'Watersheds': self.watershed_retention_health,
            'PoliticalFactors': self.institutional_policy_delay
        }

    @staticmethod
    def from_feats_dict(zone_id, feats):
        return ZoneFeature(
            zone_id=zone_id,
            monsoon_precipitation_intensity=float(feats.get('MonsoonIntensity', 7.0)),
            climate_anomaly_impact=float(feats.get('ClimateChange', 7.0)),
            topography_runoff_slope=float(feats.get('TopographyDrainage', 7.0)),
            wetland_mangrove_loss=float(feats.get('WetlandLoss', 7.0)),
            deforestation_rate=float(feats.get('Deforestation', 7.0)),
            stormwater_drainage_capacity=float(feats.get('DrainageSystems', 7.0)),
            dam_reservoir_integrity=float(feats.get('DamsQuality', 7.0)),
            deteriorating_infrastructure=float(feats.get('DeterioratingInfrastructure', 7.0)),
            river_channel_management=float(feats.get('RiverManagement', 7.0)),
            inadequate_master_planning=float(feats.get('InadequatePlanning', 7.0)),
            population_vulnerability=float(feats.get('PopulationScore', 7.0)),
            urban_impervious_density=float(feats.get('Urbanization', 7.0)),
            agricultural_soil_practices=float(feats.get('AgriculturalPractices', 7.0)),
            disaster_preparedness_deficit=float(feats.get('IneffectiveDisasterPreparedness', 7.0)),
            floodplain_encroachments=float(feats.get('Encroachments', 7.0)),
            riverbed_siltation=float(feats.get('Siltation', 7.0)),
            coastal_surge_vulnerability=float(feats.get('CoastalVulnerability', 7.0)),
            landslide_debris_risk=float(feats.get('Landslides', 7.0)),
            watershed_retention_health=float(feats.get('Watersheds', 7.0)),
            institutional_policy_delay=float(feats.get('PoliticalFactors', 7.0))
        )

class ResourceInventory(Base):
    __tablename__ = 'resource_inventory'

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    boats_available = Column(Integer, nullable=False, default=50)
    rescue_teams_available = Column(Integer, nullable=False, default=18)
    ambulances_available = Column(Integer, nullable=False, default=24)
    medical_kits_available = Column(Integer, nullable=False, default=5000)
    food_packets_available = Column(Integer, nullable=False, default=12000)
    water_units_available = Column(Integer, nullable=False, default=10000)
    shelters_available = Column(Integer, nullable=False, default=400)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    incident = relationship('Incident', back_populates='inventory')

    def to_dict(self):
        return {
            'total_boats': self.boats_available,
            'total_rescue_teams': self.rescue_teams_available,
            'total_ambulances': self.ambulances_available,
            'total_medical': self.medical_kits_available,
            'total_food': self.food_packets_available,
            'total_water': self.water_units_available,
            'total_shelters': self.shelters_available
        }

class RescueTeam(Base):
    __tablename__ = 'rescue_teams'

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(String(50), unique=True, nullable=False, index=True) # e.g. RT-001, NDRF-AP-10
    name = Column(String(150), nullable=False)
    organization = Column(String(150), nullable=False) # e.g. NDRF, SDRF, EMS, Fire & Rescue
    team_type = Column(String(100), nullable=False) # Flood Rescue, Medical Triage, Relief Logistics
    base_location = Column(String(150), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    phone = Column(String(50), nullable=False, default='+91-XXXXXXXXXX')
    sms_number = Column(String(50), nullable=False, default='+91-XXXXXXXXXX')
    email = Column(String(100), nullable=False, default='responder@disaster.gov.in')
    capabilities = Column(String(200), nullable=False)
    status = Column(String(50), nullable=False, default='AVAILABLE') # AVAILABLE, DEPLOYED, STANDBY
    available = Column(Boolean, default=True)

    # Assignment tracking
    assigned_incident_id = Column(Integer, ForeignKey('incidents.id', ondelete='SET NULL'), nullable=True)
    assigned_zone_name = Column(String(150), nullable=True)
    acknowledgement_status = Column(String(50), default='STANDBY') # STANDBY, AWAITING_RESPONSE, ACCEPTED, DECLINED, UNAVAILABLE
    acknowledged_at = Column(DateTime, nullable=True)

    # Relationships
    assigned_incident = relationship('Incident', back_populates='assigned_teams')

    def to_dict(self):
        return {
            'id': self.id,
            'team_id': self.team_id,
            'name': self.name,
            'organization': self.organization,
            'team_type': self.team_type,
            'base_location': self.base_location,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'phone': self.phone,
            'capabilities': self.capabilities,
            'status': self.status,
            'available': self.available,
            'assigned_zone': self.assigned_zone_name,
            'acknowledgement_status': self.acknowledgement_status,
            'acknowledged_at': self.acknowledged_at.strftime('%H:%M:%S UTC') if self.acknowledged_at else None
        }

class ResourceAllocation(Base):
    __tablename__ = 'resource_allocations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False, index=True)
    zone_id = Column(Integer, ForeignKey('zones.id', ondelete='CASCADE'), nullable=False, index=True)
    boats_allocated = Column(Integer, nullable=False, default=0)
    rescue_teams_allocated = Column(Integer, nullable=False, default=0)
    ambulances_allocated = Column(Integer, nullable=False, default=0)
    medical_kits_allocated = Column(Integer, nullable=False, default=0)
    food_packets_allocated = Column(Integer, nullable=False, default=0)
    water_units_allocated = Column(Integer, nullable=False, default=0)
    shelters_allocated = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    incident = relationship('Incident', back_populates='allocations')
    zone = relationship('Zone', back_populates='allocations')

    def to_dict(self):
        return {
            'zone_id': self.zone_id,
            'boats': self.boats_allocated,
            'rescue_teams': self.rescue_teams_allocated,
            'ambulances': self.ambulances_allocated,
            'medical': self.medical_kits_allocated,
            'food': self.food_packets_allocated,
            'water': self.water_units_allocated,
            'shelters': self.shelters_allocated
        }

class ResponsePlan(Base):
    __tablename__ = 'response_plans'

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False, index=True)
    status = Column(String(50), nullable=False, default='PENDING_APPROVAL') # PENDING_APPROVAL, APPROVED, DISPATCHED, REVISED
    primary_zone_name = Column(String(150), nullable=False)
    primary_action = Column(String(200), nullable=False)
    recommendation = Column(Text, nullable=False)
    shortage_detected = Column(Boolean, default=False)
    shortage_details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String(100), nullable=True)

    # Relationships
    incident = relationship('Incident', back_populates='response_plans')

    def to_dict(self):
        return {
            'id': self.id,
            'incident_id': self.incident_id,
            'status': self.status,
            'primary_zone_name': self.primary_zone_name,
            'primary_action': self.primary_action,
            'recommendation': self.recommendation,
            'shortage_detected': self.shortage_detected,
            'shortage_details': self.shortage_details,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if self.created_at else None,
            'approved_at': self.approved_at.strftime('%Y-%m-%d %H:%M:%S UTC') if self.approved_at else None,
            'approved_by': self.approved_by
        }

class CommunicationLog(Base):
    __tablename__ = 'communication_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False, index=True)
    team_id = Column(String(50), nullable=True)
    recipient = Column(String(150), nullable=False)
    role = Column(String(100), nullable=True)
    channel = Column(String(50), default='TACTICAL_DISPATCH') # SMS, VOICE_CALL, RADIO_DISPATCH, WHATSAPP
    message = Column(Text, nullable=False)
    provider = Column(String(100), nullable=False, default='Emergency Dispatch Simulator')
    status = Column(String(50), nullable=False, default='SENT (PROTOTYPE SIMULATION)')
    response_status = Column(String(50), default='AWAITING_RESPONSE') # AWAITING_RESPONSE, ACCEPTED, DECLINED, UNAVAILABLE
    provider_message_id = Column(String(100), nullable=True)
    sent_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)

    # Relationships
    incident = relationship('Incident', back_populates='communications')

    def to_dict(self):
        return {
            'id': self.id,
            'incident_id': self.incident_id,
            'team_id': self.team_id,
            'recipient': self.recipient,
            'role': self.role,
            'channel': self.channel,
            'message': self.message,
            'provider': self.provider,
            'status': self.status,
            'response_status': self.response_status,
            'provider_message_id': self.provider_message_id,
            'sent_at': self.sent_at.strftime('%H:%M:%S UTC') if self.sent_at else None,
            'acknowledged_at': self.acknowledged_at.strftime('%H:%M:%S UTC') if self.acknowledged_at else None
        }

class MonitoringEvent(Base):
    __tablename__ = 'monitoring_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False, index=True)
    event_type = Column(String(100), nullable=False) # CLOUDBURST_SURGE, DAM_SPILLWAY_RELEASE, FLOOD_CREST
    old_value = Column(String(100), nullable=True)
    new_value = Column(String(100), nullable=True)
    details = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    incident = relationship('Incident', back_populates='monitoring_events')

    def to_dict(self):
        return {
            'id': self.id,
            'incident_id': self.incident_id,
            'event_type': self.event_type,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'details': self.details,
            'created_at': self.created_at.strftime('%H:%M:%S UTC') if self.created_at else None
        }

class AuditLog(Base):
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    actor = Column(String(100), nullable=False, default='AI Agent Orchestrator')
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    details = Column(Text, nullable=True)

    # Relationships
    incident = relationship('Incident', back_populates='audit_logs')

    def to_dict(self):
        return {
            'id': self.id,
            'action': self.action,
            'actor': self.actor,
            'timestamp': self.timestamp.strftime('%H:%M:%S UTC') if self.timestamp else None,
            'details': self.details
        }

# Backwards compatibility aliases
Assessment = Incident
ZoneRiskFactor = ZoneFeature

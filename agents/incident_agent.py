"""
Incident Intelligence Agent
Responsible for incident intake, location normalization, ID generation,
and audit trail initialization.
"""
from datetime import datetime, timezone
import random
import logging
from database import get_db
from models import Incident, AuditLog
from services.location_service import LocationService

logger = logging.getLogger(__name__)

class IncidentAgent:
    def __init__(self):
        self.location_service = LocationService()

    def create_incident(self, disaster_type, location_str, severity_notes=None):
        """
        Creates and stores a validated incident in the database.
        """
        normalized_loc = self.location_service.normalize_location(location_str)
        year = datetime.now(timezone.utc).year
        random_suffix = random.randint(100, 999)
        incident_code = f"INC-{year}-{random_suffix}"

        with get_db() as session:
            incident = Incident(
                incident_id=incident_code,
                disaster_type=disaster_type or "Flood",
                location=location_str.strip() if location_str else "Regional Operations Area",
                normalized_location=normalized_loc["display_name"],
                latitude=normalized_loc["latitude"],
                longitude=normalized_loc["longitude"],
                status="AWAITING_APPROVAL",
                overall_risk="CRITICAL",
                severity_notes=severity_notes or "Field telemetry received. Automated assessment in progress."
            )
            session.add(incident)
            session.flush()

            # Record initial audit entry
            audit = AuditLog(
                incident_id=incident.id,
                action="Incident Initialized",
                actor="Incident Intelligence Agent",
                details=f"Created incident {incident_code} for {normalized_loc['display_name']}."
            )
            session.add(audit)

            logger.info(f"Created Incident #{incident.id} ({incident_code})")
            return incident.to_dict(), normalized_loc

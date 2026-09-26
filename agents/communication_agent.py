"""
AI Communication Agent
Executes human-authorized dispatch directives to registered response teams.
Tracks delivery logs and interactive team acknowledgements (ACCEPT, DECLINE, UNAVAILABLE).
"""
from datetime import datetime, timezone
import logging
from database import get_db
from models import Incident, ResponsePlan, CommunicationLog, AuditLog, RescueTeam
from services.communication_service import EmergencyCommunicationService

logger = logging.getLogger(__name__)

class CommunicationAgent:
    def __init__(self):
        self.service = EmergencyCommunicationService()

    def get_registered_teams(self, incident_db_id=None):
        """Retrieves active registered response teams from database."""
        with get_db() as session:
            teams = session.query(RescueTeam).all()
            return [t.to_dict() for t in teams]

    def execute_authorized_dispatch(self, incident_db_id, officer_name, badge_number):
        """
        Executes authorized tactical dispatch after officer sign-off.
        Updates incident status to DISPATCHED and logs every transmission.
        """
        now_utc = datetime.now(timezone.utc)

        with get_db() as session:
            incident = session.query(Incident).filter_by(id=incident_db_id).first()
            if not incident:
                raise ValueError(f"Incident #{incident_db_id} not found in database.")

            plan = session.query(ResponsePlan).filter_by(incident_id=incident_db_id).order_by(ResponsePlan.id.desc()).first()
            if not plan:
                raise ValueError(f"No active response plan found for incident #{incident_db_id}.")

            # Update Plan and Incident authorization status
            plan.status = "DISPATCHED"
            plan.approved_by = f"{officer_name} (Badge: {badge_number})"
            plan.approved_at = now_utc
            incident.status = "DISPATCHED"

            # Retrieve registered response teams
            db_teams = session.query(RescueTeam).all()
            matched_teams = []
            for t in db_teams:
                t.assigned_incident_id = incident.id
                t.assigned_zone_name = plan.primary_zone_name
                t.acknowledgement_status = "AWAITING_RESPONSE"
                matched_teams.append(t.to_dict())

            # Format decision card dict for transmission
            plan_summary = {
                "primary_zone": plan.primary_zone_name,
                "primary_assets": {
                    "boats": incident.allocations[0].boats_allocated if incident.allocations else 15,
                    "teams": incident.allocations[0].rescue_teams_allocated if incident.allocations else 6,
                    "ambulances": incident.allocations[0].ambulances_allocated if incident.allocations else 8,
                    "medical": incident.allocations[0].medical_kits_allocated if incident.allocations else 1500,
                    "food": incident.allocations[0].food_packets_allocated if incident.allocations else 3500,
                    "water": incident.allocations[0].water_units_allocated if incident.allocations else 3000,
                    "shelters": incident.allocations[0].shelters_allocated if incident.allocations else 120
                }
            }

            # Transmit dispatches
            dispatch_results = self.service.transmit_team_dispatches(
                incident_code=incident.incident_id,
                response_plan=plan_summary,
                authorized_officer=plan.approved_by,
                matched_teams=matched_teams[:3] # Send to primary 3 operational response units
            )

            # Record in PostgreSQL communication_logs table
            db_logs = []
            for res in dispatch_results:
                log_entry = CommunicationLog(
                    incident_id=incident.id,
                    team_id=res.get("team_id"),
                    recipient=res["recipient"],
                    role=res["role"],
                    channel=res.get("channel", "TACTICAL_DISPATCH"),
                    message=res["message"],
                    provider=res["provider"],
                    status=res["status"],
                    response_status="AWAITING_RESPONSE",
                    provider_message_id=res.get("provider_message_id")
                )
                session.add(log_entry)
                db_logs.append(log_entry)

            # Record audit entry
            audit = AuditLog(
                incident_id=incident.id,
                action="Emergency Dispatch Authorized & Transmitted",
                actor=plan.approved_by,
                details=f"Authorized deployment to {plan.primary_zone_name}. Dispatched {len(dispatch_results)} notifications via {dispatch_results[0]['provider']}."
            )
            session.add(audit)

            logger.info(f"Authorized dispatch executed for Incident #{incident.id} by {plan.approved_by}")
            return {
                "success": True,
                "incident_id": incident.incident_id,
                "status": "DISPATCHED",
                "approved_by": plan.approved_by,
                "approved_at": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "communications": [l.to_dict() for l in db_logs],
                "teams": [t.to_dict() for t in db_teams]
            }

    def record_team_response(self, incident_db_id, team_id, response_action):
        """
        Records field acknowledgement (ACCEPT, DECLINE, UNAVAILABLE) from a response team.
        If a team declines, flags an operational replacement need.
        """
        now_utc = datetime.now(timezone.utc)
        action_clean = response_action.strip().upper()
        if action_clean not in ["ACCEPTED", "DECLINED", "UNAVAILABLE"]:
            action_clean = "ACCEPTED"

        with get_db() as session:
            team = session.query(RescueTeam).filter_by(team_id=team_id).first()
            if not team:
                raise ValueError(f"Team {team_id} not found.")

            team.acknowledgement_status = action_clean
            team.acknowledged_at = now_utc

            # Update communication log if present
            comm = session.query(CommunicationLog).filter_by(incident_id=incident_db_id, team_id=team_id).first()
            if comm:
                comm.response_status = action_clean
                comm.acknowledged_at = now_utc

            # Audit event
            if action_clean == "ACCEPTED":
                audit_msg = f"{team.name} ({team.team_id}) confirmed deployment. Status: READY TO DEPLOY."
            else:
                audit_msg = f"⚠️ SQUAD SHORTAGE: {team.name} ({team.team_id}) reported {action_clean}. Requesting secondary reserve unit."

            audit = AuditLog(
                incident_id=incident_db_id,
                action=f"Response Team Acknowledgement ({action_clean})",
                actor=f"{team.team_id} Dispatch Receiver",
                details=audit_msg
            )
            session.add(audit)

            all_teams = session.query(RescueTeam).all()
            return {
                "success": True,
                "team_id": team.team_id,
                "acknowledgement_status": action_clean,
                "acknowledged_at": now_utc.strftime("%H:%M:%S UTC"),
                "teams": [t.to_dict() for t in all_teams]
            }

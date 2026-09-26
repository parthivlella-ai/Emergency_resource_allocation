"""
Response Planning Agent
Converts resource allocations and zone prioritizations into an actionable,
explainable operational response plan awaiting authorized officer approval.
"""
from datetime import datetime, timezone
import logging
from database import get_db
from models import ResponsePlan, AuditLog

logger = logging.getLogger(__name__)

class ResponsePlanningAgent:
    def build_response_plan(self, incident_db_id, incident_code, prioritized_zones):
        """
        Assembles tactical response plan and stores in PostgreSQL with status PENDING_APPROVAL.
        """
        top_zone = prioritized_zones[0]
        second_zone = prioritized_zones[1] if len(prioritized_zones) > 1 else None

        tactical_orders = [
            f"Dispatch {top_zone['allocations']['boats']['count']} rescue boats & {top_zone['allocations']['rescue_teams']['count']} rescue squads directly to sector perimeter.",
            f"Deploy {top_zone['allocations']['ambulances']['count']} critical ambulances and establish field triage with {top_zone['allocations']['medical']['count']:,} medical kits.",
            f"Distribute {top_zone['allocations']['food']['count']:,} food packets and {top_zone['allocations']['water']['count']:,} water units to emergency staging shelters.",
            f"Issue mandatory evacuation alert for low-lying and riverbed settlements in {top_zone['name']}."
        ]

        decision_card = {
            'primary_zone': top_zone['short_name'],
            'primary_full_name': top_zone['name'],
            'primary_rank': top_zone['priority_rank'],
            'primary_headline': top_zone['action_headline'],
            'primary_rationale': top_zone['rationale'],
            'primary_orders': tactical_orders,
            'primary_assets': {
                'boats': top_zone['allocations']['boats']['count'],
                'teams': top_zone['allocations']['rescue_teams']['count'],
                'ambulances': top_zone['allocations']['ambulances']['count'],
                'medical': top_zone['allocations']['medical']['count'],
                'food': top_zone['allocations']['food']['count'],
                'water': top_zone['allocations']['water']['count'],
                'shelters': top_zone['allocations']['shelters']['count']
            },
            'secondary_zone': second_zone['short_name'] if second_zone else None,
            'secondary_headline': second_zone['action_headline'] if second_zone else None,
            'secondary_boats': second_zone['allocations']['boats']['count'] if second_zone else 0,
            'secondary_teams': second_zone['allocations']['rescue_teams']['count'] if second_zone else 0
        }

        # Persist response plan to database
        with get_db() as session:
            plan = ResponsePlan(
                incident_id=incident_db_id,
                status="PENDING_APPROVAL",
                primary_zone_name=top_zone['name'],
                primary_action=top_zone['action_headline'],
                recommendation=top_zone['rationale']
            )
            session.add(plan)
            session.flush()

            audit = AuditLog(
                incident_id=incident_db_id,
                action="Response Plan Generated",
                actor="Response Planning Agent",
                details=f"Generated Plan #{plan.id}: Prioritizing {top_zone['name']} (Pending Officer Approval)."
            )
            session.add(audit)

            logger.info(f"Created Response Plan #{plan.id} for incident {incident_code}")
            return plan.to_dict(), decision_card

"""
Decision Intelligence Agent
Calculates multi-factor priority scores, determines regional priority ranks,
and synthesizes plain-language operational justifications.
"""
import logging
from config import Config

logger = logging.getLogger(__name__)

class DecisionAgent:
    def __init__(self, weights=None):
        self.weights = weights or Config.PRIORITY_WEIGHTS

    def prioritize_zones(self, zones):
        """
        Calculates transparent priority score across all evaluated zones.
        Priority = 0.40 * Flood Risk + 0.25 * Norm(Pop) + 0.20 * Vulnerability + 0.15 * Urgency
        """
        if not zones:
            return []

        populations = [max(1000, int(z.get('population', 50000))) for z in zones]
        max_pop = max(populations) if populations else 1
        min_pop = min(populations) if populations else 0
        pop_range = max(1, max_pop - min_pop)

        w_risk = self.weights.get('flood_risk', 0.40)
        w_pop = self.weights.get('population', 0.25)
        w_vuln = self.weights.get('vulnerability', 0.20)
        w_urg = self.weights.get('urgency', 0.15)

        for z in zones:
            z['name'] = z.get('name', z.get('id', 'Operational Zone'))
            z['short_name'] = z.get('short_name', z['name'])
            z['population'] = max(1000, int(z.get('population', 50000)))
            z['vulnerability'] = Config.parse_qualitative_val(z.get('vulnerability', 0.65))
            z['vulnerability_label'] = Config.num_to_qualitative_label(z['vulnerability'])
            z['urgency'] = Config.parse_qualitative_val(z.get('urgency', 0.65))
            z['urgency_label'] = Config.num_to_qualitative_label(z['urgency'])

            # Normalized population exposure scaled with baseline buffer
            norm_pop = round((z['population'] - min_pop) / pop_range * 0.8 + 0.2, 4)
            z['norm_pop'] = norm_pop

            risk_part = w_risk * z['risk_score']
            pop_part = w_pop * norm_pop
            vuln_part = w_vuln * z['vulnerability']
            urg_part = w_urg * z['urgency']

            priority_score = round(risk_part + pop_part + vuln_part + urg_part, 4)
            z['priority_score'] = priority_score
            z['priority_breakdown'] = {
                'risk_contrib': round(risk_part, 3),
                'pop_contrib': round(pop_part, 3),
                'vuln_contrib': round(vuln_part, 3),
                'urg_contrib': round(urg_part, 3)
            }

        # Sort descending by priority score
        zones_sorted = sorted(zones, key=lambda x: x['priority_score'], reverse=True)
        for rank, z in enumerate(zones_sorted, 1):
            z['priority_rank'] = rank

            # Synthesize explainable justification
            breakdown = z['priority_breakdown']
            factors = [
                ('acute flood inundation risk', breakdown['risk_contrib']),
                ('high demographic exposure', breakdown['pop_contrib']),
                ('critical infrastructure vulnerability', breakdown['vuln_contrib']),
                ('urgent evacuation timeline', breakdown['urg_contrib'])
            ]
            top_factor = sorted(factors, key=lambda x: x[1], reverse=True)[0][0]

            if rank == 1:
                z['action_headline'] = f"IMMEDIATE DEPLOYMENT TO {z['short_name'].upper()}"
                z['rationale'] = (
                    f"{z['name']} has been prioritized as Rank #1 because it combines high predicted "
                    f"flood risk ({z['risk_pct']}%) with {top_factor} ({z['population']:,} exposed residents). "
                    f"Immediate priority deployment is authorized to avert acute danger."
                )
            elif rank == 2:
                z['action_headline'] = f"PRE-POSITION RESOURCES IN {z['short_name'].upper()}"
                z['rationale'] = (
                    f"{z['name']} represents Rank #2 Priority with {top_factor} "
                    f"and {z['risk_pct']}% flood probability. Heavy rescue buffer staging is required."
                )
            elif z['risk_score'] >= 0.38:
                z['action_headline'] = f"PREPARE & MONITOR {z['short_name'].upper()}"
                z['rationale'] = (
                    f"{z['name']} is at Moderate Priority with {z['risk_pct']}% flood risk. "
                    f"Secondary equipment reserve assigned."
                )
            else:
                z['action_headline'] = f"MONITOR {z['short_name'].upper()}"
                z['rationale'] = (
                    f"{z['name']} maintains low flood risk ({z['risk_pct']}%) with natural drainage buffer."
                )

        logger.info(f"Prioritized {len(zones_sorted)} zones. Rank #1 Target: {zones_sorted[0]['name']}")
        return zones_sorted

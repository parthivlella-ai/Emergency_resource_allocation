import os
import joblib
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Base 20 features expected by the trained LightGBM model
BASE_FEATURES = [
    'MonsoonIntensity', 'TopographyDrainage', 'RiverManagement', 'Deforestation',
    'Urbanization', 'ClimateChange', 'DamsQuality', 'Siltation', 'AgriculturalPractices',
    'Encroachments', 'IneffectiveDisasterPreparedness', 'DrainageSystems', 'CoastalVulnerability',
    'Landslides', 'Watersheds', 'DeterioratingInfrastructure', 'PopulationScore',
    'WetlandLoss', 'InadequatePlanning', 'PoliticalFactors'
]

# Logical grouping per Hackathon Phase 12 (Environment, Infrastructure, Community)
FEATURE_CATEGORIES_LOGICAL = {
    'Environment & Climate': [
        ('MonsoonIntensity', 'Monsoon Precipitation Intensity', 'Seasonal rainfall severity index (1-15)'),
        ('ClimateChange', 'Climate Anomaly Impact', 'Regional temperature & storm deviations (1-15)'),
        ('TopographyDrainage', 'Topography & Runoff Slope', 'Natural slope and runoff velocity (1-15)'),
        ('WetlandLoss', 'Wetland & Mangrove Loss', 'Destruction of natural retention buffers (1-15)'),
        ('Deforestation', 'Deforestation Rate', 'Loss of canopy accelerating surface wash (1-15)')
    ],
    'Hydrology & Infrastructure': [
        ('DrainageSystems', 'Stormwater Drainage Capacity', 'Urban conduit and culvert throughput (1-15)'),
        ('DamsQuality', 'Dam & Reservoir Integrity', 'Spillway maintenance and dam holding safety (1-15)'),
        ('DeterioratingInfrastructure', 'Deteriorating Infrastructure', 'Age and decay of flood containment walls (1-15)'),
        ('RiverManagement', 'River Channel Management', 'Dredging quality and levee condition (1-15)'),
        ('InadequatePlanning', 'Inadequate Master Planning', 'Absence of stormwater zoning codes (1-15)')
    ],
    'Community & Governance': [
        ('PopulationScore', 'Population Vulnerability', 'Demographic exposure & density stress (1-15)'),
        ('Urbanization', 'Urban Impervious Density', 'Paved ground preventing natural infiltration (1-15)'),
        ('AgriculturalPractices', 'Agricultural Soil Practices', 'Farming methods causing severe erosion (1-15)'),
        ('IneffectiveDisasterPreparedness', 'Disaster Preparedness Deficit', 'Gaps in sirens, staging, and drills (1-15)'),
        ('Encroachments', 'Floodplain Encroachments', 'Unregulated settlements in high-risk zones (1-15)')
    ],
    'Watershed & Geotechnical': [
        ('Siltation', 'Riverbed Siltation', 'Sediment buildup reducing river channel volume (1-15)'),
        ('CoastalVulnerability', 'Coastal Surge Vulnerability', 'Tidal backflow and storm surge exposure (1-15)'),
        ('Landslides', 'Landslide & Debris Risk', 'Slope destabilization and river damming hazard (1-15)'),
        ('Watersheds', 'Watershed Retention Health', 'Natural catchment health and vegetation (1-15)'),
        ('PoliticalFactors', 'Institutional & Policy Delay', 'Emergency response administrative friction (1-15)')
    ]
}

# Legacy categorization retained for compatibility
FEATURE_CATEGORIES = {
    'Meteorological & Climate': [
        ('MonsoonIntensity', 'Monsoon Intensity', 'Annual or seasonal monsoon precipitation severity (1-15)'),
        ('ClimateChange', 'Climate Change Impact', 'Observed deviations in regional climate stability (1-15)')
    ],
    'Hydrology & Water Management': [
        ('TopographyDrainage', 'Topography Drainage', 'Natural slope and runoff efficiency of terrain (1-15)'),
        ('RiverManagement', 'River Basin Management', 'Condition of channels, levees, and dredging (1-15)'),
        ('DamsQuality', 'Dams Quality & Maintenance', 'Structural integrity and capacity of reservoirs (1-15)'),
        ('Siltation', 'Riverbed Siltation', 'Sediment accumulation reducing river carrying capacity (1-15)'),
        ('DrainageSystems', 'Drainage Systems Network', 'Stormwater and urban drainage throughput (1-15)'),
        ('Watersheds', 'Watershed Health', 'Basin retention capacity and vegetative cover (1-15)')
    ],
    'Terrain & Environment': [
        ('Deforestation', 'Deforestation Rate', 'Loss of forest cover accelerating surface runoff (1-15)'),
        ('AgriculturalPractices', 'Agricultural Practices', 'Soil erosion and flood-exacerbating farming methods (1-15)'),
        ('CoastalVulnerability', 'Coastal Vulnerability', 'Exposure to storm surges and tidal backflows (1-15)'),
        ('Landslides', 'Landslide Frequency', 'Geotechnical instability and debris damming risk (1-15)'),
        ('WetlandLoss', 'Wetland & Mangrove Loss', 'Destruction of natural retention buffers (1-15)')
    ],
    'Infrastructure & Governance': [
        ('Urbanization', 'Urbanization Density', 'Impervious surface expansion and runoff generation (1-15)'),
        ('Encroachments', 'Floodplain Encroachments', 'Unauthorized settlements in active floodplains (1-15)'),
        ('IneffectiveDisasterPreparedness', 'Preparedness Inefficiency', 'Deficits in sirens, evacuation, and drill readiness (1-15)'),
        ('DeterioratingInfrastructure', 'Deteriorating Infrastructure', 'Age and decay of flood barriers and culverts (1-15)'),
        ('PopulationScore', 'Population Vulnerability', 'Demographic exposure and density index (1-15)'),
        ('InadequatePlanning', 'Inadequate Master Planning', 'Absence of zoning regulations and runoff codes (1-15)'),
        ('PoliticalFactors', 'Institutional & Policy Delay', 'Governance barriers and regulatory bottlenecks (1-15)')
    ]
}

# Configurable Weights for Transparent Priority Scoring (Phase 4)
DEFAULT_PRIORITY_WEIGHTS = {
    'flood_risk': 0.40,
    'population': 0.25,
    'vulnerability': 0.20,
    'urgency': 0.15
}

# Prototype Emergency Resource Constraints (Phase 5)
DEFAULT_RESOURCES = {
    'total_boats': 50,
    'total_rescue_teams': 18,
    'total_ambulances': 24,
    'total_medical': 5000,
    'total_food': 12000,
    'total_water': 10000,
    'total_shelters': 400
}

# Prototype Operational Zones (Phase 2 & 3)
# Note: In accordance with hackathon instructions, simulated zones are clearly labeled as "Prototype Operational Zones"
PROTOTYPE_ZONES_CONFIG = [
    {
        'id': 'zone_a',
        'code': 'ZONE A',
        'name': 'Zone A',
        'short_name': 'Zone A',
        'type': 'Coastal Estuary / High Inundation Risk',
        'coordinates': 'Grid 14-E (Coastal Sector)',
        'population': 180000,
        'vulnerability': 0.85,
        'urgency': 0.88,
        'accessibility': 'Moderate (Waterways Open, Coastal Roads Vulnerable)',
        'feats': {
            'MonsoonIntensity': 12, 'TopographyDrainage': 11, 'RiverManagement': 11, 'Deforestation': 10,
            'Urbanization': 12, 'ClimateChange': 12, 'DamsQuality': 11, 'Siltation': 12,
            'AgriculturalPractices': 9, 'Encroachments': 11, 'IneffectiveDisasterPreparedness': 12,
            'DrainageSystems': 11, 'CoastalVulnerability': 13, 'Landslides': 7, 'Watersheds': 10,
            'DeterioratingInfrastructure': 11, 'PopulationScore': 12, 'WetlandLoss': 12,
            'InadequatePlanning': 12, 'PoliticalFactors': 10
        }
    },
    {
        'id': 'zone_b',
        'code': 'ZONE B',
        'name': 'Zone B',
        'short_name': 'Zone B',
        'type': 'High-Density Urban Confluence',
        'coordinates': 'Grid 22-C (Metro Confluence)',
        'population': 190000,
        'vulnerability': 0.82,
        'urgency': 0.85,
        'accessibility': 'High (Major Arterial Expressways)',
        'feats': {
            'MonsoonIntensity': 11, 'TopographyDrainage': 9, 'RiverManagement': 10, 'Deforestation': 9,
            'Urbanization': 13, 'ClimateChange': 10, 'DamsQuality': 9, 'Siltation': 11,
            'AgriculturalPractices': 7, 'Encroachments': 12, 'IneffectiveDisasterPreparedness': 11,
            'DrainageSystems': 12, 'CoastalVulnerability': 9, 'Landslides': 6, 'Watersheds': 9,
            'DeterioratingInfrastructure': 12, 'PopulationScore': 12, 'WetlandLoss': 11,
            'InadequatePlanning': 12, 'PoliticalFactors': 10
        }
    },
    {
        'id': 'zone_c',
        'code': 'ZONE C',
        'name': 'Zone C',
        'short_name': 'Zone C',
        'type': 'Mountain Valley & Spillway Reach',
        'coordinates': 'Grid 08-A (Highland Reach)',
        'population': 110000,
        'vulnerability': 0.75,
        'urgency': 0.72,
        'accessibility': 'Challenging (Mountain Passes Subject to Landslides)',
        'feats': {
            'MonsoonIntensity': 9, 'TopographyDrainage': 7, 'RiverManagement': 8, 'Deforestation': 11,
            'Urbanization': 6, 'ClimateChange': 8, 'DamsQuality': 10, 'Siltation': 8,
            'AgriculturalPractices': 9, 'Encroachments': 7, 'IneffectiveDisasterPreparedness': 8,
            'DrainageSystems': 7, 'CoastalVulnerability': 4, 'Landslides': 11, 'Watersheds': 10,
            'DeterioratingInfrastructure': 9, 'PopulationScore': 7, 'WetlandLoss': 8,
            'InadequatePlanning': 8, 'PoliticalFactors': 7
        }
    },
    {
        'id': 'zone_d',
        'code': 'ZONE D',
        'name': 'Zone D',
        'short_name': 'Zone D',
        'type': 'Rural Floodplain & Farmland Basin',
        'coordinates': 'Grid 31-F (Rural Plain)',
        'population': 95000,
        'vulnerability': 0.55,
        'urgency': 0.50,
        'accessibility': 'Moderate (Unpaved Secondary Roads)',
        'feats': {
            'MonsoonIntensity': 7, 'TopographyDrainage': 6, 'RiverManagement': 6, 'Deforestation': 7,
            'Urbanization': 5, 'ClimateChange': 7, 'DamsQuality': 6, 'Siltation': 8,
            'AgriculturalPractices': 10, 'Encroachments': 6, 'IneffectiveDisasterPreparedness': 6,
            'DrainageSystems': 6, 'CoastalVulnerability': 6, 'Landslides': 5, 'Watersheds': 7,
            'DeterioratingInfrastructure': 6, 'PopulationScore': 6, 'WetlandLoss': 8,
            'InadequatePlanning': 6, 'PoliticalFactors': 5
        }
    },
    {
        'id': 'zone_e',
        'code': 'ZONE E',
        'name': 'Zone E',
        'short_name': 'Zone E',
        'type': 'Elevated Natural Drainage Buffer',
        'coordinates': 'Grid 02-B (Plateau Reserve)',
        'population': 60000,
        'vulnerability': 0.30,
        'urgency': 0.25,
        'accessibility': 'Good (Highland Expressways Clear)',
        'feats': {
            'MonsoonIntensity': 3, 'TopographyDrainage': 4, 'RiverManagement': 4, 'Deforestation': 3,
            'Urbanization': 4, 'ClimateChange': 4, 'DamsQuality': 3, 'Siltation': 3,
            'AgriculturalPractices': 4, 'Encroachments': 3, 'IneffectiveDisasterPreparedness': 4,
            'DrainageSystems': 4, 'CoastalVulnerability': 2, 'Landslides': 2, 'Watersheds': 4,
            'DeterioratingInfrastructure': 4, 'PopulationScore': 3, 'WetlandLoss': 3,
            'InadequatePlanning': 4, 'PoliticalFactors': 3
        }
    }
]

# Load the pre-trained LightGBM model once at server startup
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'flood_risk_model.pkl')
print(f"Loading trained LightGBM model from {MODEL_PATH}...")
try:
    model = joblib.load(MODEL_PATH)
    print("Model loaded successfully into memory.")
except Exception as e:
    print(f"Error loading model: {e}")
    model = None

def predict_zone_risk(feat_dict):
    """
    Evaluates flood risk probability for a specific zone using the trained LightGBM model.
    Dynamically computes engineered features: Environmental_Stress_Sum and Environmental_Stress_Std.
    Bounds output strictly between 0.01 and 0.99.
    """
    if model is None:
        return 0.50

    try:
        values = [float(feat_dict.get(k, 5.0)) for k in BASE_FEATURES]
        stress_sum = float(np.sum(values))
        stress_std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0

        all_feats = BASE_FEATURES + ['Environmental_Stress_Sum', 'Environmental_Stress_Std']
        row_values = values + [stress_sum, stress_std]
        input_df = pd.DataFrame([row_values], columns=all_feats)

        pred_raw = model.predict(input_df)[0]
        return float(np.clip(pred_raw, 0.01, 0.99))
    except Exception as e:
        print(f"Prediction inference error: {e}")
        return 0.50

def get_operational_status(risk_score, priority_score=None):
    """Determine operational readiness status from risk and composite priority."""
    score_to_use = priority_score if priority_score is not None else risk_score

    if score_to_use >= 0.70 or risk_score >= 0.68:
        return {
            'level': 'CRITICAL',
            'badge': 'critical',
            'color': '#ef4444',
            'action_tier': 'IMMEDIATE DEPLOYMENT',
            'icon': '🚨',
            'description': 'Severe imminent threat to life & property. Tier-1 emergency mobilization required immediately.'
        }
    elif score_to_use >= 0.52 or risk_score >= 0.50:
        return {
            'level': 'ALERT',
            'badge': 'alert',
            'color': '#f59e0b',
            'action_tier': 'PRE-POSITION ASSETS',
            'icon': '⚠️',
            'description': 'Heightened flood threat. Pre-position heavy rescue assets and stage mobile medical teams.'
        }
    elif score_to_use >= 0.38:
        return {
            'level': 'MONITOR',
            'badge': 'moderate',
            'color': '#3b82f6',
            'action_tier': 'PREPARE & MONITOR',
            'icon': '📋',
            'description': 'Moderate vulnerability. Maintain communications, verify shelters, and review dispatch routes.'
        }
    else:
        return {
            'level': 'STANDBY',
            'badge': 'standby',
            'color': '#10b981',
            'action_tier': 'ROUTINE SURVEILLANCE',
            'icon': '🛡️',
            'description': 'Low inundation risk. Maintain automated reservoir telemetry and hold squads on secondary notice.'
        }

def allocate_constrained_resources(total_units, weights):
    """
    Constrained proportional resource allocation algorithm using the Largest Remainder Method (Hamilton-Hare).
    Guarantees:
      1. Proportionality strictly according to priority weights
      2. Discrete integer unit allocations
      3. Sum(allocations) == total_units with 0 unallocated units and 0 resource drift
      4. Strict conservation: Allocated <= Available
    """
    total_units = int(max(0, total_units))
    if total_units <= 0:
        return [0] * len(weights)
    
    total_weight = sum(weights)
    if total_weight <= 0:
        weights = [1.0] * len(weights)
        total_weight = sum(weights)

    raw_allocations = [(w / total_weight) * total_units for w in weights]
    floored = [int(np.floor(a)) for a in raw_allocations]
    remainders = [a - f for a, f in zip(raw_allocations, floored)]

    unallocated = total_units - sum(floored)
    # Distribute leftover single discrete units to zones with highest fractional remainders
    priority_order = sorted(range(len(weights)), key=lambda i: remainders[i], reverse=True)
    for i in range(unallocated):
        floored[priority_order[i % len(weights)]] += 1

    return floored

def evaluate_multizone_system(zones_data, resources_data, weights_config=None):
    """
    Core Multi-Zone Decision Engine (Phases 2-8):
      1. Runs ML model inference for EACH operational zone dynamically
      2. Normalizes population exposure so population size alone does not dominate
      3. Computes transparent composite Priority Score using configurable weights
      4. Allocates all emergency resources with 100% exact conservation via Largest Remainder
      5. Synthesizes explainable action recommendations and tactical orders
    """
    if weights_config is None:
        weights_config = DEFAULT_PRIORITY_WEIGHTS

    # 1. Run ML inference for every zone
    for z in zones_data:
        z['risk_score'] = predict_zone_risk(z['feats'])
        z['risk_pct'] = round(z['risk_score'] * 100, 1)

    # 2. Normalize population across monitored zones
    max_pop = max(z['population'] for z in zones_data) if zones_data else 1
    min_pop = min(z['population'] for z in zones_data) if zones_data else 0
    pop_range = max(1, max_pop - min_pop)

    # 3. Compute Transparent Priority Scores
    w_risk = weights_config.get('flood_risk', 0.40)
    w_pop = weights_config.get('population', 0.25)
    w_vuln = weights_config.get('vulnerability', 0.20)
    w_urg = weights_config.get('urgency', 0.15)

    for z in zones_data:
        # Normalized population exposure scaled with non-zero baseline
        z['norm_pop'] = round((z['population'] - min_pop) / pop_range * 0.8 + 0.2, 4)
        
        # Transparent 4-factor priority score calculation
        risk_part = w_risk * z['risk_score']
        pop_part = w_pop * z['norm_pop']
        vuln_part = w_vuln * z['vulnerability']
        urg_part = w_urg * z['urgency']

        z['priority_score'] = round(risk_part + pop_part + vuln_part + urg_part, 4)
        z['priority_breakdown'] = {
            'risk_contrib': round(risk_part, 3),
            'pop_contrib': round(pop_part, 3),
            'vuln_contrib': round(vuln_part, 3),
            'urg_contrib': round(urg_part, 3)
        }
        z['status'] = get_operational_status(z['risk_score'], z['priority_score'])

    # Sort zones by priority score descending to determine regional priority ranks
    zones_sorted = sorted(zones_data, key=lambda x: x['priority_score'], reverse=True)
    for rank, z in enumerate(zones_sorted, 1):
        z['priority_rank'] = rank

    # 4. Proportional Resource Allocation across all resources (Phase 5 & 6)
    priority_weights = [z['priority_score'] for z in zones_sorted]
    total_priority = sum(priority_weights)

    resource_keys = [
        ('boats', 'total_boats', 'Rescue Boats'),
        ('rescue_teams', 'total_rescue_teams', 'Rescue Teams'),
        ('ambulances', 'total_ambulances', 'Ambulances'),
        ('medical', 'total_medical', 'Medical Kits'),
        ('food', 'total_food', 'Food Rations'),
        ('water', 'total_water', 'Drinking Water'),
        ('shelters', 'total_shelters', 'Shelter Tents')
    ]

    allocations = {}
    totals = {}

    for short_key, total_key, name in resource_keys:
        tot = int(resources_data.get(total_key, DEFAULT_RESOURCES.get(total_key, 0)))
        alloc = allocate_constrained_resources(tot, priority_weights)
        allocations[short_key] = alloc
        totals[total_key] = tot
        totals[f'allocated_{short_key}'] = sum(alloc)

    # Attach allocations to each zone
    for i, z in enumerate(zones_sorted):
        z['priority_share_pct'] = round((z['priority_score'] / total_priority) * 100, 1) if total_priority > 0 else 20.0
        z['allocations'] = {}
        for short_key, total_key, name in resource_keys:
            assigned = allocations[short_key][i]
            avail = totals[total_key]
            pct = round((assigned / avail) * 100, 1) if avail > 0 else 0
            z['allocations'][short_key] = {
                'count': assigned,
                'pct': pct,
                'name': name
            }

    # 5. Synthesize Explainable Action Recommendations (Phases 7 & 8)
    for z in zones_sorted:
        # Determine top contributing factor
        breakdown = z['priority_breakdown']
        factors = [
            ('flood inundation risk', breakdown['risk_contrib']),
            ('high demographic exposure', breakdown['pop_contrib']),
            ('infrastructure vulnerability', breakdown['vuln_contrib']),
            ('evacuation time urgency', breakdown['urg_contrib'])
        ]
        top_factor = sorted(factors, key=lambda x: x[1], reverse=True)[0][0]

        if z['priority_rank'] == 1:
            z['action_headline'] = f"🚨 IMMEDIATE DEPLOYMENT TO {z['short_name'].upper()}"
            z['rationale'] = (
                f"{z['name']} holds Rank #1 Priority ({z['priority_score']:.2f}) driven primarily by "
                f"critical {top_factor} and predicted flood probability of {z['risk_pct']}%. "
                f"Mandatory priority dispatch is authorized to avert acute life risk."
            )
            z['tactical_orders'] = [
                f"Dispatch {z['allocations']['boats']['count']} rescue boats & {z['allocations']['rescue_teams']['count']} search teams to sector water perimeter.",
                f"Pre-deploy {z['allocations']['ambulances']['count']} critical ambulances and establish emergency medical triage with {z['allocations']['medical']['count']:,} medical kits.",
                f"Distribute {z['allocations']['food']['count']:,} food rations and {z['allocations']['water']['count']:,} water units to regional relief centers.",
                "Issue immediate siren evacuation advisory for floodplains and low-lying estuarine settlements."
            ]
        elif z['priority_rank'] == 2:
            z['action_headline'] = f"⚠️ PRE-POSITION RESOURCES IN {z['short_name'].upper()}"
            z['rationale'] = (
                f"{z['name']} represents Rank #2 Priority ({z['priority_score']:.2f}) with significant {top_factor} "
                f"and {z['risk_pct']}% flood probability. High demographic exposure requires active buffer staging."
            )
            z['tactical_orders'] = [
                f"Stage {z['allocations']['boats']['count']} boats and {z['allocations']['rescue_teams']['count']} teams along highway staging corridors.",
                f"Deliver {z['allocations']['medical']['count']:,} medical kits & {z['allocations']['shelters']['count']} emergency tents to municipal staging depots.",
                "Verify evacuation routes and test emergency floodgate communication protocols."
            ]
        elif z['status']['level'] == 'MONITOR':
            z['action_headline'] = f"📋 PREPARE & MONITOR {z['short_name'].upper()}"
            z['rationale'] = (
                f"{z['name']} is at Moderate Priority ({z['priority_score']:.2f}) with {z['risk_pct']}% flood risk. "
                f"Resource buffer allocated: {z['allocations']['boats']['count']} boats, {z['allocations']['rescue_teams']['count']} teams."
            )
            z['tactical_orders'] = [
                "Place local volunteer squads on 2-hour standby.",
                "Monitor upstream dam discharge and hourly river gauge telemetry.",
                "Maintain supply depot readiness for rapid diversion if surge worsens."
            ]
        else:
            z['action_headline'] = f"🛡️ ROUTINE SURVEILLANCE IN {z['short_name'].upper()}"
            z['rationale'] = (
                f"{z['name']} maintains low flood probability ({z['risk_pct']}%) with natural drainage buffer. "
                f"Minimal reserve allocation assigned ({z['allocations']['boats']['count']} boats)."
            )
            z['tactical_orders'] = [
                "Continue automated hydrologic sensor monitoring.",
                "Maintain secondary dispatch notice for medical reserve units."
            ]

    # Primary Decision Card (The #1 Action of the whole system)
    top_zone = zones_sorted[0]
    second_zone = zones_sorted[1] if len(zones_sorted) > 1 else None

    decision_card = {
        'primary_zone': top_zone['short_name'],
        'primary_rank': top_zone['priority_rank'],
        'primary_headline': top_zone['action_headline'],
        'primary_rationale': top_zone['rationale'],
        'primary_orders': top_zone['tactical_orders'],
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

    # Macro Situation Overview
    totals['total_population'] = sum(z['population'] for z in zones_sorted)
    totals['avg_risk'] = round(float(np.mean([z['risk_score'] for z in zones_sorted])) * 100, 1)
    totals['critical_zones_count'] = sum(1 for z in zones_sorted if z['status']['level'] == 'CRITICAL')
    totals['alert_zones_count'] = sum(1 for z in zones_sorted if z['status']['level'] == 'ALERT')
    totals['is_conserved'] = all(
        totals[f'allocated_{short_key}'] <= totals[total_key]
        for short_key, total_key, name in resource_keys
    )

    # Backward compatibility aliases for existing templates/scripts
    top_risk = top_zone['risk_score'] if top_zone else 0.50
    return {
        'zones': zones_sorted,
        'sectors': zones_sorted,  # compatibility alias
        'decision_card': decision_card,
        'totals': totals,
        'weights_config': weights_config,
        'target_risk': top_risk,
        'target_risk_pct': round(top_risk * 100, 1),
        'target_status': top_zone['status'] if top_zone else {}
    }

@app.route('/', methods=['GET'])
def index():
    """Command Center Landing Dashboard with dynamic baseline evaluation preloaded."""
    import copy
    default_zones = copy.deepcopy(PROTOTYPE_ZONES_CONFIG)
    default_resources = copy.deepcopy(DEFAULT_RESOURCES)
    
    # Run dynamic multi-zone evaluation so the dashboard opens with full live results!
    results = evaluate_multizone_system(default_zones, default_resources)

    # Inputs dictionary for Zone A (for the telemetry inspector)
    zone_a_inputs = default_zones[0]['feats']

    return render_template(
        'index.html',
        base_features=BASE_FEATURES,
        feature_categories=FEATURE_CATEGORIES_LOGICAL,
        inputs=zone_a_inputs,
        resources=default_resources,
        results=results,
        zones_config=default_zones
    )

@app.route('/predict_and_allocate', methods=['POST'])
def predict_and_allocate():
    """
    Handles operational assessment execution.
    Supports both traditional Form POST and AJAX JSON payloads.
    Runs ML model across all zones dynamically without hardcoding.
    """
    try:
        import copy
        zones = copy.deepcopy(PROTOTYPE_ZONES_CONFIG)
        form_data = request.form

        # Check if JSON payload was submitted
        if request.is_json:
            req_json = request.get_json() or {}
            custom_zones = req_json.get('zones')
            if custom_zones and isinstance(custom_zones, list):
                zones = custom_zones
            resources_data = req_json.get('resources', DEFAULT_RESOURCES)
        else:
            # Traditional form submission:
            selected_zone_id = form_data.get('selected_zone', 'zone_a').strip().lower()
            target_idx = 0
            for idx, z in enumerate(zones):
                if z['id'].lower() == selected_zone_id:
                    target_idx = idx
                    break

            feat_values = {}
            for feat in BASE_FEATURES:
                feat_values[feat] = float(form_data.get(feat, zones[target_idx]['feats'].get(feat, 5.0)))
            
            zones[target_idx]['feats'] = feat_values
            
            # Optional zone overrides
            if form_data.get('zone_population'):
                zones[target_idx]['population'] = max(1000, int(form_data.get('zone_population')))
            if form_data.get('zone_vulnerability'):
                zones[target_idx]['vulnerability'] = max(0.05, min(1.0, float(form_data.get('zone_vulnerability'))))
            if form_data.get('zone_urgency'):
                zones[target_idx]['urgency'] = max(0.05, min(1.0, float(form_data.get('zone_urgency'))))
            if form_data.get('target_sector_name'):
                zones[target_idx]['name'] = form_data.get('target_sector_name').strip()
                zones[target_idx]['short_name'] = zones[target_idx]['name']

            # Read resource constraints with fallback to defaults
            resources_data = {
                'total_boats': max(0, int(form_data.get('total_boats', DEFAULT_RESOURCES['total_boats']))),
                'total_rescue_teams': max(0, int(form_data.get('total_rescue_teams', DEFAULT_RESOURCES['total_rescue_teams']))),
                'total_ambulances': max(0, int(form_data.get('total_ambulances', DEFAULT_RESOURCES['total_ambulances']))),
                'total_medical': max(0, int(form_data.get('total_medical', DEFAULT_RESOURCES['total_medical']))),
                'total_food': max(0, int(form_data.get('total_food', DEFAULT_RESOURCES['total_food']))),
                'total_water': max(0, int(form_data.get('total_water', DEFAULT_RESOURCES['total_water']))),
                'total_shelters': max(0, int(form_data.get('total_shelters', DEFAULT_RESOURCES['total_shelters'])))
            }

        # Run multi-zone dynamic decision engine
        results = evaluate_multizone_system(zones, resources_data)

        # Return JSON if requested via AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': True, 'results': results})

        # Regular HTML response
        zone_a_inputs = zones[0]['feats']
        return render_template(
            'index.html',
            base_features=BASE_FEATURES,
            feature_categories=FEATURE_CATEGORIES_LOGICAL,
            inputs=zone_a_inputs,
            resources=resources_data,
            results=results,
            zones_config=zones
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 500
        
        # User-friendly error page without exposing raw stack trace
        import copy
        default_zones = copy.deepcopy(PROTOTYPE_ZONES_CONFIG)
        default_resources = copy.deepcopy(DEFAULT_RESOURCES)
        results = evaluate_multizone_system(default_zones, default_resources)
        
        return render_template(
            'index.html',
            base_features=BASE_FEATURES,
            feature_categories=FEATURE_CATEGORIES_LOGICAL,
            inputs=default_zones[0]['feats'],
            resources=default_resources,
            results=results,
            zones_config=default_zones,
            error_message="Operational assessment encountered an input validation error. Default parameters restored."
        )

@app.route('/api/assess', methods=['POST'])
def api_assess():
    """Clean REST API for multi-region decision assessment."""
    try:
        data = request.get_json(force=True) or {}
        zones = data.get('zones', PROTOTYPE_ZONES_CONFIG)
        resources = data.get('resources', DEFAULT_RESOURCES)
        weights = data.get('weights', DEFAULT_PRIORITY_WEIGHTS)

        results = evaluate_multizone_system(zones, resources, weights)
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/demo_scenario', methods=['GET'])
def api_demo_scenario():
    """
    Returns preset operational scenarios for instant 1-click hackathon demonstration (Phase 20).
    Demonstrates dynamic prioritization where different zones become Critical Rank 1 based on conditions.
    """
    scenario_type = request.args.get('type', 'cyclone_surge')
    import copy
    zones = copy.deepcopy(PROTOTYPE_ZONES_CONFIG)

    if scenario_type == 'cyclone_surge':
        # Severe Coastal Cyclone Surge -> ZONE A becomes Critical Rank 1
        for k in BASE_FEATURES:
            zones[0]['feats'][k] = 14
        zones[0]['urgency'] = 0.98
        zones[0]['vulnerability'] = 0.95
        zones[0]['population'] = 220000
        # Other zones moderate
        for z in zones[1:]:
            for k in BASE_FEATURES:
                z['feats'][k] = min(z['feats'][k], 7)
            z['urgency'] = 0.50
            z['vulnerability'] = 0.50

    elif scenario_type == 'urban_collapse':
        # Catastrophic Metro Drainage Inundation -> ZONE B becomes Critical Rank 1
        for k in BASE_FEATURES:
            zones[1]['feats'][k] = 15
        zones[1]['urgency'] = 0.98
        zones[1]['vulnerability'] = 0.95
        zones[1]['population'] = 240000
        # Reduce other zones
        for idx in [0, 2, 3, 4]:
            for k in BASE_FEATURES:
                zones[idx]['feats'][k] = min(zones[idx]['feats'][k], 6)
            zones[idx]['urgency'] = 0.45
            zones[idx]['vulnerability'] = 0.45

    elif scenario_type == 'dam_spillway':
        # Mountain Valley Dam Spillway Breach -> ZONE C becomes Critical Rank 1
        for k in BASE_FEATURES:
            zones[2]['feats'][k] = 15
        zones[2]['urgency'] = 0.98
        zones[2]['vulnerability'] = 0.95
        zones[2]['population'] = 190000
        # Reduce other zones
        for idx in [0, 1, 3, 4]:
            for k in BASE_FEATURES:
                zones[idx]['feats'][k] = min(zones[idx]['feats'][k], 6)
            zones[idx]['urgency'] = 0.45
            zones[idx]['vulnerability'] = 0.45

    elif scenario_type == 'lowland_flood':
        # Agricultural Basin Levee Failure -> ZONE D becomes Critical Rank 1
        for k in BASE_FEATURES:
            zones[3]['feats'][k] = 15
        zones[3]['urgency'] = 0.98
        zones[3]['vulnerability'] = 0.95
        zones[3]['population'] = 200000
        # Reduce other zones
        for idx in [0, 1, 2, 4]:
            for k in BASE_FEATURES:
                zones[idx]['feats'][k] = min(zones[idx]['feats'][k], 6)
            zones[idx]['urgency'] = 0.45
            zones[idx]['vulnerability'] = 0.45

    elif scenario_type == 'seasonal_baseline':
        # Dry weather / seasonal baseline -> All Standby / Routine Monitoring
        for z in zones:
            for k in BASE_FEATURES:
                z['feats'][k] = 4
            z['urgency'] = 0.30
            z['vulnerability'] = 0.30

    results = evaluate_multizone_system(zones, DEFAULT_RESOURCES)
    return jsonify({
        'success': True,
        'scenario': scenario_type,
        'zones': zones,
        'resources': DEFAULT_RESOURCES,
        'results': results
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

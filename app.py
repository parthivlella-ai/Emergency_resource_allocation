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

# Load the pre-trained LightGBM model once at server startup
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'flood_risk_model.pkl')
print(f"Loading trained LightGBM model from {MODEL_PATH}...")
model = joblib.load(MODEL_PATH)
print("Model loaded successfully into memory.")

def get_operational_status(risk_score):
    """Determine dispatch readiness level based on operational risk threshold."""
    if risk_score >= 0.60:
        return {
            'level': 'CRITICAL',
            'badge': 'critical',
            'color': '#ef4444',
            'description': 'Immediate emergency mobilization required. Severe threat to life & infrastructure.'
        }
    elif risk_score >= 0.45:
        return {
            'level': 'ALERT',
            'badge': 'alert',
            'color': '#f59e0b',
            'description': 'Heightened surveillance and active pre-positioning of rapid response assets.'
        }
    else:
        return {
            'level': 'STANDBY',
            'badge': 'standby',
            'color': '#10b981',
            'description': 'Routine monitoring. Resources held on secondary notice.'
        }

def allocate_constrained_resources(total_units, weights):
    """
    Constrained proportional resource allocation algorithm using the Largest Remainder Method (Hamilton-Hare).
    Guarantees:
      1. Proportionality according to impact weights: W_i = Risk_i * Population_i
      2. Strict integer unit allocation
      3. Sum(allocations) == total_units with 0 rounding drift or lost units
    """
    total_units = int(total_units)
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
    # Distribute leftover single units to sectors with highest fractional remainder
    priority_order = sorted(range(len(weights)), key=lambda i: remainders[i], reverse=True)
    for i in range(unallocated):
        floored[priority_order[i % len(weights)]] += 1

    return floored

@app.route('/', methods=['GET'])
def index():
    # Default initial values for environmental parameters (baseline 5)
    default_inputs = {feat: 5 for feat in BASE_FEATURES}
    default_resources = {
        'total_boats': 50,
        'total_medical': 30,
        'total_food': 2500,
        'target_population': 120000,
        'target_sector_name': 'District Alpha (Target District)'
    }
    return render_template(
        'index.html',
        base_features=BASE_FEATURES,
        feature_categories=FEATURE_CATEGORIES,
        inputs=default_inputs,
        resources=default_resources,
        results=None
    )

@app.route('/predict_and_allocate', methods=['POST'])
def predict_and_allocate():
    try:
        # 1. Extract 20 environmental parameters from request
        form_data = request.form
        feature_values = []
        inputs_dict = {}

        for feat in BASE_FEATURES:
            val = float(form_data.get(feat, 5.0))
            feature_values.append(val)
            inputs_dict[feat] = val

        # 2. Compute Level 2 engineered features
        stress_sum = float(np.sum(feature_values))
        stress_std = float(np.std(feature_values, ddof=1)) if len(feature_values) > 1 else 0.0

        all_features = BASE_FEATURES + ['Environmental_Stress_Sum', 'Environmental_Stress_Std']
        row_values = feature_values + [stress_sum, stress_std]

        # 3. Model Inference (Level 2: Target District Flood Risk Probability)
        input_df = pd.DataFrame([row_values], columns=all_features)
        pred_raw = model.predict(input_df)[0]
        # Bound risk between 0.0 and 1.0
        target_risk = float(np.clip(pred_raw, 0.01, 0.99))

        # 4. Extract Resource Constraints & Sector Parameters
        total_boats = max(0, int(form_data.get('total_boats', 50)))
        total_medical = max(0, int(form_data.get('total_medical', 30)))
        total_food = max(0, int(form_data.get('total_food', 2500)))
        target_population = max(1000, int(form_data.get('target_population', 120000)))
        target_sector_name = form_data.get('target_sector_name', 'District Alpha (Target District)').strip()
        if not target_sector_name:
            target_sector_name = 'District Alpha (Target District)'

        # 5. Define 3 Sectors (Target + 2 Simulated Sectors per Problem Statement)
        # Sector B: 58% risk, simulated urban center
        # Sector C: 25% risk, simulated rural plain
        sectors = [
            {
                'id': 'sector_a',
                'name': target_sector_name,
                'type': 'Evaluated Operational Zone',
                'population': target_population,
                'risk_score': target_risk,
                'risk_pct': round(target_risk * 100, 2),
                'status': get_operational_status(target_risk)
            },
            {
                'id': 'sector_b',
                'name': 'Sector Bravo (Urban Estuary)',
                'type': 'Simulated Metro District',
                'population': 150000,
                'risk_score': 0.58,
                'risk_pct': 58.00,
                'status': get_operational_status(0.58)
            },
            {
                'id': 'sector_c',
                'name': 'Sector Charlie (Upstream Basin)',
                'type': 'Simulated Rural Plain',
                'population': 80000,
                'risk_score': 0.25,
                'risk_pct': 25.00,
                'status': get_operational_status(0.25)
            }
        ]

        # 6. Level 3 Decision Engine: Weighted Impact = Risk Score * Sector Population
        impact_weights = [s['risk_score'] * s['population'] for s in sectors]
        total_impact = sum(impact_weights)

        for i, s in enumerate(sectors):
            s['impact_weight'] = round(impact_weights[i], 1)
            s['weight_pct'] = round((impact_weights[i] / total_impact) * 100, 2) if total_impact > 0 else 33.33

        # 7. Proportional Resource Allocations with Exact Conservation
        boats_alloc = allocate_constrained_resources(total_boats, impact_weights)
        med_alloc = allocate_constrained_resources(total_medical, impact_weights)
        food_alloc = allocate_constrained_resources(total_food, impact_weights)

        for i, s in enumerate(sectors):
            s['boats'] = boats_alloc[i]
            s['medical'] = med_alloc[i]
            s['food'] = food_alloc[i]
            s['boats_pct'] = round((boats_alloc[i] / total_boats) * 100, 1) if total_boats > 0 else 0
            s['med_pct'] = round((med_alloc[i] / total_medical) * 100, 1) if total_medical > 0 else 0
            s['food_pct'] = round((food_alloc[i] / total_food) * 100, 1) if total_food > 0 else 0

        # Totals for validation banner
        totals = {
            'total_boats': total_boats,
            'allocated_boats': sum(boats_alloc),
            'total_medical': total_medical,
            'allocated_medical': sum(med_alloc),
            'total_food': total_food,
            'allocated_food': sum(food_alloc),
            'total_population': sum(s['population'] for s in sectors),
            'avg_risk': round(np.mean([s['risk_score'] for s in sectors]) * 100, 2)
        }

        results = {
            'target_risk': target_risk,
            'target_risk_pct': round(target_risk * 100, 2),
            'target_status': sectors[0]['status'],
            'stress_sum': round(stress_sum, 2),
            'stress_std': round(stress_std, 4),
            'sectors': sectors,
            'totals': totals
        }

        # If AJAX request, return JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': True, 'results': results})

        # Regular form submission renders page with results
        resources = {
            'total_boats': total_boats,
            'total_medical': total_medical,
            'total_food': total_food,
            'target_population': target_population,
            'target_sector_name': target_sector_name
        }

        return render_template(
            'index.html',
            base_features=BASE_FEATURES,
            feature_categories=FEATURE_CATEGORIES,
            inputs=inputs_dict,
            resources=resources,
            results=results
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 500
        return render_template(
            'index.html',
            base_features=BASE_FEATURES,
            feature_categories=FEATURE_CATEGORIES,
            inputs={feat: 5 for feat in BASE_FEATURES},
            resources={
                'total_boats': 50,
                'total_medical': 30,
                'total_food': 2500,
                'target_population': 120000,
                'target_sector_name': 'District Alpha (Target District)'
            },
            results=None,
            error=str(e)
        )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

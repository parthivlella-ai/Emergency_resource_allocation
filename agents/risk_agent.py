"""
Risk Prediction Agent
Wraps the trained LightGBM flood risk model, validates feature vectors,
computes engineered features, and assigns operational risk levels.
"""
import os
import joblib
import numpy as np
import pandas as pd
import logging
from config import Config

logger = logging.getLogger(__name__)

BASE_FEATURES = [
    'MonsoonIntensity', 'TopographyDrainage', 'RiverManagement', 'Deforestation',
    'Urbanization', 'ClimateChange', 'DamsQuality', 'Siltation', 'AgriculturalPractices',
    'Encroachments', 'IneffectiveDisasterPreparedness', 'DrainageSystems', 'CoastalVulnerability',
    'Landslides', 'Watersheds', 'DeterioratingInfrastructure', 'PopulationScore',
    'WetlandLoss', 'InadequatePlanning', 'PoliticalFactors'
]

class RiskAgent:
    def __init__(self, model_path=None):
        path = model_path or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'flood_risk_model.pkl')
        try:
            self.model = joblib.load(path)
            logger.info("Risk Prediction Agent loaded trained LightGBM model successfully.")
        except Exception as e:
            logger.error(f"Error loading trained ML model from {path}: {e}")
            self.model = None

    def predict_risk(self, feat_dict):
        """
        Runs LightGBM inference with dynamic engineered features:
        Environmental_Stress_Sum and Environmental_Stress_Std.
        """
        if self.model is None:
            return 0.50

        try:
            values = [float(feat_dict.get(k, 7.0)) for k in BASE_FEATURES]
            stress_sum = float(np.sum(values))
            stress_std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0

            all_feats = BASE_FEATURES + ['Environmental_Stress_Sum', 'Environmental_Stress_Std']
            row_values = values + [stress_sum, stress_std]
            input_df = pd.DataFrame([row_values], columns=all_feats)

            pred_raw = self.model.predict(input_df)[0]
            return float(np.clip(pred_raw, 0.01, 0.99))
        except Exception as e:
            logger.error(f"Prediction inference error: {e}")
            return 0.50

    def evaluate_zones(self, zones):
        """
        Evaluates flood probabilities across all operational zones.
        """
        for z in zones:
            score = self.predict_risk(z.get("feats", {}))
            z["risk_score"] = score
            z["risk_pct"] = round(score * 100, 1)

            if score >= Config.ACTION_THRESHOLDS['critical']:
                z["risk_level"] = "CRITICAL"
                z["action_tier"] = "IMMEDIATE DEPLOYMENT"
                z["status_badge"] = "critical"
                z["status_color"] = "#ef4444"
            elif score >= Config.ACTION_THRESHOLDS['high']:
                z["risk_level"] = "HIGH"
                z["action_tier"] = "PRE-POSITION RESOURCES"
                z["status_badge"] = "alert"
                z["status_color"] = "#f59e0b"
            elif score >= Config.ACTION_THRESHOLDS['moderate']:
                z["risk_level"] = "MODERATE"
                z["action_tier"] = "PREPARE & MONITOR"
                z["status_badge"] = "moderate"
                z["status_color"] = "#3b82f6"
            else:
                z["risk_level"] = "LOW"
                z["action_tier"] = "MONITOR"
                z["status_badge"] = "standby"
                z["status_color"] = "#10b981"

        return zones

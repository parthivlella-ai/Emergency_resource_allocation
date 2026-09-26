import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'emergency-command-center-secret-key-2026')
    
    # Database Configuration: PostgreSQL is preferred; falls back gracefully to SQLite for zero-setup local dev
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        # Default local SQLite fallback for seamless execution
        base_dir = os.path.abspath(os.path.dirname(__file__))
        DATABASE_URL = f"sqlite:///{os.path.join(base_dir, 'emergency_command.db')}"
    elif DATABASE_URL.startswith("postgres://"):
        # Fix for Heroku / Render legacy postgres:// prefix
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }

    # Hackathon Priority Weights (Transparent multi-factor prioritization)
    PRIORITY_WEIGHTS = {
        'flood_risk': float(os.environ.get('WEIGHT_FLOOD_RISK', 0.40)),
        'population': float(os.environ.get('WEIGHT_POPULATION', 0.25)),
        'vulnerability': float(os.environ.get('WEIGHT_VULNERABILITY', 0.20)),
        'urgency': float(os.environ.get('WEIGHT_URGENCY', 0.15))
    }

    # Action Level Thresholds
    ACTION_THRESHOLDS = {
        'critical': 0.70,
        'high': 0.52,
        'moderate': 0.38
    }

    # Default Emergency Resources Pool
    DEFAULT_RESOURCES = {
        'total_boats': 50,
        'total_rescue_teams': 18,
        'total_ambulances': 24,
        'total_medical': 5000,
        'total_food': 12000,
        'total_water': 10000,
        'total_shelters': 400
    }

    # 1-5 Human-friendly scale to LightGBM model continuous feature scale
    # Level 1 (Very Low): 3.0, Level 2 (Low): 5.0, Level 3 (Moderate): 7.0, Level 4 (High): 10.0, Level 5 (Very High): 13.0
    HUMAN_SCALE_TO_MODEL = {
        1: 3.0,
        2: 5.0,
        3: 7.0,
        4: 10.0,
        5: 13.0
    }

    # Model scale back to nearest human scale (for UI initialization)
    @staticmethod
    def model_val_to_human_level(val):
        val = float(val)
        if val <= 3.5:
            return 1
        elif val <= 5.5:
            return 2
        elif val <= 8.0:
            return 3
        elif val <= 11.0:
            return 4
        else:
            return 5

    # Human text labels for 1-5 scale
    HUMAN_LEVEL_LABELS = {
        1: 'Very Low',
        2: 'Low',
        3: 'Moderate',
        4: 'High',
        5: 'Very High'
    }

    # Qualitative mapping for Vulnerability and Urgency
    QUALITATIVE_LEVELS = {
        'low': 0.30,
        'medium': 0.65,
        'high': 0.90
    }

    @staticmethod
    def parse_qualitative_val(val, default=0.65):
        if isinstance(val, (int, float)):
            return max(0.05, min(1.0, float(val)))
        if isinstance(val, str):
            val_str = val.strip().lower()
            if val_str in Config.QUALITATIVE_LEVELS:
                return Config.QUALITATIVE_LEVELS[val_str]
            try:
                num = float(val)
                return max(0.05, min(1.0, num))
            except ValueError:
                pass
        return default

    @staticmethod
    def num_to_qualitative_label(num):
        num = float(num)
        if num < 0.45:
            return 'Low'
        elif num < 0.78:
            return 'Medium'
        else:
            return 'High'

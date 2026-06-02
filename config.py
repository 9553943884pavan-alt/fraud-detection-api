# ============================================================
# Configuration File
# Centralized settings for the Fraud Detection API
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# SERVER CONFIGURATION
# ============================================================
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
ENV = os.getenv('ENVIRONMENT', 'development')

# ============================================================
# MODEL PATHS
# ============================================================
MODEL_PATH = os.getenv('MODEL_PATH', 'Fraud_ensemble_model.pkl')
DATA_PATH = os.getenv('DATA_PATH', 'creditcard.csv')

# ============================================================
# MODEL THRESHOLDS & CONSTANTS
# ============================================================
FRAUD_THRESHOLD = 0.30
HIGH_RISK_THRESHOLD = 0.70
MEDIUM_RISK_THRESHOLD = 0.30

# Dataset statistics for engineered features
AMOUNT_MEAN = 95.97
AMOUNT_STD = 213.40

# Base fraud rate from training data
BASE_FRAUD_RATE = 0.0017

# ============================================================
# RISK LEVEL & RECOMMENDATION MAPPING
# ============================================================
RISK_LEVELS = {
    'HIGH': {'threshold': 0.70, 'recommendation': 'BLOCK TRANSACTION'},
    'MEDIUM': {'threshold': 0.30, 'recommendation': 'MANUAL REVIEW'},
    'LOW': {'threshold': 0.0, 'recommendation': 'APPROVE TRANSACTION'}
}

# ============================================================
# LOGGING CONFIGURATION
# ============================================================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'fraud_detection_api.log')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# ============================================================
# REQUEST/RESPONSE LIMITS
# ============================================================
MAX_BULK_PREDICT_SIZE = 1000
MIN_FEATURE_COUNT = 30

# ============================================================
# PHASE 3: BACKEND IMPROVEMENTS
# ============================================================
# Rate Limiting
RATE_LIMIT_MAX_REQUESTS = int(os.getenv('RATE_LIMIT_MAX', 100))
RATE_LIMIT_WINDOW = int(os.getenv('RATE_LIMIT_WINDOW', 60))

# API Key (optional)
API_KEY = os.getenv('API_KEY', None)

# Prediction Cache
PREDICTION_CACHE_SIZE = int(os.getenv('CACHE_SIZE', 1000))

# ============================================================
# VALIDATION CONSTRAINTS
# ============================================================
VALID_FILTERS = ['all', 'fraud', 'legitimate']
FEATURE_VALUE_RANGE = (-10, 100)  # Reasonable range for normalized features

# ============================================================
# DATASET INFO (from training set)
# ============================================================
DATASET_INFO = {
    'total_transactions': 284807,
    'fraud_count': 492,
    'fraud_rate': 0.1727
}

# ============================================================
# API INFO
# ============================================================
API_VERSION = '1.0'
MODEL_VERSION = 'Weighted RF Ensemble v1.0'
MODEL_INFO = {
    'precision': 0.9239,
    'recall': 0.8673,
    'f1': 0.8947,
    'algorithm': 'Weighted RF Ensemble (W=10, W=50, W=200)'
}

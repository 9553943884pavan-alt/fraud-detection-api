# ============================================================
# Fraud Detection Flask API
# Weighted RF Ensemble (W=10, W=50, W=200)
# ============================================================

import os
import pickle
import numpy as np
import pandas as pd
import time
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from collections import defaultdict
import hashlib
import json
import config

# In-memory store for prediction history
prediction_history = []
MAX_HISTORY_SIZE = 50

# ============================================================
# LOGGING SETUP
# ============================================================
def setup_logging():
    """Configure logging to file and console."""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, config.LOG_LEVEL))
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(getattr(logging, config.LOG_LEVEL))
    file_handler.setFormatter(logging.Formatter(config.LOG_FORMAT))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, config.LOG_LEVEL))
    console_handler.setFormatter(logging.Formatter(config.LOG_FORMAT))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# In-memory stores for Phase 3
rate_limits = defaultdict(list)
prediction_cache = {}

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# ============================================================
# PHASE 3: MIDDLEWARE & HELPERS
# ============================================================
def check_rate_limit(ip):
    """Simple in-memory rate limiting."""
    now = time.time()
    # Clean up old timestamps
    rate_limits[ip] = [t for t in rate_limits[ip] if now - t < config.RATE_LIMIT_WINDOW]
    
    if len(rate_limits[ip]) >= config.RATE_LIMIT_MAX_REQUESTS:
        return False
    
    rate_limits[ip].append(now)
    return True

def get_cache_key(feature_data):
    """Generate a unique key for the feature data."""
    # Sort keys for consistency
    feat_json = json.dumps(feature_data, sort_keys=True)
    return hashlib.md5(feat_json.encode()).hexdigest()

# ============================================================
# LOAD MODEL ON STARTUP
# ============================================================
try:
    with open(config.MODEL_PATH, 'rb') as f:
        bundle = pickle.load(f)
    
    rf_w10 = bundle['rf_w10']
    rf_w50 = bundle['rf_w50']
    rf_w200 = bundle['rf_w200']
    Features = bundle['Features']     # capital F — 30 feature names
    weights = bundle['weights']
    THRESHOLD = bundle['threshold']    # 0.30
    
    logger.info(f"Model loaded! Features: {len(Features)}, Threshold: {THRESHOLD}")
except Exception as e:
    logger.error(f"Failed to load model: {str(e)}")
    raise

# Load dataset for transaction browser
try:
    df = pd.read_csv(config.DATA_PATH)
    df['amount_per_second'] = df['Amount'] / (df['Time'] + 1)
    df['amount_zscore'] = (df['Amount'] - config.AMOUNT_MEAN) / config.AMOUNT_STD
    logger.info(f"Dataset loaded: {len(df)} transactions")
except Exception as e:
    logger.error(f"Failed to load dataset: {str(e)}")
    raise


# ============================================================
# VALIDATION & HELPER FUNCTIONS
# ============================================================

def validate_feature_data(feature_data, required_features):
    """
    Validate that all required features are present and valid.
    
    Args:
        feature_data (dict): Feature dictionary from request
        required_features (list): List of required feature names
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not isinstance(feature_data, dict):
        return False, "feature_data must be a dictionary"
    
    missing_features = set(required_features) - set(feature_data.keys())
    if missing_features:
        return False, f"Missing features: {', '.join(sorted(missing_features))}"
    
    for feat in required_features:
        try:
            val = float(feature_data[feat])
            # Check if value is within reasonable range
            if not (config.FEATURE_VALUE_RANGE[0] <= val <= config.FEATURE_VALUE_RANGE[1]):
                logger.warning(f"Feature {feat} value {val} outside typical range")
        except (ValueError, TypeError):
            return False, f"Feature '{feat}' must be numeric, got {type(feature_data[feat]).__name__}"
    
    return True, None


def validate_bulk_request(transactions):
    """
    Validate bulk prediction request.
    
    Args:
        transactions (list): List of transaction dicts
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not isinstance(transactions, list):
        return False, "transactions must be a list"
    
    if len(transactions) == 0:
        return False, "transactions list cannot be empty"
    
    if len(transactions) > config.MAX_BULK_PREDICT_SIZE:
        return False, f"Maximum {config.MAX_BULK_PREDICT_SIZE} transactions per request"
    
    return True, None


def get_risk_level(prob):
    """Classify risk level based on probability."""
    if prob >= config.HIGH_RISK_THRESHOLD:
        return 'HIGH'
    elif prob >= config.MEDIUM_RISK_THRESHOLD:
        return 'MEDIUM'
    else:
        return 'LOW'


def get_recommendation(prob):
    """Get recommendation based on fraud probability."""
    if prob >= config.HIGH_RISK_THRESHOLD:
        return 'BLOCK TRANSACTION'
    elif prob >= config.MEDIUM_RISK_THRESHOLD:
        return 'MANUAL REVIEW'
    else:
        return 'APPROVE TRANSACTION'


def ensemble_predict_proba(X, feature_names=None):
    """
    Generate ensemble predictions from three weighted Random Forest models.
    
    Args:
        X: Feature array or DataFrame
        feature_names: List of feature names
        
    Returns:
        numpy array: Fraud probabilities
    """
    if feature_names is not None:
        X = pd.DataFrame(X, columns=feature_names)
    p10  = rf_w10.predict_proba(X)[:, 1]
    p50  = rf_w50.predict_proba(X)[:, 1]
    p200 = rf_w200.predict_proba(X)[:, 1]
    return (weights['w10']  * p10 +
            weights['w50']  * p50 +
            weights['w200'] * p200)


def get_shap_explanation(X_row):
    """
    Approximate SHAP using RF W=10 feature importances.
    Returns top 3 features with direction and contribution.
    
    Args:
        X_row: Single feature row as numpy array
        
    Returns:
        dict: SHAP explanation with top features
    """
    importances = rf_w10.feature_importances_
    feat_imp = sorted(
        zip(Features, importances),
        key=lambda x: x[1], reverse=True
    )[:3]

    prob = ensemble_predict_proba(X_row, Features)[0]
    base = config.BASE_FRAUD_RATE

    top_features = []
    for feat, imp in feat_imp:
        contribution = imp * (prob - base)
        direction = 'toward_fraud' if contribution > 0 else 'away_from_fraud'
        top_features.append({
            'feature': feat,
            'shap_value': float(abs(contribution)), # Increased precision
            'direction': direction,
            'raw_value': round(float(X_row[0][Features.index(feat)]), 4),
            'importance': float(imp) # Added base importance for context
        })

    return {
        'top_features': top_features,
        'base_value': float(base)
    }


# ============================================================
# ROUTES
# ============================================================

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    Returns service status and basic info.
    """
    return jsonify({
        'status': 'healthy',
        'service': 'Fraud Detection API',
        'version': config.API_VERSION,
        'model_version': config.MODEL_VERSION,
        'timestamp': time.time()
    }), 200


@app.route('/')
def index():
    """Serve the frontend."""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error serving index: {str(e)}")
        return jsonify({'error': 'Failed to load frontend'}), 500


@app.route('/prediction_history', methods=['GET'])
def get_prediction_history():
    """Return the recent prediction history."""
    return jsonify({
        'predictions': prediction_history,
        'count': len(prediction_history)
    }), 200


# ------------------------------------------------------------
# GET /get_transaction
# Fetch a random (or specific) transaction from dataset
# ------------------------------------------------------------
@app.route('/get_transaction', methods=['GET'])
def get_transaction():
    try:
        filter_type = request.args.get('filter', 'all')
        idx = request.args.get('idx', None)
        
        # Validate filter type
        if filter_type not in config.VALID_FILTERS:
            logger.warning(f"Invalid filter type: {filter_type}")
            return jsonify({'error': f"Invalid filter. Must be one of {config.VALID_FILTERS}"}), 400

        if idx is not None:
            try:
                idx = int(idx)
                if idx < 0 or idx >= len(df):
                    return jsonify({'error': f"Index {idx} out of range [0, {len(df)-1}]"}), 400
                row = df.iloc[idx]
            except ValueError:
                return jsonify({'error': "Index must be an integer"}), 400
        else:
            if filter_type == 'fraud':
                fraud_df = df[df['Class'] == 1]
                if fraud_df.empty:
                    return jsonify({'error': 'No fraud transactions available'}), 404
                row = fraud_df.sample(1).iloc[0]
            elif filter_type == 'legitimate':
                legit_df = df[df['Class'] == 0]
                if legit_df.empty:
                    return jsonify({'error': 'No legitimate transactions available'}), 404
                row = legit_df.sample(1).iloc[0]
            else:
                row = df.sample(1).iloc[0]

        feature_data = {feat: round(float(row[feat]), 6) for feat in Features}
        
        response = {
            'transaction_id': int(row.name),
            'amount': round(float(row['Amount']), 2),
            'time': round(float(row['Time']), 0),
            'true_label': int(row['Class']),
            'feature_data': feature_data
        }
        
        logger.debug(f"Fetched transaction {int(row.name)}")
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Error in get_transaction: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


# ------------------------------------------------------------
# POST /predict
# Single transaction prediction with validation
# ------------------------------------------------------------
@app.route('/predict', methods=['POST'])
def predict():
    start = time.time()
    
    # Rate Limiting
    if not check_rate_limit(request.remote_addr):
        return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429
    
    # API Key Auth (if configured)
    if config.API_KEY:
        provided_key = request.headers.get('X-API-Key')
        if provided_key != config.API_KEY:
            return jsonify({'error': 'Unauthorized: Valid API key required'}), 401
    
    try:
        data = request.get_json()
        
        if not data:
            logger.warning("Empty request body received")
            return jsonify({'error': 'Request body must be JSON'}), 400
            
        # Check Cache
        cache_key = get_cache_key(data.get('feature_data', {}))
        if cache_key in prediction_cache:
            logger.info("Serving cached prediction")
            cached_res = prediction_cache[cache_key].copy()
            cached_res['cached'] = True
            cached_res['latency_ms'] = round((time.time() - start) * 1000, 2)
            return jsonify(cached_res), 200
        
        # Validate feature_data presence
        if 'feature_data' not in data:
            return jsonify({'error': 'Missing required field: feature_data'}), 400
        
        # Validate feature data
        is_valid, error_msg = validate_feature_data(data['feature_data'], Features)
        if not is_valid:
            logger.warning(f"Validation error: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        # Build feature array in correct order
        X = np.array([[data['feature_data'][f] for f in Features]])
        
        # Predict
        prob = float(ensemble_predict_proba(X, Features)[0])
        decision = 'FRAUD' if prob >= THRESHOLD else 'LEGITIMATE'
        risk = get_risk_level(prob)
        recommend = get_recommendation(prob)
        shap_info = get_shap_explanation(X)
        
        latency_ms = round((time.time() - start) * 1000, 2)
        
        response = {
            'decision': decision,
            'probability': round(prob, 4),
            'probability_pct': round(prob * 100, 2),
            'confidence': risk,
            'threshold': THRESHOLD,
            'risk_level': risk,
            'recommendation': recommend,
            'transaction': {
                'amount': data.get('amount', 0),
                'time': data.get('time', 0),
                'hour_of_day': int(data.get('time', 0) // 3600 % 24),
                'true_label': data.get('true_label', -1)
            },
            'shap_explanation': shap_info,
            'latency_ms': latency_ms,
            'model_version': config.MODEL_VERSION
        }
        
        logger.info(f"Prediction: {decision} (prob={prob:.4f}, latency={latency_ms}ms)")
        
        # Store in history
        history_item = {
            'timestamp': time.time(),
            'decision': decision,
            'probability': round(prob, 4),
            'amount': data.get('amount', 0),
            'risk_level': risk
        }
        prediction_history.insert(0, history_item)
        if len(prediction_history) > MAX_HISTORY_SIZE:
            prediction_history.pop()
            
        # Store in cache
        if len(prediction_cache) < config.PREDICTION_CACHE_SIZE:
            response['cached'] = False
            prediction_cache[cache_key] = response
            
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error in predict: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ------------------------------------------------------------
# POST /bulk_predict
# Predict multiple transactions with validation
# ------------------------------------------------------------
@app.route('/bulk_predict', methods=['POST'])
def bulk_predict():
    start = time.time()
    
    try:
        data = request.get_json()
        
        if not data or 'transactions' not in data:
            logger.warning("Invalid bulk request format")
            return jsonify({'error': 'Request must contain transactions array'}), 400
        
        transactions = data['transactions']
        
        # Validate bulk request
        is_valid, error_msg = validate_bulk_request(transactions)
        if not is_valid:
            logger.warning(f"Bulk validation error: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        # Validate all transactions
        for i, t in enumerate(transactions):
            if 'feature_data' not in t:
                return jsonify({'error': f"Transaction {i} missing feature_data"}), 400
            
            is_valid, error_msg = validate_feature_data(t['feature_data'], Features)
            if not is_valid:
                return jsonify({'error': f"Transaction {i}: {error_msg}"}), 400
        
        # Build matrix
        X = np.array([
            [t['feature_data'][f] for f in Features]
            for t in transactions
        ])
        
        probs = ensemble_predict_proba(X, Features)
        decisions = ['FRAUD' if p >= THRESHOLD else 'LEGITIMATE' for p in probs]
        
        # Per-transaction results
        results = []
        for i, (prob, decision) in enumerate(zip(probs, decisions)):
            results.append({
                'id': i + 1,
                'decision': decision,
                'probability': round(float(prob), 4),
                'probability_pct': round(float(prob) * 100, 2),
                'risk_level': get_risk_level(float(prob)),
                'amount': transactions[i].get('amount', 0)
            })
        
        # Summary stats
        fraud_count = sum(1 for d in decisions if d == 'FRAUD')
        legit_count = len(decisions) - fraud_count
        high_risk = sum(1 for p in probs if p >= config.HIGH_RISK_THRESHOLD)
        medium_risk = sum(1 for p in probs if config.MEDIUM_RISK_THRESHOLD <= p < config.HIGH_RISK_THRESHOLD)
        low_risk = sum(1 for p in probs if p < config.MEDIUM_RISK_THRESHOLD)
        latency_ms = round((time.time() - start) * 1000, 2)
        
        response = {
            'summary': {
                'total_transactions': len(transactions),
                'fraud_count': fraud_count,
                'legitimate_count': legit_count,
                'fraud_percentage': round(fraud_count / len(transactions) * 100, 2),
                'average_fraud_probability': round(float(np.mean(probs)) * 100, 2),
                'risk_distribution': {
                    'high_risk': high_risk,
                    'medium_risk': medium_risk,
                    'low_risk': low_risk
                }
            },
            'transactions': results,
            'processing_time_ms': latency_ms,
            'model_version': config.MODEL_VERSION
        }
        
        logger.info(f"Bulk prediction: {len(transactions)} transactions, {fraud_count} fraud, latency={latency_ms}ms")
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error in bulk_predict: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ------------------------------------------------------------
# GET /model_stats
# Return model performance + feature importance
# ------------------------------------------------------------
@app.route('/model_stats', methods=['GET'])
def model_stats():
    try:
        feat_imp = sorted(
            zip(Features, rf_w10.feature_importances_.tolist()),
            key=lambda x: x[1], reverse=True
        )
        
        response = {
            'performance': {
                'precision': config.MODEL_INFO['precision'],
                'recall': config.MODEL_INFO['recall'],
                'f1': config.MODEL_INFO['f1'],
                'threshold': THRESHOLD,
                'algorithm': config.MODEL_INFO['algorithm']
            },
            'top_features': [
                {'feature': f, 'importance': round(imp, 4)}
                for f, imp in feat_imp[:10]
            ],
            'dataset_info': config.DATASET_INFO,
            'ensemble_weights': {
                'RF_W10': round(weights['w10'], 4),
                'RF_W50': round(weights['w50'], 4),
                'RF_W200': round(weights['w200'], 4)
            }
        }
        
        logger.debug("Model stats requested")
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Error in model_stats: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    logger.warning(f"404 error: {request.path}")
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    """Handle 405 errors."""
    logger.warning(f"405 error: {request.method} {request.path}")
    return jsonify({'error': 'Method not allowed'}), 405


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors."""
    logger.error(f"500 error: {str(e)}")
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================
# RUN
# ============================================================
if __name__ == '__main__':
    logger.info(f"Starting Fraud Detection API v{config.API_VERSION}")
    logger.info(f"Environment: {config.ENV}")
    logger.info(f"Server: {config.HOST}:{config.PORT}")
    
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )

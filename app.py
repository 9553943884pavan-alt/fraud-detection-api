# ============================================================
# Fraud Detection Flask API
# Weighted RF Ensemble (W=10, W=50, W=200)
# ============================================================

import os
import pickle
import numpy as np
import pandas as pd
import time
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# ============================================================
# LOAD MODEL ON STARTUP
# ============================================================
MODEL_PATH = 'Fraud_ensemble_model.pkl'
DATA_PATH  = 'creditcard.csv'

# Dataset statistics for engineered features
AMOUNT_MEAN = 95.97
AMOUNT_STD  = 213.40

# Load model bundle
with open(MODEL_PATH, 'rb') as f:
    bundle = pickle.load(f)

rf_w10    = bundle['rf_w10']
rf_w50    = bundle['rf_w50']
rf_w200   = bundle['rf_w200']
Features  = bundle['Features']     # capital F — 30 feature names
weights   = bundle['weights']
THRESHOLD = bundle['threshold']    # 0.30

# Model info (not in pkl — defined here)
MODEL_INFO = {
    'precision' : 0.9239,
    'recall'    : 0.8673,
    'f1'        : 0.8947,
    'algorithm' : 'Weighted RF Ensemble (W=10, W=50, W=200)'
}

print(f"Model loaded! Features: {len(Features)}, Threshold: {THRESHOLD}")

# Load dataset for transaction browser
df = pd.read_csv(DATA_PATH)
df['amount_per_second'] = df['Amount'] / (df['Time'] + 1)
df['amount_zscore']     = (df['Amount'] - AMOUNT_MEAN) / AMOUNT_STD
print(f"Dataset loaded: {len(df)} transactions")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_risk_level(prob):
    if prob >= 0.70:
        return 'HIGH'
    elif prob >= 0.30:
        return 'MEDIUM'
    else:
        return 'LOW'


def get_recommendation(prob):
    if prob >= 0.70:
        return 'BLOCK TRANSACTION'
    elif prob >= 0.30:
        return 'MANUAL REVIEW'
    else:
        return 'APPROVE TRANSACTION'


def ensemble_predict_proba(X, feature_names=None):
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
    """
    importances = rf_w10.feature_importances_
    feat_imp = sorted(
        zip(Features, importances),
        key=lambda x: x[1], reverse=True
    )[:3]

    prob = ensemble_predict_proba(X_row, Features)[0]
    base     = 0.0017   # Dataset fraud rate

    top_features = []
    for feat, imp in feat_imp:
        contribution = imp * (prob - base)
        direction    = 'toward_fraud' if contribution > 0 else 'away_from_fraud'
        top_features.append({
            'feature'   : feat,
            'shap_value': round(abs(contribution), 4),
            'direction' : direction,
            'raw_value' : round(float(X_row[0][Features.index(feat)]), 4)
        })

    return {
        'top_features': top_features,
        'base_value'  : base
    }


# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    """Serve the frontend."""
    return render_template('index.html')


# ------------------------------------------------------------
# GET /get_transaction
# Fetch a random (or specific) transaction from dataset
# ------------------------------------------------------------
@app.route('/get_transaction', methods=['GET'])
def get_transaction():
    filter_type = request.args.get('filter', 'all')
    idx         = request.args.get('idx', None)

    if idx is not None:
        row = df.iloc[int(idx)]
    else:
        if filter_type == 'fraud':
            row = df[df['Class'] == 1].sample(1).iloc[0]
        elif filter_type == 'legitimate':
            row = df[df['Class'] == 0].sample(1).iloc[0]
        else:
            row = df.sample(1).iloc[0]

    # Build feature dict using correct Features key
    feature_data = {feat: round(float(row[feat]), 6) for feat in Features}

    return jsonify({
        'transaction_id' : int(row.name),
        'amount'         : round(float(row['Amount']), 2),
        'time'           : round(float(row['Time']), 0),
        'true_label'     : int(row['Class']),
        'feature_data'   : feature_data
    })


# ------------------------------------------------------------
# POST /predict
# Single transaction prediction
# ------------------------------------------------------------
@app.route('/predict', methods=['POST'])
def predict():
    start = time.time()
    data  = request.get_json()

    try:
        # Build feature array in correct order — no scaling
        X = np.array([[data['feature_data'][f] for f in Features]])

        # Predict directly
        prob = float(ensemble_predict_proba(X, Features)[0])
        decision  = 'FRAUD' if prob >= THRESHOLD else 'LEGITIMATE'
        risk      = get_risk_level(prob)
        recommend = get_recommendation(prob)
        shap_info = get_shap_explanation(X)

        latency_ms = round((time.time() - start) * 1000, 2)

        return jsonify({
            'decision'        : decision,
            'probability'     : round(prob, 4),
            'probability_pct' : round(prob * 100, 2),
            'confidence'      : risk,
            'threshold'       : THRESHOLD,
            'risk_level'      : risk,
            'recommendation'  : recommend,
            'transaction'     : {
                'amount'     : data.get('amount', 0),
                'time'       : data.get('time', 0),
                'hour_of_day': int(data.get('time', 0) // 3600 % 24),
                'true_label' : data.get('true_label', -1)
            },
            'shap_explanation': shap_info,
            'latency_ms'      : latency_ms,
            'model_version'   : 'Weighted RF Ensemble v1.0'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400


# ------------------------------------------------------------
# POST /bulk_predict
# Predict multiple transactions at once
# ------------------------------------------------------------
@app.route('/bulk_predict', methods=['POST'])
def bulk_predict():
    start = time.time()
    data  = request.get_json()

    try:
        transactions = data['transactions']

        # Build matrix — no scaling
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
                'id'             : i + 1,
                'decision'       : decision,
                'probability'    : round(float(prob), 4),
                'probability_pct': round(float(prob) * 100, 2),
                'risk_level'     : get_risk_level(float(prob)),
                'amount'         : transactions[i].get('amount', 0)
            })

        # Summary stats
        fraud_count = sum(1 for d in decisions if d == 'FRAUD')
        legit_count = len(decisions) - fraud_count
        high_risk   = sum(1 for p in probs if p >= 0.70)
        medium_risk = sum(1 for p in probs if 0.30 <= p < 0.70)
        low_risk    = sum(1 for p in probs if p < 0.30)
        latency_ms  = round((time.time() - start) * 1000, 2)

        return jsonify({
            'summary': {
                'total_transactions'       : len(transactions),
                'fraud_count'              : fraud_count,
                'legitimate_count'         : legit_count,
                'fraud_percentage'         : round(fraud_count / len(transactions) * 100, 2),
                'average_fraud_probability': round(float(np.mean(probs)) * 100, 2),
                'risk_distribution'        : {
                    'high_risk'  : high_risk,
                    'medium_risk': medium_risk,
                    'low_risk'   : low_risk
                }
            },
            'transactions'      : results,
            'processing_time_ms': latency_ms,
            'model_version'     : 'Weighted RF Ensemble v1.0'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400


# ------------------------------------------------------------
# GET /model_stats
# Return model performance + feature importance
# ------------------------------------------------------------
@app.route('/model_stats', methods=['GET'])
def model_stats():
    feat_imp = sorted(
        zip(Features, rf_w10.feature_importances_.tolist()),
        key=lambda x: x[1], reverse=True
    )
    return jsonify({
        'performance': {
            'precision' : MODEL_INFO['precision'],
            'recall'    : MODEL_INFO['recall'],
            'f1'        : MODEL_INFO['f1'],
            'threshold' : THRESHOLD,
            'algorithm' : MODEL_INFO['algorithm']
        },
        'top_features': [
            {'feature': f, 'importance': round(imp, 4)}
            for f, imp in feat_imp[:10]
        ],
        'dataset_info': {
            # Hardcode REAL dataset stats, not demo CSV stats
            'total_transactions': 284807,
            'fraud_count'       : 492,
            'fraud_rate'        : 0.1727
        },
        'ensemble_weights': {
            'RF_W10' : round(weights['w10'],  4),
            'RF_W50' : round(weights['w50'],  4),
            'RF_W200': round(weights['w200'], 4)
        }
    })


# ============================================================
# RUN
# ============================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

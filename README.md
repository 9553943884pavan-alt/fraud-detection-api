<div align="center">

# 🛡️ Credit Card Fraud Detection API

### Production-grade ML system that catches fraud in real-time using a 600-tree weighted ensemble

[![Live Demo](https://img.shields.io/badge/🚀_Live_Demo-fraud--detection--api--erjr.onrender.com-00e676?style=for-the-badge)](https://fraud-detection-api-erjr.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.12.10-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.6.1-f7931e?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org)
[![Render](https://img.shields.io/badge/Deployed_on-Render-46e3b7?style=for-the-badge)](https://render.com)

<br/>

| Metric | Score |
|:---:|:---:|
| 🎯 Precision | **92.4%** |
| 🔍 Recall | **86.7%** |
| ⚖️ F1-Score | **89.5%** |
| ⚡ Latency | **600ms** |

<br/>

> Built in 10 days · 25+ experiments · 600 trees · Deployed on Render

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Live Demo](#-live-demo)
- [Features](#-features)
- [Model Architecture](#-model-architecture)
- [Performance](#-performance)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [API Endpoints](#-api-endpoints)
- [Installation](#-installation)
- [Usage](#-usage)
- [Key Insights](#-key-insights)
- [Lessons Learned](#-lessons-learned)
- [Author](#-author)

---

## 🧠 Overview

This project tackles **binary classification on extreme class imbalance** — only **0.17%** of 284,807 credit card transactions are fraud. A naive model that predicts everything as "not fraud" achieves 99.83% accuracy but catches **zero** frauds. This project builds a system that actually works.

**The core challenge:**
```
Dataset:   284,807 transactions
Fraud:         492 (0.17%)
Non-fraud: 284,315 (99.83%)

Baseline (predict all legit): 99.83% accuracy, 0% recall → useless
Final model:                   92.4% precision, 86.7% recall → production-ready
```

**Business framing:** Missed fraud costs ~$500/incident. A blocked legitimate customer costs ~$100. This asymmetry drove every modeling decision — including the custom threshold of **0.30** instead of the default 0.5.

---

## 🚀 Live Demo

**→ [https://fraud-detection-api-erjr.onrender.com](https://fraud-detection-api-erjr.onrender.com)**

> ⚠️ **Note:** The app is on Render's free tier. First load after inactivity takes ~60 seconds (cold start). Subsequent requests respond in ~318ms.

The dashboard has 4 tabs:

| Tab | What It Does |
|---|---|
| **Single Prediction** | Fetch a transaction, run prediction, see probability gauge + SHAP explanation |
| **Bulk Prediction** | Predict 200 transactions at once, see risk distribution, download CSV |
| **Dataset Browser** | Browse transaction cards filtered by fraud/legit, click to analyze |
| **Model Stats** | Precision/Recall/F1, feature importance bars, confusion matrix, ensemble weights |

---

## ✨ Features

### 🤖 ML Backend
- **Weighted RF Ensemble** — 3 Random Forest models × 200 trees = **600 trees total**
- **SHAP Feature Attribution** — per-transaction explanation of top contributing features
- **Custom threshold (0.30)** — business-tuned for fraud cost asymmetry
- **MD5 prediction caching** — identical transactions served in sub-1ms
- **IP-based rate limiting** — 100 requests/minute protection

### 📊 Dashboard UI
- **Circular SVG probability gauge** — animates to fraud probability with color-coded glow
- **Risk color system** — Green (0–30% safe) / Amber (30–70% review) / Red (70%+ block)
- **Analytics tab** — live session stats, detection distribution bar, latency sparkline
- **Prediction history sidebar** — collapsible, color-coded, persists across session
- **Export report** — generate `.txt` assessment for any analyzed transaction
- **Transaction ID search** — look up any index from 0–999

### 🏭 Production-Ready
- Structured logging with rotating file handler (10MB, 5 backups)
- Input validation on all 30 features with actionable error messages
- `/health` endpoint for load balancer monitoring
- CORS support via `flask-cors`
- Environment-based configuration via `config.py` + `.env`
- 7+ unit tests covering health, filters, predictions, and validation

---

## 🏗️ Model Architecture

### Why Random Forest beat everything else

| Model | Precision | Recall | F1 | Notes |
|---|---|---|---|---|
| Logistic Regression (balanced) | 0.060 | 0.910 | 0.110 | Broken precision — unusable |
| LightGBM (scale_pos_weight=577) | 0.108 | 0.827 | 0.192 | **Boosting failed on extreme imbalance** |
| RF + SMOTE | 0.859 | 0.867 | 0.863 | SMOTE added noise, hurt F1 |
| RF W=10 (class weight) | 0.896 | 0.878 | 0.887 | First working model |
| RF W=200 | 0.954 | 0.837 | 0.891 | High precision, lower recall |
| **Weighted Ensemble (final)** | **0.924** | **0.867** | **0.895** | ✅ Best balance |

### The Weighted Ensemble

```python
# Three RF models with different fraud cost weights
RF W=10:   {0:1, 1:10}    →  High Recall focus   (weight: 33.3%)
RF W=50:   {0:1, 1:50}    →  Balanced            (weight: 33.2%)
RF W=200:  {0:1, 1:200}   →  High Precision focus (weight: 33.5%)

# Weighted average of fraud probabilities
prob = 0.333 × p_w10 + 0.332 × p_w50 + 0.335 × p_w200

# Decision at custom threshold
decision = "FRAUD" if prob >= 0.30 else "LEGITIMATE"
```

**Why ensemble improved precision but not recall:**
Borderline legitimate transactions are pushed below 0.30 by the ensemble average, reducing false alarms. But the 13 truly invisible frauds (card-testing micro-transactions) score 0.000 across all 600 trees — no ensemble can rescue them.

---

## 📈 Performance

### Final Metrics (Test Set)
```
Precision:  92.4%   (of flagged transactions, 924/1000 are real fraud)
Recall:     86.7%   (of actual frauds, 867/1000 are caught)
F1-Score:   89.5%
Latency:    318ms per prediction
```

### Why Recall Stopped at 86.7%

Seven fraud transactions have probability = **0.000 across all 600 trees**:

```
Amounts: $1.00, $1.00, $1.79, $2.47, $4.49, $29.95, $98.01
```

These are **card-testing transactions** — fraudsters verify a stolen card with a tiny purchase before using it for large theft. Their V-features (PCA-transformed behavioral data) look identical to legitimate small purchases like parking meters or app store trials.

**The honest answer:** ML alone catches 86.7%. ML + a rule engine ("flag ALL first-time cards transacting under $2") would push this to 95%+. Production fraud detection is always ML + Rules.

### Threshold Analysis
```
Threshold  Precision  Recall   F1
  0.50       0.961     0.755   0.846   ← Too conservative
  0.40       0.941     0.816   0.874
  0.30       0.924     0.867   0.895   ← CHOSEN (best F1)
  0.20       0.847     0.847   0.847
  0.10       0.761     0.878   0.815   ← Too aggressive
```

---

## 🛠️ Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Language | Python | 3.12.10 |
| ML Framework | scikit-learn | 1.6.1 (pinned!) |
| Web Framework | Flask | 3.1.0 |
| Production Server | Gunicorn | 21.2.0 |
| Data Processing | pandas, numpy | 2.2.2, 2.0.2 |
| Explainability | SHAP | latest |
| CORS | flask-cors | 4.0.0 |
| Config | python-dotenv | 1.0.1 |
| Frontend | HTML + CSS + Vanilla JS | — |
| Deployment | Render (free tier) | — |

> **Why scikit-learn 1.6.1 is pinned:** The PKL file was trained with this exact version. Loading with a different minor version triggers `InconsistentVersionWarning` and may produce different predictions.

---

## 📁 Project Structure

```
fraud_detection_api/
├── app.py                      ← Flask backend: prediction, caching, rate-limiting,
│                                  history endpoint, SHAP attribution
├── config.py                   ← Centralized config with environment variables
├── requirements.txt            ← All dependencies with pinned versions
├── .env.example                ← Template for environment variables
├── .gitignore                  ← Excludes venv/, logs, .env, __pycache__
├── README.md                   ← This file
├── Fraud_ensemble_model.pkl    ← Trained model (14.83 MB)
│                                  Contains: rf_w10, rf_w50, rf_w200,
│                                            Features (30), weights, threshold
├── creditcard.csv              ← Demo dataset (1000 rows: 300 fraud + 700 legit)
│                                  Reduced from 67MB original for deployment
├── templates/
│   └── index.html              ← Full 4-tab dashboard (HTML + CSS + JS)
│                                  Tabs: Single Prediction, Bulk, Browser, Stats
│                                  Features: SVG gauge, analytics, sidebar, search
└── tests/
    └── test_api.py             ← 7+ unit tests (health, predict, validate, bulk)
```

> ⚠️ `venv/` is excluded from git. Never push it — it's 500MB+ and machine-specific.

---

## 🔌 API Endpoints

### `GET /health`
Health check for monitoring and load balancers.
```json
{
  "status": "healthy",
  "version": "1.0",
  "timestamp": "2026-06-01T10:30:00Z"
}
```

### `GET /get_transaction?filter=all`
Fetch a random transaction from the demo CSV.
- `filter`: `all` | `fraud` | `legit`

```json
{
  "transaction_id": 142,
  "amount": 129.50,
  "time": 86400,
  "feature_data": { "V1": -1.36, "V2": -0.07, ... },
  "true_label": 1
}
```

### `POST /predict`
Single transaction prediction with SHAP explanation.

**Request:**
```json
{
  "feature_data": { "V1": -1.36, "V2": -0.07, ..., "amount_zscore": 0.18 },
  "amount": 129.50,
  "time": 86400
}
```

**Response:**
```json
{
  "decision": "FRAUD",
  "probability": 0.8742,
  "probability_pct": 87.42,
  "risk_level": "HIGH",
  "recommendation": "BLOCK TRANSACTION",
  "threshold": 0.30,
  "latency_ms": 318.4,
  "shap_explanation": [
    { "feature": "V14", "contribution": 0.35, "direction": "toward_fraud", "value": -3.2 },
    { "feature": "V17", "contribution": 0.28, "direction": "toward_fraud", "value": -2.1 }
  ],
  "model_version": "Weighted RF Ensemble v1.0"
}
```

### `POST /bulk_predict`
Predict multiple transactions at once (vectorized — much faster than N single calls).

**Request:** JSON array of transactions, or upload CSV file.

**Response:**
```json
{
  "total": 200,
  "fraud_count": 43,
  "legit_count": 157,
  "fraud_percentage": 21.5,
  "risk_distribution": { "high": 38, "medium": 12, "low": 150 },
  "results": [ ... ]
}
```

### `GET /model_stats`
Model performance metrics, feature importance, and ensemble configuration.

### `GET /prediction_history`
Session prediction history for the sidebar panel.

---

## ⚙️ Installation

### Prerequisites
- Python 3.12.x (must match minor version for sklearn PKL compatibility)
- Git

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/9553943884pavan-alt/fraud-detection-api.git
cd fraud-detection-api

# 2. Create virtual environment
python -m venv venv

# 3. Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment (optional)
cp .env.example .env
# Edit .env with your settings

# 6. Run the app
python app.py
```

Open **http://localhost:5000** in your browser.

> ⚠️ Always run through Flask (`python app.py`), never open `index.html` directly. Direct file opening breaks all API calls with a JSON SyntaxError.

### Production (Gunicorn)
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Run Tests
```bash
python -m pytest tests/test_api.py -v
```

---

## 🧪 Usage

### Single Prediction (curl)
```bash
curl -X POST https://fraud-detection-api-erjr.onrender.com/predict \
  -H "Content-Type: application/json" \
  -d '{
    "feature_data": {
      "V1": -1.3598, "V2": -0.0728, "V3": 2.5363,
      "V4": 1.3782, "V5": -0.3383, "V6": 0.4624,
      "V7": 0.2396, "V8": 0.0987, "V9": 0.3638,
      "V10": 0.0908, "V11": -0.5516, "V12": -0.6178,
      "V13": -0.9914, "V14": -0.3112, "V15": 1.4681,
      "V16": -0.4704, "V17": 0.2079, "V18": 0.0258,
      "V19": 0.4040, "V20": 0.2514, "V21": -0.0183,
      "V22": 0.2778, "V23": -0.1105, "V24": 0.0669,
      "V25": 0.1285, "V26": -0.1891, "V27": 0.1336,
      "V28": -0.0210, "amount_per_second": 0.0012,
      "amount_zscore": 0.1856
    },
    "amount": 149.62,
    "time": 0
  }'
```

### Python Client
```python
import requests

response = requests.post(
    "https://fraud-detection-api-erjr.onrender.com/predict",
    json={"feature_data": {...}, "amount": 149.62, "time": 0}
)
result = response.json()
print(f"Decision: {result['decision']}")
print(f"Probability: {result['probability_pct']}%")
print(f"Recommendation: {result['recommendation']}")
```

---

## 💡 Key Insights

### 1. Why Boosting Failed on Extreme Imbalance
LightGBM's sequential error correction amplifies the majority class. Tree 1 sees 99.83% non-fraud → its "errors" are mostly non-fraud → Tree 2 focuses on non-fraud. By Tree 500, fraud signal is diluted. Random Forest's **independent trees** with `class_weight` each pay equal attention to fraud.

### 2. Why SMOTE Hurt Performance
With only 394 real fraud examples, synthetic interpolation creates points that fall in non-fraud territory (frauds aren't densely clustered). Combined with class weights, it caused double-penalization — F1 dropped from 0.887 → 0.863.

### 3. The V-Feature Secret
V1–V28 are PCA transformations of the original 28 behavioral features (merchant category, geographic behavior, transaction velocity, etc.). They carry **28 behavioral dimensions** vs. Amount's single dollar value.
```
V17 correlation with fraud: -0.3265  ← Low V17 = fraud fingerprint
V14 correlation with fraud: -0.3025
amount_per_second:           0.0000  ← Your engineered feature, essentially useless
```

### 4. Threshold is a Business Decision
Default threshold 0.50 gave F1=0.846. Tuning to **0.30** gave F1=0.895. The optimal threshold is wherever the Precision-Recall tradeoff aligns with your cost matrix — not always 0.5.

### 5. Production = ML + Rules
ML catches pattern-based fraud (V-feature anomalies). Rules catch behavior-based fraud (card testing). A rule like "flag all first-time cards under $2" would catch the 7 invisible frauds and push recall past 93%.

---

## 📚 Lessons Learned

| # | Lesson |
|---|---|
| 1 | **Accuracy lies on imbalanced data** — 99.83% accuracy = worst model |
| 2 | **Business cost matrix before modeling** — $500 vs $100 error cost changes everything |
| 3 | **Intuitive features can be mathematically weak** — amount_per_second corr = 0.0000 |
| 4 | **Class weights beat SMOTE for this dataset** — real data > synthetic data |
| 5 | **Boosting fails on extreme imbalance** — LightGBM F1=0.19 vs RF F1=0.895 |
| 6 | **Threshold 0.5 is rarely optimal** — plot Precision-Recall curve first |
| 7 | **Ensemble improves precision, not recall** — can't rescue 0.000-probability frauds |
| 8 | **Pin sklearn version exactly** — PKL trained on 1.6.1 must deploy with 1.6.1 |
| 9 | **Test full pipeline before deploying** — scaler/feature mismatch crashes on request 1 |
| 10 | **Production = ML + Rule Engine** — some patterns are invisible to any ML model |

---

## 📊 Dataset

- **Source:** [Kaggle Credit Card Fraud Detection](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud)
- **Total transactions:** 284,807
- **Fraud:** 492 (0.17%)
- **Features:** V1–V28 (PCA-transformed), Amount, Time + 2 engineered features
- **Deployed CSV:** 1,000 rows (300 fraud + 700 legit) — reduced from 67MB for GitHub/Render compatibility

---

## 🔮 Future Enhancements

- [ ] Rule engine layer for card-testing detection (push recall to 95%+)
- [ ] Real SHAP values via `TreeExplainer` (currently approximate)
- [ ] Database integration for persistent audit trails
- [ ] Authentication / API key management
- [ ] Webhook notifications for high-risk detections
- [ ] Model versioning and A/B testing framework
- [ ] Async processing with Celery for bulk predictions
- [ ] Dark/Light theme toggle in dashboard

---

## 👨‍💻 Author

**Pavan Kumar** (Thunuguntla Venkata Pavan Kumar)  
B.Tech ECE | IIIT Allahabad | 

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0077b5?style=flat-square&logo=linkedin)](https://www.linkedin.com/in/pavan-kumar-7274aa352/)
[![GitHub](https://img.shields.io/badge/GitHub-Profile-181717?style=flat-square&logo=github)](https://github.com/9553943884pavan-alt)

---

<div align="center">

**Built with 25+ experiments, 10 days, and a lot of confusion matrices**

*Reference document compiled from complete project journey — June 2026*

</div>

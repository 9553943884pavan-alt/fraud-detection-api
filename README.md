# Fraud Detection API

A production-ready Flask API for credit card fraud detection using a weighted ensemble of Random Forest models with explainability features.

## Features

- **Weighted Ensemble Model**: Combines three RF models (W=10, W=50, W=200) for robust predictions
- **High Accuracy**: Precision: 92.39%, Recall: 86.73%, F1: 89.47%
- **Explainability**: SHAP-based feature importance for fraud predictions
- **Batch Processing**: Predict up to 1000 transactions at once
- **Input Validation**: Comprehensive validation with clear error messages
- **Logging**: Structured logging for debugging and audit trails
- **CORS Enabled**: Cross-origin requests supported
- **Health Monitoring**: `/health` endpoint for monitoring systems

## Installation

### Prerequisites
- Python 3.8+
- pip or conda

### Setup

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd fraud_detection_api
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment (optional)**
   ```bash
   cp .env.example .env
   # Edit .env with your settings (optional)
   ```

5. **Run the API**
   ```bash
   python app.py
   ```

   Server will start at `http://localhost:5000`

## API Endpoints

### Health Check
```bash
GET /health
```
Returns service status and version info.

**Response:**
```json
{
  "status": "healthy",
  "service": "Fraud Detection API",
  "version": "1.0",
  "model_version": "Weighted RF Ensemble v1.0",
  "timestamp": 1706000000.000
}
```

### Get Transaction
```bash
GET /get_transaction?filter=all&idx=optional_index
```
Fetch a transaction from the dataset.

**Parameters:**
- `filter` (optional): `all`, `fraud`, `legitimate` (default: `all`)
- `idx` (optional): Specific transaction index

**Response:**
```json
{
  "transaction_id": 12345,
  "amount": 95.50,
  "time": 43200,
  "true_label": 0,
  "feature_data": {
    "V1": -0.234,
    "V2": 0.456,
    ...
  }
}
```

### Predict (Single Transaction)
```bash
POST /predict
Content-Type: application/json
```

**Request:**
```json
{
  "feature_data": {
    "V1": -0.234,
    "V2": 0.456,
    ...
    "Amount": 95.50,
    "Time": 43200
  },
  "amount": 95.50,
  "time": 43200,
  "true_label": 0
}
```

**Response:**
```json
{
  "decision": "LEGITIMATE",
  "probability": 0.1234,
  "probability_pct": 12.34,
  "risk_level": "LOW",
  "recommendation": "APPROVE TRANSACTION",
  "threshold": 0.30,
  "transaction": {
    "amount": 95.50,
    "time": 43200,
    "hour_of_day": 12,
    "true_label": 0
  },
  "shap_explanation": {
    "top_features": [
      {
        "feature": "V4",
        "shap_value": 0.0234,
        "direction": "away_from_fraud",
        "raw_value": 1.234
      }
    ],
    "base_value": 0.0017
  },
  "latency_ms": 15.32,
  "model_version": "Weighted RF Ensemble v1.0"
}
```

### Bulk Predict
```bash
POST /bulk_predict
Content-Type: application/json
```

**Request:**
```json
{
  "transactions": [
    {
      "feature_data": { ... },
      "amount": 95.50,
      "time": 43200
    },
    ...
  ]
}
```

**Response:**
```json
{
  "summary": {
    "total_transactions": 100,
    "fraud_count": 5,
    "legitimate_count": 95,
    "fraud_percentage": 5.0,
    "average_fraud_probability": 8.5,
    "risk_distribution": {
      "high_risk": 3,
      "medium_risk": 8,
      "low_risk": 89
    }
  },
  "transactions": [
    {
      "id": 1,
      "decision": "LEGITIMATE",
      "probability": 0.1234,
      "probability_pct": 12.34,
      "risk_level": "LOW",
      "amount": 95.50
    }
  ],
  "processing_time_ms": 125.45,
  "model_version": "Weighted RF Ensemble v1.0"
}
```

### Model Statistics
```bash
GET /model_stats
```

**Response:**
```json
{
  "performance": {
    "precision": 0.9239,
    "recall": 0.8673,
    "f1": 0.8947,
    "threshold": 0.30,
    "algorithm": "Weighted RF Ensemble (W=10, W=50, W=200)"
  },
  "top_features": [
    {
      "feature": "V4",
      "importance": 0.0956
    },
    ...
  ],
  "dataset_info": {
    "total_transactions": 284807,
    "fraud_count": 492,
    "fraud_rate": 0.1727
  },
  "ensemble_weights": {
    "RF_W10": 0.3,
    "RF_W50": 0.3,
    "RF_W200": 0.4
  }
}
```

## Configuration

Edit `.env` to customize settings:

```bash
# Server
HOST=0.0.0.0
PORT=5000
ENVIRONMENT=production
DEBUG=False

# Logging
LOG_LEVEL=INFO
LOG_FILE=fraud_detection_api.log

# Paths
MODEL_PATH=Fraud_ensemble_model.pkl
DATA_PATH=creditcard.csv
```

## Error Handling

The API returns standard HTTP status codes with error messages:

- **400 Bad Request**: Invalid input or missing required fields
- **404 Not Found**: Endpoint not found
- **405 Method Not Allowed**: Invalid HTTP method
- **500 Internal Server Error**: Unexpected server error

**Error Response Example:**
```json
{
  "error": "Missing features: V5, V10, V15"
}
```

## Validation Rules

### Feature Data
- All 30 features must be provided
- Values must be numeric (float or int)
- Values should be in range [-10, 100] (normalized features)

### Bulk Predictions
- Maximum 1000 transactions per request
- Each transaction must have complete feature data
- Empty transaction list not allowed

## Logging

Logs are written to `fraud_detection_api.log` with rotation (10MB files, 5 backups).

Log format: `TIMESTAMP - MODULE - LEVEL - MESSAGE`

Example logs:
```
2024-01-15 10:23:45,123 - root - INFO - ✓ Model loaded! Features: 30, Threshold: 0.30
2024-01-15 10:23:50,456 - root - INFO - Prediction: LEGITIMATE (prob=0.1234, latency=15.32ms)
2024-01-15 10:23:55,789 - root - WARNING - Validation error: Missing features: V5, V10
```

## Deployment

### Using Gunicorn (Production)
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Using Docker
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

Build and run:
```bash
docker build -t fraud-detection-api .
docker run -p 5000:5000 fraud-detection-api
```

## Performance

- **Single Prediction**: ~15ms latency
- **Bulk Prediction** (100 transactions): ~120ms
- **Memory Usage**: ~500MB (model + dataset in memory)

## Improvements Made

✅ **Input Validation** - Comprehensive validation with clear error messages
✅ **Logging System** - Structured logging to file and console
✅ **Health Check** - `/health` endpoint for monitoring
✅ **Error Handling** - Proper HTTP status codes and error responses
✅ **Configuration** - Centralized config file with environment variables
✅ **Documentation** - Complete API documentation
✅ **CORS Support** - Cross-origin requests enabled
✅ **Code Quality** - Added docstrings and type hints

## Future Enhancements

- [ ] Database integration for audit trails
- [ ] Request rate limiting
- [ ] Authentication/Authorization
- [ ] Webhook notifications
- [ ] Model versioning
- [ ] A/B testing framework
- [ ] Caching layer
- [ ] Async processing with Celery

## License

[Your License Here]

## Support

For issues or questions, please open an issue on GitHub.

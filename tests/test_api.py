import pytest
import sys
import os
import json

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app as flask_app
import config

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client

def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'
    assert 'version' in data

def test_get_transaction_all(client):
    """Test getting any transaction."""
    response = client.get('/get_transaction?filter=all')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'feature_data' in data
    assert 'amount' in data

def test_get_transaction_fraud(client):
    """Test getting a fraud transaction."""
    response = client.get('/get_transaction?filter=fraud')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['true_label'] == 1

def test_get_transaction_invalid_filter(client):
    """Test invalid filter handling."""
    response = client.get('/get_transaction?filter=invalid')
    assert response.status_code == 400

def test_predict_standard(client):
    """Test single prediction with valid data."""
    # First get a valid transaction
    tx_res = client.get('/get_transaction?filter=all')
    tx_data = json.loads(tx_res.data)
    
    predict_res = client.post('/predict', 
                           json={'feature_data': tx_data['feature_data'], 
                                 'amount': tx_data['amount']},
                           content_type='application/json')
    assert predict_res.status_code == 200
    p_data = json.loads(predict_res.data)
    assert 'decision' in p_data
    assert 'probability' in p_data

def test_predict_missing_data(client):
    """Test prediction with missing feature data."""
    response = client.post('/predict', json={'amount': 100})
    assert response.status_code == 400

def test_bulk_predict(client):
    """Test bulk prediction."""
    tx_res = client.get('/get_transaction?filter=all')
    tx_data = json.loads(tx_res.data)
    
    bulk_data = {
        'transactions': [
            {'feature_data': tx_data['feature_data'], 'amount': tx_data['amount']},
            {'feature_data': tx_data['feature_data'], 'amount': 50}
        ]
    }
    response = client.post('/bulk_predict', json=bulk_data)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['summary']['total_transactions'] == 2

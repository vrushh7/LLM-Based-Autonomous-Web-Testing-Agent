import os
import requests


def test_health_endpoint():
    """Check the backend /health endpoint returns the expected fields.

    Uses BACKEND_URL env var if set, otherwise defaults to http://localhost:8001
    """
    base = os.getenv("BACKEND_URL", "http://localhost:8001")
    resp = requests.get(f"{base}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert 'status' in data
    assert 'llm_available' in data
    assert 'message' in data

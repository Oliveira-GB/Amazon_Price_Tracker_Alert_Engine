
from fastapi.testclient import TestClient


class TestAPIIntegration:
    def test_health_endpoint(self):
        from api.main import app

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "env" in data

    def test_ready_endpoint(self):
        from api.main import app

        client = TestClient(app)
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

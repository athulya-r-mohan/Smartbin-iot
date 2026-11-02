import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.crud import calculate_status

# Test database setup (SQLite in-memory)
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def run_around_tests():
    # Setup fresh tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

def test_status_calculation():
    """Verify status thresholds: Low (<50%), Medium (50-74%), Full (75-79%), Danger (>=80%)"""
    assert calculate_status(20, True) == "LOW"
    assert calculate_status(49, True) == "LOW"
    assert calculate_status(50, True) == "MEDIUM"
    assert calculate_status(74, True) == "MEDIUM"
    assert calculate_status(75, True) == "FULL"
    assert calculate_status(79, True) == "FULL"
    assert calculate_status(80, True) == "DANGER"
    assert calculate_status(95, True) == "DANGER"
    assert calculate_status(50, False) == "INVALID"

def test_create_and_get_reading():
    """Test creating a sensor reading and retrieving it"""
    payload = {
        "distance_cm": 14.5,
        "fill_percentage": 25,
        "is_valid": True,
        "source": "TEST"
    }
    response = client.post("/api/readings", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["fill_percentage"] == 25
    assert data["status"] == "LOW"
    assert data["distance_cm"] == 14.5
    assert "id" in data
    assert "timestamp" in data

def test_danger_status_at_80_percent():
    """Test that fill percentage >= 80% triggers DANGER status"""
    payload = {
        "distance_cm": 4.2,
        "fill_percentage": 82,
        "is_valid": True,
        "source": "ESP32"
    }
    response = client.post("/api/readings", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["fill_percentage"] == 82
    assert data["status"] == "DANGER"

def test_latest_reading_and_stats():
    """Test latest reading retrieval and aggregation statistics"""
    readings = [
        {"distance_cm": 15.0, "fill_percentage": 20, "is_valid": True},
        {"distance_cm": 10.0, "fill_percentage": 55, "is_valid": True},
        {"distance_cm": 5.0, "fill_percentage": 85, "is_valid": True},
    ]
    for r in readings:
        client.post("/api/readings", json=r)

    # Check latest
    latest_res = client.get("/api/readings/latest")
    assert latest_res.status_code == 200
    latest_data = latest_res.json()
    assert latest_data["reading"]["fill_percentage"] == 85
    assert latest_data["reading"]["status"] == "DANGER"

    # Check stats
    stats_res = client.get("/api/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_readings"] == 3
    assert stats["danger_count"] == 1
    assert stats["medium_count"] == 1
    assert stats["low_count"] == 1
    assert stats["current_fill"] == 85
    assert stats["current_status"] == "DANGER"

    # Check history endpoint
    hist_res = client.get("/api/readings/history?limit=10")
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert len(history) == 3
    assert history[0]["fill_percentage"] == 20
    assert history[2]["fill_percentage"] == 85

    # Check delete/clear readings
    del_res = client.delete("/api/readings")
    assert del_res.status_code == 200
    assert client.get("/api/stats").json()["total_readings"] == 0

def test_update_esp32_ip_hotspot():
    """Test dynamically changing the ESP32 IP address for college hotspot use"""
    # Read initial config
    cfg_res = client.get("/api/config")
    assert cfg_res.status_code == 200

    # Update to a new mobile hotspot IP
    new_ip = "192.168.43.188"
    update_res = client.post("/api/config/esp32-ip", json={"esp32_ip": new_ip, "esp32_port": 80})
    assert update_res.status_code == 200
    updated_cfg = update_res.json()
    assert updated_cfg["esp32_ip"] == new_ip
    assert f"http://{new_ip}" in updated_cfg["target_url"]

def test_websocket_connection():
    """Test that WebSocket connects and receives initial state"""
    # Insert one reading first
    client.post("/api/readings", json={"distance_cm": 12.0, "fill_percentage": 40, "is_valid": True})

    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "initial_state"
        assert data["data"]["fill_percentage"] == 40
        assert data["data"]["status"] == "LOW"

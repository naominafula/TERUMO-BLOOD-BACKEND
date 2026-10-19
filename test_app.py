from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def get_auth_headers(username="admin", password="admin123"):
    register_response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
            "role": "admin",
        },
    )
    if register_response.status_code not in (201, 409):
        raise AssertionError(f"Registration failed: {register_response.text}")

    login_response = client.post(
        "/api/auth/login",
        json={
            "username": username,
            "password": password,
        },
    )
    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_create_hospital_and_get_list():
    headers = get_auth_headers("admin1", "admin123")
    hospital_payload = {
        "name": "City General Hospital",
        "code": "CGH-001",
        "location": "Nairobi",
        "contact_phone": "+254700000001",
        "email": "info@citygeneral.example",
        "is_active": True,
    }

    create_response = client.post("/api/hospitals", json=hospital_payload, headers=headers)
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == hospital_payload["name"]

    list_response = client.get("/api/hospitals", headers=headers)
    assert list_response.status_code == 200
    assert any(item["code"] == hospital_payload["code"] for item in list_response.json())


def test_create_donor_and_inventory_and_request():
    headers = get_auth_headers("admin2", "admin123")
    donor_payload = {
        "full_name": "Jane Doe",
        "email": "jane.doe@example.com",
        "phone": "+254712345678",
        "blood_group": "O+",
        "location": "Kisumu",
    }

    donor_response = client.post("/api/donors", json=donor_payload, headers=headers)
    assert donor_response.status_code == 201
    donor = donor_response.json()
    assert donor["full_name"] == donor_payload["full_name"]

    inventory_payload = {
        "blood_group": "O+",
        "component": "whole_blood",
        "batch_number": "BATCH-TEST-01",
        "units": 120,
        "expiry_date": "2027-01-15",
    }
    inventory_response = client.post("/api/inventory", json=inventory_payload, headers=headers)
    assert inventory_response.status_code == 201
    inventory = inventory_response.json()
    assert inventory["batch_number"] == inventory_payload["batch_number"]

    hospital_payload = {
        "name": "Mombasa Referral Hospital",
        "code": "MRH-001",
        "location": "Mombasa",
        "contact_phone": "+254711111111",
        "email": "support@mombasareferral.example",
        "is_active": True,
    }
    hospital_response = client.post("/api/hospitals", json=hospital_payload, headers=headers)
    assert hospital_response.status_code == 201
    hospital_id = hospital_response.json()["id"]

    request_payload = {
        "hospital_id": hospital_id,
        "blood_group": "O+",
        "component": "whole_blood",
        "units_needed": 20,
        "priority": "high",
        "notes": "Urgent surgery support.",
    }
    request_response = client.post("/api/blood-requests", json=request_payload, headers=headers)
    assert request_response.status_code == 201
    request = request_response.json()
    assert request["units_needed"] == 20


def test_distribution_and_alerts_route():
    headers = get_auth_headers("admin3", "admin123")
    hospital_payload = {
        "name": "Nakuru General Hospital",
        "code": "NGH-015",
        "location": "Nakuru",
        "contact_phone": "+254722222222",
        "email": "ops@nakurugeneral.example",
        "is_active": True,
    }
    hospital_response = client.post("/api/hospitals", json=hospital_payload, headers=headers)
    assert hospital_response.status_code == 201, hospital_response.text
    hospital_id = hospital_response.json()["id"]

    inventory_payload = {
        "blood_group": "A+",
        "component": "plasma",
        "batch_number": "BATCH-ALERT-05",
        "units": 12,
        "expiry_date": "2026-10-30",
    }
    inventory_response = client.post("/api/inventory", json=inventory_payload, headers=headers)
    assert inventory_response.status_code == 201, inventory_response.text
    inventory_id = inventory_response.json()["id"]

    request_payload = {
        "hospital_id": hospital_id,
        "blood_group": "A+",
        "component": "plasma",
        "units_needed": 6,
        "priority": "medium",
        "notes": "Routine plasma request.",
    }
    request_response = client.post("/api/blood-requests", json=request_payload, headers=headers)
    assert request_response.status_code == 201, request_response.text
    request_id = request_response.json()["id"]

    distribution_payload = {
        "request_id": request_id,
        "inventory_id": inventory_id,
        "hospital_id": hospital_id,
        "units_dispatched": 6,
        "recipient_reference": "RX-9001",
        "notes": "Plasma dispatched for patient care.",
    }
    distribution_response = client.post("/api/distributions", json=distribution_payload, headers=headers)
    assert distribution_response.status_code == 201
    assert distribution_response.json()["status"] == "dispatched"

    alerts_response = client.get("/api/reports/alerts", headers=headers)
    assert alerts_response.status_code == 200
    data = alerts_response.json()
    assert "low_stock" in data
    assert "expiring_soon" in data

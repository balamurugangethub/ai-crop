def test_register_login_logout(client):
    r = client.post("/api/auth/register", json={"name": "Murugan", "phone": "+91 98765 43210", "pin": "4321",
                                                "village": "Thiruvaiyaru", "language": "ta"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["phone"] == "9876543210"
    assert body["user"]["language"] == "ta"
    assert "pin" not in str(body["user"]).lower() or "pin_hash" not in body["user"]

    # duplicate number
    assert client.post("/api/auth/register", json={"name": "X", "phone": "9876543210", "pin": "1111"}).json()["detail"] == "phone_exists"
    # wrong PIN
    r = client.post("/api/auth/login", json={"phone": "9876543210", "pin": "0000"})
    assert r.status_code == 401 and r.json()["detail"] == "bad_credentials"
    # right PIN
    r = client.post("/api/auth/login", json={"phone": "9876543210", "pin": "4321"})
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/me", headers=h).json()["name"] == "Murugan"
    assert client.patch("/api/me", headers=h, json={"language": "en"}).json()["language"] == "en"
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    assert client.get("/api/me", headers=h).status_code == 401


def test_validation(client):
    bad = [({"name": "", "phone": "9876500000", "pin": "1234"}, "invalid_name"),
           ({"name": "A", "phone": "12345", "pin": "1234"}, "invalid_phone"),
           ({"name": "A", "phone": "9876500001", "pin": "12"}, "invalid_pin"),
           ({"name": "A", "phone": "9876500002", "pin": "abcd"}, "invalid_pin")]
    for body, code in bad:
        r = client.post("/api/auth/register", json=body)
        assert r.status_code == 422 and r.json()["detail"] == code


def test_protected_routes_need_login(client):
    for path in ("/api/reports", "/api/me"):
        assert client.get(path).status_code == 401
    assert client.post("/api/diagnose", files={"image": ("a.jpg", b"x", "image/jpeg")}).status_code == 401

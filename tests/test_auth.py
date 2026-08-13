REGISTER_PAYLOAD = {
    "login": "adrian",
    "password": "supersecret1",
    "repeat_password": "supersecret1",
}


def test_register(client):
    resp = client.post("/auth", json=REGISTER_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["login"] == "adrian"
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_login(client):
    assert client.post("/auth", json=REGISTER_PAYLOAD).status_code == 201
    resp = client.post("/auth", json=REGISTER_PAYLOAD)
    assert resp.status_code == 409


def test_register_password_mismatch(client):
    payload = {**REGISTER_PAYLOAD, "repeat_password": "somethingelse"}
    resp = client.post("/auth", json=payload)
    assert resp.status_code == 422


def test_register_short_password(client):
    payload = {"login": "adrian", "password": "short", "repeat_password": "short"}
    resp = client.post("/auth", json=payload)
    assert resp.status_code == 422


def test_login(client):
    client.post("/auth", json=REGISTER_PAYLOAD)
    resp = client.post("/login", json={"login": "adrian", "password": "supersecret1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password(client):
    client.post("/auth", json=REGISTER_PAYLOAD)
    resp = client.post("/login", json={"login": "adrian", "password": "not-the-password"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/login", json={"login": "ghost", "password": "whatever123"})
    assert resp.status_code == 401


def test_me_returns_current_user(client, make_user):
    headers = make_user("adrian")
    resp = client.get("/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["login"] == "adrian"


def test_me_without_token(client):
    assert client.get("/me").status_code == 401


def test_me_with_garbage_token(client):
    resp = client.get("/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401

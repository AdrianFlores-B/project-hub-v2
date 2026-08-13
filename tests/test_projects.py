def create_project(client, headers, name="Demo project", description="just testing") -> int:
    resp = client.post(
        "/projects", json={"name": name, "description": description}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_create_project(client, make_user):
    headers = make_user("alice")
    resp = client.post(
        "/projects", json={"name": "My project", "description": "hello"}, headers=headers
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My project"
    assert body["description"] == "hello"
    assert "id" in body


def test_create_project_requires_auth(client):
    resp = client.post("/projects", json={"name": "Nope"})
    assert resp.status_code == 401


def test_list_projects_only_shows_accessible(client, make_user):
    alice = make_user("alice")
    bob = make_user("bob")
    p1 = create_project(client, alice, name="Alice 1")
    p2 = create_project(client, alice, name="Alice 2")
    p3 = create_project(client, bob, name="Bob 1")

    alice_ids = {p["id"] for p in client.get("/projects", headers=alice).json()}
    bob_ids = {p["id"] for p in client.get("/projects", headers=bob).json()}
    assert alice_ids == {p1, p2}
    assert bob_ids == {p3}


def test_get_project_info(client, make_user):
    alice = make_user("alice")
    project_id = create_project(client, alice, name="Readable")
    resp = client.get(f"/project/{project_id}/info", headers=alice)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Readable"


def test_get_project_info_without_access(client, make_user):
    alice = make_user("alice")
    bob = make_user("bob")
    project_id = create_project(client, alice)
    resp = client.get(f"/project/{project_id}/info", headers=bob)
    assert resp.status_code == 403


def test_get_missing_project(client, make_user):
    alice = make_user("alice")
    resp = client.get("/project/9999/info", headers=alice)
    assert resp.status_code == 404


def test_update_project_info(client, make_user):
    alice = make_user("alice")
    project_id = create_project(client, alice)
    resp = client.put(
        f"/project/{project_id}/info",
        json={"name": "Renamed", "description": "new text"},
        headers=alice,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
    assert resp.json()["description"] == "new text"


def test_partial_update_keeps_other_fields(client, make_user):
    alice = make_user("alice")
    project_id = create_project(client, alice, name="Original", description="original text")
    resp = client.put(
        f"/project/{project_id}/info", json={"description": "only this"}, headers=alice
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Original"
    assert resp.json()["description"] == "only this"


def test_outsider_cannot_update(client, make_user):
    alice = make_user("alice")
    bob = make_user("bob")
    project_id = create_project(client, alice)
    resp = client.put(f"/project/{project_id}/info", json={"name": "Hacked"}, headers=bob)
    assert resp.status_code == 403


def test_invited_participant_can_view_and_update(client, make_user):
    alice = make_user("alice")
    bob = make_user("bob")
    project_id = create_project(client, alice)

    resp = client.post(f"/project/{project_id}/invite", params={"user": "bob"}, headers=alice)
    assert resp.status_code == 201
    assert resp.json() == {"login": "bob", "role": "participant"}

    assert client.get(f"/project/{project_id}/info", headers=bob).status_code == 200
    resp = client.put(f"/project/{project_id}/info", json={"name": "By bob"}, headers=bob)
    assert resp.status_code == 200

    bob_ids = {p["id"] for p in client.get("/projects", headers=bob).json()}
    assert project_id in bob_ids


def test_participant_cannot_delete_or_invite(client, make_user):
    alice = make_user("alice")
    bob = make_user("bob")
    make_user("carol")
    project_id = create_project(client, alice)
    client.post(f"/project/{project_id}/invite", params={"user": "bob"}, headers=alice)

    assert client.delete(f"/project/{project_id}", headers=bob).status_code == 403
    resp = client.post(f"/project/{project_id}/invite", params={"user": "carol"}, headers=bob)
    assert resp.status_code == 403


def test_owner_can_delete_project(client, make_user):
    alice = make_user("alice")
    project_id = create_project(client, alice)
    resp = client.delete(f"/project/{project_id}", headers=alice)
    assert resp.status_code == 204
    assert client.get(f"/project/{project_id}/info", headers=alice).status_code == 404


def test_delete_missing_project(client, make_user):
    alice = make_user("alice")
    assert client.delete("/project/9999", headers=alice).status_code == 404


def test_invite_unknown_user(client, make_user):
    alice = make_user("alice")
    project_id = create_project(client, alice)
    resp = client.post(f"/project/{project_id}/invite", params={"user": "ghost"}, headers=alice)
    assert resp.status_code == 404


def test_invite_twice(client, make_user):
    alice = make_user("alice")
    make_user("bob")
    project_id = create_project(client, alice)
    first = client.post(f"/project/{project_id}/invite", params={"user": "bob"}, headers=alice)
    assert first.status_code == 201
    resp = client.post(f"/project/{project_id}/invite", params={"user": "bob"}, headers=alice)
    assert resp.status_code == 409

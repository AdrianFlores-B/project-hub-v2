from app.config import settings
from tests.test_projects import create_project

TOKEN_HEADER = {"X-Internal-Token": settings.internal_token}


def test_set_project_size(client, make_user):
    alice = make_user("alice")
    project_id = create_project(client, alice)

    resp = client.post(
        f"/internal/projects/{project_id}/size",
        json={"total_size_bytes": 12345},
        headers=TOKEN_HEADER,
    )
    assert resp.status_code == 204

    info = client.get(f"/project/{project_id}/info", headers=alice).json()
    assert info["total_size_bytes"] == 12345


def test_internal_endpoint_rejects_bad_token(client, make_user):
    alice = make_user("alice")
    project_id = create_project(client, alice)

    resp = client.post(
        f"/internal/projects/{project_id}/size",
        json={"total_size_bytes": 1},
        headers={"X-Internal-Token": "wrong"},
    )
    assert resp.status_code == 401

    resp = client.post(f"/internal/projects/{project_id}/size", json={"total_size_bytes": 1})
    assert resp.status_code == 401


def test_internal_endpoint_missing_project(client):
    resp = client.post(
        "/internal/projects/9999/size", json={"total_size_bytes": 1}, headers=TOKEN_HEADER
    )
    assert resp.status_code == 404


def test_negative_size_rejected(client, make_user):
    alice = make_user("alice")
    project_id = create_project(client, alice)
    resp = client.post(
        f"/internal/projects/{project_id}/size",
        json={"total_size_bytes": -5},
        headers=TOKEN_HEADER,
    )
    assert resp.status_code == 422

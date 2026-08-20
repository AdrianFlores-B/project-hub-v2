from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app import security
from app.config import settings
from tests.test_projects import create_project


@pytest.fixture()
def sent_emails(monkeypatch):
    sent = []

    def fake_send(to, project_name, join_url):
        sent.append({"to": to, "project": project_name, "url": join_url})

    monkeypatch.setattr("app.mailer.send_share_email", fake_send)
    return sent


def share(client, headers, project_id, email="friend@example.com"):
    return client.get(f"/project/{project_id}/share", params={"with": email}, headers=headers)


def test_share_sends_email_with_join_link(client, make_user, sent_emails):
    alice = make_user("alice")
    project_id = create_project(client, alice, name="Shared one")

    resp = share(client, alice, project_id, "bob@example.com")
    assert resp.status_code == 200, resp.text

    assert len(sent_emails) == 1
    mail = sent_emails[0]
    assert mail["to"] == "bob@example.com"
    assert mail["project"] == "Shared one"
    assert f"{settings.app_base_url}/join?token=" in mail["url"]


def test_share_requires_owner(client, make_user, sent_emails):
    alice = make_user("alice")
    bob = make_user("bob")
    project_id = create_project(client, alice)
    client.post(f"/project/{project_id}/invite", params={"user": "bob"}, headers=alice)

    assert share(client, bob, project_id).status_code == 403
    assert sent_emails == []


def test_share_validates_email(client, make_user, sent_emails):
    alice = make_user("alice")
    project_id = create_project(client, alice)
    assert share(client, alice, project_id, "not-an-email").status_code == 422
    assert sent_emails == []


def test_join_via_share_link(client, make_user, sent_emails):
    alice = make_user("alice")
    bob = make_user("bob")
    project_id = create_project(client, alice, name="Joinable")
    share(client, alice, project_id, "bob@example.com")

    token = sent_emails[0]["url"].split("token=")[1]
    resp = client.get("/join", params={"token": token}, headers=bob)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Joinable"

    # bob is now a participant: sees the project but cannot delete it
    bob_ids = {p["id"] for p in client.get("/projects", headers=bob).json()}
    assert project_id in bob_ids
    assert client.delete(f"/project/{project_id}", headers=bob).status_code == 403

    # clicking the link a second time is fine
    assert client.get("/join", params={"token": token}, headers=bob).status_code == 200


def test_join_requires_auth(client, make_user, sent_emails):
    alice = make_user("alice")
    project_id = create_project(client, alice)
    share(client, alice, project_id)
    token = sent_emails[0]["url"].split("token=")[1]

    assert client.get("/join", params={"token": token}).status_code == 401


def test_join_with_garbage_token(client, make_user):
    bob = make_user("bob")
    resp = client.get("/join", params={"token": "not-a-real-token"}, headers=bob)
    assert resp.status_code == 400


def test_join_with_expired_token(client, make_user):
    bob = make_user("bob")
    payload = {
        "project_id": 1,
        "purpose": "share",
        "exp": datetime.now(UTC) - timedelta(hours=1),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=security.ALGORITHM)
    assert client.get("/join", params={"token": token}, headers=bob).status_code == 400


def test_join_for_deleted_project(client, make_user, sent_emails):
    alice = make_user("alice")
    bob = make_user("bob")
    project_id = create_project(client, alice)
    share(client, alice, project_id)
    token = sent_emails[0]["url"].split("token=")[1]
    client.delete(f"/project/{project_id}", headers=alice)

    assert client.get("/join", params={"token": token}, headers=bob).status_code == 404


def test_access_token_is_not_a_share_token(client, make_user):
    bob = make_user("bob")
    access_token = bob["Authorization"].removeprefix("Bearer ")
    resp = client.get("/join", params={"token": access_token}, headers=bob)
    assert resp.status_code == 400


def test_share_token_is_not_an_access_token(client, make_user, sent_emails):
    alice = make_user("alice")
    project_id = create_project(client, alice)
    share(client, alice, project_id)
    token = sent_emails[0]["url"].split("token=")[1]

    resp = client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401

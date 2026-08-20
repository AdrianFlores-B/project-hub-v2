from app.config import settings
from tests.test_documents import pdf_file, upload
from tests.test_internal import TOKEN_HEADER
from tests.test_projects import create_project


def test_upload_over_limit_rejected(client, make_user, storage, monkeypatch):
    monkeypatch.setattr(settings, "project_size_limit_bytes", 10)
    alice = make_user("alice")
    project_id = create_project(client, alice)

    resp = upload(client, alice, project_id, pdf_file(data=b"x" * 11))
    assert resp.status_code == 413
    assert storage.objects == {}


def test_upload_counts_existing_total(client, make_user, storage, monkeypatch):
    monkeypatch.setattr(settings, "project_size_limit_bytes", 100)
    alice = make_user("alice")
    project_id = create_project(client, alice)

    # simulate the lambda having already reported 95 bytes in use
    client.post(
        f"/internal/projects/{project_id}/size",
        json={"total_size_bytes": 95},
        headers=TOKEN_HEADER,
    )

    resp = upload(client, alice, project_id, pdf_file(data=b"x" * 10))
    assert resp.status_code == 413
    assert storage.objects == {}


def test_upload_within_limit_passes(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "project_size_limit_bytes", 100)
    alice = make_user("alice")
    project_id = create_project(client, alice)

    resp = upload(client, alice, project_id, pdf_file(data=b"x" * 99))
    assert resp.status_code == 201


def test_update_over_limit_rejected(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "project_size_limit_bytes", 100)
    alice = make_user("alice")
    project_id = create_project(client, alice)
    doc_id = upload(client, alice, project_id, pdf_file(data=b"x" * 50)).json()[0]["id"]

    # lambda reported the current usage
    client.post(
        f"/internal/projects/{project_id}/size",
        json={"total_size_bytes": 50},
        headers=TOKEN_HEADER,
    )

    # replacing the 50-byte file with a 101-byte one busts the limit
    resp = client.put(
        f"/document/{doc_id}",
        files={"file": ("big.pdf", b"x" * 101, "application/pdf")},
        headers=alice,
    )
    assert resp.status_code == 413

    # replacing it with a 100-byte one is fine because the old file goes away
    resp = client.put(
        f"/document/{doc_id}",
        files={"file": ("ok.pdf", b"x" * 100, "application/pdf")},
        headers=alice,
    )
    assert resp.status_code == 200

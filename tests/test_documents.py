from tests.test_projects import create_project

PDF_BYTES = b"%PDF-1.4 fake pdf content"
DOCX_BYTES = b"PK fake docx content"


def upload(client, headers, project_id, *files):
    return client.post(f"/project/{project_id}/documents", files=list(files), headers=headers)


def pdf_file(name="report.pdf", data=PDF_BYTES):
    return ("files", (name, data, "application/pdf"))


def test_upload_single_document(client, make_user, storage):
    alice = make_user("alice")
    project_id = create_project(client, alice)

    resp = upload(client, alice, project_id, pdf_file())
    assert resp.status_code == 201, resp.text
    (doc,) = resp.json()
    assert doc["filename"] == "report.pdf"
    assert doc["content_type"] == "application/pdf"
    assert doc["size_bytes"] == len(PDF_BYTES)

    expected_key = f"projects/{project_id}/{doc['id']}/report.pdf"
    assert storage.objects[expected_key] == PDF_BYTES


def test_upload_multiple_documents(client, make_user, storage):
    alice = make_user("alice")
    project_id = create_project(client, alice)

    resp = upload(
        client,
        alice,
        project_id,
        pdf_file(),
        ("files", ("notes.docx", DOCX_BYTES, "application/octet-stream")),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body) == 2
    # content type comes from the extension, not from what the client claims
    assert body[1]["content_type"].endswith("wordprocessingml.document")
    assert len(storage.objects) == 2


def test_upload_rejects_unsupported_extension(client, make_user, storage):
    alice = make_user("alice")
    project_id = create_project(client, alice)

    resp = upload(
        client,
        alice,
        project_id,
        pdf_file(),
        ("files", ("virus.exe", b"MZ", "application/pdf")),
    )
    assert resp.status_code == 415
    # the whole batch is rejected, including the valid pdf
    assert storage.objects == {}
    assert client.get(f"/project/{project_id}/documents", headers=alice).json() == []


def test_upload_requires_project_access(client, make_user):
    alice = make_user("alice")
    bob = make_user("bob")
    project_id = create_project(client, alice)
    resp = upload(client, bob, project_id, pdf_file())
    assert resp.status_code == 403


def test_list_documents(client, make_user):
    alice = make_user("alice")
    project_id = create_project(client, alice)
    upload(client, alice, project_id, pdf_file(), pdf_file("second.pdf"))

    resp = client.get(f"/project/{project_id}/documents", headers=alice)
    assert resp.status_code == 200
    assert [d["filename"] for d in resp.json()] == ["report.pdf", "second.pdf"]


def test_download_document(client, make_user):
    alice = make_user("alice")
    project_id = create_project(client, alice)
    doc_id = upload(client, alice, project_id, pdf_file()).json()[0]["id"]

    resp = client.get(f"/document/{doc_id}", headers=alice)
    assert resp.status_code == 200
    assert resp.content == PDF_BYTES
    assert resp.headers["content-type"] == "application/pdf"
    assert 'filename="report.pdf"' in resp.headers["content-disposition"]


def test_download_requires_access(client, make_user):
    alice = make_user("alice")
    bob = make_user("bob")
    project_id = create_project(client, alice)
    doc_id = upload(client, alice, project_id, pdf_file()).json()[0]["id"]

    assert client.get(f"/document/{doc_id}", headers=bob).status_code == 403
    assert client.get("/document/9999", headers=alice).status_code == 404


def test_participant_can_download(client, make_user):
    alice = make_user("alice")
    bob = make_user("bob")
    project_id = create_project(client, alice)
    doc_id = upload(client, alice, project_id, pdf_file()).json()[0]["id"]
    client.post(f"/project/{project_id}/invite", params={"user": "bob"}, headers=alice)

    assert client.get(f"/document/{doc_id}", headers=bob).status_code == 200


def test_outsider_cannot_update_or_delete_document(client, make_user, storage):
    alice = make_user("alice")
    bob = make_user("bob")
    project_id = create_project(client, alice)
    doc_id = upload(client, alice, project_id, pdf_file()).json()[0]["id"]

    resp = client.put(
        f"/document/{doc_id}",
        files={"file": ("evil.pdf", b"%PDF-1.4 evil", "application/pdf")},
        headers=bob,
    )
    assert resp.status_code == 403
    assert client.delete(f"/document/{doc_id}", headers=bob).status_code == 403
    # the original file is untouched
    assert storage.objects[f"projects/{project_id}/{doc_id}/report.pdf"] == PDF_BYTES


def test_update_document(client, make_user, storage):
    alice = make_user("alice")
    project_id = create_project(client, alice)
    doc_id = upload(client, alice, project_id, pdf_file()).json()[0]["id"]

    new_bytes = b"%PDF-1.4 replacement"
    resp = client.put(
        f"/document/{doc_id}",
        files={"file": ("renamed.pdf", new_bytes, "application/pdf")},
        headers=alice,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "renamed.pdf"
    assert body["size_bytes"] == len(new_bytes)

    # old object replaced by the new one
    assert list(storage.objects) == [f"projects/{project_id}/{doc_id}/renamed.pdf"]
    assert client.get(f"/document/{doc_id}", headers=alice).content == new_bytes


def test_delete_document(client, make_user, storage):
    alice = make_user("alice")
    project_id = create_project(client, alice)
    doc_id = upload(client, alice, project_id, pdf_file()).json()[0]["id"]

    assert client.delete(f"/document/{doc_id}", headers=alice).status_code == 204
    assert client.get(f"/document/{doc_id}", headers=alice).status_code == 404
    assert storage.objects == {}


def test_delete_project_removes_files(client, make_user, storage):
    alice = make_user("alice")
    project_id = create_project(client, alice)
    upload(client, alice, project_id, pdf_file(), pdf_file("second.pdf"))
    assert len(storage.objects) == 2

    assert client.delete(f"/project/{project_id}", headers=alice).status_code == 204
    assert storage.objects == {}


def test_project_list_includes_documents(client, make_user):
    alice = make_user("alice")
    project_id = create_project(client, alice)
    upload(client, alice, project_id, pdf_file())

    projects = client.get("/projects", headers=alice).json()
    assert projects[0]["id"] == project_id
    assert [d["filename"] for d in projects[0]["documents"]] == ["report.pdf"]

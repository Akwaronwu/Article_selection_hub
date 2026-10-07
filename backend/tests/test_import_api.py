"""Import API tests: background jobs, dedup, RBAC, failure paths (§8, §108)."""

from sqlalchemy import select

from app import db as db_module
from app.models import AuditLog, ImportBatch, StudySource


def _create_project(client, title="Import test"):
    return client.post("/api/v1/projects", json={"title": title}).json()["id"]


def _upload(client, project_id, file_bytes, name, source="Scopus", fmt=None):
    """POST a multipart import; returns the 202 response."""
    data = {"source_database": source}
    if fmt:
        data["format"] = fmt
    return client.post(
        f"/api/v1/projects/{project_id}/studies/import",
        files={"file": (name, file_bytes, "application/octet-stream")},
        data=data,
    )


def test_import_ris_happy_path(
    client, register_user, fixture_bytes, poll_job
):
    register_user(client)
    project_id = _create_project(client)

    response = _upload(client, project_id, fixture_bytes("sample.ris"), "sample.ris")
    assert response.status_code == 202, response.text
    job = poll_job(response.json()["job_id"])
    assert job["status"] == "done", job.get("error")
    # 3 records: two titled + one DOI-only; all new to this project.
    assert job["result"]["imported"] == 3
    assert job["result"]["skipped_existing"] == 0
    assert job["result"]["rejected"] == 0

    studies = client.get(f"/api/v1/projects/{project_id}/studies").json()
    assert studies["total"] == 3
    titles = {s["title"] for s in studies["items"]}
    assert "Large Language Models for Vulnerability Detection: An Empirical Study" in titles
    assert None in titles  # DOI-only record kept, title resolved later

    # Provenance + audit recorded.
    session = db_module.get_session_factory()()
    try:
        batch_id = job["result"]["batch_id"]
        batch = session.get(ImportBatch, batch_id)
        assert batch is not None
        assert batch.source_database == "Scopus"
        assert batch.record_count == 3
        sources = session.scalars(
            select(StudySource).where(StudySource.import_batch_id == batch_id)
        ).all()
        assert len(sources) == 3
        audit = session.scalar(
            select(AuditLog).where(AuditLog.action == "studies.import")
        )
        assert audit is not None and audit.entity_id == batch_id
    finally:
        session.close()


def test_reimport_skips_existing_dois(
    client, register_user, fixture_bytes, poll_job
):
    """Re-importing the identical file must not duplicate studies (§9)."""
    register_user(client)
    project_id = _create_project(client)

    first = _upload(client, project_id, fixture_bytes("sample.ris"), "sample.ris")
    done1 = poll_job(first.json()["job_id"])
    assert done1["result"]["imported"] == 3

    second = _upload(client, project_id, fixture_bytes("sample.ris"), "sample.ris")
    done2 = poll_job(second.json()["job_id"])
    assert done2["result"]["imported"] == 0
    assert done2["result"]["skipped_existing"] == 3

    studies = client.get(f"/api/v1/projects/{project_id}/studies").json()
    assert studies["total"] == 3


def test_viewer_cannot_import_and_stranger_gets_404(
    client, make_client, register_user, fixture_bytes
):
    register_user(client)
    project_id = _create_project(client)

    viewer = make_client()
    register_user(viewer, email="viewer@example.org", name="V")
    client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": "viewer@example.org", "role": "viewer"},
    )
    denied = _upload(viewer, project_id, fixture_bytes("sample.ris"), "sample.ris")
    assert denied.status_code == 403
    assert "studies:import" in denied.json()["detail"]

    stranger = make_client()
    register_user(stranger, email="stranger@example.org", name="S")
    from_stranger = _upload(
        stranger, project_id, fixture_bytes("sample.ris"), "sample.ris"
    )
    assert from_stranger.status_code == 404
    # Reading studies still works for the viewer.
    listing = viewer.get(f"/api/v1/projects/{project_id}/studies")
    assert listing.status_code == 200
    assert listing.json()["total"] == 0


def test_unsupported_file_fails_fast_with_422(client, register_user):
    register_user(client)
    project_id = _create_project(client)
    response = _upload(client, project_id, b"\x00\x01binary junk", "mystery.xyz")
    assert response.status_code == 422
    assert "detect" in response.json()["detail"].lower()


def test_empty_file_rejected(client, register_user):
    register_user(client)
    project_id = _create_project(client)
    response = _upload(client, project_id, b"", "empty.ris")
    assert response.status_code == 422


def test_csv_missing_title_column_marks_job_failed_without_partial_data(
    client, register_user, poll_job
):
    """A parse failure rolls back completely — job failed, zero studies (§109)."""
    register_user(client)
    project_id = _create_project(client)

    bad_csv = b"Name,Price\nWidget,10\nGadget,20\n"
    response = _upload(client, project_id, bad_csv, "bad.csv", fmt="csv")
    assert response.status_code == 202
    job = poll_job(response.json()["job_id"])

    assert job["status"] == "failed"
    assert "title or DOI column" in (job["error"] or "")

    studies = client.get(f"/api/v1/projects/{project_id}/studies").json()
    assert studies["total"] == 0
    # No batch or audit row persisted for the failed run.
    session = db_module.get_session_factory()()
    try:
        assert session.scalars(select(ImportBatch)).all() == []
        assert session.scalars(
            select(AuditLog).where(AuditLog.action == "studies.import")
        ).all() == []
    finally:
        session.close()


def test_doi_list_import_creates_titleless_studies(
    client, register_user, fixture_bytes, poll_job
):
    register_user(client)
    project_id = _create_project(client)

    response = _upload(client, project_id, fixture_bytes("dois.txt"), "dois.txt")
    assert response.status_code == 202
    job = poll_job(response.json()["job_id"])
    assert job["status"] == "done", job.get("error")
    assert job["result"]["imported"] == 4
    assert job["result"]["invalid_entries"] == 1

    studies = client.get(f"/api/v1/projects/{project_id}/studies").json()
    assert all(s["title"] is None for s in studies["items"])
    assert all(s["doi"] for s in studies["items"])


def test_explicit_format_overrides_sniffing(
    client, register_user, fixture_bytes, poll_job
):
    register_user(client)
    project_id = _create_project(client)
    # .txt extension could be many things; explicit format wins.
    response = _upload(
        client, project_id, fixture_bytes("sample.ris"), "export.txt", fmt="ris"
    )
    assert response.status_code == 202
    job = poll_job(response.json()["job_id"])
    assert job["status"] == "done"
    assert job["result"]["imported"] == 3


def test_invalid_explicit_format_rejected(client, register_user):
    register_user(client)
    project_id = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/studies/import",
        files={"file": ("x.txt", b"data", "text/plain")},
        data={"format": "endnote-xml"},
    )
    assert response.status_code == 422


def test_studies_listing_pagination_and_filters(
    client, register_user, fixture_bytes, poll_job
):
    register_user(client)
    project_id = _create_project(client)
    response = _upload(client, project_id, fixture_bytes("sample.ris"), "sample.ris")
    poll_job(response.json()["job_id"])

    page1 = client.get(f"/api/v1/projects/{project_id}/studies?page=1&page_size=2").json()
    assert page1["total"] == 3
    assert len(page1["items"]) == 2
    assert page1["page"] == 1

    page2 = client.get(f"/api/v1/projects/{project_id}/studies?page=2&page_size=2").json()
    assert len(page2["items"]) == 1

    # Text search over title/abstract/DOI.
    no_hits = client.get(f"/api/v1/projects/{project_id}/studies?q=malware").json()
    assert no_hits["total"] == 0  # malware lives in the CSV fixture, not RIS
    hits = client.get(f"/api/v1/projects/{project_id}/studies?q=vulnerability").json()
    assert hits["total"] == 1

    # Status filter works; unknown status → 422 (typo protection).
    imported = client.get(
        f"/api/v1/projects/{project_id}/studies?status=IMPORTED"
    ).json()
    assert imported["total"] == 3
    bad = client.get(f"/api/v1/projects/{project_id}/studies?status=NOPE")
    assert bad.status_code == 422


def test_study_detail_and_cross_project_isolation(
    client, make_client, register_user, fixture_bytes, poll_job
):
    register_user(client)
    project_a = _create_project(client, "Project A")
    response = _upload(client, project_a, fixture_bytes("sample.ris"), "sample.ris")
    poll_job(response.json()["job_id"])

    study = client.get(f"/api/v1/projects/{project_a}/studies").json()["items"][0]
    detail = client.get(f"/api/v1/projects/{project_a}/studies/{study['id']}")
    assert detail.status_code == 200
    assert detail.json()["doi"] or detail.json()["title"]

    # The same user's other project cannot reach A's study id (anti-IDOR).
    project_b = _create_project(client, "Project B")
    assert (
        client.get(f"/api/v1/projects/{project_b}/studies/{study['id']}").status_code
        == 404
    )

    # Unauthenticated access denied.
    anon = make_client()
    assert anon.get(f"/api/v1/projects/{project_a}/studies").status_code == 401


def test_job_visibility_requires_project_membership(
    client, make_client, register_user, fixture_bytes, poll_job
):
    register_user(client)
    project_id = _create_project(client)
    response = _upload(client, project_id, fixture_bytes("dois.txt"), "dois.txt")
    job_id = response.json()["job_id"]
    assert poll_job(job_id)["status"] == "done"

    outsider = make_client()
    register_user(outsider, email="outsider@example.org", name="O")
    assert outsider.get(f"/api/v1/jobs/{job_id}").status_code == 404
    assert client.get(f"/api/v1/jobs/{job_id}").status_code == 200
    assert client.get("/api/v1/jobs/does-not-exist").status_code == 404


def test_reimport_of_identical_batch_creates_new_batch_row(
    client, register_user, fixture_bytes, poll_job
):
    """Each import is an auditable batch even when everything is skipped."""
    register_user(client)
    project_id = _create_project(client)
    first = _upload(client, project_id, fixture_bytes("sample.csv"), "sample.csv")
    assert poll_job(first.json()["job_id"])["result"]["imported"] == 2
    second = _upload(client, project_id, fixture_bytes("sample.csv"), "sample.csv")
    job = poll_job(second.json()["job_id"])
    assert job["result"]["imported"] == 0
    assert job["result"]["skipped_existing"] == 2
    assert job["result"]["rejected"] == 0

    session = db_module.get_session_factory()()
    try:
        batches = session.scalars(
            select(ImportBatch).where(ImportBatch.project_id == project_id)
        ).all()
        assert len(batches) == 2
    finally:
        session.close()


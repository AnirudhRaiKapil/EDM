import io


def auth_headers(client, email="quality@example.com") -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email, "password": "hunter2pass"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "hunter2pass"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _setup_pipeline(client, headers, csv_content: bytes) -> dict:
    workspace = client.post(
        "/api/v1/workspaces", json={"name": "quality-co", "description": ""}, headers=headers
    ).json()
    project = client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        json={"name": "data", "environment": "dev"},
        headers=headers,
    ).json()
    source = client.post(
        f"/api/v1/projects/{project['id']}/sources",
        json={"name": "people-csv", "connector_type": "csv"},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/sources/{source['id']}/upload",
        files={"file": ("people.csv", io.BytesIO(csv_content), "text/csv")},
        headers=headers,
    )
    pipeline = client.post(
        f"/api/v1/projects/{project['id']}/pipelines",
        json={
            "name": "people-pipeline",
            "source_id": source["id"],
            "output_dataset_name": "people",
            "output_layer": "silver",
            "transformations": [],
        },
        headers=headers,
    ).json()
    return pipeline


def test_blocking_failure_rejects_batch_and_keeps_old_data_published(client):
    headers = auth_headers(client)
    pipeline = _setup_pipeline(client, headers, b"name,email\nA,a@x.com\nB,b@x.com\n")

    first_job = client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers).json()
    assert first_job["status"] == "succeeded"
    dataset_id = first_job["dataset_id"]

    rule = client.post(
        f"/api/v1/catalog/datasets/{dataset_id}/quality-rules",
        json={"expectation_type": "not_null", "parameters": {"column": "email"}, "severity": "blocking"},
        headers=headers,
    )
    assert rule.status_code == 201

    # First query against the currently-published (good) data, to compare against later.
    before = client.post(
        "/api/v1/query",
        json={"dataset_id": dataset_id, "sql": "SELECT COUNT(*) AS n FROM dataset"},
        headers=headers,
    ).json()
    assert before["rows"][0]["n"] == 2

    # Re-upload bad data (a null email) onto the SAME source, then rerun the pipeline.
    source_id = pipeline["source_id"]
    client.post(
        f"/api/v1/sources/{source_id}/upload",
        files={"file": ("people2.csv", io.BytesIO(b"name,email\nA,a@x.com\nB,\n"), "text/csv")},
        headers=headers,
    )
    second_job = client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers).json()
    assert second_job["status"] == "failed"
    assert "quality" in second_job["error_message"].lower()

    runs = client.get(f"/api/v1/catalog/datasets/{dataset_id}/quality-runs", headers=headers).json()
    assert runs[0]["outcome"] == "failed"
    assert runs[0]["job_id"] == second_job["id"]

    # Previously published data must be untouched -- "prevent downstream publication".
    after = client.post(
        "/api/v1/query",
        json={"dataset_id": dataset_id, "sql": "SELECT COUNT(*) AS n FROM dataset"},
        headers=headers,
    ).json()
    assert after["rows"][0]["n"] == 2


def test_warning_severity_does_not_block_publication(client):
    headers = auth_headers(client)
    pipeline = _setup_pipeline(client, headers, b"name,email\nA,a@x.com\n")

    first_job = client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers).json()
    dataset_id = first_job["dataset_id"]

    client.post(
        f"/api/v1/catalog/datasets/{dataset_id}/quality-rules",
        json={"expectation_type": "unique", "parameters": {"column": "name"}, "severity": "warning"},
        headers=headers,
    )

    source_id = pipeline["source_id"]
    client.post(
        f"/api/v1/sources/{source_id}/upload",
        files={"file": ("dup.csv", io.BytesIO(b"name,email\nA,a@x.com\nA,a2@x.com\n"), "text/csv")},
        headers=headers,
    )
    second_job = client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers).json()
    assert second_job["status"] == "succeeded"
    assert second_job["metrics"]["qualityOutcome"] == "passed_with_warnings"
    assert second_job["metrics"]["rowsOut"] == 2

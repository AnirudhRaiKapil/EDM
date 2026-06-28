import io


def auth_headers(client, email="alerts@example.com") -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email, "password": "hunter2pass"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "hunter2pass"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _setup_pipeline(client, headers, csv_content: bytes) -> dict:
    workspace = client.post(
        "/api/v1/workspaces", json={"name": "alert-co", "description": ""}, headers=headers
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


def test_job_failure_creates_critical_alert(client):
    headers = auth_headers(client)
    pipeline = _setup_pipeline(client, headers, b"name,email\nA,a@x.com\n")
    project_id = pipeline["project_id"]

    # Pointing the pipeline's source at a connector with no file attached makes the run fail.
    bad_source = client.post(
        f"/api/v1/projects/{project_id}/sources",
        json={"name": "no-file-csv", "connector_type": "csv"},
        headers=headers,
    ).json()
    bad_pipeline = client.post(
        f"/api/v1/projects/{project_id}/pipelines",
        json={
            "name": "broken-pipeline",
            "source_id": bad_source["id"],
            "output_dataset_name": "broken",
            "output_layer": "silver",
            "transformations": [],
        },
        headers=headers,
    ).json()

    job = client.post(f"/api/v1/pipelines/{bad_pipeline['id']}/jobs", headers=headers).json()
    assert job["status"] == "failed"

    alerts = client.get(f"/api/v1/projects/{project_id}/alerts", headers=headers).json()
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "critical"
    assert alerts[0]["source_entity_type"] == "job"
    assert alerts[0]["source_entity_id"] == job["id"]
    assert alerts[0]["status"] == "open"


def test_quality_warning_creates_warning_alert_but_job_still_succeeds(client):
    headers = auth_headers(client)
    pipeline = _setup_pipeline(client, headers, b"name,email\nA,a@x.com\n")
    project_id = pipeline["project_id"]

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

    alerts = client.get(f"/api/v1/projects/{project_id}/alerts", headers=headers).json()
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "warning"
    assert alerts[0]["source_entity_id"] == second_job["id"]


def test_acknowledge_and_resolve_alert(client):
    headers = auth_headers(client)
    pipeline = _setup_pipeline(client, headers, b"name,email\nA,a@x.com\n")
    project_id = pipeline["project_id"]

    bad_pipeline = client.post(
        f"/api/v1/projects/{project_id}/pipelines",
        json={
            "name": "broken-pipeline-2",
            "source_id": pipeline["source_id"],
            "output_dataset_name": "broken2",
            "output_layer": "silver",
            "transformations": [{"type": "select_columns", "order": 0, "parameters": {"columns": ["nope"]}}],
        },
        headers=headers,
    ).json()
    client.post(f"/api/v1/pipelines/{bad_pipeline['id']}/jobs", headers=headers)

    alerts = client.get(f"/api/v1/projects/{project_id}/alerts", headers=headers).json()
    alert_id = alerts[0]["id"]

    ack = client.patch(f"/api/v1/alerts/{alert_id}", json={"status": "acknowledged"}, headers=headers)
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"

    resolve = client.patch(f"/api/v1/alerts/{alert_id}", json={"status": "resolved"}, headers=headers)
    assert resolve.json()["status"] == "resolved"

    open_only = client.get(
        f"/api/v1/projects/{project_id}/alerts", params={"status": "open"}, headers=headers
    ).json()
    assert open_only == []


def test_non_member_cannot_see_or_update_alerts(client):
    owner_headers = auth_headers(client, email="owner-alerts@example.com")
    outsider_headers = auth_headers(client, email="outsider-alerts@example.com")
    pipeline = _setup_pipeline(client, owner_headers, b"name,email\nA,a@x.com\n")
    project_id = pipeline["project_id"]

    bad_pipeline = client.post(
        f"/api/v1/projects/{project_id}/pipelines",
        json={
            "name": "broken-pipeline-3",
            "source_id": pipeline["source_id"],
            "output_dataset_name": "broken3",
            "output_layer": "silver",
            "transformations": [{"type": "select_columns", "order": 0, "parameters": {"columns": ["nope"]}}],
        },
        headers=owner_headers,
    ).json()
    client.post(f"/api/v1/pipelines/{bad_pipeline['id']}/jobs", headers=owner_headers)
    alert_id = client.get(f"/api/v1/projects/{project_id}/alerts", headers=owner_headers).json()[0]["id"]

    assert (
        client.get(f"/api/v1/projects/{project_id}/alerts", headers=outsider_headers).status_code == 404
    )
    assert (
        client.patch(
            f"/api/v1/alerts/{alert_id}", json={"status": "resolved"}, headers=outsider_headers
        ).status_code
        == 404
    )

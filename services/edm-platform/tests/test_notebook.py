import io


def auth_headers(client, email="notebook@example.com") -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email, "password": "hunter2pass"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "hunter2pass"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _setup_source(client, headers, csv_content: bytes) -> tuple[str, str]:
    workspace = client.post(
        "/api/v1/workspaces", json={"name": "notebook-co", "description": ""}, headers=headers
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
    return project["id"], source["id"]


def test_notebook_run_executes_cells_in_order_against_a_sample(client):
    headers = auth_headers(client)
    project_id, source_id = _setup_source(
        client, headers, b"name,amount\nAda,10\nLin,20\nMo,30\n"
    )

    notebook = client.post(
        f"/api/v1/projects/{project_id}/notebooks",
        json={"name": "explore", "source_id": source_id, "sample_size": 2},
        headers=headers,
    ).json()
    assert notebook["status"] == "draft"

    client.post(
        f"/api/v1/notebooks/{notebook['id']}/cells",
        json={"code": "df['amount'] = df['amount'] * 10"},
        headers=headers,
    )
    client.post(
        f"/api/v1/notebooks/{notebook['id']}/cells",
        json={"code": "print(df['amount'].sum())"},
        headers=headers,
    )

    run = client.post(f"/api/v1/notebooks/{notebook['id']}/run", headers=headers).json()
    results = run["results"]
    assert len(results) == 2
    assert results[0]["status"] == "ok"
    # sample_size=2 means only the first 2 of 3 source rows are in scope
    assert results[0]["row_count"] == 2
    assert results[1]["stdout"].strip() == "300"


def test_notebook_run_up_to_cell_stops_early(client):
    headers = auth_headers(client)
    project_id, source_id = _setup_source(client, headers, b"x\n1\n2\n")

    notebook = client.post(
        f"/api/v1/projects/{project_id}/notebooks",
        json={"name": "explore", "source_id": source_id},
        headers=headers,
    ).json()
    first_cell = client.post(
        f"/api/v1/notebooks/{notebook['id']}/cells",
        json={"code": "df['x'] = df['x'] + 1"},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/notebooks/{notebook['id']}/cells",
        json={"code": "df['x'] = df['x'] * 100"},
        headers=headers,
    )

    run = client.post(
        f"/api/v1/notebooks/{notebook['id']}/run",
        params={"up_to_cell_id": first_cell["id"]},
        headers=headers,
    ).json()
    assert len(run["results"]) == 1
    assert run["results"][0]["preview"][0]["x"] == 2


def test_notebook_run_surfaces_sandboxed_error_without_500(client):
    headers = auth_headers(client)
    project_id, source_id = _setup_source(client, headers, b"x\n1\n")

    notebook = client.post(
        f"/api/v1/projects/{project_id}/notebooks",
        json={"name": "explore", "source_id": source_id},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/notebooks/{notebook['id']}/cells",
        json={"code": "import os"},
        headers=headers,
    )

    response = client.post(f"/api/v1/notebooks/{notebook['id']}/run", headers=headers)
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "error"
    assert "not allowed" in result["error"]


def test_promote_notebook_creates_runnable_pipeline(client):
    headers = auth_headers(client)
    project_id, source_id = _setup_source(
        client, headers, b"name,amount\nAda,10\nAda,10\nLin,20\n"
    )

    notebook = client.post(
        f"/api/v1/projects/{project_id}/notebooks",
        json={"name": "dedupe-and-scale", "source_id": source_id},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/notebooks/{notebook['id']}/cells",
        json={"code": "df = df.drop_duplicates()"},
        headers=headers,
    )
    client.post(
        f"/api/v1/notebooks/{notebook['id']}/cells",
        json={"code": "df['amount'] = df['amount'] * 2"},
        headers=headers,
    )

    pipeline = client.post(
        f"/api/v1/notebooks/{notebook['id']}/promote",
        json={"output_dataset_name": "scaled_people", "output_layer": "silver"},
        headers=headers,
    ).json()
    assert pipeline["transformations"][0]["type"] == "python_code"

    job = client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers).json()
    assert job["status"] == "succeeded", job
    assert job["metrics"]["rowsIn"] == 3
    assert job["metrics"]["rowsOut"] == 2

    notebook_after = client.get(f"/api/v1/notebooks/{notebook['id']}", headers=headers).json()
    assert notebook_after["status"] == "promoted"
    assert notebook_after["promoted_pipeline_id"] == pipeline["id"]

    query = client.post(
        "/api/v1/query",
        json={"dataset_id": job["dataset_id"], "sql": "SELECT * FROM dataset ORDER BY name"},
        headers=headers,
    ).json()
    assert query["rows"][0] == {"name": "Ada", "amount": 20}
    assert query["rows"][1] == {"name": "Lin", "amount": 40}


def test_cannot_promote_notebook_with_no_cells(client):
    headers = auth_headers(client)
    project_id, source_id = _setup_source(client, headers, b"x\n1\n")
    notebook = client.post(
        f"/api/v1/projects/{project_id}/notebooks",
        json={"name": "empty", "source_id": source_id},
        headers=headers,
    ).json()

    response = client.post(
        f"/api/v1/notebooks/{notebook['id']}/promote",
        json={"output_dataset_name": "out"},
        headers=headers,
    )
    assert response.status_code == 422


def test_non_member_cannot_access_notebook(client):
    owner_headers = auth_headers(client, email="nb-owner@example.com")
    outsider_headers = auth_headers(client, email="nb-outsider@example.com")
    project_id, source_id = _setup_source(client, owner_headers, b"x\n1\n")
    notebook = client.post(
        f"/api/v1/projects/{project_id}/notebooks",
        json={"name": "private", "source_id": source_id},
        headers=owner_headers,
    ).json()

    assert (
        client.get(f"/api/v1/notebooks/{notebook['id']}", headers=outsider_headers).status_code
        == 404
    )

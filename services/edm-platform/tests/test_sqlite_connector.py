import sqlite3


def auth_headers(client, email="dbuser@example.com") -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email, "password": "hunter2pass"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "hunter2pass"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_sqlite_db(tmp_path) -> str:
    db_path = tmp_path / "legacy_app.db"
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE customers (id INTEGER, name TEXT, country TEXT)")
    connection.executemany(
        "INSERT INTO customers VALUES (?, ?, ?)",
        [(1, "Alice", "US"), (2, "Bob", "CA"), (3, "Cara", "US")],
    )
    connection.commit()
    connection.close()
    return str(db_path)


def test_sqlite_source_via_table(client, tmp_path):
    headers = auth_headers(client)
    db_path = _make_sqlite_db(tmp_path)

    workspace = client.post(
        "/api/v1/workspaces", json={"name": "legacy", "description": ""}, headers=headers
    ).json()
    project = client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        json={"name": "crm", "environment": "dev"},
        headers=headers,
    ).json()

    source = client.post(
        f"/api/v1/projects/{project['id']}/sources",
        json={
            "name": "legacy-customers-db",
            "connector_type": "sqlite",
            "connection_config": {"db_path": db_path, "table": "customers"},
        },
        headers=headers,
    )
    assert source.status_code == 201, source.text
    source = source.json()

    pipeline = client.post(
        f"/api/v1/projects/{project['id']}/pipelines",
        json={
            "name": "us-customers",
            "source_id": source["id"],
            "output_dataset_name": "us_customers",
            "output_layer": "silver",
            "transformations": [
                {"type": "filter_rows", "order": 0, "parameters": {"column": "country", "operator": "eq", "value": "US"}},
            ],
        },
        headers=headers,
    ).json()

    job = client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers).json()
    assert job["status"] == "succeeded", job
    assert job["metrics"]["rowsIn"] == 3
    assert job["metrics"]["rowsOut"] == 2


def test_sqlite_source_rejects_non_select_query(client, tmp_path):
    headers = auth_headers(client)
    db_path = _make_sqlite_db(tmp_path)

    workspace = client.post(
        "/api/v1/workspaces", json={"name": "legacy2", "description": ""}, headers=headers
    ).json()
    project = client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        json={"name": "crm", "environment": "dev"},
        headers=headers,
    ).json()

    source = client.post(
        f"/api/v1/projects/{project['id']}/sources",
        json={
            "name": "evil-source",
            "connector_type": "sqlite",
            "connection_config": {"db_path": db_path, "query": "DROP TABLE customers"},
        },
        headers=headers,
    ).json()

    pipeline = client.post(
        f"/api/v1/projects/{project['id']}/pipelines",
        json={
            "name": "evil-pipeline",
            "source_id": source["id"],
            "output_dataset_name": "evil_output",
            "output_layer": "silver",
            "transformations": [],
        },
        headers=headers,
    ).json()

    job = client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers).json()
    assert job["status"] == "failed"
    assert "SELECT" in job["error_message"]

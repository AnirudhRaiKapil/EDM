import io
import os
import tempfile

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    from app.main import app

    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


def auth_headers(client) -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": "engineer@example.com", "display_name": "Engineer", "password": "hunter2pass"},
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": "engineer@example.com", "password": "hunter2pass"}
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_golden_path_ingest_transform_query(client):
    headers = auth_headers(client)

    workspace = client.post(
        "/api/v1/workspaces", json={"name": "acme", "description": "Acme workspace"}, headers=headers
    ).json()

    project = client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        json={"name": "sales", "environment": "dev"},
        headers=headers,
    ).json()

    source = client.post(
        f"/api/v1/projects/{project['id']}/sources",
        json={"name": "customers-csv", "connector_type": "csv"},
        headers=headers,
    ).json()

    csv_content = b"Email, Name\n a@example.com , Alice \n a@example.com , Alice \n b@example.com , Bob \n"
    upload = client.post(
        f"/api/v1/sources/{source['id']}/upload",
        files={"file": ("customers.csv", io.BytesIO(csv_content), "text/csv")},
        headers=headers,
    )
    assert upload.status_code == 200
    assert upload.json()["raw_file_path"]

    pipeline = client.post(
        f"/api/v1/projects/{project['id']}/pipelines",
        json={
            "name": "standardize-customers",
            "source_id": source["id"],
            "output_dataset_name": "customers",
            "output_layer": "silver",
            "transformations": [
                {"type": "standardize", "order": 0, "parameters": {}},
                {"type": "dedupe", "order": 1, "parameters": {}},
            ],
        },
        headers=headers,
    ).json()

    job = client.post(
        f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers
    ).json()
    assert job["status"] == "succeeded", job
    assert job["metrics"]["rowsIn"] == 3
    assert job["metrics"]["rowsOut"] == 2

    datasets = client.get("/api/v1/catalog/datasets", headers=headers).json()
    assert len(datasets) == 1
    dataset_id = datasets[0]["id"]

    detail = client.get(f"/api/v1/catalog/datasets/{dataset_id}", headers=headers).json()
    column_names = {c["name"] for c in detail["schema_info"]["columns"]}
    assert column_names == {"email", "name"}

    query = client.post(
        "/api/v1/query",
        json={"dataset_id": dataset_id, "sql": "SELECT * FROM dataset ORDER BY email"},
        headers=headers,
    ).json()
    assert query["row_count"] == 2
    assert query["rows"][0]["email"] == "a@example.com"

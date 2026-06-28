import io


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


def test_json_source_with_filter_and_select(client):
    headers = auth_headers(client)

    workspace = client.post(
        "/api/v1/workspaces", json={"name": "json-co", "description": ""}, headers=headers
    ).json()
    project = client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        json={"name": "events", "environment": "dev"},
        headers=headers,
    ).json()
    source = client.post(
        f"/api/v1/projects/{project['id']}/sources",
        json={"name": "orders-json", "connector_type": "json"},
        headers=headers,
    ).json()

    json_content = (
        b'[{"order_id": 1, "amount": 50, "status": "paid"},'
        b'{"order_id": 2, "amount": 5, "status": "paid"},'
        b'{"order_id": 3, "amount": 200, "status": "refunded"}]'
    )
    upload = client.post(
        f"/api/v1/sources/{source['id']}/upload",
        files={"file": ("orders.json", io.BytesIO(json_content), "application/json")},
        headers=headers,
    )
    assert upload.status_code == 200

    pipeline = client.post(
        f"/api/v1/projects/{project['id']}/pipelines",
        json={
            "name": "high-value-paid-orders",
            "source_id": source["id"],
            "output_dataset_name": "high_value_orders",
            "output_layer": "silver",
            "transformations": [
                {"type": "filter_rows", "order": 0, "parameters": {"column": "status", "operator": "eq", "value": "paid"}},
                {"type": "filter_rows", "order": 1, "parameters": {"column": "amount", "operator": "gt", "value": 10}},
                {"type": "select_columns", "order": 2, "parameters": {"columns": ["order_id", "amount"]}},
            ],
        },
        headers=headers,
    ).json()

    job = client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers).json()
    assert job["status"] == "succeeded", job
    assert job["metrics"]["rowsIn"] == 3
    assert job["metrics"]["rowsOut"] == 1

    datasets = client.get(
        "/api/v1/catalog/datasets", params={"project_id": project["id"]}, headers=headers
    ).json()
    dataset_id = next(d["id"] for d in datasets if d["name"] == "high_value_orders")

    query = client.post(
        "/api/v1/query",
        json={"dataset_id": dataset_id, "sql": "SELECT * FROM dataset"},
        headers=headers,
    ).json()
    assert query["row_count"] == 1
    assert set(query["columns"]) == {"order_id", "amount"}
    assert query["rows"][0]["order_id"] == 1

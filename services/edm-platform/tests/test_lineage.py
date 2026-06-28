import io


def auth_headers(client, email="lineage@example.com") -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email, "password": "hunter2pass"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "hunter2pass"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_lineage_traces_source_and_pipeline_to_dataset(client):
    headers = auth_headers(client)

    workspace = client.post(
        "/api/v1/workspaces", json={"name": "lineage-co", "description": ""}, headers=headers
    ).json()
    project = client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        json={"name": "data", "environment": "dev"},
        headers=headers,
    ).json()
    source = client.post(
        f"/api/v1/projects/{project['id']}/sources",
        json={"name": "orders-csv", "connector_type": "csv"},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/sources/{source['id']}/upload",
        files={"file": ("orders.csv", io.BytesIO(b"id,amount\n1,10\n2,20\n"), "text/csv")},
        headers=headers,
    )
    pipeline = client.post(
        f"/api/v1/projects/{project['id']}/pipelines",
        json={
            "name": "orders-pipeline",
            "source_id": source["id"],
            "output_dataset_name": "orders",
            "output_layer": "silver",
            "transformations": [],
        },
        headers=headers,
    ).json()
    job = client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers).json()
    assert job["status"] == "succeeded", job
    dataset_id = job["dataset_id"]

    dataset_lineage = client.get(f"/api/v1/lineage/datasets/{dataset_id}", headers=headers).json()
    assert dataset_lineage["downstream"] == []
    upstream_pairs = {
        (e["from_entity_type"], e["from_entity_id"]) for e in dataset_lineage["upstream"]
    }
    assert ("source", source["id"]) in upstream_pairs
    assert ("pipeline", pipeline["id"]) in upstream_pairs
    assert all(e["job_id"] == job["id"] for e in dataset_lineage["upstream"])

    source_lineage = client.get(f"/api/v1/lineage/sources/{source['id']}", headers=headers).json()
    assert source_lineage["upstream"] == []
    downstream_pairs = {
        (e["to_entity_type"], e["to_entity_id"]) for e in source_lineage["downstream"]
    }
    assert ("dataset", dataset_id) in downstream_pairs

    pipeline_lineage = client.get(
        f"/api/v1/lineage/pipelines/{pipeline['id']}", headers=headers
    ).json()
    assert any(
        e["to_entity_type"] == "dataset" and e["to_entity_id"] == dataset_id
        for e in pipeline_lineage["downstream"]
    )


def test_lineage_rerun_appends_a_new_edge_per_job(client):
    headers = auth_headers(client, email="lineage2@example.com")

    workspace = client.post(
        "/api/v1/workspaces", json={"name": "lineage-co2", "description": ""}, headers=headers
    ).json()
    project = client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        json={"name": "data", "environment": "dev"},
        headers=headers,
    ).json()
    source = client.post(
        f"/api/v1/projects/{project['id']}/sources",
        json={"name": "orders-csv", "connector_type": "csv"},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/sources/{source['id']}/upload",
        files={"file": ("orders.csv", io.BytesIO(b"id,amount\n1,10\n"), "text/csv")},
        headers=headers,
    )
    pipeline = client.post(
        f"/api/v1/projects/{project['id']}/pipelines",
        json={
            "name": "orders-pipeline",
            "source_id": source["id"],
            "output_dataset_name": "orders",
            "output_layer": "silver",
            "transformations": [],
        },
        headers=headers,
    ).json()

    job1 = client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers).json()
    job2 = client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers).json()
    assert job1["dataset_id"] == job2["dataset_id"]

    lineage = client.get(f"/api/v1/lineage/datasets/{job1['dataset_id']}", headers=headers).json()
    job_ids_recorded = {e["job_id"] for e in lineage["upstream"]}
    assert {job1["id"], job2["id"]} <= job_ids_recorded

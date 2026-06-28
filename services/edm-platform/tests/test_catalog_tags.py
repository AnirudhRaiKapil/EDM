import io


def auth_headers(client, email="cataloger@example.com") -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email, "password": "hunter2pass"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "hunter2pass"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _build_dataset(client, headers) -> str:
    workspace = client.post(
        "/api/v1/workspaces", json={"name": "tag-co", "description": ""}, headers=headers
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
        files={"file": ("people.csv", io.BytesIO(b"name,email\nA,a@x.com\n"), "text/csv")},
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
    job = client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers).json()
    assert job["status"] == "succeeded", job
    return job["dataset_id"]


def test_tag_lifecycle_and_filtering(client):
    headers = auth_headers(client)
    dataset_id = _build_dataset(client, headers)

    tag = client.post(
        f"/api/v1/catalog/datasets/{dataset_id}/tags",
        json={"key": "pii", "value": "true"},
        headers=headers,
    )
    assert tag.status_code == 201
    tag_id = tag.json()["id"]

    detail = client.get(f"/api/v1/catalog/datasets/{dataset_id}", headers=headers).json()
    assert detail["tags"] == [{"id": tag_id, "key": "pii", "value": "true"}]

    found = client.get(
        "/api/v1/catalog/datasets", params={"tag_key": "pii", "tag_value": "true"}, headers=headers
    ).json()
    assert any(d["id"] == dataset_id for d in found)

    not_found = client.get(
        "/api/v1/catalog/datasets", params={"tag_key": "pii", "tag_value": "false"}, headers=headers
    ).json()
    assert not any(d["id"] == dataset_id for d in not_found)

    delete = client.delete(f"/api/v1/catalog/datasets/{dataset_id}/tags/{tag_id}", headers=headers)
    assert delete.status_code == 204

    detail_after = client.get(f"/api/v1/catalog/datasets/{dataset_id}", headers=headers).json()
    assert detail_after["tags"] == []


def test_update_dataset_classification(client):
    headers = auth_headers(client)
    dataset_id = _build_dataset(client, headers)

    response = client.patch(
        f"/api/v1/catalog/datasets/{dataset_id}",
        json={"classification": ["pii", "confidential"]},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["classification"] == ["pii", "confidential"]

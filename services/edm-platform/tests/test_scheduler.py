import io

import pytest

from app.modules.core.exceptions import ValidationFailedError
from app.scheduler import list_scheduled_pipeline_ids, sync_schedule, validate_cron


def test_validate_cron_accepts_standard_expression():
    validate_cron("0 * * * *")  # does not raise


def test_validate_cron_rejects_garbage():
    with pytest.raises(ValidationFailedError):
        validate_cron("not a cron expression")


def test_sync_schedule_registers_and_removes_job():
    sync_schedule("pipeline-abc", "0 * * * *")
    assert "pipeline-abc" in list_scheduled_pipeline_ids()

    sync_schedule("pipeline-abc", None)
    assert "pipeline-abc" not in list_scheduled_pipeline_ids()


def auth_headers(client, email="scheduler@example.com") -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email, "password": "hunter2pass"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "hunter2pass"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _setup_pipeline(client, headers) -> str:
    workspace = client.post(
        "/api/v1/workspaces", json={"name": "sched-co", "description": ""}, headers=headers
    ).json()
    project = client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        json={"name": "data", "environment": "dev"},
        headers=headers,
    ).json()
    source = client.post(
        f"/api/v1/projects/{project['id']}/sources",
        json={"name": "csv", "connector_type": "csv"},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/sources/{source['id']}/upload",
        files={"file": ("f.csv", io.BytesIO(b"x\n1\n"), "text/csv")},
        headers=headers,
    )
    pipeline = client.post(
        f"/api/v1/projects/{project['id']}/pipelines",
        json={
            "name": "p",
            "source_id": source["id"],
            "output_dataset_name": "out",
            "output_layer": "silver",
            "transformations": [],
        },
        headers=headers,
    ).json()
    return pipeline["id"]


def test_set_schedule_via_api(client):
    headers = auth_headers(client)
    pipeline_id = _setup_pipeline(client, headers)

    response = client.patch(
        f"/api/v1/pipelines/{pipeline_id}/schedule", json={"cron": "0 * * * *"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["schedule_cron"] == "0 * * * *"
    assert pipeline_id in list_scheduled_pipeline_ids()

    cleared = client.patch(
        f"/api/v1/pipelines/{pipeline_id}/schedule", json={"cron": None}, headers=headers
    )
    assert cleared.json()["schedule_cron"] is None
    assert pipeline_id not in list_scheduled_pipeline_ids()


def test_set_schedule_rejects_invalid_cron(client):
    headers = auth_headers(client)
    pipeline_id = _setup_pipeline(client, headers)

    response = client.patch(
        f"/api/v1/pipelines/{pipeline_id}/schedule", json={"cron": "nonsense"}, headers=headers
    )
    assert response.status_code == 422


def test_non_member_cannot_set_schedule(client):
    owner_headers = auth_headers(client, email="sched-owner@example.com")
    outsider_headers = auth_headers(client, email="sched-outsider@example.com")
    pipeline_id = _setup_pipeline(client, owner_headers)

    response = client.patch(
        f"/api/v1/pipelines/{pipeline_id}/schedule", json={"cron": "0 * * * *"}, headers=outsider_headers
    )
    assert response.status_code == 404

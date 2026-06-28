def register(client, email="audit@example.com", password="hunter2pass") -> dict:
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email, "password": password},
    ).json()


def login_headers(client, email, password="hunter2pass") -> dict:
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_register_and_login_are_audited(client):
    register(client, email="owner@example.com")
    headers = login_headers(client, "owner@example.com")

    events = client.get("/api/v1/users/me/audit-events", headers=headers).json()
    actions = [e["action"] for e in events]
    assert "user.registered" in actions
    assert "user.login_succeeded" in actions


def test_failed_login_is_audited_against_the_target_email_even_without_an_account(client):
    register(client, email="owner2@example.com")
    headers = login_headers(client, "owner2@example.com")

    client.post(
        "/api/v1/auth/login", json={"email": "owner2@example.com", "password": "wrong-one"}
    )
    client.post(
        "/api/v1/auth/login", json={"email": "no-such-account@example.com", "password": "x"}
    )

    my_events = client.get("/api/v1/users/me/audit-events", headers=headers).json()
    failed = [e for e in my_events if e["action"] == "user.login_failed"]
    assert len(failed) == 1
    assert failed[0]["subject_email"] == "owner2@example.com"
    assert failed[0]["actor_user_id"] is not None  # account exists, just wrong password


def test_role_assignment_is_audited(client):
    register(client, email="ws-owner@example.com")
    owner_headers = login_headers(client, "ws-owner@example.com")
    register(client, email="ws-member@example.com")

    workspace = client.post(
        "/api/v1/workspaces", json={"name": "audited-co", "description": ""}, headers=owner_headers
    ).json()
    client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        json={"email": "ws-member@example.com", "role": "member"},
        headers=owner_headers,
    )

    events = client.get(
        f"/api/v1/workspaces/{workspace['id']}/audit-events", headers=owner_headers
    ).json()
    role_events = [e for e in events if e["action"] == "role.assigned"]
    # one for the auto-assigned owner role on workspace creation, one for the new member
    assert len(role_events) == 2
    assert any(e["event_metadata"]["role"] == "member" for e in role_events)


def test_credentials_set_is_audited_without_leaking_the_credential_value(client):
    register(client, email="cred-owner@example.com")
    headers = login_headers(client, "cred-owner@example.com")
    workspace = client.post(
        "/api/v1/workspaces", json={"name": "cred-co", "description": ""}, headers=headers
    ).json()
    project = client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        json={"name": "p", "environment": "dev"},
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/projects/{project['id']}/sources",
        json={
            "name": "oracle-src",
            "connector_type": "oracle",
            "connection_config": {"host": "db", "port": 1521, "service_name": "ORCL", "table": "t"},
            "credentials": {"username": "admin", "password": "do-not-leak-me"},
        },
        headers=headers,
    )

    events = client.get(
        f"/api/v1/workspaces/{workspace['id']}/audit-events", headers=headers
    ).json()
    credential_events = [e for e in events if e["action"] == "source.credentials_set"]
    assert len(credential_events) == 1
    assert "do-not-leak-me" not in str(credential_events[0])


def test_schedule_changes_are_audited(client):
    register(client, email="sched-owner@example.com")
    headers = login_headers(client, "sched-owner@example.com")
    workspace = client.post(
        "/api/v1/workspaces", json={"name": "sched-co", "description": ""}, headers=headers
    ).json()
    project = client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        json={"name": "p", "environment": "dev"},
        headers=headers,
    ).json()
    source = client.post(
        f"/api/v1/projects/{project['id']}/sources",
        json={"name": "csv", "connector_type": "csv"},
        headers=headers,
    ).json()
    pipeline = client.post(
        f"/api/v1/projects/{project['id']}/pipelines",
        json={
            "name": "p",
            "source_id": source["id"],
            "output_dataset_name": "out",
            "transformations": [],
        },
        headers=headers,
    ).json()

    client.patch(f"/api/v1/pipelines/{pipeline['id']}/schedule", json={"cron": "0 * * * *"}, headers=headers)
    client.patch(f"/api/v1/pipelines/{pipeline['id']}/schedule", json={"cron": None}, headers=headers)

    events = client.get(
        f"/api/v1/workspaces/{workspace['id']}/audit-events", headers=headers
    ).json()
    actions = [e["action"] for e in events]
    assert "pipeline.schedule_set" in actions
    assert "pipeline.schedule_cleared" in actions


def test_non_owner_member_cannot_view_workspace_audit_log(client):
    register(client, email="audit-owner@example.com")
    owner_headers = login_headers(client, "audit-owner@example.com")
    register(client, email="audit-member@example.com")
    member_headers = login_headers(client, "audit-member@example.com")

    workspace = client.post(
        "/api/v1/workspaces", json={"name": "co", "description": ""}, headers=owner_headers
    ).json()
    client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        json={"email": "audit-member@example.com", "role": "member"},
        headers=owner_headers,
    )

    response = client.get(
        f"/api/v1/workspaces/{workspace['id']}/audit-events", headers=member_headers
    )
    assert response.status_code == 403


def test_non_member_cannot_view_workspace_audit_log(client):
    register(client, email="audit-private-owner@example.com")
    owner_headers = login_headers(client, "audit-private-owner@example.com")
    register(client, email="audit-outsider@example.com")
    outsider_headers = login_headers(client, "audit-outsider@example.com")

    workspace = client.post(
        "/api/v1/workspaces", json={"name": "private-co", "description": ""}, headers=owner_headers
    ).json()

    response = client.get(
        f"/api/v1/workspaces/{workspace['id']}/audit-events", headers=outsider_headers
    )
    assert response.status_code == 404

def register_and_login(client, email: str) -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email, "password": "hunter2pass"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "hunter2pass"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_workspace_creator_is_owner(client):
    owner_headers = register_and_login(client, "owner@example.com")
    workspace = client.post(
        "/api/v1/workspaces", json={"name": "acme", "description": ""}, headers=owner_headers
    ).json()

    members = client.get(f"/api/v1/workspaces/{workspace['id']}/members", headers=owner_headers).json()
    assert len(members) == 1
    assert members[0]["email"] == "owner@example.com"
    assert members[0]["role_name"] == "owner"


def test_non_member_cannot_access_workspace_or_its_projects(client):
    owner_headers = register_and_login(client, "owner2@example.com")
    outsider_headers = register_and_login(client, "outsider@example.com")

    workspace = client.post(
        "/api/v1/workspaces", json={"name": "acme2", "description": ""}, headers=owner_headers
    ).json()
    project = client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        json={"name": "sales", "environment": "dev"},
        headers=owner_headers,
    ).json()

    # outsider can't see the workspace, its projects, or create anything inside it
    assert client.get(f"/api/v1/workspaces/{workspace['id']}", headers=outsider_headers).status_code == 404
    assert (
        client.get(f"/api/v1/workspaces/{workspace['id']}/projects", headers=outsider_headers).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/projects/{project['id']}/sources",
            json={"name": "x", "connector_type": "csv"},
            headers=outsider_headers,
        ).status_code
        == 404
    )

    # outsider's own workspace list is empty (no leakage of others' workspaces)
    assert client.get("/api/v1/workspaces", headers=outsider_headers).json() == []


def test_member_gains_access_after_being_added_but_cannot_manage_members(client):
    owner_headers = register_and_login(client, "owner3@example.com")
    member_headers = register_and_login(client, "member3@example.com")

    workspace = client.post(
        "/api/v1/workspaces", json={"name": "acme3", "description": ""}, headers=owner_headers
    ).json()

    # not yet a member -> forbidden/not found
    assert (
        client.get(f"/api/v1/workspaces/{workspace['id']}/projects", headers=member_headers).status_code
        == 404
    )

    add = client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        json={"email": "member3@example.com", "role": "member"},
        headers=owner_headers,
    )
    assert add.status_code == 201
    assert add.json()["role_name"] == "member"

    # now a member -> can read and create projects
    ok = client.get(f"/api/v1/workspaces/{workspace['id']}/projects", headers=member_headers)
    assert ok.status_code == 200

    # but a plain "member" cannot add other members (owner-only)
    forbidden = client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        json={"email": "owner3@example.com", "role": "owner"},
        headers=member_headers,
    )
    assert forbidden.status_code == 403

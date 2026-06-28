import io

import jwt


def auth_headers(client, email="sec@example.com", password="hunter2pass") -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email, "password": password},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _setup_dataset(client, headers) -> tuple[str, str]:
    """Returns (project_id, dataset_id) for a small published CSV dataset."""
    workspace = client.post(
        "/api/v1/workspaces", json={"name": "sec-co", "description": ""}, headers=headers
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
        files={"file": ("f.csv", io.BytesIO(b"x,secret\n1,classified\n"), "text/csv")},
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
    job = client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers).json()
    return project["id"], job["dataset_id"]


def _invite_member(client, owner_headers, workspace_id, email) -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email, "password": "hunter2pass"},
    )
    client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": email, "role": "member"},
        headers=owner_headers,
    )
    return login_as(client, email)


def login_as(client, email, password="hunter2pass") -> dict:
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _setup_dataset_with_workspace(client, headers) -> tuple[str, str, str]:
    """Like _setup_dataset, but also returns the workspace_id (needed to invite a
    second, non-owner member for the masking tests below)."""
    workspace = client.post(
        "/api/v1/workspaces", json={"name": "pii-co", "description": ""}, headers=headers
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
        files={
            "file": (
                "f.csv",
                io.BytesIO(b"name,email,amount\nAda,ada@example.com,91\n"),
                "text/csv",
            )
        },
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
    job = client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers).json()
    return workspace["id"], project["id"], job["dataset_id"]


# --- governance: PII column masking ---------------------------------------------------


def test_pii_columns_masked_for_member_but_not_owner(client):
    owner_headers = auth_headers(client, email="pii-owner@example.com")
    workspace_id, _, dataset_id = _setup_dataset_with_workspace(client, owner_headers)
    member_headers = _invite_member(client, owner_headers, workspace_id, "pii-member@example.com")

    client.patch(
        f"/api/v1/catalog/datasets/{dataset_id}", json={"classification": ["pii"]}, headers=owner_headers
    )

    owner_query = client.post(
        "/api/v1/query",
        json={"dataset_id": dataset_id, "sql": "SELECT * FROM dataset"},
        headers=owner_headers,
    ).json()
    assert owner_query["rows"] == [{"name": "Ada", "email": "ada@example.com", "amount": 91}]

    member_query = client.post(
        "/api/v1/query",
        json={"dataset_id": dataset_id, "sql": "SELECT * FROM dataset"},
        headers=member_headers,
    ).json()
    row = member_query["rows"][0]
    assert row["email"] == "***MASKED***"
    assert row["name"] == "Ada"  # "name" isn't a recognized PII column pattern
    assert row["amount"] == 91


def test_unclassified_dataset_is_never_masked_even_for_members(client):
    owner_headers = auth_headers(client, email="unclassified-owner@example.com")
    workspace_id, _, dataset_id = _setup_dataset_with_workspace(client, owner_headers)
    member_headers = _invite_member(
        client, owner_headers, workspace_id, "unclassified-member@example.com"
    )
    # classification left at its default ([]) -- masking must not trigger on its own
    # just because a column happens to be named "email".

    member_query = client.post(
        "/api/v1/query",
        json={"dataset_id": dataset_id, "sql": "SELECT * FROM dataset"},
        headers=member_headers,
    ).json()
    assert member_query["rows"][0]["email"] == "ada@example.com"


# --- query endpoint: local file inclusion / exfiltration ---------------------------


def test_query_cannot_read_arbitrary_local_files_via_read_csv(client, tmp_path):
    headers = auth_headers(client)
    _, dataset_id = _setup_dataset(client, headers)

    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("TOP-SECRET-CONTENT")
    # DuckDB accepts forward slashes on Windows; round-trip through as_posix() so the
    # injected SQL string itself doesn't need escaped backslashes.
    payload_path = secret_file.as_posix()

    response = client.post(
        "/api/v1/query",
        json={"dataset_id": dataset_id, "sql": f"SELECT * FROM read_csv('{payload_path}')"},
        headers=headers,
    )
    assert response.status_code != 200 or "TOP-SECRET-CONTENT" not in response.text


def test_query_cannot_exfiltrate_via_copy_to(client, tmp_path):
    headers = auth_headers(client)
    _, dataset_id = _setup_dataset(client, headers)
    target = (tmp_path / "exfil.csv").as_posix()

    response = client.post(
        "/api/v1/query",
        json={"dataset_id": dataset_id, "sql": f"COPY (SELECT 1) TO '{target}'"},
        headers=headers,
    )
    # Either rejected outright (doesn't start with SELECT) or fails inside DuckDB
    # (enable_external_access=False) -- either way, the file must not be written.
    assert response.status_code != 200
    assert not (tmp_path / "exfil.csv").exists()


def test_query_legitimate_select_still_works(client):
    headers = auth_headers(client)
    _, dataset_id = _setup_dataset(client, headers)

    response = client.post(
        "/api/v1/query",
        json={"dataset_id": dataset_id, "sql": "SELECT * FROM dataset"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["rows"] == [{"x": 1, "secret": "classified"}]


# --- auth hardening -----------------------------------------------------------------


def test_password_too_short_is_rejected(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "display_name": "x", "password": "abc123"},
    )
    assert response.status_code == 422


def test_password_at_minimum_length_is_accepted(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "minlen@example.com", "display_name": "x", "password": "0123456789"},
    )
    assert response.status_code == 201


def test_wrong_password_and_nonexistent_user_return_identical_error(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "real@example.com", "display_name": "x", "password": "hunter2pass"},
    )
    wrong_password = client.post(
        "/api/v1/auth/login", json={"email": "real@example.com", "password": "totally-wrong"}
    )
    no_such_user = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "totally-wrong"}
    )
    assert wrong_password.status_code == no_such_user.status_code == 401
    assert wrong_password.json()["detail"] == no_such_user.json()["detail"]


def test_login_rate_limit_blocks_after_threshold(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth_rate_limit_max_attempts", 3)
    # register() itself consumes one slot from the same shared budget (by design --
    # it guards against registration spam too), so only 2 login attempts remain
    # before the 3rd trips the limit.
    client.post(
        "/api/v1/auth/register",
        json={"email": "ratelimited@example.com", "display_name": "x", "password": "hunter2pass"},
    )
    statuses = [
        client.post(
            "/api/v1/auth/login",
            json={"email": "ratelimited@example.com", "password": "wrong-password"},
        ).status_code
        for _ in range(5)
    ]
    assert statuses[:2] == [401, 401]
    assert 429 in statuses[2:]


def test_register_rate_limit_is_keyed_by_ip_not_just_email(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth_rate_limit_max_attempts", 3)
    for i in range(3):
        client.post(
            "/api/v1/auth/register",
            json={"email": f"distinct{i}@example.com", "display_name": "x", "password": "hunter2pass"},
        )
    blocked = client.post(
        "/api/v1/auth/register",
        json={"email": "yet-another@example.com", "display_name": "x", "password": "hunter2pass"},
    )
    assert blocked.status_code == 429


# --- upload size limit ---------------------------------------------------------------


def test_oversized_upload_is_rejected(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_upload_mb", 1)
    headers = auth_headers(client, email="upload-limit@example.com")
    workspace = client.post(
        "/api/v1/workspaces", json={"name": "co", "description": ""}, headers=headers
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

    oversized = b"x\n" + (b"1\n" * (2 * 1024 * 1024))  # well over the 1MB limit
    response = client.post(
        f"/api/v1/sources/{source['id']}/upload",
        files={"file": ("big.csv", io.BytesIO(oversized), "text/csv")},
        headers=headers,
    )
    assert response.status_code == 413


# --- security headers ----------------------------------------------------------------


def test_responses_carry_security_headers(client):
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"


# --- JWT tampering --------------------------------------------------------------------


def test_token_signed_with_wrong_secret_is_rejected(client):
    headers = auth_headers(client, email="jwt-victim@example.com")
    token = headers["Authorization"].split(" ")[1]
    payload = jwt.decode(token, options={"verify_signature": False})

    forged = jwt.encode(payload, "attacker-controlled-secret-thats-long-enough", algorithm="HS256")
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_token_with_none_algorithm_is_rejected(client):
    headers = auth_headers(client, email="jwt-none-alg@example.com")
    token = headers["Authorization"].split(" ")[1]
    payload = jwt.decode(token, options={"verify_signature": False})

    forged = jwt.encode(payload, "", algorithm="none")
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_malformed_token_is_rejected(client):
    response = client.get("/api/v1/users/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_missing_token_is_rejected(client):
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401


# --- IDOR sweep: a non-member must get 404 (not the resource) from every owned type --


def test_non_member_cannot_access_another_users_resources_across_modules(client):
    owner = auth_headers(client, email="idor-owner@example.com")
    outsider = auth_headers(client, email="idor-outsider@example.com")
    project_id, dataset_id = _setup_dataset(client, owner)

    assert (
        client.get(f"/api/v1/projects/{project_id}/sources", headers=outsider).status_code == 404
    )
    assert (
        client.get(f"/api/v1/projects/{project_id}/pipelines", headers=outsider).status_code == 404
    )
    assert (
        client.post(
            "/api/v1/query",
            json={"dataset_id": dataset_id, "sql": "SELECT * FROM dataset"},
            headers=outsider,
        ).status_code
        == 404
    )

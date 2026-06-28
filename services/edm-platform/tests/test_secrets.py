import io

import pytest

from app.secrets import decrypt_credentials, encrypt_credentials


def test_encrypt_decrypt_roundtrip():
    original = {"username": "admin", "password": "hunter2pass"}
    ciphertext = encrypt_credentials(original)
    assert ciphertext != str(original)
    assert decrypt_credentials(ciphertext) == original


def test_decrypt_rejects_tampered_ciphertext():
    ciphertext = encrypt_credentials({"password": "secret"})
    with pytest.raises(ValueError):
        decrypt_credentials(ciphertext[:-4] + "abcd")


def auth_headers(client, email="creds@example.com") -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email, "password": "hunter2pass"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "hunter2pass"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_credentials_never_returned_by_api(client):
    headers = auth_headers(client)
    workspace = client.post(
        "/api/v1/workspaces", json={"name": "secrets-co", "description": ""}, headers=headers
    ).json()
    project = client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        json={"name": "data", "environment": "dev"},
        headers=headers,
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/sources",
        json={
            "name": "secure-db",
            "connector_type": "oracle",
            "connection_config": {"host": "db.internal", "port": 1521, "service_name": "ORCL", "table": "customers"},
            "credentials": {"username": "admin", "password": "super-secret-password"},
        },
        headers=headers,
    )
    assert response.status_code == 201
    body = response.text
    assert "super-secret-password" not in body
    assert response.json()["has_credentials"] is True
    assert "credentials" not in response.json()
    assert "encrypted_credentials" not in response.json()

    fetched = client.get(f"/api/v1/sources/{response.json()['id']}", headers=headers)
    assert "super-secret-password" not in fetched.text
    assert fetched.json()["has_credentials"] is True

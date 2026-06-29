import httpx
import pytest

from app.modules.alerting.models import Alert
from app.modules.notification import senders
from app.modules.notification.models import NotificationChannel


def _alert(**overrides) -> Alert:
    defaults = dict(
        id="alert-1",
        project_id="project-1",
        source_entity_type="job",
        source_entity_id="job-1",
        severity="critical",
        message="pipeline failed",
        status="open",
    )
    defaults.update(overrides)
    return Alert(**defaults)


def _channel(channel_type: str, config: dict) -> NotificationChannel:
    return NotificationChannel(
        id="channel-1", project_id="project-1", type=channel_type, config=config, owner_id="user-1"
    )


# --- senders: unit-level, no real network/SMTP ---------------------------------------


def test_send_webhook_posts_the_alert_payload():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    channel = _channel("webhook", {"url": "https://hooks.example.com/edm"})
    senders.send_webhook(channel, _alert(), client=client)

    assert len(seen) == 1
    assert seen[0].url == httpx.URL("https://hooks.example.com/edm")
    body = httpx.Response(200, content=seen[0].read()).json()
    assert body["alert_id"] == "alert-1"
    assert body["severity"] == "critical"
    assert body["message"] == "pipeline failed"


def test_send_webhook_raises_on_http_error_so_caller_can_log_and_skip():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    channel = _channel("webhook", {"url": "https://hooks.example.com/edm"})
    with pytest.raises(httpx.HTTPStatusError):
        senders.send_webhook(channel, _alert(), client=client)


def test_send_webhook_requires_a_url():
    channel = _channel("webhook", {})
    with pytest.raises(ValueError):
        senders.send_webhook(channel, _alert())


def test_send_slack_posts_a_text_payload():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"ok")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    channel = _channel("slack", {"url": "https://hooks.slack.com/services/x"})
    senders.send_slack(channel, _alert(message="pipeline failed"), client=client)

    assert len(seen) == 1
    body = httpx.Response(200, content=seen[0].read()).json()
    assert body["text"] == "[CRITICAL] pipeline failed"


def test_send_slack_requires_a_url():
    channel = _channel("slack", {})
    with pytest.raises(ValueError):
        senders.send_slack(channel, _alert())


def test_send_teams_posts_a_message_card():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"1")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    channel = _channel("teams", {"url": "https://outlook.office.com/webhook/x"})
    senders.send_teams(channel, _alert(severity="warning", message="quality check failed"), client=client)

    assert len(seen) == 1
    body = httpx.Response(200, content=seen[0].read()).json()
    assert body["@type"] == "MessageCard"
    assert body["themeColor"] == "FFA500"
    assert body["text"] == "quality check failed"


def test_send_teams_requires_a_url():
    channel = _channel("teams", {})
    with pytest.raises(ValueError):
        senders.send_teams(channel, _alert())


class _FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.started_tls = False
        self.login_args = None
        self.sent_messages = []
        _FakeSMTP.instances.append(self)

    def starttls(self):
        self.started_tls = True

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, message):
        self.sent_messages.append(message)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_send_email_delivers_via_configured_smtp(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_username", "edm")
    monkeypatch.setattr(settings, "smtp_password", "app-password")
    _FakeSMTP.instances.clear()

    channel = _channel("email", {"to_address": "oncall@example.com"})
    senders.send_email(channel, _alert(message="critical alert body"), smtp_cls=_FakeSMTP)

    assert len(_FakeSMTP.instances) == 1
    smtp = _FakeSMTP.instances[0]
    assert smtp.started_tls is True
    assert smtp.login_args == ("edm", "app-password")
    assert len(smtp.sent_messages) == 1
    assert smtp.sent_messages[0]["To"] == "oncall@example.com"
    assert "critical alert body" in smtp.sent_messages[0].get_content()


def test_send_email_is_a_silent_no_op_without_an_smtp_host(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "smtp_host", "")
    _FakeSMTP.instances.clear()

    channel = _channel("email", {"to_address": "oncall@example.com"})
    senders.send_email(channel, _alert(), smtp_cls=_FakeSMTP)  # must not raise

    assert _FakeSMTP.instances == []


def test_send_email_requires_a_to_address():
    channel = _channel("email", {})
    with pytest.raises(ValueError):
        senders.send_email(channel, _alert())


# --- full stack: channel CRUD, permissions, and dispatch firing on a real alert ------


def auth_headers(client, email="notify@example.com") -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": email, "password": "hunter2pass"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "hunter2pass"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _setup_project(client, headers) -> tuple[str, str]:
    workspace = client.post(
        "/api/v1/workspaces", json={"name": "notify-co", "description": ""}, headers=headers
    ).json()
    project = client.post(
        f"/api/v1/workspaces/{workspace['id']}/projects",
        json={"name": "p", "environment": "dev"},
        headers=headers,
    ).json()
    return workspace["id"], project["id"]


def test_create_list_delete_channel(client):
    headers = auth_headers(client)
    _, project_id = _setup_project(client, headers)

    created = client.post(
        f"/api/v1/projects/{project_id}/notification-channels",
        json={"type": "webhook", "config": {"url": "https://hooks.example.com/x"}},
        headers=headers,
    )
    assert created.status_code == 201
    channel_id = created.json()["id"]

    listed = client.get(
        f"/api/v1/projects/{project_id}/notification-channels", headers=headers
    ).json()
    assert len(listed) == 1

    deleted = client.delete(f"/api/v1/notification-channels/{channel_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/projects/{project_id}/notification-channels", headers=headers).json() == []


def test_webhook_channel_missing_url_is_rejected(client):
    headers = auth_headers(client)
    _, project_id = _setup_project(client, headers)

    response = client.post(
        f"/api/v1/projects/{project_id}/notification-channels",
        json={"type": "webhook", "config": {}},
        headers=headers,
    )
    assert response.status_code == 422


def test_create_slack_and_teams_channels(client):
    headers = auth_headers(client, email="slack-teams@example.com")
    _, project_id = _setup_project(client, headers)

    for channel_type, url in (
        ("slack", "https://hooks.slack.com/services/x"),
        ("teams", "https://outlook.office.com/webhook/x"),
    ):
        created = client.post(
            f"/api/v1/projects/{project_id}/notification-channels",
            json={"type": channel_type, "config": {"url": url}},
            headers=headers,
        )
        assert created.status_code == 201
        assert created.json()["type"] == channel_type


def test_slack_channel_missing_url_is_rejected(client):
    headers = auth_headers(client, email="slack-missing-url@example.com")
    _, project_id = _setup_project(client, headers)

    response = client.post(
        f"/api/v1/projects/{project_id}/notification-channels",
        json={"type": "slack", "config": {}},
        headers=headers,
    )
    assert response.status_code == 422


def test_non_member_cannot_manage_channels(client):
    owner_headers = auth_headers(client, email="notify-owner@example.com")
    outsider_headers = auth_headers(client, email="notify-outsider@example.com")
    _, project_id = _setup_project(client, owner_headers)

    assert (
        client.get(
            f"/api/v1/projects/{project_id}/notification-channels", headers=outsider_headers
        ).status_code
        == 404
    )


def test_alert_creation_dispatches_to_a_registered_webhook(client, monkeypatch):
    import httpx as httpx_module

    from app.modules.notification import senders as senders_module

    received = []

    def fake_send_webhook(channel, alert, client=None):
        received.append((channel.config["url"], alert.severity, alert.message))

    monkeypatch.setattr(senders_module, "send_webhook", fake_send_webhook)
    # service.py imported the function by reference at module load time; patch its
    # copy of the name too so the dispatch table actually calls the fake.
    from app.modules.notification import service as notification_service

    monkeypatch.setitem(notification_service._SENDERS, "webhook", fake_send_webhook)

    headers = auth_headers(client, email="dispatch@example.com")
    _, project_id = _setup_project(client, headers)
    client.post(
        f"/api/v1/projects/{project_id}/notification-channels",
        json={"type": "webhook", "config": {"url": "https://hooks.example.com/alerts"}},
        headers=headers,
    )

    source = client.post(
        f"/api/v1/projects/{project_id}/sources",
        json={"name": "csv", "connector_type": "csv"},
        headers=headers,
    ).json()
    pipeline = client.post(
        f"/api/v1/projects/{project_id}/pipelines",
        json={
            "name": "broken",
            "source_id": source["id"],
            "output_dataset_name": "out",
            "transformations": [{"type": "select_columns", "order": 0, "parameters": {"columns": ["does_not_exist"]}}],
        },
        headers=headers,
    ).json()
    # No file uploaded -- this run fails, which is exactly what raises a critical Alert.
    client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers)

    assert len(received) == 1
    assert received[0][0] == "https://hooks.example.com/alerts"
    assert received[0][1] == "critical"


def test_one_channel_failing_does_not_block_alert_creation(client, monkeypatch):
    from app.modules.notification import service as notification_service

    def raising_sender(channel, alert, client=None):
        raise ConnectionError("webhook host unreachable")

    monkeypatch.setitem(notification_service._SENDERS, "webhook", raising_sender)

    headers = auth_headers(client, email="resilient@example.com")
    _, project_id = _setup_project(client, headers)
    client.post(
        f"/api/v1/projects/{project_id}/notification-channels",
        json={"type": "webhook", "config": {"url": "https://unreachable.example.com"}},
        headers=headers,
    )

    source = client.post(
        f"/api/v1/projects/{project_id}/sources",
        json={"name": "csv", "connector_type": "csv"},
        headers=headers,
    ).json()
    pipeline = client.post(
        f"/api/v1/projects/{project_id}/pipelines",
        json={
            "name": "broken",
            "source_id": source["id"],
            "output_dataset_name": "out",
            "transformations": [{"type": "select_columns", "order": 0, "parameters": {"columns": ["does_not_exist"]}}],
        },
        headers=headers,
    ).json()

    job_response = client.post(f"/api/v1/pipelines/{pipeline['id']}/jobs", headers=headers)
    # The job's own failure response must come back normally -- a broken notification
    # channel must never turn into a 500 for the request that triggered it.
    assert job_response.status_code == 201
    assert job_response.json()["status"] == "failed"

    alerts = client.get(f"/api/v1/projects/{project_id}/alerts", headers=headers).json()
    assert len(alerts) == 1

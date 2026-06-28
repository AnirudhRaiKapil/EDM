import httpx
import pytest

from app.modules.ingestion import connectors, rest_client
from app.secrets import encrypt_credentials


class _FakeSource:
    def __init__(self, connector_type, connection_config, credentials=None):
        self.id = "source-1"
        self.connector_type = connector_type
        self.connection_config = connection_config
        self.encrypted_credentials = encrypt_credentials(credentials) if credentials else None
        self.raw_file_path = None


@pytest.fixture()
def mock_transport(monkeypatch):
    requests_seen = []
    real_client_cls = httpx.Client

    def install(handler):
        def wrapped_handler(request):
            requests_seen.append(request)
            return handler(request)

        def fake_client(**kwargs):
            return real_client_cls(transport=httpx.MockTransport(wrapped_handler))

        monkeypatch.setattr(rest_client.httpx, "Client", fake_client)
        return requests_seen

    return install


def test_servicenow_connector_builds_table_api_request(mock_transport):
    def handler(request):
        assert request.url.path == "/api/now/table/incident"
        assert "Basic " in request.headers["authorization"]
        return httpx.Response(200, json={"result": [{"number": "INC0000123"}]})

    seen = mock_transport(handler)
    source = _FakeSource(
        "servicenow",
        {"instance_url": "https://example.service-now.com", "table": "incident"},
        {"username": "admin", "password": "pass"},
    )

    df = connectors.load_source_dataframe(source)
    assert list(df["number"]) == ["INC0000123"]
    assert seen[0].url.params.get("sysparm_offset") == "0"


def test_jira_connector_maps_email_and_token_to_basic_auth_and_sends_jql(mock_transport):
    def handler(request):
        assert request.url.path == "/rest/api/3/search"
        assert request.url.params.get("jql") == "project = OPS"
        return httpx.Response(200, json={"issues": [{"key": "OPS-1"}, {"key": "OPS-2"}]})

    mock_transport(handler)
    source = _FakeSource(
        "jira",
        {"base_url": "https://example.atlassian.net", "jql": "project = OPS"},
        {"email": "me@example.com", "api_token": "tok"},
    )

    df = connectors.load_source_dataframe(source)
    assert list(df["key"]) == ["OPS-1", "OPS-2"]


def test_confluence_connector_uses_space_key_query(mock_transport):
    def handler(request):
        assert request.url.path == "/wiki/rest/api/content"
        assert request.url.params.get("spaceKey") == "ENG"
        return httpx.Response(200, json={"results": [{"id": "123", "title": "Runbook"}]})

    mock_transport(handler)
    source = _FakeSource(
        "confluence",
        {"base_url": "https://example.atlassian.net", "space_key": "ENG"},
        {"email": "me@example.com", "api_token": "tok"},
    )

    df = connectors.load_source_dataframe(source)
    assert list(df["title"]) == ["Runbook"]


def test_rest_api_connector_is_fully_generic(mock_transport):
    def handler(request):
        assert request.headers.get("x-api-key") == "k-123"
        return httpx.Response(200, json={"data": {"items": [{"a": 1}]}})

    mock_transport(handler)
    source = _FakeSource(
        "rest_api",
        {
            "base_url": "https://api.example.com",
            "path": "v1/things",
            "auth_type": "api_key_header",
            "api_key_header_name": "X-Api-Key",
            "records_path": "data.items",
        },
        {"api_key": "k-123"},
    )

    df = connectors.load_source_dataframe(source)
    assert list(df["a"]) == [1]

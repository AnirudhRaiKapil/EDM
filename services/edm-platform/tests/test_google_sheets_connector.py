"""Google Sheets connector tests using httpx.MockTransport -- no real Google
account/service-account key is available in this dev environment (see ADR-0009),
so these verify the request-building (URL/auth) and values-to-DataFrame mapping,
not a real round trip against the Sheets API."""

import httpx
import pytest

from app.modules.ingestion import connectors
from app.secrets import encrypt_credentials


class _FakeSource:
    def __init__(self, connection_config, credentials=None):
        self.id = "source-1"
        self.connector_type = "google_sheets"
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

        monkeypatch.setattr(connectors.httpx, "Client", fake_client)
        return requests_seen

    return install


def test_google_sheets_connector_uses_api_key_and_header_row(mock_transport):
    def handler(request):
        assert request.url.path == "/v4/spreadsheets/sheet-123/values/Sheet1!A1:B3"
        assert request.url.params.get("key") == "k-abc"
        return httpx.Response(200, json={"values": [["name", "amount"], ["Ada", "91"], ["Lin", "77"]]})

    mock_transport(handler)
    source = _FakeSource(
        {"spreadsheet_id": "sheet-123", "range": "Sheet1!A1:B3"},
        {"api_key": "k-abc"},
    )

    df = connectors.load_source_dataframe(source)
    assert list(df.columns) == ["name", "amount"]
    assert list(df["name"]) == ["Ada", "Lin"]


def test_google_sheets_connector_uses_bearer_token(mock_transport):
    def handler(request):
        assert request.headers["authorization"] == "Bearer tok-xyz"
        return httpx.Response(200, json={"values": [["name"], ["Ada"]]})

    mock_transport(handler)
    source = _FakeSource(
        {"spreadsheet_id": "sheet-123", "range": "Sheet1!A1:A2", "auth_type": "bearer"},
        {"token": "tok-xyz"},
    )

    df = connectors.load_source_dataframe(source)
    assert list(df["name"]) == ["Ada"]


def test_google_sheets_connector_without_header_row(mock_transport):
    def handler(request):
        return httpx.Response(200, json={"values": [["Ada", "91"], ["Lin", "77"]]})

    mock_transport(handler)
    source = _FakeSource(
        {"spreadsheet_id": "sheet-123", "range": "Sheet1!A1:B2", "header_row": False},
        {"api_key": "k-abc"},
    )

    df = connectors.load_source_dataframe(source)
    assert df.shape == (2, 2)


def test_google_sheets_connector_pads_short_rows(mock_transport):
    def handler(request):
        return httpx.Response(200, json={"values": [["name", "amount"], ["Ada"]]})

    mock_transport(handler)
    source = _FakeSource(
        {"spreadsheet_id": "sheet-123", "range": "Sheet1!A1:B2"},
        {"api_key": "k-abc"},
    )

    df = connectors.load_source_dataframe(source)
    assert df.iloc[0]["amount"] is None

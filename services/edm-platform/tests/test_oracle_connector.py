"""Unit tests for the Oracle connector's request-building logic, using a mocked
oracledb connection. There is no real Oracle instance available in this dev
environment to integration-test against (see ADR-0009) -- these tests verify the
DSN/query construction and result-to-DataFrame mapping, not a real round trip."""

import pytest

from app.modules.core.exceptions import ValidationFailedError
from app.modules.ingestion import connectors
from app.secrets import encrypt_credentials


class _FakeCursor:
    def __init__(self, columns, rows):
        self.description = [(c,) for c in columns]
        self._rows = rows
        self.executed_query = None

    def execute(self, query):
        self.executed_query = query

    def fetchall(self):
        return self._rows


class _FakeConnection:
    def __init__(self, columns, rows, **connect_kwargs):
        self.connect_kwargs = connect_kwargs
        self._cursor = _FakeCursor(columns, rows)
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


class _FakeSource:
    def __init__(self, connection_config, credentials=None):
        self.id = "source-1"
        self.connector_type = "oracle"
        self.connection_config = connection_config
        self.encrypted_credentials = encrypt_credentials(credentials) if credentials else None
        self.raw_file_path = None


@pytest.fixture()
def fake_oracledb(monkeypatch):
    import oracledb

    state = {}

    def fake_connect(**kwargs):
        state["connect_kwargs"] = kwargs
        connection = _FakeConnection(["ID", "NAME"], [(1, "Ada"), (2, "Lin")], **kwargs)
        state["connection"] = connection
        return connection

    monkeypatch.setattr(oracledb, "connect", fake_connect)
    return state


def test_oracle_connector_builds_dsn_and_select_star_for_table(fake_oracledb):
    source = _FakeSource(
        {"host": "db.internal", "port": 1521, "service_name": "ORCL", "table": "customers"},
        {"username": "admin", "password": "secret"},
    )

    df = connectors.load_source_dataframe(source)

    assert fake_oracledb["connect_kwargs"]["dsn"] == "db.internal:1521/ORCL"
    assert fake_oracledb["connect_kwargs"]["user"] == "admin"
    assert fake_oracledb["connect_kwargs"]["password"] == "secret"
    assert fake_oracledb["connection"]._cursor.executed_query == 'SELECT * FROM "customers"'
    assert fake_oracledb["connection"].closed is True
    assert list(df.columns) == ["ID", "NAME"]
    assert list(df["NAME"]) == ["Ada", "Lin"]


def test_oracle_connector_rejects_non_select_query(fake_oracledb):
    source = _FakeSource(
        {"host": "db.internal", "port": 1521, "service_name": "ORCL", "query": "DROP TABLE customers"},
        {"username": "admin", "password": "secret"},
    )

    with pytest.raises(ValidationFailedError):
        connectors.load_source_dataframe(source)


def test_oracle_connector_rejects_invalid_table_name(fake_oracledb):
    source = _FakeSource(
        {"host": "db.internal", "port": 1521, "service_name": "ORCL", "table": "x; drop table y"},
        {"username": "admin", "password": "secret"},
    )

    with pytest.raises(ValidationFailedError):
        connectors.load_source_dataframe(source)

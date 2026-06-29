"""Unit tests for the Postgres connector's request-building logic, using a mocked
psycopg2 connection. There is no real Postgres instance available in this dev
environment to integration-test against (see ADR-0009) -- these tests verify the
connection-kwarg/query construction and result-to-DataFrame mapping, not a real
round trip."""

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
        self.connector_type = "postgres"
        self.connection_config = connection_config
        self.encrypted_credentials = encrypt_credentials(credentials) if credentials else None
        self.raw_file_path = None


@pytest.fixture()
def fake_psycopg2(monkeypatch):
    import psycopg2

    state = {}

    def fake_connect(**kwargs):
        state["connect_kwargs"] = kwargs
        connection = _FakeConnection(["id", "name"], [(1, "Ada"), (2, "Lin")], **kwargs)
        state["connection"] = connection
        return connection

    monkeypatch.setattr(psycopg2, "connect", fake_connect)
    return state


def test_postgres_connector_builds_select_star_for_table(fake_psycopg2):
    source = _FakeSource(
        {"host": "db.internal", "port": 5432, "database": "app", "table": "customers"},
        {"username": "admin", "password": "secret"},
    )

    df = connectors.load_source_dataframe(source)

    assert fake_psycopg2["connect_kwargs"]["host"] == "db.internal"
    assert fake_psycopg2["connect_kwargs"]["port"] == 5432
    assert fake_psycopg2["connect_kwargs"]["dbname"] == "app"
    assert fake_psycopg2["connect_kwargs"]["user"] == "admin"
    assert fake_psycopg2["connect_kwargs"]["password"] == "secret"
    assert fake_psycopg2["connection"]._cursor.executed_query == 'SELECT * FROM "customers"'
    assert fake_psycopg2["connection"].closed is True
    assert list(df.columns) == ["id", "name"]
    assert list(df["name"]) == ["Ada", "Lin"]


def test_postgres_connector_uses_explicit_query(fake_psycopg2):
    source = _FakeSource(
        {"host": "db.internal", "port": 5432, "database": "app", "query": "SELECT id FROM customers"},
        {"username": "admin", "password": "secret"},
    )

    connectors.load_source_dataframe(source)

    assert fake_psycopg2["connection"]._cursor.executed_query == "SELECT id FROM customers"


def test_postgres_connector_rejects_non_select_query(fake_psycopg2):
    source = _FakeSource(
        {"host": "db.internal", "port": 5432, "database": "app", "query": "DROP TABLE customers"},
        {"username": "admin", "password": "secret"},
    )

    with pytest.raises(ValidationFailedError):
        connectors.load_source_dataframe(source)


def test_postgres_connector_rejects_invalid_table_name(fake_psycopg2):
    source = _FakeSource(
        {"host": "db.internal", "port": 5432, "database": "app", "table": "x; drop table y"},
        {"username": "admin", "password": "secret"},
    )

    with pytest.raises(ValidationFailedError):
        connectors.load_source_dataframe(source)

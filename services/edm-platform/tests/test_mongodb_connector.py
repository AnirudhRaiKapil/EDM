"""MongoDB connector tests using mongomock, which emulates the real pymongo API
in-memory -- the same verification tier as the S3/moto tests, exercising actual
pymongo-shaped calls (find/limit, client/db/collection indexing) rather than a
hand-rolled mock."""

import mongomock
import pytest

from app.modules.ingestion import connectors
from app.secrets import encrypt_credentials


class _FakeSource:
    def __init__(self, connection_config, credentials=None):
        self.id = "source-1"
        self.connector_type = "mongodb"
        self.connection_config = connection_config
        self.encrypted_credentials = encrypt_credentials(credentials) if credentials else None
        self.raw_file_path = None


@pytest.fixture()
def mongo_collection(monkeypatch):
    import pymongo

    client = mongomock.MongoClient()
    monkeypatch.setattr(pymongo, "MongoClient", lambda *a, **k: client)
    return client["app"]["customers"]


def test_mongodb_connector_reads_collection(mongo_collection):
    mongo_collection.insert_many([{"name": "Ada", "amount": 91}, {"name": "Lin", "amount": 77}])

    source = _FakeSource({"host": "localhost", "port": 27017, "database": "app", "collection": "customers"})

    df = connectors.load_source_dataframe(source)
    assert list(df["name"]) == ["Ada", "Lin"]
    assert "_id" not in df.columns


def test_mongodb_connector_applies_filter_and_limit(mongo_collection):
    mongo_collection.insert_many(
        [
            {"name": "Ada", "status": "active"},
            {"name": "Lin", "status": "inactive"},
            {"name": "Grace", "status": "active"},
        ]
    )

    source = _FakeSource(
        {
            "host": "localhost",
            "port": 27017,
            "database": "app",
            "collection": "customers",
            "filter": {"status": "active"},
            "limit": 1,
        }
    )

    df = connectors.load_source_dataframe(source)
    assert len(df) == 1
    assert df.iloc[0]["status"] == "active"


def test_mongodb_connector_works_without_credentials(mongo_collection):
    mongo_collection.insert_one({"name": "Ada"})

    source = _FakeSource({"host": "localhost", "port": 27017, "database": "app", "collection": "customers"})

    df = connectors.load_source_dataframe(source)
    assert list(df["name"]) == ["Ada"]

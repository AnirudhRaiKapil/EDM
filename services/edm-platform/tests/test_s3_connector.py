"""S3 connector tests using moto, which emulates the real S3 API in-memory --
unlike the REST/Oracle connector tests, this exercises actual boto3 wire behavior,
not a hand-rolled mock."""

import boto3
import pytest
from moto import mock_aws

from app.secrets import encrypt_credentials


class _FakeSource:
    def __init__(self, connection_config, credentials=None):
        self.id = "source-1"
        self.connector_type = "s3"
        self.connection_config = connection_config
        self.encrypted_credentials = encrypt_credentials(credentials) if credentials else None
        self.raw_file_path = None


@pytest.fixture()
def s3_bucket():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="edm-test-bucket")
        yield client


def test_s3_connector_reads_csv_with_explicit_credentials(s3_bucket):
    from app.modules.ingestion import connectors

    s3_bucket.put_object(Bucket="edm-test-bucket", Key="data/customers.csv", Body=b"name,amount\nAda,91\nLin,77\n")

    source = _FakeSource(
        {"bucket": "edm-test-bucket", "key": "data/customers.csv", "region": "us-east-1"},
        {"access_key_id": "testing", "secret_access_key": "testing"},
    )

    df = connectors.load_source_dataframe(source)
    assert list(df["name"]) == ["Ada", "Lin"]
    assert list(df["amount"]) == [91, 77]


def test_s3_connector_infers_format_from_key_extension(s3_bucket):
    from app.modules.ingestion import connectors

    s3_bucket.put_object(
        Bucket="edm-test-bucket", Key="data/events.json", Body=b'[{"id": 1}, {"id": 2}]'
    )

    source = _FakeSource(
        {"bucket": "edm-test-bucket", "key": "data/events.json", "region": "us-east-1"},
        {"access_key_id": "testing", "secret_access_key": "testing"},
    )

    df = connectors.load_source_dataframe(source)
    assert list(df["id"]) == [1, 2]


def test_s3_connector_without_credentials_uses_default_chain(s3_bucket, monkeypatch):
    from app.modules.ingestion import connectors

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    s3_bucket.put_object(Bucket="edm-test-bucket", Key="data/customers.csv", Body=b"name\nAda\n")

    source = _FakeSource({"bucket": "edm-test-bucket", "key": "data/customers.csv", "region": "us-east-1"})

    df = connectors.load_source_dataframe(source)
    assert list(df["name"]) == ["Ada"]

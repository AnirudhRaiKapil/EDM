import io
import re
import sqlite3
from pathlib import Path

import pandas as pd

from app.modules.core.exceptions import ValidationFailedError
from app.modules.ingestion.rest_client import fetch_paginated_records
from app.modules.source.models import Source
from app.modules.storage.adapter import storage
from app.secrets import decrypt_credentials

_READERS = {
    "csv": pd.read_csv,
    "json": pd.read_json,
}

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _credentials_for(source: Source) -> dict | None:
    if not source.encrypted_credentials:
        return None
    return decrypt_credentials(source.encrypted_credentials)


def _load_sqlite(source: Source) -> pd.DataFrame:
    config = source.connection_config or {}
    db_path = config.get("db_path")
    query = config.get("query")
    table = config.get("table")
    if not db_path:
        raise ValidationFailedError(f"source '{source.id}' is missing connection_config.db_path")
    if not Path(db_path).is_file():
        raise ValidationFailedError(f"sqlite db_path '{db_path}' does not exist")

    if query:
        if not query.strip().lower().startswith("select"):
            raise ValidationFailedError("sqlite source query must be a SELECT statement")
    elif table:
        if not _IDENTIFIER_RE.match(table):
            raise ValidationFailedError(f"invalid table name '{table}'")
        query = f'SELECT * FROM "{table}"'
    else:
        raise ValidationFailedError(f"source '{source.id}' is missing connection_config.query/.table")

    connection = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query(query, connection)
    finally:
        connection.close()


def _load_oracle(source: Source) -> pd.DataFrame:
    import oracledb  # imported lazily: not every install needs the Oracle client

    config = source.connection_config or {}
    credentials = _credentials_for(source) or {}
    query = config.get("query")
    table = config.get("table")

    if query:
        if not query.strip().lower().startswith("select"):
            raise ValidationFailedError("oracle source query must be a SELECT statement")
    elif table:
        if not _IDENTIFIER_RE.match(table):
            raise ValidationFailedError(f"invalid table name '{table}'")
        query = f'SELECT * FROM "{table}"'
    else:
        raise ValidationFailedError(f"source '{source.id}' is missing connection_config.query/.table")

    dsn = f"{config['host']}:{config['port']}/{config['service_name']}"
    connection = oracledb.connect(user=credentials.get("username"), password=credentials.get("password"), dsn=dsn)
    try:
        cursor = connection.cursor()
        cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=columns)
    finally:
        connection.close()


def _load_s3(source: Source) -> pd.DataFrame:
    import boto3  # imported lazily: not every install needs AWS support

    config = source.connection_config or {}
    credentials = _credentials_for(source)
    bucket = config["bucket"]
    key = config["key"]
    file_format = config.get("file_format") or Path(key).suffix.lstrip(".") or "csv"

    session_kwargs = {"region_name": config.get("region")} if config.get("region") else {}
    if credentials and credentials.get("access_key_id"):
        session_kwargs["aws_access_key_id"] = credentials["access_key_id"]
        session_kwargs["aws_secret_access_key"] = credentials.get("secret_access_key")
    # When no explicit credentials are given, boto3 falls back to its default
    # credential chain (env vars / shared config / IAM role) -- the AWS-recommended
    # approach where available, rather than forcing every source to store a key pair.
    client = boto3.client("s3", **session_kwargs)

    body = client.get_object(Bucket=bucket, Key=key)["Body"].read()
    if file_format == "csv":
        return pd.read_csv(io.BytesIO(body))
    if file_format == "json":
        return pd.read_json(io.BytesIO(body))
    if file_format == "parquet":
        return pd.read_parquet(io.BytesIO(body))
    raise ValidationFailedError(f"unsupported s3 file_format '{file_format}'")


def _load_rest_api(source: Source) -> pd.DataFrame:
    config = source.connection_config or {}
    credentials = _credentials_for(source)
    records = fetch_paginated_records(
        config["base_url"], config["path"], credentials, config, config.get("method", "GET")
    )
    return pd.DataFrame(records)


def _load_servicenow(source: Source) -> pd.DataFrame:
    config = source.connection_config or {}
    credentials = _credentials_for(source)
    rest_config = {
        "auth_type": "basic",
        "records_path": "result",
        "pagination": {
            "type": "offset",
            "offset_param": "sysparm_offset",
            "limit_param": "sysparm_limit",
            "size": config.get("page_size", 100),
        },
        "query_params": {"sysparm_query": config["query"]} if config.get("query") else {},
    }
    records = fetch_paginated_records(
        config["instance_url"], f"api/now/table/{config['table']}", credentials, rest_config
    )
    return pd.DataFrame(records)


def _load_jira(source: Source) -> pd.DataFrame:
    config = source.connection_config or {}
    credentials = _credentials_for(source) or {}
    rest_credentials = {"username": credentials.get("email"), "password": credentials.get("api_token")}
    rest_config = {
        "auth_type": "basic",
        "records_path": "issues",
        "pagination": {
            "type": "offset",
            "offset_param": "startAt",
            "limit_param": "maxResults",
            "size": config.get("page_size", 50),
        },
        "query_params": {"jql": config.get("jql", "")},
    }
    records = fetch_paginated_records(
        config["base_url"], "rest/api/3/search", rest_credentials, rest_config
    )
    return pd.DataFrame(records)


def _load_confluence(source: Source) -> pd.DataFrame:
    config = source.connection_config or {}
    credentials = _credentials_for(source) or {}
    rest_credentials = {"username": credentials.get("email"), "password": credentials.get("api_token")}
    query_params = {}
    if config.get("cql"):
        query_params["cql"] = config["cql"]
    elif config.get("space_key"):
        query_params["spaceKey"] = config["space_key"]
    rest_config = {
        "auth_type": "basic",
        "records_path": "results",
        "pagination": {
            "type": "offset",
            "offset_param": "start",
            "limit_param": "limit",
            "size": config.get("page_size", 25),
        },
        "query_params": query_params,
    }
    records = fetch_paginated_records(
        config["base_url"], "wiki/rest/api/content", rest_credentials, rest_config
    )
    return pd.DataFrame(records)


_CONNECTOR_LOADERS = {
    "sqlite": _load_sqlite,
    "oracle": _load_oracle,
    "s3": _load_s3,
    "rest_api": _load_rest_api,
    "servicenow": _load_servicenow,
    "jira": _load_jira,
    "confluence": _load_confluence,
}


def load_source_dataframe(source: Source) -> pd.DataFrame:
    loader = _CONNECTOR_LOADERS.get(source.connector_type)
    if loader is not None:
        return loader(source)

    reader = _READERS.get(source.connector_type)
    if reader is None:
        raise ValidationFailedError(f"no connector implementation for '{source.connector_type}'")
    if not source.raw_file_path:
        raise ValidationFailedError(f"source '{source.id}' has no file attached yet")
    return reader(storage.absolute_path(source.raw_file_path))

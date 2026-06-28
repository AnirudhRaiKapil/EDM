from app.modules.core.exceptions import ValidationFailedError

FILE_BASED_CONNECTOR_TYPES = ["csv", "json"]


def _require_config(config: dict, keys: list[str], connector_type: str) -> None:
    missing = [k for k in keys if not config.get(k)]
    if missing:
        raise ValidationFailedError(
            f"{connector_type} sources require connection_config.{'/'.join(missing)}"
        )


def _require_credentials(credentials: dict | None, keys: list[str], connector_type: str) -> None:
    creds = credentials or {}
    missing = [k for k in keys if not creds.get(k)]
    if missing:
        raise ValidationFailedError(
            f"{connector_type} sources require credentials.{'/'.join(missing)}"
        )


def _validate_sqlite(config: dict, credentials: dict | None) -> None:
    _require_config(config, ["db_path"], "sqlite")
    if not config.get("query") and not config.get("table"):
        raise ValidationFailedError("sqlite sources require connection_config.query or .table")


def _validate_oracle(config: dict, credentials: dict | None) -> None:
    _require_config(config, ["host", "port", "service_name"], "oracle")
    if not config.get("query") and not config.get("table"):
        raise ValidationFailedError("oracle sources require connection_config.query or .table")
    _require_credentials(credentials, ["username", "password"], "oracle")


def _validate_s3(config: dict, credentials: dict | None) -> None:
    _require_config(config, ["bucket", "key"], "s3")
    # credentials are optional: falls back to boto3's default credential chain (env/IAM role)
    # when omitted, which is the AWS-recommended approach where available.


def _validate_rest_api(config: dict, credentials: dict | None) -> None:
    _require_config(config, ["base_url", "path"], "rest_api")
    auth_type = config.get("auth_type", "none")
    if auth_type == "bearer":
        _require_credentials(credentials, ["token"], "rest_api (bearer auth)")
    elif auth_type == "basic":
        _require_credentials(credentials, ["username", "password"], "rest_api (basic auth)")
    elif auth_type == "api_key_header":
        _require_config(config, ["api_key_header_name"], "rest_api (api_key_header auth)")
        _require_credentials(credentials, ["api_key"], "rest_api (api_key_header auth)")
    elif auth_type != "none":
        raise ValidationFailedError(
            "rest_api connection_config.auth_type must be one of: none, bearer, basic, api_key_header"
        )


def _validate_servicenow(config: dict, credentials: dict | None) -> None:
    _require_config(config, ["instance_url", "table"], "servicenow")
    _require_credentials(credentials, ["username", "password"], "servicenow")


def _validate_jira(config: dict, credentials: dict | None) -> None:
    _require_config(config, ["base_url"], "jira")
    _require_credentials(credentials, ["email", "api_token"], "jira")


def _validate_confluence(config: dict, credentials: dict | None) -> None:
    _require_config(config, ["base_url"], "confluence")
    _require_credentials(credentials, ["email", "api_token"], "confluence")


_VALIDATORS = {
    "sqlite": _validate_sqlite,
    "oracle": _validate_oracle,
    "s3": _validate_s3,
    "rest_api": _validate_rest_api,
    "servicenow": _validate_servicenow,
    "jira": _validate_jira,
    "confluence": _validate_confluence,
}


def validate_connector_config(
    connector_type: str, connection_config: dict | None, credentials: dict | None
) -> None:
    validator = _VALIDATORS.get(connector_type)
    if validator is None:
        return  # file-based connectors (csv/json) need no upfront config
    validator(connection_config or {}, credentials)

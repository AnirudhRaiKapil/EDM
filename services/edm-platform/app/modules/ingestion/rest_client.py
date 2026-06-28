import httpx

from app.modules.core.exceptions import ValidationFailedError

MAX_PAGES = 1000
REQUEST_TIMEOUT = 30.0


def _build_auth(auth_type: str, credentials: dict | None, config: dict) -> tuple[dict, httpx.Auth | None]:
    creds = credentials or {}
    headers: dict = {}
    auth: httpx.Auth | None = None

    if auth_type == "bearer":
        headers["Authorization"] = f"Bearer {creds.get('token')}"
    elif auth_type == "basic":
        auth = httpx.BasicAuth(creds.get("username", ""), creds.get("password", ""))
    elif auth_type == "api_key_header":
        headers[config["api_key_header_name"]] = creds.get("api_key", "")
    elif auth_type != "none":
        raise ValidationFailedError(f"unsupported auth_type '{auth_type}'")

    return headers, auth


def _extract_records(payload, records_path: str | None) -> list[dict]:
    data = payload
    if records_path:
        for part in records_path.split("."):
            if isinstance(data, dict):
                data = data.get(part)
            else:
                data = None
            if data is None:
                return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []


def fetch_paginated_records(
    base_url: str,
    path: str,
    credentials: dict | None,
    config: dict,
    method: str = "GET",
    client: httpx.Client | None = None,
) -> list[dict]:
    """`client` is injectable so tests can pass an httpx.Client(transport=MockTransport(...))
    instead of making real network calls."""
    auth_type = config.get("auth_type", "none")
    headers, auth = _build_auth(auth_type, credentials, config)
    headers.update(config.get("headers") or {})
    static_params = dict(config.get("query_params") or {})
    records_path = config.get("records_path")
    pagination = config.get("pagination") or {"type": "none"}

    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    records: list[dict] = []

    owns_client = client is None
    client = client or httpx.Client(timeout=REQUEST_TIMEOUT)
    try:
        if pagination.get("type") == "none":
            response = client.request(method, url, headers=headers, auth=auth, params=static_params)
            response.raise_for_status()
            return _extract_records(response.json(), records_path)

        page_size = pagination.get("size", 100)
        for page_index in range(MAX_PAGES):
            params = dict(static_params)
            if pagination["type"] == "page":
                params[pagination.get("page_param", "page")] = pagination.get("start_page", 1) + page_index
                params[pagination.get("size_param", "limit")] = page_size
            elif pagination["type"] == "offset":
                params[pagination.get("offset_param", "offset")] = page_index * page_size
                params[pagination.get("limit_param", "limit")] = page_size
            else:
                raise ValidationFailedError(f"unsupported pagination.type '{pagination['type']}'")

            response = client.request(method, url, headers=headers, auth=auth, params=params)
            response.raise_for_status()
            batch = _extract_records(response.json(), records_path)
            records.extend(batch)
            if len(batch) < page_size:
                break
    finally:
        if owns_client:
            client.close()

    return records

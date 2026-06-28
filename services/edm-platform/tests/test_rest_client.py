import httpx

from app.modules.ingestion.rest_client import fetch_paginated_records


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_no_pagination_extracts_bare_list():
    def handler(request):
        return httpx.Response(200, json=[{"id": 1}, {"id": 2}])

    records = fetch_paginated_records(
        "https://api.example.com", "things", None, {}, client=_client(handler)
    )
    assert records == [{"id": 1}, {"id": 2}]


def test_records_path_extracts_nested_list():
    def handler(request):
        return httpx.Response(200, json={"result": [{"id": 1}]})

    records = fetch_paginated_records(
        "https://api.example.com", "things", None, {"records_path": "result"}, client=_client(handler)
    )
    assert records == [{"id": 1}]


def test_offset_pagination_stops_on_short_page():
    calls = []

    def handler(request):
        offset = int(request.url.params.get("offset", "0"))
        calls.append(offset)
        if offset == 0:
            return httpx.Response(200, json=[{"id": i} for i in range(2)])
        return httpx.Response(200, json=[{"id": 99}])

    config = {"pagination": {"type": "offset", "size": 2}}
    records = fetch_paginated_records(
        "https://api.example.com", "things", None, config, client=_client(handler)
    )
    assert calls == [0, 2]
    assert records == [{"id": 0}, {"id": 1}, {"id": 99}]


def test_page_pagination_increments_page_number():
    seen_pages = []

    def handler(request):
        page = int(request.url.params.get("page", "1"))
        seen_pages.append(page)
        if page <= 2:
            return httpx.Response(200, json=[{"id": page}, {"id": page * 10}])
        return httpx.Response(200, json=[])

    config = {"pagination": {"type": "page", "size": 2, "start_page": 1}}
    records = fetch_paginated_records(
        "https://api.example.com", "things", None, config, client=_client(handler)
    )
    assert seen_pages == [1, 2, 3]
    assert len(records) == 4


def test_bearer_auth_sets_authorization_header():
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=[])

    fetch_paginated_records(
        "https://api.example.com",
        "things",
        {"token": "abc123"},
        {"auth_type": "bearer"},
        client=_client(handler),
    )
    assert captured["auth"] == "Bearer abc123"


def test_basic_auth_sets_credentials():
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=[])

    fetch_paginated_records(
        "https://api.example.com",
        "things",
        {"username": "user", "password": "pass"},
        {"auth_type": "basic"},
        client=_client(handler),
    )
    assert captured["auth"] is not None and captured["auth"].startswith("Basic ")


def test_api_key_header_auth():
    captured = {}

    def handler(request):
        captured["key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json=[])

    fetch_paginated_records(
        "https://api.example.com",
        "things",
        {"api_key": "secret-key"},
        {"auth_type": "api_key_header", "api_key_header_name": "X-Api-Key"},
        client=_client(handler),
    )
    assert captured["key"] == "secret-key"


def test_raises_on_http_error():
    def handler(request):
        return httpx.Response(500, text="boom")

    try:
        fetch_paginated_records("https://api.example.com", "things", None, {}, client=_client(handler))
        assert False, "expected an exception"
    except httpx.HTTPStatusError:
        pass

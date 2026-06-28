import httpx

from edm_cli.config import get_api_url, load_token


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{status_code}] {detail}")


class ApiClient:
    def __init__(self, require_auth: bool = True):
        self.base_url = get_api_url()
        token = load_token()
        if require_auth and not token:
            raise ApiError(401, "not logged in — run 'edm auth login' first")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=30.0)

    def _handle(self, response: httpx.Response):
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ApiError(response.status_code, detail)
        if response.status_code == 204:
            return None
        return response.json()

    def get(self, path: str, params: dict | None = None):
        return self._handle(self._client.get(path, params=params))

    def post(
        self,
        path: str,
        json: dict | None = None,
        files: dict | None = None,
        params: dict | None = None,
    ):
        return self._handle(self._client.post(path, json=json, files=files, params=params))

    def patch(self, path: str, json: dict | None = None):
        return self._handle(self._client.patch(path, json=json))

    def delete(self, path: str):
        return self._handle(self._client.delete(path))

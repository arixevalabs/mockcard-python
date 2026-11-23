"""HTTP client for the MockCard API (https://www.mockcard.io/openapi.yaml), standard library only.

Author: Arixeva Labs <hello@arixevalabs.com>
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional


class MockCardError(Exception):
    """Raised for every non-2xx API response.

    Attributes:
        status: HTTP status (0 for network errors).
        code: MockCard's machine-readable code, e.g. "invalid_api_key".
    """

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class MockCard:
    """API client.

    Args:
        api_key: Your API key; defaults to the MOCKCARD_API_KEY environment variable.
        base_url: API origin.

    Raises:
        MockCardError: When no API key is given or found.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://www.mockcard.io") -> None:
        self.api_key = api_key or os.environ.get("MOCKCARD_API_KEY", "")
        if not self.api_key:
            raise MockCardError(0, "missing_api_key", "Pass api_key or set MOCKCARD_API_KEY. Create one at https://www.mockcard.io/dashboard.")
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        """Sends an authenticated request.

        Args:
            method: HTTP method.
            path: API path, e.g. "/api/v1/runs".
            body: JSON body, if any.

        Returns:
            The decoded JSON response.

        Raises:
            MockCardError: For non-2xx responses and network failures.
        """
        data = None if body is None else json.dumps(body).encode()
        headers = {"X-Api-Key": self.api_key, "Accept": "application/json", "User-Agent": "mockcard-python/2.0.0"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.loads(res.read() or b"{}")
        except urllib.error.HTTPError as err:
            try:
                error = json.loads(err.read() or b"{}").get("error", {})
            except ValueError:
                error = {}
            raise MockCardError(err.code, error.get("code", "http_error"), error.get("message", f"HTTP {err.code}")) from None
        except urllib.error.URLError as err:
            raise MockCardError(0, "network_error", str(err.reason)) from None

    def list_projects(self) -> list[dict]:
        """Lists your projects."""
        return self.request("GET", "/api/v1/projects")["projects"]

    def create_project(self, name: str, gateway: str = "stripe") -> dict:
        """Creates a project (account-scoped key). Returns the project and its probe secret (shown only now)."""
        return self.request("POST", "/api/v1/projects", {"name": name, "gateway": gateway})

    def create_run(self, **options: Any) -> dict:
        """Creates a run. Options: project_id (required), mode, scenarios, target_url, time_scale, trigger, commit_sha, branch."""
        return self.request("POST", "/api/v1/runs", {k: v for k, v in options.items() if v is not None})

    def get_run(self, run_id: str) -> dict:
        """Reads a run with its score and checks."""
        return self.request("GET", f"/api/v1/runs/{run_id}")["run"]

    def report_results(self, run_id: str, deliveries: list[dict], assertions: Optional[list[dict]] = None) -> dict:
        """Reports pull-run results (once per run). Returns the scored run."""
        return self.request("POST", f"/api/v1/runs/{run_id}/results", {"deliveries": deliveries, "assertions": assertions or []})["run"]

    def health_check(self, webhook_url: str, gateway: str = "stripe") -> dict:
        """Runs the 5-probe webhook health check against a public URL."""
        return self.request("POST", "/api/v1/audit/quick", {"webhook_url": webhook_url, "gateway": gateway})

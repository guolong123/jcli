"""Jenkins API client."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from jcli.sdk.exceptions import (
    JenkinsAPIError,
    JenkinsAuthError,
    JenkinsConnectionError,
    JenkinsCrumbError,
    JenkinsNotFoundError,
)

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 1
RETRYABLE_STATUS_CODES = {503, 504}


class JenkinsClient:
    """Lightweight Jenkins REST API client.

    Supports automatic HTTP Basic Auth, Crumb (CSRF) handling,
    and maps HTTP errors to typed exceptions.
    """

    def __init__(
        self,
        base_url: str,
        username: str = "",
        token: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if username and token:
            self.session.auth = (username, token)

        # Crumb cache: lazily fetched on first POST
        self._crumb_header: str | None = None
        self._crumb_value: str | None = None

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    # ------------------------------------------------------------------
    # Crumb (CSRF token) handling
    # ------------------------------------------------------------------

    def _fetch_crumb(self) -> None:
        """Fetch Jenkins Crumb from ``/crumbIssuer/api/json``.

        Caches the header name and value for subsequent POST requests.
        Raises ``JenkinsCrumbError`` if the fetch fails.
        """
        url = self._url("/crumbIssuer/api/json")
        try:
            resp = self.session.get(url, timeout=10)
        except requests.RequestException as exc:
            raise JenkinsCrumbError(
                f"Failed to connect for crumb: {exc}"
            ) from exc

        if resp.status_code == 404:
            # Crumb issuer disabled – nothing to do
            logger.debug("Crumb issuer not available (404), CSRF protection disabled")
            return

        if resp.status_code != 200:
            raise JenkinsCrumbError(
                f"Crumb fetch failed with status {resp.status_code}"
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise JenkinsCrumbError(
                "Crumb response is not valid JSON"
            ) from exc

        self._crumb_header = data.get("crumbRequestField")
        self._crumb_value = data.get("crumb")
        if not self._crumb_header or not self._crumb_value:
            raise JenkinsCrumbError("Crumb response missing header or value")

        logger.debug("Crumb fetched: %s", self._crumb_header)

    def _ensure_crumb(self) -> dict[str, str]:
        """Return crumb headers, fetching if needed. Empty dict if unavailable."""
        if self._crumb_header and self._crumb_value:
            return {self._crumb_header: self._crumb_value}

        self._fetch_crumb()

        if self._crumb_header and self._crumb_value:
            return {self._crumb_header: self._crumb_value}
        return {}

    # ------------------------------------------------------------------
    # Error mapping
    # ------------------------------------------------------------------

    def _map_error(self, resp: requests.Response) -> None:
        """Raise a typed exception for error status codes."""
        status = resp.status_code
        if status == 401:
            raise JenkinsAuthError(
                f"Authentication failed (401) for {resp.url}"
            )
        if status == 404:
            raise JenkinsNotFoundError(
                f"Resource not found (404) for {resp.url}"
            )
        if status >= 400:
            raise JenkinsAPIError(
                f"API error {status} for {resp.url}",
                status_code=status,
            )

    # ------------------------------------------------------------------
    # Core request method
    # ------------------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: Any = None,
        json: Any = None,
        timeout: int = 30,
        retries: int = MAX_RETRIES,
        **kwargs: Any,
    ) -> requests.Response:
        """Unified HTTP request with error mapping and retry on 503/504.

        :param method: HTTP method (GET, POST, PUT, DELETE, …)
        :param path: URL path relative to base_url
        :param retries: Number of retries on 503/504 (default 1)
        :returns: ``requests.Response``
        :raises JenkinsAuthError: on 401
        :raises JenkinsNotFoundError: on 404
        :raises JenkinsAPIError: on other 4xx
        :raises JenkinsConnectionError: on connection failures
        """
        url = self._url(path)
        req_headers: dict[str, str] = dict(headers) if headers else {}

        # Add crumb for mutating methods
        if method.upper() in ("POST", "PUT", "DELETE"):
            crumb_headers = self._ensure_crumb()
            req_headers.update(crumb_headers)

        last_exc: Exception | None = None
        for attempt in range(1 + retries):
            try:
                resp = self.session.request(
                    method,
                    url,
                    params=params,
                    headers=req_headers,
                    data=data,
                    json=json,
                    timeout=timeout,
                    **kwargs,
                )
            except requests.ConnectionError as exc:
                raise JenkinsConnectionError(
                    f"Connection failed: {exc}"
                ) from exc
            except requests.Timeout as exc:
                raise JenkinsConnectionError(
                    f"Request timed out after {timeout}s"
                ) from exc
            except requests.RequestException as exc:
                raise JenkinsConnectionError(
                    f"Request failed: {exc}"
                ) from exc

            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < retries:
                logger.warning(
                    "Retryable status %d on %s %s (attempt %d/%d)",
                    resp.status_code,
                    method,
                    path,
                    attempt + 1,
                    retries,
                )
                time.sleep(0.1)
                continue

            self._map_error(resp)
            return resp

        # Should not reach here, but safety net
        return resp  # type: ignore[possibly-undefined]

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def get_json(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        tree: str | None = None,
    ) -> Any:
        """GET request returning parsed JSON.

        :param path: URL path relative to base_url
        :param params: Query parameters
        :param tree: Jenkins tree parameter for field filtering
        :returns: Parsed JSON (dict or list)
        """
        if tree:
            params = dict(params) if params else {}
            params["tree"] = tree
        resp = self.request("GET", path, params=params)
        return resp.json()

    def post_xml(self, path: str, xml_data: str | bytes) -> requests.Response:
        """POST with ``application/xml`` content type.

        :param path: URL path relative to base_url
        :param xml_data: XML payload (str or bytes)
        :returns: ``requests.Response``
        """
        return self.request(
            "POST",
            path,
            data=xml_data.encode("utf-8") if isinstance(xml_data, str) else xml_data,
            headers={"Content-Type": "application/xml"},
        )

    def post_data(
        self,
        path: str,
        data: dict[str, Any] | str | bytes,
        content_type: str = "application/x-www-form-urlencoded",
    ) -> requests.Response:
        """POST with arbitrary content type.

        :param path: URL path relative to base_url
        :param data: Form data (dict), raw string, or bytes
        :param content_type: Content-Type header (default form-encoded)
        :returns: ``requests.Response``
        """
        return self.request(
            "POST",
            path,
            data=data,
            headers={"Content-Type": content_type},
        )

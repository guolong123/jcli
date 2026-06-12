"""Jenkins SDK exception hierarchy.

All exceptions inherit from JenkinsError, so callers can catch broadly or narrowly.
"""


class JenkinsError(Exception):
    """Base exception for all Jenkins-related errors."""

    def __init__(self, message: str = "Jenkins error") -> None:
        super().__init__(message)
        self.message = message


class JenkinsAuthError(JenkinsError):
    """Raised when authentication fails (HTTP 401)."""

    def __init__(self, message: str = "Authentication failed (401)") -> None:
        super().__init__(message)


class JenkinsNotFoundError(JenkinsError):
    """Raised when a resource is not found (HTTP 404)."""

    def __init__(self, message: str = "Resource not found (404)") -> None:
        super().__init__(message)


class JenkinsConnectionError(JenkinsError):
    """Raised when connection to Jenkins fails or times out."""

    def __init__(self, message: str = "Connection failed") -> None:
        super().__init__(message)


class JenkinsAPIError(JenkinsError):
    """Raised for non-401/404 API errors.

    Attributes:
        status_code: HTTP status code from the response.
    """

    def __init__(self, message: str = "API error", status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class JenkinsConfigError(JenkinsError):
    """Raised for configuration errors (invalid URL, missing credentials, etc.)."""

    def __init__(self, message: str = "Configuration error") -> None:
        super().__init__(message)


class JenkinsCrumbError(JenkinsError):
    """Raised when Crumb (CSRF token) fetch fails."""

    def __init__(self, message: str = "Crumb fetch failed") -> None:
        super().__init__(message)

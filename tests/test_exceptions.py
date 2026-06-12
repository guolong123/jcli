"""Tests for jcli.sdk.exceptions hierarchy."""

import pytest

from jcli.sdk.exceptions import (
    JenkinsAPIError,
    JenkinsAuthError,
    JenkinsConfigError,
    JenkinsConnectionError,
    JenkinsCrumbError,
    JenkinsError,
    JenkinsNotFoundError,
)


class TestInheritanceChain:
    """All custom exceptions must inherit from JenkinsError (and Exception)."""

    @pytest.mark.parametrize(
        "exc_cls",
        [
            JenkinsAuthError,
            JenkinsNotFoundError,
            JenkinsConnectionError,
            JenkinsAPIError,
            JenkinsConfigError,
            JenkinsCrumbError,
        ],
    )
    def test_subclass_of_jenkins_error(self, exc_cls: type) -> None:
        assert issubclass(exc_cls, JenkinsError)

    @pytest.mark.parametrize(
        "exc_cls",
        [
            JenkinsError,
            JenkinsAuthError,
            JenkinsNotFoundError,
            JenkinsConnectionError,
            JenkinsAPIError,
            JenkinsConfigError,
            JenkinsCrumbError,
        ],
    )
    def test_subclass_of_exception(self, exc_cls: type) -> None:
        assert issubclass(exc_cls, Exception)

    def test_jenkins_error_is_base(self) -> None:
        assert JenkinsError.__bases__ == (Exception,)


class TestMessageAttribute:
    """All exceptions expose a .message attribute and produce meaningful str()."""

    @pytest.mark.parametrize(
        "exc_cls, default_msg",
        [
            (JenkinsError, "Jenkins error"),
            (JenkinsAuthError, "Authentication failed (401)"),
            (JenkinsNotFoundError, "Resource not found (404)"),
            (JenkinsConnectionError, "Connection failed"),
            (JenkinsAPIError, "API error"),
            (JenkinsConfigError, "Configuration error"),
            (JenkinsCrumbError, "Crumb fetch failed"),
        ],
    )
    def test_default_message(self, exc_cls: type, default_msg: str) -> None:
        exc = exc_cls()
        assert exc.message == default_msg
        assert str(exc) == default_msg

    def test_custom_message(self) -> None:
        exc = JenkinsAuthError("Invalid token")
        assert exc.message == "Invalid token"
        assert str(exc) == "Invalid token"

    def test_catch_broad(self) -> None:
        """Catching JenkinsError should catch all sub-exceptions."""
        with pytest.raises(JenkinsError):
            raise JenkinsAuthError("nope")

    def test_catch_specific(self) -> None:
        with pytest.raises(JenkinsNotFoundError):
            raise JenkinsNotFoundError("job 'x' not found")


class TestJenkinsAPIErrorStatusCode:
    """JenkinsAPIError carries an optional status_code."""

    def test_status_code_default_none(self) -> None:
        exc = JenkinsAPIError()
        assert exc.status_code is None

    def test_status_code_set(self) -> None:
        exc = JenkinsAPIError("Server error", status_code=500)
        assert exc.status_code == 500
        assert str(exc) == "Server error"

    def test_status_code_403(self) -> None:
        exc = JenkinsAPIError("Forbidden", status_code=403)
        assert exc.status_code == 403

    def test_is_jenkins_error(self) -> None:
        exc = JenkinsAPIError("err", status_code=422)
        assert isinstance(exc, JenkinsError)

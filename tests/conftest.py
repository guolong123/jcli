"""Shared test fixtures for jcli test suite."""

import pytest
import responses


@pytest.fixture
def mock_jenkins_server():
    """Activate responses mock for Jenkins HTTP calls.

    Usage in tests:
        @responses.activate
        def test_something(mock_jenkins_server):
            ...
    """
    responses.start()
    yield
    responses.stop()
    responses.reset()


@pytest.fixture
def sample_job_list():
    """Sample Jenkins job list response."""
    return {
        "jobs": [
            {
                "name": "test-job",
                "url": "http://jenkins/job/test-job/",
                "color": "blue",
            }
        ]
    }


@pytest.fixture
def sample_build_data():
    """Sample Jenkins build data response."""
    return {
        "number": 1,
        "result": "SUCCESS",
        "duration": 12345,
    }


@pytest.fixture
def jenkins_client():
    """Create a JenkinsClient with a mock base URL and credentials."""
    from jcli.sdk.client import JenkinsClient

    return JenkinsClient(
        base_url="http://jenkins.example.com",
        username="admin",
        token="fake-token",
    )


@pytest.fixture
def jenkins_client_with_crumb():
    """Create a JenkinsClient with pre-cached crumb to skip crumb endpoint mocking."""
    from jcli.sdk.client import JenkinsClient

    client = JenkinsClient(
        base_url="http://jenkins.example.com",
        username="admin",
        token="fake-token",
    )
    client._crumb_header = "Jenkins-Crumb"
    client._crumb_value = "test-crumb"
    return client

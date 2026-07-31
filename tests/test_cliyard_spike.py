"""Spike tests: verify responses can intercept cliyard's HttpClient.

cliyard 的 HttpClient 基于 requests.Session（实例级 _session），模块级
request() 使用 requests.request()。responses 拦截的是 requests 底层
HTTPAdapter.send，对两者均生效。这些测试只验证 mock 拦截能力，
不涉及任何 jcli 业务逻辑。
"""

import pytest
import responses

from cliyard.client.http import HttpClient, request


@responses.activate
def test_http_client_session_get_intercepted():
    """HttpClient._session.request 走 responses mock。"""
    responses.add(
        responses.GET,
        "http://jenkins.example.com/api/json",
        json={"jobs": []},
        status=200,
    )
    client = HttpClient(base_url="http://jenkins.example.com")
    resp = client.request("GET", "/api/json")
    assert resp.status_code == 200
    assert resp.json() == {"jobs": []}


@responses.activate
def test_http_client_session_post_json_intercepted():
    """POST JSON body 经 _session.request 发送并被 mock 拦截。"""
    responses.add(
        responses.POST,
        "http://jenkins.example.com/build",
        json={"result": "ok"},
        status=200,
    )
    client = HttpClient(base_url="http://jenkins.example.com")
    resp = client.request("POST", "/build", data={"param": "value"})
    assert resp.status_code == 200
    assert resp.json() == {"result": "ok"}


@responses.activate
def test_http_client_raises_api_error_on_4xx():
    """4xx 响应抛 cliyard ApiError（无网络请求发生）。"""
    responses.add(
        responses.GET,
        "http://jenkins.example.com/404",
        body="not found",
        status=404,
    )
    client = HttpClient(base_url="http://jenkins.example.com")
    with pytest.raises(Exception) as exc_info:
        client.request("GET", "/404")
    assert exc_info.value.status == 404


@responses.activate
def test_module_level_request_intercepted():
    """模块级 request()（requests.request）同样被 responses 拦截。"""
    responses.add(
        responses.GET,
        "http://jenkins.example.com/health",
        json={"status": "up"},
        status=200,
    )
    resp = request("GET", "http://jenkins.example.com/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "up"}

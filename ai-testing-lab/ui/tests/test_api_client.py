"""Pruebas del cliente HTTP (sin Streamlit runtime)."""

from __future__ import annotations

import httpx
import pytest

from api_client import GatewayClient
from config import UIConfig


def _cfg(**overrides) -> UIConfig:
    base = UIConfig(
        api_base_url="http://ailab-api:8080",
        api_public_url="http://127.0.0.1:8080",
        openapi_docs_url="http://127.0.0.1:8080/docs",
        phoenix_public_url="http://127.0.0.1:6006",
        connect_timeout_s=1.0,
        read_timeout_s=2.0,
        status_cache_ttl_s=30,
    )
    if not overrides:
        return base
    data = base.__dict__.copy()
    data.update(overrides)
    return UIConfig(**data)


class _FakeResp:
    def __init__(self, status_code: int, payload=None, text: str = "", json_error: bool = False):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("not json")
        return self._payload


def test_internal_url_from_config():
    client = GatewayClient(_cfg())
    assert client.base_url == "http://ailab-api:8080"


def test_public_urls_not_used_for_requests():
    cfg = _cfg()
    assert cfg.api_public_url.startswith("http://127.0.0.1")
    assert cfg.api_base_url == "http://ailab-api:8080"
    assert cfg.openapi_docs_url.endswith("/docs")


def test_health_ok(monkeypatch):
    def fake_request(self, method, url, json=None):
        assert method == "GET"
        assert url.endswith("/health")
        return _FakeResp(200, {"status": "ok"})

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    result = GatewayClient(_cfg()).health()
    assert result.ok
    assert result.data["status"] == "ok"


def test_system_status_ok(monkeypatch):
    def fake_request(self, method, url, json=None):
        return _FakeResp(
            200,
            {
                "gateway": "available",
                "components": [],
                "chat_model": "llama3.2:1b",
                "embedding_model": "nomic-embed-text",
                "rag": {},
            },
        )

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    result = GatewayClient(_cfg()).system_status()
    assert result.ok
    assert result.data["chat_model"] == "llama3.2:1b"


def test_timeout(monkeypatch):
    def fake_request(self, method, url, json=None):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    result = GatewayClient(_cfg()).health()
    assert not result.ok
    assert result.error_kind == "timeout"


def test_connection_rejected(monkeypatch):
    def fake_request(self, method, url, json=None):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    result = GatewayClient(_cfg()).health()
    assert not result.ok
    assert result.error_kind == "connection"
    assert "Gateway no disponible" in (result.error_message or "")


def test_invalid_json(monkeypatch):
    def fake_request(self, method, url, json=None):
        return _FakeResp(200, json_error=True)

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    result = GatewayClient(_cfg()).get("/health")
    assert not result.ok
    assert result.error_kind == "invalid_json"


def test_http_500(monkeypatch):
    def fake_request(self, method, url, json=None):
        return _FakeResp(500, {"detail": "boom"})

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    result = GatewayClient(_cfg(api_base_url="http://x")).get("/system/status", retry_once=False)
    assert not result.ok
    assert result.status_code == 500
    assert result.error_kind == "server_error"


def test_http_503(monkeypatch):
    def fake_request(self, method, url, json=None):
        return _FakeResp(503, {"error": {"code": "OLLAMA_UNAVAILABLE"}})

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    result = GatewayClient(_cfg()).get("/chat")
    assert not result.ok
    assert result.status_code == 503
    assert result.error_kind == "unavailable"


def test_optional_fields_absent(monkeypatch):
    def fake_request(self, method, url, json=None):
        return _FakeResp(200, {"gateway": "available", "components": []})

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    result = GatewayClient(_cfg()).system_status()
    assert result.ok
    assert result.data.get("last_evaluation") is None
    assert result.data.get("last_report") is None


def test_sanitized_error_message(monkeypatch):
    long = "x" * 500

    def fake_request(self, method, url, json=None):
        raise httpx.ConnectError(long)

    monkeypatch.setattr(httpx.Client, "request", fake_request)
    result = GatewayClient(_cfg()).health()
    assert result.error_message is not None
    assert len(result.error_message) <= 243

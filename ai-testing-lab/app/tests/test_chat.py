"""Tests de chat (contratos y validación)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from schemas.chat import ChatRequest
from services.chat_service import run_chat
from services.ollama_probe import OllamaUnavailableError


def test_chat_validation_empty_message():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ChatRequest(messages=[{"role": "user", "content": "   "}])


def test_chat_validation_temperature():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ChatRequest(
            messages=[{"role": "user", "content": "hola"}],
            temperature=9.0,
        )


def test_chat_valid_request(client, monkeypatch):
    mock_resp = MagicMock()
    mock_resp.reply = "hola"
    with patch("api.routers.chat.run_chat") as mocked:
        from schemas.chat import ChatResponse

        mocked.return_value = ChatResponse(
            reply="hola",
            model="llama3.2:1b",
            temperature=0.2,
            max_tokens=512,
            duration_ms=1.0,
            trace_id=None,
        )
        resp = client.post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "Hola"}],
                "model": "llama3.2:1b",
                "temperature": 0.2,
                "max_tokens": 64,
            },
        )
    assert resp.status_code == 200
    assert resp.json()["reply"] == "hola"


def test_chat_ollama_unavailable(client):
    with patch("api.routers.chat.run_chat", side_effect=OllamaUnavailableError("down")):
        resp = client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "Hola"}]},
        )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "OLLAMA_UNAVAILABLE"


def test_chat_model_not_found(client):
    with patch("api.routers.chat.run_chat", side_effect=LookupError("no model")):
        resp = client.post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "Hola"}],
                "model": "no-existe:7b",
            },
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MODEL_NOT_FOUND"


def test_run_chat_model_missing_in_tags():
    import pytest

    with patch("services.chat_service.probe_ollama", return_value=True), patch(
        "services.chat_service.list_ollama_tags",
        return_value=[{"name": "llama3.2:1b"}],
    ):
        with pytest.raises(LookupError):
            run_chat(
                ChatRequest(
                    messages=[{"role": "user", "content": "hola"}],
                    model="fantasma:1b",
                )
            )

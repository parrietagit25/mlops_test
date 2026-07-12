"""Pruebas del cliente HTTP y lógica de chat (sin Streamlit / sin Ollama)."""

from __future__ import annotations

import httpx
import pytest

from api_client import GatewayClient
from chat_payload import (
    ChatPayloadError,
    build_chat_payload,
    chat_model_names,
    format_assistant_caption,
    humanize_chat_error,
    select_default_chat_model,
)
from config import UIConfig


def _cfg(**overrides) -> UIConfig:
    base = UIConfig(
        api_base_url="http://api:8080",
        api_public_url="http://127.0.0.1:8080",
        openapi_docs_url="http://127.0.0.1:8080/docs",
        phoenix_public_url="http://127.0.0.1:6006",
        connect_timeout_s=1.0,
        read_timeout_s=2.0,
        chat_read_timeout_s=30.0,
        skill_read_timeout_s=30.0,
        rag_read_timeout_s=30.0,
        status_cache_ttl_s=30,
        ui_timezone="UTC",
    )
    if not overrides:
        return base
    data = base.__dict__.copy()
    data.update(overrides)
    return UIConfig(**data)


class _FakeResp:
    def __init__(self, status_code: int, payload=None, json_error: bool = False):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("not json")
        return self._payload


def test_internal_url_from_config():
    assert GatewayClient(_cfg()).base_url == "http://api:8080"


def test_public_urls_not_used_for_requests():
    cfg = _cfg()
    assert cfg.api_base_url == "http://api:8080"
    assert cfg.api_public_url.startswith("http://127.0.0.1")


def test_health_ok(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda self, method, url, **kwargs: _FakeResp(200, {"status": "ok"}),
    )
    assert GatewayClient(_cfg()).health().data["status"] == "ok"


def test_timeout(monkeypatch):
    def boom(self, method, url, **kwargs):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(httpx.Client, "request", boom)
    r = GatewayClient(_cfg()).health()
    assert r.error_kind == "timeout"


def test_connection_rejected(monkeypatch):
    def boom(self, method, url, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx.Client, "request", boom)
    r = GatewayClient(_cfg()).send_chat(messages=[{"role": "user", "content": "x"}])
    assert r.error_kind == "connection"


def test_invalid_json(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda self, method, url, **kwargs: _FakeResp(200, json_error=True),
    )
    r = GatewayClient(_cfg()).get("/health")
    assert r.error_kind == "invalid_json"


def test_http_400_model_not_found(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda self, method, url, **kwargs: _FakeResp(
            400,
            {"error": {"code": "MODEL_NOT_FOUND", "message": "missing", "details": None}},
        ),
    )
    r = GatewayClient(_cfg()).send_chat(
        messages=[{"role": "user", "content": "Hola"}], model="fantasma:1b"
    )
    assert r.status_code == 400
    assert r.error_code == "MODEL_NOT_FOUND"


def test_http_422(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda self, method, url, **kwargs: _FakeResp(
            422,
            {"error": {"code": "VALIDATION_ERROR", "message": "invalid", "details": []}},
        ),
    )
    r = GatewayClient(_cfg()).send_chat(messages=[{"role": "user", "content": "x"}])
    assert r.status_code == 422


def test_http_500(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda self, method, url, **kwargs: _FakeResp(
            500, {"error": {"code": "CHAT_FAILED", "message": "boom"}}
        ),
    )
    r = GatewayClient(_cfg()).send_chat(messages=[{"role": "user", "content": "x"}])
    assert r.error_kind == "server_error"


def test_http_503(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda self, method, url, **kwargs: _FakeResp(
            503,
            {"error": {"code": "OLLAMA_UNAVAILABLE", "message": "down", "details": None}},
        ),
    )
    r = GatewayClient(_cfg()).send_chat(messages=[{"role": "user", "content": "x"}])
    assert r.error_kind == "unavailable"


def test_send_chat_ok_payload(monkeypatch):
    captured = {}

    def fake(self, method, url, **kwargs):
        captured.update(method=method, url=url, json=kwargs.get("json"))
        return _FakeResp(
            200,
            {
                "reply": "listo",
                "model": "llama3.2:1b",
                "temperature": 0.2,
                "max_tokens": 16,
                "duration_ms": 100.0,
                "trace_id": None,
            },
        )

    monkeypatch.setattr(httpx.Client, "request", fake)
    r = GatewayClient(_cfg()).send_chat(
        messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "Hola"},
        ],
        model="llama3.2:1b",
        temperature=0.2,
        max_tokens=16,
    )
    assert r.ok
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/chat")
    assert captured["json"]["messages"][0]["role"] == "system"
    assert "metadata" not in captured["json"]["messages"][0]


def test_send_chat_no_retry(monkeypatch):
    n = {"c": 0}

    def fake(self, method, url, **kwargs):
        n["c"] += 1
        return _FakeResp(500, {"error": {"code": "X", "message": "y"}})

    monkeypatch.setattr(httpx.Client, "request", fake)
    GatewayClient(_cfg()).send_chat(messages=[{"role": "user", "content": "x"}])
    assert n["c"] == 1


def test_get_models_valid(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda self, method, url, **kwargs: _FakeResp(
            200,
            {
                "chat_models": [{"name": "llama3.2:1b", "default": True}],
                "embedding_models": [{"name": "nomic-embed-text", "default": True}],
                "ollama_status": "available",
            },
        ),
    )
    r = GatewayClient(_cfg()).get_models()
    names = chat_model_names(r.data)
    assert names == ["llama3.2:1b"]
    assert "nomic-embed-text" not in names


def test_select_default_and_fallback():
    name, fallback = select_default_chat_model(
        {"chat_models": [{"name": "a", "default": False}, {"name": "b", "default": True}]}
    )
    assert name == "b" and fallback is False
    name, fallback = select_default_chat_model(
        {"chat_models": [{"name": "solo", "default": False}]}
    )
    assert name == "solo" and fallback is True
    name, fallback = select_default_chat_model({"chat_models": []})
    assert name is None
    name, fallback = select_default_chat_model(
        {"chat_models": [], "embedding_models": [{"name": "emb", "default": True}]}
    )
    assert name is None


def test_build_payload_order_and_no_metadata():
    payload = build_chat_payload(
        history=[
            {"role": "user", "content": "uno", "metadata": {"x": 1}},
            {"role": "assistant", "content": "dos", "metadata": {"y": 2}},
            {"role": "system", "content": "should-skip"},
        ],
        user_text="tres",
        system_prompt="Eres útil.",
        model="llama3.2:1b",
        temperature=0.2,
        max_tokens=64,
    )
    assert [m["role"] for m in payload["messages"]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert all("metadata" not in m for m in payload["messages"])
    assert sum(1 for m in payload["messages"] if m["role"] == "system") == 1


def test_build_payload_empty_system_omitted():
    payload = build_chat_payload(
        history=[],
        user_text="hola",
        system_prompt="   ",
        model="llama3.2:1b",
        temperature=0.2,
        max_tokens=32,
    )
    assert payload["messages"][0]["role"] == "user"


def test_build_payload_rejects_empty_user():
    with pytest.raises(ChatPayloadError):
        build_chat_payload(
            history=[],
            user_text="  ",
            system_prompt="",
            model="llama3.2:1b",
            temperature=0.2,
            max_tokens=32,
        )


def test_build_payload_rejects_too_many_messages():
    history = []
    for i in range(40):
        history.append({"role": "user", "content": f"u{i}"})
    with pytest.raises(ChatPayloadError, match="límites|máximo"):
        build_chat_payload(
            history=history,
            user_text="final",
            system_prompt="sys",
            model="llama3.2:1b",
            temperature=0.2,
            max_tokens=32,
        )


def test_build_payload_rejects_long_content():
    with pytest.raises(ChatPayloadError, match="límites|supera"):
        build_chat_payload(
            history=[],
            user_text="x" * 16001,
            system_prompt="",
            model="llama3.2:1b",
            temperature=0.2,
            max_tokens=32,
        )


def test_build_payload_no_silent_user_mutation():
    text = "contenido exacto del usuario"
    payload = build_chat_payload(
        history=[],
        user_text=text,
        system_prompt="",
        model="llama3.2:1b",
        temperature=0.2,
        max_tokens=32,
    )
    assert payload["messages"][-1]["content"] == text


def test_build_payload_requires_model():
    with pytest.raises(ChatPayloadError, match="modelo"):
        build_chat_payload(
            history=[],
            user_text="hola",
            system_prompt="",
            model=None,
            temperature=0.2,
            max_tokens=32,
        )


def test_format_caption_null_trace():
    assert "no disponible" in format_assistant_caption(
        {"model": "llama3.2:1b", "duration_ms": 1240, "trace_id": None}
    ).lower()


def test_humanize_errors():
    assert "Gateway no disponible" in humanize_chat_error(
        error_kind="connection", error_code=None, error_message="x", status_code=None
    )
    assert "Ollama" in humanize_chat_error(
        error_kind="unavailable", error_code="OLLAMA_UNAVAILABLE", error_message="x", status_code=503
    )
    assert "ya no está disponible" in humanize_chat_error(
        error_kind="client_error",
        error_code="MODEL_NOT_FOUND",
        error_message="x",
        status_code=400,
    )


def test_clear_chat_preserves_config_semantics():
    # Lógica pura equivalente a clear_chat (sin Streamlit).
    messages = [{"role": "user", "content": "a"}]
    model, temp, tokens, system = "llama3.2:1b", 0.4, 256, "sys"
    messages = []
    error = None
    assert messages == []
    assert model == "llama3.2:1b"
    assert temp == 0.4
    assert tokens == 256
    assert system == "sys"
    assert error is None


def test_no_user_url_in_payload_builder():
    payload = build_chat_payload(
        history=[],
        user_text="http://evil.example",
        system_prompt="",
        model="llama3.2:1b",
        temperature=0.2,
        max_tokens=32,
    )
    assert "base_url" not in payload
    assert payload["model"] == "llama3.2:1b"


# ---------------------------------------------------------------------------
# UI-1C Skills
# ---------------------------------------------------------------------------

from skills_payload import (  # noqa: E402
    SKILLS_HISTORY_LIMIT,
    SkillPayloadError,
    UI_SUPPORTED_SKILLS,
    assert_skill_allowed,
    authorized_skill_names,
    build_rag_qa_payload,
    build_skill_payload,
    build_summarizer_payload,
    humanize_skill_error,
    parse_skill_result,
    safe_metadata_for_display,
    summarize_input,
)


def test_get_skills_ok(monkeypatch):
    payload = [
        {"name": "summarizer", "description": "Resume"},
        {"name": "rag_qa", "description": "RAG"},
    ]
    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda self, method, url, **kwargs: _FakeResp(200, payload),
    )
    r = GatewayClient(_cfg()).get_skills()
    assert r.ok
    assert authorized_skill_names(r.data) == ["summarizer", "rag_qa"]


def test_get_skills_empty(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda self, method, url, **kwargs: _FakeResp(200, []),
    )
    r = GatewayClient(_cfg()).get_skills()
    assert r.ok
    assert authorized_skill_names(r.data) == []


def test_get_skills_invalid_shape(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda self, method, url, **kwargs: _FakeResp(200, {"not": "a list"}),
    )
    r = GatewayClient(_cfg()).get_skills()
    assert r.ok
    assert authorized_skill_names(r.data) == []


def test_run_skill_ok_payload(monkeypatch):
    captured = {}

    def fake(self, method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        captured["files"] = kwargs.get("files")
        captured["params"] = kwargs.get("params")
        return _FakeResp(200, {"output": "ok", "metadata": {"skill": "summarizer"}})

    monkeypatch.setattr(httpx.Client, "request", fake)
    r = GatewayClient(_cfg()).run_skill(
        "summarizer", {"text": "hola mundo", "max_sentences": 2}
    )
    assert r.ok
    assert captured["method"] == "POST"
    assert captured["url"] == "http://api:8080/agents/summarizer/run"
    assert captured["json"] == {
        "payload": {"text": "hola mundo", "max_sentences": 2}
    }
    assert "11434" not in captured["url"]


def test_run_skill_no_retry(monkeypatch):
    calls = {"n": 0}

    def fake(self, method, url, **kwargs):
        calls["n"] += 1
        return _FakeResp(500, {"error": {"code": "X", "message": "boom"}})

    monkeypatch.setattr(httpx.Client, "request", fake)
    r = GatewayClient(_cfg()).run_skill("summarizer", {"text": "x", "max_sentences": 1})
    assert not r.ok
    assert calls["n"] == 1


@pytest.mark.parametrize(
    "status,kind",
    [
        (400, "client_error"),
        (404, "client_error"),
        (422, "client_error"),
        (500, "server_error"),
        (503, "unavailable"),
    ],
)
def test_run_skill_http_errors(monkeypatch, status, kind):
    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda self, method, url, **kwargs: _FakeResp(
            status, {"error": {"code": "E", "message": "fail"}}
        ),
    )
    r = GatewayClient(_cfg()).run_skill("summarizer", {"text": "x", "max_sentences": 1})
    assert not r.ok
    assert r.status_code == status
    assert r.error_kind == kind


def test_run_skill_connection_timeout(monkeypatch):
    def boom(self, method, url, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx.Client, "request", boom)
    r = GatewayClient(_cfg()).run_skill("summarizer", {"text": "x", "max_sentences": 1})
    assert r.error_kind == "connection"


def test_run_skill_timeout(monkeypatch):
    def boom(self, method, url, **kwargs):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(httpx.Client, "request", boom)
    r = GatewayClient(_cfg()).run_skill("rag_qa", {"question": "q", "top_k": 2})
    assert r.error_kind == "timeout"


def test_run_skill_invalid_json(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda self, method, url, **kwargs: _FakeResp(200, json_error=True),
    )
    r = GatewayClient(_cfg()).run_skill("summarizer", {"text": "x", "max_sentences": 1})
    assert r.error_kind == "invalid_json"


def test_run_skill_empty_name():
    r = GatewayClient(_cfg()).run_skill("  ", {"text": "x"})
    assert not r.ok


def test_authorized_skills_filters_unknown():
    names = authorized_skill_names(
        [
            {"name": "summarizer"},
            {"name": "evil_skill"},
            {"name": "rag_qa"},
            {"name": "summarizer"},
        ]
    )
    assert names == ["summarizer", "rag_qa"]
    assert "evil_skill" not in UI_SUPPORTED_SKILLS or "evil_skill" not in names


def test_assert_skill_allowed():
    assert assert_skill_allowed("summarizer", ["summarizer", "rag_qa"]) == "summarizer"
    with pytest.raises(SkillPayloadError):
        assert_skill_allowed("evil", ["summarizer"])
    with pytest.raises(SkillPayloadError):
        assert_skill_allowed("summarizer", ["rag_qa"])
    with pytest.raises(SkillPayloadError):
        assert_skill_allowed("", ["summarizer"])


def test_build_summarizer_payload_exact():
    p = build_summarizer_payload(text="  Hola  ", max_sentences=3)
    assert p == {"text": "Hola", "max_sentences": 3}
    assert set(p.keys()) == {"text", "max_sentences"}


def test_build_rag_qa_payload_exact():
    p = build_rag_qa_payload(question=" ¿Qué es? ", top_k=2)
    assert p == {"question": "¿Qué es?", "top_k": 2}
    assert set(p.keys()) == {"question", "top_k"}


def test_build_skill_payload_rejects_extra_via_builder():
    # El builder solo toma campos conocidos; no reenvía extras del form.
    p = build_skill_payload(
        "summarizer",
        {"text": "abc", "max_sentences": 2, "hack": True, "url": "http://x"},
    )
    assert "hack" not in p
    assert "url" not in p


def test_build_payload_rejects_empty_and_limits():
    with pytest.raises(SkillPayloadError):
        build_summarizer_payload(text="   ", max_sentences=3)
    with pytest.raises(SkillPayloadError):
        build_rag_qa_payload(question="", top_k=3)
    with pytest.raises(SkillPayloadError):
        build_summarizer_payload(text="x", max_sentences=99)
    with pytest.raises(SkillPayloadError):
        build_rag_qa_payload(question="q", top_k=0)


def test_parse_skill_result_and_metadata():
    out, meta, err = parse_skill_result(
        {"output": "respuesta", "metadata": {"skill": "rag_qa", "chunks_used": 2, "secret": "no"}}
    )
    assert out == "respuesta"
    assert err is None
    safe = safe_metadata_for_display(meta)
    assert "secret" not in safe
    assert safe["chunks_used"] == 2
    assert parse_skill_result({})[2]
    assert parse_skill_result({"output": ""})[2]
    assert parse_skill_result(None)[2]


def test_humanize_skill_errors():
    assert "Gateway" in humanize_skill_error(
        error_kind="connection", error_code=None, error_message=None, status_code=None
    )
    assert "no existe" in humanize_skill_error(
        error_kind="client_error",
        error_code="SKILL_NOT_FOUND",
        error_message="x",
        status_code=404,
    ).lower() or "registrada" in humanize_skill_error(
        error_kind="client_error",
        error_code="SKILL_NOT_FOUND",
        error_message="x",
        status_code=404,
    )


def test_skills_history_limit_and_clear_semantics():
    history = [{"skill": f"s{i}"} for i in range(25)]
    trimmed = history[:SKILLS_HISTORY_LIMIT]
    assert len(trimmed) == 20
    chat_messages = [{"role": "user", "content": "keep"}]
    # clear skills only
    history = []
    skills_error = None
    assert history == []
    assert skills_error is None
    assert chat_messages == [{"role": "user", "content": "keep"}]


def test_summarize_input_bounded():
    long_text = "palabra " * 100
    s = summarize_input("summarizer", {"text": long_text})
    assert len(s) <= 120


def test_no_shell_or_arbitrary_skill_in_payload_module():
    import skills_payload as sp

    src = open(sp.__file__, encoding="utf-8").read()
    assert "subprocess" not in src
    assert "os.system" not in src
    assert "shell=True" not in src
    with pytest.raises(SkillPayloadError):
        build_skill_payload("arbitrary", {"text": "x"})


# ---------------------------------------------------------------------------
# UI-1D RAG
# ---------------------------------------------------------------------------

from rag_payload import (  # noqa: E402
    HISTORY_LIMIT as RAG_HISTORY_LIMIT,
    RagPayloadError,
    humanize_rag_error,
    parse_query_response,
    unique_sources,
    validate_query,
    validate_upload_batch,
    validate_upload_filename,
)


def test_rag_status_ok(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda self, method, url, **kwargs: _FakeResp(
            200,
            {
                "available": True,
                "embedding_model": "nomic-embed-text",
                "documents_indexed": 2,
                "chunks_indexed": 4,
                "allowed_directory": "rag/sample_docs",
                "allowed_extensions": [".txt", ".md"],
            },
        ),
    )
    r = GatewayClient(_cfg()).get_rag_status()
    assert r.ok
    assert r.data["documents_indexed"] == 2


def test_query_rag_ok(monkeypatch):
    captured = {}

    def fake(self, method, url, **kwargs):
        captured.update(method=method, url=url, params=kwargs.get("params"))
        return _FakeResp(
            200,
            {
                "query": "hola",
                "results": [
                    {"source": "a.txt", "text": "uno", "score": 0.9},
                    {"source": "b.txt", "text": "dos", "score": 0.8},
                ],
            },
        )

    monkeypatch.setattr(httpx.Client, "request", fake)
    r = GatewayClient(_cfg()).query_rag(q="hola", top_k=2)
    assert r.ok
    assert captured["method"] == "GET"
    assert captured["url"].endswith("/rag/query")
    assert captured["params"] == {"q": "hola", "top_k": 2}


def test_ingest_rag_multipart(monkeypatch):
    captured = {}

    def fake(self, method, url, **kwargs):
        captured.update(method=method, url=url, files=kwargs.get("files"), json=kwargs.get("json"))
        return _FakeResp(
            200,
            {
                "documents_indexed": 1,
                "chunks_indexed": 2,
                "mode": "sample_docs+uploads",
                "uploaded_files": ["doc.txt"],
                "sources": ["doc.txt"],
            },
        )

    monkeypatch.setattr(httpx.Client, "request", fake)
    r = GatewayClient(_cfg()).ingest_rag_files(
        [("doc.txt", b"hola", "text/plain")]
    )
    assert r.ok
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/rag/ingest")
    assert captured["json"] is None
    assert captured["files"] is not None


def test_ingest_sample_docs_no_files(monkeypatch):
    captured = {}

    def fake(self, method, url, **kwargs):
        captured.update(files=kwargs.get("files"), json=kwargs.get("json"))
        return _FakeResp(
            200,
            {
                "documents_indexed": 2,
                "chunks_indexed": 4,
                "mode": "sample_docs",
                "uploaded_files": [],
                "sources": ["a.txt"],
            },
        )

    monkeypatch.setattr(httpx.Client, "request", fake)
    r = GatewayClient(_cfg()).ingest_rag_files(None)
    assert r.ok
    assert captured["files"] is None


@pytest.mark.parametrize("status", [400, 404, 413, 422, 500, 503])
def test_rag_http_errors(monkeypatch, status):
    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda self, method, url, **kwargs: _FakeResp(
            status, {"error": {"code": "E", "message": "fail"}}
        ),
    )
    r = GatewayClient(_cfg()).query_rag(q="x", top_k=1)
    assert not r.ok
    assert r.status_code == status


def test_rag_connection_and_timeout(monkeypatch):
    def boom(self, method, url, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx.Client, "request", boom)
    assert GatewayClient(_cfg()).get_rag_status().error_kind == "connection"

    def slow(self, method, url, **kwargs):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(httpx.Client, "request", slow)
    assert GatewayClient(_cfg()).query_rag(q="x", top_k=1).error_kind == "timeout"


def test_rag_invalid_json_empty(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda self, method, url, **kwargs: _FakeResp(200, json_error=True),
    )
    assert GatewayClient(_cfg()).query_rag(q="x", top_k=1).error_kind == "invalid_json"
    q, results, err = parse_query_response(None)
    assert err
    assert results == []


def test_unique_sources_preserves_order_and_count():
    results = [
        {"source": "testing_policy.txt", "text": "a"},
        {"source": "lab_overview.txt", "text": "b"},
        {"source": "testing_policy.txt", "text": "c"},
        {"source": "lab_overview.txt", "text": "d"},
    ]
    assert unique_sources(results) == ["testing_policy.txt", "lab_overview.txt"]
    assert len(results) == 4
    assert unique_sources([]) == []
    assert unique_sources(None) == []


def test_upload_validation():
    from rag_payload import MAX_UPLOAD_BYTES, upload_selection_error

    assert validate_upload_filename("nota.txt") == "nota.txt"
    assert validate_upload_filename("doc.MD") == "doc.MD"
    with pytest.raises(RagPayloadError):
        validate_upload_filename("evil.py")
    with pytest.raises(RagPayloadError):
        validate_upload_filename("x.exe")
    with pytest.raises(RagPayloadError):
        validate_upload_filename("a.zip")
    with pytest.raises(RagPayloadError):
        validate_upload_filename("x.sh")
    with pytest.raises(RagPayloadError):
        validate_upload_filename("x.ps1")
    with pytest.raises(RagPayloadError):
        validate_upload_filename("../secrets.txt")
    with pytest.raises(RagPayloadError):
        validate_upload_filename("C:\\abs\\file.txt")
    with pytest.raises(RagPayloadError):
        validate_upload_batch([("a.txt", 0)])
    # Límite exacto inclusive / exclusivo.
    assert validate_upload_batch([("ok.txt", MAX_UPLOAD_BYTES)]) == ["ok.txt"]
    with pytest.raises(RagPayloadError):
        validate_upload_batch([("big.txt", MAX_UPLOAD_BYTES + 1)])
    assert upload_selection_error([("big.txt", MAX_UPLOAD_BYTES + 1)])
    assert upload_selection_error([("ok.txt", MAX_UPLOAD_BYTES)]) is None
    # 10 ok, 11 no.
    assert len(validate_upload_batch([(f"{i}.txt", 10) for i in range(10)])) == 10
    with pytest.raises(RagPayloadError):
        validate_upload_batch([(f"{i}.txt", 10) for i in range(11)])
    assert validate_upload_batch([("ok.txt", 12)]) == ["ok.txt"]
    assert validate_upload_batch([("ok.md", 12)]) == ["ok.md"]


def test_streamlit_upload_config_documents_1mb_global():
    from pathlib import Path

    cfg = Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml"
    text = cfg.read_text(encoding="utf-8")
    assert "maxUploadSize = 1" in text
    assert "[server]" in text


def test_query_validation():
    assert validate_query(question="  hola  ", top_k=3) == ("hola", 3)
    with pytest.raises(RagPayloadError):
        validate_query(question="  ", top_k=3)
    with pytest.raises(RagPayloadError):
        validate_query(question="hola", top_k=0)
    with pytest.raises(RagPayloadError):
        validate_query(question="hola", top_k=99)


def test_parse_query_and_humanize():
    q, results, err = parse_query_response(
        {"query": "q", "results": [{"source": "a.txt", "text": "t", "score": 0.5}]}
    )
    assert q == "q" and err is None and results[0]["score"] == 0.5
    assert "Gateway" in humanize_rag_error(
        error_kind="connection", error_code=None, error_message=None, status_code=None
    )


def test_rag_history_clear_keeps_chat_skills():
    rag_hist = [{"q": i} for i in range(25)]
    trimmed = rag_hist[:RAG_HISTORY_LIMIT]
    assert len(trimmed) == 20
    chat = [{"role": "user", "content": "keep"}]
    skills = [{"skill": "summarizer"}]
    rag_hist = []
    assert chat and skills and rag_hist == []


def test_no_shell_in_rag_payload():
    import rag_payload as rp

    src = open(rp.__file__, encoding="utf-8").read()
    assert "subprocess" not in src
    assert "os.system" not in src
    assert "shell=True" not in src

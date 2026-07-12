"""Tests de uploads RAG y endpoints auxiliares."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch


def test_rag_status(client):
    resp = client.get("/rag/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "embedding_model" in data
    assert ".txt" in data["allowed_extensions"]
    assert "vector" in data["warning"].lower() or "RAG" in data["warning"]


def test_health_and_system(client):
    assert client.get("/health").json() == {"status": "ok"}
    with patch("services.system_status.probe_ollama", return_value=True), patch(
        "services.system_status.probe_phoenix", return_value=True
    ):
        resp = client.get("/system/status")
    assert resp.status_code == 200
    assert resp.json()["phase"] == "1-local"


def test_observability(client):
    with patch("api.routers.observability.probe_phoenix", return_value=True):
        resp = client.get("/observability")
    assert resp.status_code == 200
    assert resp.json()["phoenix"]["url"].startswith("http://")


def test_models_unavailable(client):
    with patch("services.models_service.list_ollama_tags", side_effect=Exception("down")):
        # models_service catches OllamaUnavailableError specifically
        from services.ollama_probe import OllamaUnavailableError

        with patch(
            "services.models_service.list_ollama_tags",
            side_effect=OllamaUnavailableError("down"),
        ):
            resp = client.get("/models")
    assert resp.status_code == 200
    assert resp.json()["ollama_status"] == "unavailable"


def test_upload_txt_ok(client):
    with patch("api.routers.rag_ext.ingest_directories", return_value={
        "documents_indexed": 1,
        "chunks_indexed": 2,
        "sources": ["hello.txt"],
    }):
        resp = client.post(
            "/rag/ingest",
            files=[("files", ("hello.txt", BytesIO(b"hola mundo"), "text/plain"))],
        )
    assert resp.status_code == 200
    assert "hello.txt" in resp.json()["uploaded_files"]


def test_upload_md_ok(client):
    with patch("api.routers.rag_ext.ingest_directories", return_value={
        "documents_indexed": 1,
        "chunks_indexed": 1,
        "sources": ["n.md"],
    }):
        resp = client.post(
            "/rag/ingest",
            files=[("files", ("n.md", BytesIO(b"# title"), "text/markdown"))],
        )
    assert resp.status_code == 200


def test_upload_py_rejected(client):
    resp = client.post(
        "/rag/ingest",
        files=[("files", ("x.py", BytesIO(b"print(1)"), "text/x-python"))],
    )
    assert resp.status_code == 400


def test_upload_exe_rejected(client):
    resp = client.post(
        "/rag/ingest",
        files=[("files", ("x.exe", BytesIO(b"MZ"), "application/octet-stream"))],
    )
    assert resp.status_code == 400


def test_upload_too_large(client, monkeypatch):
    monkeypatch.setenv("RAG_MAX_UPLOAD_BYTES", "10")
    from core.config import get_settings

    get_settings.cache_clear()
    resp = client.post(
        "/rag/ingest",
        files=[("files", ("big.txt", BytesIO(b"x" * 50), "text/plain"))],
    )
    # Re-import may still use old settings on router — force via service
    assert resp.status_code in (400, 413)


def test_ingest_without_files_compatible(client):
    with patch("api.routers.rag_ext.ingest_directories", return_value={
        "documents_indexed": 2,
        "chunks_indexed": 4,
        "sources": ["a.txt", "b.txt"],
    }):
        resp = client.post("/rag/ingest")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "sample_docs"
    assert resp.json()["documents_indexed"] == 2

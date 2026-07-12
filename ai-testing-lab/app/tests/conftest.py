"""Fixtures comunes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.config import get_settings
from core.llm_client import reset_llm_client
from services.job_manager import reset_job_manager


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Aislar reports/ bajo tmp
    monkeypatch.setenv("LAB_ROOT", str(tmp_path))
    get_settings.cache_clear()
    reset_llm_client()
    reset_job_manager()
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)

    from api.main import app

    with TestClient(app) as c:
        yield c

    reset_job_manager()
    get_settings.cache_clear()
    reset_llm_client()

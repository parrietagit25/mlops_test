"""Timeout controlado del eval runner."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from schemas.evals import EvalSuite
from services.eval_runner import EvalRunnerError, run_suite
from services.job_manager import JobRecord


def test_eval_timeout(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_ROOT", str(tmp_path))
    monkeypatch.setenv("EVAL_TIMEOUT_SECONDS", "1")
    from core.config import get_settings

    get_settings.cache_clear()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    script = scripts / "run_deepeval.sh"
    script.write_text("#!/bin/bash\nsleep 30\n", encoding="utf-8")

    record = JobRecord(
        job_id="t1",
        suite=EvalSuite.deepeval,
        status="running",
        created_at="2026-01-01T00:00:00+00:00",
    )

    with patch("services.eval_runner.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["x"], timeout=1)):
        with pytest.raises(EvalRunnerError, match="Timeout"):
            run_suite(EvalSuite.deepeval, record)
    assert record.error is not None

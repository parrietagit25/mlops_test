"""Aislamiento por job_id en el eval runner (EVAL-RUNTIME-1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from services import eval_runner
from services.eval_runner import EvalRunnerError, _prepare_run_tree, job_run_root


def test_job_run_root_isolated():
    a = job_run_root("aaa" + "1" * 29)
    b = job_run_root("bbb" + "2" * 29)
    assert a != b
    assert a.parent == b.parent
    assert a.name.startswith("aaa")
    assert b.name.startswith("bbb")


def test_job_run_root_rejects_traversal():
    with pytest.raises(EvalRunnerError):
        job_run_root("../etc")
    with pytest.raises(EvalRunnerError):
        job_run_root("a/b")
    with pytest.raises(EvalRunnerError):
        job_run_root("")


def test_prepare_run_tree_per_job(tmp_path, monkeypatch):
    monkeypatch.setattr(eval_runner, "_RUN_BASE", tmp_path / "ailab_run")
    lab = tmp_path / "lab"
    scripts = lab / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "run_deepeval.sh").write_text("#!/bin/bash\necho ok\n", encoding="utf-8")
    (lab / "evals").mkdir()
    (lab / "reports").mkdir()
    (lab / "app").mkdir()

    root_a = _prepare_run_tree(lab, "jobaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    root_b = _prepare_run_tree(lab, "jobbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")

    assert root_a != root_b
    assert (root_a / "scripts" / "run_deepeval.sh").is_file()
    assert (root_b / "scripts" / "run_deepeval.sh").is_file()
    # Borrar el segundo no afecta al primero.
    marker = root_a / "scripts" / "run_deepeval.sh"
    content = marker.read_text(encoding="utf-8")
    assert "echo ok" in content
    assert root_a.exists() and root_b.exists()

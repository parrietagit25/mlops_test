"""Tests de evaluaciones / jobs."""

from __future__ import annotations

import time
from unittest.mock import patch

from schemas.evals import EvalSuite
from services.job_manager import DuplicateSuiteError, JobRecord, get_job_manager, reset_job_manager


def test_invalid_suite(client):
    resp = client.post("/evals/not-a-suite/run")
    assert resp.status_code == 422


def test_valid_suite_queues_job(client):
    def fake_runner(record: JobRecord) -> None:
        record.summary = "ok"
        time.sleep(0.05)

    with patch("api.routers.evals.run_suite", side_effect=lambda suite, record: fake_runner(record)):
        resp = client.post("/evals/deepeval/run")
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] in ("queued", "running", "completed")
    job_id = body["job_id"]

    # Esperar a que termine
    for _ in range(50):
        detail = client.get(f"/evals/jobs/{job_id}").json()
        if detail["status"] in ("completed", "failed"):
            break
        time.sleep(0.05)
    assert detail["status"] == "completed"


def test_duplicate_suite(client):
    gate = {"release": False}

    def blocking_runner(record: JobRecord) -> None:
        while not gate["release"]:
            time.sleep(0.02)
        record.summary = "done"

    with patch("api.routers.evals.run_suite", side_effect=lambda s, r: blocking_runner(r)):
        first = client.post("/evals/ragas/run")
        assert first.status_code == 202
        second = client.post("/evals/ragas/run")
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "DUPLICATE_SUITE"
        gate["release"] = True
        # drain
        time.sleep(0.2)


def test_job_not_found(client):
    resp = client.get("/evals/jobs/doesnotexist")
    assert resp.status_code == 404


def test_list_jobs(client):
    with patch("api.routers.evals.run_suite", side_effect=lambda s, r: setattr(r, "summary", "x")):
        client.post("/evals/security/run")
        time.sleep(0.1)
    resp = client.get("/evals/jobs")
    assert resp.status_code == 200
    assert "jobs" in resp.json()


def test_manager_duplicate_direct():
    reset_job_manager()
    mgr = get_job_manager()
    started = {"go": False}

    def block(record: JobRecord) -> None:
        while not started["go"]:
            time.sleep(0.01)

    mgr.submit(EvalSuite.promptfoo, block)
    try:
        mgr.submit(EvalSuite.promptfoo, block)
        assert False, "expected DuplicateSuiteError"
    except DuplicateSuiteError:
        pass
    finally:
        started["go"] = True
        time.sleep(0.1)
        reset_job_manager()

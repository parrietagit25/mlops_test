"""Administrador de jobs in-memory (Fase 1 Local).

Limitaciones documentadas:
- No es una cola distribuida (sin Redis/Celery/RabbitMQ).
- El estado se pierde al reiniciar el proceso/contenedor API.
- Una suite no puede tener más de un job queued/running a la vez.
"""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from schemas.evals import EvalSuite, JobStatus


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class JobRecord:
    job_id: str
    suite: EvalSuite
    status: JobStatus
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: float | None = None
    summary: str | None = None
    report_ref: str | None = None
    error: str | None = None
    _future: Future | None = field(default=None, repr=False)


class DuplicateSuiteError(RuntimeError):
    pass


class JobManager:
    def __init__(self, max_workers: int = 2) -> None:
        self._lock = threading.RLock()
        self._jobs: dict[str, JobRecord] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="eval-job")

    def list_jobs(self) -> list[JobRecord]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def has_active_suite(self, suite: EvalSuite) -> bool:
        with self._lock:
            for job in self._jobs.values():
                if job.suite == suite and job.status in ("queued", "running"):
                    return True
            return False

    def submit(
        self,
        suite: EvalSuite,
        runner: Callable[[JobRecord], None],
    ) -> JobRecord:
        with self._lock:
            if self.has_active_suite(suite):
                raise DuplicateSuiteError(
                    f"Ya hay un job queued/running para la suite '{suite.value}'."
                )
            job_id = uuid.uuid4().hex
            record = JobRecord(
                job_id=job_id,
                suite=suite,
                status="queued",
                created_at=_utc_now(),
            )
            self._jobs[job_id] = record

            def _wrapped() -> None:
                with self._lock:
                    record.status = "running"
                    record.started_at = _utc_now()
                try:
                    runner(record)
                    with self._lock:
                        if record.status == "running":
                            record.status = "completed"
                except Exception as exc:  # noqa: BLE001 — capturamos para marcar failed
                    with self._lock:
                        record.status = "failed"
                        record.error = str(exc)
                finally:
                    with self._lock:
                        record.finished_at = _utc_now()
                        if record.started_at:
                            try:
                                start = datetime.fromisoformat(record.started_at)
                                end = datetime.fromisoformat(record.finished_at)
                                record.duration_ms = (end - start).total_seconds() * 1000.0
                            except Exception:
                                record.duration_ms = None

            record._future = self._executor.submit(_wrapped)
            return record


_manager: JobManager | None = None
_manager_lock = threading.Lock()


def get_job_manager() -> JobManager:
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = JobManager()
        return _manager


def reset_job_manager() -> None:
    """Solo tests."""
    global _manager
    with _manager_lock:
        if _manager is not None:
            _manager._executor.shutdown(wait=False, cancel_futures=True)
        _manager = None

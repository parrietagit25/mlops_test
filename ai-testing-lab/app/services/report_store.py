"""Lectura segura de reports/ con path jail y whitelist de extensiones."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from core.config import get_settings
from schemas.reports import (
    ReportFileContentResponse,
    ReportFileInfo,
    ReportLatestResponse,
    ReportListResponse,
    ReportSummary,
)
from security.paths import PathJailError, resolve_under
from services.secrets_redact import redact

ALLOWED_REPORT_EXTENSIONS = {".json", ".html", ".md", ".txt", ".csv", ".log"}
_REPORT_ID_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{6})$")

_MEDIA = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".log": "text/plain",
    ".csv": "text/csv",
    ".json": "application/json",
    ".html": "text/html",
}


class ReportNotFoundError(LookupError):
    pass


class ReportAccessError(ValueError):
    pass


def _reports_root() -> Path:
    root = get_settings().reports_dir
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def parse_report_id(report_id: str) -> tuple[str, str]:
    if not report_id or "/" in report_id or "\\" in report_id or ".." in report_id:
        raise ReportAccessError("report_id inválido.")
    match = _REPORT_ID_RE.fullmatch(report_id)
    if not match:
        raise ReportAccessError(
            "report_id debe tener formato YYYY-MM-DD_HHMMSS (sin rutas)."
        )
    return match.group(1), match.group(2)


def report_id_from_parts(date: str, time: str) -> str:
    return f"{date}_{time}"


def _run_dir(date: str, time: str) -> Path:
    root = _reports_root()
    return resolve_under(root, date, time)


def _collect_files(run_dir: Path) -> list[ReportFileInfo]:
    files: list[ReportFileInfo] = []
    if not run_dir.is_dir():
        return files
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_REPORT_EXTENSIONS:
            continue
        if not path.resolve().is_relative_to(_reports_root()):
            continue
        files.append(
            ReportFileInfo(
                name=str(path.relative_to(run_dir)).replace("\\", "/"),
                size_bytes=path.stat().st_size,
                content_type_hint=_MEDIA.get(path.suffix.lower(), "application/octet-stream"),
            )
        )
    return files


def _summary_excerpt(run_dir: Path) -> tuple[bool, str | None]:
    summary = run_dir / "summary.md"
    if not summary.is_file():
        return False, None
    try:
        text = redact(summary.read_text(encoding="utf-8", errors="replace"), 800)
        return True, text
    except Exception:
        return True, None


def _suites_present(files: list[ReportFileInfo]) -> list[str]:
    suites = []
    for name in ("promptfoo", "deepeval", "ragas", "security"):
        if any(f.name.startswith(f"{name}/") or f"/{name}/" in f"/{f.name}" for f in files):
            suites.append(name)
    return suites


def build_report_summary(date: str, time: str) -> ReportSummary:
    run_dir = _run_dir(date, time)
    if not run_dir.is_dir():
        raise ReportNotFoundError(f"Reporte no encontrado: {report_id_from_parts(date, time)}")
    files = _collect_files(run_dir)
    has_summary, excerpt = _summary_excerpt(run_dir)
    try:
        mtime = datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc).isoformat()
    except Exception:
        mtime = f"{date}T{time[0:2]}:{time[2:4]}:{time[4:6]}+00:00"
    return ReportSummary(
        report_id=report_id_from_parts(date, time),
        date=date,
        time=time,
        created_at=mtime,
        suites_present=_suites_present(files),
        has_summary=has_summary,
        summary_excerpt=excerpt,
        files=files,
        total_size_bytes=sum(f.size_bytes for f in files),
        status="available" if files else "partial",
    )


def list_reports(limit: int | None = None) -> ReportListResponse:
    settings = get_settings()
    limit = limit or settings.reports_max_list
    root = _reports_root()
    found: list[tuple[str, str]] = []
    if root.is_dir():
        for date_dir in sorted(root.iterdir(), reverse=True):
            if not date_dir.is_dir() or date_dir.name.startswith("."):
                continue
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_dir.name):
                continue
            for time_dir in sorted(date_dir.iterdir(), reverse=True):
                if not time_dir.is_dir():
                    continue
                if not re.fullmatch(r"\d{6}", time_dir.name):
                    continue
                found.append((date_dir.name, time_dir.name))
    reports = [build_report_summary(d, t) for d, t in found[:limit]]
    return ReportListResponse(reports=reports, count=len(reports))


def latest_report() -> ReportLatestResponse:
    listed = list_reports(limit=1)
    return ReportLatestResponse(
        criterion="Max lexicográfico de reports/YYYY-MM-DD/HHMMSS (fecha luego hora).",
        report=listed.reports[0] if listed.reports else None,
    )


def latest_report_id() -> str | None:
    latest = latest_report().report
    return latest.report_id if latest else None


def get_report(report_id: str) -> ReportSummary:
    date, time = parse_report_id(report_id)
    return build_report_summary(date, time)


def read_report_file(report_id: str, filename: str) -> ReportFileContentResponse:
    date, time = parse_report_id(report_id)
    run_dir = _run_dir(date, time)
    if not run_dir.is_dir():
        raise ReportNotFoundError(f"Reporte no encontrado: {report_id}")

    # filename puede ser relativo tipo promptfoo/output.log — validar cada parte
    parts = filename.replace("\\", "/").split("/")
    if any(p in {"", ".", ".."} for p in parts):
        raise ReportAccessError("Nombre de archivo inválido.")
    try:
        path = resolve_under(run_dir, *parts)
    except PathJailError as exc:
        raise ReportAccessError(str(exc)) from exc

    if not path.is_file():
        raise ReportNotFoundError(f"Archivo no encontrado: {filename}")

    ext = path.suffix.lower()
    if ext not in ALLOWED_REPORT_EXTENSIONS:
        raise ReportAccessError(f"Extensión no permitida: {ext}")

    settings = get_settings()
    raw = path.read_bytes()
    truncated = len(raw) > settings.reports_max_file_bytes
    if truncated:
        raw = raw[: settings.reports_max_file_bytes]
    text = redact(raw.decode("utf-8", errors="replace"))
    return ReportFileContentResponse(
        report_id=report_id,
        filename="/".join(parts),
        media_type=_MEDIA.get(ext, "text/plain"),
        size_bytes=path.stat().st_size,
        truncated=truncated,
        content=text,
    )

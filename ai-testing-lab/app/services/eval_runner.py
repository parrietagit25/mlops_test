"""Runner de evaluaciones: whitelist estricta → scripts fijos (shell=False).

Reutiliza scripts/run_*.sh. El cliente nunca aporta comando, ruta ni args.

Nota Windows/Docker: los scripts en el volumen pueden tener CRLF. Se materializa
una copia LF bajo /tmp/ailab_run/<job_id>/ con symlinks a evals/ y reports/
reales (un directorio por job para evitar condiciones de carrera).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from core.config import get_settings
from schemas.evals import EvalSuite
from services.job_manager import JobRecord
from services.secrets_redact import redact

# Mapeo interno fijo: suite → script relativo a LAB_ROOT/scripts/
_SUITE_SCRIPTS: dict[EvalSuite, str] = {
    EvalSuite.promptfoo: "run_prompt_tests.sh",
    EvalSuite.deepeval: "run_deepeval.sh",
    EvalSuite.ragas: "run_ragas.sh",
    EvalSuite.security: "run_security_checks.sh",
    EvalSuite.all: "run_all_evals.sh",
}

_RUN_BASE = Path("/tmp/ailab_run")


class EvalRunnerError(RuntimeError):
    pass


def suite_script_path(suite: EvalSuite) -> Path:
    settings = get_settings()
    script_name = _SUITE_SCRIPTS[suite]
    return (settings.lab_root_path / "scripts" / script_name).resolve()


def _read_lf(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def _assert_safe_job_id(job_id: str) -> str:
    jid = (job_id or "").strip()
    if not jid or "/" in jid or "\\" in jid or ".." in jid:
        raise EvalRunnerError("job_id inválido para el directorio temporal.")
    return jid


def job_run_root(job_id: str) -> Path:
    """Raíz temporal aislada por job bajo /tmp/ailab_run/<job_id>."""
    return _RUN_BASE / _assert_safe_job_id(job_id)


def _prepare_run_tree(lab: Path, job_id: str) -> Path:
    """Crea /tmp/ailab_run/<job_id> con scripts en LF y enlaces a evals/reports."""
    run_root = job_run_root(job_id)
    if run_root.exists():
        shutil.rmtree(run_root, ignore_errors=True)
    scripts_dst = run_root / "scripts"
    scripts_dst.mkdir(parents=True)

    src_scripts = lab / "scripts"
    for path in src_scripts.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(src_scripts)
        dest = scripts_dst / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix in {".sh", ".bash", ""} or "find_python" in path.name:
            dest.write_text(_read_lf(path), encoding="utf-8")
            dest.chmod(0o755)
        else:
            shutil.copy2(path, dest)

    for name in ("evals", "reports", "app"):
        src = lab / name
        dst = run_root / name
        if src.exists():
            if dst.exists() or dst.is_symlink():
                dst.unlink(missing_ok=True)
            os.symlink(src, dst)

    # No copiar .env del host al jail: suele traer OLLAMA_BASE_URL=localhost
    # y pisa las URLs de Compose (http://ollama:11434) inyectadas por el runner.
    # Los scripts en host siguen leyendo el .env real del lab fuera de Docker.

    return run_root


def _cleanup_run_tree(run_root: Path) -> None:
    try:
        if run_root.exists() and run_root.resolve().is_relative_to(_RUN_BASE.resolve()):
            shutil.rmtree(run_root, ignore_errors=True)
    except Exception:
        pass


def run_suite(suite: EvalSuite, record: JobRecord) -> None:
    settings = get_settings()
    script = suite_script_path(suite)
    lab = settings.lab_root_path
    job_id = record.job_id

    if not script.is_file():
        raise EvalRunnerError(f"Script de suite no encontrado en el laboratorio: {script.name}")

    scripts_dir = (lab / "scripts").resolve()
    try:
        script.relative_to(scripts_dir)
    except ValueError as exc:
        raise EvalRunnerError("Script fuera del directorio permitido.") from exc

    run_root = _prepare_run_tree(lab, job_id)
    run_script = (run_root / "scripts" / script.name).resolve()
    try:
        run_script.relative_to((run_root / "scripts").resolve())
    except ValueError as exc:
        raise EvalRunnerError("Script normalizado fuera del jail temporal.") from exc

    env = os.environ.copy()
    env["OLLAMA_BASE_URL"] = settings.ollama_base_url
    env["OPENAI_BASE_URL"] = settings.openai_compat_base_url
    env["OPENAI_API_KEY"] = env.get("OPENAI_API_KEY") or "ollama-local-no-key-needed"
    env["API_PORT"] = str(settings.api_port)
    env["API_BASE_URL"] = f"http://127.0.0.1:{settings.api_port}"
    env["OLLAMA_CHAT_MODEL"] = settings.ollama_chat_model
    env["OLLAMA_EMBED_MODEL"] = settings.ollama_embed_model
    env["AILAB_RUN_ROOT"] = str(run_root)
    env["AILAB_JOB_ID"] = job_id

    cmd = ["/bin/bash", str(run_script)]
    started = time.perf_counter()
    try:
        try:
            completed = subprocess.run(
                cmd,
                cwd=str(run_root),
                env=env,
                shell=False,
                capture_output=True,
                text=True,
                timeout=settings.eval_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or "") + "\n" + (exc.stderr or "")
            record.summary = redact(out, settings.eval_output_max_chars)
            record.error = f"Timeout tras {settings.eval_timeout_seconds}s"
            raise EvalRunnerError(record.error) from exc
        except FileNotFoundError as exc:
            raise EvalRunnerError(
                "No se encontró /bin/bash en el contenedor API. "
                "Las evaluaciones requieren la imagen con bash."
            ) from exc

        combined = (completed.stdout or "") + "\n" + (completed.stderr or "")
        record.summary = redact(combined.strip(), settings.eval_output_max_chars)
        record.duration_ms = (time.perf_counter() - started) * 1000.0

        try:
            from services.report_store import latest_report_id

            record.report_ref = latest_report_id()
        except Exception:
            record.report_ref = None

        if completed.returncode != 0:
            record.error = redact(
                f"Suite '{suite.value}' terminó con código {completed.returncode}."
            )
            raise EvalRunnerError(record.error)
    finally:
        _cleanup_run_tree(run_root)

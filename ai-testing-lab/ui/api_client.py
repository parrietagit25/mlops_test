"""Cliente HTTP centralizado hacia el FastAPI Gateway.

Streamlit no habla con Ollama, Phoenix, scripts ni filesystem:
solo con esta capa.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from config import UIConfig, load_config


@dataclass
class ApiResult:
    ok: bool
    status_code: int | None
    data: Any = None
    error_kind: str | None = None
    error_message: str | None = None
    error_code: str | None = None


def _sanitize(message: str, max_len: int = 240) -> str:
    text = " ".join(str(message).split())
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def _parse_gateway_error(resp: httpx.Response) -> tuple[str | None, str]:
    """Extrae code/message del ErrorResponse del Gateway si está disponible."""
    try:
        body = resp.json()
    except ValueError:
        return None, _sanitize(f"Gateway respondió {resp.status_code}.")
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        err = body["error"]
        code = err.get("code")
        msg = err.get("message") or f"Gateway respondió {resp.status_code}."
        return (str(code) if code else None), _sanitize(str(msg))
    return None, _sanitize(f"Gateway respondió {resp.status_code}.")


class GatewayClient:
    """Cliente síncrono mínimo. Sin reintentos agresivos."""

    def __init__(self, cfg: UIConfig | None = None) -> None:
        self.cfg = cfg or load_config()
        self._timeout = httpx.Timeout(
            connect=self.cfg.connect_timeout_s,
            read=self.cfg.read_timeout_s,
            write=self.cfg.read_timeout_s,
            pool=self.cfg.connect_timeout_s,
        )

    @property
    def base_url(self) -> str:
        return self.cfg.api_base_url

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        files: Any = None,
        retry_once: bool = False,
        timeout: httpx.Timeout | None = None,
    ) -> ApiResult:
        url = f"{self.cfg.api_base_url}{path}"
        attempts = 2 if retry_once else 1
        last: ApiResult | None = None
        req_timeout = timeout or self._timeout

        for attempt in range(attempts):
            try:
                with httpx.Client(timeout=req_timeout) as client:
                    kwargs: dict[str, Any] = {"params": params}
                    if files is not None:
                        kwargs["files"] = files
                    elif json_body is not None:
                        kwargs["json"] = json_body
                    resp = client.request(method, url, **kwargs)
            except httpx.ConnectError as exc:
                last = ApiResult(
                    ok=False,
                    status_code=None,
                    error_kind="connection",
                    error_message=_sanitize(
                        f"Gateway no disponible (conexión rechazada): {exc}"
                    ),
                )
                continue
            except httpx.TimeoutException:
                last = ApiResult(
                    ok=False,
                    status_code=None,
                    error_kind="timeout",
                    error_message="Timeout al contactar el Gateway.",
                )
                continue
            except httpx.HTTPError as exc:
                last = ApiResult(
                    ok=False,
                    status_code=None,
                    error_kind="http_error",
                    error_message=_sanitize(f"Error HTTP: {exc}"),
                )
                continue

            if resp.status_code == 503:
                code, msg = _parse_gateway_error(resp)
                return ApiResult(
                    ok=False,
                    status_code=503,
                    error_kind="unavailable",
                    error_message=msg or "Servicio requerido no disponible (503).",
                    error_code=code,
                )

            if resp.status_code >= 500:
                code, msg = _parse_gateway_error(resp)
                last = ApiResult(
                    ok=False,
                    status_code=resp.status_code,
                    error_kind="server_error",
                    error_message=msg,
                    error_code=code,
                )
                if retry_once and attempt == 0:
                    continue
                return last

            if resp.status_code >= 400:
                code, msg = _parse_gateway_error(resp)
                return ApiResult(
                    ok=False,
                    status_code=resp.status_code,
                    error_kind="client_error",
                    error_message=msg,
                    error_code=code,
                )

            try:
                data = resp.json()
            except ValueError:
                return ApiResult(
                    ok=False,
                    status_code=resp.status_code,
                    error_kind="invalid_json",
                    error_message="Respuesta del Gateway no es JSON válido.",
                )

            return ApiResult(ok=True, status_code=resp.status_code, data=data)

        return last or ApiResult(
            ok=False,
            status_code=None,
            error_kind="unknown",
            error_message="Error desconocido al contactar el Gateway.",
        )

    def get(
        self,
        path: str,
        *,
        params: dict | None = None,
        retry_once: bool = False,
        timeout: httpx.Timeout | None = None,
    ) -> ApiResult:
        return self._request(
            "GET", path, params=params, retry_once=retry_once, timeout=timeout
        )

    def post(
        self,
        path: str,
        json_body: dict | None = None,
        *,
        files: Any = None,
        timeout: httpx.Timeout | None = None,
    ) -> ApiResult:
        return self._request(
            "POST",
            path,
            json_body=json_body,
            files=files,
            retry_once=False,
            timeout=timeout,
        )

    def health(self) -> ApiResult:
        return self.get("/health", retry_once=True)

    def system_status(self) -> ApiResult:
        return self.get("/system/status", retry_once=True)

    def models(self) -> ApiResult:
        return self.get("/models", retry_once=True)

    def get_models(self) -> ApiResult:
        """Alias explícito para UI-1B (mismo contrato GET /models)."""
        return self.models()

    def rag_status(self) -> ApiResult:
        return self.get("/rag/status", retry_once=True)

    def observability(self) -> ApiResult:
        return self.get("/observability", retry_once=True)

    def send_chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> ApiResult:
        """POST /chat — sin reintento automático (inferencia no idempotente)."""
        body: dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if model:
            body["model"] = model
        chat_timeout = httpx.Timeout(
            connect=self.cfg.connect_timeout_s,
            read=self.cfg.chat_read_timeout_s,
            write=self.cfg.chat_read_timeout_s,
            pool=self.cfg.connect_timeout_s,
        )
        return self.post("/chat", json_body=body, timeout=chat_timeout)

    def get_skills(self) -> ApiResult:
        """GET /skills — lista [{name, description}, ...]."""
        return self.get("/skills", retry_once=True)

    def run_skill(self, skill_name: str, payload: dict[str, Any]) -> ApiResult:
        """POST /agents/{skill_name}/run — sin reintento automático."""
        name = (skill_name or "").strip()
        if not name:
            return ApiResult(
                ok=False,
                status_code=None,
                error_kind="client_error",
                error_message="Nombre de skill vacío.",
            )
        # Solo path relativo fijo + nombre ya autorizado por la UI.
        body = {"payload": payload}
        skill_timeout = httpx.Timeout(
            connect=self.cfg.connect_timeout_s,
            read=self.cfg.skill_read_timeout_s,
            write=self.cfg.skill_read_timeout_s,
            pool=self.cfg.connect_timeout_s,
        )
        return self.post(
            f"/agents/{name}/run",
            json_body=body,
            timeout=skill_timeout,
        )

    def get_rag_status(self) -> ApiResult:
        """Alias explícito de GET /rag/status."""
        return self.rag_status()

    def ingest_rag_files(
        self,
        files: list[tuple[str, bytes, str]] | None = None,
    ) -> ApiResult:
        """POST /rag/ingest — multipart `files` o sin archivos (sample_docs).

        files: lista de (filename, content_bytes, content_type).
        """
        rag_timeout = httpx.Timeout(
            connect=self.cfg.connect_timeout_s,
            read=self.cfg.rag_read_timeout_s,
            write=self.cfg.rag_read_timeout_s,
            pool=self.cfg.connect_timeout_s,
        )
        if not files:
            # Legacy: reindex sample_docs sin multipart.
            return self.post("/rag/ingest", json_body=None, timeout=rag_timeout)

        multipart = [
            ("files", (name, content, ctype or "text/plain"))
            for name, content, ctype in files
        ]
        return self.post("/rag/ingest", files=multipart, timeout=rag_timeout)

    def query_rag(self, *, q: str, top_k: int = 3) -> ApiResult:
        """GET /rag/query — retriever (chunks), no genera respuesta LLM."""
        rag_timeout = httpx.Timeout(
            connect=self.cfg.connect_timeout_s,
            read=self.cfg.rag_read_timeout_s,
            write=self.cfg.rag_read_timeout_s,
            pool=self.cfg.connect_timeout_s,
        )
        return self.get(
            "/rag/query",
            params={"q": q, "top_k": top_k},
            retry_once=False,
            timeout=rag_timeout,
        )

    def run_evaluation(self, suite: str) -> ApiResult:
        """POST /evals/{suite}/run — sin reintento automático."""
        try:
            from evals_payload import assert_suite_allowed

            name = assert_suite_allowed(suite)
        except ValueError as exc:
            return ApiResult(
                ok=False,
                status_code=None,
                error_kind="client_error",
                error_message=str(exc),
            )
        timeout = httpx.Timeout(
            connect=self.cfg.connect_timeout_s,
            read=self.cfg.eval_create_timeout_s,
            write=self.cfg.eval_create_timeout_s,
            pool=self.cfg.connect_timeout_s,
        )
        return self.post(f"/evals/{name}/run", timeout=timeout)

    def get_evaluation_jobs(self) -> ApiResult:
        """GET /evals/jobs."""
        timeout = httpx.Timeout(
            connect=self.cfg.connect_timeout_s,
            read=self.cfg.eval_read_timeout_s,
            write=self.cfg.eval_read_timeout_s,
            pool=self.cfg.connect_timeout_s,
        )
        return self.get("/evals/jobs", retry_once=True, timeout=timeout)

    def get_evaluation_job(self, job_id: str) -> ApiResult:
        """GET /evals/jobs/{job_id} — job_id validado como identificador."""
        try:
            from evals_payload import validate_job_id

            jid = validate_job_id(job_id)
        except ValueError as exc:
            return ApiResult(
                ok=False,
                status_code=None,
                error_kind="client_error",
                error_message=str(exc),
            )
        timeout = httpx.Timeout(
            connect=self.cfg.connect_timeout_s,
            read=self.cfg.eval_read_timeout_s,
            write=self.cfg.eval_read_timeout_s,
            pool=self.cfg.connect_timeout_s,
        )
        return self.get(f"/evals/jobs/{jid}", retry_once=False, timeout=timeout)

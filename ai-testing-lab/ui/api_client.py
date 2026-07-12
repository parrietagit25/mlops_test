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


def _sanitize(message: str, max_len: int = 240) -> str:
    text = " ".join(str(message).split())
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


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
        retry_once: bool = False,
    ) -> ApiResult:
        url = f"{self.cfg.api_base_url}{path}"
        attempts = 2 if retry_once else 1
        last: ApiResult | None = None

        for attempt in range(attempts):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.request(method, url, json=json_body)
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
                return ApiResult(
                    ok=False,
                    status_code=503,
                    error_kind="unavailable",
                    error_message="Servicio requerido no disponible (503).",
                )

            if resp.status_code >= 500:
                last = ApiResult(
                    ok=False,
                    status_code=resp.status_code,
                    error_kind="server_error",
                    error_message=_sanitize(
                        f"Gateway respondió {resp.status_code}."
                    ),
                )
                # Un reintento breve solo en consultas de estado (retry_once).
                if retry_once and attempt == 0:
                    continue
                return last

            if resp.status_code >= 400:
                return ApiResult(
                    ok=False,
                    status_code=resp.status_code,
                    error_kind="client_error",
                    error_message=_sanitize(f"Solicitud rechazada ({resp.status_code})."),
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

    def get(self, path: str, *, retry_once: bool = False) -> ApiResult:
        return self._request("GET", path, retry_once=retry_once)

    def post(self, path: str, json_body: dict | None = None) -> ApiResult:
        return self._request("POST", path, json_body=json_body, retry_once=False)

    def health(self) -> ApiResult:
        return self.get("/health", retry_once=True)

    def system_status(self) -> ApiResult:
        return self.get("/system/status", retry_once=True)

    def models(self) -> ApiResult:
        return self.get("/models", retry_once=True)

    def rag_status(self) -> ApiResult:
        return self.get("/rag/status", retry_once=True)

    def observability(self) -> ApiResult:
        return self.get("/observability", retry_once=True)

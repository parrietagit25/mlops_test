"""Vista Chat (UI-1B) — cliente HTTP de POST /chat vía Gateway."""

from __future__ import annotations

import time
from typing import Any

import streamlit as st

from api_client import ApiResult, GatewayClient
from chat_payload import (
    MAX_TOKENS_MAX,
    MAX_TOKENS_MIN,
    TEMP_MAX,
    TEMP_MIN,
    build_chat_payload,
    chat_model_names,
    format_assistant_caption,
    humanize_chat_error,
    select_default_chat_model,
)
from components.messages import show_error, show_info, show_warning
from config import UIConfig
from state import (
    CHAT_MODELS_TTL_S,
    append_chat_message,
    clear_chat,
    invalidate_chat_models_cache,
)


def _fetch_models(client: GatewayClient, *, force: bool = False) -> ApiResult:
    now = time.time()
    cached = st.session_state.chat_models_payload
    fetched_at = float(st.session_state.chat_models_fetched_at or 0.0)
    if (
        not force
        and isinstance(cached, dict)
        and (now - fetched_at) < CHAT_MODELS_TTL_S
    ):
        return ApiResult(ok=True, status_code=200, data=cached)

    result = client.get_models()
    if result.ok and isinstance(result.data, dict):
        st.session_state.chat_models_payload = result.data
        st.session_state.chat_models_fetched_at = now
    return result


def _apply_model_selection(payload: dict[str, Any] | None) -> tuple[list[str], bool]:
    names = chat_model_names(payload)
    default, used_fallback = select_default_chat_model(payload)
    warning = None
    if names:
        if st.session_state.chat_model not in names:
            st.session_state.chat_model = default
            if used_fallback:
                warning = (
                    "Ningún modelo marcado como default; "
                    f"se seleccionó el primero disponible (`{default}`)."
                )
        elif used_fallback and st.session_state.chat_model == default:
            warning = (
                "Ningún modelo marcado como default; "
                f"usando el primero disponible (`{default}`)."
            )
    else:
        st.session_state.chat_model = None
    st.session_state.chat_models_warning = warning
    return names, used_fallback


def _render_settings(model_names: list[str], models_result: ApiResult) -> None:
    with st.expander("Parámetros de generación", expanded=True):
        if not models_result.ok:
            show_warning("Modelos no disponibles. Verifica el Gateway y pulsa Actualizar modelos.")
        elif not model_names:
            show_warning("Modelos no disponibles (la lista de chat está vacía).")

        if st.session_state.chat_models_warning:
            show_info(st.session_state.chat_models_warning)

        if model_names:
            st.selectbox(
                "Modelo",
                options=model_names,
                key="chat_model",
                help="Solo modelos de chat desde GET /models. No se listan embeddings.",
            )
        else:
            st.selectbox(
                "Modelo",
                options=["Modelos no disponibles"],
                disabled=True,
                help="Actualiza la lista cuando el Gateway responda.",
            )

        st.text_area(
            "System prompt",
            key="chat_system_prompt",
            height=100,
            max_chars=16_000,
            help=(
                "Los cambios en el system prompt se aplican a la siguiente respuesta "
                "y no eliminan el historial existente."
            ),
        )
        st.caption(
            "Los cambios en el system prompt se aplican a la siguiente respuesta "
            "y no eliminan el historial existente."
        )

        c1, c2 = st.columns(2)
        with c1:
            st.slider(
                "Temperature",
                min_value=float(TEMP_MIN),
                max_value=float(TEMP_MAX),
                step=0.05,
                key="chat_temperature",
                help="Valores bajos: más consistentes. Valores altos: más variadas.",
            )
            st.caption("Baja = más consistente · Alta = más variada")
        with c2:
            st.number_input(
                "Max tokens",
                min_value=MAX_TOKENS_MIN,
                max_value=MAX_TOKENS_MAX,
                step=32,
                key="chat_max_tokens",
                help="Limita la longitud máxima esperada de la respuesta.",
            )
            st.caption("Limita la longitud máxima de la respuesta")

        b1, b2 = st.columns(2)
        with b1:
            st.button(
                "Limpiar conversación",
                use_container_width=True,
                disabled=len(st.session_state.chat_messages) == 0,
                on_click=clear_chat,
            )
        with b2:
            if st.button("Actualizar modelos", use_container_width=True):
                invalidate_chat_models_cache()
                st.rerun()


def _render_history() -> None:
    for msg in st.session_state.chat_messages:
        role = msg.get("role", "assistant")
        if role not in {"user", "assistant"}:
            continue
        with st.chat_message(role):
            st.markdown(str(msg.get("content") or ""), unsafe_allow_html=False)
            if role == "assistant":
                st.caption(format_assistant_caption(msg.get("metadata")))


def _parse_assistant_reply(result: ApiResult) -> tuple[str | None, str | None]:
    if not result.ok:
        return None, humanize_chat_error(
            error_kind=result.error_kind,
            error_code=result.error_code,
            error_message=result.error_message,
            status_code=result.status_code,
        )
    if not isinstance(result.data, dict):
        return None, "La respuesta del Gateway no tiene el formato esperado."
    reply = result.data.get("reply")
    if reply is None or str(reply).strip() == "":
        return None, "La respuesta del Gateway no tiene el formato esperado."
    return str(reply), None


def _send_user_message(client: GatewayClient, user_text: str) -> None:
    if st.session_state.chat_request_in_progress:
        show_info("Ya hay una solicitud de chat en curso.")
        return

    text = (user_text or "").strip()
    if not text:
        st.session_state.chat_last_error = "El mensaje no puede estar vacío."
        return

    if not st.session_state.chat_model:
        st.session_state.chat_last_error = (
            "Modelos no disponibles. Actualiza la lista antes de enviar."
        )
        return

    # Validar payload ANTES de mutar el historial (sin truncado silencioso).
    try:
        payload = build_chat_payload(
            history=list(st.session_state.chat_messages),
            user_text=text,
            system_prompt=st.session_state.chat_system_prompt,
            model=st.session_state.chat_model,
            temperature=st.session_state.chat_temperature,
            max_tokens=st.session_state.chat_max_tokens,
        )
    except ValueError as exc:
        st.session_state.chat_last_error = str(exc)
        return

    st.session_state.chat_last_error = None
    st.session_state.chat_request_in_progress = True
    append_chat_message("user", text)

    try:
        with st.spinner("Generando respuesta…"):
            result = client.send_chat(
                messages=payload["messages"],
                model=payload.get("model"),
                temperature=payload["temperature"],
                max_tokens=payload["max_tokens"],
            )
        reply, err = _parse_assistant_reply(result)
        if err:
            st.session_state.chat_last_error = err
        else:
            data = result.data if isinstance(result.data, dict) else {}
            append_chat_message(
                "assistant",
                reply or "",
                metadata={
                    "model": data.get("model"),
                    "duration_ms": data.get("duration_ms"),
                    "trace_id": data.get("trace_id"),
                },
            )
    except Exception:
        st.session_state.chat_last_error = (
            "No se pudo completar la solicitud de chat."
        )
    finally:
        st.session_state.chat_request_in_progress = False


def render(client: GatewayClient, cfg: UIConfig) -> None:
    st.markdown("## Chat con modelos locales")
    st.caption(
        "Conversa con los modelos disponibles a través del FastAPI Gateway. "
        "La interfaz no se conecta directamente a Ollama."
    )
    st.caption(
        f"Timeout de inferencia: {cfg.chat_read_timeout_s:.0f}s · "
        "El historial vive solo en esta sesión del navegador "
        "(se pierde al cerrar o reiniciar el contenedor)."
    )

    models_result = _fetch_models(client, force=False)
    model_names, _ = _apply_model_selection(
        models_result.data if models_result.ok and isinstance(models_result.data, dict) else None
    )
    _render_settings(model_names, models_result)

    if st.session_state.chat_last_error:
        show_error(st.session_state.chat_last_error)

    _render_history()

    can_send = (
        bool(model_names)
        and bool(st.session_state.chat_model)
        and not st.session_state.chat_request_in_progress
        and models_result.ok
    )
    prompt = st.chat_input(
        "Escribe un mensaje…",
        disabled=not can_send,
    )
    if prompt:
        _send_user_message(client, prompt)
        st.rerun()

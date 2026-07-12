"""Mensajes de estado / error sanitizados."""

from __future__ import annotations

import streamlit as st


def show_error(message: str) -> None:
    st.error(message)


def show_warning(message: str) -> None:
    st.warning(message)


def show_info(message: str) -> None:
    st.info(message)


def show_placeholder(module: str, stage: str) -> None:
    st.markdown(f"## {module}")
    st.info(f"Módulo preparado. Se implementará en **{stage}**.")
    st.caption(
        "Esta página no ejecuta acciones todavía. "
        "No hay botones operativos en esta etapa."
    )

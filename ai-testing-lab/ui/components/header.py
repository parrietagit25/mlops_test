"""Encabezado del laboratorio (contraste adaptable al tema)."""

from __future__ import annotations

import streamlit as st


def render_header() -> None:
    st.markdown(
        """
        <div class="ailab-header">
          <div class="ailab-title">ai-testing-lab</div>
          <div class="ailab-subtitle">
            Laboratorio local de AI Engineering / LLMOps — interfaz cliente del Gateway
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st


@contextmanager
def render_page(title: str, subtitle: str) -> Iterator[None]:
    st.markdown(
        """
        <style>
            div[data-testid="stDialog"] div[role="dialog"] {
                width: 96vw !important;
                max-width: 1280px !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title(title)
    st.caption(subtitle)
    with st.container(border=True):
        yield

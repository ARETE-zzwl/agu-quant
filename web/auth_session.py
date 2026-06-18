"""Streamlit session helpers for account login state."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local", override=True)

AUTH_SESSION_KEY = "ta_auth_user"


def current_user() -> dict | None:
    from tradingagents.auth.access import development_auth_enabled

    if development_auth_enabled():
        return {
            "user_name": "developer",
            "role": "admin",
            "plan": "pro",
            "development": True,
        }
    user = st.session_state.get(AUTH_SESSION_KEY)
    return user if isinstance(user, dict) else None


def sign_in(auth_result: dict) -> None:
    st.session_state[AUTH_SESSION_KEY] = {
        "user_name": auth_result["user_name"],
        "role": auth_result["role"],
        "plan": auth_result.get("plan", "pro"),
    }
    st.session_state["admin_authed"] = auth_result["role"] == "admin"


def sign_out() -> None:
    st.session_state.pop(AUTH_SESSION_KEY, None)
    st.session_state["admin_authed"] = False


def is_admin() -> bool:
    user = current_user()
    return bool(user and user.get("role") == "admin")

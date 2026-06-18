"""Account authentication helpers for the Streamlit app."""

from __future__ import annotations

import hashlib
import hmac
import os

from . import license as license_mod
from . import machine_id
from .user_db import bind_machine, normalize_user_name


_TRUE_VALUES = {"1", "true", "yes", "on"}


def development_auth_enabled() -> bool:
    """Return whether the explicit local-development auth bypass is enabled."""
    return os.getenv("TA_DEV_MODE", "").strip().lower() in _TRUE_VALUES

def _fail(message: str) -> dict:
    return {"success": False, "message": message}


def _configured_admin_username() -> str | None:
    raw = os.getenv("TA_ADMIN_USERNAME") or os.getenv("ADMIN_USERNAME")
    if raw:
        return normalize_user_name(raw)
    if os.getenv("TA_ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD"):
        return "admin"
    return None


def _configured_admin_password_matches(password: str) -> bool:
    configured_password = os.getenv("TA_ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD")
    if configured_password:
        return hmac.compare_digest(password, configured_password)
    return False


def is_admin_user(user_name: str) -> bool:
    try:
        normalized_user = normalize_user_name(user_name)
    except ValueError:
        return False
    configured_user = _configured_admin_username()
    return configured_user is not None and normalized_user == configured_user


def authenticate_admin(user_name: str, password: str) -> dict:
    try:
        normalized_user = normalize_user_name(user_name)
    except ValueError as exc:
        return _fail(str(exc))

    password_value = str(password or "")
    configured_user = _configured_admin_username()
    if (
        configured_user is not None
        and normalized_user == configured_user
        and _configured_admin_password_matches(password_value)
    ):
        return {"success": True, "role": "admin", "user_name": normalized_user}

    return _fail("管理员用户名或密码错误")


def authenticate_license_user(user_name: str, license_key: str) -> dict:
    try:
        normalized_user = normalize_user_name(user_name)
    except ValueError as exc:
        return _fail(str(exc))

    key = str(license_key or "").strip()
    if not key:
        return _fail("请输入激活码")
    if not license_mod._validate_key_integrity(key, normalized_user):
        return _fail("激活码与用户名不匹配")

    key_hash = hashlib.sha256(key.encode()).hexdigest()
    if not bind_machine(key_hash, machine_id.get_machine_fingerprint()):
        return _fail("设备绑定失败，请联系管理员重置设备。")

    result = license_mod.activate_license(key, normalized_user)
    if not result["success"]:
        return result
    return {
        "success": True,
        "role": "user",
        "user_name": normalized_user,
        "expire_month": result.get("expire_month"),
        "plan": result.get("plan", "pro"),
        "is_permanent": result.get("is_permanent", False),
    }


def authenticate_account(user_name: str, secret: str) -> dict:
    if is_admin_user(user_name):
        return authenticate_admin(user_name, secret)
    return authenticate_license_user(user_name, secret)

"""赞赏激活 — 邮箱注册 + 激活码解锁."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from tradingagents.auth import activate_license, get_license_status
from tradingagents.auth.access import authenticate_account
from tradingagents.auth.license import generate_license_key
from tradingagents.auth.machine_id import get_machine_fingerprint
from tradingagents.auth.user_db import add_license, bind_machine, normalize_user_name
from web.auth_session import current_user, is_admin, sign_in, sign_out
from web.components.common import inject_css

st.set_page_config(page_title="赞赏激活", page_icon="🔑", layout="wide", initial_sidebar_state="collapsed")
inject_css()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TRIAL_DAYS = 7


def _normalize_email(email: str) -> str:
    value = (email or "").strip().lower()
    if not _EMAIL_RE.fullmatch(value):
        raise ValueError("请输入有效的邮箱地址")
    return value


def _trial_expire_month() -> str:
    return (datetime.now() + timedelta(days=_TRIAL_DAYS)).strftime("%Y%m")


def _activate_trial(email: str) -> tuple[bool, str]:
    user_name = normalize_user_name(email)
    trial_expire = _trial_expire_month()
    trial_key = generate_license_key(user_name, trial_expire)
    key_hash = hashlib.sha256(trial_key.encode()).hexdigest()

    try:
        created = add_license(user_name, key_hash, trial_expire, 1)
    except ValueError as exc:
        return False, str(exc)
    if not created:
        return False, "该邮箱已注册过试用，请使用管理员提供的激活码续期。"
    if not bind_machine(key_hash, get_machine_fingerprint(), 1):
        return False, "设备绑定失败，请联系管理员重置设备。"

    result = activate_license(trial_key, user_name, trial_days=_TRIAL_DAYS)
    if not result["success"]:
        return False, result["message"]
    return True, f"{_TRIAL_DAYS}天试用已激活，到期日以本机授权状态为准。"


st.markdown(
    """
    <div class="ta-page-header">
        <div class="ta-eyebrow">ACCOUNT ACCESS</div>
        <h1 class="ta-page-title">赞赏激活</h1>
        <div class="ta-page-subtitle">
            管理试用、激活码与本机授权状态。注册邮箱会进入本地用户库，管理员可在后台统一查看和续期。
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

status = get_license_status()
auth_user = current_user()

st.markdown('<div class="ta-panel-title">统一登录入口</div>', unsafe_allow_html=True)
if auth_user:
    role_name = "管理员" if auth_user.get("role") == "admin" else "用户"
    st.success(f"已登录: {auth_user['user_name']} ({role_name})")
    c1, c2 = st.columns(2)
    if is_admin() and c1.button("进入管理员看板", use_container_width=True):
        st.switch_page("pages/admin.py")
    if c2.button("退出登录", use_container_width=True):
        sign_out()
        st.rerun()
    st.stop()

with st.form("account_login_form"):
    login_user = st.text_input("用户名/邮箱", placeholder="管理员用户名或用户邮箱")
    login_secret = st.text_input("密码/激活码", type="password", placeholder="管理员密码或用户激活码")
    login_submitted = st.form_submit_button("登录", type="primary", use_container_width=True)

if login_submitted:
    result = authenticate_account(login_user, login_secret)
    if result["success"]:
        sign_in(result)
        st.success("登录成功")
        if result["role"] == "admin":
            st.switch_page("pages/admin.py")
        st.rerun()
    else:
        st.error(result["message"])

if status["valid"]:
    st.info(f"本机授权状态: {status['display']}")

left, right = st.columns([1.05, 1], gap="large")

with left:
    st.markdown(
        """
        <div class="ta-panel">
            <div class="ta-panel-title">当前状态</div>
            <div class="ta-muted">免费版正在运行，深度分析、AI荐股、因子引擎、股票监控、模拟盘和基金中心需激活后使用。</div>
            <div class="ta-badge-row">
                <span class="ta-badge">本机授权</span>
                <span class="ta-badge">邮箱试用</span>
                <span class="ta-badge">设备绑定</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="ta-warning-strip">免费版 - 付费功能已锁定</div>', unsafe_allow_html=True)

    st.write("支持者权益、价格和官方购买渠道统一在支持计划页公布。")
    st.page_link(
        "pages/12_Support_Open_Source.py",
        label="查看支持开源计划",
        use_container_width=True,
    )

with right:
    st.markdown('<div class="ta-panel-title">邮箱注册试用</div>', unsafe_allow_html=True)
    email = st.text_input("邮箱地址", placeholder="your@email.com", key="reg_email")

    send_col, code_col = st.columns([1.35, 1])
    if send_col.button("获取验证码", use_container_width=True):
        try:
            normalized_email = _normalize_email(email)
        except ValueError as exc:
            st.error(str(exc))
        else:
            from tradingagents.auth.email_service import send_verification_code

            result = send_verification_code(normalized_email)
            if result["success"]:
                st.success(result["message"])
                st.session_state["reg_email_sent_to"] = normalized_email
            else:
                st.warning(result["message"])

    pending_email = st.session_state.get("reg_email_sent_to", "")
    vcode = code_col.text_input("验证码", max_chars=6, placeholder="6位数字", disabled=not pending_email)

    if pending_email:
        st.caption(f"验证码已发送至 {pending_email}")

    if st.button("验证并激活试用", type="primary", use_container_width=True, disabled=not pending_email):
        from tradingagents.auth.email_service import notify_admin_new_user, send_welcome, verify_code

        vresult = verify_code(pending_email, vcode)
        if vresult.get("verified"):
            ok, message = _activate_trial(pending_email)
            if ok:
                notify_admin_new_user(pending_email)
                send_welcome(pending_email, pending_email.split("@", 1)[0])
                sign_in({"role": "user", "user_name": pending_email})
                st.success(message)
                st.balloons()
                st.rerun()
            else:
                st.error(message)
        else:
            st.error(vresult.get("message", "验证失败"))

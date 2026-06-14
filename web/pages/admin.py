"""管理员看板 — 用户管理 · 激活码 · 邮件群发 · 数据统计."""

import hashlib
import os
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from web.components.common import inject_css
from tradingagents.auth.license import generate_license_key
from tradingagents.auth.user_db import (
    add_license, list_users, update_license_status, reset_devices,
)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

st.set_page_config(page_title="管理员看板", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")
inject_css()

if "admin_authed" not in st.session_state:
    st.session_state["admin_authed"] = False

if not st.session_state["admin_authed"]:
    st.markdown("### 🛡️ 管理员登录")
    pw = st.text_input("密码", type="password")
    if st.button("登录", type="primary"):
        if pw == ADMIN_PASSWORD:
            st.session_state["admin_authed"] = True
            st.rerun()
        else:
            st.error("密码错误")
    st.caption("在 .env 文件中修改 ADMIN_PASSWORD")
    st.stop()

st.markdown(
    '<div style="font-size:1.4rem;font-weight:800;color:#f5f1eb;margin-bottom:1rem;">🛡️ 管理员看板</div>',
    unsafe_allow_html=True,
)

users_data = list_users()
active_users = [u for u in users_data if u["active"]]
perm_users = [u for u in active_users if u["expire_month"] == "999912"]
monthly_users = [u for u in active_users if u["expire_month"] != "999912"]
today = datetime.now().strftime("%Y-%m-%d")
this_month = datetime.now().strftime("%Y-%m")
new_this_month = [u for u in users_data if u.get("created_at", "")[:7] == this_month]

# ── KPI Row ──────────────────────────────────────────────────────────────────────

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("总用户", len(users_data))
k2.metric("活跃", len(active_users), delta=f"+{len(new_this_month)}本月")
k3.metric("永久", len(perm_users))
k4.metric("月付", len(monthly_users))
k5.metric("月收入(估)", f"¥{len(monthly_users)*99 + len(perm_users)*299:,}")
k6.metric("今日", today)

st.markdown("---")

# ── Tabs ─────────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs(["👥 用户管理", "🔑 激活码", "📧 邮件群发", "📊 统计"])

with tab1:
    if not users_data:
        st.info("暂无用户")
    else:
        rows = []
        for u in users_data:
            em = u["expire_month"]
            rows.append({
                "ID": u["id"], "用户名": u["user_name"],
                "类型": "永久" if em == "999912" else "月付",
                "到期": "永久" if em == "999912" else f"{em[:4]}-{em[4:]}",
                "设备": f'{u["device_count"]}/{u["max_devices"]}',
                "创建": u["created_at"][:10] if u.get("created_at") else "",
                "状态": "✅" if u["active"] else "❌",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Quick actions
        st.markdown("---")
        col_a, col_b, col_c = st.columns(3)
        action_user = col_a.selectbox("操作对象", [u["user_name"] for u in users_data])
        info = next((u for u in users_data if u["user_name"] == action_user), None)
        if info:
            col_b.metric("设备", f'{info["device_count"]}/{info["max_devices"]}')
            col_c.metric("到期", "永久" if info["expire_month"] == "999912" else info["expire_month"])

        ca, cb, cc = st.columns(3)
        if ca.button("🔄 切换启用/禁用", use_container_width=True):
            update_license_status(action_user, not info["active"])
            st.rerun()
        if cb.button("🗑️ 重置设备绑定", use_container_width=True):
            import sqlite3
            from tradingagents.auth.user_db import DB_PATH
            db = sqlite3.connect(str(DB_PATH))
            row = db.execute("SELECT key_hash FROM licenses WHERE user_name=?", (action_user,)).fetchone()
            db.close()
            if row:
                reset_devices(row[0])
                st.success(f"已重置 {action_user} 设备")
                st.rerun()

with tab2:
    st.markdown("#### 生成激活码")
    c1, c2, c3, c4 = st.columns(4)
    gen_name = c1.text_input("用户名", key="gen_name")
    gen_type = c2.selectbox("类型", ["月付", "永久"], key="gen_type")
    gen_expire = c3.text_input("到期年月", "202712", key="gen_expire",
                                help="月付时填写YYYYMM，永久忽略")
    gen_dev = c4.number_input("设备数", 1, 5, 1, key="gen_dev")

    col_k, col_m = st.columns([3, 1])
    if col_k.button("🔑 生成激活码", type="primary", use_container_width=True):
        if not gen_name:
            st.error("请输入用户名")
        else:
            exp = "999912" if gen_type == "永久" else gen_expire
            key = generate_license_key(gen_name, exp)
            key_hash = hashlib.sha256(key.encode()).hexdigest()
            if add_license(gen_name, key_hash, exp, gen_dev):
                st.success("✅ 激活码已生成，请复制发给用户")
                st.code(key, language="")
                st.session_state["last_key"] = key
                st.session_state["last_user"] = gen_name
                st.session_state["last_expire"] = exp
            else:
                st.error("用户已存在")

    # Send email
    last_key = st.session_state.get("last_key", "")
    if last_key:
        col_e, col_s = st.columns([3, 1])
        email_addr = col_e.text_input("用户邮箱(可选)", key="send_email")
        if col_s.button("📧 发送", use_container_width=True) and email_addr:
            from tradingagents.auth.email_service import send_activation_key
            if send_activation_key(email_addr, st.session_state.get("last_user", ""),
                                    last_key, st.session_state.get("last_expire", "999912")):
                st.success("已发送")
            else:
                st.warning("发送失败")

with tab3:
    st.markdown("#### 邮件群发")

    etype = st.selectbox("模板", ["验证码(测试)", "每日简报", "欢迎邮件"])

    if etype == "验证码(测试)":
        test_email = st.text_input("测试邮箱", "zwiilliamz007@163.com")
        if st.button("📧 发送测试验证码", use_container_width=True):
            from tradingagents.auth.email_service import send_verification_code
            r = send_verification_code(test_email)
            if r["success"]:
                st.success(r["message"])
            else:
                st.warning(r["message"])

    elif etype == "每日简报":
        if st.button("📧 发送每日简报(测试)", use_container_width=True):
            from tradingagents.dataflows.a_stock import get_market_indices, get_market_breadth
            from tradingagents.auth.email_service import send_daily_briefing
            indices = get_market_indices()
            breadth = get_market_breadth()
            brief = {
                "indices": [{"name": i["name"], "price": i["price"],
                              "change_pct": i["change_pct"]} for i in indices[:5]],
                "up": breadth.get("total_up", 0), "dn": breadth.get("total_down", 0),
                "nb": 0, "hot": "请打开软件查看完整数据",
            }
            if send_daily_briefing("zwiilliamz007@163.com", brief):
                st.success("每日简报已发送")

    elif etype == "欢迎邮件":
        w_email = st.text_input("邮箱地址")
        w_name = st.text_input("用户名")
        if st.button("📧 发送欢迎邮件", use_container_width=True):
            from tradingagents.auth.email_service import send_welcome
            if send_welcome(w_email, w_name):
                st.success("欢迎邮件已发送")

with tab4:
    st.markdown("#### 数据概览")
    # User growth chart (mock)
    months = ["1月", "2月", "3月", "4月", "5月", "6月"]
    growth = [0, 0, 0, 0, len(users_data), len(users_data)]
    growth_df = pd.DataFrame({"月份": months, "用户数": growth})
    st.bar_chart(growth_df.set_index("月份"))

    st.metric("赞赏总收入(估算)", f"¥{len(monthly_users)*99 + len(perm_users)*299:,}")

st.markdown("---")
if st.button("🚪 退出登录", use_container_width=True):
    st.session_state["admin_authed"] = False
    st.rerun()

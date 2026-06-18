"""管理员看板 — 用户管理 · 激活码 · 邮件群发 · 数据统计."""

from __future__ import annotations

import hashlib
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from tradingagents.auth.license import generate_license_key
from tradingagents.auth.plans import PLAN_LABELS, plan_label
from tradingagents.auth.user_db import (
    add_license,
    get_license_key_hash_for_user,
    list_users,
    normalize_user_name,
    reset_devices,
    update_license_status,
    validate_expire_month,
)
from web.auth_session import is_admin, sign_out
from web.components.common import inject_css

st.set_page_config(page_title="管理员看板", page_icon="🛡️", layout="wide", initial_sidebar_state="collapsed")
inject_css()


def _format_expire(expire_month: str) -> str:
    return "永久" if expire_month == "999912" else f"{expire_month[:4]}-{expire_month[4:]}"


def _license_type(expire_month: str) -> str:
    return "永久" if expire_month == "999912" else "月付/试用"


def _monthly_growth(users: list[dict]) -> pd.DataFrame:
    end = pd.Period(datetime.now().strftime("%Y-%m"), freq="M")
    months = [str(m) for m in pd.period_range(end=end, periods=6, freq="M")]
    rows = []
    for month in months:
        rows.append({
            "月份": month,
            "新增用户": sum(1 for u in users if (u.get("created_at") or "")[:7] == month),
        })
    return pd.DataFrame(rows)


def _require_admin():
    st.markdown(
        """
        <div class="ta-page-header">
            <div class="ta-eyebrow">ADMIN</div>
            <h1 class="ta-page-title">管理员权限</h1>
            <div class="ta-page-subtitle">请通过统一登录入口使用管理员账号进入后台。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.warning("当前会话不是管理员。请使用管理员账号从统一入口登录。")
    st.page_link("pages/activate.py", label="前往登录", use_container_width=True)
    st.stop()


if not is_admin():
    _require_admin()

st.markdown(
    """
    <div class="ta-page-header">
        <div class="ta-eyebrow">USER OPERATIONS</div>
        <h1 class="ta-page-title">管理员看板</h1>
        <div class="ta-page-subtitle">集中查看用户授权、生成激活码、重置设备绑定和发送通知邮件。</div>
    </div>
    """,
    unsafe_allow_html=True,
)

users_data = list_users()
active_users = [u for u in users_data if u["active"]]
perm_users = [u for u in active_users if u["expire_month"] == "999912"]
supporter_users = [u for u in active_users if u.get("plan") == "supporter"]
pro_users = [u for u in active_users if u.get("plan", "pro") == "pro"]
this_month = datetime.now().strftime("%Y-%m")
new_this_month = [u for u in users_data if (u.get("created_at") or "")[:7] == this_month]

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("总用户", len(users_data))
k2.metric("活跃", len(active_users), delta=f"+{len(new_this_month)}本月")
k3.metric("支持者版", len(supporter_users))
k4.metric("Pro 版", len(pro_users))
k5.metric("永久支持", len(perm_users))
k6.metric("今日", datetime.now().strftime("%Y-%m-%d"))

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["👥 用户管理", "🔑 激活码", "📧 邮件", "📊 统计"])

with tab1:
    q_col, status_col, plan_col, type_col = st.columns([2, 1, 1, 1])
    query = q_col.text_input("搜索用户", placeholder="用户名或邮箱")
    status_filter = status_col.selectbox("状态", ["全部", "活跃", "禁用"])
    plan_filter = plan_col.selectbox("套餐", ["全部", *PLAN_LABELS.values()])
    type_filter = type_col.selectbox("类型", ["全部", "永久", "月付/试用"])

    filtered_users = users_data
    if query.strip():
        needle = query.strip().lower()
        filtered_users = [u for u in filtered_users if needle in u["user_name"].lower()]
    if status_filter == "活跃":
        filtered_users = [u for u in filtered_users if u["active"]]
    elif status_filter == "禁用":
        filtered_users = [u for u in filtered_users if not u["active"]]
    if plan_filter != "全部":
        filtered_users = [u for u in filtered_users if plan_label(u.get("plan", "pro")) == plan_filter]
    if type_filter != "全部":
        filtered_users = [u for u in filtered_users if _license_type(u["expire_month"]) == type_filter]

    if not users_data:
        st.info("暂无用户")
    else:
        table_columns = ["ID", "用户名", "套餐", "类型", "到期", "设备", "创建", "最近检查", "状态"]
        rows = [
            {
                "ID": u["id"],
                "用户名": u["user_name"],
                "套餐": plan_label(u.get("plan", "pro")),
                "类型": _license_type(u["expire_month"]),
                "到期": _format_expire(u["expire_month"]),
                "设备": f'{u["device_count"]}/{u["max_devices"]}',
                "创建": (u.get("created_at") or "")[:10],
                "最近检查": (u.get("last_check") or "")[:16],
                "状态": "启用" if u["active"] else "禁用",
            }
            for u in filtered_users
        ]
        st.dataframe(pd.DataFrame(rows, columns=table_columns), use_container_width=True, hide_index=True)
        if not filtered_users:
            st.info("没有匹配的用户，快速操作仍可选择全部用户。")

        action_options = [u["user_name"] for u in filtered_users] or [u["user_name"] for u in users_data]
        st.markdown('<div class="ta-panel-title">快速操作</div>', unsafe_allow_html=True)
        col_a, col_b, col_c = st.columns([2, 1, 1])
        action_user = col_a.selectbox("操作对象", action_options)
        info = next((u for u in users_data if u["user_name"] == action_user), None)
        if info:
            col_b.metric("设备", f'{info["device_count"]}/{info["max_devices"]}')
            col_c.metric("到期", _format_expire(info["expire_month"]))

        ca, cb, cc = st.columns(3)
        if ca.button("切换启用/禁用", use_container_width=True, disabled=not info):
            if update_license_status(action_user, not info["active"]):
                st.success("状态已更新")
                st.rerun()
            else:
                st.error("未找到用户")
        if cb.button("重置设备绑定", use_container_width=True, disabled=not info):
            key_hash = get_license_key_hash_for_user(action_user)
            if key_hash:
                reset_devices(key_hash)
                st.success(f"已重置 {action_user} 的设备绑定")
                st.rerun()
            else:
                st.error("未找到该用户的激活码哈希")
        if cc.button("刷新列表", use_container_width=True):
            st.rerun()

with tab2:
    st.markdown('<div class="ta-panel-title">生成激活码</div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns([1.4, 0.9, 0.8, 0.9, 0.7])
    gen_name = c1.text_input("用户名/邮箱", key="gen_name")
    plan_options = list(PLAN_LABELS)
    gen_plan = c2.selectbox(
        "套餐",
        plan_options,
        index=1,
        format_func=lambda value: PLAN_LABELS[value],
        key="gen_plan",
    )
    gen_type = c3.selectbox("类型", ["月付/试用", "永久"], key="gen_type")
    gen_expire = c4.text_input("到期年月", datetime.now().strftime("%Y") + "12", key="gen_expire")
    gen_dev = c5.number_input("设备数", 1, 5, 1, key="gen_dev")

    if st.button("生成激活码", type="primary", use_container_width=True):
        try:
            normalized_name = normalize_user_name(gen_name)
            exp = "999912" if gen_type == "永久" else validate_expire_month(gen_expire)
            key = generate_license_key(normalized_name, exp, plan=gen_plan)
            key_hash = hashlib.sha256(key.encode()).hexdigest()
            created = add_license(normalized_name, key_hash, exp, int(gen_dev), plan=gen_plan)
        except ValueError as exc:
            st.error(str(exc))
        else:
            if created:
                st.success("激活码已生成")
                st.code(key, language="")
                st.session_state["last_key"] = key
                st.session_state["last_user"] = normalized_name
                st.session_state["last_expire"] = exp
            else:
                st.error("用户或激活码已存在")

    last_key = st.session_state.get("last_key", "")
    if last_key:
        st.markdown('<div class="ta-panel-title">发送激活码</div>', unsafe_allow_html=True)
        col_e, col_s = st.columns([3, 1])
        email_addr = col_e.text_input("用户邮箱", key="send_email")
        if col_s.button("发送", use_container_width=True) and email_addr:
            from tradingagents.auth.email_service import send_activation_key

            if send_activation_key(
                email_addr,
                st.session_state.get("last_user", ""),
                last_key,
                st.session_state.get("last_expire", "999912"),
            ):
                st.success("已发送")
            else:
                st.warning("发送失败")

with tab3:
    st.markdown('<div class="ta-panel-title">邮件工具</div>', unsafe_allow_html=True)
    etype = st.selectbox("模板", ["验证码测试", "每日简报", "欢迎邮件"])

    if etype == "验证码测试":
        test_email = st.text_input("测试邮箱", "")
        if st.button("发送测试验证码", use_container_width=True):
            from tradingagents.auth.email_service import send_verification_code

            r = send_verification_code(test_email)
            st.success(r["message"]) if r["success"] else st.warning(r["message"])

    elif etype == "每日简报":
        target_email = st.text_input("收件邮箱", "")
        if st.button("发送每日简报测试", use_container_width=True):
            from tradingagents.auth.email_service import send_daily_briefing
            from tradingagents.dataflows.a_stock import get_market_breadth, get_market_indices

            indices = get_market_indices()
            breadth = get_market_breadth()
            brief = {
                "indices": [
                    {"name": i["name"], "price": i["price"], "change_pct": i["change_pct"]}
                    for i in indices[:5]
                ],
                "up": breadth.get("total_up", 0),
                "dn": breadth.get("total_down", 0),
                "nb": 0,
                "hot": "请打开软件查看完整数据",
            }
            if send_daily_briefing(target_email, brief):
                st.success("每日简报已发送")
            else:
                st.warning("发送失败")

    elif etype == "欢迎邮件":
        w_email = st.text_input("邮箱地址")
        w_name = st.text_input("用户名")
        if st.button("发送欢迎邮件", use_container_width=True):
            from tradingagents.auth.email_service import send_welcome

            if send_welcome(w_email, w_name):
                st.success("欢迎邮件已发送")
            else:
                st.warning("发送失败")

with tab4:
    st.markdown('<div class="ta-panel-title">数据概览</div>', unsafe_allow_html=True)
    growth_df = _monthly_growth(users_data)
    if users_data:
        st.bar_chart(growth_df.set_index("月份"))
    else:
        st.info("暂无用户增长数据")
    s1, s2, s3 = st.columns(3)
    s1.metric("本月新增", len(new_this_month))
    s2.metric("活跃占比", f"{(len(active_users) / len(users_data) * 100):.1f}%" if users_data else "0.0%")
    s3.metric("有效授权", len(active_users))

st.markdown("---")
if st.button("退出登录", use_container_width=True):
    sign_out()
    st.rerun()

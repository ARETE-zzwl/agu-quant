"""赞赏激活 — 邮箱注册 + 激活码解锁."""

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from web.components.common import inject_css
from tradingagents.auth import activate_license, get_license_status

st.set_page_config(page_title="赞赏激活", page_icon="🔑", layout="centered", initial_sidebar_state="expanded")
inject_css()

st.markdown(
    '<div style="text-align:center;margin-bottom:1rem;">'
    '<span style="font-size:1.4rem;font-weight:800;color:#f5f1eb;">🔑 赞赏激活</span></div>',
    unsafe_allow_html=True,
)

status = get_license_status()

if status["valid"]:
    st.success(status["display"])
    exp = status.get("expire_month", "")
    if exp and exp != "999912":
        st.info(f"到期: {exp[:4]}-{exp[4:]}")
    elif status.get("is_permanent"):
        st.info("永久赞赏版 - 感谢支持!")
    st.caption("所有功能已解锁")
    st.stop()

st.warning("免费版 - 付费功能已锁定")

st.markdown("---")
st.markdown("### 赞赏支持")

c1, c2 = st.columns(2)
c1.markdown("**月付赞赏 - 99元/月**\n\nAI荐股 因子引擎 深度分析\n模拟盘 股票监控")
c2.markdown("**永久买断 - 299元**\n\n月付全部功能 +\n永久有效 2台设备 优先更新")

st.markdown("---")
st.markdown("### 邮箱注册 (7天免费试用)")

email = st.text_input("邮箱地址", placeholder="your@email.com", key="reg_email")

c_a, c_b = st.columns([3, 1])
if c_a.button("获取验证码", use_container_width=True):
    if not email or "@" not in email:
        st.error("请输入有效的邮箱地址")
    else:
        from tradingagents.auth.email_service import send_verification_code
        result = send_verification_code(email)
        if result["success"]:
            st.success(result["message"])
            st.session_state["reg_email_sent"] = True
        else:
            st.warning(result["message"])

if st.session_state.get("reg_email_sent"):
    vcode = c_b.text_input("验证码", max_chars=6, placeholder="6位数字")
    if st.button("验证并激活试用", type="primary"):
        from tradingagents.auth.email_service import verify_code, notify_admin_new_user
        vresult = verify_code(email, vcode)
        if vresult.get("verified"):
            from datetime import datetime, timedelta
            trial_expire = (datetime.now() + timedelta(days=7)).strftime("%Y%m")
            from tradingagents.auth.license import generate_license_key
            trial_key = generate_license_key(email.split("@")[0], trial_expire)
            activate_license(trial_key, email.split("@")[0])
            notify_admin_new_user(email)
            from tradingagents.auth.email_service import send_welcome
            send_welcome(email, email.split("@")[0])
            st.success(f"7天试用已激活! 到期: {trial_expire[:4]}-{trial_expire[4:]}")
            st.balloons()
            st.rerun()
        else:
            st.error(vresult.get("message", "验证失败"))

st.markdown("---")
st.markdown("### 输入激活码")
st.caption("赞赏后联系管理员获取激活码")

c1, c2 = st.columns([3, 1])
key_input = c1.text_input("激活码", placeholder="Agu-202512-XXXX-YYYY", label_visibility="collapsed", key="manual_key")
if c2.button("激活", type="primary", use_container_width=True):
    if not key_input:
        st.error("请输入激活码")
    else:
        result = activate_license(key_input)
        if result["success"]:
            st.success(result["message"])
            st.balloons()
            st.rerun()
        else:
            st.error(result["message"])

st.markdown("---")
st.caption("微信: agu_quant | Telegram: @agu_quant_bot | 转账后获取激活码")

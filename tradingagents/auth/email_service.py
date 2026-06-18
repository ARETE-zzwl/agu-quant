"""Email service via Resend API for registration & notifications."""

import json
import os
import random
import time
from datetime import datetime
from html import escape
from pathlib import Path

import resend

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
SUPPORT_CONTACT = os.getenv("TA_SUPPORT_CONTACT", "")

CODE_DIR = Path.home() / ".tradingagents" / "license"
CODE_DIR.mkdir(parents=True, exist_ok=True)
CODE_FILE = CODE_DIR / "verification_codes.json"


def _load_codes() -> dict:
    if CODE_FILE.exists():
        with open(CODE_FILE) as f:
            return json.load(f)
    return {}


def _save_codes(codes: dict):
    with open(CODE_FILE, "w") as f:
        json.dump(codes, f, indent=2)


def _clean_expired():
    codes = _load_codes()
    now = time.time()
    codes = {k: v for k, v in codes.items() if v.get("expires", 0) > now}
    _save_codes(codes)


def send_verification_code(email: str) -> dict:
    """Send a 6-digit verification code to user's email. Returns {success, message}."""
    if not RESEND_API_KEY or not FROM_EMAIL:
        return {"success": False, "message": "邮件服务未配置"}

    resend.api_key = RESEND_API_KEY
    code = str(random.randint(100000, 999999))

    try:
        r = resend.Emails.send({
            "from": FROM_EMAIL,
            "to": email,
            "subject": "A股量化系统 — 验证码",
            "html": f"""
            <div style="font-family: sans-serif; max-width: 500px; margin: 0 auto;">
                <h2 style="color: #f97316;">A股量化系统</h2>
                <p>您的验证码：</p>
                <div style="font-size: 32px; font-weight: bold; letter-spacing: 8px;
                     color: #f97316; padding: 16px; background: #1a1a1a;
                     border-radius: 8px; text-align: center;">{code}</div>
                <p style="color: #888; margin-top: 20px;">验证码 10 分钟内有效，请勿转发。</p>
            </div>
            """
        })

        _clean_expired()
        codes = _load_codes()
        codes[email] = {
            "code": code,
            "expires": time.time() + 600,
            "verified": False,
        }
        _save_codes(codes)

        return {"success": True, "message": "验证码已发送，请查收邮件"}

    except Exception as e:
        return {"success": False, "message": f"发送失败: {e}"}


def verify_code(email: str, code: str) -> dict:
    """Verify the code user entered. Returns {success, message, verified}."""
    _clean_expired()
    codes = _load_codes()
    entry = codes.get(email, {})
    if not entry:
        return {"success": False, "message": "请先获取验证码"}
    if time.time() > entry.get("expires", 0):
        return {"success": False, "message": "验证码已过期，请重新获取"}
    if entry.get("code") != code:
        return {"success": False, "message": "验证码错误"}

    codes[email]["verified"] = True
    _save_codes(codes)
    return {"success": True, "message": "验证成功", "verified": True}


def send_activation_key(email: str, user_name: str, key: str, expire_month: str) -> bool:
    """Send activation key to user after payment."""
    if not RESEND_API_KEY or not FROM_EMAIL:
        return False

    resend.api_key = RESEND_API_KEY
    is_perm = expire_month == "999912"
    expire_str = "永久有效" if is_perm else f"到期 {expire_month[:4]}-{expire_month[4:]}"

    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": email,
            "subject": "A股量化系统 — 您的激活码",
            "html": f"""
            <div style="font-family: sans-serif; max-width: 500px; margin: 0 auto;">
                <h2 style="color: #f97316;">赞赏激活码</h2>
                <p>{user_name} 您好，感谢赞赏支持！</p>
                <p>您的激活码：</p>
                <div style="font-size: 22px; font-weight: bold; letter-spacing: 2px;
                     color: #22c55e; padding: 12px; background: #1a1a1a;
                     border-radius: 8px; text-align: center;">{key}</div>
                <p>有效期: {expire_str}</p>
                <p style="color: #888; margin-top: 16px;">
                    在软件的「赞赏激活」页面输入此激活码即可解锁全部功能。
                </p>
            </div>
            """
        })
        return True
    except Exception:
        return False


def notify_admin_new_user(email: str):
    """Notify admin of new registration."""
    if not ADMIN_EMAIL or not RESEND_API_KEY or not FROM_EMAIL:
        return
    resend.api_key = RESEND_API_KEY
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": ADMIN_EMAIL,
            "subject": f"[A股量化] 新用户注册: {email}",
            "text": f"新用户注册:\n邮箱: {email}\n时间: {datetime.now()}\n",
        })
    except Exception:
        pass


def send_expiry_reminder(email: str, user_name: str, days_left: int) -> bool:
    """Send expiry reminder N days before license expires."""
    if not RESEND_API_KEY or not FROM_EMAIL:
        return False
    resend.api_key = RESEND_API_KEY
    support_message = (
        f"官方联系方式：{escape(SUPPORT_CONTACT)}"
        if SUPPORT_CONTACT
        else "请在应用内打开「支持开源计划」页面查看续费方式。"
    )
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": email,
            "subject": f"A股量化系统 — 您的赞赏即将到期 ({days_left}天后)",
            "html": f"""
            <div style="font-family: sans-serif; max-width: 500px; margin: 0 auto;">
                <h2 style="color: #f97316;">赞赏即将到期</h2>
                <p>{user_name} 您好，您的赞赏服务将在 <b>{days_left}天后</b> 到期。</p>
                <p>如需续费支持者版或 Pro 版，请通过官方支持入口办理。</p>
                <p>{support_message}</p>
            </div>
            """
        })
        return True
    except Exception:
        return False


# ── Rich Email Templates ─────────────────────────────────────────────────────


def send_welcome(email: str, user_name: str) -> bool:
    if not RESEND_API_KEY or not FROM_EMAIL:
        return False
    resend.api_key = RESEND_API_KEY
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": email,
            "subject": "欢迎使用 A股量化系统",
            "html": f"""
            <div style="font-family:sans-serif;max-width:500px;margin:0 auto;">
                <h2 style="color:#f97316;">欢迎 {user_name}！</h2>
                <h3>快速开始</h3>
                <ol><li>下载代码并安装依赖</li><li>配置 DeepSeek API Key</li><li>启动: streamlit run web/app.py</li></ol>
                <h3>主要功能</h3>
                <ul><li>AI荐股 — 12套策略评分</li><li>因子引擎 — 97因子回测</li><li>模拟盘 — A股真实规则</li><li>深度分析 — 7Agent协作</li></ul>
                <p style="color:#888;margin-top:16px;">需要官方安装包、自动日报或持续支持时，可在应用内查看支持开源计划。</p>
            </div>"""
        })
        return True
    except Exception:
        return False


def send_daily_briefing(email: str, briefing: dict) -> bool:
    """Send daily market briefing with indices, breadth, hot sectors."""
    if not RESEND_API_KEY or not FROM_EMAIL:
        return False
    resend.api_key = RESEND_API_KEY
    today = __import__('datetime').datetime.now().strftime("%Y-%m-%d")
    idx_html = ""
    for i in briefing.get("indices", [])[:5]:
        c = "#ef4444" if i.get("change_pct", 0) > 0 else "#22c55e"
        idx_html += f'<tr><td>{i["name"]}</td><td>{i["price"]:.2f}</td><td style="color:{c}">{i["change_pct"]:+.2f}%</td></tr>'
    try:
        resend.Emails.send({
            "from": FROM_EMAIL, "to": email,
            "subject": f"A股每日简报 {today}",
            "html": f"""
            <div style="font-family:sans-serif;max-width:550px;margin:0 auto;">
                <h2 style="color:#f97316;">A股每日简报 {today}</h2>
                <h3>大盘指数</h3>
                <table style="width:100%;border-collapse:collapse;">
                <tr style="background:#1a1a1a"><th>指数</th><th>价格</th><th>涨跌</th></tr>{idx_html}</table>
                <p>上涨{briefing.get('up',0)}家 | 下跌{briefing.get('dn',0)}家 | 北向{briefing.get('nb',0):+.1f}亿</p>
                <h3>热门板块</h3><p>{briefing.get('hot', '暂无')}</p>
                <p style="color:#888;margin-top:20px;">本邮件由AI生成，不构成投资建议</p>
            </div>"""
        })
        return True
    except Exception:
        return False


def send_price_alert(email: str, code: str, name: str, price: float, target: float, alert_type: str) -> bool:
    """Price alert when stock hits key levels: support/resistance/stop_loss/take_profit."""
    if not RESEND_API_KEY or not FROM_EMAIL:
        return False
    resend.api_key = RESEND_API_KEY
    labels = {"support":"触及支撑","resistance":"触及压力","stop_loss":"触发止损","take_profit":"达到止盈"}
    try:
        resend.Emails.send({
            "from": FROM_EMAIL, "to": email,
            "subject": f"[预警] {code} {name} {labels.get(alert_type, alert_type)}",
            "html": f"""
            <div style="font-family:sans-serif;max-width:500px;margin:0 auto;">
                <h2 style="color:#f97316;">价格预警</h2>
                <p><b>{code} {name}</b> {labels.get(alert_type, alert_type)}</p>
                <p>当前: {price:.2f} | 目标: {target:.2f}</p>
                <p style="color:#888;">请打开软件查看详细分析</p>
            </div>"""
        })
        return True
    except Exception:
        return False


def send_weekly_report(email: str, report: dict) -> bool:
    """Weekly portfolio performance report."""
    if not RESEND_API_KEY or not FROM_EMAIL:
        return False
    resend.api_key = RESEND_API_KEY
    c = "#ef4444" if report.get("pnl", 0) > 0 else "#22c55e"
    try:
        resend.Emails.send({
            "from": FROM_EMAIL, "to": email,
            "subject": f"模拟盘周报 ({report.get('week', '')})",
            "html": f"""
            <div style="font-family:sans-serif;max-width:500px;margin:0 auto;">
                <h2 style="color:#f97316;">模拟盘周报</h2>
                <p>总资产: {report.get('eq', 0):,.0f} | 盈亏: <span style="color:{c}">{report.get('pnl', 0):+,.0f}</span></p>
                <p>收益率: {report.get('ret', 0):+.1f}% | 夏普: {report.get('sh', 0):.2f} | 回撤: {report.get('dd', 0):.1f}%</p>
                <p>推荐: {report.get('picks', '暂无')}</p>
                <p style="color:#888;">不构成投资建议</p>
            </div>"""
        })
        return True
    except Exception:
        return False

"""License key validation — hardened version.

Honest assessment: Python open-source cannot be 100% crack-proof.
Strategy: make cracking annoying enough + trust-based model.
"""

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from .plans import PRO_PLAN, normalize_plan, plan_allows, plan_label

_SECRET = b"agu-license-v2-k3y-2025-r7q"

STATE_FILE = Path.home() / ".tradingagents" / "license" / "activation.json"
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

PREMIUM_FEATURES = ["深度分析", "AI 荐股", "因子引擎", "股票监控", "模拟盘"]
FREE_FEATURES = ["大盘看盘", "板块分析", "一键选股"]


# ── Obfuscated storage ──────────────────────────────────────────────────────

def _xor_encode(data: str) -> str:
    key = os.urandom(1)[0]
    return chr(key) + "".join(chr(ord(c) ^ key) for c in data)


def _xor_decode(encoded: str) -> str:
    key = ord(encoded[0])
    return "".join(chr(ord(c) ^ key) for c in encoded[1:])


def _state_hash(state: dict) -> str:
    payload = {k: v for k, v in state.items() if k != "_h"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:8]


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "rb") as f:
            raw = f.read()
        # Try plain JSON first
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        # Fallback: obfuscated
        try:
            encoded = raw.decode("latin-1")
            return json.loads(_xor_decode(encoded))
        except Exception:
            return {}
    except Exception:
        return {}


def _save_state(state: dict):
    state["_ts"] = int(time.time())
    state["_h"] = _state_hash(state)
    encoded = _xor_encode(json.dumps(state, ensure_ascii=True))
    with open(STATE_FILE, "wb") as f:
        f.write(encoded.encode("latin-1"))


# ── License logic ───────────────────────────────────────────────────────────

def generate_license_key(
    user_name: str,
    expire_month: str = "999912",
    plan: str = PRO_PLAN,
) -> str:
    import secrets
    from .user_db import normalize_user_name, validate_expire_month

    user_name = normalize_user_name(user_name)
    expire_month = validate_expire_month(expire_month)
    plan = normalize_plan(plan)
    rand = secrets.token_hex(2)
    base = f"Agu-{plan}-{expire_month}-{rand}"
    sig = hmac.new(_SECRET, f"{user_name}:{plan}:{expire_month}:{rand}".encode(),
                   hashlib.sha256).hexdigest()[:4]
    return f"{base}-{sig}"


def _parse_license_key(key: str) -> tuple[str, str, str, str, bool] | None:
    parts = key.strip().split("-")
    if parts[0] != "Agu" or len(parts) not in (4, 5):
        return None
    legacy = len(parts) == 4
    if legacy:
        plan = PRO_PLAN
        exp, rand, sig = parts[1:]
    else:
        try:
            plan = normalize_plan(parts[1])
        except ValueError:
            return None
        exp, rand, sig = parts[2:]
    try:
        from .user_db import validate_expire_month

        validate_expire_month(exp)
    except ValueError:
        return None
    if not rand or not sig:
        return None
    return exp, rand, sig, plan, legacy


def _validate_key_integrity(key: str, user_name: str = "") -> bool:
    """Check if key was tampered with using user-bound HMAC when possible."""
    parsed = _parse_license_key(key)
    if not parsed:
        return False
    if not user_name:
        return True

    from .user_db import normalize_user_name

    expire, rand, sig, plan, legacy = parsed
    normalized_user = normalize_user_name(user_name)
    payload = (
        f"{normalized_user}:{expire}:{rand}"
        if legacy
        else f"{normalized_user}:{plan}:{expire}:{rand}"
    )
    expected = hmac.new(
        _SECRET,
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()[:4]
    return hmac.compare_digest(expected, sig)


def activate_license(key: str, user_name: str = "", trial_days: int | None = None) -> dict:
    key = key.strip()
    parsed = _parse_license_key(key)
    if not parsed:
        return {"success": False, "message": "激活码格式无效"}
    if user_name and not _validate_key_integrity(key, user_name):
        return {"success": False, "message": "激活码与用户名不匹配"}

    from .machine_id import get_machine_fingerprint
    from .user_db import normalize_user_name

    normalized_user = normalize_user_name(user_name) if user_name else ""
    machine = get_machine_fingerprint()
    expire = parsed[0]
    plan = parsed[3]
    key_hash = hashlib.sha256(key.encode()).hexdigest()

    state = _load_state()
    state["key"] = key
    state["key_hash"] = key_hash
    state["machine"] = machine
    state["expire"] = expire
    state["plan"] = plan
    state["user"] = normalized_user
    state["activated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    if trial_days is not None:
        days = int(trial_days)
        if days < 1:
            return {"success": False, "message": "试用天数无效"}
        state["trial_expires_at"] = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    else:
        state.pop("trial_expires_at", None)
    _save_state(state)

    return {
        "success": True,
        "message": "激活成功!" + ("永久有效" if expire == "999912" else f"到期 {expire[:4]}-{expire[4:]}"),
        "expire_month": expire,
        "plan": plan,
        "is_permanent": expire == "999912",
    }


def check_license() -> dict:
    state = _load_state()
    if not state.get("key"):
        return {"valid": False, "reason": "no_key"}

    # Integrity check — detects file tampering
    saved_h = state.get("_h", "")
    computed_h = _state_hash(state)
    if saved_h and computed_h != saved_h:
        return {"valid": False, "reason": "tampered", "tampered": True}

    trial_expires_at = state.get("trial_expires_at", "")
    if trial_expires_at:
        try:
            trial_end = datetime.strptime(trial_expires_at, "%Y-%m-%d").date()
        except ValueError:
            return {"valid": False, "reason": "tampered", "tampered": True}
        if datetime.now().date() > trial_end:
            return {"valid": False, "reason": "expired", "expire": trial_expires_at}

    # Expiry check
    expire = state.get("expire", "")
    if expire and expire != "999912":
        if datetime.now().strftime("%Y%m") > expire:
            return {"valid": False, "reason": "expired", "expire": expire}

    # Machine check (soft — warn but don't block on minor mismatch)
    from .machine_id import get_machine_fingerprint
    machine = get_machine_fingerprint()
    saved_machine = state.get("machine", "")
    if saved_machine and saved_machine != machine:
        return {"valid": False, "reason": "machine_mismatch"}

    try:
        plan = normalize_plan(state.get("plan", PRO_PLAN))
    except ValueError:
        return {"valid": False, "reason": "tampered", "tampered": True}

    return {
        "valid": True,
        "user_name": state.get("user", ""),
        "expire_month": expire,
        "trial_expires_at": trial_expires_at,
        "plan": plan,
        "is_permanent": expire == "999912",
    }


def is_premium() -> bool:
    return check_license().get("valid", False)


def has_plan_access(required_plan: str = "supporter") -> bool:
    status = check_license()
    return bool(status.get("valid")) and plan_allows(status.get("plan", PRO_PLAN), required_plan)


def get_license_status() -> dict:
    result = check_license()
    if result.get("tampered"):
        return {"valid": False, "display": "⚠️ 激活文件异常 | 请重新激活",
                "reason": "tampered"}
    if result["valid"]:
        label = plan_label(result.get("plan", PRO_PLAN))
        if result["is_permanent"]:
            result["display"] = f"🔓 {label} · 永久支持"
        elif result.get("trial_expires_at"):
            result["display"] = f"🔓 {label}试用 (到期 {result['trial_expires_at']})"
        else:
            em = result["expire_month"]
            result["display"] = f"🔓 {label} (到期 {em[:4]}-{em[4:]})"
    else:
        reason = result.get("reason", "")
        if reason == "expired":
            result["display"] = "⏰ 已到期 | 续费赞赏"
        elif reason == "machine_mismatch":
            result["display"] = "⚠️ 设备变更 | 联系重置"
        else:
            result["display"] = "🔒 免费版 | 赞赏解锁"
    return result


def needs_premium(page_name: str) -> bool:
    return page_name in PREMIUM_FEATURES

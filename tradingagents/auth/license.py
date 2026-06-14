"""License key validation — hardened version.

Honest assessment: Python open-source cannot be 100% crack-proof.
Strategy: make cracking annoying enough + trust-based model.
"""

import hashlib
import hmac
import json
import os
import time
from datetime import datetime
from pathlib import Path

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
    state["_h"] = hashlib.sha256(
        json.dumps(state, sort_keys=True).encode()).hexdigest()[:8]
    encoded = _xor_encode(json.dumps(state, ensure_ascii=False))
    with open(STATE_FILE, "wb") as f:
        f.write(encoded.encode("latin-1"))


# ── License logic ───────────────────────────────────────────────────────────

def generate_license_key(user_name: str, expire_month: str = "999912") -> str:
    import secrets
    rand = secrets.token_hex(2)
    base = f"Agu-{expire_month}-{rand}"
    sig = hmac.new(_SECRET, f"{user_name}:{expire_month}:{rand}".encode(),
                   hashlib.sha256).hexdigest()[:4]
    return f"{base}-{sig}"


def _validate_key_integrity(key: str) -> bool:
    """Check if key was tampered with (basic format + checksum)."""
    parts = key.strip().split("-")
    if len(parts) != 5 or parts[0] != "Agu":
        return False
    exp = parts[1]
    return len(exp) == 6 and exp.isdigit() and (exp == "999912" or int(exp[:4]) >= 2024)


def activate_license(key: str, user_name: str = "") -> dict:
    key = key.strip()
    if not _validate_key_integrity(key):
        return {"success": False, "message": "激活码格式无效"}

    from .machine_id import get_machine_fingerprint
    machine = get_machine_fingerprint()
    parts = key.split("-")
    expire = parts[1]
    key_hash = hashlib.sha256(key.encode()).hexdigest()

    state = _load_state()
    state["key"] = key
    state["key_hash"] = key_hash
    state["machine"] = machine
    state["expire"] = expire
    state["user"] = user_name
    state["activated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _save_state(state)

    return {
        "success": True,
        "message": "激活成功!" + ("永久有效" if expire == "999912" else f"到期 {expire[:4]}-{expire[4:]}"),
        "expire_month": expire,
        "is_permanent": expire == "999912",
    }


def check_license() -> dict:
    state = _load_state()
    if not state.get("key"):
        return {"valid": False, "reason": "no_key"}

    # Integrity check — detects file tampering
    saved_h = state.pop("_h", "")
    saved_ts = state.pop("_ts", 0)
    computed_h = hashlib.sha256(
        json.dumps(state, sort_keys=True).encode()).hexdigest()[:8]
    if saved_h and computed_h != saved_h:
        return {"valid": False, "reason": "tampered", "tampered": True}

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

    # Restore hash fields
    state["_h"] = saved_h
    state["_ts"] = saved_ts

    return {
        "valid": True,
        "user_name": state.get("user", ""),
        "expire_month": expire,
        "is_permanent": expire == "999912",
    }


def is_premium() -> bool:
    return check_license().get("valid", False)


def get_license_status() -> dict:
    result = check_license()
    if result.get("tampered"):
        return {"valid": False, "display": "⚠️ 激活文件异常 | 请重新激活",
                "reason": "tampered"}
    if result["valid"]:
        if result["is_permanent"]:
            result["display"] = "🔓 永久赞赏版"
        else:
            em = result["expire_month"]
            result["display"] = f"🔓 赞赏版 (到期 {em[:4]}-{em[4:]})"
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

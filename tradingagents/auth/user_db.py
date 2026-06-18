"""SQLite-based user/license database."""

import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from .plans import PRO_PLAN, normalize_plan

DB_DIR = Path.home() / ".tradingagents" / "license"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "users.db"
_EXPIRE_MONTH_RE = re.compile(r"^\d{6}$")


def normalize_user_name(user_name: str) -> str:
    """Normalize user identifiers before storing or comparing them."""
    if not isinstance(user_name, str):
        raise ValueError("用户名不能为空")
    normalized = user_name.strip().lower()
    if not normalized:
        raise ValueError("用户名不能为空")
    if len(normalized) > 120:
        raise ValueError("用户名过长")
    if any(ch in normalized for ch in ("\x00", "\r", "\n", "\t")):
        raise ValueError("用户名包含非法字符")
    return normalized


def validate_expire_month(expire_month: str) -> str:
    """Validate and normalize a YYYYMM expiration value."""
    value = str(expire_month or "").strip()
    if value == "999912":
        return value
    if not _EXPIRE_MONTH_RE.fullmatch(value):
        raise ValueError("到期年月必须使用 YYYYMM 格式")
    year = int(value[:4])
    month = int(value[4:])
    if year < 2024 or month < 1 or month > 12:
        raise ValueError("到期年月无效")
    return value


def _normalize_max_devices(max_devices: int) -> int:
    try:
        value = int(max_devices)
    except (TypeError, ValueError):
        raise ValueError("设备数必须是整数")
    if value < 1 or value > 10:
        raise ValueError("设备数必须在 1 到 10 之间")
    return value


def _decode_machines(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _conn():
    c = sqlite3.connect(str(DB_PATH))
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init_db():
    db = _conn()
    db.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            expire_month TEXT NOT NULL,
            machine_id TEXT,
            device_count INTEGER DEFAULT 0,
            max_devices INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            last_check TEXT,
            active INTEGER DEFAULT 1
        )
    """)
    columns = {row[1] for row in db.execute("PRAGMA table_info(licenses)").fetchall()}
    if "plan" not in columns:
        db.execute("ALTER TABLE licenses ADD COLUMN plan TEXT NOT NULL DEFAULT 'pro'")
    db.execute("""
        UPDATE licenses
        SET device_count=0
        WHERE (machine_id IS NULL OR machine_id='' OR machine_id='{}')
          AND device_count != 0
    """)
    db.commit()
    db.close()


def add_license(
    user_name: str,
    key_hash: str,
    expire_month: str,
    max_devices: int = 1,
    plan: str = PRO_PLAN,
) -> bool:
    init_db()
    user_name = normalize_user_name(user_name)
    key_hash = str(key_hash or "").strip().lower()
    if not key_hash:
        raise ValueError("激活码哈希不能为空")
    expire_month = validate_expire_month(expire_month)
    max_devices = _normalize_max_devices(max_devices)
    plan = normalize_plan(plan)

    db = _conn()
    try:
        exists = db.execute(
            "SELECT 1 FROM licenses WHERE lower(user_name)=?",
            (user_name,),
        ).fetchone()
        if exists:
            return False
        db.execute(
            """
            INSERT INTO licenses
                (user_name, key_hash, expire_month, device_count, max_devices, plan)
            VALUES (?,?,?,?,?,?)
            """,
            (user_name, key_hash, expire_month, 0, max_devices, plan),
        )
        db.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        db.close()


def bind_machine(key_hash: str, machine_id: str, max_devices: int = 1) -> bool:
    init_db()
    key_hash = str(key_hash or "").strip().lower()
    machine_id = str(machine_id or "").strip()
    if not key_hash or not machine_id:
        return False

    db = _conn()
    row = db.execute(
        "SELECT machine_id, device_count, max_devices FROM licenses WHERE key_hash=? AND active=1",
        (key_hash,),
    ).fetchone()
    if not row:
        db.close()
        return False

    existing = _decode_machines(row[0])
    max_d = int(row[2] or max_devices or 1)

    if machine_id in existing:
        db.execute(
            "UPDATE licenses SET last_check=datetime('now') WHERE key_hash=?",
            (key_hash,),
        )
        db.commit()
        db.close()
        return True  # already bound

    if len(existing) >= max_d:
        db.close()
        return False  # device limit reached

    existing[machine_id] = datetime.now().strftime("%Y-%m-%d")
    db.execute(
        "UPDATE licenses SET machine_id=?, device_count=? WHERE key_hash=?",
        (json.dumps(existing), len(existing), key_hash),
    )
    db.execute(
        "UPDATE licenses SET last_check=datetime('now') WHERE key_hash=?",
        (key_hash,),
    )
    db.commit()
    db.close()
    return True


def check_license_db(key_hash: str, machine_id: str) -> dict:
    """Check license status. Returns {valid, user_name, expire_month, is_permanent}."""
    init_db()
    db = _conn()
    row = db.execute(
        "SELECT user_name, expire_month, machine_id, active, plan FROM licenses WHERE key_hash=?",
        (key_hash,),
    ).fetchone()
    db.close()

    if not row or not row[3]:
        return {"valid": False, "reason": "invalid_code"}

    user_name, expire_month, bound_machines, _, plan = row

    # Check expiration
    if expire_month != "999912":
        now = datetime.now().strftime("%Y%m")
        if now > expire_month:
            return {"valid": False, "reason": "expired", "expire_month": expire_month}

    # Check machine binding
    bound = _decode_machines(bound_machines)
    if machine_id not in bound:
        return {"valid": False, "reason": "machine_mismatch"}

    return {
        "valid": True,
        "user_name": user_name,
        "expire_month": expire_month,
        "plan": normalize_plan(plan),
        "is_permanent": expire_month == "999912",
    }


def list_users() -> list[dict]:
    init_db()
    db = _conn()
    rows = db.execute(
        "SELECT id, user_name, expire_month, device_count, max_devices, created_at, last_check, active, plan FROM licenses ORDER BY id"
    ).fetchall()
    db.close()
    return [
        {
            "id": r[0], "user_name": r[1], "expire_month": r[2],
            "device_count": r[3], "max_devices": r[4],
            "created_at": r[5], "last_check": r[6], "active": bool(r[7]),
            "plan": normalize_plan(r[8]),
        }
        for r in rows
    ]


def update_license_status(user_name: str, active: bool):
    init_db()
    user_name = normalize_user_name(user_name)
    db = _conn()
    cur = db.execute("UPDATE licenses SET active=? WHERE lower(user_name)=?", (int(active), user_name))
    db.commit()
    db.close()
    return cur.rowcount > 0


def get_license_key_hash_for_user(user_name: str) -> str | None:
    init_db()
    user_name = normalize_user_name(user_name)
    db = _conn()
    row = db.execute(
        "SELECT key_hash FROM licenses WHERE lower(user_name)=? ORDER BY id DESC LIMIT 1",
        (user_name,),
    ).fetchone()
    db.close()
    return row[0] if row else None


def reset_devices(key_hash: str):
    init_db()
    key_hash = str(key_hash or "").strip().lower()
    db = _conn()
    db.execute("UPDATE licenses SET machine_id='{}', device_count=0 WHERE key_hash=?", (key_hash,))
    db.commit()
    db.close()

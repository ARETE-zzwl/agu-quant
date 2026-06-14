"""SQLite-based user/license database."""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_DIR = Path.home() / ".tradingagents" / "license"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "users.db"


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
            device_count INTEGER DEFAULT 1,
            max_devices INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            last_check TEXT,
            active INTEGER DEFAULT 1
        )
    """)
    db.commit()
    db.close()


def add_license(user_name: str, key_hash: str, expire_month: str, max_devices: int = 1) -> bool:
    init_db()
    db = _conn()
    try:
        db.execute(
            "INSERT INTO licenses (user_name, key_hash, expire_month, max_devices) VALUES (?,?,?,?)",
            (user_name, key_hash, expire_month, max_devices),
        )
        db.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        db.close()


def bind_machine(key_hash: str, machine_id: str, max_devices: int = 1) -> bool:
    init_db()
    db = _conn()
    row = db.execute(
        "SELECT machine_id, device_count, max_devices FROM licenses WHERE key_hash=? AND active=1",
        (key_hash,),
    ).fetchone()
    if not row:
        db.close()
        return False

    existing = json.loads(row[0]) if row[0] else {}
    count = int(row[1])
    max_d = max_devices or int(row[2])

    if machine_id in existing:
        db.close()
        return True  # already bound

    if count >= max_d:
        db.close()
        return False  # device limit reached

    existing[machine_id] = datetime.now().strftime("%Y-%m-%d")
    db.execute(
        "UPDATE licenses SET machine_id=?, device_count=? WHERE key_hash=?",
        (json.dumps(existing), count + 1, key_hash),
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
        "SELECT user_name, expire_month, machine_id, active FROM licenses WHERE key_hash=?",
        (key_hash,),
    ).fetchone()
    db.close()

    if not row or not row[3]:
        return {"valid": False, "reason": "invalid_code"}

    user_name, expire_month, bound_machines, _ = row

    # Check expiration
    if expire_month != "999912":
        now = datetime.now().strftime("%Y%m")
        if now > expire_month:
            return {"valid": False, "reason": "expired", "expire_month": expire_month}

    # Check machine binding
    bound = json.loads(bound_machines) if bound_machines else {}
    if machine_id not in bound:
        return {"valid": False, "reason": "machine_mismatch"}

    return {
        "valid": True,
        "user_name": user_name,
        "expire_month": expire_month,
        "is_permanent": expire_month == "999912",
    }


def list_users() -> list[dict]:
    init_db()
    db = _conn()
    rows = db.execute(
        "SELECT id, user_name, expire_month, device_count, max_devices, created_at, last_check, active FROM licenses ORDER BY id"
    ).fetchall()
    db.close()
    return [
        {
            "id": r[0], "user_name": r[1], "expire_month": r[2],
            "device_count": r[3], "max_devices": r[4],
            "created_at": r[5], "last_check": r[6], "active": bool(r[7]),
        }
        for r in rows
    ]


def update_license_status(user_name: str, active: bool):
    init_db()
    db = _conn()
    db.execute("UPDATE licenses SET active=? WHERE user_name=?", (int(active), user_name))
    db.commit()
    db.close()


def reset_devices(key_hash: str):
    init_db()
    db = _conn()
    db.execute("UPDATE licenses SET machine_id='{}', device_count=0 WHERE key_hash=?", (key_hash,))
    db.commit()
    db.close()

"""Hardware fingerprint for license binding."""

import hashlib
import platform
import subprocess
import uuid


def _get_cpu_id() -> str:
    try:
        if platform.system() == "Windows":
            r = subprocess.run(["wmic", "cpu", "get", "ProcessorId"],
                               capture_output=True, text=True, timeout=5)
            lines = [l.strip() for l in r.stdout.split("\n") if l.strip()]
            return lines[1] if len(lines) >= 2 else ""
    except Exception:
        pass
    return ""


def _get_mac() -> str:
    try:
        return hex(uuid.getnode())
    except Exception:
        return ""


def _get_board_uuid() -> str:
    try:
        if platform.system() == "Windows":
            r = subprocess.run(["wmic", "csproduct", "get", "UUID"],
                               capture_output=True, text=True, timeout=5)
            lines = [l.strip() for l in r.stdout.split("\n") if l.strip()]
            return lines[1] if len(lines) >= 2 else ""
    except Exception:
        pass
    return ""


def get_machine_fingerprint() -> str:
    """Generate a stable machine fingerprint."""
    parts = [
        _get_cpu_id(),
        _get_mac(),
        _get_board_uuid(),
        platform.node(),
        platform.machine(),
    ]
    combined = "|".join(p for p in parts if p)
    if not combined.strip("|"):
        combined = str(uuid.getnode()) + platform.node()
    return hashlib.sha256(combined.encode()).hexdigest()[:16]

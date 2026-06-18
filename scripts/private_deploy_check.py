"""Validate private deployment configuration without printing secrets."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values


MODEL_KEY_NAMES = (
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "DASHSCOPE_API_KEY",
    "ZHIPU_API_KEY",
    "MINIMAX_API_KEY",
    "OPENROUTER_API_KEY",
)
_PLACEHOLDERS = {
    "admin123",
    "password",
    "changeme",
    "sk-your-key",
    "your-api-key",
    "your-password",
}


def _is_configured(value: object) -> bool:
    normalized = str(value or "").strip().lower()
    return (
        bool(normalized)
        and normalized not in _PLACEHOLDERS
        and "your-" not in normalized
        and not normalized.startswith("replace-")
    )


def validate_private_environment(values: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    username = str(values.get("TA_ADMIN_USERNAME", "")).strip()
    password = str(values.get("TA_ADMIN_PASSWORD", "")).strip()

    if not username:
        errors.append("必须配置 TA_ADMIN_USERNAME")
    if len(password) < 12 or not _is_configured(password):
        errors.append("TA_ADMIN_PASSWORD 管理员密码至少 12 位且不能使用占位值")
    if not any(_is_configured(values.get(name)) for name in MODEL_KEY_NAMES):
        errors.append("至少配置一个真实模型 API Key")

    public_url = str(values.get("TA_PUBLIC_BASE_URL", "")).strip()
    if public_url:
        parsed = urlparse(public_url)
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append("TA_PUBLIC_BASE_URL 必须使用完整 HTTPS 地址")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate private deployment environment")
    parser.add_argument("--env-file", type=Path, default=Path(".env.private"))
    args = parser.parse_args(argv)

    if not args.env_file.exists():
        print(f"[ERROR] Environment file not found: {args.env_file}")
        return 1
    errors = validate_private_environment(dotenv_values(args.env_file))
    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1
    print("[OK] Private deployment configuration passed validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

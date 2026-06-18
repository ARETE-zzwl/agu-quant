from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_private_deployment_validator_requires_admin_and_model_credentials():
    from scripts.private_deploy_check import validate_private_environment

    errors = validate_private_environment({})
    assert any("TA_ADMIN_USERNAME" in error for error in errors)
    assert any("模型 API Key" in error for error in errors)

    valid = {
        "TA_ADMIN_USERNAME": "owner",
        "TA_ADMIN_PASSWORD": "a-long-private-password",
        "DEEPSEEK_API_KEY": "configured-secret",
    }
    assert validate_private_environment(valid) == []


def test_private_deployment_rejects_placeholder_and_weak_admin_values():
    from scripts.private_deploy_check import validate_private_environment

    values = {
        "TA_ADMIN_USERNAME": "owner",
        "TA_ADMIN_PASSWORD": "admin123",
        "DEEPSEEK_API_KEY": "",
        "OPENAI_API_KEY": "sk-your-key",
    }
    errors = validate_private_environment(values)

    assert any("管理员密码" in error for error in errors)
    assert any("模型 API Key" in error for error in errors)

    placeholder_password = {
        "TA_ADMIN_USERNAME": "owner",
        "TA_ADMIN_PASSWORD": "replace-with-at-least-12-random-characters",
        "DEEPSEEK_API_KEY": "configured-secret",
    }
    assert validate_private_environment(placeholder_password)


def test_private_compose_runs_web_with_healthcheck_and_xsrf():
    compose = (ROOT / "docker-compose.private.yml").read_text(encoding="utf-8")

    assert "streamlit" in compose
    assert "0.0.0.0" in compose
    assert "8501:8501" in compose
    assert "enableXsrfProtection=true" in compose
    assert "_stcore/health" in compose
    assert "restart: unless-stopped" in compose
    assert "TA_ENV_FILE" in compose


def test_private_env_files_are_excluded_from_docker_build_context():
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".env*" in dockerignore


def test_private_start_script_is_ascii_for_windows_powershell_51():
    script = (ROOT / "scripts" / "start_private.ps1").read_text(encoding="utf-8")

    assert script.isascii()


def test_private_service_docs_and_support_entry_exist():
    deployment_doc = ROOT / "docs" / "PRIVATE_DEPLOYMENT.md"
    agent_brief = ROOT / "docs" / "CUSTOM_AGENT_BRIEF.md"
    support_page = (ROOT / "web" / "pages" / "12_Support_Open_Source.py").read_text(encoding="utf-8")

    assert deployment_doc.exists()
    assert agent_brief.exists()
    assert "验收标准" in deployment_doc.read_text(encoding="utf-8")
    assert "数据与工具" in agent_brief.read_text(encoding="utf-8")
    assert "PRIVATE_DEPLOYMENT.md" in support_page
    assert "TA_ENTERPRISE_CONTACT" in support_page

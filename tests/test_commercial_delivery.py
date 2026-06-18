from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_support_page_exposes_open_source_plan_and_safe_contact_fallback():
    page = ROOT / "web" / "pages" / "12_Support_Open_Source.py"

    assert page.exists()
    text = page.read_text(encoding="utf-8")
    assert "支持开源计划" in text
    assert "社区版" in text
    assert "支持者版" in text
    assert "Pro 版" in text
    assert "私有部署" in text
    assert "TA_SUPPORT_CONTACT" in text
    assert "TA_SPONSOR_QR_ENABLED" in text
    assert "wechat-sponsor.jpg" in text
    assert "购买入口尚未配置" in text
    assert "不构成证券投资咨询" in text
    assert "check_for_update" in text
    assert "TA_UPDATE_MANIFEST_URL" in text
    assert "SHA-256" in text


def test_sidebar_and_readme_link_to_support_plan():
    sidebar = (ROOT / "web" / "components" / "sidebar.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "pages/12_Support_Open_Source.py" in sidebar
    assert "支持开源计划" in readme
    assert "支持者版" in readme
    assert "Pro 版" in readme


def test_activation_page_does_not_advertise_conflicting_legacy_prices():
    page = (ROOT / "web" / "pages" / "activate.py").read_text(encoding="utf-8")

    assert "¥99 / 月" not in page
    assert "永久买断" not in page
    assert "pages/12_Support_Open_Source.py" in page


def test_email_templates_use_configured_support_contact_without_legacy_branding():
    service = (ROOT / "tradingagents" / "auth" / "email_service.py").read_text(
        encoding="utf-8"
    )

    assert "TA_SUPPORT_CONTACT" in service
    assert "agu_quant" not in service
    assert "zzwl.asia" not in service
    assert "299元（永久）" not in service


def test_release_manifest_prefers_configured_mirror_and_validates_hash():
    from tradingagents.release_update import manifest_sources, parse_release_manifest

    sources = manifest_sources("https://mirror.example.com/releases/release-manifest.json")
    assert sources[0].startswith("https://mirror.example.com/")
    assert "github.com" in sources[1]

    artifact = parse_release_manifest(
        {
            "schema_version": 1,
            "version": "0.3.0",
            "artifacts": {
                "windows-x64": {
                    "filename": "TradingAgents-Astock-0.3.0-windows-x64.zip",
                    "sha256": "a" * 64,
                    "urls": [
                        "https://mirror.example.com/TradingAgents-Astock.zip",
                        "https://github.com/simonlin1212/TradingAgents-astock/releases/download/v0.3.0/TradingAgents-Astock.zip",
                    ],
                }
            },
        }
    )

    assert artifact.version == "0.3.0"
    assert artifact.urls[0].startswith("https://mirror.example.com/")
    assert artifact.sha256 == "a" * 64


def test_release_manifest_rejects_insecure_or_malformed_downloads():
    from tradingagents.release_update import parse_release_manifest

    with pytest.raises(ValueError, match="HTTPS"):
        parse_release_manifest(
            {
                "schema_version": 1,
                "version": "0.3.0",
                "artifacts": {
                    "windows-x64": {
                        "filename": "release.zip",
                        "sha256": "b" * 64,
                        "urls": ["http://mirror.example.com/release.zip"],
                    }
                },
            }
        )


def test_release_version_and_checksum_helpers(tmp_path):
    from tradingagents.release_update import is_newer_version, verify_sha256

    artifact = tmp_path / "release.zip"
    artifact.write_bytes(b"verified release")

    assert is_newer_version("0.3.0", "0.2.7")
    assert not is_newer_version("0.2.7", "0.2.7")
    assert verify_sha256(artifact, "1ce4572138ddacf54f7b7834f96aef9b61cc975676daa26fef2fbdf5c7a2d4bf")
    assert not verify_sha256(artifact, "0" * 64)


def test_stale_mirror_manifest_falls_back_to_newer_github_release(monkeypatch):
    from tradingagents.release_update import check_for_update

    class FakeResponse:
        def __init__(self, version):
            self.version = version

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "schema_version": 1,
                "version": self.version,
                "artifacts": {
                    "windows-x64": {
                        "filename": f"TradingAgents-Astock-{self.version}-windows-x64.zip",
                        "sha256": "c" * 64,
                        "urls": [f"https://downloads.example.com/{self.version}.zip"],
                    }
                },
            }

    responses = iter([FakeResponse("0.2.7"), FakeResponse("0.3.0")])
    monkeypatch.setattr(
        "tradingagents.release_update.requests.get",
        lambda *_args, **_kwargs: next(responses),
    )

    artifact = check_for_update(
        "0.2.7",
        configured_url="https://mirror.example.com/release-manifest.json",
    )

    assert artifact is not None
    assert artifact.version == "0.3.0"


def test_windows_launcher_supports_frozen_child_mode_without_disabling_xsrf():
    launcher = (ROOT / "launcher.py").read_text(encoding="utf-8")

    assert "--streamlit-child" in launcher
    assert 'if __name__ == "__main__"' in launcher
    assert "--server.address" in launcher
    assert "127.0.0.1" in launcher
    assert "enableXsrfProtection" not in launcher


def test_windows_release_automation_and_mirror_hooks_exist():
    build_script = ROOT / "scripts" / "build_windows.ps1"
    manifest_script = ROOT / "scripts" / "release_manifest.py"
    workflow = ROOT / ".github" / "workflows" / "windows-release.yml"

    assert build_script.exists()
    assert manifest_script.exists()
    assert workflow.exists()
    workflow_text = workflow.read_text(encoding="utf-8")
    assert "windows-latest" in workflow_text
    assert "MIRROR_ENDPOINT" in workflow_text
    assert "release-manifest.json" in workflow_text


def test_windows_manual_release_uses_project_version_and_packages_scheduler():
    workflow = (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(
        encoding="utf-8"
    )
    build_script = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")

    assert "github.ref_type" in workflow
    assert "scripts\\install_daily_task.ps1" in build_script
    assert '$PackageDir "scripts"' in build_script
    assert build_script.isascii()

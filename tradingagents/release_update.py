"""Verified release discovery and download for official desktop builds."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


GITHUB_MANIFEST_URL = (
    "https://github.com/simonlin1212/TradingAgents-astock/"
    "releases/latest/download/release-manifest.json"
)
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ReleaseArtifact:
    version: str
    filename: str
    sha256: str
    urls: tuple[str, ...]


def _require_https(url: str) -> str:
    value = str(url or "").strip()
    if not value.lower().startswith("https://"):
        raise ValueError("更新地址必须使用 HTTPS")
    return value


def manifest_sources(configured_url: str | None = None) -> tuple[str, ...]:
    """Return mirror-first manifest URLs with the GitHub fallback."""
    configured = configured_url
    if configured is None:
        configured = os.getenv("TA_UPDATE_MANIFEST_URL", "")

    sources: list[str] = []
    if str(configured or "").strip():
        sources.append(_require_https(str(configured)))
    if GITHUB_MANIFEST_URL not in sources:
        sources.append(GITHUB_MANIFEST_URL)
    return tuple(sources)


def parse_release_manifest(data: dict[str, Any]) -> ReleaseArtifact:
    if data.get("schema_version") != 1:
        raise ValueError("不支持的更新清单版本")

    version = str(data.get("version", "")).strip()
    if not _VERSION_RE.fullmatch(version):
        raise ValueError("更新版本号无效")

    artifacts = data.get("artifacts")
    artifact = artifacts.get("windows-x64") if isinstance(artifacts, dict) else None
    if not isinstance(artifact, dict):
        raise ValueError("更新清单缺少 Windows 构建")

    filename = str(artifact.get("filename", "")).strip()
    if not filename or Path(filename).name != filename or not filename.lower().endswith(".zip"):
        raise ValueError("更新文件名无效")

    sha256 = str(artifact.get("sha256", "")).strip().lower()
    if not _SHA256_RE.fullmatch(sha256):
        raise ValueError("更新文件 SHA-256 无效")

    raw_urls = artifact.get("urls")
    if not isinstance(raw_urls, list) or not raw_urls:
        raise ValueError("更新清单缺少下载地址")
    urls = tuple(dict.fromkeys(_require_https(url) for url in raw_urls))

    return ReleaseArtifact(version=version, filename=filename, sha256=sha256, urls=urls)


def _version_tuple(version: str) -> tuple[int, int, int]:
    match = _VERSION_RE.fullmatch(str(version or "").strip())
    if not match:
        raise ValueError("版本号必须使用 major.minor.patch 格式")
    return tuple(int(part) for part in match.groups())


def is_newer_version(candidate: str, current: str) -> bool:
    return _version_tuple(candidate) > _version_tuple(current)


def verify_sha256(path: str | Path, expected: str) -> bool:
    expected_value = str(expected or "").strip().lower()
    if not _SHA256_RE.fullmatch(expected_value):
        return False

    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest() == expected_value


def check_for_update(
    current_version: str,
    configured_url: str | None = None,
    timeout: float = 8.0,
) -> ReleaseArtifact | None:
    """Check mirror then GitHub; return only a newer verified manifest."""
    failures: list[str] = []
    newest: ReleaseArtifact | None = None
    found_valid_manifest = False
    for source in manifest_sources(configured_url):
        try:
            response = requests.get(source, timeout=timeout)
            response.raise_for_status()
            artifact = parse_release_manifest(response.json())
            found_valid_manifest = True
            if is_newer_version(artifact.version, current_version) and (
                newest is None or is_newer_version(artifact.version, newest.version)
            ):
                newest = artifact
        except (requests.RequestException, ValueError, TypeError) as exc:
            failures.append(f"{source}: {exc}")
    if newest is not None:
        return newest
    if found_valid_manifest:
        return None
    raise RuntimeError("无法获取有效更新清单；" + "；".join(failures))


def download_release(
    artifact: ReleaseArtifact,
    target_dir: str | Path,
    timeout: float = 60.0,
) -> Path:
    """Download from mirror/fallback URLs and keep only a matching artifact."""
    destination_dir = Path(target_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / artifact.filename
    partial = destination.with_suffix(destination.suffix + ".part")
    failures: list[str] = []

    for url in artifact.urls:
        try:
            with requests.get(url, stream=True, timeout=timeout) as response:
                response.raise_for_status()
                with partial.open("wb") as output:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            output.write(chunk)
            if not verify_sha256(partial, artifact.sha256):
                raise ValueError("SHA-256 校验失败")
            partial.replace(destination)
            return destination
        except (requests.RequestException, OSError, ValueError) as exc:
            partial.unlink(missing_ok=True)
            failures.append(f"{url}: {exc}")

    raise RuntimeError("更新包下载失败；" + "；".join(failures))

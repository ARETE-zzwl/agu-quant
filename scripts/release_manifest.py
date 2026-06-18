"""Create a signed-by-hash release manifest for desktop artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_url(base_url: str, filename: str) -> str:
    value = str(base_url or "").strip().rstrip("/")
    if not value:
        return ""
    if not value.lower().startswith("https://"):
        raise ValueError("发布地址必须使用 HTTPS")
    return f"{value}/{filename}"


def build_manifest(
    artifact: Path,
    version: str,
    github_base_url: str,
    mirror_base_url: str = "",
) -> dict:
    urls = [
        url
        for url in (
            _artifact_url(mirror_base_url, artifact.name),
            _artifact_url(github_base_url, artifact.name),
        )
        if url
    ]
    return {
        "schema_version": 1,
        "version": version,
        "artifacts": {
            "windows-x64": {
                "filename": artifact.name,
                "sha256": _sha256(artifact),
                "urls": urls,
            }
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--github-base-url", required=True)
    parser.add_argument("--mirror-base-url", default="")
    parser.add_argument("--output", type=Path, default=Path("dist/release-manifest.json"))
    args = parser.parse_args()

    manifest = build_manifest(
        args.artifact,
        args.version,
        args.github_base_url,
        args.mirror_base_url,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

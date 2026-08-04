#!/usr/bin/env python3
"""Shared release-version and archive-naming helpers.

The root VERSION file is the only source of the distributable release version.
The case/package schema has its own lifecycle and intentionally remains 0.1.0.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


VERSION_PATTERN = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z")


def release_version(repo: Path) -> str:
    value = (repo / "VERSION").read_text(encoding="utf-8").strip()
    if not VERSION_PATTERN.fullmatch(value):
        raise ValueError(f"VERSION must contain one stable SemVer value, got {value!r}")
    return value


def release_names(repo: Path) -> dict[str, str]:
    version = release_version(repo)
    return {
        "version": version,
        "tag": f"v{version}",
        "release_directory": f"v{version}",
        "source_prefix": f"evidence-first-patent-skill-v{version}",
        "source_archive": f"evidence-first-patent-skill-v{version}.zip",
        "skill_prefix": "draft-patents-evidence-first",
        "skill_archive": f"draft-patents-evidence-first-v{version}.zip",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve release names from the root VERSION file")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument(
        "--format",
        choices=("version", "tag", "release-directory", "source-prefix", "source-archive", "skill-prefix", "skill-archive"),
        default="version",
    )
    args = parser.parse_args()
    key = args.format.replace("-", "_")
    print(release_names(args.repo.resolve())[key])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

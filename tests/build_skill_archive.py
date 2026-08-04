#!/usr/bin/env python3
"""Create a deterministic, install-ready archive containing only the Skill."""
from __future__ import annotations

import argparse
import subprocess
import zipfile
from pathlib import Path

from release_common import release_names


SKILL_RELATIVE = Path("skill/draft-patents-evidence-first")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo, output = args.repo.resolve(), args.output.resolve()
    names = release_names(repo)
    skill_root = repo / SKILL_RELATIVE
    if not (skill_root / "SKILL.md").is_file():
        raise FileNotFoundError(f"Skill root is incomplete: {skill_root}")
    selection = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    files = sorted(
        repo / Path(raw.decode("utf-8"))
        for raw in selection.stdout.split(b"\0")
        if raw and Path(raw.decode("utf-8")).is_relative_to(SKILL_RELATIVE)
    )
    files = [path for path in files if path.is_file()]
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in files:
            relative = source.relative_to(skill_root).as_posix()
            member = f"{names['skill_prefix']}/{relative}"
            info = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.flag_bits |= 0x800
            archive.writestr(info, source.read_bytes())
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("skill archive CRC check failed")
    print(f"Created {output.name} with {len(files)} install-ready Skill files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

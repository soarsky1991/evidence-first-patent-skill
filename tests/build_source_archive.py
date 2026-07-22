#!/usr/bin/env python3
"""Create a deterministic source archive from the public Git candidate file set."""
from __future__ import annotations

import argparse
import subprocess
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prefix", default="evidence-first-patent-skill-v0.1.0")
    args = parser.parse_args()
    repo, output = args.repo.resolve(), args.output.resolve()
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    files = sorted(Path(raw.decode("utf-8")) for raw in result.stdout.split(b"\0") if raw)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in files:
            source = repo / relative
            if not source.is_file():
                continue
            info = zipfile.ZipInfo(f"{args.prefix}/{relative.as_posix()}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.flag_bits |= 0x800
            archive.writestr(info, source.read_bytes())
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("source archive CRC check failed")
    print(f"Created {output.name} with {len(files)} public candidate files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

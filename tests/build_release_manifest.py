#!/usr/bin/env python3
"""Write v0.1.0 source/artifact hashes without making a publication decision."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo, release, output = args.repo.resolve(), args.release.resolve(), args.output.resolve()
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    source_paths = sorted(Path(raw.decode("utf-8")) for raw in result.stdout.split(b"\0") if raw)
    source_records = [
        {"path": path.as_posix(), "sha256": digest(repo / path), "bytes": (repo / path).stat().st_size}
        for path in source_paths if (repo / path).is_file()
    ]
    candidate_material = "".join(f"{item['sha256']}  {item['path']}\n" for item in source_records).encode("utf-8")
    asset_paths = sorted(
        path for path in release.iterdir()
        if path.is_file() and path.name not in {"SHA256SUMS.txt", output.name}
    )
    asset_records = [
        {"path": path.name, "sha256": digest(path), "bytes": path.stat().st_size}
        for path in asset_paths
    ]
    payload = {
        "schema_version": "0.1.0",
        "candidate_content_sha256": hashlib.sha256(candidate_material).hexdigest(),
        "source_files": source_records,
        "release_assets": asset_records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sums = [f"{item['sha256']}  {item['path']}" for item in asset_records]
    sums.append(f"{digest(output)}  {output.name}")
    (release / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_content_sha256": payload["candidate_content_sha256"], "source_files": len(source_records), "release_assets": len(asset_records)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

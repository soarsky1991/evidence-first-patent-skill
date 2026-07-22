#!/usr/bin/env python3
"""Verify a freshly rebuilt release tree without modifying it."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
import stat
from pathlib import Path, PurePosixPath


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def index_records(rows: object, label: str, errors: list[str]) -> dict[str, dict[str, object]]:
    if not isinstance(rows, list):
        errors.append(f"{label} is not a list")
        return {}
    records: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            errors.append(f"{label} contains an invalid record")
            continue
        name = row["path"]
        if name in records:
            errors.append(f"{label} contains duplicate path {name}")
            continue
        if not isinstance(row.get("bytes"), int) or not isinstance(row.get("sha256"), str):
            errors.append(f"{label} record lacks bytes/SHA-256 for {name}")
            continue
        records[name] = row
    return records


def verify_file(path: Path, record: dict[str, object], label: str, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"{label} is missing: {path.name}")
        return
    payload = path.read_bytes()
    if len(payload) != record["bytes"]:
        errors.append(f"{label} size mismatch: {path.name}")
    if digest(payload) != record["sha256"]:
        errors.append(f"{label} SHA-256 mismatch: {path.name}")


def safe_extract(archive: zipfile.ZipFile, target: Path) -> None:
    """Materialize only ordinary, relative ZIP members for the package smoke test."""
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    for info in archive.infolist():
        member = PurePosixPath(info.filename.replace("\\", "/"))
        if not info.filename or info.filename.startswith("/") or ".." in member.parts or (member.parts and ":" in member.parts[0]):
            raise ValueError(f"unsafe member {info.filename}")
        if stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError(f"symlink member {info.filename}")
        destination = (target / Path(*member.parts)).resolve()
        try:
            destination.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"member escapes root {info.filename}") from exc
        if info.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, destination.open("wb") as sink:
            sink.write(source.read())


def verify_public_sample_archive(path: Path, repo: Path, errors: list[str]) -> None:
    required = {"case.yaml", "LICENSE-DOCS", "NOTICE", "REDISTRIBUTION.md", "input/source.md", "work/sources.jsonl", "manifest.json"}
    try:
        with zipfile.ZipFile(path) as archive:
            names = Counter(info.filename for info in archive.infolist())
            missing = sorted(required - set(names))
            duplicates = sorted(name for name, count in names.items() if count > 1)
            if missing:
                errors.append(f"sample archive lacks redistribution/source files in {path.name}: {missing}")
            if duplicates:
                errors.append(f"sample archive has duplicate members in {path.name}: {duplicates}")
            if not missing:
                sources = [json.loads(line) for line in archive.read("work/sources.jsonl").decode("utf-8").splitlines() if line]
                for source in sources:
                    locator = source.get("locator")
                    expected = source.get("sha256")
                    if not isinstance(locator, str) or "://" in locator or expected is None:
                        continue
                    if names.get(locator) != 1:
                        errors.append(f"sample source locator is unresolved in {path.name}: {locator}")
                        continue
                    if digest(archive.read(locator)) != expected:
                        errors.append(f"sample source hash mismatch in {path.name}: {locator}")
            if not missing and not duplicates:
                with tempfile.TemporaryDirectory(prefix="efps-release-sample-") as temporary:
                    extracted = Path(temporary) / "case"
                    safe_extract(archive, extracted)
                    validator = repo / "skill/draft-patents-evidence-first/scripts/validate_case.py"
                    builder = repo / "skill/draft-patents-evidence-first/scripts/build_package.py"
                    validate = subprocess.run([sys.executable, str(validator), str(extracted)], text=True, capture_output=True)
                    if validate.returncode:
                        errors.append(f"sample ZIP does not validate as an extracted case {path.name}: {(validate.stderr or validate.stdout).strip()}")
                    rebuilt = Path(temporary) / "rebuilt"
                    rebuild = subprocess.run([sys.executable, str(builder), str(extracted), "--format", "md", "--output", str(rebuilt)], text=True, capture_output=True)
                    if rebuild.returncode:
                        errors.append(f"sample ZIP does not rebuild as an extracted case {path.name}: {(rebuild.stderr or rebuild.stdout).strip()}")
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid public sample archive {path.name}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--prefix", default="evidence-first-patent-skill-v0.1.0")
    args = parser.parse_args()
    repo, release = args.repo.resolve(), args.release.resolve()
    manifest_path, source_archive = args.manifest.resolve(), args.source_archive.resolve()
    errors: list[str] = []

    try:
        manifest_payload = manifest_path.read_bytes()
        manifest = json.loads(manifest_payload)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read release manifest: {exc}", file=sys.stderr)
        return 2

    source_records = index_records(manifest.get("source_files"), "source_files", errors)
    asset_records = index_records(manifest.get("release_assets"), "release_assets", errors)

    selection = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=repo,
        capture_output=True,
    )
    if selection.returncode:
        print("ERROR: git public-candidate selection failed", file=sys.stderr)
        return 2
    candidate_paths = sorted(raw.decode("utf-8") for raw in selection.stdout.split(b"\0") if raw)
    if set(candidate_paths) != set(source_records):
        errors.append("release manifest source_files differ from Git public-candidate set")
    for name, record in source_records.items():
        verify_file(repo / name, record, "source file", errors)
    candidate_material = "".join(
        f"{source_records[name]['sha256']}  {name}\n" for name in sorted(source_records)
    ).encode("utf-8")
    if digest(candidate_material) != manifest.get("candidate_content_sha256"):
        errors.append("candidate_content_sha256 mismatch")

    actual_assets = {
        path.name for path in release.iterdir()
        if path.is_file() and path.name not in {"SHA256SUMS.txt", manifest_path.name}
    }
    if actual_assets != set(asset_records):
        errors.append("release asset set differs from release manifest")
    for name, record in asset_records.items():
        verify_file(release / name, record, "release asset", errors)
    for sample_name in ("BI-PAIR-09.zip", "ZH-INV-01.zip"):
        verify_public_sample_archive(release / sample_name, repo, errors)

    try:
        lines = [line for line in (release / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines() if line]
        pairs = [line.split("  ", 1) for line in lines]
        sums = {name: checksum for checksum, name in pairs}
    except (OSError, ValueError) as exc:
        errors.append(f"invalid SHA256SUMS.txt: {exc}")
        sums = {}
    expected_sums = {name: str(record["sha256"]) for name, record in asset_records.items()}
    expected_sums[manifest_path.name] = digest(manifest_payload)
    if sums != expected_sums or len(lines) != len(expected_sums):
        errors.append("SHA256SUMS.txt differs from release manifest/assets")

    try:
        with zipfile.ZipFile(source_archive) as archive:
            infos = archive.infolist()
            counts = Counter(info.filename for info in infos)
            duplicates = sorted(name for name, count in counts.items() if count > 1)
            if duplicates:
                errors.append(f"source archive has duplicate members: {duplicates}")
            expected_members = {f"{args.prefix}/{name}" for name in source_records}
            if set(counts) != expected_members:
                errors.append("source archive membership differs from source_files")
            bad = archive.testzip()
            if bad:
                errors.append(f"source archive CRC failure: {bad}")
            for name, record in source_records.items():
                member = f"{args.prefix}/{name}"
                if counts.get(member) != 1:
                    continue
                info = archive.getinfo(member)
                payload = archive.read(info)
                if info.file_size != record["bytes"]:
                    errors.append(f"source archive size mismatch: {name}")
                if digest(payload) != record["sha256"]:
                    errors.append(f"source archive SHA-256 mismatch: {name}")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"invalid source archive: {exc}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps({
        "status": "PASS",
        "source_files": len(source_records),
        "release_assets": len(asset_records),
        "release_manifest_sha256": digest(manifest_payload),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

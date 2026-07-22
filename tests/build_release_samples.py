#!/usr/bin/env python3
"""Build the two synthetic rendered samples used by the v0.1.0 release gate."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def load_acceptance(repo: Path):
    scripts = repo / "skill/draft-patents-evidence-first/scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("run_acceptance", scripts / "run_acceptance.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_builder(repo: Path):
    scripts = repo / "skill/draft-patents-evidence-first/scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("build_package", scripts / "build_package.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def add_public_redistribution_files(repo: Path, case: Path, package: Path, builder: object) -> None:
    """Make the synthetic download independently auditable and licensable.

    General case packages intentionally exclude source inputs.  These two release
    fixtures are synthetic and public, so their declared locator and source hash must
    remain resolvable after the ZIP is downloaded separately from the repository.
    """
    if not (package / "case.yaml").is_file() or not (package / "input" / "source.md").is_file():
        raise RuntimeError("portable package is missing canonical case.yaml or referenced synthetic source")
    shutil.copy2(repo / "LICENSE-DOCS", package / "LICENSE-DOCS")
    shutil.copy2(repo / "NOTICE", package / "NOTICE")
    (package / "REDISTRIBUTION.md").write_text(
        "# Synthetic sample redistribution / 合成样例再分发\n\n"
        "This package contains only synthetic source material and repository-original "
        "content. Narrative content is distributed under CC BY 4.0 as described in "
        "LICENSE-DOCS and NOTICE. No third-party photograph or client material is included.\n\n"
        "本包只包含合成来源材料和仓库原创内容。叙事性内容依 LICENSE-DOCS 与 NOTICE "
        "所述的 CC BY 4.0 分发；包内不含第三方照片或客户材料。\n",
        encoding="utf-8",
    )
    manifest = builder.write_manifest(package)
    archive = package.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            zipped.write(path, path.relative_to(package).as_posix())
    builder.verify_archive(archive, package, manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    acceptance = load_acceptance(repo)
    builder = load_builder(repo)
    scripts = repo / "skill/draft-patents-evidence-first/scripts"
    fixtures = {fixture: acceptance.fixture_yaml(repo / "tests/fixtures" / fixture / "fixture.yaml") for fixture in ("ZH-INV-01", "BI-PAIR-09")}
    for fixture_id, fixture in fixtures.items():
        case = acceptance.make_base_case(output / "cases", fixture, bilingual=fixture["language"] == "bilingual")
        package = output / fixture_id
        result = subprocess.run(
            [sys.executable, str(scripts / "build_package.py"), str(case), "--format", "all", "--output", str(package)],
            cwd=repo,
            text=True,
            capture_output=True,
        )
        if result.returncode:
            print(result.stderr or result.stdout, file=sys.stderr)
            return result.returncode
        add_public_redistribution_files(repo, case, package, builder)
        shutil.rmtree(case)
        (output / "cases").rmdir()
        for source_name, release_name in (
            ("package.docx", f"{fixture_id}.docx"),
            ("package.pdf", f"{fixture_id}.pdf"),
            ("manifest.json", f"{fixture_id}-manifest.json"),
        ):
            shutil.copy2(package / source_name, output.parent / release_name)
        shutil.copy2(package.with_suffix(".zip"), output.parent / f"{fixture_id}.zip")
    sums = []
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        sums.append(f"{digest}  {path.relative_to(output).as_posix()}")
    (output / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "samples": sorted(fixtures), "files": len(sums)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

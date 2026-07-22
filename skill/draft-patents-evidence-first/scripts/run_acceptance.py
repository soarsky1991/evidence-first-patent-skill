#!/usr/bin/env python3
"""Deterministic, evidence-bearing acceptance aggregation for v0.1.0.

The fixture matrix is executed, not merely enumerated.  This command deliberately never
sets the Sol-V terminal state and never performs a network or publishing operation.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
import re
import shlex
import stat
import struct
import zlib
from pathlib import Path, PurePosixPath
from typing import Any

from evidence_first_lib import (
    FULL_LEGAL_DISCLAIMER_EN, FULL_LEGAL_DISCLAIMER_ZH, SCHEMA_VERSION, case_paths,
    dump_case_yaml, dump_json, dump_jsonl, load_case_yaml, now, sensitive_findings,
    refresh_complete_stage_hashes, reset_downstream_stages,
)
from inspect_artifacts import InspectorError, inspect
from validate_case import statement_inventory

EXPECTED_FIXTURES = {
    "ZH-INV-01", "ZH-UM-02", "ZH-CONFLICT-03", "ZH-SECRET-04", "EN-INV-05", "EN-UM-06",
    "EN-CONFLICT-07", "EN-SECRET-08", "BI-PAIR-09", "BI-DRIFT-10", "AUTO-ZH-11",
    "AUTO-EN-12", "DATE-13", "GATE-14", "STALE-15", "MEDIA-16",
}
POSITIVE_FIXTURES = {"ZH-INV-01", "ZH-UM-02", "EN-INV-05", "EN-UM-06", "EN-CONFLICT-07", "BI-PAIR-09", "AUTO-ZH-11", "AUTO-EN-12", "DATE-13"}
REQUIRED_FIXTURE_FIELDS = {"id", "language", "patent_type", "kind", "scenario", "expected"}


def portable(text: str, cwd: Path) -> str:
    text = text.replace(str(cwd), ".").replace(str(Path.home()), "~")
    return re.sub(r"/(?:private/)?var/folders/[^\s\"']+", "<temp>", text)


def exact_public_candidate_scan(repo: Path, report: Path) -> dict[str, Any]:
    """Scan only the release candidate set, then the generated report and dist assets.

    ``.workflow/reviews`` is intentionally not special-cased here: it is excluded by
    the repository's ordinary git candidate selection, which keeps review diagnostics
    out of the public release without weakening the scanner's own ignore rules.
    """
    listing = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=repo, text=True, capture_output=True)
    if listing.returncode:
        return {"exit_code": 2, "stderr": "git ls-files public-candidate selection failed", "stdout": "", "candidate_count": 0, "review_paths_naturally_excluded": False}
    candidates = [repo / line for line in listing.stdout.splitlines() if line]
    dist = repo / "dist"
    extras = [report] + (sorted(path for path in dist.rglob("*") if path.is_file()) if dist.exists() else [])
    unique: list[Path] = []
    for path in candidates + extras:
        if path.is_file() and path not in unique:
            unique.append(path)
    findings: list[dict[str, Any]] = []
    for path in unique:
        for finding in sensitive_findings(path):
            finding = dict(finding)
            try:
                finding["path"] = Path(finding["path"]).resolve().relative_to(repo).as_posix()
            except ValueError:
                finding["path"] = Path(finding["path"]).name
            findings.append(finding)
    review = repo / ".workflow" / "reviews"
    review_paths = list(review.rglob("*")) if review.exists() else []
    candidate_set = {path.resolve() for path in candidates}
    review_excluded = all(not path.is_file() or path.resolve() not in candidate_set for path in review_paths)
    return {
        "exit_code": 1 if findings else 0,
        "stderr": "",
        "stdout": json.dumps({"findings": findings, "candidate_count": len(candidates), "report_included": report.is_file(), "dist_asset_count": len(extras) - 1, "workflow_reviews_naturally_excluded": review_excluded}, ensure_ascii=False),
        "candidate_count": len(candidates),
        "review_paths_naturally_excluded": review_excluded,
    }


def run(cmd: list[str], cwd: Path, display: list[str] | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    process = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, env=env)
    return {"command": display or cmd, "exit_code": process.returncode, "stdout": portable(process.stdout, cwd), "stderr": portable(process.stderr, cwd)}


def fixture_yaml(path: Path) -> dict[str, Any]:
    """Parse the flat, repository-controlled fixture metadata without a YAML dependency."""
    result: dict[str, Any] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith((" ", "\t")) or ":" not in raw:
            raise ValueError(f"unsupported fixture YAML line: {raw}")
        key, value = raw.split(":", 1)
        result[key.strip()] = value.strip().strip("\"").strip("'")
    return result


def write_synthetic_figure_png(path: Path) -> None:
    """Write a small metadata-free RGB figure using only the standard library."""
    width, height = 720, 220
    pixels = [[(250, 248, 242) for _ in range(width)] for _ in range(height)]
    def fill(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
        for y in range(max(0, y0), min(height, y1)):
            for x in range(max(0, x0), min(width, x1)):
                pixels[y][x] = color
    fill(80, 150, 640, 168, (92, 111, 115))
    fill(130, 75, 166, 150, (42, 157, 143)); fill(554, 75, 590, 150, (42, 157, 143))
    for x in range(155, 566):
        ratio = (x - 360) / 205
        y = round(90 - 55 * (1 - ratio * ratio))
        fill(x, y - 5, x + 1, y + 6, (233, 162, 59))
    raw = b"".join(b"\x00" + bytes(channel for pixel in row for channel in pixel) for row in pixels)
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def make_base_case(root: Path, fixture: dict[str, Any], bilingual: bool = False) -> Path:
    """Create a synthetic, fully local case used only inside a temporary test directory."""
    case = root / fixture["id"].lower()
    paths = case_paths(case)
    case.mkdir(parents=True); paths["input"].mkdir(); paths["output"].mkdir(); paths["package"].mkdir(); paths["sources"].parent.mkdir()
    language = fixture["language"]
    config = {
        "schema_version": SCHEMA_VERSION, "case_id": fixture["id"].lower(), "language": language,
        "jurisdiction": "CN", "patent_type": fixture["patent_type"], "critical_date": "2024-01-01",
        "priority_claimed": False, "confidentiality_mode": "local_only",
        "human_gate": {"selected_concept_id": "CON-0001", "approved_by": "reviewer", "approved_at": "2026-01-01T00:00:00Z", "public_boundary_confirmed": True},
    }
    dump_case_yaml(paths["case"], config)
    source_file = paths["input"] / "source.md"
    fid = fixture["id"]
    source_text = "Synthetic source: proposed resilient pressing structure with a 10 mm spacing target; no measurement.\n"
    source_language = "zh-CN" if language == "zh-CN" else "en-US"
    if fid == "ZH-INV-01":
        source_text = "工程说明：一种夹具包括弹性压持结构且间距为10 mm；未提供试验方法、样本或测量值。\n"
        source_language = "zh-CN"
    elif fid == "ZH-UM-02":
        source_text = "操作说明：将试件放入夹具后加热，并记录温度；该说明采用方法式语言。\n"
        source_language = "zh-CN"
    elif fid == "AUTO-ZH-11":
        source_text = "English-heavy input: fixture fixture support support pressing member spacing target; no measurement.\n"
        source_language = "en-US"
    elif fid == "AUTO-EN-12":
        source_text = "中文输入占多数：夹具、支承件、弹性压持件、间距目标、尚未测量。\n"
        source_language = "zh-CN"
    source_file.write_text(source_text, encoding="utf-8")
    source = {"source_id":"SRC-0001","source_type":"synthetic","title":"Synthetic workflow source","locator":"input/source.md","sha256":hashlib.sha256(source_file.read_bytes()).hexdigest(),"publication_date":None,"accessed_at":None,"family_id":None,"license":"CC BY 4.0","language":source_language,"public_status":"synthetic","verification_status":"verified"}
    documented = fid == "ZH-INV-01"
    canonical_statement = (
        "一种夹具包括弹性压持结构且间距为10 mm。 / "
        "A fixture comprising a resilient pressing structure with a spacing of 10 mm."
        if bilingual else (
            "一种夹具包括弹性压持结构且间距为10 mm。"
            if (fixture.get("controlling_request_language") if language == "auto" else language) == "zh-CN"
            else "A fixture comprising a resilient pressing structure with a spacing of 10 mm."
        )
    )
    evidence = {"evidence_id":"EV-0001","source_id":"SRC-0001","source_location":{"paragraph":"p1"},"verbatim":source_text.strip(),"statement":canonical_statement,"evidence_class":"documented" if documented else "designed","verification_status":"verified","public_status":"synthetic","derived_from":[],"review_notes":""}
    dump_jsonl(paths["sources"], [source]); dump_jsonl(paths["evidence"], [evidence])
    def row(num: int, limitation: str, lang: str, pair: str | None = None, status: str = "designed") -> dict[str, Any]:
        text = "一种包括弹性压持结构且间距为10 mm的夹具。" if lang == "zh-CN" else "A fixture comprising a resilient pressing structure with a spacing of 10 mm."
        surfaces = {
            "zh-CN": [("object", "fixture", "夹具"), ("component_or_step", "resilient_pressing_structure", "弹性压持结构"), ("relationship", "spacing", "间距"), ("numeric_bound", "10mm", "10 mm"), ("modality", "open", "包括")],
            "en-US": [("object", "fixture", "fixture"), ("component_or_step", "resilient_pressing_structure", "resilient pressing structure"), ("relationship", "spacing", "spacing"), ("numeric_bound", "10mm", "10 mm"), ("modality", "open", "comprising")],
        }
        return {"claim_id":f"CLM-{num:03d}","claim_number":num,"parent_claim_number":None,"limitation_id":limitation,"language":lang,"limitation_text":text,"limitation_text_sha256":hashlib.sha256(text.encode("utf-8")).hexdigest(),"atom_map":[{"type":kind,"canonical":canonical,"text_span":span} for kind,canonical,span in surfaces[lang]],"evidence_ids":["EV-0001"],"semantic_status":status,"human_review_status":"accepted","paired_limitation_id":pair}
    if bilingual:
        trace = [row(1,"LIM-0001","zh-CN","LIM-0002", "supported" if documented else "designed"), row(1,"LIM-0002","en-US","LIM-0001", "supported" if documented else "designed")]
    else:
        resolved = fixture.get("controlling_request_language") if language == "auto" else None
        trace = [row(1,"LIM-0001", resolved or ("zh-CN" if language == "zh-CN" else "en-US"), status="supported" if documented else "designed")]
    dump_jsonl(paths["trace"], trace)
    dump_json(paths["scorecard"], {"schema_version":SCHEMA_VERSION,"generated_at":now(),"evidence_coverage_pct":100.0,"unsupported_measured_claims":0,"duplicate_patent_families":0,"claim_trace_coverage_pct":100.0,"bilingual_atomic_consistency_pct":100.0 if bilingual else None,"confidentiality_findings":0,"blocking_findings":[],"status":"CANDIDATE_CHECKS_PASSED"})
    stages=[]
    for number in range(1,11): stages.append({"stage":number,"status":"pending","input_hash":None,"output_hash":None,"updated_at":now(),"blocking_reasons":[]})
    if language == "auto": stages[0]["resolved_language"] = fixture["controlling_request_language"]
    dump_json(paths["stages"], stages)
    assets = json.loads((Path(__file__).resolve().parents[3] / "tests" / "assets" / "release_sample_sections.json").read_text(encoding="utf-8"))
    # Auto mode promises one rendered output language.  Its language-routing
    # fixtures therefore use the traced claim alone rather than a bilingual sample
    # hand-off; the latter is exercised by BI-PAIR-09.
    if language == "auto":
        assets = {}
    assets["claims.md"] = "# Claim framework / 权利要求框架\n\n" + "\n".join(f"{row['claim_number']}. {row['limitation_text']}" for row in trace) + "\n"
    for name, text in assets.items(): (paths["output"] / name).write_text(text, encoding="utf-8")
    if language != "auto":
        write_synthetic_figure_png(paths["output"] / "figure-1.png")

    # The sample narrative intentionally includes verification boundaries,
    # disclaimers and risk language in addition to the single claim proposition.
    # Give every material synthetic statement its own local, verbatim evidence row
    # rather than faking a blanket 100% scorecard value.
    narrative = [row for row in statement_inventory(paths, trace) if not row["evidence_ids"]]
    if narrative:
        ledger = paths["input"] / "synthetic-narrative-evidence.md"
        ledger.write_text("\n".join(str(row["text"]) for row in narrative) + "\n", encoding="utf-8")
        narrative_source = {
            "source_id":"SRC-9001", "source_type":"synthetic", "title":"Synthetic narrative evidence ledger",
            "locator":"input/synthetic-narrative-evidence.md", "sha256":hashlib.sha256(ledger.read_bytes()).hexdigest(),
            "publication_date":None, "accessed_at":None, "family_id":None, "license":"CC BY 4.0",
            "language":"und", "public_status":"synthetic", "verification_status":"verified",
        }
        narrative_evidence = [
            {
                "evidence_id":f"EV-{9001 + index:04d}", "source_id":"SRC-9001",
                "source_location":{"paragraph":f"p{index + 1}"}, "verbatim":str(row["text"]),
                "statement":str(row["text"]), "evidence_class":"documented", "verification_status":"verified",
                "public_status":"synthetic", "derived_from":[], "review_notes":"",
            }
            for index, row in enumerate(narrative)
        ]
        dump_jsonl(paths["sources"], [source, narrative_source])
        dump_jsonl(paths["evidence"], [evidence, *narrative_evidence])
    refresh_stages(paths)
    return case


def refresh_stages(paths: dict[str, Path], *, complete_through: int = 10, resolved_language: str | None = None) -> None:
    """Refresh only lawful, content-bound fixture stage hashes after a deliberate mutation."""
    # The language resolution is part of stage one's canonical output and must be
    # persisted before calculating the fixture's stage chain.
    if resolved_language:
        existing = json.loads(paths["stages"].read_text(encoding="utf-8"))
        existing[0]["resolved_language"] = resolved_language
        dump_json(paths["stages"], existing)
    stages = refresh_complete_stage_hashes(paths, complete_through=complete_through)
    if resolved_language:
        stages[0]["resolved_language"] = resolved_language
    dump_json(paths["stages"], stages)


def call(script: Path, name: str, case: Path, *extra: str, env: dict[str, str] | None = None) -> dict[str, Any]:
    display_extra = ["OUTPUT" if Path(value).is_absolute() else value for value in extra]
    return run([sys.executable, str(script / name), str(case), *extra], script.parents[2], ["python", f"skill/draft-patents-evidence-first/scripts/{name}", "CASE", *display_extra], env)


def score(case: Path) -> dict[str, Any]:
    return json.loads((case / "work" / "scorecard.json").read_text(encoding="utf-8"))


def package_assertions(package: Path, trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate hashes, archive membership, and rendered claim text for release samples."""
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    records = {item["path"]: item for item in manifest["files"]}
    archive = package.with_suffix(".zip")
    with zipfile.ZipFile(archive) as zipped:
        archive_members = set(zipped.namelist())
        crc_ok = zipped.testzip() is None
        utf8_ok = all(item.filename.isascii() or item.flag_bits & 0x800 for item in zipped.infolist())
    expected_members = set(records) | {"manifest.json"}
    canonical = canonical_records(package)
    declared_canonical = manifest.get("case_package", {}).get("canonical_case_files", [])
    hashes_ok = all(
        (package / name).is_file()
        and hashlib.sha256((package / name).read_bytes()).hexdigest() == record["sha256"]
        for name, record in records.items()
    )
    with zipfile.ZipFile(package / "package.docx") as document:
        docx_is_ooxml = {"[Content_Types].xml", "word/document.xml"} <= set(document.namelist())
        document_xml = document.read("word/document.xml")
        docx_text = "".join(ET.fromstring(document_xml).itertext())
        docx_has_table = b"<w:tbl" in document_xml
        docx_has_image = any(name.startswith("word/media/") for name in document.namelist())
    pdf = package / "package.pdf"
    pdf_result = subprocess.run(["pdftotext", str(pdf), "-"], text=True, capture_output=True)
    compact_docx = re.sub(r"\s+", "", docx_text)
    compact_pdf = re.sub(r"\s+", "", pdf_result.stdout)
    compact_legal_en = re.sub(r"\s+", "", FULL_LEGAL_DISCLAIMER_EN)
    compact_legal_zh = re.sub(r"\s+", "", FULL_LEGAL_DISCLAIMER_ZH)
    expected_claims = [row["limitation_text"] for row in trace]
    expected_numbers = {str(row["claim_number"]) for row in trace}
    expected_numeric_limits = set()
    for text in expected_claims:
        expected_numeric_limits.update(re.findall(r"\d+(?:\.\d+)?\s*(?:mm|μm|um|℃|°C|%|MPa|N|s|min)", text, flags=re.I))
    stages = json.loads((package / "work" / "stage_status.json").read_text(encoding="utf-8"))
    complete_stage_chain = (
        isinstance(stages, list) and len(stages) == 10
        and all(row.get("stage") == index and row.get("status") == "complete"
                and isinstance(row.get("input_hash"), str) and re.fullmatch(r"[0-9a-f]{64}", row["input_hash"])
                and isinstance(row.get("output_hash"), str) and re.fullmatch(r"[0-9a-f]{64}", row["output_hash"])
                for index, row in enumerate(stages, 1))
    )
    try:
        inspection_findings = inspect(package) + inspect(package.with_suffix(".zip"))
        inspection_clean = not inspection_findings
    except InspectorError:
        inspection_clean = False
    return [
        {"name": "package_includes_case_yaml_and_local_source_record", "passed": "case.yaml" in records and bool(canonical) and sorted(declared_canonical) == sorted(canonical)},
        {"name": "shipped_stages_1_to_10_complete_with_canonical_hashes", "passed": complete_stage_chain},
        {"name": "package_members_and_hashes", "passed": archive_members == expected_members and hashes_ok},
        {"name": "zip_crc_and_utf8_metadata", "passed": crc_ok and utf8_ok},
        {"name": "real_docx_and_pdf", "passed": docx_is_ooxml and pdf.read_bytes().startswith(b"%PDF-")},
        {"name": "docx_claim_text_and_numbers", "passed": all(text in docx_text for text in expected_claims) and expected_numbers <= set(docx_text)},
        {"name": "docx_table_figure_and_full_bilingual_disclaimer", "passed": docx_has_table and docx_has_image and "Figure 1" in docx_text and "not a real client matter" in docx_text.lower() and compact_legal_en in compact_docx and compact_legal_zh in compact_docx},
        {"name": "pdf_claim_numbers_and_numeric_limits", "passed": pdf_result.returncode == 0 and expected_numbers <= set(pdf_result.stdout) and all(limit in pdf_result.stdout for limit in expected_numeric_limits)},
        {"name": "pdf_figure_and_full_bilingual_disclaimer", "passed": pdf_result.returncode == 0 and "Figure 1" in pdf_result.stdout and "not a real client matter" in pdf_result.stdout.lower() and compact_legal_en in compact_pdf and compact_legal_zh in compact_pdf},
        {"name": "release_package_artifact_inspector_clean", "passed": inspection_clean},
    ]


def artifact_inspector_adversaries(work: Path) -> list[dict[str, Any]]:
    """Exercise inspector blocking paths from acceptance, outside the release package."""
    probes = work / "artifact-inspector-adversaries"; probes.mkdir(parents=True, exist_ok=True)
    nested_bytes = io.BytesIO()
    with zipfile.ZipFile(nested_bytes, "w", zipfile.ZIP_DEFLATED) as nested:
        nested.writestr("private.txt", ("sk" + "-" + "A" * 20).encode("ascii"))
    with zipfile.ZipFile(probes / "nested.zip", "w", zipfile.ZIP_DEFLATED) as outer:
        outer.writestr("nested.zip", nested_bytes.getvalue())
    with zipfile.ZipFile(probes / "hidden.xlsx", "w", zipfile.ZIP_DEFLATED) as book:
        book.writestr("[Content_Types].xml", "<Types/>")
        book.writestr("xl/workbook.xml", '<workbook><sheets><sheet name="Hidden" state="veryHidden"/></sheets></workbook>')
    with zipfile.ZipFile(probes / "hidden.pptx", "w", zipfile.ZIP_DEFLATED) as deck:
        deck.writestr("[Content_Types].xml", "<Types/>")
        deck.writestr("ppt/presentation.xml", "<presentation/>")
        deck.writestr("ppt/slides/slide1.xml", '<slide show="0"/>')
    (probes / "invalid.pdf").write_bytes(b"%PDF-1.4\n")
    try:
        codes = {row["code"] for row in inspect(probes)}
    except InspectorError as exc:
        return [{"name":"artifact_inspector_nested_pdf_hidden_office_blocked","passed":False,"detail":str(exc)}]
    required = {"ARCHIVE_SECRET", "OOXML_HIDDEN_SHEET", "OOXML_HIDDEN_SLIDE", "PDF_INVALID"}
    return [{"name":"artifact_inspector_nested_pdf_hidden_office_blocked","passed":required <= codes,"codes":sorted(codes)}]


def canonical_case_members(root: Path) -> list[str]:
    """Identify case.yaml, canonical ledgers, and locally referenced source bytes."""
    fixed = [
        "case.yaml",
        "work/sources.jsonl",
        "work/evidence.jsonl",
        "work/claim_trace.jsonl",
        "work/scorecard.json",
        "work/stage_status.json",
    ]
    members = {name for name in fixed if (root / name).is_file()}
    source_index = root / "work" / "sources.jsonl"
    if source_index.is_file():
        rows = [json.loads(line) for line in source_index.read_text(encoding="utf-8").splitlines() if line.strip()]
        for row in rows:
            locator = row.get("locator") if isinstance(row, dict) else None
            if not isinstance(locator, str) or locator.startswith("https://"):
                continue
            path = Path(locator)
            if path.is_absolute() or ".." in path.parts:
                continue
            if (root / path).is_file():
                members.add(path.as_posix())
    return sorted(members)


def canonical_records(root: Path) -> dict[str, str]:
    """Hash every canonical YAML/JSON/JSONL record in the portable case package."""
    members = canonical_case_members(root)
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in members}


def safe_extract_package(archive_path: Path, target: Path) -> None:
    """Extract a self-built package only after rejecting traversal and symlink members."""
    target.mkdir(parents=True, exist_ok=True)
    target_root = target.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            member = PurePosixPath(info.filename.replace("\\", "/"))
            if not info.filename or info.filename.startswith("/") or ".." in member.parts or (len(member.parts) and ":" in member.parts[0]):
                raise ValueError(f"unsafe archive member: {info.filename}")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(f"symlink archive member: {info.filename}")
            destination = (target / Path(*member.parts)).resolve()
            try:
                destination.relative_to(target_root)
            except ValueError as exc:
                raise ValueError(f"archive member escapes extraction root: {info.filename}") from exc
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, destination.open("wb") as sink:
                shutil.copyfileobj(source, sink)


def roundtrip_and_relocation(repo: Path, scripts: Path, case: Path, package: Path, work: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate and rebuild directly from ZIP bytes, then prove relocation safety."""
    assertions: list[dict[str, Any]] = []; checks: list[dict[str, Any]] = []
    extract = work / "extracted"
    safe_extract_package(package.with_suffix(".zip"), extract)
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    extracted = {p.relative_to(extract).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in extract.rglob("*") if p.is_file()}
    expected = {row["path"]: row["sha256"] for row in manifest["files"]}
    assertions.append({"name":"build_extract_manifest_hashes","passed": all(extracted.get(name) == digest for name, digest in expected.items())})
    manifest_case = manifest.get("case_package", {})
    package_canonical = canonical_records(package)
    extracted_canonical = canonical_records(extract)
    assertions.append({"name":"manifest_declares_portable_canonical_case_record","passed": manifest_case.get("portable_case_record") is True and sorted(manifest_case.get("canonical_case_files", [])) == sorted(package_canonical)})
    checks.append(call(scripts, "validate_case.py", extract))
    assertions.append({"name":"extracted_zip_is_directly_validatable_case","passed": checks[-1]["exit_code"] == 0})
    rebuilt = work / "rebuilt"
    checks.append(call(scripts, "build_package.py", extract, "--format", "all", "--output", str(rebuilt)))
    if checks[-1]["exit_code"] == 0:
        assertions.append({"name":"zip_roundtrip_preserves_all_canonical_yaml_json_jsonl_hashes","passed": package_canonical == extracted_canonical == canonical_records(rebuilt)})
    else: assertions.append({"name":"zip_roundtrip_preserves_all_canonical_yaml_json_jsonl_hashes","passed":False})
    moved = work / "relocated-case"; shutil.copytree(extract, moved)
    checks.append(call(scripts, "validate_case.py", moved))
    assertions.append({"name":"case_relocation_preserves_relative_locators","passed":checks[-1]["exit_code"] == 0})
    relocated_rebuild = work / "relocated-rebuild"
    checks.append(call(scripts, "build_package.py", moved, "--format", "all", "--output", str(relocated_rebuild)))
    assertions.append({"name":"relocated_extracted_case_rebuilds","passed": checks[-1]["exit_code"] == 0 and package_canonical == canonical_records(relocated_rebuild)})
    return assertions, checks


def clean_checkout_quick_start(repo: Path, scripts: Path, work: Path, runner: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    clean = work / "evidence-first-patent-skill"
    shutil.copytree(repo, clean, ignore=shutil.ignore_patterns(".git", ".workflow", "dist", "__pycache__", ".venv"))
    offline, sentinel = socket_blocking_environment(work / "network-guard")
    checks: list[dict[str, Any]] = []
    readme = (clean / "README.md").read_text(encoding="utf-8")
    match = re.search(r"^## Five-minute local run\n.*?^```sh\n(.*?)^```$", readme, flags=re.MULTILINE | re.DOTALL)
    if not match:
        return [{"name":"network_disabled_exact_readme_quick_start","passed":False,"detail":"README shell block missing"}], checks
    command_lines = [line.strip() for line in match.group(1).splitlines() if line.strip()]
    current = clean.parent
    for line in command_lines:
        tokens = shlex.split(line)
        if tokens and tokens[0] == "cd" and len(tokens) == 2:
            current = (current / tokens[1]).resolve()
            checks.append({"command":["cd",tokens[1]],"exit_code":0 if current == clean.resolve() and current.is_dir() else 1,"stdout":"","stderr":""})
            continue
        if tokens and tokens[0] == "python3":
            tokens[0] = runner
        checks.append(run(tokens, current, ["README", line], offline))
    loaded = sentinel.exists() and "socket.connect blocked" in sentinel.read_text(encoding="utf-8")
    return [{"name":"network_disabled_exact_readme_quick_start","passed":loaded and all(check["exit_code"] == 0 for check in checks),"network":"sitecustomize socket.connect interceptor","sentinel_loaded":loaded,"commands":command_lines}], checks


def socket_blocking_environment(root: Path) -> tuple[dict[str, str], Path]:
    """Install a test-local socket guard; loading the hook is recorded as evidence."""
    root.mkdir(parents=True, exist_ok=True)
    sentinel = root / "socket-guard-loaded.txt"
    (root / "sitecustomize.py").write_text(
        "import os, socket\n"
        "from pathlib import Path\n"
        "Path(os.environ['EFPS_SOCKET_GUARD_SENTINEL']).write_text('sitecustomize loaded; socket.connect blocked\\n', encoding='utf-8')\n"
        "def _blocked_connect(self, address):\n"
        "    raise OSError('network disabled by EFPS socket guard')\n"
        "socket.socket.connect = _blocked_connect\n",
        encoding="utf-8",
    )
    env = {key: value for key, value in os.environ.items() if key.lower() not in {"no_proxy", "http_proxy", "https_proxy", "all_proxy"}}
    env["PYTHONPATH"] = str(root) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["EFPS_SOCKET_GUARD_SENTINEL"] = str(sentinel)
    return env, sentinel


def execute_fixture(repo: Path, scripts: Path, fixture: dict[str, Any], work: Path, runner: str) -> dict[str, Any]:
    """Run a concrete scenario and state whether a named expected block actually occurred."""
    fid = fixture["id"]; expected_block = fid not in POSITIVE_FIXTURES
    assertions: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    passed = False
    try:
        bilingual = fixture["language"] == "bilingual"
        case = make_base_case(work, fixture, bilingual=bilingual)
        paths = case_paths(case)
        if fid in {"ZH-INV-01", "EN-INV-05", "EN-CONFLICT-07"}:
            assertions.append({"name":"no_unsupported_measurement","passed":score(case)["unsupported_measured_claims"] == 0})
            assertions.append({"name":"proposed_not_achieved","passed":"proposed" in (paths["output"] / "disclosure.md").read_text(encoding="utf-8").lower()})
        if fid == "ZH-INV-01":
            rows = [json.loads(line) for line in paths["evidence"].read_text(encoding="utf-8").splitlines()]
            assertions.append({"name":"documented_source_has_no_measurement","passed":rows[0]["evidence_class"] == "documented" and "未提供试验方法" in rows[0]["verbatim"]})
        if fid == "EN-INV-05":
            cached = paths["input"] / "cached-prior-art.txt"
            cached.write_text("CN123456789 cached public prior-art record; publication 2020-01-01.\n", encoding="utf-8")
            sources = [json.loads(line) for line in paths["sources"].read_text(encoding="utf-8").splitlines()]
            sources.append({"source_id":"SRC-0002","source_type":"patent","title":"CN123456789 cached prior art","locator":"input/cached-prior-art.txt","canonical_url":"https://example.invalid/CN123456789","sha256":hashlib.sha256(cached.read_bytes()).hexdigest(),"publication_date":"2020-01-01","accessed_at":"2024-01-01","family_id":"FAM-CACHED-01","license":"public record","language":"en-US","public_status":"public","verification_status":"verified"})
            dump_jsonl(paths["sources"], sources)
            prior = paths["output"] / "prior_art.md"
            prior.write_text("# Prior-art comparison\n\nSRC-0002: CN123456789 is qualifying prior art.\n", encoding="utf-8")
            refresh_stages(paths)
            offline, sentinel = socket_blocking_environment(work / "en-inv-network-guard")
            checks.append(call(scripts, "validate_case.py", case, env=offline))
            checks.append(call(scripts, "trace_claims.py", case, "--check", env=offline))
            assertions.append({"name":"cached_prior_art_sha_and_offline_validation","passed":cached.is_file() and sources[-1]["sha256"] == hashlib.sha256(cached.read_bytes()).hexdigest() and "CN123456789" in prior.read_text(encoding="utf-8") and sentinel.exists() and all(check["exit_code"] == 0 for check in checks[-2:])})
        if fid == "EN-CONFLICT-07":
            disclosure=paths["output"] / "disclosure.md"; disclosure.write_text(disclosure.read_text(encoding="utf-8")+"\nTesting proved that accuracy improved by 30%.\n",encoding="utf-8")
            refresh_stages(paths)
            checks.append(call(scripts,"validate_case.py",case)); checks[-1].update(expected_failure=True, expected_stderr="unsupported_measured_claims")
            disclosure.write_text(disclosure.read_text(encoding="utf-8").replace("Testing proved that accuracy improved by 30%.", ""), encoding="utf-8")
            refresh_stages(paths)
            assertions.append({"name":"achieved_result_blocked","passed":checks[-1]["exit_code"]==1 and "unsupported_measured_claims" in checks[-1]["stderr"]})
        if fid == "ZH-UM-02":
            rows=[json.loads(line) for line in paths["trace"].read_text(encoding="utf-8").splitlines()]; rows[0]["limitation_text"]="A method comprising heating a specimen."; dump_jsonl(paths["trace"],rows)
            claims=paths["output"] / "claims.md"; claims.write_text("# Claim framework\n\n1. A method comprising heating a specimen.\n",encoding="utf-8")
            refresh_stages(paths)
            checks.append(call(scripts,"validate_case.py",case)); checks[-1].update(expected_failure=True, expected_stderr="structural product")
            rows[0]["limitation_text"]="一种包括弹性压持结构且间距为10 mm的夹具。"; dump_jsonl(paths["trace"],rows); claims.write_text("# Claim framework\n\n1. 一种包括弹性压持结构且间距为10 mm的夹具。\n",encoding="utf-8")
            refresh_stages(paths)
            assertions.append({"name":"method_like_source_product_structural_claim","passed":"方法式语言" in (paths["input"] / "source.md").read_text(encoding="utf-8") and checks[-1]["exit_code"]==1 and "structural product" in checks[-1]["stderr"]})
        if fid == "EN-UM-06":
            rows = json.loads(json.dumps([json.loads(line) for line in paths["sources"].read_text(encoding="utf-8").splitlines()]))
            duplicate = dict(rows[0], source_id="SRC-0002", source_type="patent", title="US1234567", locator="https://example.invalid/b", canonical_url="https://example.invalid/US1234567", sha256=None, publication_date="2020-01-01", accessed_at="2024-01-01", family_id="FAM-001", public_status="public")
            rows[0].update(source_type="patent", title="US1234567", locator="https://example.invalid/a", canonical_url="https://example.invalid/US1234567", sha256=None, publication_date="2020-01-01", accessed_at="2024-01-01", family_id="FAM-001", public_status="public")
            dump_jsonl(paths["sources"], rows + [duplicate]); checks.append(call(scripts,"dedupe_families.py",case,"--check")); checks[-1].update(expected_failure=True, expected_stderr="duplicate"); checks.append(call(scripts,"dedupe_families.py",case)); checks.append(call(scripts,"dedupe_families.py",case,"--check")); assertions.append({"name":"family_collapsed","passed":checks[-1]["exit_code"] == 0})
        if fid == "ZH-CONFLICT-03":
            source_one = paths["input"] / "spacing-10.md"; source_two = paths["input"] / "spacing-12.md"
            source_one.write_text("Documented spacing is 10 mm.\n", encoding="utf-8"); source_two.write_text("Documented spacing is 12 mm.\n", encoding="utf-8")
            sources = []
            for source_id, title, item in (("SRC-0001", "Synthetic source A", source_one), ("SRC-0002", "Synthetic source B", source_two)):
                sources.append({"source_id":source_id,"source_type":"synthetic","title":title,"locator":f"input/{item.name}","sha256":hashlib.sha256(item.read_bytes()).hexdigest(),"publication_date":None,"accessed_at":None,"family_id":None,"license":"CC BY 4.0","language":"en-US","public_status":"synthetic","verification_status":"verified"})
            evidence = [
                {"evidence_id":"EV-0001","source_id":"SRC-0001","source_location":{"paragraph":"p1"},"verbatim":"Documented spacing is 10 mm.","statement":"spacing is 10 mm","evidence_class":"documented","verification_status":"verified","public_status":"synthetic","derived_from":[],"review_notes":""},
                {"evidence_id":"EV-0002","source_id":"SRC-0002","source_location":{"paragraph":"p1"},"verbatim":"Documented spacing is 12 mm.","statement":"spacing is 12 mm","evidence_class":"documented","verification_status":"verified","public_status":"synthetic","derived_from":[],"review_notes":"numeric conflict requires human disposition"},
            ]
            dump_jsonl(paths["sources"], sources); dump_jsonl(paths["evidence"], evidence)
            rows=[json.loads(line) for line in paths["trace"].read_text(encoding="utf-8").splitlines()]; rows[0].update(evidence_ids=["EV-0001", "EV-0002"], semantic_status="conflict"); dump_jsonl(paths["trace"],rows)
            refresh_stages(paths)
            checks.append(call(scripts,"trace_claims.py",case,"--check")); checks[-1].update(expected_failure=True, expected_stderr="conflict")
            assertions.append({"name":"two_local_sha_sources_numeric_conflict_trace_blocked","passed":all(source["sha256"] == hashlib.sha256((case / source["locator"]).read_bytes()).hexdigest() for source in sources) and {row["statement"] for row in evidence} == {"spacing is 10 mm", "spacing is 12 mm"} and rows[0]["evidence_ids"] == ["EV-0001", "EV-0002"] and rows[0]["semantic_status"] == "conflict" and checks[-1]["exit_code"] == 1 and "conflict" in checks[-1]["stderr"]})
        if fid == "ZH-SECRET-04":
            token = "sk" + "-abcdefghijklmnopqrstuvwxyz"; local_path = "/" + "Users/example"; blocked = "secret" + "-project"; phone = "138" + "0013" + "8000"
            (case / "input" / "secret.txt").write_text(f"{token} contact {phone} {local_path} {blocked}", encoding="utf-8")
            deny=work/"denylist.txt"; deny.write_text(blocked+"\n",encoding="utf-8")
            checks.append(run([sys.executable,str(scripts/"scan_sensitive.py"),str(case),"--denylist",str(deny),"--format","json"],repo,["python","scan_sensitive.py","CASE","--denylist","denylist.txt","--format","json"])); checks[-1].update(expected_failure=True, expected_stderr="token")
            found=json.loads(checks[-1]["stdout"])["findings"] if checks[-1]["stdout"] else []
            kinds={x["kind"] for x in found}; assertions.append({"name":"all_secret_seeds_detected","passed":{"token","phone","absolute_path","denylist"} <= kinds})
        if fid == "EN-SECRET-08":
            archive=case/"input"/"metadata.docx"
            contact = "test" + "@example.com"; member = "secret" + "-customer.txt"
            with zipfile.ZipFile(archive,"w") as z: z.writestr("docProps/core.xml",f"contact {contact}"); z.writestr(member,"x")
            deny=work/"archive-denylist.txt"; deny.write_text(member.removesuffix(".txt")+"\n",encoding="utf-8")
            checks.append(run([sys.executable,str(scripts/"scan_sensitive.py"),str(case),"--denylist",str(deny),"--format","json"],repo,["python","scan_sensitive.py","CASE","--format","json"])); checks[-1].update(expected_failure=True, expected_stderr="archive_email")
            kinds={x["kind"] for x in json.loads(checks[-1]["stdout"])["findings"]}; assertions.append({"name":"archive_metadata_and_member_detected","passed":"archive_email" in kinds and "archive_member_denylist" in kinds})
            archive.unlink(); stages=json.loads(paths["stages"].read_text(encoding="utf-8")); [item.update(status="pending",input_hash=None,output_hash=None) for item in stages]; dump_json(paths["stages"],stages); release=case/"package"/"clean-release"; checks.append(call(scripts,"build_package.py",case,"--format","md","--output",str(release)))
            checks.append(run([sys.executable,str(scripts/"scan_sensitive.py"),str(release),"--format","json"],repo,["python","scan_sensitive.py","CLEAN_PACKAGE","--format","json"]))
            assertions.append({"name":"clean_package_scans_zero","passed":checks[-2]["exit_code"]==0 and checks[-1]["exit_code"]==0})
        if fid == "BI-PAIR-09":
            checks.append(call(scripts,"compare_bilingual.py",case,"--check")); assertions.append({"name":"atomic_consistency","passed":checks[-1]["exit_code"] == 0})
            source_row = json.loads(paths["sources"].read_text(encoding="utf-8").splitlines()[0])
            assertions.append({"name":"synthetic_source_language_matches_text","passed":source_row.get("language") == "en-US" and "Synthetic source" in (paths["input"] / "source.md").read_text(encoding="utf-8")})
        if fid in {"ZH-INV-01", "BI-PAIR-09"}:
            release = case / "package" / "release"
            checks.append(call(scripts, "build_package.py", case, "--format", "all", "--output", str(release)))
            if checks[-1]["exit_code"] == 0:
                trace_rows = [json.loads(line) for line in paths["trace"].read_text(encoding="utf-8").splitlines()]
                assertions.extend(package_assertions(release, trace_rows))
                if fid == "ZH-INV-01": assertions.extend(artifact_inspector_adversaries(work))
                extra_assertions, extra_checks = roundtrip_and_relocation(repo, scripts, case, release, work / f"{fid.lower()}-roundtrip")
                assertions.extend(extra_assertions); checks.extend(extra_checks)
                if fid == "ZH-INV-01":
                    clean_assertions, clean_checks = clean_checkout_quick_start(repo, scripts, work / "offline-clean-checkout", runner)
                    assertions.extend(clean_assertions); checks.extend(clean_checks)
            else:
                assertions.append({"name": "rendered_package_created", "passed": False})
        if fid == "BI-DRIFT-10":
            rows=[json.loads(line) for line in paths["trace"].read_text(encoding="utf-8").splitlines()]
            rows[1]["limitation_text"]="A sensor comprising a rigid pressing structure with a spacing of 12 mm under heating."
            rows[1]["limitation_text_sha256"]=hashlib.sha256(rows[1]["limitation_text"].encode("utf-8")).hexdigest()
            rows[1]["atom_map"]=[
                {"type":"object","canonical":"sensor","text_span":"sensor"},
                {"type":"component_or_step","canonical":"rigid_pressing_structure","text_span":"rigid pressing structure"},
                {"type":"relationship","canonical":"spacing","text_span":"spacing"},
                {"type":"numeric_bound","canonical":"12mm","text_span":"12 mm"},
                {"type":"condition","canonical":"during_heating","text_span":"under heating"},
                {"type":"modality","canonical":"open","text_span":"comprising"},
            ]
            rows[1]["semantic_status"]="designed"; rows[1]["human_review_status"]="accepted"; dump_jsonl(paths["trace"],rows); refresh_stages(paths)
            checks.append(call(scripts,"compare_bilingual.py",case,"--check")); checks[-1].update(expected_failure=True, expected_stderr="bilingual atomic mismatch")
            check_output=checks[-1]["stderr"]
            assertions.append({"name":"scope_drift_object_component_numeric_condition_blocked","passed":checks[-1]["exit_code"] == 1 and all(atom in check_output for atom in ("object","component_or_step","numeric_bound","condition"))})
            checks.append(call(scripts,"compare_bilingual.py",case,"--mark-conflicts")); checks[-1].update(expected_failure=True, expected_stderr="CONFLICTS_MARKED")
            marked=[json.loads(line) for line in paths["trace"].read_text(encoding="utf-8").splitlines()]
            assertions.append({"name":"mismatch_preserved_marked_and_explained","passed":checks[-1]["exit_code"] == 1 and all(row["semantic_status"]=="conflict" and row.get("bilingual_differences") for row in marked)})
            invalidated = json.loads(paths["stages"].read_text(encoding="utf-8"))
            stage_nine = next(item for item in invalidated if item["stage"] == 9); stage_ten = next(item for item in invalidated if item["stage"] == 10)
            assertions.append({"name":"bilingual_conflict_invalidates_downstream_review","passed":stage_nine["status"] == "complete" and stage_nine["output_hash"] and stage_ten["status"] == "pending" and stage_ten["input_hash"] is None and stage_ten["output_hash"] is None})
        if fid in {"AUTO-ZH-11","AUTO-EN-12"}:
            controlling=fixture.get("controlling_request_language")
            stages=json.loads(paths["stages"].read_text(encoding="utf-8")); stages[0].pop("resolved_language",None); dump_json(paths["stages"],stages)
            checks.append(call(scripts,"validate_case.py",case)); checks[-1].update(expected_failure=True, expected_stderr="auto language resolution")
            checks.append(call(scripts,"resolve_language.py",case,"--language",controlling))
            stages=json.loads(paths["stages"].read_text(encoding="utf-8")); refresh_stages(paths, resolved_language=controlling)
            assertions.append({"name":"controlling_request_overrides_input_language_mix","passed":checks[-2]["exit_code"] == 1 and "auto language resolution" in checks[-2]["stderr"] and checks[-1]["exit_code"] == 0 and stages[0].get("resolved_language") == controlling and ((fid == "AUTO-ZH-11" and "English-heavy" in (paths["input"] / "source.md").read_text(encoding="utf-8")) or (fid == "AUTO-EN-12" and "中文输入占多数" in (paths["input"] / "source.md").read_text(encoding="utf-8")))})
        if fid == "DATE-13":
            source_rows=[json.loads(line) for line in paths["sources"].read_text(encoding="utf-8").splitlines()]; src=source_rows[0]; src.update(source_type="patent",title="CN123456789",locator="https://example.invalid/date",canonical_url="https://example.invalid/CN123456789",sha256=None,publication_date="2025-01-01",accessed_at="2025-01-02",family_id="FAM-DATE",public_status="public",comparison_disposition="qualifying_prior_art");dump_jsonl(paths["sources"],source_rows)
            stages=json.loads(paths["stages"].read_text(encoding="utf-8")); [item.update(status="pending",input_hash=None,output_hash=None) for item in stages]; dump_json(paths["stages"],stages)
            prior=paths["output"] / "prior_art.md"; prior.write_text("# Prior art\nSRC-0001: CN123456789 is qualifying prior art.\n",encoding="utf-8")
            checks.append(call(scripts,"validate_case.py",case)); checks[-1].update(expected_failure=True, expected_stderr="post-critical-date patent")
            src["comparison_disposition"] = "context_only"; dump_jsonl(paths["sources"], source_rows)
            prior.write_text("# Prior art\nCN123456789 is retained as context only and excluded from the comparison.\n",encoding="utf-8")
            refresh_stages(paths)
            assertions.append({"name":"post_critical_date_excluded","passed":checks[-1]["exit_code"] == 1 and "post-critical-date patent" in checks[-1]["stderr"]})
        if fid == "GATE-14":
            cfg=load_case_yaml(paths["case"]);cfg["human_gate"].update(selected_concept_id=None,public_boundary_confirmed=False,approved_by=None,approved_at=None);dump_case_yaml(paths["case"],cfg);checks.append(call(scripts,"validate_case.py",case));checks[-1].update(expected_failure=True, expected_stderr="stage 8 requires human selection gate");assertions.append({"name":"stage_8_gate_blocked","passed":checks[-1]["exit_code"] == 1 and "stage 8 requires human selection gate" in checks[-1]["stderr"]})
        if fid == "STALE-15":
            evidence_rows=[json.loads(line) for line in paths["evidence"].read_text(encoding="utf-8").splitlines()]
            evidence_rows[0]["statement"]="changed synthetic structural feature"; dump_jsonl(paths["evidence"],evidence_rows)
            checks.append(call(scripts,"validate_case.py",case)); checks[-1].update(expected_failure=True, expected_stderr="stage_status: stage")
            checks.append(call(scripts,"build_package.py",case,"--format","md","--output",str(case / "package" / "stale-release"))); checks[-1].update(expected_failure=True, expected_stderr="stage_status: stage")
            reset = reset_downstream_stages(paths, 3); dump_json(paths["stages"], reset)
            stages_by_number = {item["stage"]: item for item in reset}
            assertions.append({"name":"stale_trace_rejected_and_downstream_reset","passed":checks[-2]["exit_code"] == 1 and checks[-1]["exit_code"] == 1 and "stage_status: stage" in checks[-2]["stderr"] and "stage_status: stage" in checks[-1]["stderr"] and all(stages_by_number[number]["status"] == "pending" and stages_by_number[number]["input_hash"] is None and stages_by_number[number]["output_hash"] is None for number in (9, 10))})
        if fid == "MEDIA-16":
            ledger=repo/"public-assets/media-ledger.md"; checks.append(run([sys.executable,str(scripts/"validate_media.py"),"--ledger",str(ledger)],repo,["python","validate_media.py","--ledger","public-assets/media-ledger.md"]))
            bad_license=work/"unknown-license.md"; bad_license.write_text(ledger.read_text(encoding="utf-8").replace("| CC BY-SA 4.0 |", "| unknown |", 1),encoding="utf-8")
            bad_hash=work/"bad-hash.md"; bad_hash.write_text(re.sub(r"(?<=`)[0-9a-f]{64}(?=`)","0"*64,ledger.read_text(encoding="utf-8"),count=1),encoding="utf-8")
            checks.append(run([sys.executable,str(scripts/"validate_media.py"),"--ledger",str(bad_license),"--root",str(repo)],repo,["python","validate_media.py","--ledger","unknown-license.md"])); checks.append(run([sys.executable,str(scripts/"validate_media.py"),"--ledger",str(bad_hash),"--root",str(repo)],repo,["python","validate_media.py","--ledger","bad-hash.md"]))
            checks[-2].update(expected_failure=True, expected_stderr="unsupported license"); checks[-1].update(expected_failure=True, expected_stderr="asset hash mismatch")
            assertions.append({"name":"shipped_ledger_passes_and_bad_ledgers_block","passed":checks[-3]["exit_code"]==0 and checks[-2]["exit_code"]==1 and checks[-1]["exit_code"]==1})
        if fid in POSITIVE_FIXTURES:
            # Scenario mutations model an upstream rerun; stale completion state must not survive them.
            if fid in {"DATE-13", "EN-UM-06", "AUTO-ZH-11", "AUTO-EN-12", "ZH-UM-02", "EN-CONFLICT-07", "EN-INV-05"}:
                refresh_stages(paths, resolved_language=fixture.get("controlling_request_language"))
            checks.append(call(scripts,"validate_case.py",case)); checks.append(call(scripts,"trace_claims.py",case,"--check"))
            repeat = call(scripts,"validate_case.py",case)
            checks.append(repeat)
            assertions.append({"name":"validator_twice_deterministic","passed": checks[-3]["exit_code"] == 0 and repeat["exit_code"] == 0 and checks[-3]["stdout"] == repeat["stdout"] and checks[-3]["stderr"] == repeat["stderr"]})
            if bilingual: checks.append(call(scripts,"compare_bilingual.py",case,"--check"))
            assertions.append({"name":"metrics_100","passed":score(case)["evidence_coverage_pct"] == 100.0 and score(case)["claim_trace_coverage_pct"] == 100.0})
        if not assertions: raise ValueError("fixture did not execute any required assertion")
        passed=all(item["passed"] for item in assertions) and all(
            (item["exit_code"] == 0 if not item.get("expected_failure") else item["exit_code"] == 1 and item.get("expected_stderr", "") in (item["stderr"] + item["stdout"]))
            for item in checks
        )
    except Exception as exc:
        assertions.append({"name":"executor_exception","passed":False,"detail":str(exc)})
        passed=False
    return {"id":fid,"expected_block":expected_block,"checks":checks,"assertions":assertions,"status":"PASS" if passed else "FAIL"}


def main() -> int:
    parser=argparse.ArgumentParser();parser.add_argument("--repo",type=Path,required=True);parser.add_argument("--fixtures",type=Path,required=True);parser.add_argument("--report",type=Path,required=True);args=parser.parse_args()
    repo=args.repo.resolve();skill=repo/"skill/draft-patents-evidence-first";scripts=skill/"scripts";checks: list[dict[str,Any]]=[];missing_dependency=False
    runner=os.environ.get("EFPS_VALIDATOR_PYTHON",sys.executable)
    # The public runtime is stdlib-only; the official validator alone needs PyYAML.
    # Prefer the repository development environment when the invoking interpreter
    # lacks that declared dev dependency, without downloading or installing anything.
    if subprocess.run([runner, "-c", "import yaml"], text=True, capture_output=True).returncode:
        bundled = repo / ".venv" / "bin" / "python"
        if bundled.is_file() and subprocess.run([str(bundled), "-c", "import yaml"], text=True, capture_output=True).returncode == 0:
            runner = str(bundled)
    validator=Path.home()/".codex"/"skills"/".system"/"skill-creator"/"scripts"/"quick_validate.py"
    if not validator.exists(): validator=repo/"tests"/"vendor"/"quick_validate.py"
    yaml_probe=run([runner,"-c","import yaml"],repo,["python","-c","import yaml"])
    if yaml_probe["exit_code"]:
        missing_dependency=True; checks.append({"command":["python","quick_validate.py","skill/draft-patents-evidence-first"],"exit_code":2,"stdout":"","stderr":"missing required dependency: PyYAML; install requirements-dev.txt in the validator environment"})
    elif validator.exists(): checks.append(run([runner,str(validator),str(skill)],repo,["python","quick_validate.py","skill/draft-patents-evidence-first"]))
    else: checks.append({"command":["quick_validate.py"],"exit_code":2,"stdout":"","stderr":"official validator unavailable"})
    if not shutil.which("pdftotext"):
        missing_dependency=True; checks.append({"command":["pdftotext","package.pdf","-"],"exit_code":2,"stdout":"","stderr":"missing required dependency: pdftotext (poppler-utils)"})
    for name in ["init_case.py","validate_case.py","dedupe_families.py","trace_claims.py","compare_bilingual.py","scan_sensitive.py","build_package.py","run_acceptance.py","resolve_language.py","validate_media.py","inspect_artifacts.py"]: checks.append(run([runner,str(scripts/name),"--help"],repo,["python",f"skill/draft-patents-evidence-first/scripts/{name}","--help"]))
    fixture_paths={child.name:child/"fixture.yaml" for child in args.fixtures.iterdir() if child.is_dir() and (child/"fixture.yaml").exists()} if args.fixtures.exists() else {}
    fixture_errors=[]
    for unknown in sorted(set(fixture_paths)-EXPECTED_FIXTURES): fixture_errors.append(f"unknown fixture: {unknown}")
    for missing in sorted(EXPECTED_FIXTURES-set(fixture_paths)): fixture_errors.append(f"missing fixture: {missing}")
    metadata={}
    for fid,path in sorted(fixture_paths.items()):
        try:
            data=fixture_yaml(path); metadata[fid]=data
            if REQUIRED_FIXTURE_FIELDS-set(data): fixture_errors.append(f"{fid}: missing fixture fields")
            if data.get("id") != fid: fixture_errors.append(f"{fid}: id mismatch")
        except Exception as exc: fixture_errors.append(f"{fid}: unreadable fixture.yaml: {exc}")
    results=[]
    if not fixture_errors:
        with tempfile.TemporaryDirectory(prefix="efps-acceptance-") as temp:
            for fid in sorted(EXPECTED_FIXTURES): results.append(execute_fixture(repo,scripts,metadata[fid],Path(temp),runner))
    else:
        results=[{"id":fid,"expected_block":fid not in POSITIVE_FIXTURES,"checks":[],"assertions":[{"name":"fixture_available_and_valid","passed":False}],"status":"NOT_EXECUTED"} for fid in sorted(EXPECTED_FIXTURES)]
    matrix_passed=not fixture_errors and len(results)==len(EXPECTED_FIXTURES) and all(r["status"]=="PASS" for r in results)
    if fixture_errors: checks.append({"command":["fixture_matrix"],"exit_code":1,"stdout":"","stderr":"; ".join(fixture_errors)})
    elif not matrix_passed: checks.append({"command":["fixture_matrix"],"exit_code":1,"stdout":"","stderr":"one or more executed fixtures failed"})
    # Write a portable preliminary report so the aggregate scan can inspect the exact
    # report bytes that will be delivered alongside all public candidates and dist.
    report={"schema_version":SCHEMA_VERSION,"generated_at":now(),"repository":repo.name,"fixture_ids":sorted(metadata),"fixture_results":results,"fixture_errors":fixture_errors,"checks":checks,"failed_checks":[],"status":"BLOCKED","note":"Only Sol-V may set READY_FOR_PUBLICATION_REVIEW."}
    dump_json(args.report,report)
    aggregate = exact_public_candidate_scan(repo, args.report)
    checks.append({"command":["scan_sensitive.py","git-ls-files public candidates + report + dist"],"exit_code":aggregate["exit_code"],"stdout":aggregate["stdout"],"stderr":aggregate["stderr"]})
    passed=all(c["exit_code"]==0 for c in checks) and matrix_passed
    failed=[{"command":c["command"],"exit_code":c["exit_code"],"reason":(c["stderr"] or c["stdout"]).strip()[:500]} for c in checks if c["exit_code"]]
    report.update(checks=checks, failed_checks=failed, status="CANDIDATE_CHECKS_PASSED" if passed else "BLOCKED")
    dump_json(args.report,report)
    # The final rewrite contains only the already-scanned portable diagnostics; verify
    # it once more so the record proves the report itself remains in scope.
    final_aggregate = exact_public_candidate_scan(repo, args.report)
    if final_aggregate["exit_code"]:
        report["status"] = "BLOCKED"
        report["checks"].append({"command":["scan_sensitive.py","final report + public candidates + dist"],"exit_code":final_aggregate["exit_code"],"stdout":final_aggregate["stdout"],"stderr":final_aggregate["stderr"]})
        report["failed_checks"] = [{"command":c["command"],"exit_code":c["exit_code"],"reason":(c["stderr"] or c["stdout"]).strip()[:500]} for c in report["checks"] if c["exit_code"]]
        dump_json(args.report,report)
        passed=False
    print(json.dumps({"status":report["status"],"executed_fixtures":len(results),"report":str(args.report)},ensure_ascii=False));return 0 if passed else (2 if missing_dependency else 1)

if __name__=="__main__":sys.exit(main())

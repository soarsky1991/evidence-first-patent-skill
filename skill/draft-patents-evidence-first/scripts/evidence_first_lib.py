#!/usr/bin/env python3
"""Stdlib-only utilities for the Evidence-First Patent Skill.

This module intentionally has no network client. Public-search decisions are human-gated;
the local tools validate records and package only local, reviewed content.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "0.1.0"
LANGUAGES = {"zh-CN", "en-US", "auto", "bilingual"}
PATENT_TYPES = {"invention", "utility_model"}
EVIDENCE_CLASSES = {"measured", "documented", "inferred", "designed"}
VERIFY = {"verified", "needs_review", "rejected"}
PUBLIC = {"confidential", "sanitized", "public", "synthetic"}

FULL_LEGAL_DISCLAIMER_EN = (
    "This package provides drafting and evidence-governance assistance, not legal advice. "
    "It does not guarantee patentability, validity, non-infringement, freedom to operate, "
    "ownership, grant, or fitness for filing. Obtain qualified patent counsel review before "
    "disclosure, filing, or reliance."
)
FULL_LEGAL_DISCLAIMER_ZH = (
    "本文件仅提供专利撰写与证据治理辅助，不构成法律意见，也不保证可专利性、有效性、不侵权、"
    "自由实施、权属、授权或适合直接申请。披露、申请或据此作出决定前，应由具备资质的专利专业人员审核。"
)


class ValidationError(Exception):
    pass


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def canonical_hash(paths: list[Path]) -> str:
    """Hash regular files recursively with stable, case-relative path labels.

    A workflow record must not silently dereference a symlink: the linked target
    can be outside the case and can change without an auditable case-local path.
    Rejecting them is deliberate rather than treating their bytes as ordinary
    input.  Directory roots are part of the label so equal basenames in separate
    trees cannot collide.
    """
    records: list[tuple[str, str]] = []
    for root in sorted(paths, key=lambda item: item.as_posix()):
        if root.is_symlink():
            raise ValidationError(f"canonical hash rejects symlink: {root}")
        if root.is_file():
            records.append((root.name, sha256_file(root)))
            continue
        if not root.exists():
            continue
        if not root.is_dir():
            raise ValidationError(f"canonical hash requires regular file or directory: {root}")
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_symlink():
                raise ValidationError(f"canonical hash rejects symlink: {path}")
            if path.is_file():
                records.append((f"{root.name}/{path.relative_to(root).as_posix()}", sha256_file(path)))
    return stable_hash(records)


def human_gate_hash(paths: dict[str, Path]) -> str:
    """Hash only the approval facts that authorize drafting and review."""
    case = load_case_yaml(paths["case"])
    gate = case.get("human_gate")
    return stable_hash(gate if isinstance(gate, dict) else gate)


def expected_stage_hashes(paths: dict[str, Path]) -> dict[int, tuple[str, str]]:
    output_files = sorted(paths["output"].glob("*"))
    source = canonical_hash([paths["sources"]]); evidence = canonical_hash([paths["evidence"]])
    trace = canonical_hash([paths["trace"]]); output = canonical_hash(output_files)
    case = canonical_hash([paths["case"]]); prior = canonical_hash([paths["output"] / "prior_art.md"])
    gate = human_gate_hash(paths)
    resolved_language = None
    stages_path = paths["stages"]
    if stages_path.exists():
        stages = load_json(stages_path)
        if isinstance(stages, list) and stages and isinstance(stages[0], dict):
            resolved_language = stages[0].get("resolved_language")
    stage_one_output = stable_hash({"sources": source, "resolved_language": resolved_language})
    stage_seven_output = stable_hash({"case": case, "human_gate": gate})
    stage_eight_output = stable_hash({"output": output, "human_gate": gate})
    stage_nine_output = stable_hash({"trace": trace, "human_gate": gate})
    stage_ten_output = stable_hash({"scorecard": canonical_hash([paths["scorecard"]]), "human_gate": gate})
    # Every input consumes the preceding canonical output.  This makes a changed
    # resolved language, source, or approval record stale all the way downstream.
    return {
        1: (canonical_hash([paths["input"]]), stage_one_output),
        2: (stage_one_output, source),
        3: (source, evidence),
        4: (evidence, evidence),
        5: (evidence, source),
        6: (source, prior),
        7: (prior, stage_seven_output),
        8: (stage_seven_output, stage_eight_output),
        9: (stage_eight_output, stage_nine_output),
        10: (stage_nine_output, stage_ten_output),
    }


def reset_downstream_stages(paths: dict[str, Path], changed_stage: int, stages: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Return a stage list with every dependent row reset to pending.

    Validators stay read-only; a workflow transition or explicit conflict-marking
    operation persists this returned value with ``dump_json``.
    """
    if changed_stage not in range(1, 11):
        raise ValueError("changed_stage must be between 1 and 10")
    records = stages if stages is not None else load_json(paths["stages"])
    if not isinstance(records, list):
        raise ValidationError("stage_status: needs an array before downstream reset")
    for item in records:
        if isinstance(item, dict) and item.get("stage", 0) > changed_stage:
            item.update(status="pending", input_hash=None, output_hash=None, updated_at=now(), blocking_reasons=[])
    return records


def refresh_complete_stage_hashes(paths: dict[str, Path], *, complete_through: int = 10) -> list[dict[str, Any]]:
    """Return a legal, content-bound complete stage record set for synthetic fixtures.

    This is intentionally a harness helper rather than a workflow transition command:
    real workflow stages must be completed by their corresponding operations.  Fixtures
    use it only after all canonical case records have been written, so a negative test
    reaches its named validator instead of failing first on a deliberately stale hash.
    """
    if not 0 <= complete_through <= 10:
        raise ValueError("complete_through must be between 0 and 10")
    resolved_language = None
    if paths["stages"].exists():
        existing = load_json(paths["stages"])
        if isinstance(existing, list) and existing and isinstance(existing[0], dict):
            resolved_language = existing[0].get("resolved_language")
    expected = expected_stage_hashes(paths)
    stages: list[dict[str, Any]] = []
    for number in range(1, 11):
        status = "complete" if number <= complete_through else "pending"
        input_hash, output_hash = expected[number] if status == "complete" else (None, None)
        record = {
            "stage": number,
            "status": status,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "updated_at": now(),
            "blocking_reasons": [],
        }
        if number == 1 and resolved_language is not None:
            record["resolved_language"] = resolved_language
        stages.append(record)
    return stages


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"invalid JSON {path}: {exc}") from exc


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"null", "~"}:
        return None
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.startswith(("\"", "'")):
        try:
            return json.loads(value) if value.startswith("\"") else value[1:-1]
        except json.JSONDecodeError:
            return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def load_case_yaml(path: Path) -> dict[str, Any]:
    """Read the deliberately narrow YAML emitted by init_case without PyYAML."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValidationError(f"missing case.yaml: {exc}") from exc
    result: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if ":" not in raw:
            raise ValidationError(f"unsupported YAML line: {raw}")
        key, value = raw.strip().split(":", 1)
        if indent == 0:
            if value.strip():
                result[key] = parse_scalar(value)
                current = None
            else:
                current = {}
                result[key] = current
        elif indent == 2 and current is not None:
            current[key] = parse_scalar(value)
        else:
            raise ValidationError(f"unsupported YAML indentation: {raw}")
    return result


def dump_case_yaml(path: Path, case: dict[str, Any]) -> None:
    ordered = ["schema_version", "case_id", "language", "jurisdiction", "patent_type", "critical_date", "priority_claimed", "confidentiality_mode", "human_gate"]
    lines: list[str] = []
    for key in ordered:
        value = case.get(key)
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for child, child_value in value.items():
                if child_value is None:
                    rendered = "null"
                elif isinstance(child_value, bool):
                    rendered = str(child_value).lower()
                else:
                    rendered = json.dumps(child_value, ensure_ascii=False)
                lines.append(f"  {child}: {rendered}")
        elif value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, bool):
            lines.append(f"{key}: {str(value).lower()}")
        else:
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValidationError(f"missing {label}: {path}")
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ValidationError(f"{label}:{line_no}: blank JSONL line")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{label}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValidationError(f"{label}:{line_no}: JSONL entry must be an object")
        rows.append(row)
    return rows


def dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in rows)
    path.write_text((text + "\n") if text else "", encoding="utf-8")


def require(row: dict[str, Any], keys: list[str], label: str) -> None:
    missing = [key for key in keys if key not in row]
    if missing:
        raise ValidationError(f"{label}: missing required field(s): {', '.join(missing)}")


def date_or_null(value: Any, label: str) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise ValidationError(f"{label}: date must be ISO string or null")
    try:
        dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{label}: invalid ISO date") from exc


def ensure_unique(rows: list[dict[str, Any]], field: str, label: str) -> None:
    seen: set[str] = set()
    for row in rows:
        value = row.get(field)
        if not isinstance(value, str) or not value:
            raise ValidationError(f"{label}: invalid {field}")
        if value in seen:
            raise ValidationError(f"{label}: duplicate {field} {value}")
        seen.add(value)


def case_paths(case_dir: Path) -> dict[str, Path]:
    work = case_dir / "work"
    return {
        "case": case_dir / "case.yaml", "sources": work / "sources.jsonl", "evidence": work / "evidence.jsonl",
        "trace": work / "claim_trace.jsonl", "scorecard": work / "scorecard.json", "stages": work / "stage_status.json",
        "input": case_dir / "input", "output": case_dir / "output", "package": case_dir / "package",
    }


def validate_case_config(case: dict[str, Any]) -> None:
    require(case, ["schema_version", "case_id", "language", "jurisdiction", "patent_type", "critical_date", "priority_claimed", "confidentiality_mode", "human_gate"], "case.yaml")
    if case["schema_version"] != SCHEMA_VERSION: raise ValidationError("case.yaml: unsupported schema_version")
    if not isinstance(case["case_id"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", case["case_id"]): raise ValidationError("case.yaml: invalid non-identifying case_id")
    if case["language"] not in LANGUAGES: raise ValidationError("case.yaml: invalid language")
    if case["jurisdiction"] != "CN": raise ValidationError("case.yaml: jurisdiction must be CN")
    if case["patent_type"] not in PATENT_TYPES: raise ValidationError("case.yaml: invalid patent_type")
    date_or_null(case["critical_date"], "case.yaml critical_date")
    if not isinstance(case["priority_claimed"], bool): raise ValidationError("case.yaml: priority_claimed must be boolean")
    if case["confidentiality_mode"] not in {"local_only", "sanitized_search", "approved_external"}: raise ValidationError("case.yaml: invalid confidentiality_mode")
    gate = case["human_gate"]
    if not isinstance(gate, dict): raise ValidationError("case.yaml: human_gate must be object")
    require(gate, ["selected_concept_id", "approved_by", "approved_at", "public_boundary_confirmed"], "human_gate")
    if gate["selected_concept_id"] is not None and not isinstance(gate["selected_concept_id"], str): raise ValidationError("human_gate: selected_concept_id must be string or null")
    if gate["approved_by"] is not None and not isinstance(gate["approved_by"], str): raise ValidationError("human_gate: approved_by must be string or null")
    if gate["approved_at"] is not None and not isinstance(gate["approved_at"], str): raise ValidationError("human_gate: approved_at must be RFC3339 string or null")
    if not isinstance(gate["public_boundary_confirmed"], bool): raise ValidationError("human_gate: public_boundary_confirmed must be boolean")
    if isinstance(gate["approved_by"], str) and gate["approved_by"] and "@" in gate["approved_by"]: raise ValidationError("human_gate: approved_by must be a non-email reviewer label")
    if gate["approved_at"] is not None and not valid_rfc3339(gate["approved_at"]): raise ValidationError("human_gate: approved_at must be a real RFC3339 timestamp")
    if case["priority_claimed"] and not case.get("priority_record"):
        raise ValidationError("case.yaml: priority_claimed=true needs human priority_record")


def valid_rfc3339(value: str) -> bool:
    """Accept only calendar-valid RFC 3339 timestamps with an explicit offset."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value):
        return False
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def approved_human_gate(gate: dict[str, Any]) -> bool:
    return (
        isinstance(gate.get("selected_concept_id"), str)
        and bool(gate["selected_concept_id"].strip())
        and isinstance(gate.get("approved_by"), str)
        and bool(gate["approved_by"].strip())
        and isinstance(gate.get("approved_at"), str)
        and valid_rfc3339(gate["approved_at"])
        and gate.get("public_boundary_confirmed") is True
    )


def validate_sources(rows: list[dict[str, Any]], case_dir: Path) -> None:
    required = ["source_id", "source_type", "title", "locator", "sha256", "publication_date", "accessed_at", "family_id", "license", "language", "public_status", "verification_status"]
    ensure_unique(rows, "source_id", "sources")
    for row in rows:
        require(row, required, f"source {row.get('source_id', '?')}")
        if not re.fullmatch(r"SRC-\d{4,}", row["source_id"]): raise ValidationError("sources: source_id must be SRC- plus four digits")
        if row["source_type"] not in {"internal_file", "patent", "paper", "standard", "web", "user_statement", "synthetic"}: raise ValidationError("sources: invalid source_type")
        if not isinstance(row["title"], str) or not row["title"].strip(): raise ValidationError("sources: title required")
        # Cached public material remains a local source for integrity/offline purposes.
        # Its source_type can still be ``patent`` (or paper/standard/web); locator form,
        # rather than source category, determines whether bytes must be present locally.
        local = not str(row["locator"]).startswith("https://")
        if local:
            if not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]): raise ValidationError("sources: local source needs SHA-256")
            locator = Path(str(row["locator"]))
            if locator.is_absolute() or ".." in locator.parts: raise ValidationError("sources: local locator must be case-relative")
            source_path = case_dir / locator
            if not source_path.is_file() or sha256_file(source_path) != row["sha256"]: raise ValidationError("sources: local locator missing or SHA-256 mismatch")
        if not local and not str(row["locator"]).startswith("https://"): raise ValidationError("sources: public locator must be canonical HTTPS URL")
        date_or_null(row["publication_date"], "sources publication_date")
        date_or_null(row["accessed_at"], "sources accessed_at")
        if not local and row["accessed_at"] is None: raise ValidationError("sources: network source needs accessed_at")
        if not isinstance(row["language"], str) or not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]+)*", row["language"]): raise ValidationError("sources: invalid BCP 47 language")
        if row["public_status"] not in PUBLIC: raise ValidationError("sources: invalid public_status")
        if row["verification_status"] not in {"verified", "unverified", "blocked"}: raise ValidationError("sources: invalid verification_status")
        if row["source_type"] == "patent" and not (row["family_id"] or re.search(r"\b(?:CN|US|EP|WO)\d", row["title"])): raise ValidationError("sources: patent needs publication number or family_id")
        # A local cache supports offline review but cannot replace the public
        # provenance required of a public patent record.
        if row["source_type"] == "patent" and row["public_status"] == "public":
            canonical_url = row.get("canonical_url")
            if not isinstance(canonical_url, str) or not canonical_url.startswith("https://"):
                raise ValidationError("sources: public patent needs canonical_url")
            if row["accessed_at"] is None or row["publication_date"] is None or row["verification_status"] != "verified":
                raise ValidationError("sources: public patent needs accessed_at, verified publication_date, and verified status")


def validate_evidence(rows: list[dict[str, Any]], sources: list[dict[str, Any]], case_dir: Path) -> None:
    required = ["evidence_id", "source_id", "source_location", "verbatim", "statement", "evidence_class", "verification_status", "public_status", "derived_from", "review_notes"]
    ensure_unique(rows, "evidence_id", "evidence")
    evidence_ids = {str(r.get("evidence_id")) for r in rows}
    source_by_id = {row["source_id"]: row for row in sources}
    for row in rows:
        require(row, required, f"evidence {row.get('evidence_id', '?')}")
        if not re.fullmatch(r"EV-\d{4,}", row["evidence_id"]): raise ValidationError("evidence: invalid evidence_id")
        if row["source_id"] not in source_by_id: raise ValidationError("evidence: unresolved source_id")
        if not isinstance(row["source_location"], dict) or not any(key in row["source_location"] for key in {"page", "slide", "sheet", "cell_range", "paragraph", "figure", "timestamp"}): raise ValidationError("evidence: source_location needs a coordinate")
        if not isinstance(row["verbatim"], str) or not isinstance(row["statement"], str) or not row["statement"].strip(): raise ValidationError("evidence: verbatim and statement must be strings")
        if row["evidence_class"] not in EVIDENCE_CLASSES: raise ValidationError("evidence: invalid evidence_class")
        if row["verification_status"] not in VERIFY: raise ValidationError("evidence: invalid verification_status")
        if row["public_status"] not in PUBLIC: raise ValidationError("evidence: invalid public_status")
        if not isinstance(row["derived_from"], list): raise ValidationError("evidence: derived_from must be array")
        if row["evidence_class"] == "inferred" and not row["derived_from"]: raise ValidationError("evidence: inferred needs derived_from")
        if row["evidence_class"] == "inferred" and not re.search(r"\b(?:infer(?:red|ence)?|suggest(?:s|ed)?|indicat(?:e|es|ed))\b|(?:推断|推测|表明)", row["statement"], re.I):
            raise ValidationError("evidence: inferred statement must be explicitly qualified")
        visual_exception = row["evidence_class"] == "documented" and "figure" in row["source_location"] and "visual" in row["review_notes"].casefold()
        if not row["verbatim"].strip() and not visual_exception:
            raise ValidationError("evidence: verbatim is required unless documented visual observation")
        source = source_by_id[row["source_id"]]
        if not str(source["locator"]).startswith("https://") and row["verbatim"].strip():
            source_text = (case_dir / str(source["locator"])).read_text(encoding="utf-8", errors="ignore")
            if row["verbatim"] not in source_text:
                raise ValidationError("evidence: verbatim is not bound to local source bytes")
        if row["evidence_class"] == "measured":
            measurement = row.get("measurement")
            if not isinstance(measurement, dict) or not all(isinstance(measurement.get(key), str) and measurement[key].strip() for key in ("method", "context", "result")):
                raise ValidationError("evidence: measured record needs measurement method, context, and result")
        if any(item not in evidence_ids for item in row["derived_from"]): raise ValidationError("evidence: unresolved derived_from")
        if row["verification_status"] != "verified" and not isinstance(row["review_notes"], str): raise ValidationError("evidence: review_notes needed")
    graph = {row["evidence_id"]: row["derived_from"] for row in rows}
    visiting: set[str] = set(); visited: set[str] = set()
    def visit(node: str) -> None:
        if node in visiting: raise ValidationError("evidence: derived_from cycle")
        if node not in visited:
            visiting.add(node)
            for child in graph[node]: visit(child)
            visiting.remove(node); visited.add(node)
    for node in graph: visit(node)


def validate_trace(rows: list[dict[str, Any]], evidence_rows: list[dict[str, Any]], bilingual: bool) -> None:
    required = ["claim_id", "claim_number", "parent_claim_number", "limitation_id", "language", "limitation_text", "evidence_ids", "semantic_status", "human_review_status", "paired_limitation_id"]
    ensure_unique(rows, "limitation_id", "claim trace")
    ids = {r["limitation_id"] for r in rows}
    evidence_by_id = {r["evidence_id"]: r for r in evidence_rows}
    claim_numbers = {r.get("claim_number") for r in rows}
    for row in rows:
        require(row, required, f"trace {row.get('limitation_id', '?')}")
        if not re.fullmatch(r"CLM-\d{3,}", str(row["claim_id"])) or not re.fullmatch(r"LIM-\d{4,}", str(row["limitation_id"])): raise ValidationError("trace: invalid claim or limitation ID")
        if not isinstance(row["claim_number"], int) or row["claim_number"] <= 0: raise ValidationError("trace: invalid claim_number")
        if row["parent_claim_number"] is not None and (not isinstance(row["parent_claim_number"], int) or row["parent_claim_number"] >= row["claim_number"] or row["parent_claim_number"] not in claim_numbers): raise ValidationError("trace: invalid parent claim")
        if row["language"] not in {"zh-CN", "en-US"}: raise ValidationError("trace: invalid language")
        if not isinstance(row["limitation_text"], str) or not row["limitation_text"].strip(): raise ValidationError("trace: limitation_text required")
        if not isinstance(row["evidence_ids"], list) or not row["evidence_ids"] or any(item not in evidence_by_id for item in row["evidence_ids"]): raise ValidationError("trace: unresolved evidence_ids")
        if row["semantic_status"] not in {"supported", "inferred", "designed", "conflict", "missing"}: raise ValidationError("trace: invalid semantic_status")
        if row["human_review_status"] not in {"pending", "accepted", "rejected"}: raise ValidationError("trace: invalid human_review_status")
        linked = [evidence_by_id[item] for item in row["evidence_ids"]]
        linked_classes = {item["evidence_class"] for item in linked}
        linked_verified = all(item["verification_status"] == "verified" for item in linked)
        if row["semantic_status"] == "supported" and (not linked_verified or not linked_classes <= {"measured", "documented"}):
            raise ValidationError("trace: supported limitation requires verified measured/documented evidence")
        if row["semantic_status"] == "inferred" and ("inferred" not in linked_classes or not linked_verified):
            raise ValidationError("trace: inferred limitation requires verified inferred evidence")
        if row["semantic_status"] == "designed" and ("designed" not in linked_classes or not linked_verified):
            raise ValidationError("trace: designed limitation requires verified designed evidence")
        if bilingual and (not isinstance(row["paired_limitation_id"], str) or row["paired_limitation_id"] not in ids): raise ValidationError("trace: bilingual row needs valid pair")
        if not bilingual and row["paired_limitation_id"] is not None: raise ValidationError("trace: paired limitation only allowed in bilingual case")
        if bilingual:
            expected_text_hash = hashlib.sha256(row["limitation_text"].encode("utf-8")).hexdigest()
            if row.get("limitation_text_sha256") != expected_text_hash:
                raise ValidationError("trace: bilingual limitation_text_sha256 is missing or stale")
            atom_map = row.get("atom_map")
            if not isinstance(atom_map, list) or not atom_map:
                raise ValidationError("trace: bilingual row needs a non-empty atom_map")
            allowed_atom_types = {"object", "component_or_step", "relationship", "numeric_bound", "condition", "modality"}
            mapped_atoms: set[tuple[str, str]] = set()
            mapped_types: set[str] = set()
            for atom in atom_map:
                if not isinstance(atom, dict) or set(atom) != {"type", "canonical", "text_span"}:
                    raise ValidationError("trace: atom_map entries need type, canonical, and text_span")
                atom_type, canonical, text_span = atom["type"], atom["canonical"], atom["text_span"]
                if atom_type not in allowed_atom_types:
                    raise ValidationError("trace: invalid bilingual atom type")
                if not isinstance(canonical, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_.:-]*", canonical):
                    raise ValidationError("trace: invalid bilingual canonical atom")
                if not isinstance(text_span, str) or not text_span.strip() or text_span.casefold() not in row["limitation_text"].casefold():
                    raise ValidationError("trace: bilingual atom text_span is not present in limitation_text")
                key = (atom_type, canonical)
                if key in mapped_atoms:
                    raise ValidationError("trace: duplicate bilingual canonical atom")
                mapped_atoms.add(key); mapped_types.add(atom_type)
            required_types = {"object", "modality"}
            text = row["limitation_text"]
            if re.search(r"(?:structure|member|component|assembly|module|构件|结构|组件|部件|模块)", text, re.I): required_types.add("component_or_step")
            if re.search(r"(?:spacing|between|connected|coupled|adjacent|间距|连接|之间|相邻)", text, re.I): required_types.add("relationship")
            if re.search(r"(?:under|during|when|upon|在.+?(?:时|条件下)|当.+?时)", text, re.I): required_types.add("condition")
            if not required_types <= mapped_types:
                raise ValidationError("trace: bilingual atom_map omits technical atom class")
            numeric_tokens = {
                re.sub(r"\s+", "", value).casefold()
                for value in re.findall(r"\d+(?:\.\d+)?(?:\s*(?:mm|μm|um|℃|°C|%|MPa|N|s|min))?", row["limitation_text"], flags=re.I)
            }
            mapped_numeric = {canonical for atom_type, canonical in mapped_atoms if atom_type == "numeric_bound"}
            if numeric_tokens != mapped_numeric:
                raise ValidationError("trace: numeric bounds differ from bilingual atom_map")
            # A symmetric but incomplete map must not hide a translated qualifier.  Every
            # content-bearing token must be covered by at least one exact atom span; only
            # claim grammar/function words may remain uncovered.  Canonical values remain
            # human-reviewable, while stale or omitted surface text is mechanically blocked.
            covered = [False] * len(text)
            folded = text.casefold()
            for atom in atom_map:
                needle = atom["text_span"].casefold()
                start = 0
                while True:
                    offset = folded.find(needle, start)
                    if offset < 0:
                        break
                    for index in range(offset, offset + len(needle)):
                        covered[index] = True
                    start = offset + max(1, len(needle))
            remainder = "".join(" " if covered[index] else character for index, character in enumerate(text))
            allowed_english = {
                "a", "an", "the", "one", "said", "each", "and", "or", "with", "without",
                "of", "to", "from", "for", "in", "on", "at", "by", "as", "wherein", "where",
                "that", "which", "is", "are", "be", "being", "thereof", "thereto",
            }
            uncovered_english = {
                token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", remainder)
                if token.casefold() not in allowed_english
            }
            allowed_chinese_characters = set("一种所述该各其且和及或与为的于在上中下内外之间其中")
            uncovered_chinese = {character for character in remainder if "\u4e00" <= character <= "\u9fff" and character not in allowed_chinese_characters}
            if uncovered_english or uncovered_chinese:
                raise ValidationError("trace: bilingual atom_map leaves uncovered technical text")
    if bilingual:
        for row in rows:
            pair = next(x for x in rows if x["limitation_id"] == row["paired_limitation_id"])
            if pair["paired_limitation_id"] != row["limitation_id"] or pair["language"] == row["language"]: raise ValidationError("trace: invalid bilingual pair symmetry")


def validate_stages(stages: Any, case: dict[str, Any], paths: dict[str, Path]) -> None:
    if not isinstance(stages, list) or len(stages) != 10: raise ValidationError("stage_status: needs exactly ten stages")
    seen = set(); active = 0
    for item in stages:
        require(item, ["stage", "status", "input_hash", "output_hash", "updated_at", "blocking_reasons"], "stage")
        if item["stage"] not in range(1, 11) or item["stage"] in seen: raise ValidationError("stage_status: stages 1–10 unique required")
        seen.add(item["stage"])
        if item["status"] not in {"pending", "in_progress", "blocked", "complete"}: raise ValidationError("stage_status: invalid status")
        active += item["status"] == "in_progress"
        if not isinstance(item["blocking_reasons"], list): raise ValidationError("stage_status: blocking_reasons must be array")
        if item["stage"] >= 8 and item["status"] in {"in_progress", "complete"}:
            gate = case["human_gate"]
            if not approved_human_gate(gate): raise ValidationError("stage 8 requires human selection gate approval record")
    if active > 1: raise ValidationError("stage_status: at most one in_progress")
    by_stage = {item["stage"]: item for item in stages}
    for stage in range(1, 11):
        status = by_stage[stage]["status"]
        if status in {"in_progress", "blocked", "complete"} and any(by_stage[previous]["status"] != "complete" for previous in range(1, stage)):
            raise ValidationError(f"stage_status: stage {stage} is not contiguous with completed predecessors")
    expected = expected_stage_hashes(paths)
    for stage, item in by_stage.items():
        if item["status"] == "complete" and (item.get("input_hash"), item.get("output_hash")) != expected[stage]:
            raise ValidationError(f"stage_status: stage {stage} content hash is stale")
    # The trace/review stages consume the preceding stage's canonical output. A mismatched
    # hash is an explicit stale-output signal and must be reset before validation succeeds.
    for stage in (9, 10):
        item = by_stage[stage]
        predecessor = by_stage[stage - 1]
        if item["status"] == "complete" and predecessor.get("output_hash") and item.get("input_hash") != predecessor.get("output_hash"):
            raise ValidationError(f"stage_status: stage {stage} is stale relative to stage {stage - 1}")


def read_case(case_dir: Path) -> tuple[dict[str, Any], dict[str, Path], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    paths = case_paths(case_dir)
    case = load_case_yaml(paths["case"]); validate_case_config(case)
    sources = load_jsonl(paths["sources"], "sources"); validate_sources(sources, case_dir)
    evidence = load_jsonl(paths["evidence"], "evidence"); validate_evidence(evidence, sources, case_dir)
    trace = load_jsonl(paths["trace"], "claim trace"); validate_trace(trace, evidence, case["language"] == "bilingual")
    stages = load_json(paths["stages"])
    if case["language"] == "auto":
        resolved = stages[0].get("resolved_language") if isinstance(stages, list) and stages else None
        if resolved not in {"zh-CN", "en-US"}:
            raise ValidationError("auto language resolution not persisted")
    validate_stages(stages, case, paths)
    if case["language"] == "auto":
        resolved = stages[0].get("resolved_language")
        if any(row["language"] != resolved for row in trace):
            raise ValidationError("auto language resolution differs from claim trace language")
    elif case["language"] in {"zh-CN", "en-US"} and any(row["language"] != case["language"] for row in trace):
        raise ValidationError("claim trace language differs from configured output language")
    return case, paths, sources, evidence, trace


SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    # Match complete, issued-token-shaped values only.  In particular, do not
    # flag identifiers such as ``skill_directory`` merely because they start
    # with ``sk``.  The boundary checks also prevent matching a token-shaped
    # substring embedded in a longer identifier.
    "token": re.compile(
        r"(?<![A-Za-z0-9_])(?:"
        r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}|"
        r"ghp_[A-Za-z0-9]{36}|"
        r"github_pat_[A-Za-z0-9_]{22,255}|"
        r"AKIA[A-Z0-9]{16}"
        r")(?![A-Za-z0-9_-])"
    ),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    # Deliberately narrow patterns avoid classifying ISO dates and hashes as phones.
    "phone": re.compile(r"\b(?:\+?86[- ]?)?1[3-9]\d{9}\b|\b(?:\+?1[- .]?)?\(?[2-9]\d{2}\)?[- .]\d{3}[- .]\d{4}\b"),
    "absolute_path": re.compile(r"(?<![A-Za-z0-9_])/(?:Users|home|var|tmp|private)/[^\s\"']+"),
    "cookie": re.compile(r"\b(?:sessionid|cookie|set-cookie)\s*[:=]", re.I),
}


def sensitive_findings(target: Path, denylist: Path | None = None) -> list[dict[str, Any]]:
    scan_root = target.resolve()
    def logical_path(path: Path) -> str:
        """Stable, root-relative identity material; never hash a temp parent path."""
        try:
            return path.resolve().relative_to(scan_root).as_posix() if scan_root.is_dir() else path.name
        except ValueError:
            return path.name
    blocked = []
    if denylist and denylist.exists():
        blocked = [x.strip() for x in denylist.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
    # Only machine caches are excluded.  Generated reports and release archives are
    # candidate material and must be scanned exactly as they will be shipped.
    ignored_parts = {".git", "__pycache__", ".pytest_cache", ".venv"}
    ignored_suffixes = {".pyc", ".pyo", ".DS_Store"}
    binary_suffixes = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svgz"}
    archive_text_suffixes = {".xml", ".rels", ".txt", ".md", ".json", ".jsonl", ".yaml", ".yml", ".csv"}
    def include(path: Path) -> bool:
        if set(path.parts) & ignored_parts or path.suffix in ignored_suffixes:
            return False
        try:
            relative = path.relative_to(target).as_posix()
        except ValueError:
            relative = path.as_posix()
        return True
    files = [target] if target.is_file() else [p for p in target.rglob("*") if p.is_file() and include(p)]
    findings: list[dict[str, Any]] = []
    for path in files:
        if path.suffix.lower() in {".zip", ".docx", ".pptx", ".xlsx"}:
            try:
                with zipfile.ZipFile(path) as archive:
                    for member in archive.infolist():
                        member_text = member.filename
                        for term in blocked:
                            if term in member_text:
                                findings.append({"id": stable_hash([logical_path(path), member.filename, "denylist", term])[:16], "path": str(path), "kind": "archive_member_denylist", "match": "[redacted]"})
                        payload = archive.read(member).decode("utf-8", errors="ignore") if Path(member.filename).suffix.lower() in archive_text_suffixes else ""
                        for kind, pattern in SECRET_PATTERNS.items():
                            if pattern.search(member_text) or pattern.search(payload):
                                findings.append({"id": stable_hash([logical_path(path), member.filename, kind])[:16], "path": str(path), "kind": f"archive_{kind}", "match": "[redacted]"})
            except (OSError, zipfile.BadZipFile):
                pass
            # Archive members have already been inspected selectively above. Treating the
            # compressed container bytes as UTF-8 creates random token/email false positives.
            continue
        if path.suffix.lower() in binary_suffixes:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for kind, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(content):
                findings.append({"id": stable_hash([logical_path(path), kind, match.start()])[:16], "path": str(path), "kind": kind, "match": "[redacted]"})
        for term in blocked:
            if term in content:
                findings.append({"id": stable_hash([logical_path(path), "denylist", term])[:16], "path": str(path), "kind": "denylist", "match": "[redacted]"})
    return sorted(findings, key=lambda x: (x["path"], x["kind"], x["id"]))


def command_error(exc: Exception) -> int:
    print(f"ERROR: {exc}", file=sys.stderr)
    return 1


def ensure_output_template(paths: dict[str, Path]) -> None:
    defaults = {
        "disclosure.md": (
            "# Technical disclosure\n\n"
            f"> {FULL_LEGAL_DISCLAIMER_EN}\n>\n> {FULL_LEGAL_DISCLAIMER_ZH}\n"
        ),
        "claims.md": "# Claim framework\n\n> Framework only; review every limitation and trace.\n",
        "prior_art.md": "# Prior-art comparison\n\nNo public source is date-qualified until verified.\n",
        "risk_register.md": "# Risk register\n\n| Risk | Evidence | Disposition |\n|---|---|---|\n",
        "verification_matrix.md": "# Verification matrix\n\n| Statement | Evidence class | Verification step |\n|---|---|---|\n",
    }
    paths["output"].mkdir(parents=True, exist_ok=True)
    for name, content in defaults.items():
        dest = paths["output"] / name
        if not dest.exists(): dest.write_text(content, encoding="utf-8")

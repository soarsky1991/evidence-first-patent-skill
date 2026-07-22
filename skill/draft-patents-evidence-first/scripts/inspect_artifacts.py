#!/usr/bin/env python3
"""Inspect release artifacts for metadata and archive-safety regressions.

The checker is deliberately local-only and standard-library first.  It does not
try to extract arbitrary archive contents and it never treats compressed bytes
as text.  Findings are reported against the container and, where useful, the
member inside that container.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET


class InspectorError(Exception):
    """Raised for invocation or unavailable-dependency errors."""


# Archive inspection is intentionally bounded even for locally supplied files.
# The limits are high enough for release artifacts but prevent a nested archive
# or a decompression bomb from turning validation into an extraction service.
MAX_ARCHIVE_DEPTH = 3
MAX_ARCHIVE_ENTRIES = 1_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
TEXT_MEMBER_SUFFIXES = {".xml", ".rels", ".txt", ".md", ".json", ".jsonl", ".yaml", ".yml", ".csv"}
PRIVACY_PATTERNS = {
    "SECRET": re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|(?<![A-Za-z0-9_])(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,255}|AKIA[A-Z0-9]{16})(?![A-Za-z0-9_-])"),
    "CONTACT": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b|\b(?:\+?86[- ]?)?1[3-9]\d{9}\b|\b(?:\+?1[- .]?)?\(?[2-9]\d{2}\)?[- .]\d{3}[- .]\d{4}\b"),
    "ABSOLUTE_PATH": re.compile(r"(?<![A-Za-z0-9_])/(?:Users|home|var|tmp|private)/[^\s\"']+"),
}


def finding(path: Path, code: str, detail: str, member: str | None = None) -> dict[str, str]:
    row = {"path": str(path), "code": code, "detail": detail}
    if member is not None:
        row["member"] = member
    return row


def unsafe_member(name: str) -> bool:
    """Return true for archive paths that cannot safely be materialized."""
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return (
        not normalized
        or normalized.startswith("/")
        or bool(re.match(r"^[A-Za-z]:/", normalized))
        or ".." in path.parts
    )


def parse_manifest(payload: bytes, source: str) -> dict[str, dict[str, Any]]:
    """Parse and validate the content-addressed manifest produced by build_package."""
    try:
        document = json.loads(payload.decode("utf-8"))
        rows = document["files"]
        if not isinstance(rows, list):
            raise TypeError("files is not a list")
        declared: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise TypeError("file record is not an object")
            name = row.get("path")
            if not isinstance(name, str) or unsafe_member(name):
                raise TypeError("invalid declared member")
            if name == "manifest.json":
                raise TypeError("manifest.json must not declare itself")
            if name in declared:
                raise TypeError(f"duplicate declared member: {name}")
            size = row.get("bytes")
            digest = row.get("sha256")
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                raise TypeError(f"invalid declared byte size for {name}")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise TypeError(f"invalid declared SHA-256 for {name}")
            declared[name] = {"path": name, "bytes": size, "sha256": digest}
        return declared
    except (UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
        raise InspectorError(f"invalid manifest {source}: {exc}") from exc


def load_adjacent_manifest(path: Path) -> tuple[dict[str, dict[str, Any]], str] | None:
    """Load a sidecar manifest for legacy/external ZIP layouts, when present."""
    manifest = path.parent / "manifest.json"
    if not manifest.is_file():
        return None
    try:
        return parse_manifest(manifest.read_bytes(), str(manifest)), "adjacent"
    except OSError as exc:
        raise InspectorError(f"cannot read adjacent manifest {manifest}: {exc}") from exc


def manifest_zip_findings(
    path: Path,
    archive: zipfile.ZipFile,
    records: dict[str, dict[str, Any]],
    *,
    internal_manifest: bool,
) -> list[dict[str, str]]:
    """Check exact membership and content against a parsed package manifest."""
    findings: list[dict[str, str]] = []
    infos = archive.infolist()
    counts = Counter(info.filename for info in infos)
    for name, count in sorted(counts.items()):
        if count > 1:
            findings.append(finding(path, "ZIP_DUPLICATE_MEMBER", f"member occurs {count} times", name))

    expected = set(records)
    if internal_manifest:
        expected.add("manifest.json")
    actual = set(counts)
    for name in sorted(actual - expected):
        findings.append(finding(path, "ZIP_UNDECLARED_MEMBER", "member is not declared by manifest.json", name))
    for name in sorted(expected - actual):
        findings.append(finding(path, "ZIP_MISSING_MEMBER", "declared member is missing from ZIP", name))

    unique_infos = {info.filename: info for info in infos if counts[info.filename] == 1}
    for name, record in sorted(records.items()):
        info = unique_infos.get(name)
        if info is None:
            continue
        if info.file_size != record["bytes"]:
            findings.append(finding(
                path,
                "ZIP_MANIFEST_SIZE_MISMATCH",
                f"manifest declares {record['bytes']} bytes but ZIP records {info.file_size}",
                name,
            ))
        try:
            payload = archive.read(info)
        except zipfile.BadZipFile:
            # inspect_zip emits the member-specific CRC finding.
            continue
        except (NotImplementedError, OSError, RuntimeError):
            # inspect_zip emits the more specific read/compression finding.
            continue
        digest = hashlib.sha256(payload).hexdigest()
        if digest != record["sha256"]:
            findings.append(finding(path, "ZIP_MANIFEST_SHA256_MISMATCH", "member SHA-256 differs from manifest", name))
    return findings


def privacy_findings(path: Path, text: str, *, prefix: str, member: str | None = None) -> list[dict[str, str]]:
    """Return redacted, one-per-kind privacy findings without exposing matched text."""
    findings: list[dict[str, str]] = []
    for kind, pattern in PRIVACY_PATTERNS.items():
        if pattern.search(text):
            findings.append(finding(path, f"{prefix}_{kind}", "sensitive content detected", member))
    return findings


def nested_member(parent: str | None, child: str) -> str:
    return f"{parent}!{child}" if parent else child


def inspect_zip(
    path: Path,
    archive: zipfile.ZipFile,
    findings: list[dict[str, str]],
    state: dict[str, int],
    *,
    depth: int,
    parent_member: str | None = None,
) -> None:
    """Inspect ZIP members without extracting them to disk or exceeding limits."""
    try:
        infos = sorted(archive.infolist(), key=lambda item: item.filename)
    except (OSError, zipfile.BadZipFile) as exc:
        findings.append(finding(path, "ZIP_INVALID", f"cannot list ZIP members: {exc}", parent_member))
        return
    for info in infos:
        member = nested_member(parent_member, info.filename)
        state["entries"] += 1
        if state["entries"] > MAX_ARCHIVE_ENTRIES:
            findings.append(finding(path, "ZIP_ENTRY_LIMIT", f"archive exceeds {MAX_ARCHIVE_ENTRIES} member limit", parent_member))
            return
        if unsafe_member(info.filename):
            findings.append(finding(path, "ZIP_PATH_TRAVERSAL", "archive member is absolute or traverses parent directories", member))
            continue
        if info.flag_bits & 0x1:
            findings.append(finding(path, "ZIP_ENCRYPTED_MEMBER", "encrypted archive member cannot be inspected", member))
            continue
        if state["bytes"] + info.file_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            findings.append(finding(path, "ZIP_UNCOMPRESSED_SIZE_LIMIT", f"archive exceeds {MAX_ARCHIVE_UNCOMPRESSED_BYTES} uncompressed-byte limit", member))
            return
        state["bytes"] += info.file_size
        try:
            payload = archive.read(info)
        except NotImplementedError:
            findings.append(finding(path, "ZIP_UNSUPPORTED_COMPRESSION", "archive member uses unsupported compression", member))
            continue
        except zipfile.BadZipFile:
            findings.append(finding(path, "ZIP_CRC_FAILURE", "ZIP CRC validation failed", member))
            continue
        except (OSError, RuntimeError) as exc:
            findings.append(finding(path, "ZIP_MEMBER_READ_FAILURE", f"cannot inspect archive member: {exc}", member))
            continue

        suffix = Path(info.filename).suffix.lower()
        if suffix in TEXT_MEMBER_SUFFIXES:
            findings.extend(privacy_findings(path, payload.decode("utf-8", errors="ignore"), prefix="ARCHIVE", member=member))
        if payload.startswith(b"PK\x03\x04") or payload.startswith(b"PK\x05\x06") or payload.startswith(b"PK\x07\x08"):
            if depth >= MAX_ARCHIVE_DEPTH:
                findings.append(finding(path, "ZIP_DEPTH_LIMIT", f"archive nesting exceeds {MAX_ARCHIVE_DEPTH} levels", member))
                continue
            try:
                with zipfile.ZipFile(io.BytesIO(payload)) as nested:
                    inspect_zip(path, nested, findings, state, depth=depth + 1, parent_member=member)
            except zipfile.BadZipFile as exc:
                findings.append(finding(path, "ZIP_INVALID", f"nested archive is not readable: {exc}", member))


def archive_findings(path: Path, *, apply_manifest: bool = True) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    try:
        with zipfile.ZipFile(path) as archive:
            if apply_manifest:
                manifest_infos = [info for info in archive.infolist() if info.filename == "manifest.json"]
                if len(manifest_infos) == 1:
                    try:
                        records = parse_manifest(archive.read(manifest_infos[0]), f"{path}!manifest.json")
                        findings.extend(manifest_zip_findings(path, archive, records, internal_manifest=True))
                    except InspectorError as exc:
                        findings.append(finding(path, "ZIP_MANIFEST_INVALID", str(exc), "manifest.json"))
                    except zipfile.BadZipFile:
                        # inspect_zip emits ZIP_CRC_FAILURE for the corrupt manifest.
                        pass
                elif not manifest_infos:
                    try:
                        adjacent = load_adjacent_manifest(path)
                        if adjacent is not None:
                            records, _ = adjacent
                            findings.extend(manifest_zip_findings(path, archive, records, internal_manifest=False))
                    except InspectorError as exc:
                        findings.append(finding(path, "ZIP_MANIFEST_INVALID", str(exc)))
                else:
                    # The general duplicate-member check below reports the exact count.
                    findings.extend(manifest_zip_findings(path, archive, {}, internal_manifest=True))
            inspect_zip(path, archive, findings, {"entries": 0, "bytes": 0}, depth=0)
    except zipfile.BadZipFile as exc:
        findings.append(finding(path, "ZIP_INVALID", f"not a readable ZIP archive: {exc}"))
    return sorted(findings, key=lambda row: (row["path"], row["code"], row.get("member", ""), row["detail"]))


def xml_text(root: ET.Element, local_name: str) -> str:
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] == local_name and node.text and node.text.strip():
            return node.text.strip()
    return ""


def ooxml_findings(path: Path) -> list[dict[str, str]]:
    """Inspect Word, Excel, and PowerPoint OOXML packages without materializing them."""
    required_parts = {
        ".docx": "word/document.xml",
        ".xlsx": "xl/workbook.xml",
        ".pptx": "ppt/presentation.xml",
    }
    required_part = required_parts.get(path.suffix.lower())
    if required_part is None:
        return [finding(path, "OOXML_UNSUPPORTED", "unsupported OOXML package type")]
    # A package-level manifest describes release files, not internal OOXML parts.
    findings = archive_findings(path, apply_manifest=False)
    try:
        with zipfile.ZipFile(path) as document:
            names = set(document.namelist())
            if "[Content_Types].xml" not in names or required_part not in names:
                findings.append(finding(path, "OOXML_INVALID", f"missing required OOXML part {required_part}"))
                return findings

            for name in sorted(names):
                lower = name.lower()
                if lower.endswith("vbaproject.bin") or "/vba" in lower:
                    findings.append(finding(path, "OOXML_MACRO", "macro-bearing OOXML member", name))
                if "/embeddings/" in lower or "/activex/" in lower:
                    findings.append(finding(path, "OOXML_EMBEDDED_FILE", "embedded or ActiveX content", name))
                if lower in {"word/comments.xml", "word/commentsextended.xml", "word/people.xml", "word/threadedcomments.xml"} or lower.startswith("xl/comments") or lower.startswith("xl/threadedcomments") or lower.startswith("ppt/comments") or lower.startswith("ppt/commentauthors"):
                    findings.append(finding(path, "OOXML_COMMENTS", "comment or reviewer metadata part", name))
                if lower == "docprops/custom.xml":
                    findings.append(finding(path, "OOXML_CUSTOM_PROPERTIES", "custom document properties", name))

            if "docProps/core.xml" in names:
                try:
                    root = ET.fromstring(document.read("docProps/core.xml"))
                    for field in ("creator", "lastModifiedBy"):
                        value = xml_text(root, field)
                        if value:
                            findings.append(finding(path, "OOXML_PERSONAL_METADATA", f"{field} is set", "docProps/core.xml"))
                except ET.ParseError:
                    findings.append(finding(path, "OOXML_INVALID_XML", "cannot parse core document properties", "docProps/core.xml"))

            if "docProps/app.xml" in names:
                try:
                    root = ET.fromstring(document.read("docProps/app.xml"))
                    if any((node.text or "").strip() for node in root.iter() if node.tag.rsplit("}", 1)[-1] in {"Company", "Manager", "Application", "AppVersion"}):
                        findings.append(finding(path, "OOXML_APP_PROPERTIES", "application metadata is set", "docProps/app.xml"))
                except ET.ParseError:
                    findings.append(finding(path, "OOXML_INVALID_XML", "cannot parse application properties", "docProps/app.xml"))

            for name in sorted(n for n in names if n.endswith(".rels")):
                try:
                    root = ET.fromstring(document.read(name))
                except ET.ParseError:
                    findings.append(finding(path, "OOXML_INVALID_XML", "cannot parse relationship XML", name))
                    continue
                for relationship in root.iter():
                    if relationship.tag.rsplit("}", 1)[-1] == "Relationship" and relationship.attrib.get("TargetMode", "").lower() == "external":
                        findings.append(finding(path, "OOXML_EXTERNAL_RELATIONSHIP", "external OOXML relationship", name))
                        break

            if path.suffix.lower() == ".xlsx":
                try:
                    root = ET.fromstring(document.read("xl/workbook.xml"))
                    for node in root.iter():
                        if node.tag.rsplit("}", 1)[-1] == "sheet" and node.attrib.get("state", "visible").lower() in {"hidden", "veryhidden"}:
                            findings.append(finding(path, "OOXML_HIDDEN_SHEET", "hidden worksheet is present", "xl/workbook.xml"))
                            break
                except ET.ParseError:
                    findings.append(finding(path, "OOXML_INVALID_XML", "cannot parse workbook XML", "xl/workbook.xml"))

            if path.suffix.lower() == ".pptx":
                for name in sorted(n for n in names if n.startswith("ppt/slides/slide") and n.endswith(".xml")):
                    try:
                        root = ET.fromstring(document.read(name))
                    except ET.ParseError:
                        findings.append(finding(path, "OOXML_INVALID_XML", "cannot parse slide XML", name))
                        continue
                    if root.attrib.get("show", "1").lower() in {"0", "false", "off"} or root.attrib.get("hidden", "false").lower() in {"1", "true", "on"}:
                        findings.append(finding(path, "OOXML_HIDDEN_SLIDE", "hidden slide is present", name))

            tracked = {"ins", "del", "moveFrom", "moveTo", "trackRevisions"}
            for name in sorted(n for n in names if n.startswith("word/") and n.endswith(".xml")):
                try:
                    root = ET.fromstring(document.read(name))
                except ET.ParseError:
                    findings.append(finding(path, "OOXML_INVALID_XML", "cannot parse Word XML", name))
                    continue
                if any(node.tag.rsplit("}", 1)[-1] in tracked for node in root.iter()):
                    findings.append(finding(path, "OOXML_TRACKED_CHANGES", "tracked change markup is present", name))
    except zipfile.BadZipFile:
        # archive_findings has already produced the actionable error.
        pass
    return sorted(findings, key=lambda row: (row["path"], row["code"], row.get("member", ""), row["detail"]))


def pdf_findings(path: Path) -> list[dict[str, str]]:
    pdfinfo = shutil.which("pdfinfo")
    if not pdfinfo:
        raise InspectorError("pdfinfo is required to inspect PDF metadata")
    result = subprocess.run([pdfinfo, str(path)], text=True, capture_output=True)
    if result.returncode:
        return [finding(path, "PDF_INVALID", (result.stderr or result.stdout).strip() or "pdfinfo could not read PDF")]
    fields: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip().lower()] = value.strip()
    findings: list[dict[str, str]] = []
    if fields.get("author", "").strip().lower() not in {"", "none", "(none)"}:
        findings.append(finding(path, "PDF_AUTHOR", "PDF Author metadata is set"))
    if fields.get("encrypted", "").strip().lower().startswith("yes"):
        findings.append(finding(path, "PDF_ENCRYPTED", "PDF is encrypted"))

    js = subprocess.run([pdfinfo, "-js", str(path)], text=True, capture_output=True)
    if js.returncode == 0 and js.stdout.strip():
        findings.append(finding(path, "PDF_JAVASCRIPT", "pdfinfo reports embedded JavaScript"))
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        findings.append(finding(path, "PDF_BODY_SCAN_UNAVAILABLE", "pdftotext is unavailable; PDF body privacy scan was not performed"))
    else:
        body = subprocess.run([pdftotext, str(path), "-"], text=True, capture_output=True)
        if body.returncode:
            findings.append(finding(path, "PDF_BODY_SCAN_FAILED", (body.stderr or body.stdout).strip() or "pdftotext could not extract PDF text"))
        else:
            findings.extend(privacy_findings(path, body.stdout, prefix="PDF_BODY"))
    pdfdetach = shutil.which("pdfdetach")
    if not pdfdetach:
        findings.append(finding(path, "PDF_ATTACHMENT_INVENTORY_UNAVAILABLE", "pdfdetach is unavailable; PDF attachment inventory was not performed"))
    else:
        attachments = subprocess.run([pdfdetach, "-list", str(path)], text=True, capture_output=True)
        if attachments.returncode:
            findings.append(finding(path, "PDF_ATTACHMENT_INVENTORY_FAILED", (attachments.stderr or attachments.stdout).strip() or "pdfdetach could not list PDF attachments"))
        else:
            attachment_rows = [line for line in attachments.stdout.splitlines() if re.match(r"\s*\d+:", line)]
            for line in attachment_rows:
                member = line.split(":", 1)[1].strip() or "embedded attachment"
                findings.append(finding(path, "PDF_ATTACHMENT", "embedded PDF attachment is present", member))
    return sorted(findings, key=lambda row: (row["path"], row["code"], row.get("member", ""), row["detail"]))


def jpeg_findings(path: Path) -> list[dict[str, str]]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise InspectorError(f"cannot read image {path}: {exc}") from exc
    if not data.startswith(b"\xff\xd8"):
        return [finding(path, "JPEG_INVALID", "file lacks JPEG signature")]
    findings: list[dict[str, str]] = []
    cursor = 2
    while cursor + 4 <= len(data):
        if data[cursor] != 0xFF:
            break
        while cursor < len(data) and data[cursor] == 0xFF:
            cursor += 1
        if cursor >= len(data):
            break
        marker = data[cursor]; cursor += 1
        if marker in {0xD8, 0xD9}:
            continue
        if marker == 0xDA:  # Start of Scan: following bytes are compressed image data.
            break
        if cursor + 2 > len(data):
            break
        length = int.from_bytes(data[cursor:cursor + 2], "big")
        if length < 2 or cursor + length > len(data):
            return findings + [finding(path, "JPEG_INVALID", "malformed JPEG segment")]
        payload = data[cursor + 2:cursor + length]
        if marker == 0xE1 and (payload.startswith(b"Exif\x00\x00") or payload.startswith(b"http://ns.adobe.com/xap/1.0/\x00")):
            findings.append(finding(path, "IMAGE_METADATA", "JPEG EXIF or XMP metadata segment"))
        elif marker == 0xED:
            findings.append(finding(path, "IMAGE_METADATA", "JPEG IPTC metadata segment"))
        elif marker == 0xFE:
            findings.append(finding(path, "IMAGE_METADATA", "JPEG comment segment"))
        cursor += length
    return findings


def png_findings(path: Path) -> list[dict[str, str]]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise InspectorError(f"cannot read image {path}: {exc}") from exc
    signature = b"\x89PNG\r\n\x1a\n"
    if not data.startswith(signature):
        return [finding(path, "PNG_INVALID", "file lacks PNG signature")]
    findings: list[dict[str, str]] = []
    cursor = len(signature)
    while cursor + 12 <= len(data):
        size = int.from_bytes(data[cursor:cursor + 4], "big")
        kind = data[cursor + 4:cursor + 8]
        end = cursor + 12 + size
        if end > len(data):
            return findings + [finding(path, "PNG_INVALID", "truncated PNG chunk")]
        if kind in {b"tEXt", b"zTXt", b"iTXt", b"eXIf"}:
            findings.append(finding(path, "IMAGE_METADATA", f"PNG {kind.decode('ascii')} metadata chunk"))
        cursor = end
        if kind == b"IEND":
            break
    return findings


def inspect_file(path: Path) -> list[dict[str, str]]:
    suffix = path.suffix.lower()
    if suffix in {".docx", ".xlsx", ".pptx"}:
        return ooxml_findings(path)
    if suffix == ".zip":
        return archive_findings(path)
    if suffix in {".7z", ".rar", ".tar", ".gz", ".bz2", ".xz"}:
        return [finding(path, "ARCHIVE_UNSUPPORTED_FORMAT", "archive format cannot be inspected safely by the local ZIP-only inspector")]
    if suffix == ".pdf":
        return pdf_findings(path)
    if suffix in {".jpg", ".jpeg"}:
        return jpeg_findings(path)
    if suffix == ".png":
        return png_findings(path)
    return []


def inspect(target: Path) -> list[dict[str, str]]:
    if not target.exists():
        raise InspectorError(f"target does not exist: {target}")
    files = [target] if target.is_file() else sorted(path for path in target.rglob("*") if path.is_file())
    findings: list[dict[str, str]] = []
    for path in files:
        findings.extend(inspect_file(path))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect local release artifacts for metadata and archive-safety findings.")
    parser.add_argument("target", type=Path)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()
    try:
        rows = inspect(args.target)
    except InspectorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps({"target": str(args.target), "count": len(rows), "findings": rows}, ensure_ascii=False, indent=2))
    elif rows:
        for row in rows:
            member = f" [{row['member']}]" if "member" in row else ""
            print(f"{row['code']}: {row['path']}{member}: {row['detail']}")
    else:
        print(f"CLEAN: {args.target}")
    return 1 if rows else 0


if __name__ == "__main__":
    sys.exit(main())

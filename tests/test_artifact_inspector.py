from __future__ import annotations

import hashlib
import json
import io
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import warnings
import zlib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "draft-patents-evidence-first" / "scripts" / "inspect_artifacts.py"


def write_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in members.items():
            archive.writestr(name, value)


def manifest_record(name: str, payload: bytes, **overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "path": name,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    record.update(overrides)
    return record


def write_manifest_zip(path: Path, members: dict[str, bytes], records: list[dict[str, object]] | None = None) -> None:
    manifest = json.dumps({"schema_version": "0.1.0", "files": records or [manifest_record(name, payload) for name, payload in members.items()]}).encode()
    write_zip(path, {**members, "manifest.json": manifest})


def write_docx(path: Path, *, tainted: bool = False) -> None:
    members = {
        "[Content_Types].xml": b"<Types/>",
        "word/document.xml": b'<w:document xmlns:w="urn:test"><w:body><w:p/></w:body></w:document>',
    }
    if tainted:
        members.update({
            "docProps/core.xml": b'<cp:coreProperties xmlns:cp="urn:cp" xmlns:dc="urn:dc"><dc:creator>Ada</dc:creator><cp:lastModifiedBy>Lin</cp:lastModifiedBy></cp:coreProperties>',
            "docProps/custom.xml": b"<Properties/>",
            "word/comments.xml": b"<w:comments xmlns:w='urn:test'/>",
            "word/embeddings/oleObject1.bin": b"embedded",
            "word/vbaProject.bin": b"macro",
            "word/_rels/document.xml.rels": b'<Relationships><Relationship Target="https://example.test" TargetMode="External"/></Relationships>',
            "word/document.xml": b'<w:document xmlns:w="urn:test"><w:body><w:ins><w:r/></w:ins></w:body></w:document>',
        })
    write_zip(path, members)


def write_ooxml(path: Path, members: dict[str, bytes]) -> None:
    write_zip(path, {"[Content_Types].xml": b"<Types/>", **members})


def write_text_pdf(path: Path, text: str) -> None:
    """Create a tiny valid PDF with selectable text using no test dependency."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(out)


def png(chunks: list[tuple[bytes, bytes]]) -> bytes:
    out = bytearray(b"\x89PNG\r\n\x1a\n")
    for kind, data in chunks:
        out += struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return bytes(out)


def jpeg(*, exif: bool = False, compressed_marker_text: bool = False) -> bytes:
    parts = [b"\xff\xd8"]
    if exif:
        payload = b"Exif\x00\x00metadata"
        parts.append(b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload)
    payload = b"Exif\x00\x00inside-image-data" if compressed_marker_text else b"pixels"
    parts += [b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00", payload, b"\xff\xd9"]
    return b"".join(parts)


class ArtifactInspectorTest(unittest.TestCase):
    def run_inspector(self, target: Path, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), str(target), "--format", "json"], text=True, capture_output=True, env=env)

    def codes(self, result: subprocess.CompletedProcess[str]) -> set[str]:
        return {row["code"] for row in json.loads(result.stdout)["findings"]}

    def test_clean_directory_and_compressed_bytes_are_not_misread_as_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_docx(root / "clean.docx")
            payload = b"ordinary compressed content"
            write_zip(root / "release.zip", {"payload.txt": payload})
            (root / "manifest.json").write_text(json.dumps({"files": [manifest_record("payload.txt", payload)]}), encoding="utf-8")
            (root / "clean.png").write_bytes(png([(b"IHDR", b"\x00" * 13), (b"IDAT", b"tEXt embedded in compressed pixels"), (b"IEND", b"")]))
            (root / "clean.jpg").write_bytes(jpeg(compressed_marker_text=True))
            result = self.run_inspector(root)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(json.loads(result.stdout)["count"], 0)

    def test_zip_crc_traversal_and_manifest_members_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            traversal = root / "traversal.zip"
            write_zip(traversal, {"../escape.txt": b"bad", "extra.txt": b"also bad"})
            (root / "manifest.json").write_text(json.dumps({"files": [manifest_record("allowed.txt", b"allowed")]}), encoding="utf-8")
            result = self.run_inspector(traversal)
            self.assertEqual(result.returncode, 1)
            self.assertTrue({"ZIP_PATH_TRAVERSAL", "ZIP_UNDECLARED_MEMBER", "ZIP_MISSING_MEMBER"}.issubset(self.codes(result)))

            corrupt = root / "corrupt.zip"
            with zipfile.ZipFile(corrupt, "w", zipfile.ZIP_STORED) as archive:
                archive.writestr("payload.txt", b"a payload that can be damaged")
            with zipfile.ZipFile(corrupt) as archive:
                info = archive.getinfo("payload.txt")
            data = bytearray(corrupt.read_bytes())
            offset = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
            data[offset] ^= 0x01
            corrupt.write_bytes(data)
            result = self.run_inspector(corrupt)
            self.assertEqual(result.returncode, 1)
            self.assertIn("ZIP_CRC_FAILURE", self.codes(result))

    def test_manifest_zip_checks_hash_size_missing_extra_and_duplicate_members(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = b"content-addressed payload"

            clean = root / "clean.zip"
            write_manifest_zip(clean, {"payload.txt": payload})
            result = self.run_inspector(clean)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            bad_hash = root / "bad-hash.zip"
            write_manifest_zip(bad_hash, {"payload.txt": payload}, [manifest_record("payload.txt", payload, sha256="0" * 64)])
            result = self.run_inspector(bad_hash)
            self.assertEqual(result.returncode, 1)
            self.assertIn("ZIP_MANIFEST_SHA256_MISMATCH", self.codes(result))

            bad_size = root / "bad-size.zip"
            write_manifest_zip(bad_size, {"payload.txt": payload}, [manifest_record("payload.txt", payload, bytes=len(payload) + 1)])
            result = self.run_inspector(bad_size)
            self.assertEqual(result.returncode, 1)
            self.assertIn("ZIP_MANIFEST_SIZE_MISMATCH", self.codes(result))

            missing = root / "missing.zip"
            write_manifest_zip(missing, {}, [manifest_record("payload.txt", payload)])
            result = self.run_inspector(missing)
            self.assertEqual(result.returncode, 1)
            self.assertIn("ZIP_MISSING_MEMBER", self.codes(result))

            extra = root / "extra.zip"
            write_manifest_zip(extra, {"payload.txt": payload, "extra.txt": b"extra"}, [manifest_record("payload.txt", payload)])
            result = self.run_inspector(extra)
            self.assertEqual(result.returncode, 1)
            self.assertIn("ZIP_UNDECLARED_MEMBER", self.codes(result))

            duplicate = root / "duplicate.zip"
            manifest = json.dumps({"files": [manifest_record("payload.txt", payload)]}).encode()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(duplicate, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("payload.txt", payload)
                    archive.writestr("payload.txt", payload)
                    archive.writestr("manifest.json", manifest)
            result = self.run_inspector(duplicate)
            self.assertEqual(result.returncode, 1)
            self.assertIn("ZIP_DUPLICATE_MEMBER", self.codes(result))

    def test_ooxml_personal_metadata_review_history_and_active_content_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            document = Path(temp) / "tainted.docx"
            write_docx(document, tainted=True)
            result = self.run_inspector(document)
            self.assertEqual(result.returncode, 1)
            expected = {
                "OOXML_PERSONAL_METADATA", "OOXML_COMMENTS", "OOXML_TRACKED_CHANGES",
                "OOXML_CUSTOM_PROPERTIES", "OOXML_EXTERNAL_RELATIONSHIP", "OOXML_MACRO", "OOXML_EMBEDDED_FILE",
            }
            self.assertTrue(expected.issubset(self.codes(result)), result.stdout)

    def test_nested_zip_sensitive_content_is_bounded_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            outer = Path(temp) / "outer.zip"
            inner_buffer = io.BytesIO()
            with zipfile.ZipFile(inner_buffer, "w", zipfile.ZIP_DEFLATED) as inner:
                inner.writestr("private.txt", ("sk" + "-" + "A" * 20).encode())
            write_zip(outer, {"nested.zip": inner_buffer.getvalue()})
            result = self.run_inspector(outer)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("ARCHIVE_SECRET", self.codes(result))
            rows = json.loads(result.stdout)["findings"]
            self.assertTrue(any(row.get("member") == "nested.zip!private.txt" for row in rows), result.stdout)

    def test_unsupported_archive_format_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "uninspectable.rar"
            archive.write_bytes(b"not a ZIP archive")
            result = self.run_inspector(archive)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("ARCHIVE_UNSUPPORTED_FORMAT", self.codes(result))

    def test_archive_entry_limit_is_explicit_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "many-members.zip"
            write_zip(archive, {f"items/{number}.txt": b"" for number in range(1_001)})
            result = self.run_inspector(archive)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("ZIP_ENTRY_LIMIT", self.codes(result))

    def test_hidden_xlsx_and_pptx_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workbook = root / "hidden.xlsx"
            write_ooxml(workbook, {"xl/workbook.xml": b'<workbook xmlns="urn:test"><sheets><sheet name="Hidden" state="veryHidden"/></sheets></workbook>'})
            result = self.run_inspector(workbook)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("OOXML_HIDDEN_SHEET", self.codes(result))
            presentation = root / "hidden.pptx"
            write_ooxml(presentation, {
                "ppt/presentation.xml": b'<p:presentation xmlns:p="urn:test"/>',
                "ppt/slides/slide1.xml": b'<p:sld xmlns:p="urn:test" show="0"/>',
            })
            result = self.run_inspector(presentation)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("OOXML_HIDDEN_SLIDE", self.codes(result))

    def test_png_and_jpeg_metadata_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / "meta.png"
            image.write_bytes(png([(b"IHDR", b"\x00" * 13), (b"tEXt", b"Author\x00Ada"), (b"IEND", b"")]))
            result = self.run_inspector(image)
            self.assertEqual(result.returncode, 1)
            self.assertIn("IMAGE_METADATA", self.codes(result))
            photo = root / "meta.jpg"; photo.write_bytes(jpeg(exif=True))
            result = self.run_inspector(photo)
            self.assertEqual(result.returncode, 1)
            self.assertIn("IMAGE_METADATA", self.codes(result))

    def test_pdfinfo_author_javascript_encryption_and_missing_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); pdf = root / "sample.pdf"; pdf.write_bytes(b"%PDF-1.4\n")
            fake_bin = root / "bin"; fake_bin.mkdir(); fake = fake_bin / "pdfinfo"
            fake.write_text("#!/bin/sh\nif [ \"$1\" = \"-js\" ]; then echo 'app.alert(1)'; exit 0; fi\necho 'Author: Ada'\necho 'Encrypted: yes (print:no copy:no change:no addNotes:no)'\n", encoding="utf-8")
            fake.chmod(0o755)
            env = {**os.environ, "PATH": str(fake_bin)}
            result = self.run_inspector(pdf, env=env)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertTrue({"PDF_AUTHOR", "PDF_JAVASCRIPT", "PDF_ENCRYPTED"}.issubset(self.codes(result)))
            result = self.run_inspector(pdf, env={**os.environ, "PATH": str(root / "missing")})
            self.assertEqual(result.returncode, 2)
            self.assertIn("pdfinfo is required", result.stderr)

    @unittest.skipUnless(shutil.which("pdftotext") and shutil.which("pdfdetach") and shutil.which("pdfinfo"), "local Poppler tools unavailable")
    def test_pdf_body_contact_is_reported_when_local_tools_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "contact.pdf"
            write_text_pdf(pdf, "privacy" + "@example.test")
            result = self.run_inspector(pdf)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("PDF_BODY_CONTACT", self.codes(result))


if __name__ == "__main__":
    unittest.main()

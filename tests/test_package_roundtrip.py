from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill" / "draft-patents-evidence-first" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_acceptance as acceptance  # noqa: E402
from evidence_first_lib import FULL_LEGAL_DISCLAIMER_EN, FULL_LEGAL_DISCLAIMER_ZH, case_paths, dump_jsonl  # noqa: E402


class PortablePackageTest(unittest.TestCase):
    def test_roundtrip_extractor_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("../outside.txt", "blocked")
            with self.assertRaisesRegex(ValueError, "unsafe archive member"):
                acceptance.safe_extract_package(archive, root / "extract")

    def test_md_package_retains_a_directly_validatable_case_record(self) -> None:
        fixture = {"id": "ZH-INV-01", "language": "zh-CN", "patent_type": "invention"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case = acceptance.make_base_case(root, fixture)
            # Keep this package-mechanics test narrowly about portable records.  The
            # source itself states the same structural proposition as the trace.
            paths = case_paths(case)
            source = paths["input"] / "source.md"
            source.write_text("一种夹具包括弹性压持结构且间距为10 mm。\n", encoding="utf-8")
            sources = [json.loads(line) for line in paths["sources"].read_text(encoding="utf-8").splitlines() if line]
            evidence = [json.loads(line) for line in paths["evidence"].read_text(encoding="utf-8").splitlines() if line]
            sources[0]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
            evidence[0]["verbatim"] = source.read_text(encoding="utf-8").strip()
            dump_jsonl(paths["sources"], sources)
            dump_jsonl(paths["evidence"], evidence)
            for artifact in paths["output"].iterdir():
                artifact.unlink()
            (paths["output"] / "claims.md").write_text(
                "# Claim framework\n\n1. 一种包括弹性压持结构且间距为10 mm的夹具。\n\n"
                + FULL_LEGAL_DISCLAIMER_EN + "\n\n" + FULL_LEGAL_DISCLAIMER_ZH + "\n",
                encoding="utf-8",
            )
            acceptance.refresh_stages(paths)
            package = root / "portable-package"
            build = subprocess.run(
                [sys.executable, str(SCRIPTS / "build_package.py"), str(case), "--format", "md", "--output", str(package)],
                text=True,
                capture_output=True,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
            canonical = acceptance.canonical_records(package)
            self.assertTrue((package / "case.yaml").is_file())
            self.assertTrue((package / "input" / "source.md").is_file())
            self.assertTrue(manifest["case_package"]["portable_case_record"])
            self.assertEqual(sorted(manifest["case_package"]["canonical_case_files"]), sorted(canonical))

            extracted = root / "extracted"
            acceptance.safe_extract_package(package.with_suffix(".zip"), extracted)
            validate = subprocess.run([sys.executable, str(SCRIPTS / "validate_case.py"), str(extracted)], text=True, capture_output=True)
            self.assertEqual(validate.returncode, 0, validate.stderr)
            rebuilt = root / "rebuilt"
            roundtrip = subprocess.run(
                [sys.executable, str(SCRIPTS / "build_package.py"), str(extracted), "--format", "md", "--output", str(rebuilt)],
                text=True,
                capture_output=True,
            )
            self.assertEqual(roundtrip.returncode, 0, roundtrip.stderr)
            self.assertEqual(canonical, acceptance.canonical_records(extracted))
            self.assertEqual(canonical, acceptance.canonical_records(rebuilt))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

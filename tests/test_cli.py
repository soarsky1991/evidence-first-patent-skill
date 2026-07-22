from __future__ import annotations

import json
import os
import hashlib
import subprocess
import sys
import tempfile
import unittest
import warnings
import importlib.util
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skill" / "draft-patents-evidence-first" / "scripts"


class ContractSmokeTest(unittest.TestCase):
    def run_script(self, name: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)], text=True, capture_output=True, env=env)

    def test_init_and_basic_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            case = Path(temp) / "demo"
            result = self.run_script("init_case.py", case, "--case-id", "demo-case", "--language", "zh-CN", "--patent-type", "invention")
            self.assertEqual(result.returncode, 0, result.stderr)
            result = self.run_script("validate_case.py", case)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = self.run_script("scan_sensitive.py", case, "--format", "json")
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_duplicate_family_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            case = Path(temp) / "demo"
            self.assertEqual(self.run_script("init_case.py", case, "--case-id", "demo-case", "--language", "en-US", "--patent-type", "invention").returncode, 0)
            source = {"source_id":"SRC-0001","source_type":"patent","title":"US1234567","locator":"https://example.invalid/a","sha256":None,"publication_date":"2020-01-01","accessed_at":"2020-01-02","family_id":"FAM-1","license":None,"language":"en-US","public_status":"public","verification_status":"verified"}
            duplicate = dict(source, source_id="SRC-0002", locator="https://example.invalid/b")
            (case / "work" / "sources.jsonl").write_text("\n".join(json.dumps(x) for x in [source, duplicate]) + "\n", encoding="utf-8")
            result = self.run_script("dedupe_families.py", case, "--check")
            self.assertEqual(result.returncode, 1)
            result = self.run_script("dedupe_families.py", case)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.run_script("dedupe_families.py", case, "--check").returncode, 0)

    def test_trace_and_markdown_package_after_human_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            case = Path(temp) / "demo"
            self.assertEqual(self.run_script("init_case.py", case, "--case-id", "demo-case", "--language", "zh-CN", "--patent-type", "invention").returncode, 0)
            source_path = case / "input" / "source.md"; source_path.write_text("一种包括弹性压持结构的夹具。", encoding="utf-8")
            source = {"source_id":"SRC-0001","source_type":"synthetic","title":"Synthetic source","locator":"input/source.md","sha256":hashlib.sha256(source_path.read_bytes()).hexdigest(),"publication_date":None,"accessed_at":None,"family_id":None,"license":"CC BY 4.0","language":"zh-CN","public_status":"synthetic","verification_status":"verified"}
            evidence = {"evidence_id":"EV-0001","source_id":"SRC-0001","source_location":{"paragraph":"p1"},"verbatim":"一种包括弹性压持结构的夹具。","statement":"一种包括弹性压持结构的夹具。","evidence_class":"designed","verification_status":"verified","public_status":"synthetic","derived_from":[],"review_notes":""}
            trace = {"claim_id":"CLM-001","claim_number":1,"parent_claim_number":None,"limitation_id":"LIM-0001","language":"zh-CN","limitation_text":"一种包括弹性压持结构的夹具。","evidence_ids":["EV-0001"],"semantic_status":"designed","human_review_status":"accepted","paired_limitation_id":None}
            for filename, row in [("sources.jsonl", source), ("evidence.jsonl", evidence), ("claim_trace.jsonl", trace)]:
                (case / "work" / filename).write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
            config = (case / "case.yaml").read_text(encoding="utf-8").replace("selected_concept_id: null", 'selected_concept_id: "CON-0001"').replace("approved_by: null", 'approved_by: "reviewer"').replace("approved_at: null", 'approved_at: "2026-01-01T00:00:00Z"').replace("public_boundary_confirmed: false", "public_boundary_confirmed: true")
            (case / "case.yaml").write_text(config, encoding="utf-8")
            score = json.loads((case / "work" / "scorecard.json").read_text(encoding="utf-8"))
            score.update({"evidence_coverage_pct":100.0,"claim_trace_coverage_pct":100.0,"unsupported_measured_claims":0,"duplicate_patent_families":0,"confidentiality_findings":0,"blocking_findings":[],"status":"CANDIDATE_CHECKS_PASSED"})
            (case / "work" / "scorecard.json").write_text(json.dumps(score), encoding="utf-8")
            (case / "output" / "claims.md").write_text("# Claim framework\n\n1. 一种包括弹性压持结构的夹具。\n", encoding="utf-8")
            (case / "output" / "prior_art.md").write_text("# Prior art\n", encoding="utf-8")
            self.assertEqual(self.run_script("trace_claims.py", case, "--check").returncode, 0)
            missing_renderer = self.run_script("build_package.py", case, "--format", "pdf", "--output", case / "package" / "no-renderer", env={**os.environ, "PATH": "/nonexistent"})
            self.assertEqual(missing_renderer.returncode, 2, missing_renderer.stderr)
            result = self.run_script("build_package.py", case, "--format", "md", "--output", case / "package" / "release")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((case / "package" / "release.zip").exists())

    def test_scanner_uses_real_token_shapes_and_does_not_flag_skill_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); workflow = root / ".workflow"; workflow.mkdir()
            (workflow / "test-report.json").write_text("portable report", encoding="utf-8")
            (root / "usage.txt").write_text("python quick_validate.py <skill_directory>", encoding="utf-8")
            clean = self.run_script("scan_sensitive.py", root, "--format", "json")
            self.assertEqual(clean.returncode, 0, clean.stdout)
            seeds = ["sk" + "-" + "A" * 20, "ghp_" + "A" * 36, "github_pat_" + "A" * 22, "AKIA" + "A" * 16]
            (root / "release.txt").write_text("\n".join(seeds), encoding="utf-8")
            blocked = self.run_script("scan_sensitive.py", root, "--format", "json")
            self.assertEqual(blocked.returncode, 1, blocked.stdout)
            self.assertEqual(json.loads(blocked.stdout)["count"], 4)

    def test_achieved_result_detection_covers_common_phrasing_without_target_false_positives(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        spec = importlib.util.spec_from_file_location("validate_case_under_test", SCRIPTS / "validate_case.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for sentence in (
            "The trial achieved a 30% gain.",
            "The prototype yielded lower drift.",
            "The coating reduced wear and enhanced durability.",
            "The experiment demonstrated, confirmed, and measured the result.",
            "The observation reached the threshold and resulted in stable output.",
            "样机实现了稳定定位，达到目标精度并降低了误差。",
            "试验提升了性能，改善了响应，测得10 mm，验证表明结果为合格。",
        ):
            self.assertTrue(module.is_unsupported_achieved(sentence), sentence)
        for sentence in (
            "The target is to achieve a 30% gain, to be verified.",
            "No result was measured or confirmed.",
            "拟达到10 mm，待验证。",
            "尚未测得结果，目标为降低误差。",
        ):
            self.assertFalse(module.is_unsupported_achieved(sentence), sentence)

    def test_bilingual_atom_map_detects_every_required_scope_class(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        from compare_bilingual import validate_bilingual_rows

        zh_text = "一种包括弹性压持结构且间距为10 mm的夹具。"
        en_text = "A fixture comprising a resilient pressing structure with a spacing of 10 mm."
        def make(language: str, limitation_id: str, pair: str, text: str, atoms: list[tuple[str, str, str]], parent=None) -> dict:
            return {
                "claim_id":"CLM-001", "claim_number":1, "parent_claim_number":parent,
                "limitation_id":limitation_id, "language":language, "limitation_text":text,
                "limitation_text_sha256":hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "atom_map":[{"type":kind,"canonical":canonical,"text_span":span} for kind,canonical,span in atoms],
                "evidence_ids":["EV-0001"], "semantic_status":"designed", "human_review_status":"accepted", "paired_limitation_id":pair,
            }
        base_atoms = [
            ("object","fixture","夹具"),("component_or_step","resilient_pressing_structure","弹性压持结构"),
            ("relationship","spacing","间距"),("numeric_bound","10mm","10 mm"),("modality","open","包括"),
        ]
        en_atoms = [
            ("object","fixture","fixture"),("component_or_step","resilient_pressing_structure","resilient pressing structure"),
            ("relationship","spacing","spacing"),("numeric_bound","10mm","10 mm"),("modality","open","comprising"),
        ]
        zh = make("zh-CN","LIM-0001","LIM-0002",zh_text,base_atoms)
        aligned = make("en-US","LIM-0002","LIM-0001",en_text,en_atoms)
        self.assertEqual(validate_bilingual_rows([zh, aligned]), [])
        mutations = {
            "object": ("sensor", "fixture"),
            "component_or_step": ("rigid_pressing_structure", "resilient pressing structure"),
            "relationship": ("offset", "spacing"),
            "numeric_bound": ("12mm", "10 mm"),
            "condition": ("during_heating", "fixture"),
            "modality": ("closed", "comprising"),
        }
        for kind, (canonical, span) in mutations.items():
            changed = json.loads(json.dumps(aligned))
            if kind == "condition":
                changed["atom_map"].append({"type":kind,"canonical":canonical,"text_span":span})
            else:
                next(atom for atom in changed["atom_map"] if atom["type"] == kind)["canonical"] = canonical
            differences = validate_bilingual_rows([zh, changed])
            self.assertTrue(differences and any(item["atom_type"] == kind for item in differences[0]["differences"]), kind)
        dependency = json.loads(json.dumps(aligned)); dependency["parent_claim_number"] = 1
        differences = validate_bilingual_rows([zh, dependency])
        self.assertTrue(any(item["atom_type"] == "dependency" for item in differences[0]["differences"]))

    def test_untraced_rendered_claim_cannot_keep_a_100_percent_score(self) -> None:
        """An inventory comparison must reject a claim omitted from claim_trace.jsonl."""
        sys.path.insert(0, str(SCRIPTS))
        from evidence_first_lib import dump_json, dump_jsonl, refresh_complete_stage_hashes
        with tempfile.TemporaryDirectory() as temp:
            case = Path(temp) / "inventory"
            self.assertEqual(self.run_script("init_case.py", case, "--case-id", "inventory-case", "--language", "en-US", "--patent-type", "invention").returncode, 0)
            source_path = case / "input" / "source.md"; source_path.write_text("Synthetic fixture comprising a resilient pressing structure.", encoding="utf-8")
            source = {"source_id":"SRC-0001","source_type":"synthetic","title":"synthetic","locator":"input/source.md","sha256":hashlib.sha256(source_path.read_bytes()).hexdigest(),"publication_date":None,"accessed_at":None,"family_id":None,"license":"CC BY 4.0","language":"en-US","public_status":"synthetic","verification_status":"verified"}
            evidence = {"evidence_id":"EV-0001","source_id":"SRC-0001","source_location":{"paragraph":"p1"},"verbatim":source_path.read_text(encoding="utf-8").strip(),"statement":"proposed fixture structure","evidence_class":"designed","verification_status":"verified","public_status":"synthetic","derived_from":[],"review_notes":""}
            trace = {"claim_id":"CLM-001","claim_number":1,"parent_claim_number":None,"limitation_id":"LIM-0001","language":"en-US","limitation_text":"A fixture comprising a resilient pressing structure.","evidence_ids":["EV-0001"],"semantic_status":"designed","human_review_status":"accepted","paired_limitation_id":None}
            dump_jsonl(case / "work" / "sources.jsonl", [source]); dump_jsonl(case / "work" / "evidence.jsonl", [evidence]); dump_jsonl(case / "work" / "claim_trace.jsonl", [trace])
            config = (case / "case.yaml").read_text(encoding="utf-8").replace("selected_concept_id: null", 'selected_concept_id: "CON-0001"').replace("approved_by: null", 'approved_by: "reviewer"').replace("approved_at: null", 'approved_at: "2026-01-01T00:00:00Z"').replace("public_boundary_confirmed: false", "public_boundary_confirmed: true")
            (case / "case.yaml").write_text(config, encoding="utf-8")
            score = json.loads((case / "work" / "scorecard.json").read_text(encoding="utf-8")); score.update({"evidence_coverage_pct":100.0,"claim_trace_coverage_pct":100.0,"unsupported_measured_claims":0,"duplicate_patent_families":0,"bilingual_atomic_consistency_pct":None,"blocking_findings":[],"status":"CANDIDATE_CHECKS_PASSED"}); dump_json(case / "work" / "scorecard.json", score)
            (case / "output" / "claims.md").write_text("# Claims\n\n1. A fixture comprising a resilient pressing structure.\n2. The fixture of claim 1 further comprising an untraced rigid blade.\n", encoding="utf-8")
            paths = {"input":case / "input","output":case / "output","sources":case / "work" / "sources.jsonl","evidence":case / "work" / "evidence.jsonl","trace":case / "work" / "claim_trace.jsonl","scorecard":case / "work" / "scorecard.json","stages":case / "work" / "stage_status.json","case":case / "case.yaml"}
            dump_json(case / "work" / "stage_status.json", refresh_complete_stage_hashes(paths))
            result = self.run_script("validate_case.py", case)
            self.assertEqual(result.returncode, 1)
            self.assertRegex(result.stderr, r"rendered claim(?:s| atom) inventory differs")

    def test_measurement_match_utility_gate_and_stage_reset_adversaries(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        from evidence_first_lib import reset_downstream_stages, validate_evidence, ValidationError
        spec = importlib.util.spec_from_file_location("validate_case_under_test", SCRIPTS / "validate_case.py")
        assert spec and spec.loader; validator = importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)
        measured = {"evidence_id":"EV-0001","evidence_class":"measured","verification_status":"verified","source_location":{"paragraph":"p1"},"statement":"ambient temperature was 20 C","verbatim":"ambient temperature was 20 C","measurement":{"method":"thermometer","context":"ambient","result":"20 C"}}
        self.assertFalse(validator._achieved_evidence_matches("Testing proved that accuracy improved by 30%.", [measured]))
        measured["statement"] = "testing proved accuracy improved by 30%"; measured["verbatim"] = measured["statement"]; measured["measurement"] = {"method":"accuracy test","context":"fixture","result":"accuracy improved by 30%"}
        self.assertTrue(validator._achieved_evidence_matches("Testing proved that accuracy improved by 30%.", [measured]))
        self.assertFalse(validator._utility_model_is_structural("一种用于加热试件的方法，包括将试件放入加热区。"))
        self.assertFalse(validator._utility_model_is_structural("A technique for heating a specimen, comprising applying heat."))
        self.assertTrue(validator._utility_model_is_structural("A fixture comprising a pressing member connected to a housing."))
        stages = [{"stage":number,"status":"complete","input_hash":"x","output_hash":"y","updated_at":"old","blocking_reasons":["old"]} for number in range(1, 11)]
        reset = reset_downstream_stages({}, 8, stages)
        self.assertTrue(all(row["status"] == "pending" and row["input_hash"] is None and row["output_hash"] is None for row in reset[8:]))
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.txt"; source.write_text("actual source bytes", encoding="utf-8")
            rows = [{"evidence_id":"EV-0001","source_id":"SRC-0001","source_location":{"paragraph":"p1"},"verbatim":"fabricated quotation","statement":"documented item","evidence_class":"documented","verification_status":"verified","public_status":"synthetic","derived_from":[],"review_notes":""}]
            sources = [{"source_id":"SRC-0001","locator":"source.txt"}]
            with self.assertRaisesRegex(ValidationError, "verbatim is not bound"):
                validate_evidence(rows, sources, Path(temp))

    def test_state_gate_red_team_regressions(self) -> None:
        """Adversarial cases for language, recursive hashing, gates, and prior-art disposition."""
        sys.path.insert(0, str(SCRIPTS))
        from evidence_first_lib import (
            ValidationError, canonical_hash, dump_case_yaml, dump_json, dump_jsonl,
            expected_stage_hashes, load_case_yaml, refresh_complete_stage_hashes,
        )

        def write_complete_case(case: Path, *, language: str = "en-US", patent_type: str = "invention", claim_rows: list[dict] | None = None) -> None:
            self.assertEqual(self.run_script("init_case.py", case, "--case-id", "state-gate-case", "--language", language, "--patent-type", patent_type, "--critical-date", "2024-01-01").returncode, 0)
            source_path = case / "input" / "nested" / "source.md"; source_path.parent.mkdir(); source_path.write_text("A fixture comprising a resilient pressing structure.", encoding="utf-8")
            source = {"source_id":"SRC-0001","source_type":"synthetic","title":"synthetic","locator":"input/nested/source.md","sha256":hashlib.sha256(source_path.read_bytes()).hexdigest(),"publication_date":None,"accessed_at":None,"family_id":None,"license":"CC BY 4.0","language":"en-US","public_status":"synthetic","verification_status":"verified"}
            evidence = {"evidence_id":"EV-0001","source_id":"SRC-0001","source_location":{"paragraph":"p1"},"verbatim":source_path.read_text(encoding="utf-8").strip(),"statement":"proposed fixture structure","evidence_class":"designed","verification_status":"verified","public_status":"synthetic","derived_from":[],"review_notes":""}
            rows = claim_rows or [{"claim_id":"CLM-001","claim_number":1,"parent_claim_number":None,"limitation_id":"LIM-0001","language":"en-US","limitation_text":"A fixture comprising a resilient pressing structure.","evidence_ids":["EV-0001"],"semantic_status":"designed","human_review_status":"accepted","paired_limitation_id":None}]
            dump_jsonl(case / "work" / "sources.jsonl", [source]); dump_jsonl(case / "work" / "evidence.jsonl", [evidence]); dump_jsonl(case / "work" / "claim_trace.jsonl", rows)
            config = load_case_yaml(case / "case.yaml"); config["human_gate"] = {"selected_concept_id":"CON-0001","approved_by":"reviewer","approved_at":"2026-01-01T00:00:00Z","public_boundary_confirmed":True}; dump_case_yaml(case / "case.yaml", config)
            dump_json(case / "work" / "scorecard.json", {"schema_version":"0.1.0","generated_at":"2026-01-01T00:00:00Z","evidence_coverage_pct":100.0,"unsupported_measured_claims":0,"duplicate_patent_families":0,"claim_trace_coverage_pct":100.0,"bilingual_atomic_consistency_pct":None,"confidentiality_findings":0,"blocking_findings":[],"status":"CANDIDATE_CHECKS_PASSED"})
            (case / "output" / "claims.md").write_text("# Claims\n\n" + "\n".join(f"{row['claim_number']}. {row['limitation_text']}" for row in rows) + "\n", encoding="utf-8")
            paths = {"input":case / "input","output":case / "output","sources":case / "work" / "sources.jsonl","evidence":case / "work" / "evidence.jsonl","trace":case / "work" / "claim_trace.jsonl","scorecard":case / "work" / "scorecard.json","case":case / "case.yaml","stages":case / "work" / "stage_status.json"}
            dump_json(paths["stages"], refresh_complete_stage_hashes(paths))

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); input_root = root / "input"; (input_root / "a").mkdir(parents=True); (input_root / "a" / "same.txt").write_text("same", encoding="utf-8")
            first = canonical_hash([input_root]); (input_root / "b").mkdir(); (input_root / "b" / "same.txt").write_text("same", encoding="utf-8")
            self.assertNotEqual(first, canonical_hash([input_root]), "relative nested paths must affect input hash")
            os.symlink(input_root / "a" / "same.txt", input_root / "linked.txt")
            with self.assertRaisesRegex(ValidationError, "rejects symlink"):
                canonical_hash([input_root])

        with tempfile.TemporaryDirectory() as temp:
            case = Path(temp) / "auto"; write_complete_case(case, language="auto")
            stages = json.loads((case / "work" / "stage_status.json").read_text(encoding="utf-8")); stages[0]["resolved_language"] = "en-US"; dump_json(case / "work" / "stage_status.json", stages)
            # A completed auto case can only be made valid after the trace/output are in
            # the resolved language; the resolver must also clear every dependent stage.
            resolved = self.run_script("resolve_language.py", case, "--language", "zh-CN")
            self.assertEqual(resolved.returncode, 0, resolved.stderr)
            stages = json.loads((case / "work" / "stage_status.json").read_text(encoding="utf-8"))
            self.assertEqual(stages[0]["status"], "complete")
            self.assertTrue(all(row["status"] == "pending" and row["input_hash"] is None and row["output_hash"] is None for row in stages[1:]))
            self.assertEqual(self.run_script("validate_case.py", case).returncode, 1)
            self.assertIn("claim trace language", self.run_script("validate_case.py", case).stderr)
            trace = [json.loads(line) for line in (case / "work" / "claim_trace.jsonl").read_text(encoding="utf-8").splitlines()]
            trace[0]["language"] = "zh-CN"; dump_jsonl(case / "work" / "claim_trace.jsonl", trace)
            result = self.run_script("validate_case.py", case)
            self.assertEqual(result.returncode, 1); self.assertIn("rendered claim output language", result.stderr)

        with tempfile.TemporaryDirectory() as temp:
            method = {"claim_id":"CLM-002","claim_number":2,"parent_claim_number":None,"limitation_id":"LIM-0002","language":"en-US","limitation_text":"A method comprising heating a specimen.","evidence_ids":["EV-0001"],"semantic_status":"designed","human_review_status":"accepted","paired_limitation_id":None}
            case = Path(temp) / "utility"; write_complete_case(case, patent_type="utility_model", claim_rows=[{"claim_id":"CLM-001","claim_number":1,"parent_claim_number":None,"limitation_id":"LIM-0001","language":"en-US","limitation_text":"A fixture comprising a resilient pressing structure.","evidence_ids":["EV-0001"],"semantic_status":"designed","human_review_status":"accepted","paired_limitation_id":None}, method])
            result = self.run_script("validate_case.py", case)
            self.assertEqual(result.returncode, 1); self.assertIn("every utility-model independent claim", result.stderr)

        with tempfile.TemporaryDirectory() as temp:
            case = Path(temp) / "prior"; write_complete_case(case)
            sources = [json.loads(line) for line in (case / "work" / "sources.jsonl").read_text(encoding="utf-8").splitlines()]
            sources[0].update(source_type="patent", title="CN123456789", locator="https://example.invalid/CN123456789", sha256=None, canonical_url="https://example.invalid/CN123456789", publication_date="2025-01-01", accessed_at="2025-01-02", public_status="public")
            dump_jsonl(case / "work" / "sources.jsonl", sources); (case / "output" / "prior_art.md").write_text("SRC-0001 is qualifying prior art.", encoding="utf-8")
            paths = {"input":case / "input","output":case / "output","sources":case / "work" / "sources.jsonl","evidence":case / "work" / "evidence.jsonl","trace":case / "work" / "claim_trace.jsonl","scorecard":case / "work" / "scorecard.json","case":case / "case.yaml","stages":case / "work" / "stage_status.json"}; dump_json(paths["stages"], refresh_complete_stage_hashes(paths))
            rendered_only = self.run_script("validate_case.py", case)
            self.assertEqual(rendered_only.returncode, 1, "rendered qualifying disposition must obey the critical date")
            self.assertIn("post-critical-date patent", rendered_only.stderr)
            sources[0]["comparison"] = {"disposition":"qualifying_prior_art"}; dump_jsonl(case / "work" / "sources.jsonl", sources); dump_json(paths["stages"], refresh_complete_stage_hashes(paths))
            result = self.run_script("validate_case.py", case); self.assertEqual(result.returncode, 1); self.assertIn("post-critical-date patent", result.stderr)
            before = expected_stage_hashes(paths); config = load_case_yaml(case / "case.yaml"); config["human_gate"]["approved_by"] = "reviewer-two"; dump_case_yaml(case / "case.yaml", config); after = expected_stage_hashes(paths)
            self.assertTrue(all(before[number] != after[number] for number in (8, 9, 10)))
            config["human_gate"]["approved_at"] = "2026-99-99T25:61:61Z"; dump_case_yaml(case / "case.yaml", config)
            result = self.run_script("validate_case.py", case); self.assertEqual(result.returncode, 1); self.assertIn("real RFC3339", result.stderr)

    def test_red_team_statement_inventory_covers_all_output_sections(self) -> None:
        """Untraced technical assertions cannot hide outside claims.md."""
        sys.path.insert(0, str(SCRIPTS))
        spec = importlib.util.spec_from_file_location("validate_case_under_test", SCRIPTS / "validate_case.py")
        assert spec and spec.loader; validator = importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "output"; output.mkdir()
            for name, text in {
                "disclosure.md": "A quendor bifurcates the zeta flange.",
                "prior_art.md": "D1 teaches a flux-cage interlocked with a nimbus shoe.",
                "risk_register.md": "The rotor has no frobnicator.",
                "verification_matrix.md": "Quendor deflection is 2 mm.",
                "claims.md": "# Claims\n\n1. A fixture comprising a documented guide.\n",
            }.items():
                (output / name).write_text(text, encoding="utf-8")
            paths = {"output": output}
            trace = [{"claim_number": 1, "limitation_text": "A fixture comprising a documented guide.", "evidence_ids": ["EV-0001"]}]
            inventory = validator.statement_inventory(paths, trace)
            narrative = [item for item in inventory if item["path"] != "claims.md"]
            self.assertEqual({item["path"] for item in narrative}, {"disclosure.md", "prior_art.md", "risk_register.md", "verification_matrix.md"})
            evidence = [{"evidence_id": "EV-0001", "verification_status": "verified", "statement": "documented guide", "verbatim": "documented guide"}]
            self.assertTrue(all(not validator._narrative_statement_evidence(str(item["text"]), evidence, trace) for item in narrative))
            self.assertEqual(len({item["statement_id"] for item in inventory}), len(inventory))

            (output / "disclosure.md").write_text(
                "This package is not legal advice and does not guarantee patentability.\n"
                "A quendor bifurcates the zeta flange.\n",
                encoding="utf-8",
            )
            disclosure = [item for item in validator.statement_inventory(paths, trace) if item["path"] == "disclosure.md"]
            self.assertEqual([item["text"] for item in disclosure], ["A quendor bifurcates the zeta flange"])

    def test_red_team_achieved_clause_binding_and_claim_atom_inventory(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        spec = importlib.util.spec_from_file_location("validate_case_under_test", SCRIPTS / "validate_case.py")
        assert spec and spec.loader; validator = importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)
        clauses = validator.output_clauses("The target is a 30% gain, but the trial achieved a 30% accuracy gain.")
        achieved = [clause for clause in clauses if validator.is_unsupported_achieved(clause)]
        self.assertEqual(achieved, ["but the trial achieved a 30% accuracy gain"])
        measured = {"evidence_id":"EV-0001", "evidence_class":"measured", "verification_status":"verified", "source_location":{"paragraph":"p1"}, "statement":"accuracy gain", "verbatim":"accuracy gain", "measurement":{"method":"laser accuracy test", "context":"loaded fixture", "result":"30% accuracy gain"}}
        self.assertTrue(validator._achieved_evidence_matches(achieved[0], [measured]))
        self.assertFalse(validator._achieved_evidence_matches("The trial using a vibration test under hot conditions achieved a 30% accuracy gain.", [measured]))
        unrelated = dict(measured, evidence_id="EV-0002", measurement={"method":"laser accuracy test", "context":"loaded fixture", "result":"30% accuracy loss"})
        self.assertFalse(validator._achieved_evidence_matches(achieved[0], [unrelated]))
        claim = {"claim_number": 1, "parent_claim_number": None, "text": "A fixture comprising a resilient member; a rigid blade."}
        atoms = validator.rendered_claim_atoms(claim)
        self.assertEqual([atom["text"] for atom in atoms], ["a resilient member", "a rigid blade"])

    def test_p1_multiline_claim_strict_binding_auto_narrative_and_prior_art(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        from evidence_first_lib import ValidationError
        spec = importlib.util.spec_from_file_location("validate_case_under_test", SCRIPTS / "validate_case.py")
        assert spec and spec.loader; validator = importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "output"; output.mkdir()
            (output / "claims.md").write_text(
                "# Claims\n\n1. A widget comprising:\n"
                "   - a quendor flange;\n"
                "   - and a zeta rotor.\n\n"
                "2. The widget of claim 1 comprising a nimbus shoe.\n"
                "## Notes\nThis line is not part of claim 2.\n",
                encoding="utf-8",
            )
            claims = validator.rendered_claim_inventory({"output": output})
            self.assertEqual(len(claims), 2)
            self.assertNotIn("Notes", claims[1]["text"])
            self.assertEqual(claims[1]["parent_claim_number"], 1)
            self.assertEqual([atom["text"] for atom in validator.rendered_claim_atoms(claims[0])], ["a quendor flange", "a zeta rotor"])

            for name in ("disclosure.md", "prior_art.md", "risk_register.md", "verification_matrix.md"):
                (output / name).write_text("English narrative line.\n", encoding="utf-8")
            (output / "risk_register.md").write_text("错误语言的技术陈述。\n", encoding="utf-8")
            trace = [{"language":"en-US"}]
            with self.assertRaisesRegex(ValidationError, "narrative deliverable risk_register.md"):
                validator._validate_auto_output_language({"output":output}, claims, trace, "en-US")

            # Visible Markdown link text is still output prose.  An English label
            # must not let a Chinese technical proposition escape auto=en-US.
            (output / "risk_register.md").write_text("[PriorArt](https://example.invalid/CN123456789) 弹性夹具不包含刚性刀片。\n", encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "narrative deliverable risk_register.md"):
                validator._validate_auto_output_language({"output":output}, claims, trace, "en-US")
            inventory = validator.statement_inventory({"output": output}, trace)
            self.assertIn("PriorArt 弹性夹具不包含刚性刀片", [str(item["text"]) for item in inventory])

        exact = [{"evidence_id":"EV-0001", "source_id":"SRC-0001", "verification_status":"verified", "statement":"The quendor flange interlocks with the zeta rotor at 2 mm.", "verbatim":"The quendor flange interlocks with the zeta rotor at 2 mm."}]
        self.assertEqual(validator._narrative_statement_evidence("The quendor flange interlocks with the zeta rotor at 2 mm.", exact, []), ["EV-0001"])
        self.assertEqual(validator._narrative_statement_evidence("The quendor flange supports the zeta rotor at 2 mm.", exact, []), [])
        self.assertEqual(validator._narrative_statement_evidence("The quendor flange interlocks with the zeta rotor at 3 mm.", exact, []), [])
        self.assertEqual(validator._narrative_statement_evidence("The quendor flange has no zeta rotor.", exact, []), [])
        positive = "The blade contains a rigid member and improved by 30%."
        negative = "The blade does not contain a rigid member and did not improve by 30%."
        self.assertFalse(validator._binding_matches(positive, negative))
        self.assertFalse(validator._binding_matches(negative, positive))
        self.assertFalse(validator._binding_matches("A blade contains a fixture.", "A fixture contains a blade."))
        self.assertFalse(validator._binding_matches("刀片包含夹具。", "夹具包含刀片。"))
        same_sentence = "The target is a 30% gain and the trial achieved a 30% gain."
        self.assertTrue(validator.is_unsupported_achieved(same_sentence))
        self.assertEqual([clause for clause in validator.output_clauses(same_sentence) if validator.is_unsupported_achieved(clause)], ["and the trial achieved a 30% gain"])

        # Two bullet rows without punctuation remain two traceable atoms.
        bullets = {"claim_number": 1, "parent_claim_number": None, "text": "A fixture comprising:\n  - a resilient pressing member\n  - a rigid blade"}
        self.assertEqual([item["text"] for item in validator.rendered_claim_atoms(bullets)], ["a resilient pressing member", "a rigid blade"])
        self.assertFalse(validator._trace_evidence_matches("a rigid blade", {"statement": "a resilient pressing member", "verbatim": "a resilient pressing member"}))

        postcritical = [{"source_id":"SRC-0001", "source_type":"patent", "title":"CN123456789", "verification_status":"verified", "publication_date":"2025-01-01", "accessed_at":"2025-01-02", "canonical_url":"https://example.invalid/CN123456789", "comparison_disposition":"context_only"}]
        case = {"critical_date":"2024-01-01"}
        with self.assertRaisesRegex(ValidationError, "differs from structured source record"):
            validator._validate_prior_art(case, postcritical, "SRC-0001 is qualifying prior art.")
        with self.assertRaisesRegex(ValidationError, "differs from structured source record"):
            validator._validate_prior_art(case, postcritical, "CN123456789 is qualifying prior art.")
        ledgerless_postcritical = [dict(postcritical[0])]
        ledgerless_postcritical[0].pop("comparison_disposition")
        with self.assertRaisesRegex(ValidationError, "post-critical-date patent"):
            validator._validate_prior_art(case, ledgerless_postcritical, "CN123456789 is qualifying prior art.")
        validator._validate_prior_art(case, postcritical, "SRC-0001 is retained as context only.")

    def test_red_team_off_language_statement_remains_in_inventory_and_is_blocked(self) -> None:
        """Language conformance must never improve coverage by dropping a sentence."""
        sys.path.insert(0, str(SCRIPTS))
        from evidence_first_lib import ValidationError
        spec = importlib.util.spec_from_file_location("validate_case_under_test", SCRIPTS / "validate_case.py")
        assert spec and spec.loader; validator = importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "output"; output.mkdir()
            (output / "claims.md").write_text("# Claims\n\n1. A fixture comprising a blade.\n", encoding="utf-8")
            (output / "disclosure.md").write_text("一种夹具包括刚性刀片。\n", encoding="utf-8")
            trace = [{"claim_number": 1, "limitation_text": "A fixture comprising a blade.", "evidence_ids": ["EV-0001"], "language": "en-US"}]
            inventory = validator.statement_inventory({"output": output}, trace, "en-US")
            self.assertIn("一种夹具包括刚性刀片", [str(row["text"]) for row in inventory])

    def test_sensitive_finding_ids_are_independent_of_temp_parent(self) -> None:
        def findings(root: Path) -> list[tuple[str, str]]:
            sys.path.insert(0, str(SCRIPTS))
            from evidence_first_lib import sensitive_findings
            root.mkdir(); (root / "plain.txt").write_text("sk-" + "A" * 20 + " /" + "Users/example deny-me", encoding="utf-8")
            with zipfile.ZipFile(root / "metadata.docx", "w") as archive:
                archive.writestr("docProps/core.xml", "mail" + "@example.com")
                archive.writestr("deny-me.txt", "x")
            denylist = root / "denylist.txt"; denylist.write_text("deny-me\n", encoding="utf-8")
            return sorted((item["id"], item["kind"]) for item in sensitive_findings(root, denylist))
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            self.assertEqual(findings(Path(first) / "scan"), findings(Path(second) / "scan"))

    def test_build_package_archive_verifier_rejects_hash_missing_and_duplicate_members(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        from build_package import verify_archive
        from evidence_first_lib import ValidationError

        def record(name: str, payload: bytes) -> dict[str, object]:
            return {"path": name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package"; package.mkdir()
            payload = b"expected package bytes"
            (package / "payload.txt").write_bytes(payload)
            manifest = package / "manifest.json"
            manifest.write_text(json.dumps({"schema_version":"0.1.0", "files":[record("payload.txt", payload)]}), encoding="utf-8")

            clean = root / "clean.zip"
            with zipfile.ZipFile(clean, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(package / "payload.txt", "payload.txt")
                archive.write(manifest, "manifest.json")
            verify_archive(clean, package, manifest)

            bad_hash = root / "bad-hash.zip"
            with zipfile.ZipFile(bad_hash, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("payload.txt", b"tampered package bytes")
                archive.write(manifest, "manifest.json")
            with self.assertRaisesRegex(ValidationError, "SHA256_MISMATCH"):
                verify_archive(bad_hash, package, manifest)

            missing = root / "missing.zip"
            with zipfile.ZipFile(missing, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(manifest, "manifest.json")
            with self.assertRaisesRegex(ValidationError, "MISSING_MEMBER"):
                verify_archive(missing, package, manifest)

            duplicate = root / "duplicate.zip"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(duplicate, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("payload.txt", payload)
                    archive.writestr("payload.txt", payload)
                    archive.write(manifest, "manifest.json")
            with self.assertRaisesRegex(ValidationError, "DUPLICATE_MEMBER"):
                verify_archive(duplicate, package, manifest)



if __name__ == "__main__":
    unittest.main()

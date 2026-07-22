"""Deterministic public-facing documentation contracts.

These tests intentionally inspect text only.  They must remain runnable with the
Python standard library and must not invoke the case validators or network.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest


REPOSITORY = Path(__file__).resolve().parents[1]

LEGAL_DISCLAIMER_EN = (
    "This material provides drafting and evidence-governance assistance, not legal "
    "advice. It does not guarantee patentability, validity, non-infringement, freedom "
    "to operate, ownership, grant, or fitness for filing. Obtain review from qualified "
    "patent counsel before disclosure, filing, or reliance."
)
LEGAL_DISCLAIMER_ZH = (
    "本材料仅提供专利撰写与证据治理辅助，不构成法律意见，也不保证可专利性、有效性、不侵权、"
    "自由实施、权属、授权或适合直接申请。披露、申请或据此作出决定前，应由具备资质的专利专业人员审核。"
)

README_FACING_EXAMPLES = (
    "docs/content/bad-draft-audit-correction.md",
    "examples/README.md",
    "examples/public-mechanical-case.md",
    "examples/synthetic-invention.md",
    "examples/synthetic-utility-model.md",
)

GOOD_FIRST_ISSUES = (
    "01-public-mechanical-case.md",
    "02-bilingual-terminology.md",
    "03-jurisdiction-adapter.md",
    "04-image-evidence-fixture.md",
)

FIVE_MINUTE_COMMANDS = (
    "cd evidence-first-patent-skill",
    "python3 skill/draft-patents-evidence-first/scripts/init_case.py ./demo-case "
    "--case-id demo-case --language bilingual --patent-type invention",
    "python3 skill/draft-patents-evidence-first/scripts/validate_case.py ./demo-case",
    "python3 skill/draft-patents-evidence-first/scripts/scan_sensitive.py ./demo-case --format json",
)


class PublicContentContractTests(unittest.TestCase):
    maxDiff = None

    def read(self, relative_path: str) -> str:
        return (REPOSITORY / relative_path).read_text(encoding="utf-8")

    def test_readme_facing_examples_include_the_full_bilingual_legal_disclaimer(self) -> None:
        for relative_path in README_FACING_EXAMPLES:
            with self.subTest(page=relative_path):
                page = self.read(relative_path)
                self.assertIn(LEGAL_DISCLAIMER_EN, page)
                self.assertIn(LEGAL_DISCLAIMER_ZH, page)

    def test_citation_metadata_names_a_public_project_author(self) -> None:
        citation = self.read("CITATION.cff")
        self.assertRegex(citation, r"(?m)^authors:\s*$")
        self.assertIn('name: "Evidence-First Patent Skill contributors"', citation)
        self.assertIn(
            'repository-code: "https://github.com/soarsky1991/evidence-first-patent-skill"',
            citation,
        )
        self.assertIn(
            'license-url: "https://github.com/soarsky1991/evidence-first-patent-skill/blob/v0.1.0/NOTICE"',
            citation,
        )
        self.assertNotRegex(citation, r"(?m)^license:\s*$")

    def test_bad_draft_audit_is_bilingually_aligned(self) -> None:
        page = self.read("docs/content/bad-draft-audit-correction.md")
        for text in (
            "The guide eliminates vibration and improves positioning accuracy by 30%.",
            "该导向件消除了振动，并将定位精度提高了 30%。",
            "Problem: the source states only",
            "问题：原始材料只记载",
            "Audit action:",
            "审计动作：",
            "The claim trace should map only",
            "权项溯源只能将结构限定",
        ):
            self.assertIn(text, page)

    def test_every_readme_facing_example_is_linked_from_the_readme_path(self) -> None:
        root_readmes = (self.read("README.md"), self.read("README.zh-CN.md"))
        example_index = self.read("examples/README.md")

        for readme in root_readmes:
            self.assertIn("examples/README.md", readme)
            self.assertIn("examples/public-mechanical-case.md", readme)
        self.assertIn("synthetic-invention.md", example_index)
        self.assertIn("synthetic-utility-model.md", example_index)
        self.assertIn("该合成概念是一种导轨导向结构", example_index)
        self.assertIn("该合成概念包括产品壳体", example_index)

    def test_synthetic_invention_maps_every_claim_limitation(self) -> None:
        page = self.read("examples/synthetic-invention.md")
        for limitation in (
            "rail and guide beside the rail",
            "replaceable contact insert coupled to the guide",
            "insert retained by a shoulder of the guide",
        ):
            self.assertIn(f"| {limitation} /", page)
        self.assertIn("designed proposal; not measured", page)

    def test_synthetic_utility_model_maps_every_claim_limitation(self) -> None:
        page = self.read("examples/synthetic-utility-model.md")
        for limitation in (
            "housing with a guide groove",
            "retaining shoulder at an edge of the guide groove",
            "removable cover engaged with the retaining shoulder",
            "removable cover received in the guide groove",
        ):
            self.assertIn(f"| {limitation} /", page)
        self.assertIn("designed proposal; not measured", page)

    def test_good_first_issue_drafts_are_linked_and_define_all_required_boundaries(self) -> None:
        contributing = self.read("CONTRIBUTING.md")
        required_sections = (
            "## Source and license boundary",
            "## Confidentiality boundary",
            "## Test boundary",
            "## Acceptance criteria",
        )

        for filename in GOOD_FIRST_ISSUES:
            with self.subTest(issue=filename):
                relative_path = f"docs/good-first-issues/{filename}"
                issue = self.read(relative_path)
                self.assertIn(relative_path, contributing)
                for section in required_sections:
                    self.assertIn(section, issue)

    def test_five_minute_readme_blocks_are_identical_and_local_stdlib_only(self) -> None:
        blocks = []
        for relative_path, heading in (
            ("README.md", "Five-minute local run"),
            ("README.zh-CN.md", "五分钟本地运行"),
        ):
            readme = self.read(relative_path)
            match = re.search(
                rf"^## {re.escape(heading)}\n.*?^```sh\n(.*?)^```$",
                readme,
                flags=re.MULTILINE | re.DOTALL,
            )
            self.assertIsNotNone(match, f"missing shell block under {heading!r} in {relative_path}")
            blocks.append(tuple(line for line in match.group(1).splitlines() if line.strip()))

        self.assertEqual(tuple(blocks[0]), FIVE_MINUTE_COMMANDS)
        self.assertEqual(blocks[0], blocks[1])

        forbidden = re.compile(r"\b(?:pip|venv|virtualenv|uv|poetry|conda|curl|wget|http|https)\b", re.I)
        for command in blocks[0]:
            self.assertIsNone(forbidden.search(command), command)


if __name__ == "__main__":
    unittest.main()

"""Repository-facing release, entry-point, and install-layout contracts."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit
import zipfile

from release_common import release_names, release_version


REPOSITORY = Path(__file__).resolve().parents[1]
PRIMARY_READMES = (Path("README.md"), Path("README.en.md"))
COMPATIBILITY_README = Path("README.zh-CN.md")
PUBLIC_BRAND_ENTRYPOINTS = PRIMARY_READMES + (COMPATIBILITY_README,) + (
    Path("CITATION.cff"),
    Path("RELEASE_NOTES.md"),
    Path("RELEASE_NOTES.zh-CN.md"),
)
LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)


def github_heading_slugs(markdown: str) -> set[str]:
    slugs: set[str] = set()
    seen: dict[str, int] = {}
    for heading in HEADING_PATTERN.findall(markdown):
        plain = re.sub(r"<[^>]+>", "", heading)
        plain = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", plain)
        plain = re.sub(r"[`*_~]", "", plain).strip().lower()
        base = re.sub(r"[^\w\-\s]", "", plain, flags=re.UNICODE)
        base = re.sub(r"\s+", "-", base)
        count = seen.get(base, 0)
        seen[base] = count + 1
        slugs.add(base if count == 0 else f"{base}-{count}")
    return slugs


class ReleaseContractTests(unittest.TestCase):
    maxDiff = None

    def read(self, relative: Path | str) -> str:
        return (REPOSITORY / relative).read_text(encoding="utf-8")

    def test_version_is_single_source_for_release_metadata(self) -> None:
        version = release_version(REPOSITORY)
        self.assertEqual(version, "0.2.1")
        citation = self.read("CITATION.cff")
        self.assertRegex(citation, rf'(?m)^version: "{re.escape(version)}"$')
        self.assertRegex(citation, r'(?m)^date-released: "RELEASE_DATE_PENDING"$')
        self.assertIn(f"/blob/v{version}/NOTICE", citation)
        self.assertIn(f"v{version}", self.read("RELEASE_NOTES.md").splitlines()[0])
        self.assertIn(f"v{version}", self.read("RELEASE_NOTES.zh-CN.md").splitlines()[0])

    def test_schema_version_remains_independent_from_release_version(self) -> None:
        manifest_builder = self.read("tests/build_release_manifest.py")
        self.assertIn('"schema_version": "0.1.0"', manifest_builder)
        self.assertIn('"release_version": release_version(repo)', manifest_builder)
        self.assertIn('SCHEMA_VERSION = "0.1.0"', self.read("skill/draft-patents-evidence-first/scripts/evidence_first_lib.py"))

    def test_readme_relative_links_and_anchors_resolve(self) -> None:
        for readme_path in PRIMARY_READMES + (COMPATIBILITY_README,):
            source = self.read(readme_path)
            for raw_destination in LINK_PATTERN.findall(source):
                destination = raw_destination.strip().strip("<>").split(maxsplit=1)[0]
                parsed = urlsplit(destination)
                if parsed.scheme or parsed.netloc:
                    continue
                target = readme_path.parent / unquote(parsed.path) if parsed.path else readme_path
                target = Path(target)
                with self.subTest(readme=readme_path.as_posix(), link=destination):
                    self.assertTrue((REPOSITORY / target).exists(), f"missing relative link target: {target}")
                    if parsed.fragment:
                        self.assertTrue((REPOSITORY / target).is_file(), f"anchor target is not a file: {target}")
                        slugs = github_heading_slugs(self.read(target))
                        self.assertIn(unquote(parsed.fragment).lower(), slugs)

    def test_bilingual_language_entrypoints_and_legacy_compatibility_page(self) -> None:
        chinese = self.read("README.md")
        english = self.read("README.en.md")
        compatibility = self.read(COMPATIBILITY_README)
        self.assertTrue(chinese.startswith("# 专利君｜证据优先专利工作流\n"))
        self.assertTrue(english.startswith("# Evidence-First Patent Skill\n"))
        self.assertIn("(README.en.md)", chinese)
        self.assertIn("(README.md)", english)
        self.assertTrue(compatibility.startswith("# 中文入口已迁移\n"))
        self.assertIn("[README.md](README.md)", compatibility)
        self.assertIn("[README.en.md](README.en.md)", compatibility)

    def test_public_entrypoints_respect_brand_policy(self) -> None:
        policy = json.loads(self.read("tests/assets/release_brand_policy.json"))
        corpus = "\n".join(self.read(path) for path in PUBLIC_BRAND_ENTRYPOINTS)
        self.assertIn(policy["canonical_english"], self.read("README.en.md"))
        self.assertIn(policy["canonical_chinese"], self.read("README.md"))
        for forbidden in policy["forbidden_aliases"]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden.casefold(), corpus.casefold())

    def test_skill_only_archive_is_install_ready(self) -> None:
        names = release_names(REPOSITORY)
        skill_source = REPOSITORY / "skill/draft-patents-evidence-first"
        with tempfile.TemporaryDirectory(prefix="efps-skill-archive-") as temporary:
            output = Path(temporary) / names["skill_archive"]
            result = subprocess.run(
                [sys.executable, str(REPOSITORY / "tests/build_skill_archive.py"), "--repo", str(REPOSITORY), "--output", str(output)],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                actual = set(archive.namelist())
                selection = subprocess.run(
                    ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                    cwd=REPOSITORY,
                    capture_output=True,
                    check=True,
                )
                expected = set()
                for raw in selection.stdout.split(b"\0"):
                    if not raw:
                        continue
                    relative = Path(raw.decode("utf-8"))
                    if relative.is_relative_to(Path("skill/draft-patents-evidence-first")):
                        expected.add(f"{names['skill_prefix']}/{(REPOSITORY / relative).relative_to(skill_source).as_posix()}")
                self.assertEqual(actual, expected)
                self.assertIn(f"{names['skill_prefix']}/SKILL.md", actual)
                self.assertFalse(any(name.startswith(f"{names['skill_prefix']}/skill/") for name in actual))
                archive.extractall(Path(temporary) / "installed")
            installed = Path(temporary) / "installed" / names["skill_prefix"]
            validation = subprocess.run(
                [sys.executable, str(REPOSITORY / "tests/vendor/quick_validate.py"), str(installed)],
                text=True,
                capture_output=True,
            )
            self.assertEqual(validation.returncode, 0, validation.stderr or validation.stdout)

    def test_bilingual_discussion_forms_and_dependabot_are_structurally_valid(self) -> None:
        forms = REPOSITORY / ".github/DISCUSSION_TEMPLATE"
        for slug in ("case-reviews", "data-sources", "jurisdiction-adapters", "q-and-a"):
            with self.subTest(slug=slug):
                form = (forms / f"{slug}.yml").read_text(encoding="utf-8")
                self.assertRegex(form, r"(?m)^name: .+ / .+$")
                self.assertRegex(form, r"(?m)^description: .+ / .+$")
                self.assertRegex(form, r"(?m)^body:\s*$")
                self.assertRegex(form, r"(?m)^\s+- type: (?:textarea|input|dropdown|checkboxes)\s*$")
                ids = re.findall(r"(?m)^\s+id:\s+([a-z][a-z0-9_-]*)\s*$", form)
                self.assertEqual(len(ids), len(set(ids)))
        dependabot = self.read(".github/dependabot.yml")
        ecosystems = set(re.findall(r'package-ecosystem:\s+"?([a-z-]+)"?', dependabot))
        self.assertEqual(ecosystems, {"pip", "github-actions"})


if __name__ == "__main__":
    unittest.main()

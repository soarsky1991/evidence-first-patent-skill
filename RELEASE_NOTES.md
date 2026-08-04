# v0.2.0 content notes

- Promoted Chinese as the primary README entry point and added the Patent Jun visual and governance guidance.
- Added an install-ready Skill-only archive alongside the deterministic source archive.
- Added public-entry-point, brand, release-manifest, and archive-membership checks to CI.
- Added the counsel-facing external-structure-package reference: it separates clean external documents from an internal sidecar, requires a master-assembly ledger, and defines a five-field annotation response format.
- Kept the case-data `schema_version` at `0.1.0`; this release changes workflow guidance and distribution only.

This public release remains drafting and evidence-governance assistance, not legal advice, a patentability opinion, a filing acceptance, or a guarantee of grant. Substantive outputs still require qualified human review.

The rendered release samples and deterministic archives can be rebuilt locally with:

```sh
python tests/build_release_samples.py --repo . --output dist/v0.2.0/samples
python tests/build_source_archive.py --repo . --output dist/v0.2.0/evidence-first-patent-skill-v0.2.0.zip
python tests/build_skill_archive.py --repo . --output dist/v0.2.0/draft-patents-evidence-first-v0.2.0.zip
```

# v0.2.1 content notes

- Added a mechanical figure-set consistency reference for multi-view assemblies.
- Requires a state-aware relation ledger and a shared sectional primitive so assembly, section, comparison, and local contact views cannot drift into different structures.
- Adds explicit checks for motion clearance, maximum-travel stops, disassembly paths, open-slot topology, support/contact chains, and comparative dimension baselines.
- Separates annotated counsel-review drawings from clean-line drawings and adds text-token, 300 dpi, and 600 dpi rendered checks.
- Adds independent repair and adversarial review roles with a zero-unresolved-P0/P1 exit criterion.
- Kept the case-data `schema_version` at `0.1.0`; this patch changes workflow guidance and tests only.

This public release remains drafting and evidence-governance assistance, not legal advice, a patentability opinion, a filing acceptance, or a guarantee of grant. Substantive outputs still require qualified human review.

The rendered release samples and deterministic archives can be rebuilt locally with:

```sh
python tests/build_release_samples.py --repo . --output dist/v0.2.1/samples
python tests/build_source_archive.py --repo . --output dist/v0.2.1/evidence-first-patent-skill-v0.2.1.zip
python tests/build_skill_archive.py --repo . --output dist/v0.2.1/draft-patents-evidence-first-v0.2.1.zip
```

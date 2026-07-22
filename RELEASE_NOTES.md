# v0.1.0 content notes

- Added bilingual first-screen README guidance and five-minute local interface.
- Added method, data-contract, confidentiality, and bilingual-review references.
- Added synthetic invention and utility-model demonstrations, plus a public mechanical-record reading exercise.
- Added terminology, bad-draft audit, original provenance diagram, and media-license ledger.
- Added the complete [16-fixture acceptance index](tests/fixtures/README.md) under `tests/fixtures`.

This is the first public, reproducible workflow release. It is not legal advice, a patentability opinion, a filing acceptance, or a guarantee of grant; substantive outputs still require qualified human review.

The rendered release samples and deterministic source archive can be rebuilt locally with:

```sh
python tests/build_release_samples.py --repo . --output dist/v0.1.0/samples
python tests/build_source_archive.py --repo . --output dist/v0.1.0/evidence-first-patent-skill-v0.1.0.zip
```

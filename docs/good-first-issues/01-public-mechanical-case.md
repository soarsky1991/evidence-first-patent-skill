# Good first issue: add one licensed public mechanical case

## Goal

Add one small, reproducible mechanical-domain prior-art reading case based only on redistributable public records. It must be unrelated to confidential semiconductor or client work.

## Required provenance

- Canonical public patent URL and publication number.
- Verified publication date and access date.
- Patent-family identifier, or the exact value `family unknown` with an explanation.
- Source URL, creator, license, license URL, retrieval date, modifications, and SHA-256 for every redistributed image.
- No legal-status label unless an authoritative record is cited; otherwise use `status not relied upon`.

## Source and license boundary

- Use only canonical public-record URLs and images whose redistribution terms are recorded in the media ledger.
- Preserve the source URL, creator, license, license URL, retrieval date, modifications, and SHA-256 for every redistributed asset.

## Confidentiality boundary

- Do not include customer material, personal data, credentials, local paths, unpublished dimensions, or internal images.

## Test boundary

- Add deterministic fixture tests for family deduplication and public-source metadata only; tests must not make network requests or decide legal status.

## Acceptance criteria

- Add a short paraphrased feature table with source locations; do not copy long passages.
- Add the record to `sources.jsonl`-compatible example data with a canonical HTTPS URL.
- Add a test that detects a duplicate member of the same patent family.
- Run the link, license, sensitive-data, and family-deduplication checks.
- Confirm that no customer name, person, email, local path, credential, unpublished dimension, or internal image is included.

## Out of scope

Novelty, validity, infringement, freedom-to-operate, inventorship, filing advice, and claims that the patent is expired or in force.

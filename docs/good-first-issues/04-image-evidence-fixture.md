# Good first issue: add a synthetic image-evidence fixture

## Goal

Improve image/PDF evidence extraction tests using a wholly synthetic, redistributable fixture with deterministic expected output.

## Required provenance

- Generate the fixture in-repository or use an expressly redistributable source.
- Record source URL, creator, license, license URL, retrieval date, modifications, and SHA-256 when any third-party asset is used.
- State that the fixture is synthetic and not a real client drawing or apparatus.

## Source and license boundary

- Use only in-repository synthetic material or assets with recorded source URL, creator, license, license URL, retrieval date, modifications, and SHA-256.
- Do not include unknown-license media or third-party assets without a documented redistribution basis.

## Confidentiality boundary

- Do not include client drawings, personal data, credentials, local paths, real secrets, or screenshots of logged-in services.

## Test boundary

- Add deterministic extraction and confidentiality assertions with fixed finding IDs; tests must run offline and exclude explicit timestamps from comparisons.

## Acceptance criteria

- Include a synthetic image or PDF with page/figure coordinates and expected OCR text.
- Seed a clearly synthetic confidentiality token that the scanner must detect; never use a real secret, email, phone number, or identity.
- Add positive extraction assertions and a negative confidentiality assertion with deterministic finding IDs.
- Verify image/document metadata, archive membership, and license-ledger coverage.
- Run the fixture twice and prove identical canonical results after excluding explicit timestamps.

## Out of scope

Screenshots of logged-in services, real engineering drawings, client documents, faces or personal data, unknown-license media, and OCR claims presented as verified technical facts.

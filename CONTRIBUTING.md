# Contributing

Thank you for improving a reproducible, evidence-governed patent workflow. Use only synthetic or redistributable public material. Do not submit customer material, personal data, credentials, local paths, unpublished parameters, or legal conclusions presented as facts.

Run the local validators relevant to your change, preserve source and license fields, and keep bilingual claim limitations aligned. Contributions use the Developer Certificate of Origin rather than a CLA: add `Signed-off-by: Your Name <your-email>` to each commit, certifying that you have the right to submit it under the repository licenses.

## Four good first issues

1. **[Add one licensed public mechanical case](docs/good-first-issues/01-public-mechanical-case.md).** Supply a canonical public patent URL, verified publication date, family identifier or `family unknown`, access date, short paraphrased feature table, and a test that rejects duplicate family members. Do not rely on an unverified legal-status label.
2. **[Extend the bilingual terminology set](docs/good-first-issues/02-bilingual-terminology.md).** Add ten Chinese–English engineering or patent-drafting term pairs, an allowed alias and prohibited ambiguous term where useful, and one atomic-scope comparison fixture.
3. **[Prototype a jurisdiction writing adapter](docs/good-first-issues/03-jurisdiction-adapter.md).** Add a clearly experimental, non-default adapter in a separate reference file and tests that keep the core evidence schema and human gate intact. Do not present it as filing advice.
4. **[Improve image-evidence extraction tests](docs/good-first-issues/04-image-evidence-fixture.md).** Add a fully synthetic image/PDF fixture with page or figure coordinates, expected OCR text, and a confidentiality seed that must be detected. Do not submit screenshots, real client drawings, or unknown-license media.

Use the relevant Issue Form before opening a pull request. A contribution is reviewable only when its source, license, expected assertion, and confidentiality boundary are explicit.

## Public documentation contract

Documentation and cases must state whether they are `synthetic`, licensed public material, or a reproducible local fixture. A successful validator is process evidence only: do not convert it into a claim of filing readiness, patent grant, legal status, customer authorization, or real-world technical performance. Before proposing a public visual, reserve its asset path and register its source, review result, and SHA-256; do not submit a hand-made placeholder as a final preview.

Public maintainer attribution uses 马智辰 (Zhichen Ma / 智辰老师), `soarhigh1991@gmail.com`, and X `@AI2studio`. Do not add employer, job, client, location, historical aliases, private contact data, or social profiles to public-facing material.

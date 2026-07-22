# Good first issue: extend bilingual terminology coverage

## Goal

Add ten Chinese–English engineering or patent-drafting term pairs that improve atomic limitation comparison without silently changing claim scope.

## Required provenance

- For each term, cite a public or redistributable source URL and access date.
- Record the preferred Chinese term, preferred English term, allowed alias, and a prohibited or ambiguous alternative when useful.
- Do not use confidential project terminology as a public language sample.

## Source and license boundary

- Use public or redistributable terminology sources and record each source URL, access date, and any applicable license or quotation basis.
- Do not copy restricted dictionaries or source text beyond the permitted quotation basis.

## Confidentiality boundary

- Do not include customer vocabulary, personal data, credentials, local paths, unpublished parameters, or internal claim text.

## Test boundary

- Add deterministic positive and negative atom-map fixtures only; tests must not call translation services, make network requests, or express legal-equivalence conclusions.

## Acceptance criteria

- Add ten reviewed pairs to the terminology reference.
- Add at least one positive bilingual atom-map fixture.
- Add at least one negative fixture that changes an object, component/step, relationship, numeric bound, condition, modality, or dependency and must block.
- Keep `limitation_text_sha256`, exact `text_span`, and language-neutral canonical atoms consistent.
- Run bilingual, trace, sensitive-data, and link checks.

## Out of scope

Machine translation quality scores, legal equivalence opinions, jurisdiction-specific filing advice, and undocumented terminology scraped from restricted sources.

# Good first issue: prototype an experimental jurisdiction adapter

## Goal

Prototype a writing-reference adapter for one non-CN jurisdiction while keeping the v0.1.0 CN workflow, evidence schema, and human gate unchanged.

## Required provenance

- Cite current official guidance or rules with canonical URLs and access dates.
- Identify the jurisdiction, document version/date, and license or quotation basis.
- Mark every adapter page `experimental`, `non-default`, and `not filing advice`.

## Source and license boundary

- Use current official guidance with canonical URLs, access dates, and an explicit license or quotation basis for every reproduced reference.
- Do not copy restricted forms or guidance outside that documented basis.

## Confidentiality boundary

- Do not include client facts, personal data, credentials, local paths, unpublished filing strategy, or internal work product.

## Test boundary

- Add deterministic tests that protect the existing CN workflow and prohibit submission, publishing, or filing; tests must not contact an external patent office.

## Acceptance criteria

- Place the adapter in a separate reference file; do not change `case.yaml` jurisdiction support in v0.1.0.
- Add tests proving that the core evidence classes, claim trace, confidentiality modes, and human selection gate remain mandatory.
- Add a test proving the adapter cannot submit, publish, or file anything.
- Add a staleness note for future rule changes and a maintainer-review checklist.
- Run link, license, schema, and sensitive-data checks.

## Out of scope

Production legal adaptation, filing-ready forms, legal opinions, automated submission, or claims of compliance with a foreign patent office.

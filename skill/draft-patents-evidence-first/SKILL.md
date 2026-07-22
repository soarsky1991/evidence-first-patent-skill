---
name: draft-patents-evidence-first
description: Build an evidence-governed Chinese invention or utility-model disclosure package from local engineering materials. Use when users need a bilingual (zh-CN/en-US) evidence inventory, prior-art comparison, disclosure draft, claim framework, limitation trace, or integrity check without inventing test results; not for filing, legal opinions, or public disclosure.
---

# Evidence-First Patent Workflow / 证据优先专利工作流

Use this Skill for internal drafting preparation under the China (`CN`) invention and utility-model workflow. Treat every model output as a proposal. A qualified patent professional and a human disclosure decision remain mandatory.

**Core rule:** Draft from evidence, not imagination / 从证据出发，不把目标写成结果。

## Start safely

1. Ask for the controlling request language, patent type, critical date, and confidentiality mode. Default to `local_only`.
2. Initialize a non-identifying case directory. Do not place original material outside `input/` or modify it.

```bash
python scripts/init_case.py CASE_DIR --case-id demo-fixture --language zh-CN --patent-type invention
python scripts/validate_case.py CASE_DIR
```

For `--language auto`, persist the language of the controlling user request before validation:

```bash
python scripts/resolve_language.py CASE_DIR --language zh-CN
```

3. Run `scan_sensitive.py` before any external research. In `local_only`, make no external request. In `sanitized_search`, show a human-approved sanitized query before sending it. In `approved_external`, record the scoped approval first.

## Follow the ten stages in order

1. Inventory inputs and establish the disclosure boundary.
2. Extract text, tables, figures, and case-relative locations; preserve source hashes.
3. Classify each statement as `measured`, `documented`, `inferred`, or `designed`.
4. Propose and deduplicate concepts while retaining source links.
5. Research prior art using only sanitized, approved queries; verify dates and family identifiers.
6. Create closest-art comparison, risk record, and separate selection scorecards.
7. Stop for the human selection gate. Do not draft substantively until a concept and public boundary are approved.
8. Draft disclosure, claim framework, figure plan, options, and verification matrix.
9. Trace every atomic claim limitation to evidence and compare bilingual limitation atoms.
10. Run adversarial checks, sensitive scan, rendering checks, and packaging review.

Read [workflow.md](references/workflow.md) for stage-level rules and [data-contract.md](references/data-contract.md) before creating records.

## Evidence language

- `measured`: recorded observation/test result with method/context, result, and source location.
- `documented`: an identifiable source states it, but it is not a project measurement.
- `inferred`: reasoning from listed evidence IDs; phrase it as an inference, never as an observation.
- `designed`: a proposal, target, optional embodiment, or verification plan; phrase it as proposed or to be verified.

Never present a target, design, or inference as an achieved result. Keep machine evidence labels in JSONL sidecars; use natural language such as “proposed embodiment” or “to be verified” in clean drafts.

## Required checks

Run the commands below after changing records. Validation commands do not alter source inputs.

```bash
python scripts/dedupe_families.py CASE_DIR --check
python scripts/trace_claims.py CASE_DIR --check
python scripts/compare_bilingual.py CASE_DIR --check
python scripts/scan_sensitive.py CASE_DIR --format json
python scripts/validate_case.py CASE_DIR
```

Build only after all checks pass. `docx` and `pdf` output need a local document runtime; Markdown always remains available.

```bash
python scripts/build_package.py CASE_DIR --format all --output CASE_DIR/package
# Packaging is not complete until both the folder and the ZIP pass this local-only gate.
python scripts/inspect_artifacts.py CASE_DIR/package --format json
python scripts/inspect_artifacts.py CASE_DIR/package.zip --format json
python scripts/validate_media.py --ledger public-assets/media-ledger.md
```

`inspect_artifacts.py` performs bounded recursive ZIP inspection and blocks CRC, path, encryption, size/depth, or manifest-membership problems; DOCX/XLSX/PPTX reviewer metadata, comments, revisions, hidden sheets/slides, macros, embeds, or external relationships; PDF privacy-bearing body text, attachments, author metadata, JavaScript, or encryption; and JPEG/PNG metadata. `validate_media.py` checks the shipped ledger fields, licenses, asset presence, and byte hashes. Commands return `0` when clean, `1` for findings, and `2` when a required local dependency is unavailable.

## Claim and bilingual discipline

Create one `claim_trace.jsonl` row per atomic limitation and language. Every row needs resolvable evidence. In bilingual mode, pair Chinese and English rows and compare object, component/step, relationship, numeric bound, condition, modality, and dependency. Preserve mismatches and mark them `conflict`; do not silently “fix” scope by translation.

For utility models, independent claims must be directed to a product and its structural relationships, not solely to a method.

## Boundaries

This Skill assists evidence governance and drafting preparation only. It is not legal advice and does not establish inventorship, patentability, validity, non-infringement, freedom to operate, ownership, or grant. Obtain qualified counsel review before disclosure, filing, or reliance.

Read [confidentiality.md](references/confidentiality.md) for external-search and release limits. Read [bilingual-review.md](references/bilingual-review.md) when working in `bilingual` mode.

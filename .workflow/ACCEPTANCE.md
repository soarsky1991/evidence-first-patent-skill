# v0.1.0 Acceptance Contract

Status: **FROZEN**  
Applies to: `draft-patents-evidence-first` and the public repository release candidate.  
Authority: this file and `SPEC.md` override worker self-assessments, README claims, and generated scorecards.

## 1. Final-state model

The only terminal states are:

- `READY_FOR_PUBLICATION_REVIEW`: all mandatory checks pass, two consecutive Sol-V rounds add no new critical finding, and the release candidate is ready for the user's explicit GitHub publication decision.
- `BLOCKED`: one or more blocking conditions remain, a required model route is unresolved, validation evidence is missing, or the three-round review limit ends without convergence.

`READY_FOR_PUBLICATION_REVIEW` does **not** authorize repository creation, push, release publication, Discussions changes, Topics changes, social posting, patent filing, or upload of case material. Those actions remain separate human gates.

The final status record MUST be written to `.workflow/final_status.json` with:

```json
{
  "spec_sha256": "64 lowercase hex",
  "candidate_commit": "git object id or WORKTREE",
  "status": "READY_FOR_PUBLICATION_REVIEW or BLOCKED",
  "rounds_completed": 0,
  "consecutive_clean_rounds": 0,
  "blocking_findings": [],
  "test_report_sha256": "64 lowercase hex",
  "release_manifest_sha256": "64 lowercase hex or null",
  "validated_by": "Sol-V",
  "validated_at": "RFC3339 timestamp"
}
```

Only Sol-V may set the terminal status. Terra and Luna MUST leave status unset or `BLOCKED`.

## 2. Required command interfaces

The implementation MUST expose these local, non-interactive commands. Each command MUST return exit code `0` only when its stated invariant passes, `1` for validation failure, and `2` for invalid invocation or unavailable required dependency. Validation commands MUST NOT modify source inputs.

```text
python skill/draft-patents-evidence-first/scripts/init_case.py CASE_DIR \
  --case-id ID --language {zh-CN,en-US,auto,bilingual} \
  --patent-type {invention,utility_model} [--critical-date YYYY-MM-DD]

python skill/draft-patents-evidence-first/scripts/validate_case.py CASE_DIR
python skill/draft-patents-evidence-first/scripts/dedupe_families.py CASE_DIR [--check]
python skill/draft-patents-evidence-first/scripts/trace_claims.py CASE_DIR --check
python skill/draft-patents-evidence-first/scripts/compare_bilingual.py CASE_DIR --check
python skill/draft-patents-evidence-first/scripts/scan_sensitive.py TARGET \
  [--denylist PATH] [--format json]
python skill/draft-patents-evidence-first/scripts/build_package.py CASE_DIR \
  --format {md,docx,pdf,all} --output OUTPUT_DIR
python skill/draft-patents-evidence-first/scripts/run_acceptance.py \
  --repo . --fixtures tests/fixtures --report .workflow/test-report.json
```

`run_acceptance.py` MUST be deterministic for identical repository content and fixture inputs except for explicit timestamp fields. It MUST aggregate, not bypass, individual validators.

## 3. Blocking conditions

Any item below forces `BLOCKED`.

### 3.1 Repository and Skill structure

- The official Skill `quick_validate.py` does not return success for `skill/draft-patents-evidence-first`.
- `SKILL.md` is missing, exceeds 500 physical lines, has fields other than `name` and `description` in YAML frontmatter, or contains unresolved placeholders such as `TODO`.
- `agents/openai.yaml` is missing or its display name, short description, or default prompt conflicts with `SKILL.md`.
- A reference required by `SKILL.md` is missing, nested more than one directory below `references/`, or unreachable by a direct link from `SKILL.md`.
- A script referenced by `SKILL.md` or README is missing, non-runnable through its documented Python command, or changes immutable input content during validation.
- README quick-start instructions fail in a clean checkout.

### 3.2 Public schema and workflow integrity

- Any required `case.yaml`, `sources.jsonl`, `evidence.jsonl`, `claim_trace.jsonl`, `scorecard.json`, or `stage_status.json` field violates `SPEC.md`.
- Any JSONL line is blank, malformed, non-object JSON, or contains a duplicate primary identifier.
- A foreign key (`source_id`, `evidence_ids`, `derived_from`, parent claim, or bilingual pair) is unresolved or cyclic where cycles are invalid.
- Original input SHA-256 changes after any Skill command.
- Stage 8 or later completes without a valid human selection gate.
- An upstream content/hash change leaves a downstream stage marked complete.
- A public prior-art comparison relies on a source whose publication date is null/unverified or later than the case's critical date.
- A changed schema meaning is shipped without a schema-version change and migration note.

### 3.3 Evidence and claims

- `unsupported_measured_claims` is not zero.
- A quantified achieved benefit lacks verified `measured` evidence with source location and method/context.
- A `designed` or `inferred` statement is rendered as an achieved test result.
- A material technical statement has no evidence record.
- `claim_trace_coverage_pct` is below `100.0`.
- A claim limitation has `semantic_status=missing` or `conflict`, an empty evidence list, or an unresolved evidence ID.
- A utility-model independent claim is directed solely to a method rather than a product's structural features and relationships.
- The number or dependency of claims in rendered output differs from `claim_trace.jsonl`.

### 3.4 Prior art and source reliability

- `duplicate_patent_families` is not zero after deduplication.
- A cited public source lacks canonical URL, access date, and verification status.
- A patent status such as expired/lapsed/ceased is asserted without a recorded authoritative source.
- A public-case source URL fails both HTTPS retrieval attempts separated by at least one second, unless an authoritative immutable local snapshot and its redistribution license are included.
- A quotation exceeds the repository's documented source-use limit or lacks source attribution.

### 3.5 Bilingual behavior

- `auto` resolves from input-document majority rather than the controlling user request.
- Bilingual mode lacks either Chinese or English output.
- `bilingual_atomic_consistency_pct` is below `100.0`.
- Any paired limitation differs in object, relation, numeric bound, condition, modality, or claim dependency.
- A mismatch is silently normalized instead of preserved and marked `conflict` for human review.

### 3.6 Confidentiality and external actions

- A tracked file, generated output, or archive contains a confirmed credential, token, private key, cookie, session datum, personal contact detail, machine-specific absolute path, or a term from the release denylist.
- A document package contains tracked changes, comments, hidden worksheets/slides, author metadata, image metadata, or undeclared archive members that expose private information.
- `local_only` causes any external request.
- `sanitized_search` sends an unpreviewed query or a query containing a blocked identifier or unpublished parameter combination.
- `approved_external` sends data without a scoped approval record.
- Any command files, publishes, pushes, uploads, posts, changes GitHub settings, or otherwise performs an irreversible external action.

### 3.7 Public examples, images, and licenses

- The complete demo is not visibly labeled as synthetic in both languages.
- Synthetic material is represented as a real client matter, known novel invention, filing-ready application, or achieved project result.
- A public case is related to a contributor's confidential matter or depends on non-public source material.
- Any external asset lacks `asset_path`, source URL, creator, license, license URL, retrieval date, modification statement, or SHA-256.
- Any shipped external asset has an unknown, all-rights-reserved, fair-use-only, incompatible, or unverifiable license.
- A screenshot of a web UI, third-party logo, confidential apparatus, or private document appears in the release.
- Informational images lack bilingual alt text or a material text equivalent.
- Apache-2.0 code, CC BY 4.0 original content, and third-party asset terms are not clearly separated.

### 3.8 Routes and independent review

- The common route probe does not record requested and resolved model/effort for Sol, Terra, and Luna.
- Any resolved route or effort differs from `gpt-5.6-sol/xhigh`, `gpt-5.6-terra/high`, or `gpt-5.6-luna/medium` respectively.
- A fallback model is silently accepted.
- Sol-V is not run in a fresh context, reads worker self-evaluations as evidence, changes frozen criteria, or validates its own authored implementation.
- The candidate lacks two consecutive clean Sol-V rounds within three total rounds.

### 3.9 Packaging and rendering

- The release manifest and archive membership differ.
- A release file's SHA-256 differs from the manifest.
- The archive fails integrity testing or UTF-8 filename extraction on macOS/Linux and Windows-compatible tooling.
- Markdown, DOCX, or PDF lacks a required section, contains broken internal links, or renders a claim number/table/figure differently from source records.
- Visual inspection finds missing Chinese glyphs, substituted unreadable font, clipped text, broken pagination, hidden overflow, missing images, incorrect claim numbering, or inaccessible figure captions.

## 4. Mechanical test matrix

Every row is mandatory. Fixture content MUST be synthetic or redistributable public material and MUST contain no private project data.

| ID | Locale / type | Scenario | Required assertions |
|---|---|---|---|
| `ZH-INV-01` | `zh-CN` / invention | documented engineering description, no measurements | generated benefits remain proposed; unsupported measured count `0`; trace `100%` |
| `ZH-UM-02` | `zh-CN` / utility model | structural fixture with method-like source wording | independent claim remains product-structural; dependencies valid; trace `100%` |
| `ZH-CONFLICT-03` | `zh-CN` / invention | two sources disagree on a numeric bound | conflict preserved; drafting blocked until human disposition |
| `ZH-SECRET-04` | `zh-CN` / invention | seeded token, personal contact, absolute path, and denylist identifier | scan identifies all seeds; package and external query blocked |
| `EN-INV-05` | `en-US` / invention | offline run using cached prior art | no network attempt; full local draft/trace/scorecard succeeds |
| `EN-UM-06` | `en-US` / utility model | duplicate patent publications from one family | family collapses to one comparison unit; duplicate count `0` |
| `EN-CONFLICT-07` | `en-US` / invention | unsupported performance target stated as past result | statement reclassified/reworded or blocked; unsupported measured count `0` in accepted output |
| `EN-SECRET-08` | `en-US` / utility model | confidential terms embedded in DOCX/PDF metadata and archive member | metadata/member detected; clean package contains none |
| `BI-PAIR-09` | `bilingual` / invention | aligned Chinese/English claims | atomic consistency `100%`; same numbers, modality, and dependencies |
| `BI-DRIFT-10` | `bilingual` / utility model | English omits one structural limitation | pair marked conflict; score below `100%`; acceptance blocked |
| `AUTO-ZH-11` | `auto` / invention | Chinese controlling request, English-heavy inputs | output resolves to `zh-CN` |
| `AUTO-EN-12` | `auto` / invention | English controlling request, Chinese-heavy inputs | output resolves to `en-US` |
| `DATE-13` | any / invention | patent publication after critical date | source retained as context but excluded as qualifying prior art |
| `GATE-14` | any / either | no concept approval/public-boundary confirmation | stage 8 cannot start |
| `STALE-15` | any / either | evidence changes after trace generation | stages 9–10 reset to pending; stale package rejected |
| `MEDIA-16` | both READMEs | one valid CC BY asset and one unknown-license asset | valid asset ledger passes; unknown asset blocks release |

### 4.1 Required metric assertions

For every fixture that is expected to reach a non-blocked package:

- evidence coverage: `100.0%`;
- unsupported measured claims: `0`;
- duplicate patent families: `0`;
- claim trace coverage: `100.0%`;
- confidentiality findings: `0` after sanitization/package build;
- bilingual atomic consistency: `100.0%` when applicable;
- validator exit code: `0`.

Negative fixtures MUST fail for the named reason and MUST NOT be converted into a passing package by dropping the problematic source or limitation without an auditable disposition.

### 4.2 Determinism and round-trip tests

- Running validators twice against unchanged content MUST yield identical metrics, finding IDs, and canonical record order after excluding timestamps.
- Build, extract, and rebuild MUST preserve all canonical JSON/YAML/JSONL content hashes.
- JSONL parsing and serialization MUST preserve Unicode and verbatim evidence text; no mojibake or newline corruption is allowed.
- Case-relative locators MUST remain valid after moving the case directory to a different parent path.

## 5. Documentation, link, and media checks

Before Sol-V review, the release candidate MUST provide machine-readable evidence that:

1. English README is the default entry and links prominently to the complete Chinese README; the Chinese README links back.
2. Both README first screens answer: what problem is solved, how to run in five minutes, and how unsupported claims are detected.
3. Both READMEs contain the evidence-first tagline, synthetic-case disclaimer, legal disclaimer, and a reproducible bad-draft → audit → corrected-draft example.
4. Installation and quick start succeed in a clean temporary environment with no credentials and network disabled except for the explicit link test.
5. Every documented command exists and `--help` exits `0`.
6. All Markdown links are syntactically valid; public source and license URLs pass the retrieval rule in section 3.4.
7. The social preview is exactly `1280×640`, below `1,000,000` bytes, readable at 50% scale, and contains no unverifiable performance claim.
8. Community files include contribution guidance, Code of Conduct, security/confidentiality policy, citation metadata, pull-request template, and issue forms for bugs, cases, and feature proposals.
9. Four ready-to-open `good first issue` drafts cover: a public case, bilingual terminology, a jurisdiction adapter, and image-evidence extraction. They MUST specify acceptance criteria and required source/license fields.
10. No third-party analytics, tracking pixel, remote telemetry, or badge that leaks visitor data is embedded.

## 6. DOCX/PDF and archive acceptance

A release candidate MUST be built in a clean temporary directory and produce Markdown, DOCX, PDF, and a ZIP package for at least `ZH-INV-01` and `BI-PAIR-09`.

Automated checks MUST verify:

- each expected heading, claim number, table, figure reference, and disclaimer is present;
- DOCX and PDF text extraction contains the same claim numbers and numeric limitations as Markdown;
- the ZIP passes CRC/integrity checks and contains only release-manifest paths;
- all non-ASCII archive names carry UTF-8 metadata;
- no hidden temporary, lock, cache, metadata-sidecar, or source-input file is present.

Human visual review MUST open the actual DOCX and PDF and record, per document: viewer used, page count, Chinese font/glyph status, table and figure status, claim numbering, page breaks, and any warnings. “Not inspected” is blocking.

## 7. Sol-V review protocol

### 7.1 Inputs

Sol-V receives only:

- frozen `SPEC.md` and this contract;
- route-probe record;
- raw candidate diff or release tree;
- raw test report and command logs;
- release manifest, hashes, rendered artifacts, and media-license ledger.

Worker summaries, confidence statements, and “done” claims are excluded.

### 7.2 Finding format

Every finding MUST use:

```text
Finding: concise defect
Evidence: exact path/record/test output
Impact: violated requirement and user consequence
Fix: concrete remediation
Priority: P0 | P1 | P2 | P3
Confidence: high | medium | low
```

P0 and P1 are critical for convergence. P2/P3 findings do not block only when this contract does not classify the underlying condition as blocking and a maintainer records disposition.

### 7.3 Convergence

- Maximum: three Sol-V rounds.
- Clean round: no new P0/P1 finding and no unresolved P0/P1 finding.
- Ready state requires two consecutive clean rounds on the same candidate content hash. Any content change after a clean round resets the consecutive-clean count to zero, except regeneration that is byte-identical for normative artifacts.
- If a worker fails to fix the same root cause twice at the assigned route, Sol rescue owns the remediation decision; acceptance criteria remain unchanged.
- If two consecutive clean rounds are not achieved by round three, status is `BLOCKED` with remaining findings.

## 8. Publication handoff

When and only when status is `READY_FOR_PUBLICATION_REVIEW`, prepare a human-readable handoff containing:

- actual GitHub account detected but not acted upon;
- proposed repository name `evidence-first-patent-skill`;
- visibility proposed as public;
- code license Apache-2.0 and original-content license CC BY 4.0;
- exact release manifest and SHA-256;
- proposed 12 Topics and four Discussions categories;
- proposed `v0.1.0` release notes in English and Chinese;
- an explicit statement that no repository, push, release, settings change, or post has occurred.

The user must separately approve the exact account, manifest, licenses, and external actions before publication tooling is invoked.

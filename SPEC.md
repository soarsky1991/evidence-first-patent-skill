# Evidence-First Patent Skill v0.1.0 Specification

Status: **FROZEN**  
Normative language: **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are requirements terms.  
Product line: **Draft from evidence, not imagination / 从证据出发，不把目标写成结果。**

## 1. Product definition / 产品定义

`draft-patents-evidence-first` is a bilingual agent Skill for engineering teams and patent professionals collaborating on Chinese invention-patent and utility-model disclosure packages. It turns user-supplied engineering materials and public prior art into:

1. an evidence inventory;
2. candidate inventive concepts and a human selection gate;
3. a closest-prior-art comparison and risk record;
4. a technical disclosure draft;
5. a claim framework, not a filing-ready legal opinion;
6. a claim-to-evidence trace; and
7. an integrity scorecard and review package.

The Skill's differentiator is evidence governance. It MUST distinguish source-backed facts from inferences and proposed designs, preserve verbatim provenance, and prevent unverified targets from being presented as achieved results.

### 1.1 Intended users

- Primary: engineers, R&D managers, in-house intellectual-property teams, and patent agents collaborating before formal drafting or filing.
- Secondary: educators and open-source contributors studying reproducible patent workflows.
- The Skill MUST assume a human patent professional reviews all claims, legal conclusions, filing decisions, and public disclosures.

### 1.2 v0.1.0 supported scope

- Jurisdiction workflow: China (`CN`) only.
- Patent types: invention disclosure (`invention`) and utility-model disclosure (`utility_model`).
- Languages: Simplified Chinese (`zh-CN`), US English (`en-US`), automatic selection (`auto`), and paired output (`bilingual`).
- Input: local text, Markdown, JSON, JSONL, YAML, CSV, DOCX, PDF, PPTX, XLSX, and common still-image formats when a suitable local extractor is available.
- Core output: UTF-8 Markdown, YAML, JSON, and JSONL.
- Optional output: DOCX and PDF when the required local document runtime is available.
- Offline operation: inventory, evidence classification, drafting, tracing, scoring, and packaging MUST work without network access. Prior-art discovery MAY be unavailable offline, but previously cached public sources MUST remain usable.

### 1.3 Explicitly out of scope

- Filing, publication, prosecution, freedom-to-operate opinions, infringement opinions, validity opinions, or guaranteed grant outcomes.
- Legal adaptation for the United States, European Patent Office, PCT, or any jurisdiction other than China.
- Bypassing paywalls, authentication, robots restrictions, database terms, privacy controls, or access controls.
- Inventing experimental data, dates, inventors, ownership, public disclosures, priority claims, citations, or patent-family relationships.
- Sending confidential source text to external search or model services without explicit, case-specific human approval.
- Treating an AI-generated translation as legally controlling when a bilingual pair differs.

## 2. Ten-stage workflow / 十阶段工作流

The Skill MUST execute stages in order and persist stage status. A stage may be rerun, but later outputs MUST be invalidated when an upstream source, evidence item, selected concept, or claim limitation changes.

1. **Intake and confidentiality scan**: inventory inputs, calculate content hashes, detect likely secrets and identifiers, and establish disclosure boundaries.
2. **Source extraction**: extract text, tables, figures, page/slide/sheet coordinates, and file metadata without overwriting originals.
3. **Evidence classification**: assign every material technical statement one evidence class: `measured`, `documented`, `inferred`, or `designed`.
4. **Concept generation and deduplication**: propose candidate inventive concepts, group semantic duplicates, and retain source links.
5. **Prior-art research**: generate sanitized queries, verify publication dates, record public URLs, and group patent-family duplicates.
6. **Comparison and scoring**: produce the closest-prior-art feature table, risk table, and selection scorecard separately for each patent type.
7. **Human selection gate**: stop before substantive drafting until the user records one selected concept and confirms the public-disclosure boundary.
8. **Draft package**: prepare the disclosure, claim framework, figure plan, implementation options, and verification matrix.
9. **Trace and bilingual comparison**: map every claim limitation to evidence and compare bilingual outputs at the atomic-limitation level.
10. **Adversarial review and acceptance**: scan unsupported claims, visible sensitive terms, trace completeness, family duplicates, document rendering, and package integrity.

No command in v0.1.0 may submit, publish, upload, or file a patent application. External search MUST use a sanitized query preview; if any confidential or personally identifying term remains, the query MUST be blocked.

## 3. Case directory and public interfaces / 案件目录与公共接口

### 3.1 Canonical layout

An initialized case MUST use this stable layout:

```text
case-root/
├── case.yaml
├── input/                 # immutable user-provided copies or references
├── work/
│   ├── sources.jsonl
│   ├── evidence.jsonl
│   ├── claim_trace.jsonl
│   ├── scorecard.json
│   └── stage_status.json
├── output/
│   ├── disclosure.md
│   ├── claims.md
│   ├── prior_art.md
│   ├── risk_register.md
│   └── verification_matrix.md
└── package/               # optional DOCX/PDF/archive output
```

Original input files MUST be byte-preserved. Generated records MUST reference originals by case-relative path and SHA-256, never by machine-specific absolute path.

### 3.2 `case.yaml`

Required keys and constraints:

| Key | Type | Rule |
|---|---|---|
| `schema_version` | string | MUST equal `0.1.0` |
| `case_id` | string | `^[a-z0-9][a-z0-9-]{2,63}$`; non-identifying |
| `language` | enum | `zh-CN`, `en-US`, `auto`, or `bilingual` |
| `jurisdiction` | enum | MUST equal `CN` |
| `patent_type` | enum | `invention` or `utility_model` |
| `critical_date` | date/null | ISO `YYYY-MM-DD`; null means research conclusions are provisional |
| `priority_claimed` | boolean | `false` by default; `true` requires a human-entered priority record |
| `confidentiality_mode` | enum | `local_only`, `sanitized_search`, or `approved_external` |
| `human_gate` | object | keys `selected_concept_id`, `approved_by`, `approved_at`, `public_boundary_confirmed` |

`approved_by` MUST be a non-secret reviewer label, not an email address. `approved_at` MUST be an RFC 3339 timestamp. Stage 8 MUST be blocked unless `selected_concept_id` is non-empty and `public_boundary_confirmed` is `true`.

### 3.3 `sources.jsonl`

Each line MUST be a JSON object with:

| Field | Type | Rule |
|---|---|---|
| `source_id` | string | unique; `SRC-` plus four or more digits |
| `source_type` | enum | `internal_file`, `patent`, `paper`, `standard`, `web`, `user_statement`, `synthetic` |
| `title` | string | required |
| `locator` | string | case-relative path for local sources or canonical HTTPS URL for public sources |
| `sha256` | string/null | required for local files; lowercase 64-hex |
| `publication_date` | date/null | verified publication date where relevant |
| `accessed_at` | date/null | required for network sources |
| `family_id` | string/null | normalized family identifier for patent sources |
| `license` | string/null | required when redistributing content or media |
| `language` | string | BCP 47 tag |
| `public_status` | enum | `confidential`, `public`, `synthetic` |
| `verification_status` | enum | `verified`, `unverified`, `blocked` |

Public patent sources MUST record the publication number in `title` or `family_id`. A prior-art comparison MUST NOT treat a source with `publication_date=null` or `verification_status!=verified` as date-qualified prior art.

### 3.4 `evidence.jsonl`

Each line MUST be a JSON object with:

| Field | Type | Rule |
|---|---|---|
| `evidence_id` | string | unique; `EV-` plus four or more digits |
| `source_id` | string | MUST resolve to `sources.jsonl` |
| `source_location` | object | one or more of `page`, `slide`, `sheet`, `cell_range`, `paragraph`, `figure`, `timestamp`; plus optional `bbox` |
| `verbatim` | string | exact source text; empty only for a visual observation with a documented description |
| `statement` | string | normalized technical proposition |
| `evidence_class` | enum | `measured`, `documented`, `inferred`, or `designed` |
| `verification_status` | enum | `verified`, `needs_review`, `rejected` |
| `public_status` | enum | `confidential`, `sanitized`, `public`, `synthetic` |
| `derived_from` | array[string] | required and non-empty for `inferred`; otherwise may be empty |
| `review_notes` | string | required when status is not `verified` |

Classification rules are normative:

- `measured`: a recorded observation or test result with identifiable method, specimen/context, value or qualitative result, and source location.
- `documented`: explicitly stated in an identifiable source but not a project measurement.
- `inferred`: reasoned from one or more evidence records; MUST list `derived_from` and MUST NOT be worded as observed fact.
- `designed`: a proposed parameter, structure, target, optional embodiment, or verification plan; MUST NOT be worded as achieved performance.

Changing `verbatim`, `source_location`, or `evidence_class` MUST invalidate dependent traces and scorecards.

### 3.5 `claim_trace.jsonl`

Each line represents one atomic claim limitation:

| Field | Type | Rule |
|---|---|---|
| `claim_id` | string | `CLM-` plus three or more digits |
| `claim_number` | integer | positive |
| `parent_claim_number` | integer/null | null for independent claims; MUST reference a lower existing number otherwise |
| `limitation_id` | string | unique within case; `LIM-` plus four or more digits |
| `language` | enum | `zh-CN` or `en-US` |
| `limitation_text` | string | one atomic technical limitation |
| `evidence_ids` | array[string] | non-empty; every ID MUST resolve |
| `semantic_status` | enum | `supported`, `inferred`, `designed`, `conflict`, `missing` |
| `human_review_status` | enum | `pending`, `accepted`, `rejected` |
| `paired_limitation_id` | string/null | required in bilingual mode; points to the other language |

Every limitation in a generated claim MUST have exactly one current trace row per output language. `conflict` or `missing` MUST block acceptance. `inferred` or `designed` MAY appear in a proposed claim only when explicitly identified in the review package and accepted by a human reviewer; it MUST NOT be described as experimentally verified.

### 3.6 `scorecard.json`

Required fields:

```json
{
  "schema_version": "0.1.0",
  "generated_at": "RFC3339 timestamp",
  "evidence_coverage_pct": 0.0,
  "unsupported_measured_claims": 0,
  "duplicate_patent_families": 0,
  "claim_trace_coverage_pct": 0.0,
  "bilingual_atomic_consistency_pct": null,
  "confidentiality_findings": 0,
  "blocking_findings": [],
  "status": "BLOCKED"
}
```

Metrics MUST use these formulas:

- `evidence_coverage_pct = 100 * material technical statements with >=1 non-rejected evidence record / all material technical statements`.
- `claim_trace_coverage_pct = 100 * claim limitations with a resolvable trace and non-missing status / all claim limitations`.
- `bilingual_atomic_consistency_pct = 100 * limitation pairs with matched object, relation, numeric bounds, dependency, and modality / all limitation pairs`; null outside bilingual mode.
- `duplicate_patent_families` counts additional compared references sharing a normalized family ID with an already retained reference.
- `unsupported_measured_claims` counts achieved-result or measurement statements lacking verified `measured` evidence.

Only the acceptance process may set `status` to `READY_FOR_PUBLICATION_REVIEW`.

### 3.7 `stage_status.json`

The file MUST contain all stages `1` through `10`, each with `status` (`pending`, `in_progress`, `blocked`, `complete`), `input_hash`, `output_hash`, `updated_at`, and `blocking_reasons`. At most one stage may be `in_progress`. A changed upstream `input_hash` MUST set all later stages to `pending` and clear their output hashes.

## 4. Language and drafting rules / 语言与撰写规则

### 4.1 Language selection

- `zh-CN`: all narrative deliverables and claim text in native technical Chinese; identifiers and schema keys remain English.
- `en-US`: all narrative deliverables and claim text in clear US technical English; no claim of US legal adaptation.
- `auto`: select the language used by the user's controlling request. Mixed input alone MUST NOT change the output language. Record the resolved language in stage status.
- `bilingual`: produce Chinese as the controlling working version for the CN workflow and an aligned English companion. Neither version may silently add, remove, broaden, narrow, or reorder a claim dependency.

### 4.2 Bilingual alignment

The comparator MUST atomize each claim into technical object, components/steps, relationships, numeric bounds, conditions, modality, and dependency. A pair fails if any atom is missing, additional, contradictory, or materially different. Translation quality alone is insufficient.

When a mismatch occurs, the system MUST:

1. preserve both original versions;
2. mark the pair `conflict`;
3. identify the differing atoms; and
4. require human resolution before packaging.

### 4.3 Evidence-visible versus clean drafts

- Internal review outputs MAY display evidence IDs and classes.
- Clean narrative drafts MUST move machine labels to sidecar trace files and use natural language such as “proposed embodiment” or “to be verified” where needed.
- Quantified benefits MUST be either linked to verified measured evidence or described as a target/test criterion. They MUST NOT be converted from targets into past-tense results.
- Utility-model claims MUST protect product structure and relationships, not method steps as the sole subject matter.

## 5. Confidentiality, safety, and legal boundaries / 保密、安全与法律边界

### 5.1 Confidentiality modes

- `local_only`: no source content, filenames, extracted terms, hashes, or queries may leave the local environment.
- `sanitized_search`: only a human-previewed query stripped of organizations, people, project codes, customer/supplier names, unpublished dimensions, unpublished parameter combinations, paths, credentials, and unique identifiers may be sent externally.
- `approved_external`: specific source excerpts may be sent only after the case records what data, recipient/service, purpose, approver label, and approval timestamp. Approval is scoped to those excerpts and that service.

The default is `local_only`. A model or tool failure MUST NOT silently downgrade confidentiality.

### 5.2 Required secret and privacy scanning

Before packaging, scan all tracked content and generated archives for:

- credentials, tokens, private keys, cookies, session data, email addresses, phone numbers, personal addresses, and personal identifiers;
- absolute local paths and user names;
- organization, customer, supplier, product, and project identifiers declared in the case denylist;
- confidential filenames, embedded document metadata, comments, tracked changes, hidden sheets/slides, image metadata, and archive members.

Any confirmed finding is blocking. Potential findings require human disposition with a recorded rationale; allowlisting MUST be exact, case-local, and reviewable.

### 5.3 Legal boundary

Every README-facing example and generated review package MUST state that the Skill provides drafting and evidence-governance assistance, not legal advice, and does not guarantee patentability, validity, non-infringement, freedom to operate, ownership, or grant. It MUST recommend review by qualified counsel before disclosure, filing, or reliance.

The Skill MUST not determine inventorship from contribution data. It may collect candidate contributor facts for human/legal review without labeling a person an inventor.

## 6. Public cases and media / 公开案例与图片

### 6.1 Public prior-art case

The repository MAY include a mechanical-domain case based solely on public patent records. It MUST be unrelated to any contributor's confidential client or internal semiconductor work. Each cited record MUST have:

- a canonical public URL;
- publication number and verified publication date;
- a family identifier or explicit `family unknown` state;
- an access date;
- status wording sourced from an authoritative public record, or omitted; and
- excerpts short enough to respect source terms and copyright.

“Expired”, “lapsed”, “ceased”, or similar legal-status labels MUST NOT be asserted from memory or from an unverified aggregator field. If status matters and cannot be verified, use `status not relied upon`.

### 6.2 Synthetic end-to-end case

The complete drafting demonstration MUST be wholly synthetic and visibly labeled in English and Chinese on every entry page:

> Synthetic demonstration — not a real client matter, not known to be novel, and not filing-ready.  
> 虚构演示——并非真实客户案件，未确认具备新颖性，也不可直接用于申请。

Synthetic facts MUST use `source_type=synthetic` and `public_status=synthetic`. Synthetic measured data MAY be used only when explicitly labeled “mock data for workflow testing” in the source, evidence record, and rendered output. Prefer test targets over mock measurements.

### 6.3 Images and diagrams

- Original diagrams created for the repository SHOULD be preferred and MUST be labeled as illustrations rather than measured apparatus.
- External media may be redistributed only when its license permits repository redistribution and modification status is known.
- Every external asset MUST have an entry containing `asset_path`, `source_url`, `creator`, `license`, `license_url`, `retrieved_at`, `modifications`, and `sha256`.
- Allowed default licenses: CC0, CC BY 4.0, CC BY-SA 4.0, and public-domain works with verifiable status. Other licenses require explicit review.
- No fair-use-only, all-rights-reserved, unknown-license, paywalled, screenshot-of-web-UI, logo, or contributor-confidential image may ship in v0.1.0.
- Alt text MUST describe informational content in both README languages. Images containing material text MUST have a text equivalent.

## 7. Model orchestration / 模型编排

The default development and evaluation routing is:

| Role | Requested route | Responsibility | Prohibited action |
|---|---|---|---|
| Sol-A | `gpt-5.6-sol`, `xhigh` | freeze architecture, interfaces, boundaries, and acceptance criteria | routine implementation or self-approval |
| Terra | `gpt-5.6-terra`, `high` | implement schemas, scripts, Skill resources, CI, packaging | weakening frozen criteria or declaring release readiness |
| Luna | `gpt-5.6-luna`, `medium` | prepare bilingual content, public cases, terminology, media ledger, and test fixtures | final legal, novelty, or acceptance judgment |
| Sol-V | fresh `gpt-5.6-sol`, `xhigh` context | independently review raw diff, artifacts, and test evidence | reading worker self-assessments or changing the frozen spec |

Before assigned work, the router MUST run the same bounded probe against all three requested routes and record requested model, requested effort, resolved model, resolved effort, timestamp, and a non-sensitive output digest. Any missing route, fallback, or mismatch MUST stop orchestrated implementation rather than silently substitute a model.

This routing is a development profile, not a runtime dependency of the public Skill. Public users MAY run the Skill on other capable agents; the evidence, gate, and acceptance rules remain unchanged.

Model outputs are untrusted proposals. Deterministic validators and human gates control state transitions. No worker model may alter `SPEC.md`, `.workflow/ACCEPTANCE.md`, or mark its own work accepted.

## 8. Licensing and public packaging / 许可与公开打包

- Source code and executable scripts: Apache License 2.0.
- Original documentation, examples, and original diagrams: CC BY 4.0, identified in the repository's licensing notice.
- Third-party assets: their recorded upstream license; they MUST NOT be relicensed by the repository.
- Generated case output: user's responsibility, with inherited third-party restrictions preserved.
- Contributions use Developer Certificate of Origin sign-off; no contributor license agreement is required for v0.1.0.

The repository package MUST exclude caches, source inputs, approval logs containing personal data, test secrets, local paths, private research notes, and any file not explicitly included by the release manifest.

## 9. Versioning and change control / 版本与变更控制

- Schemas use `schema_version: 0.1.0` and semantic versioning after v0.1.0.
- Adding optional fields is backward-compatible only when old validators safely ignore them.
- Renaming fields, changing enum meaning, relaxing evidence requirements, or changing metric formulas requires a schema-version change and migration note.
- This specification is frozen for v0.1.0. Implementation defects MUST be fixed in implementation; acceptance thresholds MUST NOT be lowered to obtain a pass.
- A specification change requires an explicit maintainer decision, documented rationale, a new specification hash, and re-running all acceptance tests.

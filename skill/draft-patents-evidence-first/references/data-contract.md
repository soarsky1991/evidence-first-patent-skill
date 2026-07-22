# Data contract / 数据接口

The stable case interface is `case.yaml`, `work/sources.jsonl`, `work/evidence.jsonl`, `work/claim_trace.jsonl`, `work/scorecard.json`, and `work/stage_status.json`. IDs are stable; locators are case-relative; local source hashes are SHA-256. See the frozen `SPEC.md` for normative fields.

## Evidence classes / 证据分类

| Class | Meaning | Safe wording |
|---|---|---|
| `measured` | recorded observation with method/context and location | “recorded measurement” |
| `documented` | explicit source statement, not a project measurement | “the source states…” |
| `inferred` | reasoned from evidence; list `derived_from` | “may indicate…” |
| `designed` | proposed structure, target, option, or test plan | “proposed / to be verified” |

Never turn a designed target into a past-tense result. Do not delete rejected evidence or conflicting traces to improve a score; record disposition and rerun downstream stages.

## Minimal JSONL examples / 最小 JSONL 示例

```json
{"source_id":"SRC-0001","source_type":"synthetic","title":"Mock fixture description","locator":"input/description.md","sha256":"7b4ded952a1ce77ee805350a99e3ecd6cb445da23b84653b08d4323d0f8ef836","publication_date":null,"accessed_at":null,"family_id":null,"license":"CC BY 4.0","language":"en-US","public_status":"synthetic","verification_status":"verified"}
{"evidence_id":"EV-0001","source_id":"SRC-0001","source_location":{"paragraph":"2"},"verbatim":"The guide is arranged beside the rail.","statement":"A guide is arranged beside a rail.","evidence_class":"documented","verification_status":"verified","public_status":"synthetic","derived_from":[],"review_notes":""}
{"claim_id":"CLM-001","claim_number":1,"parent_claim_number":null,"limitation_id":"LIM-0001","language":"en-US","limitation_text":"a guide arranged beside the rail","evidence_ids":["EV-0001"],"semantic_status":"supported","human_review_status":"pending","paired_limitation_id":null}
```

The source hash above is the SHA-256 of the exact UTF-8 bytes `The guide is arranged beside the rail.\n`. A qualifying public patent may retain a licensed local cache, but it also needs a separate `canonical_url`, verified `publication_date`, `accessed_at`, and `verification_status=verified`; comparison prose binds the conclusion to its `source_id`.

In bilingual cases, each trace row additionally carries a SHA-256 of `limitation_text` and a persisted `atom_map`, for example `[{"type":"object","canonical":"guide","text_span":"guide"}]`. The pair must map every technical object, component/step, relationship, numeric bound, condition, and modality that appears; dependency is checked from `parent_claim_number`.

## Scorecard reading / 指标

`evidence_coverage_pct` and `claim_trace_coverage_pct` must be `100.0` for a non-blocked package. `unsupported_measured_claims` and `duplicate_patent_families` must be `0`; bilingual atomic consistency is `100.0` in bilingual mode. Only the acceptance process may set `READY_FOR_PUBLICATION_REVIEW`.

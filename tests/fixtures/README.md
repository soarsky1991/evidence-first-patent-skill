# Acceptance fixture index / 验收 fixture 索引

All fixture records are synthetic and redistributable. Negative fixtures preserve the defect and expected blocking reason; they are not weakened into passing cases.

| ID | Locale/type | Scenario | Expected assertion |
|---|---|---|---|
| ZH-INV-01 | zh-CN / invention | documented description, no measurements | benefits proposed; trace 100%; measured 0 |
| ZH-UM-02 | zh-CN / utility_model | structural fixture with method-like wording | product-structural independent claim |
| ZH-CONFLICT-03 | zh-CN / invention | numeric disagreement | conflict preserved; drafting blocked |
| ZH-SECRET-04 | zh-CN / invention | token, contact, path, denylist seed | all detected; package blocked |
| EN-INV-05 | en-US / invention | offline cached prior art | no network; local package succeeds |
| EN-UM-06 | en-US / utility_model | duplicate publications | one family unit; duplicate count 0 |
| EN-CONFLICT-07 | en-US / invention | target written as result | reword or block; measured 0 |
| EN-SECRET-08 | en-US / utility_model | metadata/archive secret | clean package has none |
| BI-PAIR-09 | bilingual / invention | aligned claims | atomic consistency 100% |
| BI-DRIFT-10 | bilingual / utility_model | omitted structural limitation | conflict; score below 100% |
| AUTO-ZH-11 | auto / invention | Chinese controlling request | resolves zh-CN |
| AUTO-EN-12 | auto / invention | English controlling request | resolves en-US |
| DATE-13 | any / invention | later publication | context only, not qualifying prior art |
| GATE-14 | any / either | no human gate | stage 8 blocked |
| STALE-15 | any / either | evidence changed after trace | stages 9–10 pending |
| MEDIA-16 | both READMEs | valid CC BY plus unknown license | valid ledger passes; unknown blocks |

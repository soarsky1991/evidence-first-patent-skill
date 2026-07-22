# Ten-stage workflow / 十阶段工作流

Run stages in order and persist status in `work/stage_status.json`; an upstream hash change resets downstream completion.

1. Inventory inputs, hashes, confidentiality boundary. / 盘点输入、哈希和保密边界。
2. Extract text, tables, figures, and locations without overwriting originals. / 提取文本、表格、图和位置，不覆盖原件。
3. Classify each technical statement as `measured`, `documented`, `inferred`, or `designed`. / 分类每条技术陈述。
4. Generate and deduplicate concepts while preserving source links. / 生成并去重概念，保留来源。
5. Research with human-approved sanitized queries; verify dates and families. / 仅用人工批准的脱敏查询，核验日期和家族。
6. Compare closest prior art and score risks separately for each patent type. / 分别比较两类专利的最接近现有技术和风险。
7. Require a selected concept and confirmed public boundary. / 要求选定概念并确认公开边界。
8. Draft disclosure, claim framework, figure plan, options, and verification matrix. / 撰写披露、权利要求框架、附图计划、方案和验证矩阵。
9. Trace every limitation and compare bilingual atoms. / 溯源每个限定并比较双语原子。
10. Review unsupported claims, privacy, families, rendering, and package integrity. / 审核无证据陈述、隐私、家族、渲染和包完整性。

Stages 8–10 are blocked until `human_gate.selected_concept_id` is non-empty and `public_boundary_confirmed` is `true`. No stage submits, publishes, uploads, or files.

# Bilingual limitation review / 双语限定审核

Pair one Chinese and one English atomic limitation. Compare object, components or steps, relationship, numeric bounds, condition, modality, and dependency. If any atom differs, preserve both texts, set `semantic_status: conflict`, identify the differing atoms, and require human resolution. Translation fluency cannot cure a technical mismatch.

For every bilingual trace row, persist `limitation_text_sha256` and an `atom_map`. Each atom-map entry contains `type`, a language-neutral `canonical` value, and the exact `text_span` found in that limitation. The validator checks the text hash and span, compares both canonical maps bidirectionally, and derives dependency from `parent_claim_number`. This makes an edited translation stale instead of silently accepting it through a small built-in dictionary.

Run `compare_bilingual.py CASE_DIR --check` for a read-only check. Run `--mark-conflicts` to preserve both texts while marking both trace rows `conflict` and recording `bilingual_differences`; the case then remains blocked until a human resolves and accepts the pair.

Recommended review row / 推荐审核行：

| Atom | zh-CN | en-US | Result |
|---|---|---|---|
| object | 导向件 | guide | aligned |
| relation | 位于导轨旁 | beside the rail | aligned |
| modality | 拟设置 | proposed to be arranged | aligned |
| dependency | 从属项 2 | dependent claim 2 | aligned |

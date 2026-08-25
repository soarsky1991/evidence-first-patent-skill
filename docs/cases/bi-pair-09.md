# 合成案例：BI-PAIR-09 双语原子限定核对

> **SYNTHETIC / 合成案例。** `BI-PAIR-09` 的装置、来源、文本和输出仅为双语工作流训练构造，不是客户案卷、公开案件或申请文件。

## 具体问题

中英文草稿即使读起来都顺畅，也可能在对象、关系、数值、条件或从属关系上悄悄改变技术边界。这个案例把双语一致性拆成可核对的原子项。

## 输入

- `BI-PAIR-09.zip` 中的合成本地来源、证据记录和双语原子限定；
- `case.yaml` 标记为 `bilingual`；
- 预生成的合成审阅输出与溯源记录。

## 方法

1. 校验案件结构和证据字段；
2. 让每项限定回链到证据编号；
3. 比对中英文对象、关系、数值、条件与从属关系；
4. 保留冲突，而不是为了可读性自行“润色”范围差异。

## 可复现输出

```sh
unzip BI-PAIR-09.zip -d demo-bilingual
python3 skill/draft-patents-evidence-first/scripts/validate_case.py ./demo-bilingual
python3 skill/draft-patents-evidence-first/scripts/trace_claims.py ./demo-bilingual --check
python3 skill/draft-patents-evidence-first/scripts/compare_bilingual.py ./demo-bilingual --check
```

发布包中预期出现 `VALID: 100.0% trace coverage` 和双语原子一致性检查结果。若样例压缩包未随当前检出提供，请改用对应 Release；不要以缺失包伪造命令结果。

## 证据

可审阅证据包括 `sources.jsonl`、`evidence.jsonl`、`claim_trace.jsonl`、双语对比结果与案例的版本/散列记录。它们只说明此合成数据集的字段与检查链可运行。

## 不支持的结论

不支持真实翻译无歧义、任何法域的权利要求范围正确、可专利性、有效性、侵权判断或提交资格。

## 3 分钟体验

解压案例后运行后三条检查命令。若报告冲突，保留冲突记录并停止把它称为一致；若通过，也只记录为“合成数据集的原子字段一致”。

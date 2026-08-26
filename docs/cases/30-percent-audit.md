# 合成案例：30% 性能目标被证据审计拦下

> **SYNTHETIC / 合成案例。** 人名、装置、数字、记录和输出均为训练用途构造；不来自客户，不构成测试、授权、法律或商业结论。

## 具体问题

一份初稿把“定位精度提高 30%”写为既成结果，但输入只有设计讨论和待执行的验证计划。风险不在语言是否流畅，而在 `measured` 的证据要求尚未满足。

## 输入

- 合成会议记录：提出结构调整与“目标为提高约 30%”；
- 合成验证计划：列出待比较的工况与指标，没有测试结果；
- 没有带方法、环境、原始值和来源位置的实测记录。

## 方法

1. 把目标句录为 `designed`，而不是 `measured`；
2. 在权利要求草案中仅保留可溯源的结构限定；
3. 将性能句改写为“待验证目标”，并在验证矩阵中登记缺口；
4. 运行验证器，要求 `unsupported_measured_claims = 0`。

## 可复现输出

```sh
python3 skill/draft-patents-evidence-first/scripts/init_case.py ./audit-demo \
  --case-id audit-demo --language zh-CN --patent-type invention
python3 skill/draft-patents-evidence-first/scripts/validate_case.py ./audit-demo
```

预期的初始化状态是 `BLOCKED`，而非“已完成”。随后按 [错误稿审计材料](../content/bad-draft-audit-correction.md) 的字段格式录入合成证据并再次校验；通过意味着无依据的实测断言被阻断或降级，并不意味着目标已实现。

## 证据

审计的可检查证据是：证据分类、来源位置、权利要求—证据溯源、验证矩阵和 `scorecard.json` 中的检查字段。它们可支持“系统没有把目标当作结果”的过程主张。

## 不支持的结论

本案例不支持“提高 30% 已在任何设备上实现”、任何新颖性/创造性/授权判断、可直接申请，或真实案件中的适用性。

## 3 分钟体验

从仓库根目录运行上述两条命令；打开生成的 `work/scorecard.json` 与 `output/verification_matrix.md`，确认空案件仍为 `BLOCKED`。这一步不联网、不上传资料。

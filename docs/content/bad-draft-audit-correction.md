# Bad draft → evidence audit → corrected draft / 错误稿→证据审计→修正稿

> Synthetic demonstration — not a real client matter, not known to be novel, and not filing-ready.
>
> 虚构演示——并非真实客户案件，未确认具备新颖性，也不可直接用于申请。

This material provides drafting and evidence-governance assistance, not legal advice. It does not guarantee patentability, validity, non-infringement, freedom to operate, ownership, grant, or fitness for filing. Obtain review from qualified patent counsel before disclosure, filing, or reliance.

本材料仅提供专利撰写与证据治理辅助，不构成法律意见，也不保证可专利性、有效性、不侵权、自由实施、权属、授权或适合直接申请。披露、申请或据此作出决定前，应由具备资质的专利专业人员审核。

## 1. Bad draft / 错误稿

“The guide eliminates vibration and improves positioning accuracy by 30%.”

“该导向件消除了振动，并将定位精度提高了 30%。”

Problem: the source states only that “the guide is beside the rail.” It provides no measurement method, specimen, numeric observation, or test record. “Eliminates” and “30%” are therefore presented as achieved results without evidence.

问题：原始材料只记载“导向件位于导轨旁”，没有测量方法、样件、数值或测试记录；“消除”和“30%”被写成既成结果。

## 1.1 Audit chain / 审计链

| Original input / 原始输入 | Processing action / 处理动作 | Output / 输出物 | Cannot claim / 不能声称 | Invalidated if evidence changes / 证据变化后失效项 |
|---|---|---|---|---|
| “The guide is beside the rail.” / “导向件位于导轨旁。” | Preserve its locator; classify as `documented`; create only a structural evidence record and atomic trace. / 保留来源定位；分类为 `documented`；仅建立结构证据记录和原子溯源。 | EV-0001 and a trace for “guide beside rail.” / EV-0001 及“导向件位于导轨旁”的溯源。 | Vibration elimination, a 30% accuracy gain, or any achieved effect. / 消除振动、精度提高 30% 或任何既成效果。 | EV-0001, the structural trace, corrected-draft wording, and related scorecard coverage. / EV-0001、结构溯源、修正稿措辞及相关评分覆盖。 |
| No test method, specimen, baseline, numeric observation, or test record. / 没有测试方法、样件、基线、数值观察或测试记录。 | Register an evidence gap; block `measured` classification and achieved-result language; add a verification-plan requirement. / 登记证据缺口；阻断 `measured` 分类和既成结果措辞；增加验证计划要求。 | An audit finding and a verification-matrix requirement. / 审计发现及验证矩阵要求。 | That the absence of evidence is a negative technical result, or that a target has been achieved. / 证据缺失本身是负面技术结果，或某项目标已经实现。 | The verification requirement and every downstream result statement if a method, specimen, baseline, threshold, or record is later added or revised. / 如后续新增或修订方法、样件、基线、阈值或记录，验证要求及所有下游结果陈述失效。 |

## 2. Evidence audit / 证据审计

| Statement / 陈述 | Record / 记录 | Class / 等级 | Finding / 发现 |
|---|---|---|---|
| guide beside rail / 导向件位于导轨旁 | EV-0001, paragraph 2 / 第2段 | documented / 已记录 | supported as source statement / 有来源陈述支持 |
| eliminates vibration / 消除振动 | none / 无 | — | missing evidence; block achieved-result wording / 缺少证据，阻断既成效果表述 |
| improves accuracy by 30% / 精度提高30% | none / 无 | — | unsupported measured claim; block / 无依据实测陈述，阻断 |

Audit action: retain the missing-result finding, do not delete it. Add a verification plan with specimen, measurement method, baseline, and acceptance threshold.

审计动作：保留缺少结果证据的发现，不得通过删除问题陈述来制造“通过”；另行建立包含试样、测量方法、基线和验收阈值的验证方案。

## 3. Corrected draft / 修正稿

“A proposed guide is arranged beside the rail. The arrangement is intended to constrain lateral movement. Vibration response and positioning accuracy remain to be verified against a documented baseline; no achieved percentage is asserted.”

“拟在导轨旁设置导向件，用于约束横向运动。振动响应和定位精度须以记录的基线和测试方法验证；本文不宣称已达到任何百分比结果。”

The claim trace should map only the structural limitation to EV-0001. The target belongs in the verification matrix, not as measured evidence.

权项溯源只能将结构限定映射至 EV-0001。性能目标应进入验证矩阵，不得登记为实测证据。

## 4. What changes after new evidence arrives / 新证据到来后会发生什么

New evidence is not a permission slip to keep the old correction unchanged. First check whether it identifies the specimen, method, baseline, measurement time, result, and source location. If any of those inputs changes, mark the affected verification row, result wording, scorecard metric, and any claim trace that relies on the interpretation as stale; then re-run human review. A result remains a target until the record supports its `measured` classification.

新证据并不意味着可以原样保留旧修正稿。应先核对其是否写明样件、方法、基线、测量时间、结果和来源定位。上述任一输入发生变化时，受影响的验证行、结果措辞、评分指标以及依赖该解释的任何权项溯源都应标为过期，再重新进行人工复核。在记录足以支持 `measured` 分类前，结果仍只是目标。

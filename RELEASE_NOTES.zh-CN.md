# v0.2.1 内容说明

- 增加多视图机械附图组一致性参考。
- 要求建立含状态的关系账本和共享母剖面，避免总装、剖视、对比和局部接触图各自演变成不同结构。
- 增加运动间隙、最大行程限位、拆装路径、开口槽拓扑、承托/接触链及比较尺寸基准检查。
- 分离带说明的事务所核对图与纯标号净线图，并增加文字白名单、300 dpi和600 dpi渲染检查。
- 增加修复复核与独立对抗复核，终止条件为未解决P0/P1均为零。
- 案件数据的 `schema_version` 仍保持 `0.1.0`；本补丁仅更新工作流指引和测试。

本公开版本仍只提供撰写与证据治理辅助，不构成法律意见、可专利性结论、申请受理结论或授权保证；实质性产物仍须由具备资质的专业人员审核。

可用下列命令在本地重建渲染样例和确定性归档：

```sh
python tests/build_release_samples.py --repo . --output dist/v0.2.1/samples
python tests/build_source_archive.py --repo . --output dist/v0.2.1/evidence-first-patent-skill-v0.2.1.zip
python tests/build_skill_archive.py --repo . --output dist/v0.2.1/draft-patents-evidence-first-v0.2.1.zip
```

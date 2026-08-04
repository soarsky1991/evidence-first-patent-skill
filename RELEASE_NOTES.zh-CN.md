# v0.2.0 内容说明

- 以中文作为 README 主入口，增加“专利君”视觉与治理说明。
- 在确定性源码归档之外，增加可直接安装的 Skill 专用归档。
- 在 CI 中增加公开入口、品牌、发布清单和归档成员校验。
- 增加“对外结构包”参考：分离对外交底材料与内控侧车，要求主装配账本，并规定五字段的批注答复格式。
- 案件数据的 `schema_version` 仍保持 `0.1.0`；本次仅更新工作流指引与发布方式。

本公开版本仍只提供撰写与证据治理辅助，不构成法律意见、可专利性结论、申请受理结论或授权保证；实质性产物仍须由具备资质的专业人员审核。

可用下列命令在本地重建渲染样例和确定性归档：

```sh
python tests/build_release_samples.py --repo . --output dist/v0.2.0/samples
python tests/build_source_archive.py --repo . --output dist/v0.2.0/evidence-first-patent-skill-v0.2.0.zip
python tests/build_skill_archive.py --repo . --output dist/v0.2.0/draft-patents-evidence-first-v0.2.0.zip
```

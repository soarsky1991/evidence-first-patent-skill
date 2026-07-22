# v0.1.0 内容说明

- 增加双语首屏说明、五分钟本地运行和“如何确认不编造”。
- 增加方法、数据接口、保密边界和双语审核参考。
- 增加合成发明、合成实用新型演示，以及公开机械记录阅读案例。
- 增加术语表、错误稿审计示例、原创溯源图和媒体许可台账。
- 在 `tests/fixtures` 下登记完整的 [16 项验收样本索引](tests/fixtures/README.md)。

这是首个可复现的公开工作流版本。它不构成法律意见、可专利性结论、申请受理结论或授权保证；实质性产物仍须由具备资质的专业人员审核。

可用下列命令在本地重建渲染样例和确定性源码归档：

```sh
python tests/build_release_samples.py --repo . --output dist/v0.1.0/samples
python tests/build_source_archive.py --repo . --output dist/v0.1.0/evidence-first-patent-skill-v0.1.0.zip
```

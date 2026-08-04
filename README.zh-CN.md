# 中文入口已迁移

完整且持续维护的中文说明位于仓库根目录 [README.md](README.md)。其中包括：

- Codex、Claude Code 和通用 Agent 安装方式；
- 3 分钟本地结构自检；
- 15 分钟完整双语样例；
- 证据闭环与项目验收闭环；
- 合成发明、合成实用新型、错误稿审计和公开机械记录阅读练习；
- 15 个常见问题及保密、许可边界。

English documentation: [README.en.md](README.en.md).

本文件只为旧链接、引用和 v0.1 命令契约保持兼容。新读者请从 [中文主入口](README.md) 开始。

## 五分钟本地运行

以下命令只使用 Python 标准库，不发起网络请求：

```sh
cd evidence-first-patent-skill
python3 skill/draft-patents-evidence-first/scripts/init_case.py ./demo-case --case-id demo-case --language bilingual --patent-type invention
python3 skill/draft-patents-evidence-first/scripts/validate_case.py ./demo-case
python3 skill/draft-patents-evidence-first/scripts/scan_sensitive.py ./demo-case --format json
```

预期状态是 `VALID: demo-case (initialized BLOCKED case)`。`BLOCKED` 表示空案尚未录入证据和人工门禁，不是执行失败。

继续阅读：

- [示例索引](examples/README.md)
- [公开机械专利阅读练习](examples/public-mechanical-case.md)
- [错误稿→证据审计→修正稿](docs/content/bad-draft-audit-correction.md)
- [保密政策](CONFIDENTIALITY.md)

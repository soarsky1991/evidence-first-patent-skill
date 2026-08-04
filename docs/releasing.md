# Manual release runbook / 手动发布手册

This repository only builds and verifies a local candidate. Creating a Git tag, pushing, publishing a GitHub Release, or uploading assets is an external state change and requires the maintainer's explicit confirmation.

本仓库只构建并校验本地候选包。创建 Git 标签、推送、发布 GitHub Release 或上传资产都会改变外部状态，必须由维护者明确确认后才可执行。

## Local candidate / 本地候选包

Run from the repository root with a clean, reviewed working tree. `VERSION` is the single release-version input; the case schema remains `0.1.0` and is not changed for a marketing or documentation release.

在仓库根目录执行，并确保工作区干净且改动已审阅。`VERSION` 是唯一的发布版本输入；案件 schema 固定为 `0.1.0`，不能因市场或文档版本而变更。

```sh
set -eu
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 skill/draft-patents-evidence-first/scripts/validate_media.py --ledger public-assets/media-ledger.md
RELEASE_DIR="dist/$(python3 tests/release_common.py --repo . --format release-directory)"
SOURCE_ARCHIVE="$(python3 tests/release_common.py --repo . --format source-archive)"
SKILL_ARCHIVE="$(python3 tests/release_common.py --repo . --format skill-archive)"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"
python3 tests/build_release_samples.py --repo . --output "$RELEASE_DIR/samples"
python3 tests/build_source_archive.py --repo . --output "$RELEASE_DIR/$SOURCE_ARCHIVE"
python3 tests/build_skill_archive.py --repo . --output "$RELEASE_DIR/$SKILL_ARCHIVE"
python3 tests/build_release_manifest.py --repo . --release "$RELEASE_DIR" --output "$RELEASE_DIR/release-manifest.json"
python3 tests/verify_release_assets.py --repo . --release "$RELEASE_DIR" --manifest "$RELEASE_DIR/release-manifest.json" --source-archive "$RELEASE_DIR/$SOURCE_ARCHIVE" --skill-archive "$RELEASE_DIR/$SKILL_ARCHIVE"
```

The output contains the VERSION-derived source archive, an install-ready Skill-only archive with `SKILL.md` at its root, sample archives, manifest, and checksums. Do not edit any of these files after verification.

输出包含由 VERSION 派生的源码归档、根目录含 `SKILL.md` 的可安装 Skill-only 归档、样例归档、清单和校验和。验收后不得编辑这些文件。

## Required review / 必须复核

Before asking for release approval, run the full test suite plus the link/anchor, media-ledger, and public-brand contracts. Confirm that citation metadata and release notes use the VERSION-derived tag, that no confidential material is present, and that every asset in `SHA256SUMS.txt` matches the manifest.

请求发布批准前，请运行完整测试，以及链接/锚点、媒体台账和公开品牌契约。确认引用元数据和发布说明使用 VERSION 派生标签、没有保密材料，并且 `SHA256SUMS.txt` 中每项资产都与清单一致。

## Human publication gate / 人工发布门禁

After the maintainer explicitly approves the exact candidate directory, the maintainer may create the matching `v<version>` tag and upload the already-verified assets. Re-run the local verification if the candidate or repository content changes. This runbook intentionally does not contain push, tag, or release commands.

维护者明确批准该候选目录后，维护者可以创建匹配的 `v<version>` 标签并上传已经验收的资产。候选目录或仓库内容若有变化，必须重新执行本地验收。本手册故意不包含推送、打标签或发布命令。

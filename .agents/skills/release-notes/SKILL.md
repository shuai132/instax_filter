---
name: release-notes
description: 为 Instax Filter 的语义化版本生成 GitHub Release 发布日志。用户要求“生成发布日志”、“生成 release notes”、“生成 changelog”或为某个版本整理发布说明时使用；只生成日志，不创建 tag、GitHub Release 或执行推送。
---

# 生成发布日志

## 确定版本范围

1. 确认当前目录属于 Instax Filter 仓库。
2. 接受 `X.Y.Z` 或 `vX.Y.Z`，统一输出为 `vX.Y.Z`。未提供版本时，选取本地最新语义化 tag。
3. 确认目标 tag 存在，并从本地语义化 tag 中选择它的前一个版本作为起始 tag。
4. 若没有更早的语义化 tag，将目标版本视为首次发布：总结目标 tag 可达的全部提交，并省略 `Full Changelog`。

版本格式不合法或目标 tag 不存在时，停止并说明原因。

## 收集上下文

执行：

```bash
git tag --sort=-version:refname
git log --no-merges --oneline <from-tag>..<to-tag>
git remote get-url origin
```

首次发布时，将日志命令改为：

```bash
git log --no-merges --oneline <to-tag>
```

提交标题信息不足时，按需执行 `git show --stat --oneline <commit>`。从 `origin` 的 SSH 或 HTTPS URL 推导 GitHub 仓库地址；不要硬编码仓库名。

## 编写正文

按以下顺序组织，空分类整段省略：

```markdown
🐞 Bug Fixes
- 修复项

✨ Features
- 新功能

🛠 Improvements
- 改进项

Release Page: https://github.com/OWNER/REPO/releases/tag/vX.Y.Z
Full Changelog: https://github.com/OWNER/REPO/compare/vA.B.C...vX.Y.Z
```

遵守以下规则：

- 将 `fix:` 通常归入 `🐞 Bug Fixes`，将 `feat:` 通常归入 `✨ Features`。
- 将 `refactor:`、`style:`、`perf:`、`docs:`、`ci:`、`build:`、`test:`、`chore:` 通常归入 `🛠 Improvements`；仅保留对用户体验、稳定性、可维护性或发布质量有明确价值的内容。
- 以用户可见影响为准调整分类，合并同类提交，不要逐条机械改写提交标题。
- 忽略 `chore: release vX.Y.Z`、`chore: 发布 vX.Y.Z` 等发布提交。
- 使用简洁中文，不写提交 hash、文件名、函数名或过细实现细节。
- 所有标题、bullet 和链接左对齐，不添加前导空格。
- 分类之间保留一个空行。
- `Release Page` 行末保留两个真实 ASCII 空格，以强制 Markdown 换行。
- 首次发布省略 `Full Changelog`；远端不是 GitHub URL 时仍生成分类正文，但省略无法推导的链接并说明原因。

## 保存与复核

将可直接粘贴到 GitHub Release 的原始 Markdown 保存到：

```text
/tmp/instax-filter-release-notes-vX.Y.Z.md
```

macOS 下若 `pbcopy` 可用，将文件内容复制到剪贴板。复制失败不影响文件生成。

复核：

- `Release Page` 指向目标 tag。
- 非首次发布的 `Full Changelog` 使用正确的 `<from-tag>...<to-tag>`。
- 发布提交没有进入任何条目。
- 空分类没有标题或占位文本。
- 正文无意外缩进，`Release Page` 行末有两个空格。

最终只报告文件路径、剪贴板状态和必要说明。可以给出简短预览，但不要把渲染后的最终回答当作唯一复制来源。

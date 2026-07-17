---
name: release
description: 发布 Instax Filter 的语义化版本。仅当用户明确要求发布某个版本（例如“发布 1.2.3”或“发布 v1.2.3”）时使用；同步 Python 包和 macOS App 版本、提交版本变更、创建并推送 tag，然后生成发布日志。
---

# 发布版本

任一步失败都立即停止并报告当前状态；不要自动回滚已经完成的提交、tag 或推送。

## 版本文件

目标版本统一为不带 `v` 的 `X.Y.Z`。以下声明必须一致：

- `python/pyproject.toml` 的 `[project].version`
- `app/project.yml` 中 InstaxApp target 的 `MARKETING_VERSION`

`python/uv.lock` 和 `app/InstaxApp.xcodeproj/project.pbxproj` 是工具生成文件，不要手工修改版本字段。

## 1. 前置检查

并发执行：

```bash
git status --porcelain
git rev-parse HEAD
git remote get-url origin
git rev-parse vX.Y.Z 2>/dev/null
git ls-remote --exit-code --tags origin refs/tags/vX.Y.Z
```

- 版本号不是 `X.Y.Z` 或 `vX.Y.Z`：停止并说明支持的格式。
- 工作区不干净：停止并让用户决定如何处理，避免把已有改动夹进发布提交。
- 本地或远端 tag 已存在：停止并让用户选择新版本号或明确处理已有 tag。
- 没有 `origin`：停止并报错。
- `git ls-remote` 返回“未找到”可继续；连接或认证错误必须停止，不能误判为 tag 不存在。

## 2. 同步版本

读取两个版本声明并与目标版本比较。

- 两处都等于目标版本：跳到验证。
- 任一处不一致或 `MARKETING_VERSION` 尚不存在：只直接编辑 `python/pyproject.toml` 和 `app/project.yml`，然后执行：

```bash
(cd python && uv lock)
xcodegen generate --spec app/project.yml
```

检查生成结果：

- `python/uv.lock` 中当前项目 `instax-filter` 的版本等于目标版本。
- `app/InstaxApp.xcodeproj/project.pbxproj` 中 InstaxApp 的 `MARKETING_VERSION` 等于目标版本。
- `python/uv.lock` 不包含意外依赖升级。
- XcodeGen 没有产生与版本同步无关的大范围工程变更；若有，停止并核对原因。

不要手工编辑 `python/uv.lock` 或 `.pbxproj` 来绕过生成命令。

## 3. 验证并提交

执行与版本变更相称的验证：

```bash
(cd python && uv run pytest)
```

若本机已有 `cpp/.deps/opencv-app-install`，再执行：

```bash
app/build.sh --release
```

如果步骤 2 产生变更，只暂存以下版本相关文件中实际发生变化的文件：

```text
python/pyproject.toml
python/uv.lock
app/project.yml
app/InstaxApp.xcodeproj/project.pbxproj
```

确认暂存区不含其他文件后，创建独立提交：

```bash
git commit -m "chore: release vX.Y.Z"
```

如果版本已经一致，不创建空提交。

## 4. 创建并推送 tag

创建 lightweight tag：

```bash
git tag vX.Y.Z
```

若本次生成了版本提交，分开推送当前分支和 tag：

```bash
git push origin HEAD
git push origin vX.Y.Z
```

若没有生成版本提交，只推送本次 tag：

```bash
git push origin vX.Y.Z
```

不要使用 `git push --tags`。推送失败时保留本地提交和 tag，准确报告失败位置并等待用户决定。

tag 推送会触发 `.github/workflows/build.yml` 构建 `Instax-macOS-arm64.zip` 并创建 GitHub Release。

## 5. 生成发布日志

tag 推送成功后，立即按相邻的 `release-notes` skill 为 `vX.Y.Z` 生成可复制的发布日志。发布日志失败不影响已经完成的提交、tag 或推送；分别报告结果。

## 6. 回报

报告：

- 是否修改并提交了版本文件。
- tag 名及其指向的短 hash、提交标题。
- 分支和 tag 的推送结果。
- GitHub Actions 将创建的发布产物。
- 发布日志文件路径及剪贴板状态。

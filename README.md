# Instax Filter

Instax Filter 是一个以 macOS App 为主要产品形态的照片滤镜项目。App 使用 SwiftUI/AppKit 构建界面，通过 Objective-C++ bridge 调用 C++/OpenCV 图像处理核心。

## 开始使用

构建和运行 App：

```bash
app/scripts/build-opencv.sh
xcodegen generate --spec app/project.yml
app/build.sh
```

也可以生成工程后，在 Xcode 中打开 `app/InstaxApp.xcodeproj`。完整说明见 [App README](app/README.md)。

## 目录结构

```text
app/       macOS App、bridge、资源与 App 构建脚本（主入口）
cpp/       App 共用的 C++/OpenCV 滤镜核心及命令行工具
python/    独立的 Python 参考实现及命令行工具
docs/      跨实现的设计与性能资料
```

三个实现目录在仓库顶层并列；其中 `app/` 负责最终产品，`cpp/` 为 App 提供核心能力，`python/` 保留为独立参考实现。

## 其他实现

- [C++ 核心与 CLI](cpp/README.md)
- [Python 参考实现与 CLI](python/README.md)
- [技术设计](app/TECHNICAL_DESIGN.md)

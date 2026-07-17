# Instax macOS App

原生 SwiftUI/AppKit 界面，通过 Objective-C++ 调用仓库中的 C++/OpenCV 滤镜核心。

## 生成并构建工程

App 使用 `cpp/.deps/opencv-app-install` 下以 macOS 14 为部署目标的静态 OpenCV。首次构建先运行：

```bash
cd app
scripts/build-opencv.sh
xcodegen generate
xcodebuild -project InstaxApp.xcodeproj -scheme InstaxApp -configuration Debug build
```

`scripts/build-opencv.sh` 固定使用 OpenCV 4.13.0，默认以 macOS 14.0 为最低系统、为当前机器架构构建静态库。

当前 Xcode target 明确构建 `arm64`，支持 Apple Silicon Mac。Intel 支持需要先生成对应的 OpenCV 静态库，再合并为双架构产物或 XCFramework。

也可以生成工程后直接使用 Xcode 打开 `InstaxApp.xcodeproj`。

## 当前功能

- 打开或拖放 JPEG、PNG、HEIC/HEIF、TIFF 等系统支持的图片。
- 使用现有八种 C++ 滤镜模式。
- 调整成像强度、颗粒、闪光、暗角、相框和随机纹理。
- 异步生成预览，并切换查看原图。
- 以 JPEG、PNG、HEIC 或 TIFF 导出全分辨率结果。

开发工程当前针对本机 OpenCV 架构。发布前需按 `TECHNICAL_DESIGN.md` 将 OpenCV 构建成固定版本的双架构静态产物或 XCFramework。

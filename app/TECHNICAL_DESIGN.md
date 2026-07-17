# Instax macOS App 技术方案（讨论稿）

## 1. 目标与边界

在现有仓库中新增一个纯原生 macOS App：

- 界面使用 SwiftUI，必要时通过 AppKit 补足文件面板、拖放和窗口能力。
- 滤镜算法继续复用 `cpp/` 中的 C++20 + OpenCV 实现，不在 Swift 中重写。
- 第一版完成单张图片导入、模式预览、参数调整、前后对比和导出。
- App 自包含运行，最终用户不需要安装 Homebrew、Python、CMake 或 OpenCV。
- 不修改原图；所有导出都由用户明确选择目标位置。

本方案中的“纯原生”是指使用 SwiftUI/AppKit 构建 `.app`，不引入 Electron、WebView UI 或 Python 运行时。C++ 和 OpenCV 作为本地机器码随 App 一起发布。

## 2. 当前代码评估

现有 C++ 代码已经有适合复用的领域层：

- `ModeRegistry`：八种内置模式与默认参数。
- `FilterEngine`：输入 `cv::Mat3f`，返回滤镜结果和可选人脸区域。
- `FrameRenderer`：裁切和 Instax 相纸边框。

目前不适合直接给 GUI 复用的部分主要集中在 `Application`：它同时处理 CLI 参数、OpenCV 文件编解码、输出命名和调试绘制。macOS App 不应调用 CLI 子进程，也不应把 `cv::Mat` 暴露给 Swift。

建议先做一次小范围重构：保留现有算法，抽出一个与文件系统无关的 C++ facade；CLI 和 macOS App 分别成为它的调用方。这样可以确保算法只有一份实现。

## 3. 推荐架构

```text
SwiftUI Views
    │ 用户意图 / 展示状态
    ▼
AppModel（@MainActor）
    │ async 请求、取消、结果缓存
    ▼
ImageProcessingService（Swift actor）
    │ RGBA 像素 + 参数
    ▼
InstaxBridge（Objective-C++，.mm）
    │ Swift/ObjC 类型 ↔ C++/OpenCV 类型
    ▼
InstaxCore（C++20）
    ├── FilterEngine
    ├── FrameRenderer
    └── ModeRegistry
```

### 3.1 UI 层

优先使用 SwiftUI：

- `ContentView`：空状态、编辑器和错误状态的入口。
- `EditorView`：原图/效果图画布、前后对比、缩放。
- `PresetSidebar`：八种模式及缩略图。
- `AdjustmentPanel`：强度、颗粒、闪光、暗角、相框和随机种子。
- 菜单命令：打开、导出、还原参数、切换前后对比。

AppKit 仅用于 SwiftUI 不够顺手的系统能力，例如 `NSOpenPanel`、`NSSavePanel`、拖放细节、Quick Look 或窗口定制。

### 3.2 Swift 状态与并发层

`AppModel` 只在主线程更新 UI 状态，耗时处理交给独立的 `ImageProcessingService` actor。每次参数变化生成递增的请求 ID，并取消旧任务；只有最新请求可以写回预览，避免滑动参数时旧结果覆盖新结果。

建议采用两级处理：

1. 交互预览：限制长边，例如 1600 px，并做 100–150 ms 防抖。
2. 最终导出：从原始图重新处理全分辨率数据，不复用低分辨率预览。

C++ 当前内部还会依据模式限制处理尺寸，再放大回原尺寸。实现阶段需要决定预览缩放与内部缩放如何配合，避免重复缩放；初版可以保持现有算法行为，以结果一致性优先。

### 3.3 Objective-C++ 桥接层

推荐使用 Objective-C++ 作为唯一桥接边界，不让 Swift 直接导入 C++ 头文件或 OpenCV 头文件。公开接口只出现 Foundation/CoreGraphics 可理解的类型。

概念接口如下（最终签名可在实现时微调）：

```objc
@interface IFProcessingRequest : NSObject
@property NSString *mode;
@property float strength;
@property float grain;
@property float flash;
@property BOOL vignette;
@property BOOL frame;
@property uint64_t seed;
@end

@interface IFProcessor : NSObject
- (nullable CGImageRef)processImage:(CGImageRef)image
                              request:(IFProcessingRequest *)request
                                error:(NSError **)error CF_RETURNS_RETAINED;
@end
```

桥接实现负责：

- 将 `CGImage` 统一解码成 8-bit RGBA 缓冲区。
- 转换为 C++ 核心需要的 RGB `cv::Mat3f`。
- 调用 `FilterEngine` 和可选的 `FrameRenderer`。
- 把结果转换回 `CGImage`。
- 捕获所有 C++ 异常并转换为 `NSError`，禁止异常跨语言边界传播。
- 明确定义像素所有权和生命周期，避免 `cv::Mat` 引用已经释放的 Swift/CG 缓冲区。

如果后续需要 iOS 或命令行以外的调用方，可以再将 Objective-C++ 接口下沉为稳定的 C ABI；首版没有必要同时维护两层桥接。

### 3.4 图片导入与导出

macOS 侧使用 ImageIO/CoreGraphics 负责文件编解码，OpenCV 只负责像素算法：

- 输入：通过 `CGImageSource` 解码 JPEG、PNG、HEIC/HEIF、TIFF 等系统支持格式。
- 方向：读取 EXIF orientation，在进入 C++ 前统一为视觉方向正确的像素。
- 色彩：第一版统一转换到 sRGB 进行算法处理，并给输出写入 sRGB profile。
- 输出：通过 `CGImageDestination` 写出 JPEG、PNG、HEIC 或 TIFF，并控制质量参数。
- 元数据：默认保留拍摄时间等安全元数据的策略需要讨论；GPS 建议默认移除。

这样可以绕过 Homebrew OpenCV 对 HEIC codec 支持不稳定的问题，也更符合 macOS 沙盒和系统色彩管理方式。

## 4. C++ 层调整建议

建议保持滤镜数学逻辑不变，只做以下结构调整：

1. 新增 `InstaxProcessor`（暂定名），组合 `ModeRegistry`、`FilterEngine` 和 `FrameRenderer`，接受内存像素与完整参数。
2. 将当前 `application.cpp` 中可复用的调试绘制移到核心或单独的 debug renderer；GUI 首版可以不暴露 debug overlay。
3. 人脸 cascade 路径由编译期 Homebrew 路径改为调用方传入或资源定位器提供。
4. 保留 CLI 的图片 I/O 行为，让现有 `instax-filter-cpp` 继续可用。
5. 为核心新增不依赖文件系统的单元测试，验证固定 seed 下的尺寸、像素摘要和参数边界。

核心 API 应区分“参数未指定”和具体数值。默认值由 `ModeRegistry` 解析一次，Swift UI 显示解析后的有效值，避免 Swift 和 C++ 各维护一份默认配置。

## 5. OpenCV 集成与发布

### 推荐：构建最小静态库并随 App 链接

不要让正式 App 链接 `/opt/homebrew` 下的动态库。开发和发布应使用固定版本、固定编译参数的 OpenCV：

- 仅保留当前所需模块：`core`、`imgproc`、`objdetect`。
- App 已使用 ImageIO 编解码，因此正式 App 核心不需要 `imgcodecs`。
- 支持 `arm64` 和 `x86_64`，产出静态库或 XCFramework。
- Haar cascade XML 作为 App bundle resource 复制，并由 `Bundle` 定位后传入 C++。
- 检查 OpenCV 及其传递依赖的许可证文件并随发行包提供。

开发阶段可以暂时使用 Homebrew OpenCV 快速跑通，但它不应成为可分发产物的运行时依赖。

### Xcode 与 CMake 的职责

- CMake 继续构建 CLI、核心测试和 OpenCV/C++ 独立验证。
- Xcode 构建 SwiftUI App、Objective-C++ bridge 和最终签名产物。
- C++ 源文件尽量由一个明确的 core target 管理，避免 Xcode 与 CMake 长期维护两份源文件清单。实现时可用 CMake 生成库后供 Xcode 链接，或生成一个 XCFramework；初版优先选择脚本可重复、CI 易复现的方案。

## 6. 沙盒、权限与分发

建议从第一天启用 App Sandbox：

- 用户通过打开面板或拖放授予输入文件访问权。
- 用户通过保存面板选择输出路径。
- 长期记住文件位置时再使用 security-scoped bookmark；第一版通常不需要。
- 不请求照片图库、网络、摄像头等当前功能不需要的权限。

若目标包含站外分发，需要 Developer ID 签名、公证和 hardened runtime；若目标是 Mac App Store，还要进一步校验沙盒、隐私清单和依赖许可。两种渠道可以共用绝大多数代码，但发布脚本不同。

## 7. 目录结构

```text
app/                      # 主产品与构建入口
├── InstaxApp/            # SwiftUI/AppKit 界面与资源
├── InstaxBridge/         # Objective-C++ bridge
├── InstaxAppTests/
└── scripts/
cpp/                      # App 共用的 C++/OpenCV 核心
├── include/instax/
└── src/
python/                   # 独立 Python 参考实现
├── instax/
└── tests/
```

`app/`、`cpp/`、`python/` 在仓库顶层并列。App 是最终产品和主要入口；共用算法留在 `cpp/`，避免产生一份 App 专属的 C++ 副本；Python 实现独立放在 `python/`，不参与 App 构建。

## 8. 第一版产品流程

1. 启动后显示拖放区和“打开图片”。
2. 导入后生成各模式的小缩略图，默认选择 `instax`。
3. 用户调整模式和参数，画布异步刷新预览。
4. 按住对比按钮或使用分割滑块查看原图。
5. 点击导出，选择格式、质量和路径。
6. 后台以原图分辨率处理；完成后提供“在 Finder 中显示”。

批量处理、历史记录、预设收藏、Photos 扩展和实时相机建议放到后续版本，不进入第一版核心范围。

## 9. 测试与验收

### C++ 核心

- 每种模式固定 seed 的回归测试。
- 横图、竖图、超小图、超大图、灰度图和带 alpha 图片。
- strength/grain/flash 的边界值与非法参数。
- 无 cascade 资源时能够降级处理，而不是崩溃。

### Bridge

- RGBA/RGB 转换的通道顺序、stride 和内存生命周期。
- EXIF 方向与 alpha 行为。
- C++ 异常正确映射为 `NSError`。
- 连续处理时无明显内存增长。

### App

- 快速拖动参数时只展示最后一次结果。
- 导出过程中 UI 不冻结，可取消。
- 导出文件不覆盖原图。
- 沙盒下打开、拖放、保存均可用。
- Intel 与 Apple Silicon 的构建和启动验证。

视觉回归不建议要求逐像素完全相同，因为 OpenCV 版本、CPU 路径和缩放实现可能产生微小差异；可使用固定环境下的基准图，加感知差异或误差阈值。

## 10. 实施阶段

### 阶段 A：核心可嵌入化

- 抽出内存输入/输出的 C++ facade。
- 将 cascade 资源路径参数化。
- 补 C++ 回归测试，确认 CLI 输出没有非预期变化。

### 阶段 B：最小原生 App

- 创建 SwiftUI macOS 工程。
- 完成 Objective-C++ bridge、单图打开、处理和保存。
- 跑通 arm64 Debug/Release。

### 阶段 C：编辑体验

- 模式缩略图、参数面板、预览防抖与取消。
- 前后对比、错误提示和进度状态。
- 大图内存与性能优化。

### 阶段 D：可分发构建

- 固定 OpenCV 构建并产出双架构依赖。
- 开启沙盒、签名、公证。
- 完整格式、性能和设备验收。

## 11. 主要风险与处理

| 风险 | 影响 | 处理建议 |
| --- | --- | --- |
| OpenCV 动态依赖指向 Homebrew | 用户机器无法启动 | 发布版使用固定构建的静态库/XCFramework，并检查最终二进制依赖 |
| HEIC 依赖 OpenCV codec | 部分环境无法读写 | 文件编解码统一交给 ImageIO |
| 色彩空间处理不一致 | 与 Python/CLI 观感偏差 | 明确 sRGB 工作空间，建立基准图对比 |
| 大图产生多份浮点缓冲 | 内存峰值过高 | 预览降采样；导出限制并发；后续复用 buffer/分块评估 |
| 参数快速变化导致结果乱序 | UI 闪回旧预览 | actor 串行状态、请求 ID 和取消旧任务 |
| Haar XML 依赖外部路径 | 闪光人脸检测失效 | XML 打包进 App bundle，启动时显式传入 |
| 双架构 OpenCV 构建复杂 | Intel 或 Apple Silicon 缺失 | CI 分架构构建后合并 XCFramework，并分别验证 |

## 12. 需要确认的产品决策

以下决策不会阻塞核心架构，但会影响第一版范围：

1. 最低 macOS 版本。建议优先覆盖近几代系统，以减少 SwiftUI 兼容分支。
2. 发布渠道：仅本机使用、Developer ID 站外分发，还是 Mac App Store。
3. 第一版是否需要 Intel 支持；如果只面向 Apple Silicon，依赖构建会简单很多。
4. 前后对比采用按住查看、分割滑块，还是两者都要。
5. 导出是否保留 EXIF；建议保留非敏感拍摄信息，默认移除 GPS。
6. 是否首版加入批量处理。建议先把单图编辑体验和结果一致性做稳。

## 13. 当前推荐结论

采用“SwiftUI/AppKit + Objective-C++ bridge + C++/OpenCV core”的三层方案。系统 ImageIO 负责文件和色彩入口，C++ 只处理规范化后的像素；App 发布版静态携带固定版本 OpenCV 和 cascade 资源。先把现有 C++ 抽成可嵌入核心，再做最小 App，最后完善交互与发布链路。

这个方案对现有算法改动最小，能够同时保留 CLI，并为以后增加批处理、Photos 扩展或其他 Apple 平台留下清晰边界。

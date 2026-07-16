# Instax Filter C++

Python 版本的原生 C++/OpenCV 实现。支持相同的八种模式、颗粒、暗角、直闪、相纸边框和固定随机种子。

## 构建

需要 CMake 3.20+ 和 OpenCV 4.x：

```bash
brew install cmake opencv
cmake -S cpp -B cpp/build -DCMAKE_BUILD_TYPE=Release
cmake --build cpp/build -j
```

## 使用

```bash
cpp/build/instax-filter-cpp photo.jpg --mode instax --seed 42
cpp/build/instax-filter-cpp photo.jpg --mode ccd noir night
cpp/build/instax-filter-cpp photo.jpg --mode-all --no-frame
```

主要参数与 Python CLI 一致。运行 `instax-filter-cpp --help` 查看完整帮助。

OpenCV 的实际编解码格式取决于构建配置。Homebrew OpenCV 通常可处理 JPEG、PNG、WebP 和 TIFF；HEIC/HEIF 需要 OpenCV 构建时启用对应 codec。

## 代码结构

公开接口位于 `include/instax/`，实现位于 `src/`：

- `ModeRegistry`：集中管理内置模式及参数查找。
- `FilterEngine`：通过 `FilterSettings` 输入和 `FilterResult` 输出封装纯图像处理流程。
- `FrameRenderer`：负责 Instax Mini 裁切和相纸渲染。
- `cli_options`：负责命令行参数解析与校验。
- `Application`：组合注册表、处理引擎、相框和图片 I/O；`main.cpp` 仅负责启动。

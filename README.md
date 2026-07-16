# Instax Filter

用 Python 给照片添加辨识度明显、但不依赖漏光和划痕等复古特效的真实富士拍立得风格：明显降低数码清晰度、可见的乳剂颗粒、较窄的动态范围、奶油高光、青冷阴影、暖肤色、辉光、卤化效果和相纸密度变化。默认裁切成 Instax Mini 的 46×62 mm 成像比例，并输出为 54×86 mm 相纸比例；不会覆盖原图。

## 使用

```bash
uv run instax-filter ./photo.jpg
```

输出到输入图片所在目录，文件名为 `photo_instax.jpg`。

默认输出为拍立得尺寸：竖图 `1080×1720`，横图 `1720×1080`。如果只要滤镜、不需要裁切和相纸白边：

```bash
uv run instax-filter ./photo.jpg --no-frame
```

调整效果：

```bash
uv run instax-filter ./photo.jpg --strength 0.85 --grain 0.7
```

查看全部选项：

```bash
uv run instax-filter --help
```

## 支持格式

- HEIC/HEIF：`.heic`、`.heif`
- JPEG：`.jpg`、`.jpeg`
- PNG：`.png`
- WebP：`.webp`
- TIFF：`.tif`、`.tiff`

输入和输出均支持以上格式，也可以通过 `-o` 转换格式。大图会先在受控尺寸上处理，再以高质量缩放恢复原尺寸，避免 NumPy 中间数组占用过多内存。

运行测试：

```bash
uv run python -m unittest discover -s tests
```

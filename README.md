# Instax Filter

用 Python 给照片添加辨识度明显、但不依赖漏光和划痕等复古特效的真实富士拍立得风格：明显降低数码清晰度、可见的乳剂颗粒、较窄的动态范围、奶油高光、青冷阴影、暖肤色、辉光、卤化效果和相纸密度变化。默认裁切成 Instax Mini 的 46×62 mm 成像比例，并输出为 54×86 mm 相纸比例；不会覆盖原图。

## 使用

命令格式：

```bash
uv run instax-filter INPUT [-o OUTPUT] [选项]
```

使用默认效果：

```bash
uv run instax-filter ./photo.jpg
```

输出到输入图片所在目录，文件名为 `photo_instax.jpg`。

指定输出路径，并转换图片格式：

```bash
uv run instax-filter ./photo.heic -o ./photo_instax.jpg
```

调整调色和颗粒强度：

```bash
uv run instax-filter ./photo.jpg --strength 0.85 --grain 0.7
```

默认输出为拍立得尺寸：竖图 `1080×1720`，横图 `1720×1080`。只添加滤镜，不裁切、不添加相纸白边：

```bash
uv run instax-filter ./photo.jpg --no-frame
```

关闭暗角并固定随机纹理，便于重复得到相同结果：

```bash
uv run instax-filter ./photo.jpg --no-vignette --seed 42
```

### 参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `INPUT` | 必填 | 本地输入图片路径 |
| `-o PATH`、`--output PATH` | 原目录下 `*_instax` | 指定输出路径；扩展名决定输出格式 |
| `--strength FLOAT` | `1.0` | 调色和胶片质感强度，范围 `0–1.5` |
| `--grain FLOAT` | `1.0` | 颗粒强度，范围 `0–2`；设为 `0` 可关闭颗粒 |
| `--frame` | 开启 | 裁切并输出 Instax Mini 尺寸相纸 |
| `--no-frame` | — | 保持原图尺寸，不裁切、不添加相纸白边 |
| `--no-vignette` | — | 关闭轻微暗角 |
| `--seed INTEGER` | 根据输入路径生成 | 固定颗粒和相纸纹理的随机种子 |
| `--quality INTEGER` | `95` | JPEG、WebP、HEIC 输出质量，范围 `1–100` |
| `-h`、`--help` | — | 显示命令帮助 |

查看命令帮助：

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

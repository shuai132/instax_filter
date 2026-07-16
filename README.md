# Instax Filter

用 Python 模拟多种相机和胶片成像。不会覆盖原图。

- `instax`：按 Instax Mini 的成像比例和约 10 lines/mm 相纸解析力输出，保留适度反差、轻微软化、细微乳剂纹理、暖高光和常亮补闪。
- `ccd`：模拟约 4–5 MP 小尺寸传感器、机内 JPEG 锐化、较硬直闪、有限动态范围，以及暗部更明显的亮度和彩色噪点；默认不添加相纸白边。
- `lofi`：完整保留项目最初的重柔焦、粗颗粒、强辉光、青冷阴影和奶油高光配方。
- `disposable`：一次性胶片机风格，强调暖色硬直闪、绿色暗部、明显边缘失光和粗颗粒。

校准参考包括 [Fujifilm Instax Mini 12 官方规格](https://www.fujifilm.com/us/en/consumer/instax/cameras/mini12/specifications)、[Fujifilm Instax 相纸数据表](https://asset.fujifilm.com/master/apac/files/2020-06/acf110878e2c263a1a0c13b762fb1cbe/instax_datasheet.pdf)、[Canon PowerShot A520 官方资料](https://global.canon/en/c-museum/product/dcc508.html)，以及 Imaging Resource 发布的 [A520 未修改原始样片](https://old.imaging-resource.com/PRODS/A520/A52PICS.HTM)。

## 使用

命令格式：

```bash
uv run instax-filter INPUT [-o OUTPUT] [选项]
```

使用默认效果：

```bash
uv run instax-filter ./photo.jpg
```

使用 2000 年代 CCD 卡片机效果：

```bash
uv run instax-filter ./photo.jpg --mode ccd
```

使用最初的重颗粒 Lo-fi 效果：

```bash
uv run instax-filter ./photo.jpg --mode lofi
```

使用一次性胶片机效果：

```bash
uv run instax-filter ./photo.jpg --mode disposable
```

输出到输入图片所在目录，默认文件名为 `photo_{mode}.jpg`。

指定输出路径，并转换图片格式：

```bash
uv run instax-filter ./photo.heic -o ./photo_instax.jpg
```

调整调色和颗粒强度：

```bash
uv run instax-filter ./photo.jpg --strength 0.85 --grain 0.7
```

`instax` 默认输出拍立得尺寸：竖图 `1080×1720`，横图 `1720×1080`。`ccd` 默认保持原图比例且不添加白边。只应用 Instax 成像、不添加相纸白边：

```bash
uv run instax-filter ./photo.jpg --no-frame
```

关闭暗角并固定随机纹理，便于重复得到相同结果：

```bash
uv run instax-filter ./photo.jpg --no-vignette --seed 42
```

`instax` 默认使用 `0.35` 的常亮补闪，`ccd` 默认使用 `0.15` 的轻微直闪。脚本会先检测正脸和侧脸，再以每张脸为核心向头部、颈部和上半身辐射闪光；没有检测到人脸时回退到画面中央偏上的通用直闪。两种模式具有不同的闪光色温、反差和背景衰减。单写 `--flash` 时使用标准强度 `1.0`：

```bash
uv run instax-filter ./photo.jpg --flash
```

指定闪光灯强度，范围为 `0–2`：

```bash
uv run instax-filter ./photo.jpg --flash 1.6
```

完全关闭闪光灯：

```bash
uv run instax-filter ./photo.jpg --flash 0
```

标出识别到的人脸，并在遮挡较少的左上角或右上角显示当前调色信息：

```bash
uv run instax-filter ./photo.jpg --debug
```

调试面板会显示人脸数量、调色强度、颗粒、闪光、暗角、柔化、阴影与高光色调和随机种子。调试标记会写入输出图片，仅建议在检查人脸识别和滤镜参数时使用。

### 参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `INPUT` | 必填 | 本地输入图片路径 |
| `-o PATH`、`--output PATH` | 原目录下 `*_{mode}` | 指定输出路径；扩展名决定输出格式 |
| `--mode {instax,ccd,lofi,disposable}` | `instax` | 选择成像预设 |
| `--strength FLOAT` | 按模式 | 成像特征强度，范围 `0–1.5` |
| `--grain FLOAT` | 按模式 | 乳剂颗粒或传感器噪声，范围 `0–2` |
| `--frame` | 按模式 | 裁切并输出 Instax Mini 尺寸相纸；`instax`、`lofi` 默认开启，其他模式默认关闭 |
| `--no-frame` | — | 保持原图尺寸，不裁切、不添加相纸白边 |
| `--no-vignette` | — | 关闭轻微暗角 |
| `--flash [INTENSITY]` | 按模式 | 检测人脸并从主体向外辐射直闪，范围 `0–2`；单写时使用 `1.0` |
| `--debug` | 关闭 | 标出检测到的人脸，并在画面左上角或右上角显示调色信息 |
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

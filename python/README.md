# Instax Filter Python

独立的 Python 参考实现，用于模拟多种相机和胶片成像。不会覆盖原图。

- `instax`：按 Instax Mini 的成像比例和约 10 lines/mm 相纸解析力输出，保留适度反差、轻微软化、细微乳剂纹理、暖高光和自动补闪。
- `ccd`：模拟约 4–5 MP 小尺寸传感器、机内 JPEG 锐化、有限动态范围，以及暗部更明显的亮度和彩色噪点，并支持可选的较硬直闪。
- `lofi`：完整保留项目最初的重柔焦、粗颗粒、强辉光、青冷阴影和奶油高光配方。
- `disposable`：一次性胶片机风格，强调暖色硬直闪、绿色暗部、明显边缘失光和粗颗粒。
- `chrome`：高饱和反转片风格，具有深黑、浓郁蓝绿、暖高光、细颗粒和清晰边缘。
- `dream`：低反差梦境风格，抬高黑位、降低饱和度，并加入粉紫柔光和明显高光辉光。
- `noir`：高反差黑白纪实风格，采用亮度矩阵转换、深黑、粗银盐感颗粒、锐利边缘和强暗角。
- `night`：霓虹夜拍风格，使用冷蓝硬闪、洋红高光、深背景、锐利主体和强烈暗部彩噪。

校准参考包括 [Fujifilm Instax Mini 12 官方规格](https://www.fujifilm.com/us/en/consumer/instax/cameras/mini12/specifications)、[Fujifilm Instax 相纸数据表](https://asset.fujifilm.com/master/apac/files/2020-06/acf110878e2c263a1a0c13b762fb1cbe/instax_datasheet.pdf)、[Canon PowerShot A520 官方资料](https://global.canon/en/c-museum/product/dcc508.html)，以及 Imaging Resource 发布的 [A520 未修改原始样片](https://old.imaging-resource.com/PRODS/A520/A52PICS.HTM)。

## 使用

从仓库根目录进入 Python 工程：

```bash
cd python
```

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

使用高饱和反转片效果：

```bash
uv run instax-filter ./photo.jpg --mode chrome
```

使用低反差梦境效果：

```bash
uv run instax-filter ./photo.jpg --mode dream
```

使用高反差黑白效果：

```bash
uv run instax-filter ./photo.jpg --mode noir
```

使用霓虹夜拍效果：

```bash
uv run instax-filter ./photo.jpg --mode night
```

一次生成多个模式（按输入顺序分别输出）：

```bash
uv run instax-filter ./photo.jpg --mode instax ccd noir night
```

多模式会分别使用各模式的默认参数，并生成 `photo_instax.jpg`、`photo_ccd.jpg` 等文件；显式指定的 `--strength`、`--grain`、`--flash`、`--frame` 等参数会应用到所有模式。由于 `-o/--output` 只能表示一个文件，多模式下不能同时使用该参数。

一次生成全部模式：

```bash
uv run instax-filter ./photo.jpg --mode-all
```

`--mode-all` 不能与 `--mode` 或 `-o/--output` 同时使用。

输出到输入图片所在目录，默认文件名为 `photo_{mode}.jpg`。

指定输出路径，并转换图片格式：

```bash
uv run instax-filter ./photo.heic -o ./photo_instax.jpg
```

调整调色和颗粒强度：

```bash
uv run instax-filter ./photo.jpg --strength 0.85 --grain 0.7
```

所有模式默认保持原图尺寸，不裁切、不添加相纸白边。添加 Instax Mini 相纸白边（竖图 `1080×1720`，横图 `1720×1080`）：

```bash
uv run instax-filter ./photo.jpg --frame
```

`--no-frame` 可显式关闭相框，例如用于覆盖脚本或别名中预设的 `--frame`。

关闭暗角并固定随机纹理，便于重复得到相同结果：

```bash
uv run instax-filter ./photo.jpg --no-vignette --seed 42
```

`instax` 按 Mini 12 的常亮自动闪光机制默认使用 `0.35` 的补闪；`disposable` 和 `night` 分别默认使用 `0.22` 的暖色硬直闪和 `0.30` 的冷蓝夜拍直闪；其他模式默认关闭闪光灯。脚本会先检测正脸和侧脸，再以每张脸为核心向头部、颈部和上半身辐射闪光；没有检测到人脸时回退到画面中央偏上的通用直闪。各模式具有不同的闪光色温、反差和背景衰减。单写 `--flash` 时使用标准强度 `1.0`：

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
| `--mode MODE [MODE ...]` | `instax` | 选择一个或多个成像预设；可选值及简要说明也可通过 `-h` 查看 |
| `--mode-all` | 关闭 | 一次生成全部成像预设；不能与 `--mode` 或 `-o/--output` 同时使用 |
| `--strength FLOAT` | 按模式 | 成像特征强度，范围 `0–1.5` |
| `--grain FLOAT` | 按模式 | 乳剂颗粒或传感器噪声，范围 `0–2` |
| `--frame` | 关闭 | 裁切并输出 Instax Mini 尺寸相纸白边 |
| `--no-frame` | — | 显式保持原图尺寸，不裁切、不添加相纸白边 |
| `--no-vignette` | — | 关闭轻微暗角 |
| `--flash [INTENSITY]` | `instax` 为 `0.35`，`disposable` 为 `0.22`，`night` 为 `0.30`；其他模式关闭 | 检测人脸并从主体向外辐射直闪，范围 `0–2`；单写时使用 `1.0` |
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

## 代码结构

Python 实现采用分层模块，`instax_filter.py` 仅作为旧导入路径的兼容门面：

- `instax/config.py`：不可变模式配置与内置模式注册表。
- `instax/engine.py`：滤镜处理、人脸闪光和调试叠层。
- `instax/frame.py`：Instax Mini 裁切与相纸渲染。
- `instax/storage.py`：输出命名、稳定随机种子和图片持久化。
- `instax/cli.py`：参数解析、校验及应用流程编排。

C++ 实现遵循相同的职责边界，详见 [`../cpp/README.md`](../cpp/README.md)。

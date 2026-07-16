#!/usr/bin/env python3
"""Emulate Fujifilm Instax Mini and early compact CCD camera rendering."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener


from instax.config import MODE_CONFIGS, MODE_DESCRIPTIONS, ModeConfig, get_mode_config

# Register HEIF/HEIC with Pillow before any Image.open or Image.save call.
register_heif_opener()

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".heic", ".heif"}
INSTAX_PAPER_PORTRAIT = (1080, 1720)
INSTAX_IMAGE_PORTRAIT = (920, 1240)





from instax.engine import (
    _build_flash_mask,
    _draw_debug_overlay,
    apply_instax_look,
)

def fit_instax_image(image: Image.Image) -> Image.Image:
    """Crop to the Instax Mini 46×62 mm image area at a stable pixel size."""
    portrait = image.height >= image.width
    size = INSTAX_IMAGE_PORTRAIT if portrait else INSTAX_IMAGE_PORTRAIT[::-1]
    return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def add_instax_frame(image: Image.Image, *, seed: int = 0) -> Image.Image:
    """Place the image in a true-ratio 54×86 mm Instax Mini paper frame."""
    portrait = image.height >= image.width
    image_size = INSTAX_IMAGE_PORTRAIT if portrait else INSTAX_IMAGE_PORTRAIT[::-1]
    paper_size = INSTAX_PAPER_PORTRAIT if portrait else INSTAX_PAPER_PORTRAIT[::-1]
    fitted = ImageOps.fit(image, image_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))

    # Instax stock is near-neutral white with only very subtle physical variation.
    rng = np.random.default_rng(seed ^ 0x49A37B1D)
    base_color = np.array([250.0, 249.0, 246.0], dtype=np.float32)
    paper_noise = rng.normal(0.0, 0.35, (paper_size[1], paper_size[0], 1)).astype(np.float32)
    paper = np.uint8(np.clip(base_color + paper_noise, 0, 255))
    framed = Image.fromarray(paper, "RGB")

    # 20 px/mm: 4 mm side margins, 6 mm top and 18 mm bottom. In landscape,
    # rotating the print puts the signature wide margin on the right.
    position = (80, 120) if portrait else (120, 80)
    mask = fitted.getchannel("A") if "A" in fitted.getbands() else None
    framed.paste(fitted, position, mask)
    return framed


def _default_output(input_path: Path, mode: str) -> Path:
    return input_path.with_name(f"{input_path.stem}_{mode}{input_path.suffix.lower()}")


def _seed_for(path: Path) -> int:
    digest = hashlib.blake2b(str(path.resolve()).encode(), digest_size=8).digest()
    return int.from_bytes(digest, "little")


def _save(image: Image.Image, output_path: Path, *, quality: int) -> None:
    suffix = output_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        if image.mode != "RGB":
            background = Image.new("RGB", image.size, (246, 243, 232))
            alpha = image.getchannel("A") if "A" in image.getbands() else None
            background.paste(image, mask=alpha)
            image = background
        image.save(output_path, quality=quality, subsampling=0, optimize=True)
    elif suffix == ".png":
        image.save(output_path, optimize=True)
    elif suffix == ".webp":
        image.save(output_path, quality=quality, method=6)
    elif suffix in {".heic", ".heif"}:
        image.save(output_path, format="HEIF", quality=quality)
    elif suffix in {".tif", ".tiff"}:
        image.save(output_path, compression="tiff_lzw")
    else:
        raise ValueError(f"不支持的输出格式：{suffix}")


def build_parser() -> argparse.ArgumentParser:
    mode_help = "选择一个或多个成像预设（默认 instax）：\n" + "\n".join(
        f"  {mode:<10} {description}" for mode, description in MODE_DESCRIPTIONS.items()
    )
    parser = argparse.ArgumentParser(
        description="模拟多种胶片、拍立得和数码相机成像",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="本地图片路径")
    parser.add_argument("-o", "--output", type=Path, help="输出路径（默认：原目录下 *_{mode}）")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--mode",
        choices=tuple(MODE_CONFIGS),
        nargs="+",
        default=["instax"],
        metavar="MODE",
        help=mode_help,
    )
    mode_group.add_argument(
        "--mode-all",
        action="store_true",
        help="一次生成全部成像预设（不能与 --mode 或 --output 同时使用）",
    )
    parser.add_argument("--strength", type=float, help="成像特征强度，0–1.5（默认值按模式）")
    parser.add_argument("--grain", type=float, help="颗粒或传感器噪声，0–2（默认值按模式）")
    frame_group = parser.add_mutually_exclusive_group()
    frame_group.add_argument("--frame", dest="frame", action="store_true", default=None, help="裁切并添加 Instax Mini 相纸白边")
    frame_group.add_argument("--no-frame", dest="frame", action="store_false", help="不裁切、不添加相纸白边")
    parser.add_argument("--no-vignette", action="store_true", help="关闭轻微暗角")
    parser.add_argument(
        "--flash",
        nargs="?",
        const=1.0,
        default=None,
        type=float,
        metavar="INTENSITY",
        help="模拟机顶直闪，可选强度 0–2（默认值按模式；省略数值时为 1.0）",
    )
    parser.add_argument("--debug", action="store_true", help="标出人脸区域并显示当前调色参数")
    parser.add_argument("--seed", type=int, help="颗粒与相纸纹理随机种子（默认由文件路径稳定生成）")
    parser.add_argument("--quality", type=int, default=95, help="JPEG/WebP/HEIC 质量，1–100（默认 95）")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    modes = list(MODE_CONFIGS) if args.mode_all else args.mode
    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        raise SystemExit(f"找不到输入文件：{input_path}")
    if input_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise SystemExit(f"不支持的输入格式：{input_path.suffix}")
    if args.strength is not None and not 0.0 <= args.strength <= 1.5:
        raise SystemExit("--strength 必须在 0–1.5 之间")
    if args.grain is not None and not 0.0 <= args.grain <= 2.0:
        raise SystemExit("--grain 必须在 0–2 之间")
    if args.flash is not None and not 0.0 <= args.flash <= 2.0:
        raise SystemExit("--flash 强度必须在 0–2 之间")
    if not 1 <= args.quality <= 100:
        raise SystemExit("--quality 必须在 1–100 之间")
    if args.output and len(modes) > 1:
        raise SystemExit("生成多个模式时不能指定 --output；输出文件将按模式自动命名")

    output_paths = [
        (args.output.expanduser() if args.output else _default_output(input_path, mode)).resolve()
        for mode in modes
    ]
    for output_path in output_paths:
        if output_path == input_path:
            raise SystemExit("输出路径不能与输入文件相同，以免覆盖原图")
        if output_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise SystemExit(f"不支持的输出格式：{output_path.suffix}")
        if not output_path.parent.is_dir():
            raise SystemExit(f"输出目录不存在：{output_path.parent}")

    try:
        with Image.open(input_path) as opened:
            source = ImageOps.exif_transpose(opened)
            source.load()
        for mode, output_path in zip(modes, output_paths):
            mode_config = get_mode_config(mode)
            strength = args.strength if args.strength is not None else mode_config.default_strength
            grain = args.grain if args.grain is not None else mode_config.default_grain
            flash = args.flash if args.flash is not None else mode_config.default_flash
            frame = args.frame if args.frame is not None else mode_config.default_frame
            image = source.copy()
            if frame:
                image = fit_instax_image(image)
            result = apply_instax_look(
                image,
                mode=mode,
                strength=strength,
                grain=grain,
                vignette=not args.no_vignette,
                flash=flash,
                debug=args.debug,
                seed=args.seed if args.seed is not None else _seed_for(input_path),
            )
            if frame:
                result = add_instax_frame(result, seed=args.seed if args.seed is not None else _seed_for(input_path))
            _save(result, output_path, quality=args.quality)
            print(f"已输出：{output_path}")
    except (OSError, ValueError) as exc:
        raise SystemExit(f"处理失败：{exc}") from exc


if __name__ == "__main__":
    main()

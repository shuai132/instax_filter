"""Command-line adapter and application workflow."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageOps

from .config import MODE_CONFIGS, MODE_DESCRIPTIONS, get_mode_config
from .engine import apply_instax_look
from .frame import add_instax_frame, fit_instax_image
from .storage import SUPPORTED_SUFFIXES, _default_output, _save, _seed_for

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

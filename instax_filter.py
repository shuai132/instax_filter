#!/usr/bin/env python3
"""Apply a restrained Fujifilm Instax-inspired look to a local photo."""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from pillow_heif import register_heif_opener


# Register HEIF/HEIC with Pillow before any Image.open or Image.save call.
register_heif_opener()

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".heic", ".heif"}
INSTAX_PAPER_PORTRAIT = (1080, 1720)
INSTAX_IMAGE_PORTRAIT = (920, 1240)


@dataclass(frozen=True, slots=True)
class ModeConfig:
    name: str
    default_strength: float
    default_grain: float
    soften_amount: float
    local_detail_amount: float
    glow_amount: float
    halo_amount: float


MODE_CONFIGS = {
    "instax": ModeConfig(
        name="instax",
        default_strength=1.0,
        default_grain=0.8,
        soften_amount=0.18,
        local_detail_amount=0.05,
        glow_amount=0.10,
        halo_amount=0.55,
    ),
    "ccd": ModeConfig(
        name="ccd",
        default_strength=1.5,
        default_grain=2.0,
        soften_amount=0.52,
        local_detail_amount=0.16,
        glow_amount=0.17,
        halo_amount=1.0,
    ),
}


def _mode_config(mode: str) -> ModeConfig:
    try:
        return MODE_CONFIGS[mode]
    except KeyError as exc:
        raise ValueError(f"不支持的模式：{mode}") from exc


def _smoothstep(edge0: float, edge1: float, value: np.ndarray) -> np.ndarray:
    value = np.clip((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def _luminance(rgb: np.ndarray) -> np.ndarray:
    return np.sum(rgb * np.array([0.2126, 0.7152, 0.0722]), axis=2, keepdims=True)


def _to_array(image: Image.Image) -> np.ndarray:
    return np.asarray(image, dtype=np.float32) / 255.0


def _to_image(rgb: np.ndarray) -> Image.Image:
    return Image.fromarray(np.uint8(np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5), "RGB")


def _blur(rgb: np.ndarray, radius: float) -> np.ndarray:
    return _to_array(_to_image(rgb).filter(ImageFilter.GaussianBlur(radius=radius)))


def _intersection_over_union(first: tuple[int, int, int, int], second: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    overlap_w = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    overlap_h = max(0, min(ay + ah, by + bh) - max(ay, by))
    overlap = overlap_w * overlap_h
    union = aw * ah + bw * bh - overlap
    return overlap / union if union else 0.0


def _detect_faces(rgb: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Detect frontal and profile faces using OpenCV's bundled classifiers."""
    pixels = np.uint8(np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5)
    gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
    gray = cv2.equalizeHist(gray)
    height, width = gray.shape
    minimum = max(28, round(min(height, width) * 0.055))
    cascade_dir = Path(cv2.data.haarcascades)
    candidates: list[tuple[int, int, int, int]] = []

    cascade_names = ("haarcascade_frontalface_alt2.xml", "haarcascade_profileface.xml")
    for name in cascade_names:
        classifier = cv2.CascadeClassifier(str(cascade_dir / name))
        if classifier.empty():
            continue
        detections = classifier.detectMultiScale(
            gray,
            scaleFactor=1.08,
            minNeighbors=6,
            minSize=(minimum, minimum),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )
        candidates.extend(tuple(map(int, face)) for face in detections)

        # The profile classifier detects only one facing direction, so mirror the
        # image and map those results back for the opposite profile.
        if "profile" in name:
            mirrored = cv2.flip(gray, 1)
            mirrored_faces = classifier.detectMultiScale(
                mirrored,
                scaleFactor=1.08,
                minNeighbors=6,
                minSize=(minimum, minimum),
                flags=cv2.CASCADE_SCALE_IMAGE,
            )
            candidates.extend((width - int(x) - int(w), int(y), int(w), int(h)) for x, y, w, h in mirrored_faces)

    # Merge duplicates produced by frontal/profile passes, preferring larger and
    # therefore usually more stable detections.
    faces: list[tuple[int, int, int, int]] = []
    for candidate in sorted(candidates, key=lambda box: box[2] * box[3], reverse=True):
        if all(_intersection_over_union(candidate, kept) < 0.28 for kept in faces):
            faces.append(candidate)
    return faces


def _build_flash_mask(
    height: int,
    width: int,
    faces: list[tuple[int, int, int, int]],
) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width]
    if not faces:
        x = (xx / max(width - 1, 1) - 0.5) / 0.58
        y = (yy / max(height - 1, 1) - 0.43) / 0.68
        return np.exp(-2.15 * (x * x + y * y)).astype(np.float32)[..., None]

    combined = np.zeros((height, width), dtype=np.float32)
    for face_x, face_y, face_w, face_h in faces:
        center_x = face_x + face_w * 0.5
        # Shift the larger halo below the face to include neck and upper torso.
        center_y = face_y + face_h * 1.05
        radius_x = max(face_w * 1.65, width * 0.10)
        radius_y = max(face_h * 2.25, height * 0.13)
        halo = np.exp(
            -1.35 * (((xx - center_x) / radius_x) ** 2 + ((yy - center_y) / radius_y) ** 2)
        ).astype(np.float32)

        face_center_y = face_y + face_h * 0.5
        core = np.exp(
            -1.8
            * (
                ((xx - center_x) / max(face_w * 0.72, 1.0)) ** 2
                + ((yy - face_center_y) / max(face_h * 0.82, 1.0)) ** 2
            )
        ).astype(np.float32)
        person_mask = np.maximum(halo * 0.88, core)
        combined = 1.0 - (1.0 - combined) * (1.0 - person_mask)
    return np.clip(combined, 0.0, 1.0)[..., None]


def _apply_direct_flash(
    rgb: np.ndarray,
    intensity: float,
    faces: list[tuple[int, int, int, int]],
) -> np.ndarray:
    """Simulate the hard, center-weighted flash built into an instant camera."""
    height, width = rgb.shape[:2]
    flash_mask = _build_flash_mask(height, width, faces)

    # A direct flash raises exposure most strongly around a centered foreground
    # subject, flattens its local contrast, and lets pale areas clip decisively.
    original_lum = _luminance(rgb)
    amount = flash_mask * intensity
    rgb = rgb * (1.0 + 1.22 * amount) + amount * np.array([0.105, 0.100, 0.090])
    rgb = np.clip(rgb, 0.0, 1.0)
    flashed_lum = _luminance(rgb)
    rgb += (flashed_lum - rgb) * np.clip(amount * 0.20, 0.0, 0.45)

    # The flash-to-background ratio is as important as brightness: surroundings
    # fall away while the near subject reads as conspicuously overexposed.
    background = 1.0 - flash_mask
    rgb *= 1.0 - background * 0.16 * intensity
    hot = _smoothstep(0.62, 0.94, flashed_lum) * amount
    rgb += hot * np.array([0.080, 0.058, 0.028])

    # Preserve a small amount of pre-flash shadow density so the center does not
    # become a featureless white circle on already-dark photos.
    shadow_detail = (1.0 - _smoothstep(0.08, 0.42, original_lum)) * amount
    rgb -= shadow_detail * 0.018
    return np.clip(rgb, 0.0, 1.0)


def _box_overlap_area(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> int:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    return max(0, min(ax + aw, bx + bw) - max(ax, bx)) * max(0, min(ay + ah, by + bh) - max(ay, by))


def _draw_debug_overlay(
    image: Image.Image,
    faces: list[tuple[int, int, int, int]],
    *,
    mode_config: ModeConfig,
    strength: float,
    grain: float,
    flash: float,
    vignette: bool,
    seed: int,
) -> Image.Image:
    """Draw detected faces and the active film recipe onto the output image."""
    original_mode = image.mode
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = image.size
    font_size = max(14, round(min(width, height) / 52))
    small_size = max(12, round(font_size * 0.82))
    font = ImageFont.load_default(size=font_size)
    small_font = ImageFont.load_default(size=small_size)
    accent = (40, 255, 210, 255)
    line_width = max(2, round(min(width, height) / 350))

    for index, (face_x, face_y, face_w, face_h) in enumerate(faces, start=1):
        box = (face_x, face_y, face_x + face_w, face_y + face_h)
        draw.rectangle(box, outline=accent, width=line_width)
        label = f"FACE {index}  {face_w}x{face_h}"
        label_box = draw.textbbox((0, 0), label, font=small_font)
        label_w = label_box[2] - label_box[0] + 10
        label_h = label_box[3] - label_box[1] + 7
        label_y = max(0, face_y - label_h)
        draw.rectangle((face_x, label_y, face_x + label_w, label_y + label_h), fill=(4, 18, 20, 220))
        draw.text((face_x + 5, label_y + 3), label, font=small_font, fill=accent)

    lines = [
        "INSTAX FILTER / DEBUG",
        f"MODE        {mode_config.name.upper()}",
        f"FACES       {len(faces)}",
        f"STRENGTH    {strength:.2f}",
        f"GRAIN       {grain:.2f}",
        f"FLASH       {flash:.2f}",
        f"VIGNETTE    {'ON' if vignette else 'OFF'}",
        f"SOFTEN      {min(strength * mode_config.soften_amount * 100, 78):.0f}%",
        "SHADOW      CYAN + GREEN",
        "HIGHLIGHT   CREAM + WARM",
        f"SEED        {seed}",
    ]
    padding = max(10, round(font_size * 0.65))
    gap = max(2, round(font_size * 0.22))
    line_metrics = [draw.textbbox((0, 0), line, font=font) for line in lines]
    panel_w = max(metric[2] - metric[0] for metric in line_metrics) + padding * 2
    line_h = max(metric[3] - metric[1] for metric in line_metrics)
    panel_h = line_h * len(lines) + gap * (len(lines) - 1) + padding * 2
    margin = max(10, round(min(width, height) * 0.018))
    left_panel = (margin, margin, panel_w, panel_h)
    right_panel = (width - margin - panel_w, margin, panel_w, panel_h)
    left_overlap = sum(_box_overlap_area(left_panel, face) for face in faces)
    right_overlap = sum(_box_overlap_area(right_panel, face) for face in faces)
    panel_x = left_panel[0] if left_overlap <= right_overlap else right_panel[0]
    panel_y = margin

    draw.rounded_rectangle(
        (panel_x, panel_y, panel_x + panel_w, panel_y + panel_h),
        radius=max(6, round(padding * 0.55)),
        fill=(4, 12, 16, 205),
        outline=(255, 255, 255, 75),
        width=1,
    )
    text_y = panel_y + padding
    for index, line in enumerate(lines):
        color = accent if index == 0 else (238, 245, 242, 255)
        draw.text((panel_x + padding, text_y), line, font=font, fill=color)
        text_y += line_h + gap

    result = Image.alpha_composite(base, overlay)
    return result if original_mode == "RGBA" else result.convert(original_mode)


def _resize_for_processing(image: Image.Image, max_side: int = 3600) -> tuple[Image.Image, float]:
    """Cap the work image to avoid excessive RAM, returning its scale factor."""
    longest = max(image.size)
    if longest <= max_side:
        return image, 1.0
    scale = max_side / longest
    size = tuple(max(1, round(value * scale)) for value in image.size)
    return image.resize(size, Image.Resampling.LANCZOS), scale


def apply_instax_look(
    image: Image.Image,
    *,
    mode: str = "instax",
    strength: float = 1.0,
    grain: float = 0.8,
    vignette: bool = True,
    flash: float = 0.1,
    debug: bool = False,
    seed: int = 0,
) -> Image.Image:
    """Return an RGB image with a natural Instax-inspired film rendering."""
    mode_config = _mode_config(mode)
    original_size = image.size
    alpha = image.getchannel("A") if "A" in image.getbands() else None
    work, scale = _resize_for_processing(image.convert("RGB"))
    rgb = _to_array(work)
    source = rgb.copy()
    faces = _detect_faces(source) if flash > 0 or debug else []

    # Instant film has a visibly narrower latitude than a phone sensor: mids are
    # bright, blacks keep a little emulsion density, and highlights reach a creamy
    # shoulder early. This stronger curve is intentional at the default setting.
    rgb = np.clip(rgb * (2.0 ** (0.18 * strength)), 0.0, 1.0)
    film_s = rgb * rgb * (3.0 - 2.0 * rgb)
    rgb += (film_s - rgb) * 0.18 * strength
    rgb = np.power(np.clip(rgb, 0.0, 1.0), 1.0 - 0.055 * strength)
    rgb = rgb * (1.0 - 0.045 * strength) + 0.024 * strength

    lum = _luminance(rgb)
    shadows = 1.0 - _smoothstep(0.08, 0.52, lum)
    highlights = _smoothstep(0.52, 0.96, lum)

    # Instax color response: cyan/green density in shadows and unmistakably creamy
    # warm highlights. Midtones get a small green bias without pushing skin yellow.
    midtone_mask = np.clip(1.0 - shadows - highlights, 0.0, 1.0)
    rgb += shadows * np.array([-0.030, 0.018, 0.038]) * strength
    rgb += midtone_mask * np.array([0.002, 0.010, -0.005]) * strength
    rgb += highlights * np.array([0.050, 0.024, -0.038]) * strength
    color_matrix = np.array(
        [
            [1.060, -0.030, -0.030],
            [-0.018, 1.048, -0.030],
            [-0.028, 0.020, 1.008],
        ],
        dtype=np.float32,
    )
    graded = rgb @ color_matrix.T
    rgb = rgb + (graded - rgb) * strength

    # Saturation is strongest in midtones and deliberately restrained in deep
    # shadows/highlights so skin and skies do not look like a phone preset.
    lum = _luminance(rgb)
    midtone = 1.0 - np.clip(np.abs(lum - 0.52) / 0.52, 0.0, 1.0)
    saturation = 1.0 + (0.18 * midtone - 0.055) * strength
    rgb = lum + (rgb - lum) * saturation

    if flash > 0:
        rgb = _apply_direct_flash(rgb, flash, faces)

    # Remove some brittle phone-camera microcontrast. The broad component mimics
    # the taking lens and Instax emulsion, while retaining enough edge definition.
    radius = max(work.size) / 850.0
    softened = _blur(rgb, max(1.15, radius * 1.55))
    rgb += (softened - rgb) * mode_config.soften_amount * strength

    # Suppress broader local contrast too. This is what removes the brittle HDR
    # clarity of modern phone photos rather than merely blurring single pixels.
    broad = _blur(rgb, max(2.4, radius * 4.2))
    local_detail = rgb - broad
    rgb -= local_detail * mode_config.local_detail_amount * strength

    # Stronger optical bloom and a red-biased halo around only the brightest areas.
    bright = np.clip((_luminance(rgb) - 0.72) / 0.28, 0.0, 1.0) ** 2
    glow_source = rgb * bright
    glow = _blur(glow_source, max(1.2, radius * 2.8))
    rgb = 1.0 - (1.0 - rgb) * (1.0 - glow * mode_config.glow_amount * strength)
    halo = _blur(glow_source, max(2.0, radius * 5.5))
    rgb += halo * np.array([0.065, 0.025, 0.006]) * strength * mode_config.halo_amount

    height, width = rgb.shape[:2]
    yy, xx = np.mgrid[-1:1:complex(height), -1:1:complex(width)]
    distance = np.sqrt(xx * xx + yy * yy)
    if vignette:
        edge = _smoothstep(0.52, 1.38, distance)[..., None]
        rgb *= 1.0 - edge * 0.155 * strength
        # Film edges often warm very slightly as density increases.
        rgb += edge * np.array([0.012, 0.004, -0.008]) * strength

    # Very low-frequency density variation makes the result feel exposed in a
    # chemical sheet rather than uniformly transformed pixel-by-pixel.
    rng = np.random.default_rng(seed)
    texture_h, texture_w = max(2, height // 180), max(2, width // 180)
    texture = rng.normal(0.0, 1.0, (texture_h, texture_w)).astype(np.float32)
    texture_img = Image.fromarray(np.uint8(np.clip(texture * 35 + 128, 0, 255)), "L")
    texture_img = texture_img.resize((width, height), Image.Resampling.BICUBIC)
    texture = (np.asarray(texture_img, dtype=np.float32) / 255.0 - 128 / 255) / (35 / 255)
    texture = texture[..., None]
    rgb += texture * np.array([0.007, 0.008, 0.006]) * strength

    # Blend the color/tone treatment independently from grain intensity.
    if strength < 1.0:
        rgb = source + (rgb - source) * strength

    # Two grain scales avoid uniform digital noise. Grain is stronger in shadows,
    # but never disappears completely from highlights.
    if grain > 0:
        fine = rng.normal(0.0, 1.0, (height, width, 1)).astype(np.float32)
        coarse_h, coarse_w = max(2, height // 3), max(2, width // 3)
        coarse = rng.normal(0.0, 1.0, (coarse_h, coarse_w, 1)).astype(np.float32)
        coarse_img = Image.fromarray(np.uint8(np.clip(coarse * 32 + 128, 0, 255)[..., 0]), "L")
        coarse_img = coarse_img.resize((width, height), Image.Resampling.BICUBIC)
        coarse = (_to_array(coarse_img.convert("RGB"))[..., :1] - 128 / 255) / (32 / 255)
        grain_pattern = fine * 0.72 + coarse * 0.28
        grain_weight = 0.015 + 0.027 * (1.0 - np.clip(_luminance(rgb), 0.0, 1.0))
        rgb += grain_pattern * grain_weight * grain

        chroma = rng.normal(0.0, 1.0, (height, width, 3)).astype(np.float32)
        chroma -= np.mean(chroma, axis=2, keepdims=True)
        rgb += chroma * 0.0032 * grain

    result = _to_image(rgb)
    if scale != 1.0:
        result = result.resize(original_size, Image.Resampling.LANCZOS)
    if alpha is not None:
        result.putalpha(alpha)
    if debug:
        debug_faces = [
            tuple(round(value / scale) for value in face)
            for face in faces
        ]
        result = _draw_debug_overlay(
            result,
            debug_faces,
            mode_config=mode_config,
            strength=strength,
            grain=grain,
            flash=flash,
            vignette=vignette,
            seed=seed,
        )
    return result


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

    # Warm, very slightly mottled stock looks more physical than a flat #fff frame.
    rng = np.random.default_rng(seed ^ 0x49A37B1D)
    base_color = np.array([247.0, 244.0, 234.0], dtype=np.float32)
    paper_noise = rng.normal(0.0, 0.7, (paper_size[1], paper_size[0], 1)).astype(np.float32)
    paper = np.uint8(np.clip(base_color + paper_noise, 0, 255))
    framed = Image.fromarray(paper, "RGB")

    # 20 px/mm: 4 mm side margins, 6 mm top and 18 mm bottom. In landscape,
    # rotating the print puts the signature wide margin on the right.
    position = (80, 120) if portrait else (120, 80)
    mask = fitted.getchannel("A") if "A" in fitted.getbands() else None
    framed.paste(fitted, position, mask)
    return framed


def _default_output(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_instax{input_path.suffix.lower()}")


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
    parser = argparse.ArgumentParser(description="给照片添加富士拍立得或 CCD 柔焦质感")
    parser.add_argument("input", type=Path, help="本地图片路径")
    parser.add_argument("-o", "--output", type=Path, help="输出路径（默认：原目录下 *_instax）")
    parser.add_argument(
        "--mode",
        choices=tuple(MODE_CONFIGS),
        default="instax",
        help="成像模式：instax 清晰拍立得，ccd 为原有重柔焦效果（默认 instax）",
    )
    parser.add_argument("--strength", type=float, help="调色强度，0–1.5（默认：instax 1.0，ccd 1.5）")
    parser.add_argument("--grain", type=float, help="颗粒强度，0–2（默认：instax 0.8，ccd 2.0）")
    frame_group = parser.add_mutually_exclusive_group()
    frame_group.add_argument("--frame", dest="frame", action="store_true", default=True, help="输出 Instax Mini 尺寸相纸（默认）")
    frame_group.add_argument("--no-frame", dest="frame", action="store_false", help="不裁切、不添加相纸白边")
    parser.add_argument("--no-vignette", action="store_true", help="关闭轻微暗角")
    parser.add_argument(
        "--flash",
        nargs="?",
        const=1.0,
        default=0.1,
        type=float,
        metavar="INTENSITY",
        help="模拟拍立得直闪，可选强度 0–2（默认 0.1，省略数值时为 1.0）",
    )
    parser.add_argument("--debug", action="store_true", help="标出人脸区域并显示当前调色参数")
    parser.add_argument("--seed", type=int, help="颗粒与相纸纹理随机种子（默认由文件路径稳定生成）")
    parser.add_argument("--quality", type=int, default=95, help="JPEG/WebP/HEIC 质量，1–100（默认 95）")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    mode_config = _mode_config(args.mode)
    strength = args.strength if args.strength is not None else mode_config.default_strength
    grain = args.grain if args.grain is not None else mode_config.default_grain
    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        raise SystemExit(f"找不到输入文件：{input_path}")
    if input_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise SystemExit(f"不支持的输入格式：{input_path.suffix}")
    if not 0.0 <= strength <= 1.5:
        raise SystemExit("--strength 必须在 0–1.5 之间")
    if not 0.0 <= grain <= 2.0:
        raise SystemExit("--grain 必须在 0–2 之间")
    if not 0.0 <= args.flash <= 2.0:
        raise SystemExit("--flash 强度必须在 0–2 之间")
    if not 1 <= args.quality <= 100:
        raise SystemExit("--quality 必须在 1–100 之间")

    output_path = (args.output.expanduser() if args.output else _default_output(input_path)).resolve()
    if output_path == input_path:
        raise SystemExit("输出路径不能与输入文件相同，以免覆盖原图")
    if output_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise SystemExit(f"不支持的输出格式：{output_path.suffix}")
    if not output_path.parent.is_dir():
        raise SystemExit(f"输出目录不存在：{output_path.parent}")

    try:
        with Image.open(input_path) as opened:
            image = ImageOps.exif_transpose(opened)
            if args.frame:
                image = fit_instax_image(image)
            result = apply_instax_look(
                image,
                mode=args.mode,
                strength=strength,
                grain=grain,
                vignette=not args.no_vignette,
                flash=args.flash,
                debug=args.debug,
                seed=args.seed if args.seed is not None else _seed_for(input_path),
            )
        if args.frame:
            result = add_instax_frame(result, seed=args.seed if args.seed is not None else _seed_for(input_path))
        _save(result, output_path, quality=args.quality)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"处理失败：{exc}") from exc

    print(f"已输出：{output_path}")


if __name__ == "__main__":
    main()

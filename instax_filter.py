#!/usr/bin/env python3
"""Emulate Fujifilm Instax Mini and early compact CCD camera rendering."""

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
    default_flash: float
    default_frame: bool
    processing_max_side: int
    exposure_ev: float
    contrast_amount: float
    gamma_lift: float
    black_compression: float
    black_lift: float
    shadow_tint: tuple[float, float, float]
    midtone_tint: tuple[float, float, float]
    highlight_tint: tuple[float, float, float]
    color_matrix: tuple[tuple[float, float, float], ...]
    midtone_saturation: float
    saturation_bias: float
    soften_amount: float
    local_detail_amount: float
    glow_amount: float
    halo_amount: float
    vignette_amount: float
    vignette_tint: tuple[float, float, float]
    density_texture: tuple[float, float, float]
    grain_fine_mix: float
    grain_floor: float
    grain_shadow: float
    chroma_noise_floor: float
    chroma_noise_shadow: float
    flash_gain: float
    flash_bias: tuple[float, float, float]
    flash_desaturation: float
    flash_background_falloff: float
    flash_hot_tint: tuple[float, float, float]


MODE_CONFIGS = {
    "instax": ModeConfig(
        name="instax",
        default_strength=1.0,
        default_grain=0.3,
        default_flash=0.35,
        default_frame=False,
        processing_max_side=3600,
        exposure_ev=0.10,
        contrast_amount=0.20,
        gamma_lift=0.035,
        black_compression=0.035,
        black_lift=0.012,
        shadow_tint=(-0.014, 0.007, 0.016),
        midtone_tint=(0.002, 0.005, -0.003),
        highlight_tint=(0.025, 0.012, -0.018),
        color_matrix=((1.040, -0.020, -0.020), (-0.012, 1.032, -0.020), (-0.018, 0.012, 1.006)),
        midtone_saturation=0.09,
        saturation_bias=-0.025,
        soften_amount=0.12,
        local_detail_amount=0.03,
        glow_amount=0.08,
        halo_amount=0.30,
        vignette_amount=0.09,
        vignette_tint=(0.008, 0.003, -0.005),
        density_texture=(0.004, 0.0045, 0.0035),
        grain_fine_mix=0.62,
        grain_floor=0.006,
        grain_shadow=0.012,
        chroma_noise_floor=0.0005,
        chroma_noise_shadow=0.0008,
        flash_gain=1.0,
        flash_bias=(0.085, 0.080, 0.070),
        flash_desaturation=0.16,
        flash_background_falloff=0.13,
        flash_hot_tint=(0.050, 0.035, 0.015),
    ),
    "ccd": ModeConfig(
        name="ccd",
        default_strength=1.0,
        default_grain=0.65,
        default_flash=0.15,
        default_frame=False,
        processing_max_side=2300,
        exposure_ev=0.03,
        contrast_amount=0.15,
        gamma_lift=0.01,
        black_compression=0.0,
        black_lift=0.0,
        shadow_tint=(-0.003, 0.0, 0.007),
        midtone_tint=(0.003, 0.001, -0.002),
        highlight_tint=(0.006, 0.002, -0.004),
        color_matrix=((1.035, -0.018, -0.017), (-0.010, 1.028, -0.018), (-0.014, -0.002, 1.016)),
        midtone_saturation=0.14,
        saturation_bias=0.0,
        soften_amount=0.02,
        local_detail_amount=-0.09,
        glow_amount=0.015,
        halo_amount=0.04,
        vignette_amount=0.025,
        vignette_tint=(0.0, 0.0, 0.0),
        density_texture=(0.0, 0.0, 0.0),
        grain_fine_mix=0.92,
        grain_floor=0.003,
        grain_shadow=0.016,
        chroma_noise_floor=0.0015,
        chroma_noise_shadow=0.006,
        flash_gain=1.12,
        flash_bias=(0.075, 0.082, 0.095),
        flash_desaturation=0.08,
        flash_background_falloff=0.17,
        flash_hot_tint=(0.025, 0.030, 0.038),
    ),
    "lofi": ModeConfig(
        name="lofi",
        default_strength=1.5,
        default_grain=2.0,
        default_flash=0.1,
        default_frame=False,
        processing_max_side=3600,
        exposure_ev=0.18,
        contrast_amount=0.18,
        gamma_lift=0.055,
        black_compression=0.045,
        black_lift=0.024,
        shadow_tint=(-0.030, 0.018, 0.038),
        midtone_tint=(0.002, 0.010, -0.005),
        highlight_tint=(0.050, 0.024, -0.038),
        color_matrix=((1.060, -0.030, -0.030), (-0.018, 1.048, -0.030), (-0.028, 0.020, 1.008)),
        midtone_saturation=0.18,
        saturation_bias=-0.055,
        soften_amount=0.52,
        local_detail_amount=0.16,
        glow_amount=0.17,
        halo_amount=1.0,
        vignette_amount=0.155,
        vignette_tint=(0.012, 0.004, -0.008),
        density_texture=(0.007, 0.008, 0.006),
        grain_fine_mix=0.72,
        grain_floor=0.015,
        grain_shadow=0.027,
        chroma_noise_floor=0.0032,
        chroma_noise_shadow=0.0,
        flash_gain=1.22,
        flash_bias=(0.105, 0.100, 0.090),
        flash_desaturation=0.20,
        flash_background_falloff=0.16,
        flash_hot_tint=(0.080, 0.058, 0.028),
    ),
    "disposable": ModeConfig(
        name="disposable",
        default_strength=1.0,
        default_grain=0.9,
        default_flash=0.22,
        default_frame=False,
        processing_max_side=3000,
        exposure_ev=0.12,
        contrast_amount=0.24,
        gamma_lift=0.02,
        black_compression=0.0,
        black_lift=0.006,
        shadow_tint=(-0.008, 0.018, 0.003),
        midtone_tint=(0.003, 0.004, -0.004),
        highlight_tint=(0.030, 0.016, -0.020),
        color_matrix=((1.050, -0.025, -0.025), (-0.012, 1.035, -0.023), (-0.020, 0.006, 1.014)),
        midtone_saturation=0.12,
        saturation_bias=-0.02,
        soften_amount=0.08,
        local_detail_amount=0.02,
        glow_amount=0.05,
        halo_amount=0.22,
        vignette_amount=0.14,
        vignette_tint=(0.012, 0.004, -0.010),
        density_texture=(0.004, 0.0045, 0.0035),
        grain_fine_mix=0.58,
        grain_floor=0.009,
        grain_shadow=0.018,
        chroma_noise_floor=0.0008,
        chroma_noise_shadow=0.0012,
        flash_gain=1.18,
        flash_bias=(0.100, 0.092, 0.075),
        flash_desaturation=0.22,
        flash_background_falloff=0.20,
        flash_hot_tint=(0.075, 0.048, 0.020),
    ),
    "chrome": ModeConfig(
        name="chrome",
        default_strength=1.0,
        default_grain=0.22,
        default_flash=0.05,
        default_frame=False,
        processing_max_side=3600,
        exposure_ev=0.02,
        contrast_amount=0.32,
        gamma_lift=-0.005,
        black_compression=0.01,
        black_lift=0.0,
        shadow_tint=(-0.018, 0.006, 0.022),
        midtone_tint=(0.002, 0.003, -0.004),
        highlight_tint=(0.026, 0.018, -0.018),
        color_matrix=((1.075, -0.036, -0.039), (-0.020, 1.060, -0.040), (-0.030, -0.005, 1.035)),
        midtone_saturation=0.28,
        saturation_bias=0.04,
        soften_amount=0.03,
        local_detail_amount=-0.05,
        glow_amount=0.04,
        halo_amount=0.12,
        vignette_amount=0.06,
        vignette_tint=(-0.003, 0.0, 0.004),
        density_texture=(0.002, 0.002, 0.0015),
        grain_fine_mix=0.82,
        grain_floor=0.004,
        grain_shadow=0.008,
        chroma_noise_floor=0.0003,
        chroma_noise_shadow=0.0005,
        flash_gain=1.05,
        flash_bias=(0.070, 0.070, 0.068),
        flash_desaturation=0.10,
        flash_background_falloff=0.12,
        flash_hot_tint=(0.040, 0.032, 0.020),
    ),
    "dream": ModeConfig(
        name="dream",
        default_strength=1.0,
        default_grain=0.18,
        default_flash=0.0,
        default_frame=False,
        processing_max_side=3600,
        exposure_ev=0.0,
        contrast_amount=-0.12,
        gamma_lift=0.04,
        black_compression=0.06,
        black_lift=0.030,
        shadow_tint=(0.012, 0.004, 0.025),
        midtone_tint=(0.010, 0.004, 0.008),
        highlight_tint=(0.030, 0.012, 0.018),
        color_matrix=((1.025, -0.010, -0.015), (-0.008, 1.020, -0.012), (-0.004, -0.006, 1.010)),
        midtone_saturation=0.04,
        saturation_bias=-0.10,
        soften_amount=0.26,
        local_detail_amount=0.08,
        glow_amount=0.18,
        halo_amount=1.05,
        vignette_amount=0.035,
        vignette_tint=(0.006, 0.0, 0.008),
        density_texture=(0.003, 0.0025, 0.0035),
        grain_fine_mix=0.68,
        grain_floor=0.003,
        grain_shadow=0.006,
        chroma_noise_floor=0.0004,
        chroma_noise_shadow=0.0004,
        flash_gain=0.78,
        flash_bias=(0.075, 0.065, 0.078),
        flash_desaturation=0.24,
        flash_background_falloff=0.07,
        flash_hot_tint=(0.055, 0.030, 0.045),
    ),
    "noir": ModeConfig(
        name="noir",
        default_strength=1.0,
        default_grain=1.1,
        default_flash=0.25,
        default_frame=False,
        processing_max_side=2800,
        exposure_ev=-0.03,
        contrast_amount=0.38,
        gamma_lift=-0.015,
        black_compression=0.0,
        black_lift=0.0,
        shadow_tint=(0.0, 0.0, 0.0),
        midtone_tint=(0.0, 0.0, 0.0),
        highlight_tint=(0.0, 0.0, 0.0),
        color_matrix=((0.2126, 0.7152, 0.0722), (0.2126, 0.7152, 0.0722), (0.2126, 0.7152, 0.0722)),
        midtone_saturation=0.0,
        saturation_bias=0.0,
        soften_amount=0.04,
        local_detail_amount=-0.04,
        glow_amount=0.03,
        halo_amount=0.08,
        vignette_amount=0.18,
        vignette_tint=(0.0, 0.0, 0.0),
        density_texture=(0.004, 0.004, 0.004),
        grain_fine_mix=0.60,
        grain_floor=0.012,
        grain_shadow=0.024,
        chroma_noise_floor=0.0,
        chroma_noise_shadow=0.0,
        flash_gain=1.15,
        flash_bias=(0.085, 0.085, 0.085),
        flash_desaturation=0.0,
        flash_background_falloff=0.18,
        flash_hot_tint=(0.045, 0.045, 0.045),
    ),
    "night": ModeConfig(
        name="night",
        default_strength=1.0,
        default_grain=0.85,
        default_flash=0.30,
        default_frame=False,
        processing_max_side=2300,
        exposure_ev=0.05,
        contrast_amount=0.28,
        gamma_lift=0.02,
        black_compression=0.0,
        black_lift=0.0,
        shadow_tint=(-0.025, 0.008, 0.035),
        midtone_tint=(0.014, -0.005, 0.018),
        highlight_tint=(0.030, -0.006, 0.025),
        color_matrix=((1.050, -0.024, -0.026), (-0.018, 1.050, -0.032), (-0.012, -0.020, 1.032)),
        midtone_saturation=0.24,
        saturation_bias=0.03,
        soften_amount=0.03,
        local_detail_amount=-0.08,
        glow_amount=0.12,
        halo_amount=0.50,
        vignette_amount=0.15,
        vignette_tint=(-0.008, 0.0, 0.012),
        density_texture=(0.0, 0.0, 0.0),
        grain_fine_mix=0.90,
        grain_floor=0.005,
        grain_shadow=0.022,
        chroma_noise_floor=0.002,
        chroma_noise_shadow=0.010,
        flash_gain=1.25,
        flash_bias=(0.070, 0.085, 0.115),
        flash_desaturation=0.06,
        flash_background_falloff=0.24,
        flash_hot_tint=(0.025, 0.040, 0.065),
    ),
}

MODE_DESCRIPTIONS = {
    "instax": "拍立得风格：适度反差、轻微软化、暖高光和细微乳剂纹理",
    "ccd": "2000 年代 CCD 卡片机：清晰边缘、硬直闪和暗部彩噪",
    "lofi": "重度 Lo-fi：重柔焦、粗颗粒、强辉光和青冷阴影",
    "disposable": "一次性胶片机：暖色硬直闪、绿色暗部和明显失光",
    "chrome": "高饱和反转片：深黑、浓郁蓝绿、暖高光和细颗粒",
    "dream": "低反差梦境：抬高黑位、降低饱和度和粉紫柔光",
    "noir": "高反差黑白：深黑、粗银盐颗粒、锐利边缘和强暗角",
    "night": "霓虹夜拍：冷蓝硬闪、洋红高光、深背景和暗部彩噪",
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
    mode_config: ModeConfig,
) -> np.ndarray:
    """Simulate the hard, center-weighted flash built into a compact camera."""
    height, width = rgb.shape[:2]
    flash_mask = _build_flash_mask(height, width, faces)

    # A direct flash raises exposure most strongly around a centered foreground
    # subject, flattens its local contrast, and lets pale areas clip decisively.
    original_lum = _luminance(rgb)
    amount = flash_mask * intensity
    rgb = rgb * (1.0 + mode_config.flash_gain * amount)
    rgb += amount * np.asarray(mode_config.flash_bias)
    rgb = np.clip(rgb, 0.0, 1.0)
    flashed_lum = _luminance(rgb)
    rgb += (flashed_lum - rgb) * np.clip(amount * mode_config.flash_desaturation, 0.0, 0.45)

    # The flash-to-background ratio is as important as brightness: surroundings
    # fall away while the near subject reads as conspicuously overexposed.
    background = 1.0 - flash_mask
    rgb *= 1.0 - background * mode_config.flash_background_falloff * intensity
    hot = _smoothstep(0.62, 0.94, flashed_lum) * amount
    rgb += hot * np.asarray(mode_config.flash_hot_tint)

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
        "CAMERA FILTER / DEBUG",
        f"MODE        {mode_config.name.upper()}",
        f"FACES       {len(faces)}",
        f"STRENGTH    {strength:.2f}",
        f"GRAIN       {grain:.2f}",
        f"FLASH       {flash:.2f}",
        f"VIGNETTE    {'ON' if vignette else 'OFF'}",
        f"SOFTEN      {min(strength * mode_config.soften_amount * 100, 78):.0f}%",
        f"DETAIL      {-mode_config.local_detail_amount * strength:+.0%}",
        f"CHROMA NOISE {mode_config.chroma_noise_shadow * grain:.3f}",
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
    strength: float | None = None,
    grain: float | None = None,
    vignette: bool = True,
    flash: float | None = None,
    debug: bool = False,
    seed: int = 0,
) -> Image.Image:
    """Return an RGB image with the selected compact-camera rendering."""
    mode_config = _mode_config(mode)
    strength = mode_config.default_strength if strength is None else strength
    grain = mode_config.default_grain if grain is None else grain
    flash = mode_config.default_flash if flash is None else flash
    original_size = image.size
    alpha = image.getchannel("A") if "A" in image.getbands() else None
    work, scale = _resize_for_processing(image.convert("RGB"), mode_config.processing_max_side)
    rgb = _to_array(work)
    source = rgb.copy()
    faces = _detect_faces(source) if flash > 0 or debug else []

    # Both instant film and small-sensor JPEGs have less latitude than a modern
    # phone, but each recipe controls its own exposure, shoulder and black density.
    rgb = np.clip(rgb * (2.0 ** (mode_config.exposure_ev * strength)), 0.0, 1.0)
    film_s = rgb * rgb * (3.0 - 2.0 * rgb)
    rgb += (film_s - rgb) * mode_config.contrast_amount * strength
    rgb = np.power(np.clip(rgb, 0.0, 1.0), 1.0 - mode_config.gamma_lift * strength)
    rgb = rgb * (1.0 - mode_config.black_compression * strength) + mode_config.black_lift * strength

    lum = _luminance(rgb)
    shadows = 1.0 - _smoothstep(0.08, 0.52, lum)
    highlights = _smoothstep(0.52, 0.96, lum)

    # The mode map separates Instax dye response from compact-camera JPEG color.
    midtone_mask = np.clip(1.0 - shadows - highlights, 0.0, 1.0)
    rgb += shadows * np.asarray(mode_config.shadow_tint) * strength
    rgb += midtone_mask * np.asarray(mode_config.midtone_tint) * strength
    rgb += highlights * np.asarray(mode_config.highlight_tint) * strength
    color_matrix = np.asarray(mode_config.color_matrix, dtype=np.float32)
    graded = rgb @ color_matrix.T
    rgb = rgb + (graded - rgb) * strength

    # Saturation is strongest in midtones and deliberately restrained in deep
    # shadows/highlights so skin and skies do not look like a phone preset.
    lum = _luminance(rgb)
    midtone = 1.0 - np.clip(np.abs(lum - 0.52) / 0.52, 0.0, 1.0)
    saturation = 1.0 + (mode_config.midtone_saturation * midtone + mode_config.saturation_bias) * strength
    rgb = lum + (rgb - lum) * saturation

    if flash > 0:
        rgb = _apply_direct_flash(rgb, flash, faces, mode_config)

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
        rgb *= 1.0 - edge * mode_config.vignette_amount * strength
        rgb += edge * np.asarray(mode_config.vignette_tint) * strength

    # Very low-frequency density variation makes the result feel exposed in a
    # chemical sheet rather than uniformly transformed pixel-by-pixel.
    rng = np.random.default_rng(seed)
    texture_h, texture_w = max(2, height // 180), max(2, width // 180)
    texture = rng.normal(0.0, 1.0, (texture_h, texture_w)).astype(np.float32)
    texture_img = Image.fromarray(np.uint8(np.clip(texture * 35 + 128, 0, 255)), "L")
    texture_img = texture_img.resize((width, height), Image.Resampling.BICUBIC)
    texture = (np.asarray(texture_img, dtype=np.float32) / 255.0 - 128 / 255) / (35 / 255)
    texture = texture[..., None]
    rgb += texture * np.asarray(mode_config.density_texture) * strength

    # Fine/coarse and luminance/chroma noise ratios distinguish emulsion texture
    # from the colored high-ISO noise of a small CCD and its early JPEG pipeline.
    if grain > 0:
        fine = rng.normal(0.0, 1.0, (height, width, 1)).astype(np.float32)
        coarse_h, coarse_w = max(2, height // 3), max(2, width // 3)
        coarse = rng.normal(0.0, 1.0, (coarse_h, coarse_w, 1)).astype(np.float32)
        coarse_img = Image.fromarray(np.uint8(np.clip(coarse * 32 + 128, 0, 255)[..., 0]), "L")
        coarse_img = coarse_img.resize((width, height), Image.Resampling.BICUBIC)
        coarse = (_to_array(coarse_img.convert("RGB"))[..., :1] - 128 / 255) / (32 / 255)
        grain_pattern = fine * mode_config.grain_fine_mix + coarse * (1.0 - mode_config.grain_fine_mix)
        inverse_lum = 1.0 - np.clip(_luminance(rgb), 0.0, 1.0)
        grain_weight = mode_config.grain_floor + mode_config.grain_shadow * inverse_lum
        rgb += grain_pattern * grain_weight * grain

        chroma = rng.normal(0.0, 1.0, (height, width, 3)).astype(np.float32)
        chroma -= np.mean(chroma, axis=2, keepdims=True)
        chroma_weight = mode_config.chroma_noise_floor + mode_config.chroma_noise_shadow * inverse_lum
        rgb += chroma * chroma_weight * grain

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
            mode_config = _mode_config(mode)
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

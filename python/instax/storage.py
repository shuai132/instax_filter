"""Image output naming, deterministic seeding, and codec-aware persistence."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".heic", ".heif"}

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

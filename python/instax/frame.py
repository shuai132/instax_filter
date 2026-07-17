"""Instax Mini crop and paper-frame rendering."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageOps

INSTAX_PAPER_PORTRAIT = (1080, 1720)
INSTAX_IMAGE_PORTRAIT = (920, 1240)

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

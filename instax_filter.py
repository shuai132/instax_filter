#!/usr/bin/env python3
"""Backward-compatible facade for the modular :mod:`instax` package."""

from instax.cli import build_parser, main
from instax.config import MODE_CONFIGS, MODE_DESCRIPTIONS, ModeConfig, get_mode_config
from instax.engine import _build_flash_mask, _draw_debug_overlay, apply_instax_look
from instax.frame import add_instax_frame, fit_instax_image
from instax.storage import _save

__all__ = [
    "MODE_CONFIGS",
    "MODE_DESCRIPTIONS",
    "ModeConfig",
    "_build_flash_mask",
    "_draw_debug_overlay",
    "_save",
    "add_instax_frame",
    "apply_instax_look",
    "build_parser",
    "fit_instax_image",
    "get_mode_config",
    "main",
]

if __name__ == "__main__":
    main()

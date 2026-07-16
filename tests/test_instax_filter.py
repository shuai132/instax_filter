import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image

from instax_filter import _save, add_instax_frame, apply_instax_look, build_parser, fit_instax_image


class InstaxFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        yy, xx = np.mgrid[0:48, 0:64]
        pixels = np.stack(
            ((xx * 4) % 256, (yy * 5) % 256, ((xx + yy) * 2) % 256),
            axis=2,
        ).astype(np.uint8)
        self.image = Image.fromarray(pixels, "RGB")

    def test_neutral_settings_preserve_pixels(self) -> None:
        result = apply_instax_look(self.image, strength=0, grain=0)
        np.testing.assert_array_equal(np.asarray(result), np.asarray(self.image))

    def test_cli_defaults_use_maximum_film_effect(self) -> None:
        args = build_parser().parse_args(["photo.jpg"])
        self.assertEqual(args.strength, 1.5)
        self.assertEqual(args.grain, 2.0)
        self.assertEqual(args.flash, 0.1)
        self.assertEqual(build_parser().parse_args(["photo.jpg", "--flash"]).flash, 1.0)
        self.assertEqual(build_parser().parse_args(["photo.jpg", "--flash", "1.7"]).flash, 1.7)

    def test_flash_brightens_center_more_than_edges(self) -> None:
        midgray = Image.new("RGB", (120, 160), (90, 90, 90))
        baseline = np.asarray(
            apply_instax_look(midgray, strength=1, grain=0, vignette=False, flash=False),
            dtype=np.float32,
        )
        flashed = np.asarray(
            apply_instax_look(midgray, strength=1, grain=0, vignette=False, flash=1.0),
            dtype=np.float32,
        )
        delta = flashed.mean(axis=2) - baseline.mean(axis=2)
        center_delta = delta[55:105, 40:80].mean()
        edge_delta = np.concatenate((delta[:20].ravel(), delta[-20:].ravel())).mean()
        self.assertGreater(center_delta, 80)
        self.assertGreater(center_delta, edge_delta + 60)

    def test_flash_intensity_changes_exposure(self) -> None:
        dark = Image.new("RGB", (120, 160), (48, 48, 48))
        low = np.asarray(apply_instax_look(dark, strength=1, grain=0, flash=0.4), dtype=np.float32)
        high = np.asarray(apply_instax_look(dark, strength=1, grain=0, flash=1.6), dtype=np.float32)
        self.assertGreater(high[55:105, 40:80].mean(), low[55:105, 40:80].mean() + 45)

    def test_seed_makes_grain_repeatable(self) -> None:
        first = apply_instax_look(self.image, seed=123)
        second = apply_instax_look(self.image, seed=123)
        np.testing.assert_array_equal(np.asarray(first), np.asarray(second))

    def test_alpha_channel_is_preserved(self) -> None:
        rgba = self.image.convert("RGBA")
        alpha = np.arange(64, dtype=np.uint8)[None, :].repeat(48, axis=0) * 4
        rgba.putalpha(Image.fromarray(alpha, "L"))
        result = apply_instax_look(rgba, seed=1)
        np.testing.assert_array_equal(np.asarray(result.getchannel("A")), alpha)

    def test_landscape_frame_uses_instax_mini_dimensions(self) -> None:
        framed = add_instax_frame(self.image)
        self.assertEqual(framed.size, (1720, 1080))
        self.assertEqual(framed.mode, "RGB")

    def test_portrait_content_and_frame_use_instax_mini_ratio(self) -> None:
        portrait = self.image.transpose(Image.Transpose.ROTATE_90)
        fitted = fit_instax_image(portrait)
        framed = add_instax_frame(fitted)
        self.assertEqual(fitted.size, (920, 1240))
        self.assertEqual(framed.size, (1080, 1720))

    def test_heic_save_and_open_round_trip(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "filtered.heic"
            _save(self.image, output, quality=90)
            with Image.open(output) as reopened:
                reopened.load()
                self.assertEqual(reopened.size, self.image.size)
                self.assertEqual(reopened.format, "HEIF")


if __name__ == "__main__":
    unittest.main()

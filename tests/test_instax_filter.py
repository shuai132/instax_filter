import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
from PIL import Image

from instax_filter import (
    MODE_CONFIGS,
    _build_flash_mask,
    _draw_debug_overlay,
    _save,
    add_instax_frame,
    apply_instax_look,
    build_parser,
    fit_instax_image,
    main,
)


class InstaxFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        yy, xx = np.mgrid[0:48, 0:64]
        pixels = np.stack(
            ((xx * 4) % 256, (yy * 5) % 256, ((xx + yy) * 2) % 256),
            axis=2,
        ).astype(np.uint8)
        self.image = Image.fromarray(pixels, "RGB")

    def test_neutral_settings_preserve_pixels(self) -> None:
        result = apply_instax_look(self.image, strength=0, grain=0, flash=0)
        np.testing.assert_array_equal(np.asarray(result), np.asarray(self.image))

    def test_cli_defaults_use_restrained_instax_mode(self) -> None:
        args = build_parser().parse_args(["photo.jpg"])
        self.assertEqual(args.mode, ["instax"])
        self.assertIsNone(args.strength)
        self.assertIsNone(args.grain)
        self.assertIsNone(args.flash)
        self.assertIsNone(args.frame)
        self.assertTrue(build_parser().parse_args(["photo.jpg", "--frame"]).frame)
        self.assertFalse(build_parser().parse_args(["photo.jpg", "--no-frame"]).frame)
        self.assertEqual(build_parser().parse_args(["photo.jpg", "--flash"]).flash, 1.0)
        self.assertEqual(build_parser().parse_args(["photo.jpg", "--flash", "1.7"]).flash, 1.7)
        self.assertFalse(args.debug)
        self.assertTrue(build_parser().parse_args(["photo.jpg", "--debug"]).debug)

    def test_cli_accepts_multiple_modes(self) -> None:
        args = build_parser().parse_args(["photo.jpg", "--mode", "ccd", "noir", "night"])
        self.assertEqual(args.mode, ["ccd", "noir", "night"])

    def test_cli_mode_all_selects_every_mode(self) -> None:
        args = build_parser().parse_args(["photo.jpg", "--mode-all"])
        self.assertTrue(args.mode_all)

    def test_help_describes_every_mode(self) -> None:
        help_text = build_parser().format_help()
        for mode, description in {
            "instax": "拍立得风格",
            "ccd": "2000 年代 CCD 卡片机",
            "lofi": "重度 Lo-fi",
            "disposable": "一次性胶片机",
            "chrome": "高饱和反转片",
            "dream": "低反差梦境",
            "noir": "高反差黑白",
            "night": "霓虹夜拍",
        }.items():
            with self.subTest(mode=mode):
                self.assertIn(f"{mode:<10} {description}", help_text)

    def test_cli_generates_one_output_per_mode(self) -> None:
        with TemporaryDirectory() as directory:
            input_path = Path(directory) / "photo.png"
            self.image.save(input_path)
            argv = ["instax-filter", str(input_path), "--mode", "ccd", "noir", "--seed", "17"]
            with patch("sys.argv", argv), redirect_stdout(StringIO()) as stdout:
                main()
            self.assertTrue((input_path.parent / "photo_ccd.png").is_file())
            self.assertTrue((input_path.parent / "photo_noir.png").is_file())
            self.assertIn("photo_ccd.png", stdout.getvalue())
            self.assertIn("photo_noir.png", stdout.getvalue())

    def test_cli_mode_all_generates_every_mode(self) -> None:
        with TemporaryDirectory() as directory:
            input_path = Path(directory) / "photo.png"
            self.image.save(input_path)
            argv = ["instax-filter", str(input_path), "--mode-all", "--no-frame", "--seed", "17"]
            with patch("sys.argv", argv), redirect_stdout(StringIO()):
                main()
            for mode in MODE_CONFIGS:
                with self.subTest(mode=mode):
                    self.assertTrue((input_path.parent / f"photo_{mode}.png").is_file())

    def test_cli_rejects_output_path_with_multiple_modes(self) -> None:
        with TemporaryDirectory() as directory:
            input_path = Path(directory) / "photo.png"
            self.image.save(input_path)
            argv = ["instax-filter", str(input_path), "--mode", "ccd", "noir", "-o", str(Path(directory) / "out.png")]
            with patch("sys.argv", argv), self.assertRaisesRegex(SystemExit, "生成多个模式"):
                main()

    def test_cli_rejects_output_path_with_mode_all(self) -> None:
        with TemporaryDirectory() as directory:
            input_path = Path(directory) / "photo.png"
            self.image.save(input_path)
            argv = ["instax-filter", str(input_path), "--mode-all", "-o", str(Path(directory) / "out.png")]
            with patch("sys.argv", argv), self.assertRaisesRegex(SystemExit, "生成多个模式"):
                main()

    def test_ccd_mode_is_crisper_than_instax(self) -> None:
        pixels = np.zeros((160, 160, 3), dtype=np.uint8)
        pixels[:, 80:] = 255
        edge = Image.fromarray(pixels, "RGB")
        instax = np.asarray(
            apply_instax_look(edge, mode="instax", strength=1.5, grain=0, vignette=False, flash=0),
            dtype=np.float32,
        )
        ccd = np.asarray(
            apply_instax_look(edge, mode="ccd", strength=1.5, grain=0, vignette=False, flash=0),
            dtype=np.float32,
        )
        lofi = np.asarray(
            apply_instax_look(edge, mode="lofi", strength=1.5, grain=0, vignette=False, flash=0),
            dtype=np.float32,
        )
        instax_edge_contrast = instax[:, 80].mean() - instax[:, 79].mean()
        ccd_edge_contrast = ccd[:, 80].mean() - ccd[:, 79].mean()
        lofi_edge_contrast = lofi[:, 80].mean() - lofi[:, 79].mean()
        self.assertGreater(ccd_edge_contrast, instax_edge_contrast)
        self.assertGreater(instax_edge_contrast, lofi_edge_contrast)

    def test_ccd_noise_is_more_chromatic_in_shadows(self) -> None:
        dark = Image.new("RGB", (160, 160), (35, 35, 35))
        instax = np.asarray(apply_instax_look(dark, mode="instax", grain=1, flash=0, seed=7), dtype=np.float32)
        ccd = np.asarray(apply_instax_look(dark, mode="ccd", grain=1, flash=0, seed=7), dtype=np.float32)
        instax -= instax.mean(axis=(0, 1), keepdims=True)
        ccd -= ccd.mean(axis=(0, 1), keepdims=True)
        instax_chroma = np.std(instax - instax.mean(axis=2, keepdims=True))
        ccd_chroma = np.std(ccd - ccd.mean(axis=2, keepdims=True))
        self.assertGreater(ccd_chroma, instax_chroma * 2)

    def test_every_mode_preserves_original_dimensions_by_default(self) -> None:
        self.assertTrue(all(not config.default_frame for config in MODE_CONFIGS.values()))

    def test_lofi_mode_preserves_original_heavy_recipe(self) -> None:
        lofi = MODE_CONFIGS["lofi"]
        self.assertEqual(lofi.default_strength, 1.5)
        self.assertEqual(lofi.default_grain, 2.0)
        self.assertEqual(lofi.soften_amount, 0.52)
        self.assertEqual(lofi.local_detail_amount, 0.16)
        self.assertEqual(lofi.glow_amount, 0.17)

    def test_disposable_mode_uses_hard_flash_and_film_grain(self) -> None:
        disposable = MODE_CONFIGS["disposable"]
        self.assertEqual(disposable.default_grain, 0.9)
        self.assertEqual(disposable.default_flash, 0.22)
        self.assertGreater(disposable.vignette_amount, MODE_CONFIGS["instax"].vignette_amount)
        self.assertGreater(disposable.flash_background_falloff, MODE_CONFIGS["instax"].flash_background_falloff)

    def test_chrome_mode_is_vivid_crisp_and_fine_grained(self) -> None:
        chrome = MODE_CONFIGS["chrome"]
        self.assertGreater(chrome.midtone_saturation, MODE_CONFIGS["ccd"].midtone_saturation)
        self.assertLess(chrome.local_detail_amount, 0)
        self.assertLess(chrome.default_grain, MODE_CONFIGS["instax"].default_grain)

    def test_dream_mode_lifts_blacks_and_adds_bloom(self) -> None:
        dream = MODE_CONFIGS["dream"]
        self.assertLess(dream.contrast_amount, 0)
        self.assertGreater(dream.black_lift, MODE_CONFIGS["lofi"].black_lift)
        self.assertGreater(dream.glow_amount, MODE_CONFIGS["lofi"].glow_amount)
        self.assertGreater(dream.halo_amount, MODE_CONFIGS["lofi"].halo_amount)

    def test_noir_mode_outputs_neutral_monochrome(self) -> None:
        noir = np.asarray(apply_instax_look(self.image, mode="noir", grain=0, flash=0), dtype=np.int16)
        self.assertLessEqual(np.max(np.abs(noir[..., 0] - noir[..., 1])), 1)
        self.assertLessEqual(np.max(np.abs(noir[..., 1] - noir[..., 2])), 1)
        self.assertGreater(MODE_CONFIGS["noir"].contrast_amount, MODE_CONFIGS["chrome"].contrast_amount)

    def test_night_mode_uses_cool_flash_and_strong_shadow_chroma(self) -> None:
        night = MODE_CONFIGS["night"]
        self.assertGreater(night.flash_bias[2], night.flash_bias[0])
        self.assertGreater(night.chroma_noise_shadow, MODE_CONFIGS["ccd"].chroma_noise_shadow)
        self.assertGreater(night.flash_background_falloff, MODE_CONFIGS["disposable"].flash_background_falloff)

    def test_every_mode_renders_with_its_defaults(self) -> None:
        for mode in MODE_CONFIGS:
            with self.subTest(mode=mode):
                result = apply_instax_look(self.image, mode=mode, seed=17)
                self.assertEqual(result.size, self.image.size)

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

    def test_face_flash_mask_tracks_each_detected_face(self) -> None:
        mask = _build_flash_mask(200, 300, [(35, 35, 40, 40), (220, 45, 35, 35)])[..., 0]
        self.assertGreater(mask[55, 55], 0.9)
        self.assertGreater(mask[62, 237], 0.9)
        self.assertLess(mask[190, 150], 0.05)

    def test_debug_overlay_marks_faces_and_preserves_image_shape(self) -> None:
        image = Image.new("RGB", (640, 480), (90, 90, 90))
        debugged = _draw_debug_overlay(
            image,
            [(240, 120, 100, 100)],
            mode_config=MODE_CONFIGS["ccd"],
            strength=1.5,
            grain=2.0,
            flash=0.1,
            vignette=True,
            seed=42,
        )
        self.assertEqual(debugged.size, image.size)
        self.assertEqual(debugged.mode, image.mode)
        self.assertNotEqual(debugged.getpixel((240, 120)), image.getpixel((240, 120)))

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

"""Generate a deterministic input and compare Python/C++ wall time and output statistics."""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image


def timed(command: list[str], *, repeats: int) -> list[float]:
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
        samples.append(time.perf_counter() - started)
    return samples


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, default=Path("cpp/build/instax-filter-cpp"))
    parser.add_argument("--size", type=int, default=2400)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    directory = Path("cpp/build/benchmark")
    directory.mkdir(parents=True, exist_ok=True)
    height, width = round(args.size * 0.75), args.size
    yy, xx = np.mgrid[:height, :width]
    pixels = np.stack(
        ((xx * 7 + yy * 2) % 256, (yy * 5 + xx // 7) % 256, ((xx + yy) * 3) % 256),
        axis=2,
    ).astype(np.uint8)
    input_path = directory / "input.png"
    python_path = directory / "python.png"
    cpp_path = directory / "cpp.png"
    Image.fromarray(pixels, "RGB").save(input_path)

    common = ["--mode", "instax", "--seed", "42", "--flash", "0", "--grain", "0.3"]
    python_command = ["uv", "run", "instax-filter", str(input_path), "-o", str(python_path), *common]
    cpp_command = [str(args.build), str(input_path), "-o", str(cpp_path), *common]
    python_times = timed(python_command, repeats=args.repeats)
    cpp_times = timed(cpp_command, repeats=args.repeats)

    py = np.asarray(Image.open(python_path).convert("RGB"), dtype=np.float32)
    cpp = np.asarray(Image.open(cpp_path).convert("RGB"), dtype=np.float32)
    difference = np.abs(py - cpp)
    py_median = float(np.median(python_times))
    cpp_median = float(np.median(cpp_times))
    print(f"image: {width}x{height}, repeats: {args.repeats}")
    print(f"python: {py_median:.3f}s median ({', '.join(f'{v:.3f}' for v in python_times)})")
    print(f"c++:    {cpp_median:.3f}s median ({', '.join(f'{v:.3f}' for v in cpp_times)})")
    print(f"speedup: {py_median / cpp_median:.2f}x")
    print(f"output: shape_equal={py.shape == cpp.shape}, mean_abs_diff={difference.mean():.2f}, p95_abs_diff={np.percentile(difference, 95):.2f}")


if __name__ == "__main__":
    main()

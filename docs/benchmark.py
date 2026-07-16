#!/usr/bin/env python3
"""Benchmark the Python and Release C++ CLIs with the checked-in test image."""

from __future__ import annotations

import argparse
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = Path(__file__).with_name("cxk.jpg")
DEFAULT_CPP = ROOT / "cpp" / "build" / "instax-filter-cpp"


def run_timed(command: list[str]) -> float:
    started = time.perf_counter()
    subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    return time.perf_counter() - started


def describe(name: str, samples: list[float]) -> None:
    rendered = ", ".join(f"{sample:.3f}" for sample in samples)
    print(
        f"{name:<7} median={statistics.median(samples):.3f}s "
        f"min={min(samples):.3f}s max={max(samples):.3f}s samples=[{rendered}]"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--cpp", type=Path, default=DEFAULT_CPP)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--warmups", type=int, default=2)
    args = parser.parse_args()

    if args.repeats < 1 or args.warmups < 0:
        parser.error("--repeats must be positive and --warmups cannot be negative")

    input_path = args.input.resolve()
    cpp_path = args.cpp.resolve()
    if not input_path.is_file():
        parser.error(f"input image does not exist: {input_path}")
    if not cpp_path.is_file():
        parser.error(f"C++ executable does not exist: {cpp_path}")

    common = ["--mode", "instax", "--seed", "42", "--flash", "0", "--grain", "0.3"]
    with Image.open(input_path) as image:
        dimensions = image.size

    python_samples: list[float] = []
    cpp_samples: list[float] = []
    with tempfile.TemporaryDirectory(prefix="instax-benchmark-") as temporary:
        temporary_path = Path(temporary)
        commands = {
            "python": [
                sys.executable,
                str(ROOT / "instax_filter.py"),
                str(input_path),
                "-o",
                str(temporary_path / "python.jpg"),
                *common,
            ],
            "c++": [
                str(cpp_path),
                str(input_path),
                "-o",
                str(temporary_path / "cpp.jpg"),
                *common,
            ],
        }

        for _ in range(args.warmups):
            run_timed(commands["python"])
            run_timed(commands["c++"])

        # Alternate first position to reduce bias from thermal and background load.
        for index in range(args.repeats):
            order = ("python", "c++") if index % 2 == 0 else ("c++", "python")
            for implementation in order:
                elapsed = run_timed(commands[implementation])
                (python_samples if implementation == "python" else cpp_samples).append(elapsed)

    python_median = statistics.median(python_samples)
    cpp_median = statistics.median(cpp_samples)
    print(f"platform: {platform.platform()}")
    print(f"python:   {platform.python_implementation()} {platform.python_version()}")
    print(f"image:    {input_path.relative_to(ROOT)} ({dimensions[0]}x{dimensions[1]})")
    print(f"runs:     {args.repeats} measured, {args.warmups} warm-up per implementation")
    describe("Python", python_samples)
    describe("C++", cpp_samples)
    print(f"speedup: {python_median / cpp_median:.2f}x (Python median / C++ median)")


if __name__ == "__main__":
    main()

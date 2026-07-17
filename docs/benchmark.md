# C++ 与 Python 性能对比

## 结论

在 `docs/cxk.jpg`（1152 × 2048）上执行相同的 Instax 滤镜端到端任务时，Release C++ 版本的中位耗时为 **0.431 秒**，Python 版本为 **1.073 秒**。本机测试中 C++ 约为 Python 的 **2.49 倍速**，即耗时减少约 60%。

该数字包含进程启动、JPEG 解码、滤镜处理和 JPEG 编码，代表一次 CLI 调用的实际等待时间。结果只反映下述机器与软件版本，不应直接视为其他平台上的固定倍数。

## 测试条件

| 项目 | 配置 |
| --- | --- |
| 测试日期 | 2026-07-17 |
| 机器 | Apple M1 Pro，16 GiB 内存 |
| 系统 | macOS 26.5.2，arm64 |
| 测试图 | `docs/cxk.jpg`，1152 × 2048 JPEG |
| 测试参数 | `--mode instax --seed 42 --flash 0 --grain 0.3` |
| C++ | Apple Clang 17.0.0，OpenCV 4.13.0 |
| Python | CPython 3.12.12，OpenCV 4.13.0，NumPy 2.5.1，Pillow 12.3.0 |
| 采样 | 每个实现预热 2 次，再正式执行 10 次；交错执行 |

C++ 使用 CMake Release 配置构建，当前配置对应 `-O3 -DNDEBUG`。Python 包是纯 Python wheel，不含原生扩展或 Debug/Release 构建档位，因此不存在可额外切换的 Release 编译配置；测试使用锁定依赖的项目虚拟环境直接运行。

## 测试结果

| 实现 | 中位数 | 最快 | 最慢 | 相对耗时 |
| --- | ---: | ---: | ---: | ---: |
| Python | 1.073 s | 1.062 s | 1.103 s | 2.49× |
| C++ Release | 0.431 s | 0.427 s | 0.434 s | 1.00× |

原始样本（秒）：

```text
Python: 1.085, 1.062, 1.092, 1.064, 1.082, 1.070, 1.103, 1.068, 1.071, 1.075
C++:    0.430, 0.431, 0.434, 0.431, 0.432, 0.433, 0.433, 0.427, 0.431, 0.429
```

## 复现方法

从仓库根目录执行：

```bash
cmake -S cpp -B cpp/build -DCMAKE_BUILD_TYPE=Release
cmake --build cpp/build --config Release -j
uv run --project python --frozen python docs/benchmark.py
```

可通过 `--repeats`、`--warmups`、`--input` 和 `--cpp` 修改采样次数、预热次数、测试图和 C++ 可执行文件路径。例如快速检查：

```bash
uv run --project python --frozen python docs/benchmark.py --repeats 3 --warmups 1
```

基准脚本将输出写入系统临时目录并在结束后清理，不会覆盖测试图，也不会把生成图片留在仓库中。

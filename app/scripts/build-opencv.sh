#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(CDPATH= cd -- "$script_dir/../.." && pwd)
source_dir="$repo_dir/cpp/.deps/opencv"
build_dir="$repo_dir/cpp/.deps/opencv-app-build"
install_dir="$repo_dir/cpp/.deps/opencv-app-install"
opencv_version=4.13.0
deployment_target=${MACOSX_DEPLOYMENT_TARGET:-14.0}
target_arch=${INSTAX_OPENCV_ARCH:-$(uname -m)}

if [ ! -f "$source_dir/CMakeLists.txt" ]; then
    mkdir -p "$repo_dir/cpp/.deps"
    git clone --depth 1 --branch "$opencv_version" \
        https://github.com/opencv/opencv.git "$source_dir"
fi

cmake -S "$source_dir" -B "$build_dir" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$install_dir" \
    -DCMAKE_OSX_ARCHITECTURES="$target_arch" \
    -DCMAKE_OSX_DEPLOYMENT_TARGET="$deployment_target" \
    -DBUILD_LIST=core,imgproc,objdetect \
    -DBUILD_SHARED_LIBS=OFF \
    -DBUILD_TESTS=OFF \
    -DBUILD_PERF_TESTS=OFF \
    -DBUILD_EXAMPLES=OFF \
    -DBUILD_opencv_apps=OFF \
    -DBUILD_JAVA=OFF \
    -DBUILD_opencv_python3=OFF \
    -DWITH_OPENCL=OFF \
    -DWITH_FFMPEG=OFF \
    -DWITH_GSTREAMER=OFF

cmake --build "$build_dir" --parallel
cmake --install "$build_dir"

echo "OpenCV installed at $install_dir"

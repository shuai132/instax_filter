#!/bin/sh
set -eu

usage() {
    echo "Usage: ./build.sh [--debug | --release]"
}

if [ "$#" -gt 1 ]; then
    usage >&2
    exit 2
fi

configuration=Release
case "${1:-}" in
    ""|--release)
        configuration=Release
        ;;
    --debug)
        configuration=Debug
        ;;
    -h|--help)
        usage
        exit 0
        ;;
    *)
        echo "Unknown option: $1" >&2
        usage >&2
        exit 2
        ;;
esac

app_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project="$app_dir/InstaxApp.xcodeproj"
opencv_root="$app_dir/../cpp/.deps/opencv-app-install"
derived_data="$app_dir/build"
product="$derived_data/Build/Products/$configuration/Instax.app"

if ! command -v xcodebuild >/dev/null 2>&1; then
    echo "Error: xcodebuild was not found. Install Xcode first." >&2
    exit 1
fi

if [ ! -d "$project" ]; then
    echo "Error: InstaxApp.xcodeproj was not found." >&2
    echo "Run 'xcodegen generate' in the app directory first." >&2
    exit 1
fi

if [ ! -f "$opencv_root/lib/libopencv_core.a" ]; then
    echo "Error: the OpenCV static libraries were not found." >&2
    echo "Run '$app_dir/scripts/build-opencv.sh' first." >&2
    exit 1
fi

echo "Building Instax.app ($configuration)..."
xcodebuild \
    -project "$project" \
    -scheme InstaxApp \
    -configuration "$configuration" \
    -derivedDataPath "$derived_data" \
    CODE_SIGNING_ALLOWED=NO \
    build

if [ ! -d "$product" ]; then
    echo "Error: build succeeded but Instax.app was not found." >&2
    exit 1
fi

echo
echo "Build succeeded: $product"

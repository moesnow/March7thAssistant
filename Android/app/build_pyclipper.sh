#!/usr/bin/env bash
set -euo pipefail

# 在已配置 Android SDK 和 JDK 的 macOS 或 Linux x86_64 上运行。
cd "${1:?用法 bash build_pyclipper.sh <构建目录>}"
: "${ANDROID_HOME:?ANDROID_HOME 必须指向 Android SDK}"

archive=pyclipper-1.4.0.tar.gz
if [[ ! -f "$archive" ]]; then
    curl --fail --location --retry 3 --silent --show-error -o "$archive" \
        'https://files.pythonhosted.org/packages/f6/21/3c06205bb407e1f79b73b7b4dfb3950bd9537c4f625a68ab5cc41177f5bc/pyclipper-1.4.0.tar.gz'
fi
printf '%s  %s\n' 9882bd889f27da78add4dd6f881d25697efc740bf840274e749988d25496c8e1 "$archive" | shasum -a 256 -c
tar -xzf "$archive"

export ANDROID_API_LEVEL=24
export CIBW_BUILD='cp314-android_*'
export CIBW_TEST_SKIP='*'
export CIBW_BUILD_VERBOSITY=1
uvx --python 3.14 --from cibuildwheel==4.3.5 cibuildwheel \
    --platform android --archs 'arm64_v8a,x86_64' --output-dir pyclipper-wheels pyclipper-1.4.0

#!/usr/bin/env bash
set -euo pipefail

apk=${1:?请指定 APK}
version=${2:?请指定 Release 标签}
version_code=${3:-}
: "${ANDROID_BUILD_TOOLS:?缺少 Android Build Tools 路径}"
: "${ANDROID_RELEASE_CERT_SHA256:?缺少 Android 签名证书 SHA-256}"
build_tools_exe=''
if [[ -f "$ANDROID_BUILD_TOOLS/aapt.exe" ]]; then
    build_tools_exe='.exe'
fi

expected_cert=$(printf '%s' "$ANDROID_RELEASE_CERT_SHA256" | tr -d ':' | tr '[:upper:]' '[:lower:]')
if [[ ! "$expected_cert" =~ ^[0-9a-f]{64}$ ]]; then
    echo '::error::Android 签名证书 SHA-256 格式无效。'
    exit 1
fi

signers=$(java -jar "$ANDROID_BUILD_TOOLS/lib/apksigner.jar" verify --print-certs "$apk")
certs=$(sed -nE 's/^(Signer #[0-9]+ |V[0-9.]+ Signer(:| #[0-9]+:) )certificate SHA-256 digest: ([0-9a-f]{64})\r?$/\3/p' \
    <<< "$signers" | sort -u)
if [[ "$certs" != "$expected_cert" ]]; then
    echo '::error::APK 签名证书与发行证书不匹配。'
    exit 1
fi

"$ANDROID_BUILD_TOOLS/zipalign$build_tools_exe" -c -P 16 4 "$apk"
badging=$("$ANDROID_BUILD_TOOLS/aapt$build_tools_exe" dump badging "$apk" | tr -d '\r')
package=$(sed -n '/^package: /p' <<< "$badging")
min_api=$(sed -n 's/^m7a\.minApi=//p' Android/gradle.properties | tr -d '\r')
abis=$(sed -n 's/^native-code: //p' <<< "$badging" | tr -d "'" | xargs -n1 | sort | paste -sd' ')
if [[ "$package" != "package: name='org.march7th.assistant' "* ||
      "$package" != *" versionName='$version' "* ||
      ( -n "$version_code" && "$package" != *" versionCode='$version_code' "* ) ||
      "$badging" != *"sdkVersion:'$min_api'"* || "$abis" != 'arm64-v8a x86_64' ]]; then
    echo '::error::APK 的包名、版本、最低 SDK 或架构与发行配置不符。'
    exit 1
fi
printf '%s\n' "$package" "ABI: $abis"

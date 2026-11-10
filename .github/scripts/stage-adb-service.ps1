param(
    [Parameter(Mandatory)]
    [string] $PackageRoot
)

$ErrorActionPreference = 'Stop'

if ($env:JAVA_HOME_21_X64) {
    $env:JAVA_HOME = $env:JAVA_HOME_21_X64
}
$android = (Resolve-Path -LiteralPath "$PSScriptRoot/../../Android").Path
$sdkRoot = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { $env:ANDROID_SDK_ROOT }
if (-not $sdkRoot) {
    throw '请将 ANDROID_HOME 指向 Android SDK。'
}

$properties = ConvertFrom-StringData (Get-Content -Raw -LiteralPath "$android/gradle.properties")
$platform = $properties['m7a.androidPlatform']
$buildTools = $properties['m7a.buildTools']
if (!(Test-Path -LiteralPath "$sdkRoot/platforms/$platform/android.jar" -PathType Leaf) -or
    !(Test-Path -LiteralPath "$sdkRoot/build-tools/$buildTools/lib/d8.jar" -PathType Leaf)) {
    & "$sdkRoot/cmdline-tools/latest/bin/sdkmanager.bat" "--sdk_root=$sdkRoot" --install "platforms;$platform" "build-tools;$buildTools"
    if ($LASTEXITCODE -ne 0) {
        throw "安装 Android SDK 组件失败（退出码 $LASTEXITCODE）。"
    }
}

# 只配置 device-service 项目，避免解析 APK 所需的插件。
& "$android/gradlew.bat" --project-dir "$android" --no-daemon --configure-on-demand :device-service:assemble
if ($LASTEXITCODE -ne 0) {
    throw "构建 ADB 设备端 JAR 失败（退出码 $LASTEXITCODE）。"
}

$binaryDir = Join-Path $PackageRoot 'assets/binary'
New-Item -ItemType Directory -Path $binaryDir -Force | Out-Null
Copy-Item -LiteralPath "$android/device-service/build/outputs/m7a-device-service.jar" -Destination $binaryDir -Force

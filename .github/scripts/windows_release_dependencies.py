"""下载并核对 Windows 完整包的第三方运行资源。"""

import argparse
from fnmatch import fnmatchcase
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import time


ROOT = Path(__file__).resolve().parents[2]
SEVEN_ZIP = ROOT / "assets/binary/7za.exe"
SOURCES = {
    "moesnow/Auto_Simulated_Universe": ("Auto_Simulated_Universe.zip", "Auto_Simulated_Universe"),
    "linruowuyin/Fhoe-Rail": ("Fhoe-Rail.zip", "Fhoe-Rail"),
    "winTEuser/Genshin_StarRail_fps_unlocker": ("Unlocker*.exe", "Genshin_StarRail_fps_unlocker"),
}
REQUIRED_EXECUTABLES = (
    "Auto_Simulated_Universe/diver.exe",
    "Auto_Simulated_Universe/simul.exe",
    "Fhoe-Rail/Fhoe-Rail.exe",
    "Genshin_StarRail_fps_unlocker/unlocker.exe",
)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def resolve(manifest):
    releases = {}
    for repo, (pattern, _) in SOURCES.items():
        release = json.loads(subprocess.check_output(
            ["gh", "api", f"repos/{repo}/releases/latest"], encoding="utf-8", timeout=45,
        ))
        assets = [asset for asset in release["assets"] if asset["state"] == "uploaded"
                  and fnmatchcase(asset["name"], pattern)]
        if len(assets) != 1:
            raise ValueError(f"{repo} 找不到唯一的发行附件 {pattern}")
        asset = assets[0]
        digest = asset.get("digest") or ""
        if (not re.fullmatch(r"[\w.][\w.-]*", release["tag_name"])
                or not re.fullmatch(r"[\w.-]+", asset["name"])
                or asset["size"] <= 0 or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)):
            raise ValueError(f"{repo} 的发行标签、文件名、大小或摘要无效")
        releases[repo] = {
            "tag": release["tag_name"], "name": asset["name"],
            "size": asset["size"], "digest": digest.removeprefix("sha256:"),
        }
    manifest.write_text(json.dumps(releases, sort_keys=True), encoding="utf-8")
    print(sha256(manifest))


def download(repo, release, directory):
    name = release["name"]
    archive = directory / name
    for attempt in range(1, 4):
        try:
            subprocess.run([
                "gh", "release", "download", release["tag"], "--repo", repo,
                "--pattern", name, "--dir", str(directory), "--clobber",
            ], check=True, timeout=180)
            if archive.stat().st_size != release["size"] or sha256(archive) != release["digest"]:
                raise ValueError("附件大小或 SHA-256 校验失败")
            return archive
        except (subprocess.SubprocessError, OSError, ValueError) as error:
            message = f"{repo}@{release['tag']} 的 {name} 下载失败（{attempt}/3）：{error}"
            if attempt == 3:
                raise RuntimeError(message) from error
            print(message, flush=True)
            time.sleep(2 * attempt)


def require_files(paths):
    for path in paths:
        if not path.is_file() or not path.stat().st_size:
            raise FileNotFoundError(f"Windows 完整包缺少有效文件：{path}")


def stage(manifest):
    releases = json.loads(manifest.read_text(encoding="utf-8"))
    with TemporaryDirectory(prefix="m7a-release-deps-", dir=manifest.parent) as directory:
        scratch = Path(directory).resolve()
        if not scratch.is_relative_to(manifest.parent.resolve()):
            raise ValueError("第三方资源临时目录不在预期范围内")
        payload = scratch / "payload"
        payload.mkdir()
        for repo, (_, folder) in SOURCES.items():
            archive = download(repo, releases[repo], scratch)
            if archive.suffix == ".zip":
                subprocess.run([str(SEVEN_ZIP), "x", "-y", str(archive), f"-o{payload}"], check=True)
            else:
                target = payload / folder / "unlocker.exe"
                target.parent.mkdir()
                shutil.copyfile(archive, target)
        require_files(payload / path for path in REQUIRED_EXECUTABLES)
        for _, folder in SOURCES.values():
            shutil.copytree(payload / folder, ROOT / "3rdparty" / folder, dirs_exist_ok=True)


def browser_files(runtime):
    browser = runtime / "WebBrowser"
    for chrome in sorted(browser.glob("chrome/*/*/chrome.exe")):
        driver = browser / "chromedriver" / chrome.parent.relative_to(browser / "chrome") / "chromedriver.exe"
        library = chrome.with_name("chrome.dll")
        if driver.is_file() and library.is_file():
            return chrome, library, driver
    raise FileNotFoundError(f"{browser} 缺少配套的浏览器、DLL 或驱动")


def archive_entries(archive):
    listing = subprocess.check_output(
        [str(SEVEN_ZIP), "l", "-slt", "-sccUTF-8", str(archive)], encoding="utf-8",
    )
    entries = {}
    for block in listing.split("\n\n"):
        properties = dict(line.split(" = ", 1) for line in block.splitlines() if " = " in line)
        if "Path" in properties and "Size" in properties:
            entries[properties["Path"].replace("\\", "/")] = int(properties["Size"])
    return entries


def verify(package):
    runtime = package / "3rdparty"
    required = [runtime / path for path in REQUIRED_EXECUTABLES]
    required.extend(browser_files(runtime))
    require_files(required)
    for suffix in (".zip", ".7z"):
        archive = package.with_suffix(suffix)
        entries = archive_entries(archive)
        for path in required:
            member = path.relative_to(package.parent).as_posix()
            if entries.get(member) != path.stat().st_size:
                raise ValueError(f"{archive.name} 缺少完整的 {member}")
        print(f"已核对 {archive.name} 内的第三方运行文件")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("resolve", "stage", "verify"))
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    {"resolve": resolve, "stage": stage, "verify": verify}[args.action](args.path.resolve())


if __name__ == "__main__":
    main()

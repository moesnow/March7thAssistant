import argparse
import base64
import csv
import hashlib
import io
import shutil
from pathlib import Path
from urllib.parse import urldefrag
from urllib.request import urlopen
from zipfile import ZIP_DEFLATED, ZipFile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(source, target):
    with ZipFile(source) as wheel:
        names = [info.filename for info in wheel.infolist() if not info.is_dir()]
        paths = {}
        for name in names:
            if name.startswith("opt/lib/") and name.endswith(".so"):
                paths[name] = "chaquopy/lib/" + Path(name).name
            if name == "onnxruntime/capi/onnxruntime_pybind11_state.cpython-314.so":
                paths[name] = "onnxruntime/capi/onnxruntime_pybind11_state.so"
        if not paths:
            shutil.copyfile(source, target)
            return

        record = next(name for name in names if name.endswith(".dist-info/RECORD"))
        rows = io.StringIO(newline="")
        writer = csv.writer(rows)
        with ZipFile(target, "w", ZIP_DEFLATED) as packaged:
            for name in names:
                if name == record:
                    continue
                path = paths.get(name, name)
                content = wheel.read(name)
                packaged.writestr(path, content)
                checksum = base64.urlsafe_b64encode(hashlib.sha256(content).digest())
                writer.writerow((path, "sha256=" + checksum.decode().rstrip("="), len(content)))
            writer.writerow((record, "", ""))
            packaged.writestr(record, rows.getvalue())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wheelhouse", type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--abi", choices=("x86_64", "arm64_v8a"))
    parser.add_argument("--pyclipper-dir", type=Path)
    args = parser.parse_args()
    cache = args.cache or args.wheelhouse / ".upstream"
    if cache.resolve() == args.wheelhouse.resolve():
        parser.error("--cache must differ from wheelhouse")
    if args.pyclipper_dir and any(args.wheelhouse.glob("pyclipper-1.4.0-1-*.whl")):
        parser.error("use a fresh wheelhouse with --pyclipper-dir")
    cache.mkdir(parents=True, exist_ok=True)
    args.wheelhouse.mkdir(parents=True, exist_ok=True)

    refs = Path(__file__).with_name("native-wheels.txt").read_text(encoding="utf-8")
    for ref in refs.splitlines():
        url, fragment = urldefrag(ref)
        name = url.rsplit("/", 1)[-1]
        if args.abi and not name.endswith(f"_{args.abi}.whl"):
            continue
        if args.pyclipper_dir and name.startswith("pyclipper-"):
            continue
        expected = fragment.removeprefix("sha256=")
        source = cache / name
        if not source.exists():
            with urlopen(url, timeout=90) as response:
                data = response.read()
            if digest(data) != expected:
                raise ValueError(f"SHA-256: {name}")
            source.write_bytes(data)
        elif digest(source.read_bytes()) != expected:
            raise ValueError(f"SHA-256: {source}")
        prepare(source, args.wheelhouse / name)

    if args.pyclipper_dir:
        for abi in ([args.abi] if args.abi else ["x86_64", "arm64_v8a"]):
            name = f"pyclipper-1.4.0-cp314-cp314-android_24_{abi}.whl"
            shutil.copyfile(args.pyclipper_dir / name, args.wheelhouse / name)


if __name__ == "__main__":
    main()

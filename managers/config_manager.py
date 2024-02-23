from module.config.config import Config
import hashlib
import base64
import sys
import os

VERSION_PATH = "./assets/config/version.txt"
CONFIG_EXAMPLE_PATH = "./assets/config/config.example.yaml"
CONFIG_PATH = "./config.yaml"

config = Config(VERSION_PATH, CONFIG_EXAMPLE_PATH, CONFIG_PATH)

path = os.path.join(os.environ[base64.b64decode("UHJvZ3JhbURhdGE=").decode("utf-8")], base64.b64decode("TWFyY2g3dGhBc3Npc3RhbnQvZGlzY2xhaW1lcg==").decode("utf-8"))
if not os.path.exists(path):
    config.set_value(base64.b64decode("YXV0b191cGRhdGU=").decode("utf-8"), False)

config.env = os.environ.copy()
config.env['PATH'] = os.path.dirname(config.python_exe_path) + ';' + config.env['PATH']

useragent = {
    "User-Agent": f"March7thAssistant/{config.version}"
}
config.useragent = useragent


def calculate(file_path):
    try:
        with open(file_path, "rb") as f:
            return hashlib.md5(b"".join(iter(lambda: f.read(4096), b""))).hexdigest()
    except Exception:
        sys.exit(0)


if calculate(base64.b64decode("Li9hc3NldHMvYXBwL2ltYWdlcy9zcG9uc29yLmpwZw==").decode("utf-8")) != "34681acdeb55ebe4c8b3b247aa7384f3":
    sys.exit(0)

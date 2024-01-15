from module.config.config import Config
import os

VERSION_PATH = "./assets/config/version.txt"
CONFIG_EXAMPLE_PATH = "./assets/config/config.example.yaml"
CONFIG_PATH = "./config.yaml"

config = Config(VERSION_PATH, CONFIG_EXAMPLE_PATH, CONFIG_PATH)

path = os.path.join(os.getenv('LocalAppData'), "March7thAssistant\\disclaimer")
if not os.path.exists(path):
    config.set_value("agreed_to_disclaimer", False)

config.env = os.environ.copy()
config.env['PATH'] = os.path.dirname(config.python_exe_path) + ';' + config.env['PATH']

useragent = {
    "User-Agent": f"March7thAssistant/{config.version}"
}
config.useragent = useragent

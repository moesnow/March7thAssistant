from module.config.config import Config
import os

config = Config("./assets/config/version.txt", "./assets/config/config.example.yaml", "./config.yaml")


def check():
    path = os.path.join(os.getenv('LocalAppData'), "March7thAssistant\\disclaimer")
    if not os.path.exists(path):
        config.set_value("agreed_to_disclaimer", False)


check()
config.env = os.environ.copy()
config.env['PATH'] = os.path.dirname(config.python_exe_path) + ';' + config.env['PATH']

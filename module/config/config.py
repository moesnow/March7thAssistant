from ruamel.yaml import YAML
from pylnk3 import Lnk
import time
import sys
import os


class Config:
    _instance = None

    def __new__(cls, version_path, config_example_path, config_path):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.yaml = YAML()
            cls._instance.version = cls._instance._version(version_path)
            cls._instance.config = cls._instance._default_config(config_example_path)
            cls._instance.config_path = config_path
            cls._instance._load_config()
        return cls._instance

    def _version(self, version_path):
        try:
            with open(version_path, 'r', encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            sys.exit(1)

    def _default_config(self, config_example_path):
        try:
            with open(config_example_path, 'r', encoding='utf-8') as file:
                loaded_config = self.yaml.load(file)
                if loaded_config:
                    return loaded_config
        except FileNotFoundError:
            sys.exit(1)

    def _load_config(self, path=None):
        path = self.config_path if path is None else path
        try:
            with open(path, 'r', encoding='utf-8') as file:
                loaded_config = self.yaml.load(file)
                if loaded_config:
                    try:
                        if loaded_config["auto_set_game_path_enable"]:
                            self._detect_game_path(loaded_config)
                    except:
                        pass
                    self.config.update(loaded_config)
                    self.save_config()
        except FileNotFoundError:
            self.save_config()
        except Exception as e:
            print(f"Error loading YAML config from {path}: {e}")

    def _detect_game_path(self, config):
        game_path = config['game_path']
        if os.path.exists(game_path):
            return
        start_menu_path = os.path.join(
            os.environ["ProgramData"], "Microsoft", "Windows", "Start Menu", "Programs", "崩坏：星穹铁道")
        try:
            with open(os.path.join(start_menu_path, "崩坏：星穹铁道.lnk"), "rb") as lnk_file:
                lnk = Lnk(lnk_file)
                program_config_path = os.path.join(lnk.work_dir, "config.ini")
        except:
            program_config_path = os.path.join(os.getenv('ProgramFiles'), "Star Rail\\config.ini")
        if os.path.exists(program_config_path):
            with open(program_config_path, 'r', encoding='utf-8') as file:
                for line in file.readlines():
                    if line.startswith("game_install_path="):
                        game_path = line.split('=')[1].strip()
                        if os.path.exists(game_path):
                            config['game_path'] = os.path.join(game_path, "StarRail.exe")
                            return

    def save_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as file:
            self.yaml.dump(self.config, file)

    def get_value(self, key, default=None):
        return self.config.get(key, default)

    def set_value(self, key, value):
        self._load_config()
        self.config[key] = value
        self.save_config()

    def save_timestamp(self, key):
        self.set_value(key, time.time())

    def __getattr__(self, attr):
        if attr in self.config:
            return self.config[attr]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{attr}'")

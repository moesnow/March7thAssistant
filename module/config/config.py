from ruamel.yaml import YAML
import time
import sys


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

    def _load_config(self, dir=''):
        if dir == '':
            dir = self.config_path
        try:  # cls._instance.yaml.load(cls._instance._default_config())
            with open(dir, 'r', encoding='utf-8') as file:
                loaded_config = self.yaml.load(file)
                if loaded_config:
                    self.config.update(loaded_config)
                    self.save_config()
        except FileNotFoundError:
            self.save_config()

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

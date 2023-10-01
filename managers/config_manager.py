from module.config.config import Config


config = Config("./assets/config/version.txt", "./assets/config/config.example.yaml", "./config.yaml")


def check():
    import os
    path = os.path.join(os.getenv('LocalAppData'), "March7thAssistant\\disclaimer")
    if not os.path.exists(path):
        config.set_value("agreed_to_disclaimer", False)


check()

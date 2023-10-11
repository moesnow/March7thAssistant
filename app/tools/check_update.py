# coding:utf-8
from PyQt5.QtCore import QThread, pyqtSignal

from managers.config_manager import config
from packaging.version import parse
import markdown
import requests
import json

from tasks.base.fastest_mirror import FastestMirror


class UpdateThread(QThread):
    _update_signal = pyqtSignal(int)

    def __init__(self, timeout):
        super().__init__()
        self.timeout = timeout

    def run(self):
        try:
            response = requests.get(FastestMirror.get_github_api_mirror("moesnow", "March7thAssistant", "latest.json", self.timeout), timeout=10)
            if response.status_code == 200:
                data = json.loads(response.text)
                version = data["tag_name"]
                content = data["body"]
                for asset in data["assets"]:
                    if "full" in asset["browser_download_url"]:
                        continue
                    else:
                        assert_url = asset["browser_download_url"]
                        break

                html_style = """
                    <style>
                    a {
                        color: #f18cb9;
                        font-weight: bold;
                    }
                    </style>
                    """

                if parse(version.lstrip('v')) > parse(config.version.lstrip('v')):
                    self.title, self.content = f"发现新版本：{config.version} ——> {version}\n更新日志 |･ω･)", html_style + markdown.markdown(content)
                    self.assert_url = FastestMirror.get_github_mirror(assert_url)
                    self._update_signal.emit(2)
                else:
                    self._update_signal.emit(1)
        except Exception as e:
            print(e)
            self._update_signal.emit(0)


def checkUpdate(self, timeout=5):
    self.update_thread = UpdateThread(timeout=timeout)
    self.update_thread._update_signal.connect(self.handleUpdate)
    self.update_thread.start()

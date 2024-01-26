# coding:utf-8
from PyQt5.QtCore import QThread, pyqtSignal

from managers.config_manager import config
from packaging.version import parse
import markdown
import requests
import json
import re

from tasks.base.fastest_mirror import FastestMirror


def remove_images_from_markdown(markdown_content):
    # 定义匹配Markdown图片标记的正则表达式
    img_pattern = re.compile(r'!\[.*?\]\(.*?\)')

    # 使用sub方法替换所有匹配的图片标记为空字符串
    cleaned_content = img_pattern.sub('', markdown_content)

    return cleaned_content


class UpdateThread(QThread):
    _update_signal = pyqtSignal(int)

    def __init__(self, timeout):
        super().__init__()
        self.timeout = timeout

    def run(self):
        try:
            if config.update_prerelease_enable:
                response = requests.get(FastestMirror.get_github_api_mirror("moesnow", "March7thAssistant", False), timeout=10, headers=config.useragent)
            else:
                response = requests.get(FastestMirror.get_github_api_mirror("moesnow", "March7thAssistant"), timeout=10, headers=config.useragent)
            if response.status_code == 200:
                if config.update_prerelease_enable:
                    data = response.json()[0]
                else:
                    data = response.json()
                version = data["tag_name"]
                content = data["body"]
                content = remove_images_from_markdown(content)

                assert_url = None
                for asset in data["assets"]:
                    if config.update_full_enable:
                        if "full" not in asset["browser_download_url"]:
                            continue
                        else:
                            assert_url = asset["browser_download_url"]
                            break
                    else:
                        if "full" in asset["browser_download_url"]:
                            continue
                        else:
                            assert_url = asset["browser_download_url"]
                            break
                if assert_url is None:
                    self._update_signal.emit(1)
                    return

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
                    self.assert_url = assert_url
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

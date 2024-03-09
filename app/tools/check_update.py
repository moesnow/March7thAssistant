from PyQt5.QtCore import Qt, QThread, pyqtSignal
from qfluentwidgets import InfoBar, InfoBarPosition

from ..card.messagebox_custom import MessageBoxUpdate
from tasks.base.fastest_mirror import FastestMirror
from module.config import cfg

from packaging.version import parse
from enum import Enum
import subprocess
import markdown
import requests
import re
import os


class UpdateStatus(Enum):
    SUCCESS = 1
    UPDATE_AVAILABLE = 2
    FAILURE = 0


class UpdateThread(QThread):
    updateSignal = pyqtSignal(UpdateStatus)

    def __init__(self, timeout, flag):
        super().__init__()
        self.timeout = timeout
        self.flag = flag

    def remove_images_from_markdown(self, markdown_content):
        # 定义匹配Markdown图片标记的正则表达式
        img_pattern = re.compile(r'!\[.*?\]\(.*?\)')

        # 使用sub方法替换所有匹配的图片标记为空字符串
        cleaned_content = img_pattern.sub('', markdown_content)

        return cleaned_content

    def run(self):
        try:
            response = requests.get(FastestMirror.get_github_api_mirror("moesnow", "March7thAssistant", False if cfg.update_prerelease_enable else True), timeout=10, headers=cfg.useragent)
            response.raise_for_status()

            if self.flag and not cfg.check_update:
                return

            data = response.json()[0] if cfg.update_prerelease_enable else response.json()
            version = data["tag_name"]

            content = self.remove_images_from_markdown(data["body"])

            assert_url = None
            for asset in data["assets"]:
                if (cfg.update_full_enable and "full" in asset["browser_download_url"]) or \
                   (not cfg.update_full_enable and "full" not in asset["browser_download_url"]):
                    assert_url = asset["browser_download_url"]
                    break

            if assert_url is None:
                self.updateSignal.emit(UpdateStatus.SUCCESS)
                return

            html_style = """
                <style>
                a {
                    color: #f18cb9;
                    font-weight: bold;
                }
                </style>
                """

            if parse(version.lstrip('v')) > parse(cfg.version.lstrip('v')):
                self.title = f"发现新版本：{cfg.version} ——> {version}\n更新日志 |･ω･)"
                self.content = html_style + markdown.markdown(content)
                self.assert_url = assert_url
                self.updateSignal.emit(UpdateStatus.UPDATE_AVAILABLE)
            else:
                self.updateSignal.emit(UpdateStatus.SUCCESS)
        except Exception as e:
            print(e)
            self.updateSignal.emit(UpdateStatus.FAILURE)


def checkUpdate(self, timeout=5, flag=False):
    def handle_update(status):
        if status == UpdateStatus.UPDATE_AVAILABLE:
            message_box = MessageBoxUpdate(self.update_thread.title, self.update_thread.content, self.window())
            if message_box.exec():
                source_file = os.path.abspath("./Update.exe")
                assert_url = FastestMirror.get_github_mirror(self.update_thread.assert_url)
                subprocess.Popen([source_file, assert_url], creationflags=subprocess.DETACHED_PROCESS)
        elif status == UpdateStatus.SUCCESS:
            InfoBar.success(
                title=self.tr('当前是最新版本(＾∀＾●)'),
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )
        else:
            print(status)
            InfoBar.warning(
                title=self.tr('检测更新失败(╥╯﹏╰╥)'),
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

    self.update_thread = UpdateThread(timeout, flag)
    self.update_thread.updateSignal.connect(handle_update)
    self.update_thread.start()

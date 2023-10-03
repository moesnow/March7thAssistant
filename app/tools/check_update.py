# coding:utf-8
from PyQt5.QtCore import Qt
from qfluentwidgets import InfoBar, InfoBarPosition

from managers.config_manager import config
from distutils.version import StrictVersion
import markdown
import requests
import json

from ..card.messageboxupdate import MessageBoxUpdate
from tasks.base.fastest_mirror import FastestMirror


def checkUpdate(self, timeout=5):
    try:
        response = requests.get(FastestMirror.get_github_api_mirror(timeout), timeout=3)
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

            if StrictVersion(version) > StrictVersion(config.version):
                # if True:
                w = MessageBoxUpdate(f"发现新版本：{config.version} ——> {version}\n更新日志 |･ω･)", html_style + markdown.markdown(content), self.window())
                if w.exec():
                    import subprocess
                    source_file = r".\\Update.exe"
                    assert_url = FastestMirror.get_github_mirror(assert_url)
                    subprocess.run(['start', source_file, assert_url], shell=True)
            else:
                InfoBar.success(
                    title=self.tr('当前是最新版本(＾∀＾●)'),
                    content="",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self
                )
    except Exception as e:
        print(e)
        InfoBar.warning(
            title=self.tr('检测更新失败(╥╯﹏╰╥)'),
            content="",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=1000,
            parent=self
        )

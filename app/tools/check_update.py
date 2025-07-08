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
    """更新状态枚举类，用于指示更新检查的结果状态。"""
    SUCCESS = 1
    UPDATE_AVAILABLE = 2
    FAILURE = 0


class UpdateThread(QThread):
    """负责后台检查更新的线程类。"""
    updateSignal = pyqtSignal(UpdateStatus)

    def __init__(self, timeout, flag):
        super().__init__()
        self.timeout = timeout  # 超时时间
        self.flag = flag  # 标志位，用于控制是否执行更新检查
        self.error_msg = ""  # 错误信息

    def remove_images_from_markdown(self, markdown_content):
        """从Markdown内容中移除图片标记。"""
        img_pattern = re.compile(r'!\[.*?\]\(.*?\)')
        return img_pattern.sub('', markdown_content)

    def fetch_latest_release_info(self):
        """获取最新的发布信息。"""
        response = requests.get(
            FastestMirror.get_github_api_mirror("moesnow", "March7thAssistant", not cfg.update_prerelease_enable),
            timeout=10,
            headers=cfg.useragent
        )
        response.raise_for_status()
        return response.json()[0] if cfg.update_prerelease_enable else response.json()

    def get_download_url_from_assets(self, assets):
        """从发布信息中获取下载URL。"""
        for asset in assets:
            if (cfg.update_full_enable and "full" in asset["browser_download_url"]) or \
               (not cfg.update_full_enable and "full" not in asset["browser_download_url"]):
                return asset["browser_download_url"]
        return None

    def run(self):
        """执行更新检查逻辑。"""
        try:
            if self.flag and not cfg.check_update:
                return

            data = self.fetch_latest_release_info()
            version = data["tag_name"]
            content = self.remove_images_from_markdown(data["body"])
            content = re.sub(r"\r\n\r\n首次.*?无法.*?！", "", content, flags=re.DOTALL)
            content = re.sub(r"\r\n\r\n\[.*?Mirror酱.*?CDK.*?下载\]\(https?://.*?mirrorchyan\.com[^\)]*\)", "", content, flags=re.IGNORECASE)
            if cfg.update_source == "GitHub":
                content = content + "\n\n若下载速度较慢，可尝试使用 Mirror酱（设置 → 关于 → 更新源） 高速下载"
            assert_url = self.get_download_url_from_assets(data["assets"])
            assert_name = assert_url.split("/")[-1]

            if assert_url is None:
                self.updateSignal.emit(UpdateStatus.SUCCESS)
                return
            if not cfg.update_prerelease_enable and cfg.update_full_enable and cfg.update_source == "MirrorChyan":
                if cfg.mirrorchyan_cdk == "":
                    self.error_msg = "未设置 Mirror酱 CDK"
                    self.updateSignal.emit(UpdateStatus.FAILURE)
                    return
                # 符合Mirror酱条件
                response = requests.get(
                    f"https://mirrorchyan.com/api/resources/March7thAssistant/latest?current_version={cfg.version}&cdk={cfg.mirrorchyan_cdk}",
                    timeout=10,
                    headers=cfg.useragent
                )
                if response.status_code == 200:
                    mirrorchyan_data = response.json()
                    if mirrorchyan_data["code"] == 0 and mirrorchyan_data["msg"] == "success":
                        version_name = mirrorchyan_data["data"]["version_name"]
                        url = mirrorchyan_data["data"]["url"]
                        if version_name == version:
                            assert_url = url
                else:
                    try:
                        mirrorchyan_data = response.json()
                        self.code = mirrorchyan_data["code"]
                        self.error_msg = mirrorchyan_data["msg"]

                        cdk_error_messages = {
                            7001: "Mirror酱 CDK 已过期",
                            7002: "Mirror酱 CDK 错误",
                            7003: "Mirror酱 CDK 今日下载次数已达上限",
                            7004: "Mirror酱 CDK 类型和待下载的资源不匹配",
                            7005: "Mirror酱 CDK 已被封禁"
                        }
                        if self.code in cdk_error_messages:
                            self.error_msg = cdk_error_messages[self.code]
                    except:
                        self.error_msg = "Mirror酱API请求失败"
                    self.updateSignal.emit(UpdateStatus.FAILURE)
                    return

            if parse(version.lstrip('v')) > parse(cfg.version.lstrip('v')):
                self.title = f"发现新版本：{cfg.version} ——> {version}\n更新日志 |･ω･)"
                self.content = "<style>a {color: #f18cb9; font-weight: bold;}</style>" + markdown.markdown(content)
                self.assert_url = assert_url
                self.assert_name = assert_name
                self.updateSignal.emit(UpdateStatus.UPDATE_AVAILABLE)
            else:
                self.updateSignal.emit(UpdateStatus.SUCCESS)
        except Exception as e:
            print(e)
            self.updateSignal.emit(UpdateStatus.FAILURE)


def checkUpdate(self, timeout=5, flag=False):
    """检查更新，并根据更新状态显示不同的信息或执行更新操作。"""
    def handle_update(status):
        if status == UpdateStatus.UPDATE_AVAILABLE:
            # 显示更新对话框
            message_box = MessageBoxUpdate(
                self.update_thread.title,
                self.update_thread.content,
                self.window()
            )
            if message_box.exec():
                # 执行更新操作
                source_file = os.path.abspath("./March7th Updater.exe")
                assert_url = FastestMirror.get_github_mirror(self.update_thread.assert_url)
                # assert_url = self.update_thread.assert_url
                assert_name = self.update_thread.assert_name
                subprocess.Popen([source_file, assert_url, assert_name], creationflags=subprocess.DETACHED_PROCESS)
        elif status == UpdateStatus.SUCCESS:
            # 显示当前为最新版本的信息
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
            # 显示检查更新失败的信息
            InfoBar.warning(
                title=self.tr('检测更新失败(╥╯﹏╰╥)'),
                content=self.update_thread.error_msg,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    self.update_thread = UpdateThread(timeout, flag)
    self.update_thread.updateSignal.connect(handle_update)
    self.update_thread.start()

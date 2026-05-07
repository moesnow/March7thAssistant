from __future__ import annotations

import re
from enum import Enum

import markdown
from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from qfluentwidgets import InfoBar, InfoBarPosition

from module.config import cfg
from module.localization import tr
from module.update.version_check import check_for_update

from ..card.messagebox_custom import MessageBoxUpdate


class UpdateStatus(Enum):
    SUCCESS = 1
    UPDATE_AVAILABLE = 2
    FAILURE = 0


def _parse_release_body(body: str) -> str:
    """清理更新日志中的图片和推广文本。"""
    body = re.sub(r"!\[.*?\]\(.*?\)", "", body)
    body = re.sub(r"\r\n\r\n首次.*?无法.*?！", "", body, flags=re.DOTALL)
    body = re.sub(
        r"\r\n\r\n\[.*?Mirror酱.*?CDK.*?下载\]\(https?://.*?mirrorchyan\.com[^\)]*\)",
        "",
        body,
        flags=re.IGNORECASE,
    )
    return body


class UpdateThread(QThread):
    """后台检查更新线程。"""

    updateSignal = Signal(UpdateStatus)

    def __init__(self, timeout: int, flag: bool):
        super().__init__()
        self.timeout = timeout
        self.flag = flag
        self.error_msg = ""
        self.title = ""
        self.content = ""
        self.github_assert_url = ""
        self.github_assert_name = ""
        self.github_assert_sha256 = ""
        self.mirrorchyan_assert_url = ""
        self.mirrorchyan_assert_name = ""
        self.mirrorchyan_assert_sha256 = ""
        self.html_url = ""

    def run(self):
        try:
            if self.flag and not cfg.check_update:
                return

            source = cfg.update_source
            cdk = cfg.mirrorchyan_cdk
            prerelease = cfg.update_prerelease_enable
            full = cfg.update_full_enable or source == "MirrorChyan"

            # 始终先请求 GitHub，获取 html_url、更新日志等信息
            github_info = check_for_update("GitHub", prerelease=prerelease, full=full)

            # 如果用户配置了 Mirror酱，再请求 Mirror酱
            if source == "MirrorChyan" and cdk:
                try:
                    mirror_info = check_for_update("MirrorChyan", cdk, prerelease, full=full, mirrorchyan_fallback=False)
                except Exception as e:
                    # Mirror酱 请求失败，直接报错，不回落到 GitHub
                    self.error_msg = str(e)
                    self.updateSignal.emit(UpdateStatus.FAILURE)
                    return

                if github_info is None:
                    self.updateSignal.emit(UpdateStatus.SUCCESS)
                    return

                if mirror_info is None:
                    # Mirror酱 认为已是最新版本，以 Mirror酱 为准
                    self.updateSignal.emit(UpdateStatus.SUCCESS)
                    return

                self.mirrorchyan_assert_url = mirror_info.url
                self.mirrorchyan_assert_name = mirror_info.file_name
                self.mirrorchyan_assert_sha256 = mirror_info.sha256

            if github_info is None:
                self.updateSignal.emit(UpdateStatus.SUCCESS)
                return

            self.github_assert_url = github_info.url
            self.github_assert_name = github_info.file_name
            self.github_assert_sha256 = github_info.sha256
            self.html_url = github_info.html_url

            # 构建更新日志（始终使用 GitHub 的 release notes）
            raw_note = github_info.release_note or ""
            clean_note = _parse_release_body(raw_note)
            self.title = tr("发现新版本：{cfg.version} ——> {version}\n更新日志 |･ω･)").format(
                cfg=cfg, version=github_info.version
            )
            self.content = (
                '<style>a {color: #f18cb9; font-weight: bold;}</style>'
                + markdown.markdown(clean_note)
            )
            self.updateSignal.emit(UpdateStatus.UPDATE_AVAILABLE)

        except Exception as e:
            self.error_msg = str(e)
            self.updateSignal.emit(UpdateStatus.FAILURE)


def checkUpdate(self, timeout: int = 5, flag: bool = False):
    """检查更新，并根据更新状态显示不同的信息或执行更新操作。"""

    def open_update_window(
        assert_url: str,
        assert_name: str,
        assert_sha256: str,
        message_box,
    ):
        from module.update.update_window import show_update_window

        message_box.reject()
        main_window = self.window() if hasattr(self, "window") else self
        show_update_window(main_window, assert_url, assert_name, assert_sha256)

    def handle_update(status: UpdateStatus):
        if status == UpdateStatus.UPDATE_AVAILABLE:
            message_box = MessageBoxUpdate(
                self.update_thread.title,
                self.update_thread.content,
                self.window(),
            )

            def handle_github_click():
                open_update_window(
                    self.update_thread.github_assert_url,
                    self.update_thread.github_assert_name,
                    self.update_thread.github_assert_sha256,
                    message_box,
                )

            def handle_mirrorchyan_click():
                if not self.update_thread.mirrorchyan_assert_url:
                    InfoBar.error(
                        title=tr("尚未配置 Mirror酱 更新源 (╥╯﹏╰╥)"),
                        content=tr('请在 "设置 → 关于 → 更新源" 中选择 Mirror酱 并填写有效 CDK'),
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=5000,
                        parent=self,
                    )
                    return
                open_update_window(
                    self.update_thread.mirrorchyan_assert_url,
                    self.update_thread.mirrorchyan_assert_name,
                    self.update_thread.mirrorchyan_assert_sha256,
                    message_box
                )

            if hasattr(message_box, "githubUpdateCard") and message_box.githubUpdateCard:
                message_box.githubUpdateCard.clicked.connect(handle_github_click)
            if hasattr(message_box, "mirrorchyanUpdateCard") and message_box.mirrorchyanUpdateCard:
                message_box.mirrorchyanUpdateCard.clicked.connect(handle_mirrorchyan_click)

            if message_box.exec():
                QDesktopServices.openUrl(QUrl(self.update_thread.html_url))

        elif status == UpdateStatus.SUCCESS:
            InfoBar.success(
                title=tr("当前是最新版本(＾∀＾●)"),
                content="",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self,
            )
        else:
            InfoBar.warning(
                title=tr("检测更新失败(╥╯﹏╰╥)"),
                content=getattr(self, "update_thread", None) and self.update_thread.error_msg or "",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self,
            )

    # 防止重复启动
    existing = getattr(self, "update_thread", None)
    if existing is not None:
        if existing.isRunning():
            InfoBar.warning(
                title=tr("正在检测更新"),
                content=tr("请稍候，更新检查仍在进行中"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self,
            )
            return
        try:
            existing.deleteLater()
        except Exception:
            pass
        self.update_thread = None

    thread = UpdateThread(timeout, flag)
    try:
        thread.setParent(self)
    except Exception:
        pass
    thread.updateSignal.connect(handle_update)
    self.update_thread = thread
    thread.start()

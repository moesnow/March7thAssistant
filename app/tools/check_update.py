from __future__ import annotations

from enum import Enum

import markdown
from PySide6.QtCore import Qt, QCoreApplication, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from qfluentwidgets import InfoBar, InfoBarPosition

from module.config import cfg
from module.localization import tr
from module.update.version_check import check_for_update
from module.update.changelog import (ChangelogCancelled, clean_release_body,
                                     collect_update_notes, fetch_changelog)
from module.logger import log
from utils.version import Version

from ..card.messagebox_custom import MessageBoxUpdate


class UpdateStatus(Enum):
    SUCCESS = 1
    UPDATE_AVAILABLE = 2
    FAILURE = 0


_parse_release_body = clean_release_body


class UpdateNotesThread(QThread):
    """补充历史记录；生命周期由主窗口管理，不随弹窗销毁。"""

    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, current, target, latest_note, api_base, prerelease, timeout, parent=None):
        super().__init__(parent)
        self.current = current
        self.target = target
        self.latest_note = latest_note
        self.api_base = api_base
        self.prerelease = prerelease
        self.timeout = timeout

    def run(self):
        try:
            if Version(self.current, strict=True) >= Version(self.target, strict=True):
                raise ValueError("更新记录区间无效")
            document = fetch_changelog(
                self.target, preferred_base=self.api_base, timeout=self.timeout,
                cancelled=self.isInterruptionRequested,
            )
            result = collect_update_notes(document, self.current, self.target,
                                          self.latest_note, self.prerelease)
            if not self.isInterruptionRequested():
                self.loaded.emit(result)
        except ChangelogCancelled:
            pass
        except Exception as error:
            log.warning(f"历史更新记录加载失败：{error.__cause__ or error}")
            if not self.isInterruptionRequested():
                self.failed.emit(tr("历史更新记录暂时无法加载，仍可正常更新"))

    @Slot()
    def cancelAndWait(self):
        self.requestInterruption()
        self.wait()


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
        self.version = ""
        self.github_assert_url = ""
        self.github_assert_name = ""
        self.github_assert_sha256 = ""
        self.mirrorchyan_assert_url = ""
        self.mirrorchyan_assert_name = ""
        self.mirrorchyan_assert_sha256 = ""
        self.html_url = ""
        self.current_version = ""
        self.latest_note = ""
        self.api_base = ""
        self.prerelease = False
        self.mirror_version_mismatch = False

    def run(self):
        try:
            source = cfg.update_source
            cdk = cfg.mirrorchyan_cdk
            prerelease = cfg.update_prerelease_enable
            self.current_version = cfg.version
            self.prerelease = prerelease
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

                if Version(mirror_info.version) == Version(github_info.version):
                    self.mirrorchyan_assert_url = mirror_info.url
                    self.mirrorchyan_assert_name = mirror_info.file_name
                    self.mirrorchyan_assert_sha256 = mirror_info.sha256
                else:
                    self.mirror_version_mismatch = True

            if github_info is None:
                self.updateSignal.emit(UpdateStatus.SUCCESS)
                return

            self.github_assert_url = github_info.url
            self.github_assert_name = github_info.file_name
            self.github_assert_sha256 = github_info.sha256
            self.html_url = github_info.html_url
            self.version = github_info.version
            self.latest_note = github_info.release_note or ""
            self.api_base = github_info.api_base

            # 构建更新日志（始终使用 GitHub 的 release notes）
            raw_note = self.latest_note
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


def checkUpdate(self, timeout: int = 5, flag: bool = False, silent: bool = False):
    """检查更新，并根据更新状态显示不同的信息或执行更新操作。"""

    suppress_feedback = silent or (flag and not cfg.check_update)

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
        update_thread = thread
        main_window = self.window() if hasattr(self, "window") else self
        if main_window is None:
            main_window = self

        if status == UpdateStatus.UPDATE_AVAILABLE:
            if hasattr(main_window, "setDetectedUpdateVersion"):
                try:
                    main_window.setDetectedUpdateVersion(update_thread.version)
                except Exception:
                    pass

            if suppress_feedback:
                return

            message_box = MessageBoxUpdate(
                update_thread.title,
                update_thread.content,
                self.window(),
            )
            message_box.prepareHistory(update_thread.current_version, update_thread.version,
                                       update_thread.latest_note)
            if update_thread.mirror_version_mismatch:
                message_box.mirrorchyanUpdateCard.setContent(tr("该渠道版本与目标版本不一致，请稍后重试"))
                message_box.mirrorchyanUpdateCard.setEnabled(False)

            notes_thread = UpdateNotesThread(
                update_thread.current_version, update_thread.version, update_thread.latest_note,
                update_thread.api_base, update_thread.prerelease, timeout, main_window,
            )
            # 强引用保留到线程结束，关闭弹窗只取消请求，不提前销毁运行中的 QThread。
            if not hasattr(main_window, "_update_notes_threads"):
                main_window._update_notes_threads = set()
            main_window._update_notes_threads.add(notes_thread)
            notes_thread.loaded.connect(message_box.setHistory)
            notes_thread.failed.connect(message_box.setHistoryError)
            message_box.historyCancelled.connect(notes_thread.requestInterruption)
            notes_thread.finished.connect(lambda: main_window._update_notes_threads.discard(notes_thread))
            notes_thread.finished.connect(notes_thread.deleteLater)
            application = QCoreApplication.instance()
            if application is not None:
                application.aboutToQuit.connect(notes_thread.cancelAndWait)
            main_window.destroyed.connect(notes_thread.cancelAndWait)
            notes_thread.start()

            def handle_github_click():
                open_update_window(
                    update_thread.github_assert_url,
                    update_thread.github_assert_name,
                    update_thread.github_assert_sha256,
                    message_box,
                )

            def handle_mirrorchyan_click():
                if not update_thread.mirrorchyan_assert_url:
                    InfoBar.error(
                        title=tr("尚未配置 Mirror酱 更新源 (╥╯﹏╰╥)"),
                        content=tr('请在“设置 → 关于 → 更新源”中选择 Mirror酱 并填写有效 CDK'),
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=5000,
                        parent=self,
                    )
                    return
                open_update_window(
                    update_thread.mirrorchyan_assert_url,
                    update_thread.mirrorchyan_assert_name,
                    update_thread.mirrorchyan_assert_sha256,
                    message_box
                )

            if hasattr(message_box, "githubUpdateCard") and message_box.githubUpdateCard:
                message_box.githubUpdateCard.clicked.connect(handle_github_click)
            if hasattr(message_box, "mirrorchyanUpdateCard") and message_box.mirrorchyanUpdateCard:
                message_box.mirrorchyanUpdateCard.clicked.connect(handle_mirrorchyan_click)

            if message_box.exec():
                QDesktopServices.openUrl(QUrl(update_thread.html_url))

        elif status == UpdateStatus.SUCCESS:
            if hasattr(main_window, "setDetectedUpdateVersion"):
                try:
                    main_window.setDetectedUpdateVersion(None)
                except Exception:
                    pass

            if suppress_feedback:
                return

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
            if suppress_feedback:
                return

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
            if suppress_feedback:
                return
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

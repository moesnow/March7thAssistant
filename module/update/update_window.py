from __future__ import annotations

import os
import subprocess
import traceback
from datetime import datetime

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QHBoxLayout
from qfluentwidgets import BodyLabel, IndeterminateProgressBar, MessageBoxBase, PlainTextEdit, PrimaryPushButton, ProgressBar, PushButton, StateToolTip, SubtitleLabel

from module.localization import tr
from module.update.downloader import format_size as _format_size
from module.update.update_engine import (
    UpdateCancelledError,
    UpdateEngine,
    UpdateError,
    UpdateProgress,
    UpdateStage,
    build_independent_process_env,
)


class ClickableStateToolTip(StateToolTip):
    clicked = Signal()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self.clicked.emit()


class UpdatePrepareWorker(QThread):
    progressChanged = Signal(object)
    logWritten = Signal(str, str)
    prepared = Signal(str, str)
    cancelled = Signal()
    failed = Signal(str)
    noUpdate = Signal(str)

    def __init__(
        self,
        download_url: str | None,
        file_name: str | None,
        sha256: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.download_url = download_url
        self.file_name = file_name
        self.sha256 = sha256
        self.engine: UpdateEngine | None = None
        self._cancel_requested = False

    def _on_progress(self, progress: UpdateProgress):
        self.progressChanged.emit(progress)

    def _on_log(self, level: str, message: str):
        self.logWritten.emit(level, message)

    def cancel(self):
        self._cancel_requested = True
        if self.engine is not None:
            self.engine.request_cancel()

    def run(self):
        try:
            engine = UpdateEngine(
                progress_callback=self._on_progress,
                log_callback=self._on_log,
                checksum_in_subprocess=True,
            )
            self.engine = engine
            if self.download_url and self.file_name:
                engine.set_package(self.download_url, self.file_name, self.sha256)

            if self._cancel_requested:
                engine.request_cancel()

            if not engine.prepare_update():
                if self._cancel_requested:
                    self.cancelled.emit()
                    return
                self.noUpdate.emit(tr("当前已是最新版本"))
                return

            if self._cancel_requested:
                self.cancelled.emit()
                return

            self.prepared.emit(engine.file_name or "", engine.extract_folder_path or "")
        except UpdateCancelledError:
            self.cancelled.emit()
        except UpdateError as e:
            message = str(e) or tr("更新失败")
            self.failed.emit(message)
        except Exception as e:
            self.logWritten.emit("error", traceback.format_exc())
            self.failed.emit(str(e) or tr("更新失败"))
        finally:
            self.engine = None


class UpdaterWindow(MessageBoxBase):
    def __init__(
        self,
        main_window,
        download_url: str | None,
        file_name: str | None,
        sha256: str | None = None,
    ):
        super().__init__(parent=main_window)
        self.main_window = main_window
        self.download_url = download_url
        self.file_name = file_name
        self.sha256 = sha256
        self.worker: UpdatePrepareWorker | None = None
        self.background_tooltip: ClickableStateToolTip | None = None
        self.is_running = False
        self._cancel_requested = False
        self._is_in_background = False
        self._awaiting_install = False
        self._prepared_file_name: str | None = None
        self._prepared_extract_folder_path: str | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowModality(Qt.NonModal)
        self._init_ui()
        self._start_update()

    def _init_ui(self):
        self.widget.setFixedSize(720, 500)

        # 隐藏 MessageBoxBase 默认按钮区域，使用自定义按钮
        self.buttonGroup.hide()

        self.viewLayout.setContentsMargins(20, 20, 20, 20)
        self.viewLayout.setSpacing(12)

        self.title_label = SubtitleLabel(tr("正在准备更新"), self.widget)

        self.status_label = BodyLabel(tr("即将开始下载和安装新版本"), self.widget)
        self.status_label.setWordWrap(True)

        self.indeterminate_bar = IndeterminateProgressBar(self.widget)

        self.progress_bar = ProgressBar(self.widget)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)

        self.detail_label = BodyLabel("", self.widget)
        self.detail_label.setWordWrap(True)

        self.log_edit = PlainTextEdit(self.widget)
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText(tr("更新日志会显示在这里"))

        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch(1)

        self.install_button = PrimaryPushButton(tr("开始安装"), self.widget)
        self.install_button.setVisible(False)
        self.install_button.clicked.connect(self._start_install)

        self.retry_button = PrimaryPushButton(tr("重试"), self.widget)
        self.retry_button.setVisible(False)
        self.retry_button.clicked.connect(self._start_update)

        self.background_button = PushButton(tr("后台更新"), self.widget)
        self.background_button.clicked.connect(self._send_to_background)

        self.close_button = PushButton(tr("关闭"), self.widget)
        self.close_button.clicked.connect(self._handle_close_clicked)

        self.button_layout.addWidget(self.install_button)
        self.button_layout.addWidget(self.retry_button)
        self.button_layout.addWidget(self.background_button)
        self.button_layout.addWidget(self.close_button)

        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addWidget(self.status_label)
        self.viewLayout.addWidget(self.indeterminate_bar)
        self.viewLayout.addWidget(self.progress_bar)
        self.viewLayout.addWidget(self.detail_label)
        self.viewLayout.addWidget(self.log_edit, 1)
        self.viewLayout.addLayout(self.button_layout)

        self.install_button.setMinimumWidth(96)
        self.retry_button.setMinimumWidth(96)
        self.background_button.setMinimumWidth(96)
        self.close_button.setMinimumWidth(96)

    def _set_indeterminate(self, indeterminate: bool):
        self.indeterminate_bar.setVisible(indeterminate)
        self.progress_bar.setVisible(not indeterminate)
        if indeterminate:
            self.indeterminate_bar.start()
        else:
            self.indeterminate_bar.stop()

    def _append_log(self, level: str, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = level.upper()
        self.log_edit.appendPlainText(f"[{timestamp}] {prefix} {message}")
        scrollbar = self.log_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _set_running_state(self, running: bool):
        self.is_running = running
        self.install_button.setVisible(self._awaiting_install)
        self.install_button.setEnabled(self._awaiting_install)
        self.retry_button.setVisible(not running and not self._awaiting_install)
        self.retry_button.setEnabled(not running and not self._awaiting_install)
        self.background_button.setVisible(running)
        self.background_button.setEnabled(running)
        self.close_button.setEnabled(True)
        self.close_button.setText(tr("取消") if running else tr("关闭"))

    def _format_progress_detail(self, progress: UpdateProgress) -> str:
        if progress.indeterminate or not progress.total:
            return progress.message

        current = max(0, progress.current or 0)
        total = max(1, progress.total)
        if progress.stage == UpdateStage.COVER:
            percent = min(100, int(current * 100 / total))
            return f"{progress.message} {percent}%"

        return f"{progress.message} {_format_size(current)} / {_format_size(total)}"

    def _build_background_tooltip_content(self, base_text: str) -> str:
        hint = tr("点击此处可重新打开更新窗口")
        return base_text if base_text else hint

    def _close_background_tooltip(self):
        if self.background_tooltip is None:
            return

        self.background_tooltip.close()
        self.background_tooltip.deleteLater()
        self.background_tooltip = None

    def _update_background_tooltip(self, content: str):
        parent = self.main_window if self.main_window is not None else self.window()
        tooltip_content = self._build_background_tooltip_content(content)
        created = False

        if self.background_tooltip is None:
            self.background_tooltip = ClickableStateToolTip(
                tr("后台更新中"),
                tooltip_content,
                parent,
            )
            self.background_tooltip.closeButton.setVisible(False)
            self.background_tooltip.clicked.connect(self.restore_from_background)
            self.background_tooltip.setCursor(Qt.PointingHandCursor)
            created = True
        else:
            self.background_tooltip.setTitle(tr("后台更新中"))
            self.background_tooltip.setContent(tooltip_content)

        if created:
            self.background_tooltip.move(self.background_tooltip.getSuitablePos())
        self.background_tooltip.show()

    def restore_from_background(self):
        self._is_in_background = False
        self._close_background_tooltip()
        self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def _handle_close_clicked(self):
        if self.is_running:
            self._request_cancel()
            return

        self.close()

    def _send_to_background(self):
        if not self.is_running:
            return

        self._is_in_background = True
        self._update_background_tooltip(self.status_label.text())
        self.hide()

    def _request_cancel(self):
        if not self.is_running or self._cancel_requested:
            return

        self._cancel_requested = True
        self.title_label.setText(tr("正在更新 March7th Assistant"))
        self.status_label.setText(tr("已请求取消更新，正在等待当前步骤结束"))
        self.detail_label.setText("")
        self._set_indeterminate(True)
        self._append_log("warning", tr("已请求取消更新，正在等待当前步骤结束"))

        if self.worker is not None:
            self.worker.cancel()

    def _start_update(self):
        if self.worker is not None and self.worker.isRunning():
            return

        self._cancel_requested = False
        self._is_in_background = False
        self._awaiting_install = False
        self._prepared_file_name = None
        self._prepared_extract_folder_path = None
        self._close_background_tooltip()
        self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        self._set_running_state(True)
        self.title_label.setText(tr("正在更新 March7th Assistant"))
        self.status_label.setText(tr("请勿关闭此窗口，更新完成后会自动启动新版本"))
        self.detail_label.setText("")
        self._set_indeterminate(True)
        self.log_edit.clear()
        self._append_log("info", tr("更新任务已启动"))

        self.worker = UpdatePrepareWorker(
            self.download_url,
            self.file_name,
            self.sha256,
            self,
        )
        self.worker.progressChanged.connect(self._on_progress_changed)
        self.worker.logWritten.connect(self._append_log)
        self.worker.prepared.connect(self._on_prepared)
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.failed.connect(self._on_failed)
        self.worker.noUpdate.connect(self._on_no_update)
        self.worker.start()

    def _on_progress_changed(self, progress: UpdateProgress):
        detail = self._format_progress_detail(progress)

        if self.background_tooltip is not None:
            self._update_background_tooltip(detail)

        if self._cancel_requested:
            return

        self.title_label.setText(tr("正在更新 March7th Assistant"))

        if progress.indeterminate or not progress.total:
            self._set_indeterminate(True)
            self.status_label.setText(progress.message)
            self.detail_label.setText("")
            return

        self._set_indeterminate(False)
        self.progress_bar.setRange(0, 1000)
        current = max(0, progress.current or 0)
        total = max(1, progress.total)
        value = min(1000, int(current * 1000 / total))
        self.progress_bar.setValue(value)
        self.status_label.setText(progress.message)
        if progress.stage == UpdateStage.COVER:
            self.detail_label.setText(detail.rsplit(" ", 1)[-1])
        else:
            self.detail_label.setText(f"{_format_size(current)} / {_format_size(total)}")

    def _launch_helper(self, file_name: str, extract_folder_path: str):
        source_file = os.path.abspath("./March7th Updater.exe")
        if not os.path.exists(source_file):
            raise FileNotFoundError(tr("未找到更新程序"))

        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        command = [source_file, "--mode", "finalize", "--wait-pid", str(os.getpid())]
        command.extend(["--file-name", file_name])
        if extract_folder_path:
            command.extend(["--extract-folder-path", extract_folder_path])
        subprocess.Popen(
            command,
            creationflags=creationflags,
            env=build_independent_process_env(),
            close_fds=True,
        )

    def _on_prepared(self, file_name: str, extract_folder_path: str):
        if self._cancel_requested:
            self._on_cancelled()
            return

        self._prepared_file_name = file_name
        self._prepared_extract_folder_path = extract_folder_path

        if not self._is_in_background:
            self._awaiting_install = True
            self._set_running_state(False)
            self._start_install()
            return

        self._awaiting_install = True
        self._set_running_state(False)
        self._set_indeterminate(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.title_label.setText(tr("更新已准备完成"))
        self.status_label.setText(tr("更新包已下载并解压完成，点击“开始安装”后将关闭主程序并安装新版本"))
        self.detail_label.setText("")
        self._append_log("info", tr("更新已准备完成，等待开始安装"))
        if self.background_tooltip is not None:
            self.background_tooltip.setTitle(tr("更新已准备完成"))
            self.background_tooltip.setContent(
                self._build_background_tooltip_content(
                    tr("更新已准备完成，等待开始安装")
                )
            )

    def _start_install(self):
        if not self._awaiting_install or not self._prepared_file_name:
            return

        try:
            self._launch_helper(
                self._prepared_file_name,
                self._prepared_extract_folder_path or "",
            )
        except Exception as e:
            self._on_failed(str(e) or tr("启动更新器失败"))
            return

        self.install_button.setEnabled(False)
        self.retry_button.setEnabled(False)
        self.background_button.setEnabled(False)
        self.close_button.setEnabled(False)
        self._append_log("info", tr("开始安装"))
        self.title_label.setText(tr("开始安装"))
        self.status_label.setText(tr("请勿关闭此窗口，更新完成后会自动启动新版本"))
        self.detail_label.setText("")

        if self.main_window is not None and hasattr(self.main_window, "quitApp"):
            QTimer.singleShot(200, self.main_window.quitApp)
        else:
            QTimer.singleShot(200, self.close)

    def _on_cancelled(self):
        self.restore_from_background()
        self._awaiting_install = False
        self._set_running_state(False)
        self._set_indeterminate(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.title_label.setText(tr("取消"))
        self.status_label.setText(tr("更新已取消"))
        self.detail_label.setText("")
        self._append_log("info", tr("更新已取消"))

    def _on_failed(self, message: str):
        self.restore_from_background()
        self._awaiting_install = False
        self._set_running_state(False)
        self._set_indeterminate(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.title_label.setText(tr("更新失败"))
        self.status_label.setText(message)
        self.detail_label.setText(tr("请检查日志后重试"))
        self._append_log("error", message)

    def _on_no_update(self, message: str):
        self.restore_from_background()
        self._awaiting_install = False
        self._set_running_state(False)
        self._set_indeterminate(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.title_label.setText(tr("无需更新"))
        self.status_label.setText(message)
        self.detail_label.setText("")
        self._append_log("info", message)

    def closeEvent(self, event: QCloseEvent):
        if self.is_running:
            self._request_cancel()
            event.ignore()
            return

        self._close_background_tooltip()
        if self.main_window is not None and getattr(self.main_window, "gui_update_window", None) is self:
            self.main_window.gui_update_window = None
        event.accept()


def show_update_window(
    main_window,
    download_url: str | None,
    file_name: str | None,
    sha256: str | None = None,
):
    existing = getattr(main_window, "gui_update_window", None)
    if existing is not None:
        existing.restore_from_background()
        return existing

    window = UpdaterWindow(main_window, download_url, file_name, sha256)
    main_window.gui_update_window = window
    window.show()
    window.raise_()
    window.activateWindow()
    return window

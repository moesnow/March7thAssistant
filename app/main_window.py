from PyQt5.QtCore import Qt, QSize, QFileSystemWatcher, pyqtSignal, QObject
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QAction

from contextlib import redirect_stdout

with redirect_stdout(None):
    from app.tools.game_starter import GameStartStatus, GameLaunchThread
    from qfluentwidgets import NavigationItemPosition, MSFluentWindow, SplashScreen, setThemeColor, NavigationBarPushButton, toggleTheme, setTheme, Theme
    from qfluentwidgets import FluentIcon as FIF
    from qfluentwidgets import InfoBar, InfoBarPosition, SystemTrayMenu

from .home_interface import HomeInterface
from .help_interface import HelpInterface
# from .changelog_interface import ChangelogInterface
from .warp_interface import WarpInterface
from .tools_interface import ToolsInterface
from .setting_interface import SettingInterface
from .log_interface import LogInterface
from .common.signal_bus import signalBus

from .card.messagebox_custom import MessageBoxSupport
from .tools.check_update import checkUpdate
from .tools.check_theme_change import checkThemeChange
from .tools.announcement import checkAnnouncement
from .tools.disclaimer import disclaimer

from module.config import cfg
from module.game import get_game_controller
import base64
import os


class ConfigWatcher(QObject):
    """설정 파일 감시자"""
    config_changed = pyqtSignal()

    def __init__(self, config_path, parent=None):
        super().__init__(parent)
        self.config_path = config_path
        self.watcher = QFileSystemWatcher()
        self.debounce_timer = None

        # 설정 감시
        if os.path.exists(self.config_path):
            self.watcher.addPath(self.config_path)
            self.watcher.fileChanged.connect(self._on_config_changed)

    def _on_config_changed(self, path):
        """파일 변경 감지, 빈번한 트리거 방지를 위한 지연 처리"""
        from PyQt5.QtCore import QTimer

        # 이전 타이머 제거
        if self.debounce_timer:
            self.debounce_timer.stop()
            self.debounce_timer.deleteLater()

        # 새 타이머 생성, 1초 지연 (파일 쓰기 중 중복 트리거 방지)
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self._emit_change)
        self.debounce_timer.start(1000)

    def _emit_change(self):
        """파일이 실제로 변경되었는지 확인 후 신호 전송"""
        if os.path.exists(self.config_path) and cfg.is_config_changed():
            self.config_changed.emit()


class MainWindow(MSFluentWindow):
    def __init__(self, task=None, exit_on_complete=False):
        super().__init__()
        self.startup_task = task  # 시작 시 실행할 작업 저장
        self.exit_on_complete = exit_on_complete  # 작업 완료 후 종료 여부

        self.initWindow()

        self.initInterface()
        self.initNavigation()
        self.initSystemTray()

        # 설정 파일 감시자 초기화
        self.config_watcher = ConfigWatcher(os.path.abspath(cfg.config_path), self)
        self.config_watcher.config_changed.connect(self._on_config_file_changed)

        # 시작 작업이 있는 경우 지연 실행
        if self.startup_task:
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(1000, self._executeStartupTask)
        else:
            # 업데이트 확인
            checkUpdate(self, flag=True)
            checkAnnouncement(self)

    def _executeStartupTask(self):
        """시작 시 지정된 작업 실행"""
        if self.startup_task:
            from tasks.base.tasks import start_task
            start_task(self.startup_task)

    def initWindow(self):
        self.setMicaEffectEnabled(False)
        setThemeColor('#f18cb9', lazy=True)
        setTheme(Theme.AUTO, lazy=True)

        # 최대화 비활성화
        self.titleBar.maxBtn.setHidden(True)
        self.titleBar.maxBtn.setDisabled(True)
        self.titleBar.setDoubleClickEnabled(False)
        self.setResizeEnabled(False)
        self.setWindowFlags(Qt.WindowCloseButtonHint)
        # self.setWindowFlags(Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)

        self.resize(960, 640)
        self.setWindowIcon(QIcon('./assets/logo/March7th.ico'))
        self.setWindowTitle("March7th Assistant")

        # 스플래시 화면 생성
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(128, 128))
        self.splashScreen.titleBar.maxBtn.setHidden(True)
        self.splashScreen.raise_()

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

        self.show()
        QApplication.processEvents()

    def initInterface(self):
        self.homeInterface = HomeInterface(self)
        self.helpInterface = HelpInterface(self)
        # self.changelogInterface = ChangelogInterface(self)
        self.warpInterface = WarpInterface(self)
        self.toolsInterface = ToolsInterface(self)
        self.logInterface = LogInterface(self)
        self.settingInterface = SettingInterface(self)

        # 작업 시작 신호 연결
        signalBus.startTaskSignal.connect(self._onStartTask)
        # 단축키 설정 변경 신호 연결
        signalBus.hotkeyChangedSignal.connect(self._onHotkeyChanged)
        # 작업 완료 신호 연결
        self.logInterface.taskFinished.connect(self._onTaskFinished)

    def initNavigation(self):
        self.addSubInterface(self.homeInterface, FIF.HOME, '홈')
        self.addSubInterface(self.helpInterface, FIF.BOOK_SHELF, '도움말')
        # self.addSubInterface(self.changelogInterface, FIF.UPDATE, '업데이트 내역')
        self.addSubInterface(self.warpInterface, FIF.SHARE, '워프 기록')
        self.addSubInterface(self.toolsInterface, FIF.DEVELOPER_TOOLS, '도구 상자')

        self.navigationInterface.addWidget(
            'startGameButton',
            NavigationBarPushButton(FIF.PLAY, '게임 실행', isSelectable=False),
            self.startGame,
            NavigationItemPosition.BOTTOM)

        self.addSubInterface(self.logInterface, FIF.COMMAND_PROMPT, '로그', position=NavigationItemPosition.BOTTOM)

        # self.navigationInterface.addWidget(
        #     'refreshButton',
        #     NavigationBarPushButton(FIF.SYNC, '새로고침', isSelectable=False),
        #     self._on_config_file_changed,
        #     NavigationItemPosition.BOTTOM)

        # self.navigationInterface.addWidget(
        #     'themeButton',
        #     NavigationBarPushButton(FIF.BRUSH, '테마', isSelectable=False),
        #     lambda: toggleTheme(lazy=True),
        #     NavigationItemPosition.BOTTOM)

        self.navigationInterface.addWidget(
            'avatar',
            NavigationBarPushButton(FIF.HEART, '후원', isSelectable=False),
            lambda: MessageBoxSupport(
                '개발자 후원 🥰',
                '이 프로그램은 무료 오픈 소스 프로젝트입니다. 만약 돈을 지불했다면 즉시 환불을 요청하세요.\n이 프로젝트가 마음에 드신다면, 위챗(WeChat) 후원으로 개발자에게 커피 한 잔을 선물해 주세요 ☕\n여러분의 후원은 개발자가 프로젝트를 개발하고 유지 보수하는 원동력이 됩니다 🚀',
                './assets/app/images/sponsor.jpg',
                self
            ).exec(),
            NavigationItemPosition.BOTTOM
        )

        self.addSubInterface(self.settingInterface, FIF.SETTING, '설정', position=NavigationItemPosition.BOTTOM)

        self.splashScreen.finish()
        self.themeListener = checkThemeChange(self)

        if not cfg.get_value(base64.b64decode("YXV0b191cGRhdGU=").decode("utf-8")):
            disclaimer(self)

    def initSystemTray(self):
        """시스템 트레이 초기화"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon('./assets/logo/March7th.ico'))
        self.tray_icon.setToolTip('March7th Assistant')

        # 트레이 메뉴 생성
        tray_menu = SystemTrayMenu(parent=self)
        tray_menu.aboutToShow.connect(self._on_tray_menu_about_to_show)

        # 메인 화면 표시
        show_action = QAction('메인 화면 표시', self)
        show_action.triggered.connect(self.showNormal)
        show_action.triggered.connect(self.activateWindow)
        tray_menu.addAction(show_action)

        # 전체 실행
        run_action = QAction('전체 실행', self)
        run_action.triggered.connect(self.startFullTask)
        tray_menu.addAction(run_action)

        tray_menu.addSeparator()

        # 프로그램 종료
        quit_action = QAction('종료', self)
        quit_action.triggered.connect(self.quitApp)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.onTrayIconActivated)
        self.tray_icon.show()

    def onTrayIconActivated(self, reason):
        """트레이 아이콘 활성화 시 처리"""
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.activateWindow()

    def handle_external_activate(self, task=None, exit_on_complete=False):
        """다른 인스턴스의 활성화 요청 응답: 창을 맨 위로 올리고 필요 시 작업 시작 또는 종료 동작 설정"""
        from PyQt5.QtCore import QTimer
        try:
            # 창 표시 및 최상위로 이동
            self.showNormal()
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

        # 작업이 지정된 경우, 인터페이스 초기화 완료 보장을 위해 지연 실행
        if task:
            self.startup_task = task
            QTimer.singleShot(200, self._executeStartupTask)

        # 작업 완료 후 종료 여부 플래그 설정
        if exit_on_complete:
            self.exit_on_complete = exit_on_complete

    def _on_tray_menu_about_to_show(self):
        """트레이 메뉴가 표시되기 전 창을 활성화하여 Windows에서 외부 영역 클릭 시 메뉴가 닫히지 않는 문제 해결"""
        self.activateWindow()

    def _onStartTask(self, command):
        """작업 시작 신호 처리"""
        # 실행 중인 작업이 있는지 확인
        if self.logInterface.isTaskRunning():
            InfoBar.warning(
                title='작업 실행 중',
                content="새 작업을 시작하려면 먼저 현재 작업을 중지하세요",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
            # 로그 화면으로 전환
            self.switchTo(self.logInterface)
            return
        # 로그 화면으로 전환
        self.switchTo(self.logInterface)
        # 작업 시작
        self.logInterface.startTask(command)

    def startFullTask(self):
        """전체 실행 작업 시작"""
        from tasks.base.tasks import start_task
        start_task("main")

    def _onHotkeyChanged(self):
        """단축키 설정 변경 신호 처리"""
        if hasattr(self, 'logInterface'):
            self.logInterface.updateHotkey()

    def _onTaskFinished(self, exit_code):
        """작업 완료 신호 처리"""
        # 시작 작업이고 완료 후 종료가 설정된 경우, 작업 성공 시 프로그램 종료
        if self.exit_on_complete and self.startup_task and exit_code == 0:
            from PyQt5.QtCore import QTimer
            # 사용자가 완료 상태를 볼 수 있도록 잠시 지연
            QTimer.singleShot(5000, self.quitApp)
        else:
            # 작업 실패 또는 종료 미지정 시 자동 종료 플래그 해제
            self.exit_on_complete = False

    def quitApp(self):
        """애플리케이션 종료"""
        self._do_quit()

    def _on_config_file_changed(self):
        """설정 파일을 다시 로드하고 인터페이스 새로고침"""
        try:
            # 현재 설정 화면에 있는지 확인
            is_in_setting_interface = self.stackedWidget.currentWidget() == self.settingInterface

            # 설정 다시 로드
            cfg._load_config(None, save=False)

            # 알림 초기화
            try:
                from module.notification import init_notifiers
                init_notifiers()
            except Exception:
                pass

            # 로그 화면의 단축키 업데이트
            if hasattr(self, 'logInterface'):
                self.logInterface.updateHotkey()

            # 이전 설정 화면 참조 저장
            old_setting_interface = self.settingInterface
            route_key = old_setting_interface.objectName()

            # 새 설정 화면 생성
            self.settingInterface = SettingInterface(self)

            # 이전 네비게이션 항목을 먼저 숨겨야 높이 증가 버그 방지 가능
            self.navigationInterface.items[route_key].hide()

            # 이전 설정 화면 제거
            self.removeInterface(old_setting_interface, isDelete=True)

            # 새 설정 화면 추가
            self.addSubInterface(self.settingInterface, FIF.SETTING, '설정', position=NavigationItemPosition.BOTTOM)

            # 설정 다시 로드 전 설정 화면에 있었을 경우에만 새 설정 화면으로 전환
            if is_in_setting_interface:
                self.switchTo(self.settingInterface)

            # 창이 보일 때만 팁 표시
            if self.isVisible():
                InfoBar.success(
                    title='설정 업데이트됨',
                    content="설정 파일 변경이 감지되어 자동으로 다시 로드했습니다",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
        except Exception as e:
            # 창이 보일 때만 팁 표시
            if self.isVisible():
                InfoBar.warning(
                    title='설정 로드 실패',
                    content=str(e),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )

    def _stopThemeListener(self):
        """테마 감지 스레드 중지"""
        if hasattr(self, 'themeListener') and self.themeListener:
            self.themeListener.stop()
            self.themeListener = None

    def _stopRunningTask(self):
        """실행 중인 작업 중지"""
        if hasattr(self, 'logInterface') and self.logInterface.isTaskRunning():
            self.logInterface.stopTask()
            # 프로세스 종료 대기
            if self.logInterface.process:
                self.logInterface.process.waitForFinished(3000)
                # 아직 종료되지 않았다면 강제 종료
                if self.logInterface.process.state() != 0:  # QProcess.NotRunning
                    self.logInterface.process.kill()
                    self.logInterface.process.waitForFinished(1000)

    def _do_quit(self, e=None):
        """종료 전 정리 작업 수행 및 프로그램 종료
        e: 선택적 QCloseEvent, e.accept() 호출에 사용됨
        """
        try:
            self.hide()
            self.tray_icon.hide()
            QApplication.processEvents()
        except Exception:
            pass

        # 실행 중인 작업 및 테마 감지 중지
        self._stopRunningTask()
        self._stopThemeListener()

        # 로그 화면 리소스 정리 (선택 사항)
        if hasattr(self, 'logInterface'):
            try:
                self.logInterface.cleanup()
            except Exception:
                pass

        # 이벤트가 전달된 경우 수락
        if e is not None:
            try:
                e.accept()
            except Exception:
                pass

        QApplication.quit()

    def closeEvent(self, e):
        """창 닫기 시 설정에 따른 동작 수행"""
        from .card.messagebox_custom import MessageBoxCloseWindow

        close_action = cfg.get_value('close_window_action', 'ask')

        if close_action == 'ask':
            # 확인 대화 상자 표시
            dialog = MessageBoxCloseWindow(self)
            dialog.exec()

            if dialog.action == 'minimize':
                # 트레이로 최소화
                e.ignore()
                self.hide()
                self.tray_icon.showMessage(
                    'March7th Assistant',
                    '프로그램이 트레이로 최소화되었습니다',
                    QSystemTrayIcon.Information,
                    2000
                )
                # 사용자가 기억하기를 선택한 경우, 동기화를 위해 설정 화면 새로고침
                try:
                    if dialog.rememberCheckBox.isChecked():
                        self._on_config_file_changed()
                except Exception:
                    pass
            elif dialog.action == 'close':
                # 프로그램 종료
                self._do_quit(e)
            else:
                # 사용자 작업 취소 (예: X 버튼 클릭)
                e.ignore()
        elif close_action == 'minimize':
            # 트레이로 바로 최소화
            e.ignore()
            self.hide()
            # self.tray_icon.showMessage(
            #     'March7th Assistant',
            #     '프로그램이 트레이로 최소화되었습니다',
            #     QSystemTrayIcon.Information,
            #     2000
            # )
        elif close_action == 'close':
            # 프로그램 바로 종료
            self._do_quit(e)
        else:
            # 기본 동작: 트레이로 최소화
            e.ignore()
            self.hide()
            self.tray_icon.showMessage(
                'March7th Assistant',
                '프로그램이 트레이로 최소화되었습니다',
                QSystemTrayIcon.Information,
                2000
            )

    def startGame(self):
        start_game_button = self.navigationInterface.widget('startGameButton')
        if start_game_button:
            start_game_button.setEnabled(False)
        game = get_game_controller()
        if cfg.cloud_game_enable and cfg.browser_type == "integrated" and not game.is_integrated_browser_downloaded():
            InfoBar.warning(
                title='내장 브라우저 다운로드 중 (ง •̀_•́)ง',
                content="다운로드 완료 후 클라우드·붕괴: 스타레일이 자동으로 시작됩니다",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=10000,
                parent=self
            )
        elif cfg.cloud_game_enable:
            InfoBar.warning(
                title='게임 실행 중 (❁´◡`❁)',
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

        self.game_launch_thread = GameLaunchThread(game, cfg)
        self.game_launch_thread.finished_signal.connect(self.on_game_launched)
        self.game_launch_thread.start()

    def on_game_launched(self, result):
        if result == GameStartStatus.SUCCESS:
            InfoBar.success(
                title='실행 성공 (＾∀＾●)',
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        elif result == GameStartStatus.BROWSER_DOWNLOAD_FAIL:
            InfoBar.warning(
                title='브라우저 또는 드라이버 다운로드 실패 (╥╯﹏╰╥)',
                content="네트워크 연결 상태를 확인해주세요",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        elif result == GameStartStatus.BROWSER_LAUNCH_FAIL:
            InfoBar.warning(
                title='클라우드 게임 실행 실패 (╥╯﹏╰╥)',
                content="선택한 브라우저가 존재하는지, 네트워크 연결이 정상인지 확인해주세요",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        elif result == GameStartStatus.LOCAL_LAUNCH_FAIL:
            InfoBar.warning(
                title='게임 경로 설정 오류 (╥╯﹏╰╥)',
                content=" '설정' -> '프로그램' 에서 경로를 설정해주세요",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        else:
            InfoBar.warning(
                title='실행 실패',
                content=str(self.game_launch_thread.error_msg),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        start_game_button = self.navigationInterface.widget('startGameButton')
        if start_game_button:
            start_game_button.setEnabled(True)
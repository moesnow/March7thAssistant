from PySide6.QtCore import Qt, Signal, QUrl, QObject, QThread
from PySide6.QtGui import QIcon, QKeyEvent
from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QDesktopServices
from qfluentwidgets import SettingCard, FluentIconBase, InfoBar, InfoBarPosition
from .messagebox_custom import MessageBoxEdit, MessageBoxEditCode, MessageBoxDate, MessageBoxInstance, MessageBoxInstanceChallengeCount, MessageBoxNotifyTemplate, MessageBoxTeam, MessageBoxFriends, MessageBoxPowerPlan
from tasks.base.tasks import start_task
from module.config import cfg
from typing import Union
import datetime
import json
import re
import sys
from ..tools.check_update import checkUpdate


def get_key_from_value(val, map):
    """Helper function to get key from value in a dictionary"""
    for key, value in map.items():
        if value == val:
            return key
    return None


class PushSettingCard(SettingCard):
    clicked = Signal()

    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, configvalue, parent=None):
        super().__init__(icon, title, configvalue, parent)
        self.title = title
        self.configname = configname
        self.button = QPushButton(text, self)
        self.hBoxLayout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)


class PushSettingCardStr(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = str(cfg.get_value(configname))
        super().__init__(text, icon, title, configname, self.configvalue, parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxEdit(self.title, self.configvalue, self.window())
        if message_box.exec():
            cfg.set_value(self.configname, message_box.getText())
            self.contentLabel.setText(message_box.getText())
            self.configvalue = message_box.getText()


class PushSettingCardMirrorchyan(SettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, update_callback, configname, parent=None):
        self.configvalue = str(cfg.get_value(configname))
        self.update_callback = update_callback
        super().__init__(icon, title, "", parent)

        self.title = title
        self.configname = configname

        self.button3 = QPushButton("交流反馈", self)
        self.button3.setObjectName('primaryButton')
        self.hBoxLayout.addWidget(self.button3, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.button3.clicked.connect(self.__onclicked3)

        self.button2 = QPushButton("获取 CDK", self)
        self.button2.setObjectName('primaryButton')
        self.hBoxLayout.addWidget(self.button2, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.button2.clicked.connect(self.__onclicked2)

        self.button = QPushButton(text, self)
        self.hBoxLayout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxEdit(self.title, self.configvalue, self.window())
        if message_box.exec():
            cfg.set_value(self.configname, message_box.getText())
            self.contentLabel.setText(message_box.getText())
            self.configvalue = message_box.getText()
            checkUpdate(self.update_callback)

    def __onclicked2(self):
        QDesktopServices.openUrl(QUrl("https://mirrorchyan.com/?source=m7a-app"))

    def __onclicked3(self):
        QDesktopServices.openUrl(QUrl("https://pd.qq.com/g/MirrorChyan"))


class FetchLatestCodesWorker(QObject):
    finished = Signal(list, str)

    def __init__(self, server):
        super().__init__()
        self.server = server

    def run(self):
        try:
            from tasks.daily.redemption import valid_codes_for_server
            codes = valid_codes_for_server(self.server)

            try:
                used = cfg.already_used_codes or []
            except AttributeError:
                used = []

            codes = [c for c in codes if c not in used]
            self.finished.emit(codes, "")
        except Exception as e:
            self.finished.emit([], str(e))


class PushSettingCardCode(PushSettingCard):

    def __init__(self, text, icon, title, configname, parent=None):
        self.parent = parent
        super().__init__(text, icon, title, configname, "批量使用兑换码，每行一个，自动过滤空格等无效字符", parent)
        self.button.clicked.connect(self.__onclicked)

    # ===================== 主入口 =====================

    def __onclicked(self):
        self.configvalue = '\n'.join(cfg.get_value(self.configname))
        self.message_box = MessageBoxEditCode(
            self.title,
            self.configvalue,
            self.window()
        )
        self.message_box._fetch_cancelled = False
        self.message_box._fetch_thread = None

        self._connect_buttons()
        self._connect_lifecycle()

        if self.message_box.exec():
            self._save_codes()

    # ===================== 按钮绑定 =====================

    def _connect_buttons(self):
        mb = self.message_box
        mb.fetchButton.clicked.connect(self._fetch_latest)
        mb.viewUsedButton.clicked.connect(self._show_used)
        mb.clearUsedButton.clicked.connect(self._clear_used)

    def _connect_lifecycle(self):
        mb = self.message_box
        mb.accepted.connect(self._mark_cancelled)
        mb.rejected.connect(self._mark_cancelled)
        # mb.destroyed.connect(self._mark_cancelled)

    # ===================== 获取兑换码 =====================

    def _fetch_latest(self):
        mb = self.message_box

        if self._is_fetching():
            self._info_warning('正在获取', '请等待当前获取完成', mb)
            return

        server = self._get_server()
        if not server:
            return

        worker = FetchLatestCodesWorker(server)
        thread = QThread(self)

        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        worker.finished.connect(self._on_fetch_finished)
        worker.finished.connect(thread.quit)

        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        mb.fetchButton.setEnabled(False)
        mb._fetch_thread = thread

        thread.start()

        self._info_success('开始获取', '正在获取最新兑换码...', mb)

    def _on_fetch_finished(self, codes, err):
        mb = self.message_box

        if mb._fetch_cancelled:
            self._cleanup_fetch()
            return

        if err:
            self._info_warning('获取最新兑换码失败', err, mb)
        elif not codes:
            self._info_warning('未获取到兑换码', '', mb)
        else:
            mb.textEdit.setText('\n'.join(codes))
            self._info_success(
                '获取成功',
                f'已获取{len(codes)}个兑换码',
                mb
            )

        self._cleanup_fetch()

    # ===================== 已使用兑换码 =====================

    def _show_used(self):
        used = cfg.get_value('already_used_codes') or []
        if not used:
            self._info_warning('暂无已使用兑换码', '', self.message_box)
            return

        mb = MessageBoxEditCode(
            '已使用兑换码',
            '\n'.join(used),
            self.window()
        )
        mb.yesButton.setText('关闭')
        mb.cancelButton.hide()
        mb.fetchButton.hide()
        mb.viewUsedButton.hide()
        mb.clearUsedButton.hide()
        mb.textEdit.setReadOnly(True)
        mb.exec()

    def _clear_used(self):
        from qfluentwidgets import MessageBox

        confirm = MessageBox(
            '确认清空已使用兑换码',
            '此操作不可撤销，是否继续？',
            self.window()
        )
        confirm.yesButton.setText('确认')
        confirm.cancelButton.setText('取消')

        if confirm.exec():
            cfg.set_value('already_used_codes', [])
            self._info_success('', '已清空已使用兑换码', self.message_box)

    # ===================== 保存兑换码 =====================

    def _save_codes(self):
        text = self.message_box.getText()
        code = [
            line.strip()
            for line in (
                ''.join(re.findall(r'[A-Za-z0-9]', l))
                for l in text.splitlines()
            )
            if line.strip()
        ]

        cfg.set_value(self.configname, code)
        self.configvalue = '\n'.join(code)

        if code:
            start_task("redemption")
        else:
            self._info_warning('兑换码为空', '', self.parent)

    # ===================== 工具方法 =====================

    def _get_server(self):
        try:
            if sys.platform == 'win32':
                from utils.registry.star_rail_setting import get_server_by_registry
                server = get_server_by_registry()
                if not server:
                    self._info_warning(
                        '无法判断服务器类型',
                        '无法获取最新兑换码',
                        self.message_box
                    )
            else:
                server = 'cn'  # 云游戏默认国服
            return server
        except Exception as e:
            self._info_warning('获取服务器信息失败', str(e), self.message_box)
            return None

    def _is_fetching(self):
        t = getattr(self.message_box, '_fetch_thread', None)
        return t and t.isRunning()

    def _mark_cancelled(self):
        mb = self.message_box
        mb._fetch_cancelled = True
        t = getattr(mb, '_fetch_thread', None)
        if t:
            t.requestInterruption()

    def _cleanup_fetch(self):
        mb = self.message_box
        mb.fetchButton.setEnabled(True)
        mb._fetch_thread = None

    def _info_warning(self, title, content, parent):
        InfoBar.warning(
            self.tr(title),
            self.tr(content),
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=1500,
            parent=parent
        )

    def _info_success(self, title, content, parent):
        InfoBar.success(
            self.tr(title),
            self.tr(content),
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=1500,
            parent=parent
        )


class PushSettingCardEval(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = str(cfg.get_value(configname))
        super().__init__(text, icon, title, configname, self.configvalue, parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxEdit(self.title, self.configvalue, self.window())
        if message_box.exec():
            cfg.set_value(self.configname, eval(message_box.getText()))
            self.contentLabel.setText(message_box.getText())


class PushSettingCardDate(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = datetime.datetime.fromtimestamp(cfg.get_value(configname))
        super().__init__(text, icon, title, configname, self.configvalue.strftime('%Y-%m-%d %H:%M'), parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxDate(self.title, self.configvalue, self.window())
        if message_box.exec():
            time = message_box.getDateTime()
            # Make naive datetime explicit to local timezone to avoid negative timestamps on Windows
            if time.tzinfo is None or time.tzinfo.utcoffset(time) is None:
                local_offset = datetime.datetime.now().astimezone().utcoffset() or datetime.timedelta()
                time = time.replace(tzinfo=datetime.timezone(local_offset))
            try:
                timestamp = time.timestamp()
                display_time = time
            except (OSError, OverflowError, ValueError):
                timestamp = 0
                display_time = datetime.datetime.fromtimestamp(timestamp)
                InfoBar.warning(
                    '时间无效',
                    '所选时间无法转换为时间戳，已使用默认时间',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self.window()
                )
            cfg.set_value(self.configname, timestamp)
            self.configvalue = display_time
            self.contentLabel.setText(display_time.strftime('%Y-%m-%d %H:%M'))


class PushSettingCardKey(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = str(cfg.get_value(configname))
        super().__init__(text, icon, title, configname, self.configvalue, parent)
        self.button.pressed.connect(self.__onpressed)
        self.button.released.connect(self.__onreleased)

    def __onpressed(self):
        self.button.setText("按下要绑定的按键")

    def __onreleased(self):
        self.button.setText("按住以修改")

    def keyPressEvent(self, e: QKeyEvent):
        if self.button.isDown():
            key_name = self._get_key_name(e)
            if key_name:
                cfg.set_value(self.configname, key_name)
                self.contentLabel.setText(key_name)
                self.button.setText(f"已改为 {key_name}")

    def _get_key_name(self, event):
        function_keys = {
            Qt.Key_F1: "f1",
            Qt.Key_F2: "f2",
            Qt.Key_F3: "f3",
            Qt.Key_F4: "f4",
            Qt.Key_F5: "f5",
            Qt.Key_F6: "f6",
            Qt.Key_F7: "f7",
            Qt.Key_F8: "f8",
            Qt.Key_F9: "f9",
            Qt.Key_F10: "f10",
            Qt.Key_F11: "f11",
            Qt.Key_F12: "f12",
        }

        special_keys = {
            Qt.Key_Escape: "esc",
            Qt.Key_Tab: "tab",
            Qt.Key_Space: "space",
            Qt.Key_Return: "enter",
            Qt.Key_Enter: "enter",
            Qt.Key_Backspace: "backspace",
            Qt.Key_Delete: "delete",
            Qt.Key_Insert: "insert",
            Qt.Key_Home: "home",
            Qt.Key_End: "end",
            Qt.Key_PageUp: "pageup",
            Qt.Key_PageDown: "pagedown",
            Qt.Key_Up: "up",
            Qt.Key_Down: "down",
            Qt.Key_Left: "left",
            Qt.Key_Right: "right",
            Qt.Key_Shift: "shift",
            Qt.Key_Control: "ctrl",
            Qt.Key_Alt: "alt",
        }

        key = event.key()

        if key in function_keys:
            return function_keys[key]

        if key in special_keys:
            return special_keys[key]

        text = event.text()
        if text and text.isprintable() and len(text) == 1:
            return text.lower()

        return None


class PushSettingCardInstance(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, configtemplate, parent=None):
        self.configtemplate = configtemplate
        self.configvalue = cfg.get_value(configname)
        # super().__init__(text, icon, title, configname, str(self.configvalue), parent)
        super().__init__(text, icon, title, configname, "", parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxInstance(self.title, self.configvalue, self.configtemplate, self.window())
        if message_box.exec():
            for type, combobox in message_box.comboBox_dict.items():
                self.configvalue[type] = combobox.text().split('（')[0]
            cfg.set_value(self.configname, self.configvalue)
            # self.contentLabel.setText(str(self.configvalue))


class PushSettingCardInstanceChallengeCount(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = cfg.get_value(configname)
        # super().__init__(text, icon, title, configname, str(self.configvalue), parent)
        super().__init__(text, icon, title, configname, "", parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxInstanceChallengeCount(self.title, self.configvalue, self.window())
        if message_box.exec():
            for type, slider in message_box.slider_dict.items():
                self.configvalue[type] = slider.value()
            cfg.set_value(self.configname, self.configvalue)
            # self.contentLabel.setText(str(self.configvalue))


class PushSettingCardNotifyTemplate(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = cfg.get_value(configname)
        super().__init__(text, icon, title, configname, "", parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxNotifyTemplate(self.title, self.configvalue, self.window())
        if message_box.exec():
            for id, lineedit in message_box.lineEdit_dict.items():
                self.configvalue[id] = lineedit.text().replace(r"\n", "\n")
            cfg.set_value(self.configname, self.configvalue)


class PushSettingCardTeam(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        with open("./assets/config/character_names.json", 'r', encoding='utf-8') as file:
            self.template = json.load(file)
        self.configvalue = cfg.get_value(configname)
        super().__init__(text, icon, title, configname, self.translate_to_chinese(self.configvalue), parent)
        self.button.clicked.connect(self.__onclicked)

    def translate_to_chinese(self, configvalue):
        text = str(configvalue)
        for key, value in self.template.items():
            text = text.replace(key, value)
        return text

    def __onclicked(self):
        message_box = MessageBoxTeam(self.title, self.configvalue, self.template, self.window())
        if message_box.exec():
            self.newConfigValue = []
            for comboboxs in message_box.comboBox_list:
                char = get_key_from_value(comboboxs[0].text(), message_box.template)
                tech = get_key_from_value(comboboxs[1].text(), message_box.tech_map)
                self.newConfigValue.append([char, tech])
            self.configvalue = self.newConfigValue
            cfg.set_value(self.configname, self.newConfigValue)
            self.contentLabel.setText(self.translate_to_chinese(self.newConfigValue))


class PushSettingCardFriends(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        with open("./assets/config/character_names.json", 'r', encoding='utf-8') as file:
            self.template = json.load(file)
            self.template = {'None': '无', **self.template}
        self.configvalue = cfg.get_value(configname)
        super().__init__(text, icon, title, configname, self.translate_to_chinese(self.configvalue), parent)
        self.button.clicked.connect(self.__onclicked)

    def translate_to_chinese(self, configvalue):
        text = str(configvalue)
        for key, value in self.template.items():
            text = text.replace(key, value)
        return text

    def __onclicked(self):
        message_box = MessageBoxFriends(self.title, self.configvalue, self.template, self.window())
        if message_box.exec():
            self.newConfigValue = []
            for comboboxs in message_box.comboBox_list:
                char = get_key_from_value(comboboxs[0].text(), message_box.template)
                # tech = get_key_from_value(comboboxs[1].text(), message_box.tech_map)
                name = comboboxs[1].text()
                self.newConfigValue.append([char, name])
            self.configvalue = self.newConfigValue
            cfg.set_value(self.configname, self.newConfigValue)
            self.contentLabel.setText(self.translate_to_chinese(self.newConfigValue))


class PushSettingCardTeamWithSwap(SettingCard):
    """Setting card with swap button for team1 and team2 configuration"""

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, configname_team1, configname_team2, parent=None):
        with open("./assets/config/character_names.json", 'r', encoding='utf-8') as file:
            self.template = json.load(file)

        self.configname_team1 = configname_team1
        self.configname_team2 = configname_team2
        self.team1_value = cfg.get_value(configname_team1)
        self.team2_value = cfg.get_value(configname_team2)

        super().__init__(icon, title, self._get_display_text(), parent)

        # Add team1 modify button
        self.team1Button = QPushButton('修改队伍1', self)
        self.hBoxLayout.addWidget(self.team1Button, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.team1Button.clicked.connect(self.__onTeam1Clicked)

        # Add team2 modify button
        self.team2Button = QPushButton('修改队伍2', self)
        self.hBoxLayout.addWidget(self.team2Button, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.team2Button.clicked.connect(self.__onTeam2Clicked)

        # Add swap button
        self.swapButton = QPushButton('交换队伍', self)
        self.hBoxLayout.addWidget(self.swapButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.swapButton.clicked.connect(self.__onSwapClicked)

    def translate_to_chinese(self, configvalue):
        text = str(configvalue)
        for key, value in self.template.items():
            text = text.replace(key, value)
        return text

    def _get_display_text(self):
        team1_text = self.translate_to_chinese(self.team1_value)
        team2_text = self.translate_to_chinese(self.team2_value)
        return f"队伍1: {team1_text}\n队伍2: {team2_text}"

    def _update_display(self):
        self.team1_value = cfg.get_value(self.configname_team1)
        self.team2_value = cfg.get_value(self.configname_team2)
        self.contentLabel.setText(self._get_display_text())

    def __onSwapClicked(self):
        # Swap team1 and team2 - get fresh values from config to avoid stale data
        temp_team1 = cfg.get_value(self.configname_team1)
        temp_team2 = cfg.get_value(self.configname_team2)
        cfg.set_value(self.configname_team1, temp_team2)
        cfg.set_value(self.configname_team2, temp_team1)
        self._update_display()

        InfoBar.success(
            '交换成功',
            '队伍1和队伍2已成功交换',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self.window()
        )

    def __onTeam1Clicked(self):
        self._edit_team(self.configname_team1, "队伍1")

    def __onTeam2Clicked(self):
        self._edit_team(self.configname_team2, "队伍2")

    def _edit_team(self, configname, team_name):
        configvalue = cfg.get_value(configname)
        message_box = MessageBoxTeam(team_name, configvalue, self.template, self.window())
        if message_box.exec():
            newConfigValue = []
            for comboboxs in message_box.comboBox_list:
                char = get_key_from_value(comboboxs[0].text(), message_box.template)
                tech = get_key_from_value(comboboxs[1].text(), message_box.tech_map)
                newConfigValue.append([char, tech])
            cfg.set_value(configname, newConfigValue)
            self._update_display()


class PushSettingCardPowerPlan(PushSettingCard):
    """体力计划设置卡片"""

    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, configtemplate, parent=None):
        self.configtemplate = configtemplate
        self.configvalue = cfg.get_value(configname)
        super().__init__(text, icon, title, configname, self._get_display_text(), parent)
        self.button.clicked.connect(self.__onclicked)

    def _get_display_text(self):
        """获取显示文本"""
        if not self.configvalue:
            return "暂无计划"
        return f"已配置 {len(self.configvalue)} 项计划"

    def __onclicked(self):
        message_box = MessageBoxPowerPlan(self.title, self.configvalue, self.configtemplate, self.window())
        if message_box.exec():
            plans = message_box.get_plans()
            self.configvalue = plans
            cfg.set_value(self.configname, plans)
            self.contentLabel.setText(self._get_display_text())

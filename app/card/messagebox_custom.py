from PyQt5.QtCore import Qt, QUrl, QSize
from PyQt5.QtWidgets import QLabel, QHBoxLayout, QSpinBox, QVBoxLayout, QPushButton, QToolButton, QCompleter, QCheckBox
from PyQt5.QtGui import QPixmap, QDesktopServices, QFont
from qfluentwidgets import (MessageBox, LineEdit, ComboBox, EditableComboBox, DateTimeEdit,
                            BodyLabel, FluentStyleSheet, TextEdit, Slider, FluentIcon, qconfig,
                            isDarkTheme, PrimaryPushSettingCard, InfoBar, InfoBarPosition, PushButton, SpinBox, CheckBox)
from qfluentwidgets import FluentIcon as FIF
from typing import Optional
from module.config import cfg
import datetime
import json
import time
import base64


def _cleanup_infobars(widget):
    """Safely hide/close/delete any InfoBar children of `widget`.

    This helps avoid QPainter warnings when a parent widget is closing
    while an InfoBar is still animating/painting.
    """
    try:
        for bar in widget.findChildren(InfoBar):
            try:
                bar.hide()
            except Exception:
                pass
            try:
                bar.close()
            except Exception:
                pass
            try:
                bar.deleteLater()
            except Exception:
                pass
    except Exception:
        pass


def setup_completer(combo_box, items):
    """
    EditableComboBox를 위한 자동 완성 설정
    :param combo_box: EditableComboBox 인스턴스
    :param items: 옵션 목록
    """
    completer = QCompleter(items)
    completer.setCaseSensitivity(Qt.CaseInsensitive)  # 대소문자 구분 안 함
    completer.setFilterMode(Qt.MatchContains)  # 포함 모드 (부분 일치 지원)
    combo_box.setCompleter(completer)


class SliderWithSpinBox(QHBoxLayout):
    def __init__(self, min_value: int, max_value: int, step: int = 1, parent=None):
        super().__init__()

        font = QFont()
        font.setPointSize(11)

        # 슬라이더 생성
        self.slider = Slider(Qt.Horizontal, parent)
        self.slider.setRange(min_value, max_value)
        self.slider.setSingleStep(step)
        self.slider.setMinimumWidth(268)  # RangeSettingCard1과 일치시킴

        # 숫자 표시 생성
        self.valueLabel = QLabel(parent)
        self.valueLabel.setFont(font)
        self.valueLabel.setNum(min_value)
        self.valueLabel.setObjectName('valueLabel')

        # 증감 버튼 생성
        self.minusButton = QToolButton(parent)
        self.plusButton = QToolButton(parent)

        # 버튼 스타일 설정
        self.updateButtonStyle()

        self.minusButton.setFixedSize(28, 28)
        self.plusButton.setFixedSize(28, 28)
        self.minusButton.setIconSize(QSize(12, 12))
        self.plusButton.setIconSize(QSize(12, 12))

        # 레이아웃
        self.addStretch(1)
        self.addWidget(self.valueLabel)
        self.addSpacing(10)
        self.addWidget(self.minusButton)
        self.addSpacing(4)
        self.addWidget(self.slider)
        self.addSpacing(4)
        self.addWidget(self.plusButton)
        self.addSpacing(16)

        # 테마 변경 감지
        qconfig.themeChanged.connect(self.updateButtonStyle)

        # 신호 연결
        self.slider.valueChanged.connect(self.__onValueChanged)
        self.minusButton.clicked.connect(self.decreaseValue)
        self.plusButton.clicked.connect(self.increaseValue)

    def __onValueChanged(self, value: int):
        self.valueLabel.setNum(value)
        self.valueLabel.adjustSize()

    def setValue(self, value: int):
        self.slider.setValue(value)
        self.valueLabel.setNum(value)
        self.valueLabel.adjustSize()

    def value(self) -> int:
        return self.slider.value()

    def decreaseValue(self):
        value = self.slider.value()
        if value > self.slider.minimum():
            self.slider.setValue(value - 1)

    def increaseValue(self):
        value = self.slider.value()
        if value < self.slider.maximum():
            self.slider.setValue(value + 1)

    def updateButtonStyle(self):
        """현재 테마에 따라 버튼 스타일 업데이트"""
        style = '''
            QToolButton {
                background-color: transparent;
                border: 1px solid %s;
                border-radius: 5px;
            }
            QToolButton:hover {
                background-color: %s;
            }
            QToolButton:pressed {
                background-color: %s;
            }
        '''

        if isDarkTheme():
            # 다크 테마
            border_color = '#424242'
            hover_color = '#424242'
            pressed_color = '#333333'
        else:
            # 라이트 테마
            border_color = '#E5E5E5'
            hover_color = '#E5E5E5'
            pressed_color = '#DDDDDD'

        self.minusButton.setStyleSheet(style % (border_color, hover_color, pressed_color))
        self.plusButton.setStyleSheet(style % (border_color, hover_color, pressed_color))

        # 아이콘 업데이트
        self.minusButton.setIcon(FluentIcon.REMOVE.icon())
        self.plusButton.setIcon(FluentIcon.ADD.icon())


class MessageBoxImage(MessageBox):
    def __init__(self, title: str, content: str, image: Optional[str | QPixmap], parent=None):
        super().__init__(title, content, parent)
        if image is not None:
            self.imageLabel = QLabel(parent)
            if isinstance(image, QPixmap):
                self.imageLabel.setPixmap(image)
            elif isinstance(image, str):
                self.imageLabel.setPixmap(QPixmap(image))
            else:
                raise ValueError("Unsupported image type.")
            self.imageLabel.setScaledContents(True)

            imageIndex = self.vBoxLayout.indexOf(self.textLayout) + 1
            self.vBoxLayout.insertWidget(imageIndex, self.imageLabel, 0, Qt.AlignCenter)


class MessageBoxSupport(MessageBoxImage):
    def __init__(self, title: str, content: str, image: str, parent=None):
        super().__init__(title, content, image, parent)

        self.yesButton.setText('다음에 할게요')
        self.cancelButton.setHidden(True)


class MessageBoxAnnouncement(MessageBoxImage):
    def __init__(self, title: str, content: str, image: Optional[str | QPixmap], parent=None):
        super().__init__(title, content, image, parent)

        self.yesButton.setText('확인')
        self.cancelButton.setHidden(True)
        self.setContentCopyable(True)


class MessageBoxHtml(MessageBox):
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(title, content, parent)

        self.buttonLayout.removeWidget(self.yesButton)
        self.buttonLayout.removeWidget(self.cancelButton)
        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.contentLabel = BodyLabel(content, parent)
        self.contentLabel.setObjectName("contentLabel")
        self.contentLabel.setOpenExternalLinks(True)
        self.contentLabel.linkActivated.connect(self.open_url)
        self.contentLabel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        FluentStyleSheet.DIALOG.apply(self.contentLabel)

        self.buttonLayout.addWidget(self.cancelButton, 1, Qt.AlignVCenter)
        self.buttonLayout.addWidget(self.yesButton, 1, Qt.AlignVCenter)
        self.textLayout.addWidget(self.contentLabel, 0, Qt.AlignTop)

    def open_url(self, url):
        QDesktopServices.openUrl(QUrl(url))


class MessageBoxHtmlUpdate(MessageBox):
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(title, content, parent)

        self.buttonLayout.removeWidget(self.yesButton)
        self.buttonLayout.removeWidget(self.cancelButton)
        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.contentLabel = BodyLabel(content, parent)
        self.contentLabel.setObjectName("contentLabel")
        self.contentLabel.setOpenExternalLinks(True)
        self.contentLabel.linkActivated.connect(self.open_url)
        self.contentLabel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.contentLabel.setMinimumWidth(500)
        FluentStyleSheet.DIALOG.apply(self.contentLabel)

        self.buttonLayout.addWidget(self.cancelButton, 1, Qt.AlignVCenter)
        self.buttonLayout.addWidget(self.yesButton, 1, Qt.AlignVCenter)
        self.textLayout.addWidget(self.contentLabel, 0, Qt.AlignTop)

        self.githubUpdateCard = PrimaryPushSettingCard(
            '즉시 업데이트',
            FIF.GITHUB,
            '오픈 소스 채널',
            "GitHub에서 직접 다운로드 및 업데이트"
        )

        self.mirrorchyanUpdateCard = PrimaryPushSettingCard(
            '즉시 업데이트',
            FIF.CLOUD,
            'MirrorChyan 서비스 ⚡',
            "MirrorChyan 사용자는 CDK를 통해 고속 업데이트 가능 (버전 간 증분 업데이트 지원)"
        )
        self.textLayout.addWidget(self.githubUpdateCard, 0, Qt.AlignTop)
        self.textLayout.addWidget(self.mirrorchyanUpdateCard, 0, Qt.AlignTop)

        # self.githubUpdateCard.clicked.connect(self._githubupdate())

    def open_url(self, url):
        QDesktopServices.openUrl(QUrl(url))


class MessageBoxUpdate(MessageBoxHtmlUpdate):
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(title, content, parent)

        self.yesButton.setText('수동 다운로드')
        self.cancelButton.setText('확인')


class MessageBoxDisclaimer(MessageBoxHtml):
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(title, content, parent)

        self.yesButton.setText('종료')
        self.cancelButton.setText('숙지했습니다')
        self.setContentCopyable(True)
        self._opened_at: float | None = time.time()
        self._min_confirm_seconds = 10

    def exec(self):
        """열린 시간을 기록한 후 차단 방식으로 표시합니다."""
        self._opened_at = time.time()
        return super().exec()

    def _confirm_waited_long_enough(self) -> bool:
        return self._opened_at is not None and (time.time() - self._opened_at) >= self._min_confirm_seconds

    def _show_fast_warning(self):
        InfoBar.error(
            title="읽는 시간이 너무 짧아요, 조금만 더 머물러주세요(>∀<)",
            content="",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )

    def accept(self):
        # if not self._confirm_waited_long_enough():
        #     self._show_fast_warning()
        #     return
        _cleanup_infobars(self)
        super().accept()

    def reject(self):
        if not self._confirm_waited_long_enough():
            self._show_fast_warning()
            self._opened_at = time.time()
            return
        _cleanup_infobars(self)
        super().reject()


class MessageBoxEdit(MessageBox):
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(title, content, parent)

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('확인')
        self.cancelButton.setText('취소')

        self.lineEdit = LineEdit(self)
        self.lineEdit.setText(self.content)
        self.textLayout.addWidget(self.lineEdit, 0, Qt.AlignTop)

        self.buttonGroup.setMinimumWidth(480)

    def getText(self):
        return self.lineEdit.text()


class MessageBoxEditCode(MessageBox):
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(title, content, parent)

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('확인')
        self.cancelButton.setText('취소')

        # 작업 버튼: 최신 리딤코드 가져오기 / 사용된 것 보기 / 사용된 것 비우기
        buttonRow = QHBoxLayout()
        self.fetchButton = PushButton('최신 리딤코드 가져오기', self)
        self.viewUsedButton = PushButton('사용된 리딤코드 보기', self)
        self.clearUsedButton = PushButton('사용된 리딤코드 비우기', self)
        buttonRow.addWidget(self.fetchButton)
        buttonRow.addWidget(self.viewUsedButton)
        buttonRow.addWidget(self.clearUsedButton)
        buttonRow.addStretch(1)
        self.textLayout.addLayout(buttonRow)

        self.textEdit = TextEdit(self)
        self.textEdit.setFixedHeight(250)
        self.textEdit.setText(self.content)
        self.textLayout.addWidget(self.textEdit, 0, Qt.AlignTop)

        self.buttonGroup.setMinimumWidth(480)

    def getText(self):
        return self.textEdit.toPlainText()

    def accept(self):
        _cleanup_infobars(self)
        super().accept()

    def reject(self):
        _cleanup_infobars(self)
        super().reject()


class MessageBoxDate(MessageBox):
    def __init__(self, title: str, content: datetime, parent=None):
        super().__init__(title, "", parent)

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('확인')
        self.cancelButton.setText('취소')

        self.datePicker = DateTimeEdit(self)
        self.datePicker.setDateTime(content)
        self._default_datetime = content
        self._epoch_datetime = datetime.datetime.fromtimestamp(0)

        shortcutLayout = QHBoxLayout()
        self.resetButton = PushButton("시간 초기화", self)
        self.nowButton = PushButton("현재 시간으로 설정", self)
        shortcutLayout.addWidget(self.resetButton)
        shortcutLayout.addWidget(self.nowButton)
        shortcutLayout.addStretch(1)

        self.textLayout.addWidget(self.datePicker, 0, Qt.AlignTop)
        self.textLayout.addLayout(shortcutLayout)

        self.buttonGroup.setMinimumWidth(480)

        self.resetButton.clicked.connect(self.reset_default_time)
        self.nowButton.clicked.connect(self.set_current_time)

    def getDateTime(self):
        return self.datePicker.dateTime().toPyDateTime()

    def reset_default_time(self):
        # 타임스탬프 0과 일치하도록 에포크 시작으로 재설정
        self.datePicker.setDateTime(self._epoch_datetime)

    def set_current_time(self):
        self.datePicker.setDateTime(datetime.datetime.now())


class MessageBoxInstance(MessageBox):
    def __init__(self, title: str, content: dict, configtemplate: str, parent=None):
        super().__init__(title, "", parent)
        self.content = content

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('확인')
        self.cancelButton.setText('취소')

        self.buttonGroup.setMinimumWidth(480)

        font = QFont()
        font.setPointSize(11)

        with open(configtemplate, 'r', encoding='utf-8') as file:
            self.template = json.load(file)

        self.comboBox_dict = {}
        for type, names in self.template.items():
            horizontalLayout = QHBoxLayout()

            titleLabel = QLabel(type, parent)
            # titleLabel.setFont(font)
            # titleLabel.setMinimumWidth(100)
            horizontalLayout.addWidget(titleLabel)

            # comboBox = ComboBox()
            comboBox = EditableComboBox()

            has_default = False
            item_list = []
            for name, info in names.items():
                item_name = f"{name}（{info}）"
                comboBox.addItem(item_name)
                item_list.append(item_name)
                if self.content[type] == name:
                    comboBox.setCurrentText(item_name)
                    has_default = True
            if not has_default:
                comboBox.setText(self.content[type])

            # 자동 완성 설정
            setup_completer(comboBox, item_list)

            horizontalLayout.addWidget(comboBox)
            self.textLayout.addLayout(horizontalLayout)
            self.comboBox_dict[type] = comboBox

        self.titleLabelInfo = QLabel("설명: 개척력 소모는 선택한 던전 유형에 따라 판단되며, 던전 이름은 2배 이벤트에도 사용됩니다", parent)
        self.titleLabelInfo.setFont(font)
        self.textLayout.addWidget(self.titleLabelInfo, 0, Qt.AlignTop)

    def validate_inputs(self):
        """모든 입력이 옵션과 일치하는지 확인"""
        for type, comboBox in self.comboBox_dict.items():
            input_text = comboBox.text()

            # 유효한 옵션 목록 생성 (전체 "이름(정보)" 형식 포함)
            valid_options = set()
            for name, info in self.template[type].items():
                valid_options.add(f"{name}（{info}）")
                # 이름 부분만 입력하는 것도 허용 (하위 호환성)
                valid_options.add(name)

            # 입력이 유효한 옵션 중 하나와 일치하는지 확인
            if input_text not in valid_options:
                InfoBar.error(
                    title='입력 오류',
                    content=f'"{type}"의 입력 "{input_text}"이(가) 옵션에 없습니다. 다시 선택해주세요.',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return False

        return True

    def accept(self):
        """유효성 검사를 추가하고 닫기 전에 InfoBar를 정리하기 위해 accept 메서드 재정의"""
        if self.validate_inputs():
            # 대화 상자가 실제로 닫히기 전에 존재하는 모든 InfoBar 정리
            _cleanup_infobars(self)
            super().accept()

    def reject(self):
        """거부/취소 시에도 InfoBar를 정리하여 소멸 중에 InfoBar가 계속 그려지는 것을 방지"""
        _cleanup_infobars(self)
        try:
            super().reject()
        except Exception:
            try:
                self.close()
            except Exception:
                pass


class MessageBoxInstanceChallengeCount(MessageBox):
    def __init__(self, title: str, content: dict, parent=None):
        super().__init__(title, "", parent)
        self.content = content

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('확인')
        self.cancelButton.setText('취소')

        self.buttonGroup.setMinimumWidth(300)

        font = QFont()
        font.setPointSize(11)

        self.template = {
            "拟造花萼（金）": 24,  # 고치 (금)
            "拟造花萼（赤）": 24,  # 고치 (적)
            "凝滞虚影": 8,        # 정체된 허영
            "侵蚀隧洞": 6,        # 침식된 터널
            "饰品提取": 6,        # 장신구 추출
            "历战余响": 3         # 전쟁의 여운
        }
        # 한국어 라벨 매핑 (config 키는 유지하고 표시만 변경)
        self.display_names = {
            "拟造花萼（金）": "고치 (금)",
            "拟造花萼（赤）": "고치 (적)",
            "凝滞虚影": "정체된 허영",
            "侵蚀隧洞": "침식된 터널",
            "饰品提取": "장신구 추출",
            "历战余响": "전쟁의 여운"
        }

        self.slider_dict = {}
        for type, count in self.template.items():
            horizontalLayout = QHBoxLayout()
            horizontalLayout.setContentsMargins(24, 8, 24, 8)  # 여백을 늘려 레이아웃을 더 예쁘게 만듦

            # 라벨 생성
            display_text = self.display_names.get(type, type)
            titleLabel = QLabel(display_text, parent)
            titleLabel.setFont(font)
            horizontalLayout.addWidget(titleLabel)

            # 슬라이더 컴포넌트 생성
            sliderLayout = SliderWithSpinBox(1, count, 1, self)
            sliderLayout.setValue(self.content[type])
            horizontalLayout.addLayout(sliderLayout)
            self.slider_dict[type] = sliderLayout

            self.textLayout.addLayout(horizontalLayout)


class MessageBoxNotify(MessageBox):
    def __init__(self, title: str, configlist: dict, parent=None):
        super().__init__(title.capitalize(), "", parent)
        self.configlist = configlist

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('확인')
        self.cancelButton.setText('취소')

        self.buttonGroup.setMinimumWidth(480)

        font = QFont()
        font.setPointSize(10)
        lineEditFont = QFont()
        lineEditFont.setPointSize(9)
        self.textLayout.setSpacing(4)

        self.lineEdit_dict = {}
        for name, config in self.configlist.items():
            titleLabel = QLabel(name.capitalize(), parent)
            titleLabel.setFont(font)
            self.textLayout.addWidget(titleLabel, 0, Qt.AlignTop)

            lineEdit = LineEdit(self)
            lineEdit.setText(str(cfg.get_value(config)))
            lineEdit.setFont(lineEditFont)
            lineEdit.setFixedHeight(22)

            self.textLayout.addWidget(lineEdit, 0, Qt.AlignTop)
            self.lineEdit_dict[config] = lineEdit


class MessageBoxNotifyTemplate(MessageBox):
    def __init__(self, title: str, content: dict, parent=None):
        super().__init__(title, "", parent)
        self.content = content

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('확인')
        self.cancelButton.setText('취소')

        self.buttonGroup.setMinimumWidth(480)

        font = QFont()
        font.setPointSize(9)
        self.textLayout.setSpacing(4)

        self.lineEdit_dict = {}
        for id, template in self.content.items():
            lineEdit = LineEdit(self)
            lineEdit.setText(template.replace("\n", r"\n"))
            lineEdit.setFont(font)

            lineEdit.setFixedHeight(22)
            self.buttonLayout.setContentsMargins(24, 10, 24, 10)
            self.textLayout.setContentsMargins(24, 24, 24, 6)
            self.textLayout.addWidget(lineEdit, 0, Qt.AlignTop)

            self.lineEdit_dict[id] = lineEdit

        self.titleLabelInfo = QLabel("설명: { } 안의 내용은 실제 전송 시 대체되며, \\n은 줄바꿈을 나타냅니다.", parent)
        self.textLayout.addWidget(self.titleLabelInfo, 0, Qt.AlignTop)


class MessageBoxTeam(MessageBox):
    def __init__(self, title: str, content: dict, template: dict, parent=None):
        super().__init__(title, "", parent)
        self.content = content

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('확인')
        self.cancelButton.setText('취소')

        self.buttonGroup.setMinimumWidth(400)

        font = QFont()
        font.setPointSize(11)

        self.template = template

        self.tech_map = {
            -1: "비술 / 진입",
            0: "조작 없음",
            1: "비술 1회",
            2: "비술 2회",
        }

        self.comboBox_list = []
        for i in range(1, 5):
            # titleLabel과 두 개의 콤보박스를 같은 줄에 배치
            horizontalLayout = QHBoxLayout()

            titleLabel = QLabel(f"{i}번 자리", parent)
            titleLabel.setFont(font)
            # titleLabel.setMinimumWidth(60)
            titleLabel.setAlignment(Qt.AlignVCenter)
            horizontalLayout.addWidget(titleLabel)

            charComboBox = EditableComboBox()
            charComboBox.setMinimumWidth(130)
            charComboBox.addItems(self.template.values())
            charComboBox.setCurrentText(self.template[self.content[i - 1][0]])
            setup_completer(charComboBox, list(self.template.values()))
            horizontalLayout.addWidget(charComboBox)

            techComboBox = ComboBox()
            techComboBox.setMinimumWidth(130)
            techComboBox.addItems(self.tech_map.values())
            techComboBox.setCurrentText(self.tech_map[self.content[i - 1][1]])
            horizontalLayout.addWidget(techComboBox)

            self.textLayout.addLayout(horizontalLayout)

            self.comboBox_list.append((charComboBox, techComboBox))

        self.titleLabelInfo = QLabel("각 파티당 한 명의 캐릭터만 '비술 / 진입'으로 설정할 수 있습니다.", parent)
        self.titleLabelInfo.setFont(font)
        self.textLayout.addWidget(self.titleLabelInfo, 0, Qt.AlignTop)

    def validate_inputs(self):
        """모든 입력이 옵션과 일치하는지 확인"""
        valid_chars = set(self.template.values())
        valid_techs = set(self.tech_map.values())

        for i, (charComboBox, techComboBox) in enumerate(self.comboBox_list, 1):
            char_text = charComboBox.text()
            tech_text = techComboBox.currentText()

            if char_text not in valid_chars:
                InfoBar.error(
                    title='입력 오류',
                    content=f'{i}번 자리 캐릭터 "{char_text}"이(가) 옵션에 없습니다. 다시 선택해주세요.',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return False

            if tech_text not in valid_techs:
                InfoBar.error(
                    title='입력 오류',
                    content=f'{i}번 자리 비술 설정 "{tech_text}"이(가) 옵션에 없습니다. 다시 선택해주세요.',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return False

        return True

    def accept(self):
        """유효성 검사를 추가하고 닫기 전에 InfoBar를 정리하기 위해 accept 메서드 재정의"""
        if self.validate_inputs():
            _cleanup_infobars(self)
            super().accept()

    def reject(self):
        _cleanup_infobars(self)
        try:
            super().reject()
        except Exception:
            try:
                self.close()
            except Exception:
                pass


class MessageBoxFriends(MessageBox):
    def __init__(self, title: str, content: dict, template: dict, parent=None):
        super().__init__(title, "", parent)
        self.content = content

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('확인')
        self.cancelButton.setText('취소')

        self.buttonGroup.setMinimumWidth(400)

        font = QFont()
        font.setPointSize(12)

        self.template = template

        self.comboBox_list = []
        for i in range(1, 7):

            charComboBox = EditableComboBox()
            charComboBox.setMaximumWidth(150)
            charComboBox.addItems(self.template.values())
            charComboBox.setCurrentText(self.template[self.content[i - 1][0]])
            setup_completer(charComboBox, list(self.template.values()))

            nameLineEdit = LineEdit()
            nameLineEdit.setMaximumWidth(150)
            nameLineEdit.setText(self.content[i - 1][1])

            horizontalLayout = QHBoxLayout()
            horizontalLayout.addWidget(charComboBox)
            horizontalLayout.addWidget(nameLineEdit)
            self.textLayout.addLayout(horizontalLayout)

            self.comboBox_list.append((charComboBox, nameLineEdit))

        self.titleLabelInfo = QLabel("설명: 왼쪽에서 캐릭터 선택 후 오른쪽 텍스트 상자에 친구 이름을 입력하세요.\n예: 친구 이름이 'SilverWolf'인 경우 'Silver'만 입력해도 매칭됩니다.\n친구 이름을 비워두면 선택한 캐릭터만 검색합니다.", parent)
        self.textLayout.addWidget(self.titleLabelInfo, 0, Qt.AlignTop)

    def validate_inputs(self):
        """모든 입력이 옵션과 일치하는지 확인"""
        valid_chars = set(self.template.values())

        for i, (charComboBox, nameLineEdit) in enumerate(self.comboBox_list, 1):
            char_text = charComboBox.text()

            if char_text not in valid_chars:
                InfoBar.error(
                    title='입력 오류',
                    content=f'{i}번째 지원 캐릭터 "{char_text}"이(가) 옵션에 없습니다. 다시 선택해주세요.',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return False

        return True

    def accept(self):
        """유효성 검사를 추가하고 닫기 전에 InfoBar를 정리하기 위해 accept 메서드 재정의"""
        if self.validate_inputs():
            _cleanup_infobars(self)
            super().accept()

    def reject(self):
        _cleanup_infobars(self)
        try:
            super().reject()
        except Exception:
            try:
                self.close()
            except Exception:
                pass


class MessageBoxPowerPlan(MessageBox):
    """체력 계획 설정 대화 상자"""

    def __init__(self, title: str, content: list, configtemplate: str, parent=None):
        super().__init__(title, "", parent)
        self.content = content if content else []

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('확인')
        self.cancelButton.setText('취소')

        self.buttonGroup.setMinimumWidth(500)

        font = QFont()
        font.setPointSize(11)

        # 副本模板(던전 템플릿) 로드
        with open(configtemplate, 'r', encoding='utf-8') as file:
            self.template = json.load(file)

        # 副本类型列表(던전 유형 목록)
        blacklist_type = ["历战余响"]  # 필터링할 항목 (전쟁의 여운)
        self.instance_types = list(self.template.keys())
        for btype in blacklist_type:
            if btype in self.instance_types:
                self.instance_types.remove(btype)

        # 모든 계획 행 컨트롤 저장
        self.plan_rows = []

        # 설명 추가
        self.titleLabelInfo = QLabel("체력 계획은 개척력 소모 전 우선 실행되며, 완료 후 목록에서 자동 삭제됩니다.", parent)
        self.titleLabelInfo.setFont(font)
        self.textLayout.addWidget(self.titleLabelInfo, 0, Qt.AlignTop)

        # 계획 목록 컨테이너
        self.planLayout = QVBoxLayout()
        self.textLayout.addLayout(self.planLayout)

        # 기존 내용에 따라 계획 행 추가
        for plan in self.content:
            if len(plan) == 3:
                self.add_plan_row(plan[0], plan[1], plan[2])

        # 버튼 추가
        addButtonLayout = QHBoxLayout()
        self.addButton = PushButton("계획 추가", self)
        self.addButton.clicked.connect(self.add_plan_row)
        addButtonLayout.addWidget(self.addButton)
        addButtonLayout.addStretch(1)
        self.textLayout.addLayout(addButtonLayout)

    def add_plan_row(self, instance_type=None, instance_name=None, count=1):
        """체력 계획 설정 행 추가"""
        # 최대 수량 제한 확인
        if len(self.plan_rows) >= 8:
            InfoBar.warning(
                title='추가 불가',
                content='최대 계획 수량에 도달했습니다',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        horizontalLayout = QHBoxLayout()

        # 던전 유형 콤보박스
        typeComboBox = ComboBox()
        typeComboBox.setMinimumWidth(140)
        typeComboBox.addItems(self.instance_types)
        if instance_type and instance_type in self.instance_types:
            typeComboBox.setCurrentText(instance_type)
        else:
            typeComboBox.setCurrentIndex(0)

        # 던전 이름 콤보박스
        nameComboBox = EditableComboBox()
        nameComboBox.setMinimumWidth(320)

        # 횟수 입력 상자
        countSpinBox = SpinBox()
        countSpinBox.setMinimum(1)
        countSpinBox.setMaximum(999)
        countSpinBox.setValue(count if count else 1)
        countSpinBox.setMinimumWidth(120)

        # 삭제 버튼
        deleteButton = PushButton("삭제", self)
        deleteButton.setMaximumWidth(60)

        # 던전 이름 옵션 업데이트 함수
        def update_instance_names(selected_type):
            nameComboBox.clear()
            if selected_type in self.template:
                item_list = []
                for name, info in self.template[selected_type].items():
                    item_name = f"{name}（{info}）"
                    nameComboBox.addItem(item_name)
                    item_list.append(item_name)
                setup_completer(nameComboBox, item_list)

        # 던전 이름 초기화
        current_type = typeComboBox.currentText()
        update_instance_names(current_type)
        if instance_name:
            # instance_name에 이미 괄호 설명이 포함된 경우 직접 사용; 그렇지 않으면 일치 및 포맷 시도
            if "（" in instance_name and "）" in instance_name:
                nameComboBox.setCurrentText(instance_name)
            else:
                # 해당 설명 찾기 및 포맷
                if current_type in self.template and instance_name in self.template[current_type]:
                    formatted_name = f"{instance_name}（{self.template[current_type][instance_name]}）"
                    nameComboBox.setCurrentText(formatted_name)
                else:
                    nameComboBox.setText(instance_name)

        # 던전 유형 변경 신호 연결
        typeComboBox.currentTextChanged.connect(update_instance_names)

        # 삭제 버튼 기능
        def delete_row():
            # 인터페이스에서 제거
            horizontalLayout.setParent(None)
            for i in reversed(range(horizontalLayout.count())):
                widget = horizontalLayout.itemAt(i).widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()

            # 목록에서 제거
            if (typeComboBox, nameComboBox, countSpinBox, deleteButton) in self.plan_rows:
                self.plan_rows.remove((typeComboBox, nameComboBox, countSpinBox, deleteButton))

        deleteButton.clicked.connect(delete_row)

        # 레이아웃에 추가
        horizontalLayout.addWidget(QLabel("유형:"))
        horizontalLayout.addWidget(typeComboBox)
        horizontalLayout.addWidget(QLabel("이름:"))
        horizontalLayout.addWidget(nameComboBox)
        horizontalLayout.addWidget(QLabel("횟수:"))
        horizontalLayout.addWidget(countSpinBox)
        horizontalLayout.addWidget(deleteButton)

        self.planLayout.addLayout(horizontalLayout)

        # 목록에 저장
        self.plan_rows.append((typeComboBox, nameComboBox, countSpinBox, deleteButton))

    def get_plans(self):
        """모든 계획 가져오기"""
        plans = []
        for typeCombo, nameCombo, countSpin, _ in self.plan_rows:
            instance_type = typeCombo.currentText()
            instance_name = nameCombo.text()

            # 입력에 괄호 설명이 포함된 경우 실제 이름 추출
            if "（" in instance_name and "）" in instance_name:
                instance_name = instance_name.split("（")[0]

            count = countSpin.value()
            if instance_type and instance_name and count > 0:
                plans.append([instance_type, instance_name, count])
        return plans

    def validate_inputs(self):
        """모든 입력이 옵션과 일치하는지 확인"""
        for i, (typeCombo, nameCombo, countSpin, _) in enumerate(self.plan_rows, 1):
            instance_type = typeCombo.currentText()
            input_text = nameCombo.text()

            if not instance_type or instance_type not in self.template:
                InfoBar.error(
                    title='입력 오류',
                    content=f'{i}번째 계획의 던전 유형이 유효하지 않습니다',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return False

            # 유효한 옵션 목록 생성
            valid_options = set()
            for name, info in self.template[instance_type].items():
                valid_options.add(f"{name}（{info}）")
                valid_options.add(name)
            
            # 중국어 키워드 제거 (필요시 한국어로 대체 가능하지만, 템플릿 데이터가 중국어일 수 있음)
            if "无（跳过）" in valid_options: valid_options.remove("无（跳过）")
            if "无" in valid_options: valid_options.remove("无")

            # 입력이 유효한 옵션 중 하나와 일치하는지 확인
            if input_text not in valid_options:
                InfoBar.error(
                    title='입력 오류',
                    content=f'{i}번째 계획의 던전 이름 "{input_text}"이(가) 옵션에 없습니다. 다시 선택해주세요.',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return False

        return True

    def accept(self):
        """확인 및 저장"""
        if self.validate_inputs():
            _cleanup_infobars(self)
            super().accept()

    def reject(self):
        """취소"""
        _cleanup_infobars(self)
        try:
            super().reject()
        except Exception:
            try:
                self.close()
            except Exception:
                pass


class MessageBoxCloseWindow(MessageBox):
    """창 닫기 확인 대화 상자"""

    def __init__(self, parent=None):
        super().__init__(
            '종료 확인',
            '프로그램을 어떻게 처리하시겠습니까?',
            parent
        )

        # 버튼 텍스트 수정
        self.yesButton.setText('트레이로 최소화')
        self.cancelButton.setText('프로그램 종료')

        # 선택 기억 확인란 추가
        self.rememberCheckBox = CheckBox('선택 사항 기억하기 (다음부터 묻지 않음)', self)
        self.textLayout.addWidget(self.rememberCheckBox)

        # 사용자 선택 저장
        self.action = None  # 'minimize' 또는 'close'

    def accept(self):
        """사용자가 트레이로 최소화 선택"""
        self.action = 'minimize'
        if self.rememberCheckBox.isChecked():
            cfg.set_value('close_window_action', 'minimize')
        _cleanup_infobars(self)
        super().accept()

    def reject(self):
        """사용자가 프로그램 종료 선택"""
        self.action = 'close'
        if self.rememberCheckBox.isChecked():
            cfg.set_value('close_window_action', 'close')
        _cleanup_infobars(self)
        super().reject()
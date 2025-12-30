# coding:utf-8
from typing import Union, List
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget
from qfluentwidgets import ExpandSettingCard, FluentIconBase, SwitchButton, IndicatorPosition, SettingCard, ComboBox, PrimaryPushButton


class ExpandableSwitchSettingCard(ExpandSettingCard):
    """ 확장 가능한 스위치 설정 카드 - 범용 구현

    이것은 임의의 하위 설정 카드를 포함할 수 있는 범용 확장 가능한 스위치 카드입니다.
    사용자가 카드를 클릭하여 하위 옵션을 펼치거나 접을 수 있으며, 오른쪽의 스위치로 기능을 활성화/비활성화할 수 있습니다.
    """

    switchChanged = pyqtSignal(bool)
    expandStateChanged = pyqtSignal(bool)  # 새로운 신호: 펼침 상태가 변경될 때 발생, 매개변수는 펼침 여부

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase],
                 title: str, content: str = None, parent=None):
        """
        매개변수:
        - configname: 구성 항목 이름
        - icon: 아이콘
        - title: 제목
        - content: 내용 설명
        - parent: 부모 구성 요소
        """
        super().__init__(icon, title, content, parent)
        self.configname = configname

        # 스위치 버튼
        self.switchButton = SwitchButton('꺼짐', self, IndicatorPosition.RIGHT)

        # addWidget 메서드를 사용하여 카드 레이아웃에 스위치 버튼 추가
        self.card.addWidget(self.switchButton)

        # 순환 참조를 피하기 위해 여기서 config 가져오기
        from module.config import cfg
        self.cfg = cfg

        # 초기값 설정
        self.setValue(self.cfg.get_value(self.configname))

        # 신호 연결
        self.switchButton.checkedChanged.connect(self.__onSwitchChanged)

    def __onSwitchChanged(self, isChecked: bool):
        """스위치 버튼 상태 변경 슬롯"""
        self.setValue(isChecked)
        self.cfg.set_value(self.configname, isChecked)
        self.switchChanged.emit(isChecked)

    def setValue(self, isChecked: bool):
        """스위치 버튼 상태 설정"""
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText('켜짐' if isChecked else '꺼짐')

    def getSwitchState(self) -> bool:
        """현재 스위치 상태 가져오기"""
        return self.switchButton.isChecked()

    def addSettingCard(self, card: SettingCard):
        """확장 가능한 영역에 하위 설정 카드 추가"""
        self.viewLayout.addWidget(card)
        self._adjustViewSize()

    def addSettingCards(self, cards: List[SettingCard]):
        """확장 가능한 영역에 하위 설정 카드 일괄 추가"""
        for card in cards:
            self.viewLayout.addWidget(card)
        self._adjustViewSize()

    def setExpand(self, isExpand: bool):
        """펼치기/접기 메서드 재정의, 애니메이션 전/후에 신호를 보내 부모 컨테이너 높이 조정"""
        is_expanding = not self.isExpand

        # 펼치기 작업인 경우, 애니메이션 전에 신호 전송 (컨테이너를 미리 확장해야 함)
        if is_expanding:
            self.expandStateChanged.emit(True)

        # 부모 클래스 메서드 호출하여 애니메이션 실행
        super().setExpand(isExpand)

        # 접기 작업인 경우, 애니메이션 완료 후 신호 전송 (애니메이션이 끝난 후 컨테이너 축소)
        if not is_expanding:
            # 애니메이션 완료 신호 연결
            self.expandAni.finished.connect(lambda: self._onCollapseFinished())

    def _onCollapseFinished(self):
        """접기 애니메이션 완료 후 콜백"""
        # 중복 연결을 피하기 위해 신호 연결 해제
        try:
            self.expandAni.finished.disconnect()
        except:
            pass
        # 접기 신호 전송
        self.expandStateChanged.emit(False)


class ExpandablePushSettingCard(ExpandSettingCard):
    """확장 가능한 버튼 설정 카드 - 테스트 알림 등 작업에 사용"""

    expandStateChanged = pyqtSignal(bool)
    clicked = pyqtSignal()

    def __init__(self, title: str, icon: Union[str, QIcon, FluentIconBase],
                 content: str = None, button_text: str = "Click", parent=None):
        """
        매개변수:
        - title: 제목
        - icon: 아이콘
        - content: 내용 설명
        - button_text: 버튼 텍스트
        - parent: 부모 구성 요소
        """
        super().__init__(icon, title, content, parent)

        # 푸시 버튼
        self.pushButton = PrimaryPushButton(button_text, self)
        self.card.addWidget(self.pushButton)

        # 신호 연결
        self.pushButton.clicked.connect(self.clicked.emit)

    def setExpand(self, isExpand: bool):
        """펼치기/접기 메서드 재정의, 애니메이션 전/후에 신호를 보내 부모 컨테이너 높이 조정"""
        is_expanding = not self.isExpand

        # 펼치기 작업인 경우, 애니메이션 전에 신호 전송 (컨테이너를 미리 확장해야 함)
        if is_expanding:
            self.expandStateChanged.emit(True)

        # 부모 클래스 메서드 호출하여 애니메이션 실행
        super().setExpand(isExpand)

        # 접기 작업인 경우, 애니메이션 완료 후 신호 전송 (애니메이션이 끝난 후 컨테이너 축소)
        if not is_expanding:
            # 애니메이션 완료 신호 연결
            self.expandAni.finished.connect(lambda: self._onCollapseFinished())

    def _onCollapseFinished(self):
        """접기 애니메이션 완료 후 콜백"""
        # 중복 연결을 피하기 위해 신호 연결 해제
        try:
            self.expandAni.finished.disconnect()
        except:
            pass
        # 접기 신호 전송
        self.expandStateChanged.emit(False)

    def addSettingCard(self, card: SettingCard):
        """확장 가능한 영역에 하위 설정 카드 추가"""
        self.viewLayout.addWidget(card)
        self._adjustViewSize()

    def addSettingCards(self, cards: List[SettingCard]):
        """확장 가능한 영역에 하위 설정 카드 일괄 추가"""
        for card in cards:
            self.viewLayout.addWidget(card)
        self._adjustViewSize()


class ExpandableComboBoxSettingCard(ExpandSettingCard):
    """확장 가능한 콤보박스(드롭다운) 설정 카드 - 범용 구현"""

    expandStateChanged = pyqtSignal(bool)
    currentIndexChanged = pyqtSignal(int)

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase],
                 title: str, content: str = None, texts: dict = None, parent=None):
        """
        매개변수:
        - configname: 구성 항목 이름
        - icon: 아이콘
        - title: 제목
        - content: 내용 설명
        - texts: 드롭다운 메뉴 옵션 {'표시 이름': '값'}
        - parent: 부모 구성 요소
        """
        super().__init__(icon, title, content, parent)
        self.configname = configname

        # 콤보박스
        self.comboBox = ComboBox(self)
        self.card.addWidget(self.comboBox)

        # 순환 참조를 피하기 위해 여기서 config 가져오기
        from module.config import cfg
        self.cfg = cfg

        # 콤보박스 항목 설정
        if texts:
            for key, value in texts.items():
                self.comboBox.addItem(key, userData=value)
                if value == self.cfg.get_value(configname):
                    self.comboBox.setCurrentText(key)

        # 신호 연결
        self.comboBox.currentIndexChanged.connect(self.__onComboBoxChanged)

    def __onComboBoxChanged(self, index: int):
        """콤보박스 변경 슬롯"""
        self.cfg.set_value(self.configname, self.comboBox.itemData(index))
        self.currentIndexChanged.emit(index)

    def setExpand(self, isExpand: bool):
        """펼치기/접기 메서드 재정의, 애니메이션 전/후에 신호를 보내 부모 컨테이너 높이 조정"""
        is_expanding = not self.isExpand

        # 펼치기 작업인 경우, 애니메이션 전에 신호 전송 (컨테이너를 미리 확장해야 함)
        if is_expanding:
            self.expandStateChanged.emit(True)

        # 부모 클래스 메서드 호출하여 애니메이션 실행
        super().setExpand(isExpand)

        # 접기 작업인 경우, 애니메이션 완료 후 신호 전송 (애니메이션이 끝난 후 컨테이너 축소)
        if not is_expanding:
            # 애니메이션 완료 신호 연결
            self.expandAni.finished.connect(lambda: self._onCollapseFinished())

    def _onCollapseFinished(self):
        """접기 애니메이션 완료 후 콜백"""
        # 중복 연결을 피하기 위해 신호 연결 해제
        try:
            self.expandAni.finished.disconnect()
        except:
            pass
        # 접기 신호 전송
        self.expandStateChanged.emit(False)

    def addSettingCard(self, card: SettingCard):
        """확장 가능한 영역에 하위 설정 카드 추가"""
        self.viewLayout.addWidget(card)
        self._adjustViewSize()

    def addSettingCards(self, cards: List[SettingCard]):
        """확장 가능한 영역에 하위 설정 카드 일괄 추가"""
        for card in cards:
            self.viewLayout.addWidget(card)
        self._adjustViewSize()


class ExpandableComboBoxSettingCardUpdateSource(ExpandSettingCard):
    """확장 가능한 콤보박스 설정 카드 - 업데이트 소스 선택용"""

    expandStateChanged = pyqtSignal(bool)

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase],
                 title: str, update_callback, content: str = None, texts: dict = None, parent=None):
        """
        매개변수:
        - configname: 구성 항목 이름
        - icon: 아이콘
        - title: 제목
        - update_callback: 업데이트 콜백 함수
        - content: 내용 설명
        - texts: 드롭다운 메뉴 옵션 {'표시 이름': '값'}
        - parent: 부모 구성 요소
        """
        super().__init__(icon, title, content, parent)
        self.configname = configname
        self.update_callback = update_callback

        # 콤보박스
        self.comboBox = ComboBox(self)
        self.card.addWidget(self.comboBox)

        # 순환 참조를 피하기 위해 여기서 config 가져오기
        from module.config import cfg
        from app.tools.check_update import checkUpdate
        self.cfg = cfg
        self.checkUpdate = checkUpdate

        # 콤보박스 항목 설정
        if texts:
            for key, value in texts.items():
                self.comboBox.addItem(key, userData=value)
                if value == self.cfg.get_value(configname):
                    self.comboBox.setCurrentText(key)

        # 신호 연결
        self.comboBox.currentIndexChanged.connect(self.__onComboBoxChanged)

    def __onComboBoxChanged(self, index: int):
        """콤보박스 변경 슬롯"""
        self.cfg.set_value(self.configname, self.comboBox.itemData(index))
        self.checkUpdate(self.update_callback)

    def setExpand(self, isExpand: bool):
        """펼치기/접기 메서드 재정의, 애니메이션 전/후에 신호를 보내 부모 컨테이너 높이 조정"""
        is_expanding = not self.isExpand

        # 펼치기 작업인 경우, 애니메이션 전에 신호 전송 (컨테이너를 미리 확장해야 함)
        if is_expanding:
            self.expandStateChanged.emit(True)

        # 부모 클래스 메서드 호출하여 애니메이션 실행
        super().setExpand(isExpand)

        # 접기 작업인 경우, 애니메이션 완료 후 신호 전송 (애니메이션이 끝난 후 컨테이너 축소)
        if not is_expanding:
            # 애니메이션 완료 신호 연결
            self.expandAni.finished.connect(lambda: self._onCollapseFinished())

    def _onCollapseFinished(self):
        """접기 애니메이션 완료 후 콜백"""
        # 중복 연결을 피하기 위해 신호 연결 해제
        try:
            self.expandAni.finished.disconnect()
        except:
            pass
        # 접기 신호 전송
        self.expandStateChanged.emit(False)

    def addSettingCard(self, card: SettingCard):
        """확장 가능한 영역에 하위 설정 카드 추가"""
        self.viewLayout.addWidget(card)
        self._adjustViewSize()

    def addSettingCards(self, cards: List[SettingCard]):
        """확장 가능한 영역에 하위 설정 카드 일괄 추가"""
        for card in cards:
            self.viewLayout.addWidget(card)
        self._adjustViewSize()


class ExpandableComboBoxSettingCard1(ExpandSettingCard):
    """확장 가능한 콤보박스 설정 카드 - ComboBoxSettingCard1 유형용"""

    expandStateChanged = pyqtSignal(bool)
    currentIndexChanged = pyqtSignal(int)

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase],
                 title: str, content: str = None, texts: list = None, parent=None):
        """
        매개변수:
        - configname: 구성 항목 이름
        - icon: 아이콘
        - title: 제목
        - content: 내용 설명
        - texts: 드롭다운 메뉴 옵션 목록
        - parent: 부모 구성 요소
        """
        super().__init__(icon, title, content, parent)
        self.configname = configname

        # 콤보박스
        self.comboBox = ComboBox(self)
        self.card.addWidget(self.comboBox)

        # 순환 참조를 피하기 위해 여기서 config 가져오기
        from module.config import cfg
        self.cfg = cfg

        # 콤보박스 항목 설정
        if texts:
            if isinstance(texts, list):
                # 리스트인 경우 직접 추가
                for item in texts:
                    self.comboBox.addItem(item)
                # 구성에서 현재 항목 설정 시도
                current_value = self.cfg.get_value(configname)
                if current_value and current_value in texts:
                    self.comboBox.setCurrentText(current_value)
            else:
                # 딕셔너리인 경우 딕셔너리 방식대로 처리
                for key, value in texts.items():
                    self.comboBox.addItem(key, userData=value)
                    if value == self.cfg.get_value(configname):
                        self.comboBox.setCurrentText(key)

        # 신호 연결
        self.comboBox.currentIndexChanged.connect(self.__onComboBoxChanged)

    def __onComboBoxChanged(self, index: int):
        """콤보박스 변경 슬롯"""
        self.cfg.set_value(self.configname, self.comboBox.currentText())
        self.currentIndexChanged.emit(index)

    def setExpand(self, isExpand: bool):
        """펼치기/접기 메서드 재정의, 애니메이션 전/후에 신호를 보내 부모 컨테이너 높이 조정"""
        is_expanding = not self.isExpand

        # 펼치기 작업인 경우, 애니메이션 전에 신호 전송 (컨테이너를 미리 확장해야 함)
        if is_expanding:
            self.expandStateChanged.emit(True)

        # 부모 클래스 메서드 호출하여 애니메이션 실행
        super().setExpand(isExpand)

        # 접기 작업인 경우, 애니메이션 완료 후 신호 전송 (애니메이션이 끝난 후 컨테이너 축소)
        if not is_expanding:
            # 애니메이션 완료 신호 연결
            self.expandAni.finished.connect(lambda: self._onCollapseFinished())

    def _onCollapseFinished(self):
        """접기 애니메이션 완료 후 콜백"""
        # 중복 연결을 피하기 위해 신호 연결 해제
        try:
            self.expandAni.finished.disconnect()
        except:
            pass
        # 접기 신호 전송
        self.expandStateChanged.emit(False)

    def addSettingCard(self, card: SettingCard):
        """확장 가능한 영역에 하위 설정 카드 추가"""
        self.viewLayout.addWidget(card)
        self._adjustViewSize()

    def addSettingCards(self, cards: List[SettingCard]):
        """확장 가능한 영역에 하위 설정 카드 일괄 추가"""
        for card in cards:
            self.viewLayout.addWidget(card)
        self._adjustViewSize()


class ExpandableSwitchSettingCardEchoofwar(ExpandSettingCard):
    """확장 가능한 전쟁의 여운 스위치 설정 카드, 실행 시작 요일 선택 콤보박스 포함"""

    switchChanged = pyqtSignal(bool)
    expandStateChanged = pyqtSignal(bool)
    currentIndexChanged = pyqtSignal(int)

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase],
                 title: str, content: str = None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname

        # 콤보박스: 전쟁의 여운을 시작할 요일 선택
        self.comboBox = ComboBox(self)
        self.card.addWidget(self.comboBox)

        # 구성 읽기
        from module.config import cfg
        self.cfg = cfg

        texts = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        options = [1, 2, 3, 4, 5, 6, 7]
        for text, option in zip(texts, options):
            self.comboBox.addItem(text, userData=option)

        # 안전하게 현재 값 설정, 기본값은 첫 번째 항목으로 폴백
        current_day = self.cfg.get_value("echo_of_war_start_day_of_week")
        if isinstance(current_day, int) and 1 <= current_day <= 7:
            self.comboBox.setCurrentText(texts[current_day - 1])
        else:
            self.comboBox.setCurrentText(texts[0])

        self.comboBox.currentIndexChanged.connect(self._onCurrentIndexChanged)

        # 스위치 버튼
        self.switchButton = SwitchButton('꺼짐', self, IndicatorPosition.RIGHT)
        self.card.addWidget(self.switchButton)

        self.setValue(self.cfg.get_value(self.configname))
        self.switchButton.checkedChanged.connect(self.__onSwitchChanged)

    def __onSwitchChanged(self, isChecked: bool):
        """스위치 상태 변경 슬롯"""
        self.setValue(isChecked)
        self.cfg.set_value(self.configname, isChecked)
        self.switchChanged.emit(isChecked)

    def setValue(self, isChecked: bool):
        """스위치 상태 설정"""
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText('켜짐' if isChecked else '꺼짐')

    def _onCurrentIndexChanged(self, index: int):
        self.cfg.set_value("echo_of_war_start_day_of_week", self.comboBox.itemData(index))
        self.currentIndexChanged.emit(index)

    def addSettingCard(self, card: SettingCard):
        """확장 가능한 영역에 하위 설정 카드 추가"""
        self.viewLayout.addWidget(card)
        self._adjustViewSize()

    def addSettingCards(self, cards: List[SettingCard]):
        """확장 가능한 영역에 하위 설정 카드 일괄 추가"""
        for card in cards:
            self.viewLayout.addWidget(card)
        self._adjustViewSize()

    def setExpand(self, isExpand: bool):
        """펼치기/접기 메서드 재정의, 애니메이션 전/후에 신호를 보내 부모 컨테이너 높이 조정"""
        is_expanding = not self.isExpand

        if is_expanding:
            self.expandStateChanged.emit(True)

        super().setExpand(isExpand)

        if not is_expanding:
            self.expandAni.finished.connect(lambda: self._onCollapseFinished())

    def _onCollapseFinished(self):
        """접기 애니메이션 완료 후 콜백"""
        try:
            self.expandAni.finished.disconnect()
        except Exception:
            pass
        self.expandStateChanged.emit(False)
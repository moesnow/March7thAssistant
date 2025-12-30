# coding:utf-8
from PyQt5.QtCore import Qt, QTime, QDateTime
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
                             QWidget, QFileDialog, QHeaderView, QComboBox,
                             QSpinBox, QCheckBox, QAbstractItemView)
from qfluentwidgets import TimePicker, BodyLabel, PushButton, TableWidget, MaskDialogBase, MessageBox, Dialog
from qfluentwidgets import LineEdit, ComboBox, CheckBox, SpinBox
from qfluentwidgets import InfoBar, InfoBarPosition
from utils.tasks import TASK_NAMES
import uuid
import os
import json
from module.config import cfg

# assets/config/special_programs.json에서 특수 프로그램 정의 로드 (존재하는 경우)
SPECIAL_PROGRAMS = []
_SPECIAL_BY_DISPLAY = {}
_SPECIAL_BY_EXEC = {}
try:
    cfg_path = "./assets/config/special_programs.json"
    if os.path.exists(cfg_path):
        with open(cfg_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            SPECIAL_PROGRAMS = data.get('special_programs', []) or []
            for p in SPECIAL_PROGRAMS:
                _SPECIAL_BY_DISPLAY[p.get('display_name')] = p
                _SPECIAL_BY_EXEC[p.get('executable', '').lower()] = p
except Exception:
    SPECIAL_PROGRAMS = []


class AddEditScheduleDialog(MessageBox):
    """MessageBox 기반의 예약 작업 추가/편집 대화 상자"""

    def __init__(self, parent=None, task=None, scheduled_tasks=None):
        # MessageBox 스타일로 초기화 (기본 내용 표시 안 함)
        super().__init__("예약 작업 추가/편집", "", parent)
        self.task = task or {}
        # 시간 중복 확인을 위한 기존 작업 목록 (현재 편집 중인 작업 포함될 수 있음)
        self.existing_tasks = scheduled_tasks or []

        # 기본 내용 Label 제거 및 textLayout을 사용하여 사용자 정의 양식 추가
        try:
            self.textLayout.removeWidget(self.contentLabel)
            self.contentLabel.clear()
        except Exception:
            pass

        # 버튼 텍스트 및 너비 조정
        self.yesButton.setText('확인')
        self.cancelButton.setText('취소')
        self.buttonGroup.setMinimumWidth(480)

        # 이름
        self.name_edit = LineEdit(self)
        self.name_edit.setPlaceholderText("예: 전체 실행")

        # 시간
        self.time_picker = TimePicker(self)
        # 기본 시간 04:00으로 설정
        self.time_picker.setTime(QTime(4, 0))

        # 프로그램 유형 ('본체'는 프로그램 자체 실행, '외부 프로그램'은 실행 파일 선택)
        self.program_type_combo = ComboBox(self)
        # 프로그램 유형: 본체, 외부 프로그램, 그리고 설정의 특수 프로그램
        items = ['본체', '외부 프로그램']
        for sp in SPECIAL_PROGRAMS:
            # display_name에 공백 등이 포함될 수 있으므로 로컬라이즈 시 tr(display_name) 사용
            items.append(self.tr(sp.get('display_name')))
        self.program_type_combo.addItems(items)

        # 선택적 외부 프로그램 경로 (외부 프로그램 선택 시에만 활성화)
        self.program_path_edit = LineEdit(self)
        self.program_path_edit.setMinimumWidth(400)
        self.program_path_edit.setPlaceholderText("외부 프로그램 또는 스크립트 전체 경로")
        self.prog_btn = PushButton("프로그램 선택", self)
        self.prog_btn.clicked.connect(self._choose_program)

        prog_layout = QHBoxLayout()
        prog_layout.addWidget(self.program_type_combo)
        prog_layout.addWidget(self.program_path_edit)
        prog_layout.addWidget(self.prog_btn)

        # 실행 인수 (외부 프로그램용) 또는 작업 선택 (본체용)
        self.args_edit = LineEdit(self)
        self.args_edit.setPlaceholderText("외부 프로그램 실행 인수 (선택 사항)")
        self.args_combo = ComboBox(self)
        # 작업 이름을 한국어로 표시하지만, 저장 시에는 해당 작업 ID 유지
        # TASK_NAMES의 원래 순서(삽입 순서) 유지
        task_items = list(TASK_NAMES.items())
        self._task_keys = [k for k, v in task_items]
        self._task_labels = [v for k, v in task_items]
        self.args_combo.addItems(self._task_labels)
        self.args_combo.setVisible(True)
        # 사용자가 내장 작업을 선택할 때 작업 이름을 자동으로 채움 (사용자 조작 시에만 트리거)
        self.args_combo.activated.connect(self._on_args_activated)

        # 타임아웃 강제 중지, 기본 60분, 단위 분
        self.timeout_spin = SpinBox(self)
        self.timeout_spin.setRange(0, 24 * 60)
        self.timeout_spin.setSuffix(" 분 (0은 비활성화)")

        # 초기 표시 상태: 기본값 본체 선택
        self.program_type_combo.setCurrentText('본체')
        # 신호 연결, args_label 생성 후 다시 트리거하여 텍스트가 올바른지 확인
        self.program_type_combo.currentTextChanged.connect(self._on_program_type_changed)
        # activated 신호 연결, 사용자가 수동 선택 시 기본 매개변수 적용 감지 (사용자 트리거만)
        self.program_type_combo.activated.connect(self._on_program_type_activated)

        # 완료 후 알림 푸시 여부 (Boolean)
        self.notify_check = CheckBox("완료 후 푸시 알림", self)
        self.notify_check.setChecked(False)

        # 작업 완료 후 동작 (로컬라이즈된 라벨로 표시, 내부는 키 저장)
        self.post_action_combo = ComboBox(self)
        # keys 와 labels 대응
        self._post_action_items = [
            ("None", "작업 없음"),
            ("Shutdown", "시스템 종료"),
            ("Sleep", "절전 모드"),
            ("Hibernate", "최대 절전 모드"),
            ("Restart", "다시 시작"),
            ("Logoff", "로그아웃"),
            ("TurnOffDisplay", "모니터 끄기"),
        ]
        self._post_action_keys = [k for k, l in self._post_action_items]
        self._post_action_labels = [l for k, l in self._post_action_items]
        self.post_action_combo.addItems(self._post_action_labels)

        # 완료 후 알림 푸시 (기본값: 아니요)
        # 참고: 필드명은 notify, Boolean 값, true는 알림 전송, false는 전송 안 함
        # 활성화
        self.enable_check = CheckBox("활성화", self)
        self.enable_check.setChecked(True)

        # 폼 조합 및 textLayout에 추가 (라벨과 컨트롤 좌우 배열)
        form = QVBoxLayout()
        label_width = 100

        # 활성화 (상단 왼쪽 정렬)
        top_row = QHBoxLayout()
        top_row.addWidget(self.enable_check)
        top_row.addStretch()
        form.addLayout(top_row)

        # 이름과 시간은 같은 행
        row = QHBoxLayout()
        label = BodyLabel("작업 이름:")
        label.setFixedWidth(label_width)
        row.addWidget(label)
        row.addWidget(self.name_edit, 1)
        # 시간은 같은 행의 오른쪽
        time_label = BodyLabel("시작 시간:")
        time_label.setFixedWidth(90)
        row.addWidget(time_label)
        row.addWidget(self.time_picker)
        form.addLayout(row)

        # 프로그램 경로 행
        row = QHBoxLayout()
        label = BodyLabel("프로그램 경로:")
        label.setFixedWidth(label_width)
        row.addWidget(label)
        row.addLayout(prog_layout)
        form.addLayout(row)

        # 실행 인수 / 작업 행 (가변 라벨, 프로그램 유형에 따라 전환)
        row = QHBoxLayout()
        self.args_label = BodyLabel("실행 인수 또는 작업 선택:")
        self.args_label.setFixedWidth(label_width)
        row.addWidget(self.args_label)
        row.addWidget(self.args_edit)
        row.addWidget(self.args_combo)
        form.addLayout(row)

        # 타임아웃과 작업 완료 후 동작 같은 행
        row = QHBoxLayout()
        label = BodyLabel("타임아웃 강제 중지:")
        label.setFixedWidth(label_width)
        row.addWidget(label)
        row.addWidget(self.timeout_spin)
        # 간격
        spacer = QLabel("")
        spacer.setFixedWidth(16)
        row.addWidget(spacer)
        post_label = BodyLabel("작업 완료 후 동작:")
        post_label.setFixedWidth(120)
        row.addWidget(post_label)
        row.addWidget(self.post_action_combo)
        form.addLayout(row)

        # 완료 후 프로세스 종료 (여러 개 입력 가능, 쉼표 구분)
        row = QHBoxLayout()
        label = BodyLabel("완료 후 프로세스 종료:")
        label.setFixedWidth(label_width)
        self.kill_processes_edit = LineEdit(self)
        self.kill_processes_edit.setPlaceholderText("예: StarRail.exe, YuanShen.exe (쉼표로 구분)")
        row.addWidget(label)
        row.addWidget(self.kill_processes_edit)
        form.addLayout(row)

        # 완료 후 알림 푸시 (왼쪽 정렬)
        row = QHBoxLayout()
        label = BodyLabel("완료 후 푸시 알림:")
        label.setFixedWidth(label_width)
        row.addWidget(label)
        row.addWidget(self.notify_check)
        row.addStretch()
        form.addLayout(row)

        self.textLayout.addLayout(form, 0)

        # args_label 텍스트가 올바른지 확인 (처음 열 때 program_type은 이미 기본값으로 설정됨)
        self._on_program_type_changed(self.program_type_combo.currentText())

        # 편집인 경우 데이터 채우기
        if self.task:
            self._load_task(self.task)

        # 프로그램 유형 변경 시 입력 모드 전환
        # 생성자에서 이미 연결됨: self.program_type_combo.currentTextChanged -> _on_program_type_changed

    def exec_(self):
        """구형 호출 호환: QDialog.Accepted 또는 QDialog.Rejected 반환"""
        result = super().exec()
        return QDialog.Accepted if result else QDialog.Rejected

    def accept(self):
        """확인 전 필드 검증 수행: 이름 비어있지 않음, 시간 중복 없음, 외부 프로그램 경로 비어있지 않음."""
        name = self.name_edit.text().strip()
        if not name:
            m = MessageBox('오류', '작업 이름은 비워둘 수 없습니다', self)
            m.cancelButton.hide()
            m.yesButton.setText('확인')
            m.exec()
            return

        # 시간 중복 확인 (현재 편집 중인 작업 ID는 건너뜀)
        time_str = self.time_picker.time.toString('HH:mm')
        for t in (self.existing_tasks or []):
            if self.task and t.get('id') == self.task.get('id'):
                continue
            if t.get('time') == time_str:
                m = MessageBox('오류', '동일한 시간의 작업이 이미 존재합니다. 다른 시간을 선택해주세요.', self)
                m.cancelButton.hide()
                m.yesButton.setText('확인')
                m.exec()
                return

        # 프로그램 경로 비어있지 않음 (본체 유형이 아닐 경우 경로 요구)
        if self.program_type_combo.currentText() != '본체':
            prog = self.program_path_edit.text().strip()
            if not prog:
                m = MessageBox('오류', '프로그램 경로는 비워둘 수 없습니다', self)
                m.cancelButton.hide()
                m.yesButton.setText('확인')
                m.exec()
                return

        # 기타 필드(실행 인수, 메시지)는 비워둘 수 있음, 검증 통과
        try:
            super().accept()
        except Exception:
            # 호환성 폴백
            self.close()

    def _choose_program(self):
        path, _ = QFileDialog.getOpenFileName(self, "프로그램 또는 스크립트 선택", "", "실행 파일 (*.exe *.bat *.ps1);;모든 파일 (*.*)")
        if path:
            # 선택한 경로를 외부 프로그램 경로 컨트롤에 채움
            self.program_path_edit.setText(path)

    def _on_program_type_changed(self, text):
        """프로그램 유형에 따라 인터페이스 조정: 본체 -> 작업 드롭다운 표시; 외부 프로그램 -> 경로 및 인수 입력 표시 및 라벨 텍스트 변경"""
        if text == '본체':
            self.program_path_edit.setVisible(False)
            self.prog_btn.setVisible(False)
            self.args_edit.setVisible(False)
            self.args_combo.setVisible(True)
            # 라벨을 작업 선택으로 업데이트
            try:
                self.args_label.setText('작업 선택:')
            except Exception:
                pass
        elif text == '외부 프로그램':
            self.program_path_edit.setVisible(True)
            self.prog_btn.setVisible(True)
            self.args_edit.setVisible(True)
            self.args_combo.setVisible(False)
            # 라벨을 실행 인수로 업데이트
            try:
                self.args_label.setText('실행 인수:')
                self.program_path_edit.setPlaceholderText('외부 프로그램 또는 스크립트 전체 경로')
            except Exception:
                pass
        else:
            # 설정의 특수 프로그램인지 확인 (display_name의 tr 버전을 사용하여 비교)
            found = None
            for sp in SPECIAL_PROGRAMS:
                if text == self.tr(sp.get('display_name')):
                    found = sp
                    break
            if found:
                self.program_path_edit.setVisible(True)
                self.prog_btn.setVisible(True)
                self.args_edit.setVisible(True)
                self.args_combo.setVisible(False)
                try:
                    self.args_label.setText('실행 인수:')
                    # 실행 파일 예시를 placeholder로 표시
                    exe = found.get('executable', '')
                    self.program_path_edit.setPlaceholderText(self.tr(f'{exe} 전체 경로'))
                except Exception:
                    pass
            else:
                # 폴백
                self.program_path_edit.setVisible(True)
                self.prog_btn.setVisible(True)
                self.args_edit.setVisible(True)
                self.args_combo.setVisible(False)
                try:
                    self.args_label.setText('실행 인수:')
                except Exception:
                    pass

    def _on_program_type_activated(self, index):
        """사용자가 수동으로 선택했을 때만 기본 매개변수 적용 (매개변수가 비어있는 경우)"""
        try:
            text = self.program_type_combo.itemText(index)
        except Exception:
            text = self.program_type_combo.currentText()
        # 본체/외부 프로그램 수동 선택 -> 이름 및 args 지우기 (사용자가 입력하도록)
        if text == '본체' or text == '외부 프로그램':
            self.name_edit.setText('')
            self.args_edit.setText('')
            self.kill_processes_edit.setText('')
            return
        # 특수 프로그램: 설정 조회 및 short_name과 기본 args 적용 (args가 비어있는 경우에만)
        for sp in SPECIAL_PROGRAMS:
            if text == self.tr(sp.get('display_name')):
                try:
                    self.name_edit.setText(sp.get('short_name', ''))
                    self.args_edit.setText(sp.get('default_args', ''))
                    # 완료 후 종료할 프로세스 자동 채우기
                    try:
                        kp = sp.get('kill_processes', []) or []
                        self.kill_processes_edit.setText(', '.join(kp))
                    except Exception:
                        pass
                except Exception:
                    pass
                return

    def _on_args_activated(self, index):
        """사용자가 내장 작업을 선택할 때 작업 이름을 해당 라벨로 동기화 업데이트 (사용자 트리거만)"""
        try:
            label = self.args_combo.itemText(index)
        except Exception:
            label = self.args_combo.currentText()
        # 현재 선택된 내장 작업을 반영하여 이름을 직접 설정
        self.name_edit.setText(label)

    def _load_task(self, task):
        self.name_edit.setText(task.get('name', ''))
        t = task.get('time', '04:00')
        parts = list(map(int, t.split(':')))
        self.time_picker.setTime(QTime(*parts))

        prog = task.get('program', 'self')
        if isinstance(prog, str) and prog.strip().lower() == 'self':
            # 본체 작업
            self.program_type_combo.setCurrentText('본체')
            # self._task_keys에서 해당 task key의 인덱스 찾기
            args_key = task.get('args', 'main')
            try:
                idx = self._task_keys.index(args_key)
            except ValueError:
                # 예비: args가 한국어 라벨인 경우 라벨 매칭 시도
                try:
                    idx = self._task_labels.index(args_key)
                except ValueError:
                    idx = 0
            self.args_combo.setCurrentIndex(idx)
        else:
            # 외부 프로그램 또는 특정 외부 유형
            self.program_path_edit.setText(str(prog))
            lower = str(prog).lower()
            # 파일 이름이 특정 인식 가능한 exe와 일치하면 해당 유형을 자동 선택하고 기본 인수 채움 (없을 경우)
            basename = os.path.basename(lower)
            sp = _SPECIAL_BY_EXEC.get(basename.lower())
            if sp:
                # 설정에서 특수 프로그램을 찾아 해당 display_name 설정 (tr 및 표시)
                self.program_type_combo.setCurrentText(self.tr(sp.get('display_name')))
                self.args_edit.setText(task.get('args', ''))
            else:
                self.program_type_combo.setCurrentText('외부 프로그램')
                self.args_edit.setText(task.get('args', ''))

        # task['timeout']은 초 단위 저장, UI는 분 단위 사용이므로 변환
        try:
            self.timeout_spin.setValue(int(task.get('timeout', 0)) // 60)
        except Exception:
            self.timeout_spin.setValue(0)
        # 완료 후 알림 푸시 여부 -> 새 필드 notify
        try:
            self.notify_check.setChecked(bool(task.get('notify', False)))
        except Exception:
            self.notify_check.setChecked(False)

        # 완료 후 프로세스 종료 (리스트 또는 쉼표 구분 문자열 모두 호환)
        try:
            kp = task.get('kill_processes', [])
            if isinstance(kp, list):
                self.kill_processes_edit.setText(', '.join(kp))
            else:
                self.kill_processes_edit.setText(str(kp) if kp else '')
        except Exception:
            self.kill_processes_edit.setText('')
        # 구형 값 호환: task['post_action']은 key 또는 라벨일 수 있음
        post_val = task.get('post_action', 'None')
        idx = 0
        if post_val in self._post_action_keys:
            idx = self._post_action_keys.index(post_val)
        else:
            try:
                idx = self._post_action_labels.index(post_val)
            except ValueError:
                idx = 0
        self.post_action_combo.setCurrentIndex(idx)
        self.enable_check.setChecked(task.get('enabled', True))
        self._on_program_type_changed(self.program_type_combo.currentText())

    def get_task(self):
        task = {}
        task['id'] = self.task.get('id') if self.task and self.task.get('id') else str(uuid.uuid4())
        task['name'] = self.name_edit.text().strip() or '이름 없음'
        # TimePicker.time은 호출 가능한 객체가 아닌 QTime 객체이므로 속성에 직접 액세스
        task['time'] = self.time_picker.time.toString('HH:mm')

        # 프로그램 유형에 따라 program 필드 저장: 'self' 또는 외부 프로그램 경로
        if self.program_type_combo.currentText() == '본체':
            task['program'] = 'self'
            # args는 한국어 라벨이 아닌 작업 id(key)로 저장
            idx = self.args_combo.currentIndex() if self.args_combo.count() > 0 else 0
            task['args'] = self._task_keys[idx] if idx >= 0 and idx < len(self._task_keys) else 'main'
        else:
            task['program'] = self.program_path_edit.text().strip() or ''
            task['args'] = self.args_edit.text().strip()

        # 초 단위로 저장 (기존 실행/타임아웃 로직과 호환)
        task['timeout'] = int(self.timeout_spin.value()) * 60
        # 완료 후 알림 푸시 여부 (Boolean)
        task['notify'] = bool(self.notify_check.isChecked())
        # key로 저장 (_post_action_keys와 대응)
        pa_idx = self.post_action_combo.currentIndex() if self.post_action_combo.count() > 0 else 0
        task['post_action'] = self._post_action_keys[pa_idx] if pa_idx >= 0 and pa_idx < len(self._post_action_keys) else 'None'
        task['enabled'] = bool(self.enable_check.isChecked())

        # 완료 후 종료할 프로세스 이름, 프로세스 이름 리스트로 저장 (빈 항목 및 공백 제거)
        kp_text = self.kill_processes_edit.text().strip()
        if kp_text:
            kp_list = [p.strip() for p in kp_text.split(',') if p.strip()]
        else:
            kp_list = []
        task['kill_processes'] = kp_list

        return task


class ScheduleManagerDialog(MessageBox):
    """MessageBox 기반의 예약 작업 관리 대화 상자"""

    def __init__(self, parent=None, scheduled_tasks=None, save_callback=None):
        super().__init__('예약 작업 설정', "", parent)
        self.scheduled_tasks = scheduled_tasks or []
        self.save_callback = save_callback

        # 기본 내용 정리
        try:
            self.textLayout.removeWidget(self.contentLabel)
            self.contentLabel.clear()
        except Exception:
            pass

        # 버튼 조정 (닫기 버튼 하나만 표시)
        self.yesButton.hide()
        self.cancelButton.setText('닫기')
        self.buttonGroup.setMinimumWidth(480)

        # 테이블
        self.table = TableWidget(self)
        # 열 추가: 완료 후 프로세스 종료
        self.table.setColumnCount(7)
        # 열 순서: 활성화, 이름, 시간, 프로그램, 인수/작업, 알림, 프로세스 종료
        self.table.setHorizontalHeaderLabels(['활성화', '이름', '시간', '프로그램', '인수/작업', '알림', '프로세스 종료'])
        # self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 60)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 90)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 70)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 150)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 50)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.setMinimumWidth(800)
        self.table.setMinimumHeight(350)
        # 읽기 전용 테이블 설정: 직접 편집 금지, 행 단위 선택, 단일 선택 모드 (버튼을 통해서만 편집)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        # 조작 버튼 행 (추가/편집/삭제)
        btn_layout = QHBoxLayout()
        self.add_btn = PushButton('추가', self)
        self.edit_btn = PushButton('편집', self)
        self.del_btn = PushButton('삭제', self)
        self.run_btn = PushButton('즉시 실행', self)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addWidget(self.run_btn)

        # 충돌 처리: 예약 작업 트리거 시 이미 실행 중인 작업이 있을 경우 처리 방법 (skip/stop)
        conflict_label = BodyLabel('충돌 처리:')
        # conflict_label.setFixedWidth(90)
        self.conflict_combo = ComboBox(self)
        # options: key, label
        self._conflict_options = [('skip', '실행할 작업 건너뛰기'), ('stop', '실행 중인 작업 중지')]
        for key, label in self._conflict_options:
            self.conflict_combo.addItem(label, userData=key)
        # 설정에 저장된 값으로 설정 (기본값 skip)
        try:
            cur = cfg.get_value('scheduled_on_conflict', 'skip')
            for i in range(self.conflict_combo.count()):
                if self.conflict_combo.itemData(i) == cur:
                    self.conflict_combo.setCurrentIndex(i)
                    break
        except Exception:
            pass
        # 설정을 구성에 저장 (사용자가 변경 시 즉시 저장)
        try:
            self.conflict_combo.currentIndexChanged.connect(lambda i: cfg.set_value('scheduled_on_conflict', self.conflict_combo.itemData(i) or 'skip'))
        except Exception:
            pass

        btn_layout.addWidget(conflict_label)
        btn_layout.addWidget(self.conflict_combo)
        btn_layout.addStretch()

        # textLayout에 삽입
        self.textLayout.addWidget(self.table, 0, Qt.AlignTop)
        self.textLayout.addLayout(btn_layout)

        # 연결
        self.add_btn.clicked.connect(self._on_add)
        self.edit_btn.clicked.connect(self._on_edit)
        self.del_btn.clicked.connect(self._on_delete)
        self.run_btn.clicked.connect(self._on_run_now)
        # 행 더블 클릭 시 편집 열기 (편집 버튼과 동일)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)

        # 데이터 로드
        self._reload_table()

    def exec_(self):
        """구형 호출 호환"""
        result = super().exec()
        return QDialog.Accepted if result else QDialog.Rejected

    def _reload_table(self):
        self.table.setRowCount(len(self.scheduled_tasks))
        for i, t in enumerate(self.scheduled_tasks):
            # 활성화 (첫 번째 열)
            enabled_item = QTableWidgetItem('예' if t.get('enabled', True) else '아니요')
            self.table.setItem(i, 0, enabled_item)
            # 이름
            self.table.setItem(i, 1, QTableWidgetItem(t.get('name', '')))
            # 시간
            self.table.setItem(i, 2, QTableWidgetItem(t.get('time', '')))
            # 프로그램 (본체는 "본체" 표시, 그 외는 경로 또는 파일명)
            prog = t.get('program', '')
            if prog == 'self':
                prog_display = '본체'
                prog_item = QTableWidgetItem(prog_display)
            else:
                prog_str = str(prog)
                # 경로 형식인지 판단 (절대 경로 또는 경로 구분자 포함), 맞다면 파일명만 표시하고 툴팁에 전체 경로 표시
                if os.path.isabs(prog_str) or ('\\' in prog_str) or ('/' in prog_str):
                    prog_display = os.path.basename(prog_str) or prog_str
                    prog_item = QTableWidgetItem(prog_display)
                    prog_item.setToolTip(prog_str)
                else:
                    prog_display = prog_str
                    prog_item = QTableWidgetItem(prog_display)
            self.table.setItem(i, 3, prog_item)
            # 인수/작업 (본체인 경우 로컬라이즈된 작업명 표시)
            args = t.get('args', '')
            if prog == 'self':
                args_display = TASK_NAMES.get(args, args)
            else:
                args_display = args
            self.table.setItem(i, 4, QTableWidgetItem(args_display))
            notify_item = QTableWidgetItem('예' if t.get('notify', False) else '아니요')
            self.table.setItem(i, 5, notify_item)
            # 완료 후 프로세스 종료 표시 (6번째 열, 인덱스 6)
            kp = t.get('kill_processes', [])
            if isinstance(kp, list):
                kp_display = ', '.join(kp)
            else:
                kp_display = str(kp) if kp else ''
            self.table.setItem(i, 6, QTableWidgetItem(kp_display))

    def _on_add(self):
        dlg = AddEditScheduleDialog(self, scheduled_tasks=self.scheduled_tasks)
        if dlg.exec_() == QDialog.Accepted:
            task = dlg.get_task()
            self.scheduled_tasks.append(task)
            self._reload_table()
            if self.save_callback:
                self.save_callback(self.scheduled_tasks)

    def _on_edit(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.scheduled_tasks):
            m = MessageBox('알림', '먼저 편집할 작업을 선택해주세요', self)
            m.cancelButton.hide()
            m.yesButton.setText('확인')
            m.exec()
            return
        task = self.scheduled_tasks[row]
        dlg = AddEditScheduleDialog(self, task=task, scheduled_tasks=self.scheduled_tasks)
        if dlg.exec_() == QDialog.Accepted:
            self.scheduled_tasks[row] = dlg.get_task()
            self._reload_table()
            if self.save_callback:
                self.save_callback(self.scheduled_tasks)

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.scheduled_tasks):
            m = MessageBox('알림', '먼저 삭제할 작업을 선택해주세요', self)
            m.cancelButton.hide()
            m.yesButton.setText('확인')
            m.exec()
            return
        m = MessageBox('확인', '선택한 예약 작업을 삭제하시겠습니까?', self)
        m.yesButton.setText('확인')
        m.cancelButton.setText('취소')
        if m.exec():
            self.scheduled_tasks.pop(row)
            self._reload_table()
            if self.save_callback:
                self.save_callback(self.scheduled_tasks)

    def _on_run_now(self):
        """선택한 작업을 즉시 실행 (확인 포함), 트리거 프로세스는 _checkScheduledTime과 일치 유지."""
        row = self.table.currentRow()
        if row < 0 or row >= len(self.scheduled_tasks):
            m = MessageBox('알림', '먼저 실행할 작업을 선택해주세요', self)
            m.cancelButton.hide()
            m.yesButton.setText('확인')
            m.exec()
            return
        t = self.scheduled_tasks[row]
        # 확인
        m = MessageBox('확인', self.tr(f'"{t.get("name", "")}" 작업을 즉시 실행하시겠습니까?'), self)
        m.yesButton.setText('확인')
        m.cancelButton.setText('취소')
        if not m.exec():
            return

        # _checkScheduledTime과 일치하는 작업 딕셔너리 구성
        task_for_start = {
            'program': t.get('program', 'self'),
            'args': t.get('args', ''),
            'timeout': int(t.get('timeout', 0) or 0),
            'name': t.get('name', ''),
            'notify': bool(t.get('notify', False)),
            'post_action': t.get('post_action', 'None'),
            'id': t.get('id'),
        }

        try:
            parent = self.parent()
            # 보류 중인 메타 및 트리거 타임스탬프 기록 (타이머 충돌 방지)
            now_ts = QDateTime.currentDateTime().toSecsSinceEpoch()
            try:
                if hasattr(parent, '_pending_task_meta'):
                    parent._pending_task_meta = t
            except Exception:
                pass
            try:
                if hasattr(parent, '_last_triggered_ts') and t.get('id'):
                    parent._last_triggered_ts[t.get('id')] = now_ts
            except Exception:
                pass

            # 로그 기록 (부모 컴포넌트가 지원하는 경우)
            try:
                if hasattr(parent, 'appendLog'):
                    parent.appendLog(f"\n========== 예약 작업 수동 트리거 ({t.get('name', '이름 없음')} @ {t.get('time', '')}) ==========")
            except Exception:
                pass

            # 작업 시작
            if hasattr(parent, 'startTask'):
                # 작업이 실행 중인지 확인
                if parent.isTaskRunning():
                    InfoBar.warning(
                        title='작업 실행 중',
                        content="새 작업을 시작하려면 먼저 현재 작업을 중지하세요",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=5000,
                        parent=parent
                    )
                    # 로그 인터페이스로 전환
                    try:
                        self.close()
                    except Exception:
                        pass
                else:
                    parent.startTask(task_for_start)
                    try:
                        self.close()
                    except Exception:
                        pass
            else:
                info = MessageBox('오류', '작업을 실행할 수 없음: 부모 컴포넌트가 startTask를 지원하지 않음', self)
                info.cancelButton.hide()
                info.yesButton.setText('확인')
                info.exec()
        except Exception as e:
            m = MessageBox('오류', self.tr(f'작업 시작 실패: {e}'), self)
            m.cancelButton.hide()
            m.yesButton.setText('확인')
            m.exec()

    def _on_row_double_clicked(self, row: int, column: int):
        """테이블 셀 더블 클릭 시 편집 트리거 (편집 버튼과 동일)."""
        # 보호 검사
        if row < 0 or row >= self.table.rowCount():
            return
        # 해당 행 선택 및 편집 대화 상자 열기
        self.table.selectRow(row)
        self.table.setCurrentCell(row, 0)
        self._on_edit()
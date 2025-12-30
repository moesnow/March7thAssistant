from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QFont
from PyQt5.QtWidgets import QWidget, QLabel, QFileDialog, QVBoxLayout, QStackedWidget, QSpacerItem, QScrollArea, QSizePolicy, QScroller, QScrollerProperties
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import SettingCardGroup, PushSettingCard, ScrollArea, InfoBar, PrimaryPushSettingCard
from app.sub_interfaces.accounts_interface import accounts_interface
from .common.style_sheet import StyleSheet
from .components.pivot import SettingPivot
from .card.comboboxsettingcard1 import ComboBoxSettingCard1
from .card.comboboxsettingcard2 import ComboBoxSettingCard2, ComboBoxSettingCardUpdateSource, ComboBoxSettingCardLog
from .card.switchsettingcard1 import SwitchSettingCard1, SwitchSettingCardNotify, StartMarch7thAssistantSwitchSettingCard, SwitchSettingCardTeam, SwitchSettingCardImmersifier, SwitchSettingCardGardenofplenty, SwitchSettingCardEchoofwar, SwitchSettingCardHotkey, SwitchSettingCardCloudGameStatus
from .card.rangesettingcard1 import RangeSettingCard1
from .card.pushsettingcard1 import PushSettingCardInstance, PushSettingCardInstanceChallengeCount, PushSettingCardNotifyTemplate, PushSettingCardMirrorchyan, PushSettingCardEval, PushSettingCardDate, PushSettingCardKey, PushSettingCardTeam, PushSettingCardFriends, PushSettingCardTeamWithSwap, PushSettingCardPowerPlan
from .card.timepickersettingcard1 import TimePickerSettingCard1
from .card.expandable_switch_setting_card import ExpandableSwitchSettingCard, ExpandableComboBoxSettingCardUpdateSource, ExpandablePushSettingCard, ExpandableComboBoxSettingCard, ExpandableComboBoxSettingCard1, ExpandableSwitchSettingCardEchoofwar
from module.config import cfg
from module.notification import notif
from tasks.base.tasks import start_task
from .tools.check_update import checkUpdate
import os


class SettingInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        # self.title_area = QScrollArea(self)
        self.pivot = SettingPivot(self)
        self.stackedWidget = QStackedWidget(self)

        self.settingLabel = QLabel("설정", self)

        self.__initWidget()
        self.__initCard()
        self.__initLayout()
        self.__connectSignalToSlot()

    def __initWidget(self):
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setViewportMargins(0, 140, 0, 5)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # self.title_area.setWidget(self.pivot)
        # self.title_area.setWidgetResizable(True)
        # self.title_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # self.title_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.title_area.setMinimumSize(800, 50)
        # self.title_area.setStyleSheet("""
        #     QScrollBar:horizontal {
        #         height: 4px;
        #         background: #f0f0f0;
        #         border-radius: 10px;
        #     }

        #     QScrollBar::handle:horizontal {
        #         background: #888;
        #         border-radius: 10px;
        #     }

        #     QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        #         background: none;
        #     }

        #     QScrollBar::handle:horizontal:hover {
        #         background: #555;
        #     }
        # """)
        self.setObjectName('settingInterface')
        self.scrollWidget.setObjectName('scrollWidget')
        self.settingLabel.setObjectName('settingLabel')
        StyleSheet.SETTING_INTERFACE.apply(self)

        QScroller.grabGesture(self.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        scroller = QScroller.scroller(self.viewport())
        scroller_props = scroller.scrollerProperties()
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootDragDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.5)
        scroller.setScrollerProperties(scroller_props)

    def __initCard(self):
        self.PowerGroup = SettingCardGroup("개척력 설정", self.scrollWidget)
        self.powerPlanCard = PushSettingCardPowerPlan(
            '설정',
            FIF.CALENDAR,
            "개척력 계획",
            "power_plan",
            "./assets/config/instance_names.json"
        )
        self.instanceTypeCard = ExpandableComboBoxSettingCard1(
            "instance_type",
            FIF.ALIGNMENT,
            '던전 유형',
            None,
            texts=['고치 (금)', '고치 (적)', '정체된 허영', '침식된 터널', '장신구 추출']
        )
        # self.calyxGoldenPreferenceCard = ComboBoxSettingCard2(
        #     "calyx_golden_preference",
        #     FIF.PIE_SINGLE,
        #     '고치 (금) 선호 지역',
        #     '',
        #     texts={'야릴로-VI': 'Jarilo-VI', '선주「나부」': 'XianzhouLuofu', '페나코니': 'Penacony'}
        # )
        self.instanceNameCard = PushSettingCardInstance(
            '수정',
            FIF.PALETTE,
            "던전 이름",
            "instance_names",
            "./assets/config/instance_names.json"
        )
        # self.maxCalyxPerRoundNumOfAttempts = RangeSettingCard1(
        #     "max_calyx_per_round_num_of_attempts",
        #     [1, 6],
        #     FIF.HISTORY,
        #     "매 회차 고치 도전 횟수",
        #     '',
        # )
        self.instanceTeamEnableCard = SwitchSettingCardTeam(
            FIF.EDIT,
            '자동 파티 교체',
            None,
            "instance_team_enable",
            "instance_team_number"
        )
        self.tpBeforeInstanceEnableCard = SwitchSettingCard1(
            FIF.LEAF,
            '개척력 소모 전 임의의 닻(텔레포트)으로 이동',
            "",
            "tp_before_instance"
        )
        # self.instanceTeamNumberCard = ComboBoxSettingCard1(
        #     "instance_team_number",
        #     FIF.FLAG,
        #     '파티 번호',
        #     None,
        #     texts=['3', '4', '5', '6', '7']
        # )
        self.useReservedTrailblazePowerEnableCard = SwitchSettingCard1(
            FIF.HEART,
            '예비 개척력 사용',
            "1회 상한 300pt, 전부 사용하려면 '작업 완료 후' 옵션을 '반복'으로 변경한 뒤 '전체 실행'을 클릭하세요.",
            "use_reserved_trailblaze_power"
        )
        self.useFuelEnableCard = SwitchSettingCard1(
            FIF.CAFE,
            '연료 사용',
            "1회 상한 5개, 전부 사용하려면 '작업 완료 후' 옵션을 '반복'으로 변경한 뒤 '전체 실행'을 클릭하세요.",
            "use_fuel"
        )
        self.breakDownLevelFourRelicsetEnableCard = SwitchSettingCard1(
            FIF.FILTER,
            '4성 유물 자동 분해 (게임 내 자동 분해 설정 권장)',
            '침식된 터널, 장신구 추출, 전쟁의 여운, 시뮬레이션 우주 완료 후 4성 이하 유물 자동 분해',
            "break_down_level_four_relicset"
        )
        self.mergeImmersifierEnableCard = SwitchSettingCardImmersifier(
            FIF.BASKETBALL,
            '개척력으로 몰입기 우선 합성 (장신구 추출 권장)',
            "지정된 상한 도달 시 중지",
            "merge_immersifier"
        )
        self.instanceNameChallengeCountCard = PushSettingCardInstanceChallengeCount(
            '수정',
            FIF.HISTORY,
            "던전 최대 연속 도전 횟수 (기본값 유지 권장)",
            "instance_names_challenge_count"
        )
        self.borrowEnableCard = ExpandableSwitchSettingCard(
            "borrow_enable",
            FIF.PIN,
            '지원 캐릭터 사용 활성화',
            ''
        )
        self.borrowCharacterEnableCard = SwitchSettingCard1(
            FIF.UNPIN,
            '강제 지원 캐릭터 사용',
            '일일 훈련 요구 사항이 완료되어도 항상 지원 캐릭터 사용',
            "borrow_character_enable"
        )
        self.borrowFriendsCard = PushSettingCardFriends(
            '수정',
            FIF.FLAG,
            "지원 목록",
            "borrow_friends"
        )
        self.borrowScrollTimesCard = RangeSettingCard1(
            "borrow_scroll_times",
            [1, 10],
            FIF.HISTORY,
            "스크롤 검색 횟수",
            '',
        )
        self.buildTargetEnableCard = ExpandableSwitchSettingCard(
            "build_target_enable",
            FIF.LEAF,
            '육성 목표 활성화',
            "육성 목표에 따라 행적 및 유물 던전 파밍, 목표를 가져올 수 없는 경우 기본 던전 설정으로 돌아감"
        )
        self.buildTargetPlanarOrnamentWeeklyCountCard = RangeSettingCard1(
            "build_target_ornament_weekly_count",
            [0, 7],
            FIF.CALENDAR,
            '매주 장신구 추출 횟수',
            '목표에 충분한 자원이 있는 경우 장신구 추출 실행 횟수, 나머지 시간은 침식된 터널 실행',
        )
        self.echoofwarEnableCard = ExpandableSwitchSettingCardEchoofwar(
            "echo_of_war_enable",
            FIF.MEGAPHONE,
            '전쟁의 여운 활성화',
            "매주 개척력으로 '전쟁의 여운' 3회 우선 완료, 실행 시작 요일 설정 지원, 전체 실행 시에만 유효",
        )
        self.echoofwarRunTimeCard = PushSettingCardDate(
            '수정',
            FIF.DATE_TIME,
            "마지막 전쟁의 여운 완료 시간",
            "echo_of_war_timestamp"
        )
        # self.echoofwarStartDayOfWeekCard = RangeSettingCard1(
        #     "echo_of_war_start_day_of_week",
        #     [1, 7],
        #     FIF.HISTORY,
        #     "周几开始执行【历战余响】",
        #     "假设值为4，那么周1、2、3不执行「历战余响」，周4、5、6、7则执行",
        # )
        # self.borrowCharacterFromCard = PushSettingCardEval(
        #     '修改',
        #     FIF.PEOPLE,
        #     "指定好友的支援角色（填写用户名，模糊匹配模式）",
        #     "borrow_character_from"
        # )
        # self.borrowCharacterInfoCard = PrimaryPushSettingCard(
        #     '打开角色文件夹',
        #     FIF.INFO,
        #     "↓↓支援角色↓↓",
        #     "角色对应的英文名字可以在 \"March7thAssistant\\assets\\images\\share\\character\" 中查看"
        # )
        # self.borrowCharacterCard = PushSettingCardEval(
        #     '修改',
        #     FIF.ARROW_DOWN,
        #     "支援角色优先级（从高到低）",
        #     "borrow_character"
        # )

        self.DailyGroup = SettingCardGroup("일일 설정", self.scrollWidget)
        self.dailyEnableCard = ExpandableSwitchSettingCard(
            "daily_enable",
            FIF.CALENDAR,
            '일일 훈련 활성화',
            ""
        )
        self.dailyMaterialEnableCard = SwitchSettingCard1(
            FIF.CHECKBOX,
            "'재료 합성'으로 임무 완료",
            "가방에 '미광 원핵' 합성을 위한 '꺼진 원핵'이 충분한지 확인하세요",
            "daily_material_enable"
        )
        # self.dailyHimekoTryEnableCard = SwitchSettingCard1(
        #     FIF.CHECKBOX,
        #     '通过 “姬子试用” 完成任务',
        #     "",
        #     "daily_himeko_try_enable"
        # )
        self.dailyMemoryOneEnableCard = SwitchSettingCard1(
            FIF.CHECKBOX,
            "'기억 1'로 임무 완료",
            "혼돈의 기억을 해제하고 파티를 설정한 후 이 옵션을 켜세요",
            "daily_memory_one_enable"
        )
        self.dailyMemoryOneTeamCard = PushSettingCardTeam(
            '수정',
            FIF.FLAG,
            "기억 1 파티",
            "daily_memory_one_team"
        )
        self.lastRunTimeCard = PushSettingCardDate(
            '수정',
            FIF.DATE_TIME,
            "마지막 일일 훈련 완료 감지 시간",
            "last_run_timestamp"
        )
        self.activityEnableCard = ExpandableSwitchSettingCard(
            "activity_enable",
            FIF.CERTIFICATE,
            '이벤트 감지 활성화',
            None
        )
        self.activityDailyCheckInEnableCard = SwitchSettingCard1(
            FIF.COMPLETED,
            '일일 출석',
            "'별의 궤도 전용티켓' 또는 '성옥' 자동 수령, 순성의 선물, 순광의 선물, 축제 선물 이벤트 포함",
            "activity_dailycheckin_enable"
        )
        self.activityGardenOfPlentyEnableCard = SwitchSettingCardGardenofplenty(
            FIF.CALORIES,
            '꽃이 피는 정원',
            "2배 횟수가 있을 때 개척력 우선 '고치' 사용",
            "activity_gardenofplenty_enable"
        )
        self.activityRealmOfTheStrangeEnableCard = SwitchSettingCard1(
            FIF.CALORIES,
            '기묘한 영역',
            "2배 횟수가 있을 때 개척력 우선 '침식된 터널' 사용",
            "activity_realmofthestrange_enable"
        )
        self.activityPlanarFissureEnableCard = SwitchSettingCard1(
            FIF.CALORIES,
            '차원 분열',
            "2배 횟수가 있을 때 개척력 우선 '장신구 추출' 사용",
            "activity_planarfissure_enable"
        )
        self.rewardEnableCard = ExpandableSwitchSettingCard(
            "reward_enable",
            FIF.TRANSPARENT,
            '보상 수령 활성화',
            ""
        )
        self.dispatchEnableCard = SwitchSettingCard1(
            FIF.STOP_WATCH,
            '의뢰',
            None,
            "reward_dispatch_enable"
        )
        self.mailEnableCard = SwitchSettingCard1(
            FIF.MAIL,
            '우편',
            None,
            "reward_mail_enable"
        )
        self.assistEnableCard = SwitchSettingCard1(
            FIF.BRUSH,
            '지원',
            None,
            "reward_assist_enable"
        )
        self.questEnableCard = SwitchSettingCard1(
            FIF.STOP_WATCH,
            '일일 훈련',
            None,
            "reward_quest_enable"
        )
        self.srpassEnableCard = SwitchSettingCard1(
            FIF.QUIET_HOURS,
            '무명의 공훈',
            None,
            "reward_srpass_enable"
        )
        self.achievementEnableCard = SwitchSettingCard1(
            FIF.CERTIFICATE,
            '업적',
            None,
            "reward_achievement_enable"
        )

        # 兑换码奖励开关
        self.redemptionEnableCard = SwitchSettingCard1(
            FIF.BOOK_SHELF,
            '리딤코드',
            None,
            "reward_redemption_code_enable"
        )

        self.CurrencywarsGroup = SettingCardGroup("화폐 전쟁", self.scrollWidget)
        self.currencywarsEnableCard = SwitchSettingCard1(
            FIF.DICTIONARY,
            "'화폐 전쟁' 포인트 보상 활성화",
            "",
            "currencywars_enable"
        )
        self.currencywarsTypeCard = ComboBoxSettingCard2(
            "currencywars_type",
            FIF.COMMAND_PROMPT,
            '유형',
            '',
            texts={'표준 게임': 'normal', '오버클럭 게임': 'overclock'}
        )
        self.currencywarsRunTimeCard = PushSettingCardDate(
            '수정',
            FIF.DATE_TIME,
            "마지막 화폐 전쟁 포인트 보상 완료 감지 시간",
            "currencywars_timestamp"
        )

        self.UniverseGroup = SettingCardGroup("시뮬레이션 우주", self.scrollWidget)
        self.weeklyDivergentEnableCard = ExpandableSwitchSettingCard(
            "weekly_divergent_enable",
            FIF.VPN,
            "'차분화 우주' 포인트 보상 활성화",
            ""
        )
        self.weeklyDivergentTypeCard = ComboBoxSettingCard2(
            "weekly_divergent_type",
            FIF.COMMAND_PROMPT,
            '유형',
            '',
            texts={'일반 연산': 'normal', '주기 연산': 'cycle'}
        )
        self.weeklyDivergentRunTimeCard = PushSettingCardDate(
            '수정',
            FIF.DATE_TIME,
            "마지막 차분화 우주 포인트 보상 완료 감지 시간",
            "weekly_divergent_timestamp"
        )
        self.universeEnableCard = ExpandableSwitchSettingCard(
            "universe_enable",
            FIF.VPN,
            '시뮬레이션 우주/차분화 우주 활성화 (Auto_Simulated_Universe)',
            "보통 매주 상한까지 유물 경험치와 영혼의 눈물(적 드랍 재료 대체)을 반복 파밍하는 데 사용됨"
        )
        self.universeOperationModeCard = ComboBoxSettingCard2(
            "universe_operation_mode",
            FIF.COMMAND_PROMPT,
            '실행 모드',
            '',
            texts={'통합(exe)': 'exe', '소스코드': 'source'}
        )
        self.universeCategoryCard = ComboBoxSettingCard2(
            "universe_category",
            FIF.COMMAND_PROMPT,
            '유형',
            '',
            texts={'차분화 우주': 'divergent', '시뮬레이션 우주': 'universe'}
        )
        self.divergentTypeCard = ComboBoxSettingCard2(
            "divergent_type",
            FIF.COMMAND_PROMPT,
            '차분화 우주 선택 시 유형',
            '',
            texts={'일반 연산': 'normal', '주기 연산': 'cycle'}
        )
        self.universeDisableGpuCard = SwitchSettingCard1(
            FIF.COMMAND_PROMPT,
            'GPU 가속 비활성화',
            '차분화 우주가 정상적으로 실행되지 않을 때 시도해보세요',
            "universe_disable_gpu"
        )
        self.universeTimeoutCard = RangeSettingCard1(
            "universe_timeout",
            [1, 24],
            FIF.HISTORY,
            "시뮬레이션 우주/차분화 우주 타임아웃",
            "설정 시간 초과 시 강제 중지 (단위: 시간)",
        )
        self.universeRunTimeCard = PushSettingCardDate(
            '수정',
            FIF.DATE_TIME,
            "마지막 시뮬레이션 우주/차분화 우주 실행 시간",
            "universe_timestamp"
        )
        self.universeBonusEnableCard = SwitchSettingCard1(
            FIF.IOT,
            '장신구 추출 자동 실행/몰입 보상 수령',
            "유형이 '차분화 우주'인 경우 포인트 보상 수령 후 자동으로 장신구 추출 실행(몰입기 소모). '시뮬레이션 우주'인 경우 몰입 보상 자동 수령.",
            "universe_bonus_enable"
        )
        self.universeFrequencyCard = ComboBoxSettingCard2(
            "universe_frequency",
            FIF.MINIMIZE,
            '실행 빈도',
            '',
            texts={'매주': 'weekly', '매일': 'daily'}
        )
        self.universeCountCard = RangeSettingCard1(
            "universe_count",
            [0, 34],
            FIF.HISTORY,
            "실행 횟수",
            "중도 정지는 카운트되지 않음. 0은 지정하지 않음(시뮬레이션 우주 원본 로직 사용)",
        )
        self.divergentTeamTypeCard = ComboBoxSettingCard2(
            "divergent_team_type",
            FIF.FLAG,
            '차분화 우주 파티 유형',
            '',
            texts={'추가 공격': '追击', '지속 피해': 'dot', '필살기': '终结技', '격파': '击破', '보존(반격)': '盾反'}
        )
        fates = {}
        for a, b in [("설정 안 함", "不配置"), ("보존", "存护"), ("기억", "记忆"), ("공허", "虚无"), ("풍요", "丰饶"), ("수렵", "巡猎"), ("파멸", "毁灭"), ("환락", "欢愉"), ("번식", "繁育"), ("지식", "智识")]:
            fates[a] = b
        self.universeFateCard = ComboBoxSettingCard2(
            "universe_fate",
            FIF.PIE_SINGLE,
            '운명의 길 (시뮬레이션 우주만 유효)',
            '',
            texts=fates
        )
        self.universeDifficultyCard = RangeSettingCard1(
            "universe_difficulty",
            [0, 5],
            FIF.HISTORY,
            "난이도 (0은 설정 안 함, 시뮬레이션 우주만 유효)",
            "",
        )

        self.FightGroup = SettingCardGroup("필드 토벌", self.scrollWidget)
        self.fightEnableCard = ExpandableSwitchSettingCard(
            "fight_enable",
            FIF.BUS,
            '필드 토벌 활성화 (Fhoe-Rail)',
            ""
        )
        self.fightOperationModeCard = ComboBoxSettingCard2(
            "fight_operation_mode",
            FIF.COMMAND_PROMPT,
            '실행 모드',
            '',
            texts={'통합(exe)': 'exe', '소스코드': 'source'}
        )
        self.fightTimeoutCard = RangeSettingCard1(
            "fight_timeout",
            [1, 24],
            FIF.HISTORY,
            "필드 토벌 타임아웃",
            "설정 시간 초과 시 강제 중지 (단위: 시간)",
        )
        self.fightTeamEnableCard = SwitchSettingCardTeam(
            FIF.EDIT,
            '자동 파티 교체',
            None,
            "fight_team_enable",
            "fight_team_number"
        )
        # self.fightTeamNumberCard = ComboBoxSettingCard1(
        #     "fight_team_number",
        #     FIF.FLAG,
        #     '队伍编号',
        #     None,
        #     texts=['3', '4', '5', '6', '7']
        # )
        self.FightRunTimeCard = PushSettingCardDate(
            '수정',
            FIF.DATE_TIME,
            "마지막 필드 토벌 실행 시간",
            "fight_timestamp"
        )
        self.fightAllowMapBuyCard = ComboBoxSettingCard2(
            "fight_allow_map_buy",
            FIF.GLOBE,
            '코인 및 만료된 택배 구매',
            '',
            texts={"설정 안 함": "不配置", "활성화": True, "비활성화": False}
        )
        self.fightAllowSnackBuyCard = ComboBoxSettingCard2(
            "fight_allow_snack_buy",
            FIF.GLOBE,
            '비술 간식 구매 및 합성',
            '',
            texts={"설정 안 함": "不配置", "활성화": True, "비활성화": False}
        )
        self.fightMainMapCard = ComboBoxSettingCard2(
            "fight_main_map",
            FIF.GLOBE,
            '우선 행성',
            '',
            texts={"설정 안 함": "0", "우주정거장": "1", "야릴로": "2", "선주": "3", "페나코니": "4", "옴팔로스": 5}
        )

        self.ImmortalGameGroup = SettingCardGroup("빛 따라 금 찾아", self.scrollWidget)
        self.forgottenhallEnableCard = ExpandableSwitchSettingCard(
            "forgottenhall_enable",
            FIF.SPEED_HIGH,
            '혼돈의 기억 활성화',
            ""
        )
        self.forgottenhallLevelCard = PushSettingCardEval(
            '수정',
            FIF.MINIMIZE,
            "관문 범위",
            "forgottenhall_level"
        )
        # self.forgottenhallRetriesCard = RangeSettingCard1(
        #     "forgottenhall_retries",
        #     [0, 10],
        #     FIF.REMOVE_FROM,
        #     "重试次数",
        # )
        self.forgottenhallTeamsCard = PushSettingCardTeamWithSwap(
            FIF.FLAG,
            "혼돈의 기억 파티 설정",
            "forgottenhall_team1",
            "forgottenhall_team2"
        )
        self.forgottenhallRunTimeCard = PushSettingCardDate(
            '수정',
            FIF.DATE_TIME,
            "마지막 혼돈의 기억 실행 시간",
            "forgottenhall_timestamp"
        )

        self.purefictionEnableCard = ExpandableSwitchSettingCard(
            "purefiction_enable",
            FIF.SPEED_HIGH,
            '허구 이야기 활성화',
            ""
        )
        self.purefictionLevelCard = PushSettingCardEval(
            '수정',
            FIF.MINIMIZE,
            "관문 범위",
            "purefiction_level"
        )
        self.purefictionTeamsCard = PushSettingCardTeamWithSwap(
            FIF.FLAG,
            "허구 이야기 파티 설정",
            "purefiction_team1",
            "purefiction_team2"
        )
        self.purefictionRunTimeCard = PushSettingCardDate(
            '수정',
            FIF.DATE_TIME,
            "마지막 허구 이야기 실행 시간",
            "purefiction_timestamp"
        )

        self.ApocalypticEnableCard = ExpandableSwitchSettingCard(
            "apocalyptic_enable",
            FIF.SPEED_HIGH,
            '종말의 환영 활성화',
            ""
        )
        self.ApocalypticLevelCard = PushSettingCardEval(
            '수정',
            FIF.MINIMIZE,
            "관문 범위",
            "apocalyptic_level"
        )
        self.ApocalypticTeamsCard = PushSettingCardTeamWithSwap(
            FIF.FLAG,
            "종말의 환영 파티 설정",
            "apocalyptic_team1",
            "apocalyptic_team2"
        )
        self.ApocalypticRunTimeCard = PushSettingCardDate(
            '수정',
            FIF.DATE_TIME,
            "마지막 종말의 환영 실행 시간",
            "apocalyptic_timestamp"
        )

        self.CloudGameGroup = SettingCardGroup(
            "클라우드 게임 설정",
            self.scrollWidget
        )
        self.cloudGameEnableCard = SwitchSettingCard1(
            FIF.SPEED_HIGH,
            "'클라우드·붕괴: 스타레일' 사용",
            "활성화 시, 클라우드·붕괴: 스타레일을 사용하여 개척력 소모 등의 자동화 작업을 수행합니다. 창 고정이 필요 없으며 백그라운드 실행이 가능합니다. (시뮬레이션 우주와 필드 토벌은 여전히 창 전체 화면 유지 필요)",
            "cloud_game_enable"
        )
        self.cloudGameFullScreenCard = SwitchSettingCard1(
            FIF.FULL_SCREEN,
            "전체 화면 실행",
            None,
            "cloud_game_fullscreen_enable"
        )
        self.cloudGameMaxQueueTimeCard = RangeSettingCard1(
            "cloud_game_max_queue_time",
            [1, 120],
            FIF.SPEED_MEDIUM,
            "최대 대기열 대기 시간 (분)",
            ''
        )
        # self.cloudGameVideoQualityCard = ComboBoxSettingCard2(
        #     "cloud_game_video_quality",
        #     FIF.VIDEO,
        #     "云游戏画质",
        #     None,
        #     texts={"超高清": "0", "高清": "1", "标清": "2", "低清": "3"}
        # )
        # self.cloudGameSmoothFirstCard = SwitchSettingCard1(
        #     FIF.SPEED_HIGH,
        #     "画面流畅优先",
        #     "启用这个选项后，当网速过慢时，会自动调低画质",
        #     "cloud_game_smooth_first_enable"
        # )
        # self.cloudGameShowStatusCard = SwitchSettingCardCloudGameStatus(
        #     FIF.INFO,
        #     "云游戏内显示网络状态",
        #     None,
        #     "cloud_game_status_bar_enable",
        #     "cloud_game_status_bar_type"
        # )
        self.browserTypeCard = ExpandableComboBoxSettingCard(
            "browser_type",
            FIF.GLOBE,
            "브라우저 유형",
            "기본값인 '통합 (Chrome For Testing)'을 유지하는 것을 권장합니다.",
            {"통합 (Chrome For Testing)": "integrated", "Chrome": "chrome", "Edge": "edge"}
        )
        self.browserDownloadUseMirrorCard = SwitchSettingCard1(
            FIF.CLOUD_DOWNLOAD,
            "브라우저 및 드라이버 다운로드 시 미러 사이트 사용",
            None,
            "browser_download_use_mirror"
        )
        self.browserPersistentCard = SwitchSettingCard1(
            FIF.DOWNLOAD,
            "브라우저 데이터 저장 (게임 로그인 상태 및 로컬 데이터)",
            None,
            "browser_persistent_enable"
        )
        self.browserScaleCard = ComboBoxSettingCard2(
            "browser_scale_factor",
            FIF.ZOOM,
            "브라우저 화면 배율 (DPI)",
            "1920x1080 해상도가 아닌 경우, 클라우드 게임 화면이 꽉 차지 않을 수 있습니다. 이 값을 조정하여 배율을 변경하세요.",
            texts={'50%': 0.5, '67%': 0.67, '75%': 0.75, '80%': 0.80, '90%': 0.90, '배율 없음 (100%)': 1.0,
                   '110%': 1.10, '125%': 1.25, '150%': 1.5, '175%': 1.75, '200%': 2.0}
        )
        self.browserLaunchArgCard = PushSettingCardEval(
            "수정",
            FIF.CODE,
            "브라우저 시작 매개변수",
            "browser_launch_argument"
        )
        self.browserHeadlessCard = SwitchSettingCard1(
            FIF.VIEW,
            "창 없는 모드 (백그라운드 실행)",
            "시뮬레이션 우주 및 필드 토벌 미지원",
            "browser_headless_enable"
        )
        # self.browserCookiesCard = SwitchSettingCard1(
        #     FIF.PALETTE,    # 这个画盘长得很像 Cookie
        #     "保存 Cookies（登录状态）",
        #     None,
        #     "browser_dump_cookies_enable"
        # )

        self.ProgramGroup = SettingCardGroup('프로그램 설정', self.scrollWidget)
        self.logLevelCard = ComboBoxSettingCardLog(
            "log_level",
            FIF.TAG,
            '로그 레벨',
            "",
            texts={'간결': 'INFO', '상세': 'DEBUG'}
        )
        self.gamePathCard = PushSettingCard(
            '수정',
            FIF.GAME,
            "게임 경로",
            cfg.game_path
        )
        self.updateViaLauncherEnableCard = ExpandableSwitchSettingCard(
            "update_via_launcher",
            FIF.UPDATE,
            '런처를 통한 게임 업데이트 [베타]',
            ""
        )
        self.launcherPathCard = PushSettingCard(
            '수정',
            FIF.GAME,
            "미호요 런처 경로",
            cfg.launcher_path
        )
        self.startGameTimeoutCard = RangeSettingCard1(
            "start_game_timeout",
            [10, 60],
            FIF.DATE_TIME,
            "게임 시작 타임아웃 (분)",
            "",
        )
        self.updateGameTimeoutCard = RangeSettingCard1(
            "update_game_timeout",
            [1, 24],
            FIF.DATE_TIME,
            "게임 업데이트 타임아웃 (시간)",
            "",
        )
        # self.importConfigCard = PushSettingCard(
        #     '导入',
        #     FIF.ADD_TO,
        #     '导入配置',
        #     '选择需要导入的 config.yaml 文件（重启后生效）'
        # )
        self.pauseAfterSuccess = SwitchSettingCard1(
            FIF.SYNC,
            '성공 후 프로그램 일시 정지',
            "체크 시, 반복 모드가 아니라면 실행 성공 후 프로그램을 일시 정지합니다.",
            "pause_after_success"
        )
        self.exitAfterFailure = SwitchSettingCard1(
            FIF.SYNC,
            '실패 후 즉시 종료',
            "체크 시, 실패하면 즉시 종료합니다. 체크하지 않으면 실패 후 일시 정지합니다.",
            "exit_after_failure"
        )
        self.afterFinishCard = ExpandableComboBoxSettingCard(
            "after_finish",
            FIF.POWER_BUTTON,
            '작업 완료 후',
            "'종료'는 게임 종료를 의미합니다. 반복 모드는 더 이상 권장되지 않으니 로그 인터페이스의 예약 작업 기능을 사용하세요.",
            texts={'없음': 'None', '게임 종료': 'Exit', '시스템 종료': 'Shutdown', '절전 모드': 'Sleep', '최대 절전 모드': 'Hibernate', '다시 시작': 'Restart', '로그아웃': 'Logoff', '모니터 끄기': 'TurnOffDisplay', '스크립트 실행': 'RunScript', '반복': 'Loop'}
        )
        self.loopModeCard = ComboBoxSettingCard2(
            "loop_mode",
            FIF.COMMAND_PROMPT,
            '반복 모드 (로그 화면의 예약 작업 기능을 사용하세요)',
            '',
            texts={'예약 작업': 'scheduled', '개척력 기준': 'power'}
        )
        self.scheduledCard = TimePickerSettingCard1(
            "scheduled_time",
            FIF.DATE_TIME,
            "예약 작업 시간",
        )
        self.powerLimitCard = RangeSettingCard1(
            "power_limit",
            [10, 300],
            FIF.HEART,
            "반복 실행 재시작 필요 개척력",
            "게임 갱신(새벽 4시)이 우선순위가 더 높음",
        )
        self.refreshHourEnableCard = RangeSettingCard1(
            "refresh_hour",
            [0, 23],
            FIF.DATE_TIME,
            "게임 갱신 시간",
            "반복 실행 및 임무 상태 판단에 사용, 기본값 새벽 4시",
        )
        self.ScriptPathCard = PushSettingCard(
            '수정',
            FIF.CODE,
            "스크립트 또는 프로그램 경로 (스크립트 실행 선택 시 유효)",
            cfg.script_path
        )
        self.playAudioCard = SwitchSettingCard1(
            FIF.ALBUM,
            '음성 알림',
            '작업 완료 후 열차장(폼폼)이 노래를 불러요!',
            "play_audio"
        )
        self.closeWindowActionCard = ComboBoxSettingCard2(
            "close_window_action",
            FIF.CLOSE,
            '창을 닫을 때',
            '창을 닫을 때의 기본 동작을 선택하거나, 닫을 때마다 대화 상자로 물어봅니다.',
            texts={'물어보기': 'ask', '트레이로 최소화': 'minimize', '프로그램 종료': 'close'}
        )

        self.NotifyGroup = SettingCardGroup("메시지 푸시", self.scrollWidget)
        self.testNotifyCard = ExpandablePushSettingCard(
            "테스트 메시지 푸시",
            FIF.RINGER,
            "",
            "메시지 전송"
        )
        self.notifyLevelCard = ComboBoxSettingCard2(
            "notify_level",
            FIF.COMMAND_PROMPT,
            '알림 레벨',
            '',
            texts={'모든 알림 푸시': 'all', '오류 알림만 푸시': 'error'}
        )
        self.notifyTemplateCard = PushSettingCardNotifyTemplate(
            '수정',
            FIF.FONT_SIZE,
            "메시지 푸시 형식",
            "notify_template"
        )

        self.notifyEnableGroup = []
        self.notifyLogoDict = {
            "winotify": FIF.BACK_TO_WINDOW,
            "telegram": FIF.AIRPLANE,
            "serverchanturbo": FIF.ROBOT,
            "serverchan3": FIF.ROBOT,
            # "bark": FIF.MAIL,
            "smtp": FIF.MAIL,
            # "dingtalk": FIF.MAIL,
            # "pushplus": FIF.MAIL,
            # "wechatworkapp": FIF.MAIL,
            # "wechatworkbot": FIF.MAIL,
            # "onebot": FIF.MAIL,
            # "gocqhttp": FIF.MAIL,
            # "gotify": FIF.MAIL,
            # "discord": FIF.MAIL,
            # "pushdeer": FIF.MAIL,
            # "lark": FIF.MAIL,
            # "custom": FIF.MAIL
        }
        self.notifySupportImage = ["telegram", "matrix", "smtp", "wechatworkapp", "wechatworkbot", "onebot", "gocqhttp", "lark", "custom"]

        for key, _ in cfg.config.items():
            if key.startswith("notify_") and key.endswith("_enable"):
                notifier_name = key[len("notify_"):-len("_enable")]

                notifyEnableCard = SwitchSettingCardNotify(
                    self.notifyLogoDict[notifier_name] if notifier_name in self.notifyLogoDict else FIF.MAIL,
                    self.tr(f'{notifier_name.capitalize()} 알림 활성화 {"(이미지 지원)"if notifier_name in self.notifySupportImage else ""}'),
                    notifier_name,
                    key
                )
                self.notifyEnableGroup.append(notifyEnableCard)

        self.MiscGroup = SettingCardGroup("기타", self.scrollWidget)
        self.autoBattleDetectEnableCard = SwitchSettingCard1(
            FIF.ROBOT,
            '자동 전투 감지 활성화',
            "게임 시작 전 레지스트리 또는 로컬 저장을 수정하여 자동 전투를 켜고, 개척력 소모, 화폐 전쟁, 빛 따라 금 찾아 장면에서 자동 전투 상태를 감지하고 유지합니다.",
            "auto_battle_detect_enable"
        )
        self.autoSetResolutionEnableCard = SwitchSettingCard1(
            FIF.FULL_SCREEN,
            '해상도 자동 수정 및 자동 HDR 끄기 활성화',
            "소프트웨어로 게임 실행 시 자동으로 1920x1080 해상도로 수정하고 자동 HDR을 끕니다. 수동 실행에는 영향을 주지 않습니다. (국제 서버 및 중국 서버 지원)",
            "auto_set_resolution_enable"
        )
        self.autoSetGamePathEnableCard = SwitchSettingCard1(
            FIF.GAME,
            '게임 경로 자동 설정 활성화',
            "바로가기, 공식 런처, 실행 중인 게임 프로세스 등을 통해 게임 경로 자동 설정을 시도합니다. (국제 서버 및 중국 서버 지원)",
            "auto_set_game_path_enable"
        )
        self.allScreensCard = SwitchSettingCard1(
            FIF.ZOOM,
            '다중 모니터에서 스크린샷 캡처',
            "기본값 켜짐. 다중 모니터 사용 중 스크린샷이 정상적으로 찍히지 않는 경우 이 옵션을 끄고 재시도하세요.",
            "all_screens"
        )
        self.StartMarch7thAssistantCard = StartMarch7thAssistantSwitchSettingCard(
            FIF.GAME,
            '사용자 로그인 시 시작 (부팅 시 실행)',
            "작업 스케줄러를 통해 부팅 후 자동으로 전체 실행 모드를 수행합니다. (비밀번호 입력 없이 자동 로그인되도록 컴퓨터를 설정해야 할 수 있음)"
        )
        self.hotkeyCard = SwitchSettingCardHotkey(
            FIF.SETTING,
            '단축키 수정',
            "비술, 지도, 워프, 작업 중지 등의 단축키 설정"
        )

        self.AboutGroup = SettingCardGroup('정보', self.scrollWidget)
        self.githubCard = PrimaryPushSettingCard(
            '프로젝트 홈페이지',
            FIF.GITHUB,
            '프로젝트 홈페이지',
            "https://github.com/moesnow/March7thAssistant"
        )
        self.qqGroupCard = PrimaryPushSettingCard(
            '그룹 채팅 참여',
            FIF.EXPRESSIVE_INPUT_ENTRY,
            'QQ 그룹',
            ""
        )
        self.feedbackCard = PrimaryPushSettingCard(
            '피드백 보내기',
            FIF.FEEDBACK,
            '피드백 보내기',
            'March7thAssistant 개선을 도와주세요'
        )
        self.aboutCard = PrimaryPushSettingCard(
            '업데이트 확인',
            FIF.INFO,
            '정보',
            '현재 버전: ' + " " + cfg.version
        )
        self.updateSourceCard = ExpandableComboBoxSettingCardUpdateSource(
            "update_source",
            FIF.SPEED_HIGH,
            '업데이트 소스',
            self.parent,
            "",
            texts={'해외 소스': 'GitHub', 'MirrorChyan': 'MirrorChyan'}
        )
        self.checkUpdateCard = SwitchSettingCard1(
            FIF.SYNC,
            '시작 시 업데이트 확인',
            "",
            "check_update"
        )
        self.updatePrereleaseEnableCard = SwitchSettingCard1(
            FIF.TRAIN,
            '미리보기(Preview) 업데이트 채널 참여',
            "",
            "update_prerelease_enable"
        )
        self.updateFullEnableCard = SwitchSettingCard1(
            FIF.GLOBE,
            '업데이트 시 전체 패키지 다운로드',
            "업데이트에 의존성 구성 요소가 포함됩니다. 켜두는 것을 권장합니다. 끄면 의존성 구성 요소를 직접 업데이트해야 하며, 예상치 못한 오류가 발생할 수 있습니다.",
            "update_full_enable"
        )
        self.mirrorchyanCdkCard = PushSettingCardMirrorchyan(
            '수정',
            FIF.BOOK_SHELF,
            "MirrorChyan CDK",
            self.parent,
            "mirrorchyan_cdk"
        )

    def __initLayout(self):
        self.settingLabel.move(36, 30)
        self.pivot.move(40, 80)
        # self.title_area.move(36, 80)
        # self.vBoxLayout.addWidget(self.pivot, 0, Qt.AlignTop)
        self.vBoxLayout.addWidget(self.stackedWidget, 0, Qt.AlignTop)
        self.vBoxLayout.setContentsMargins(36, 0, 36, 0)

        self.PowerGroup.addSettingCard(self.powerPlanCard)
        self.PowerGroup.addSettingCard(self.instanceTypeCard)
        # self.PowerGroup.addSettingCard(self.calyxGoldenPreferenceCard)
        self.PowerGroup.addSettingCard(self.instanceTypeCard)
        self.instanceTypeCard.addSettingCards([
            self.instanceNameCard,
            self.instanceTeamEnableCard,
            self.tpBeforeInstanceEnableCard,
            self.useReservedTrailblazePowerEnableCard,
            self.useFuelEnableCard,
            self.breakDownLevelFourRelicsetEnableCard,
            self.mergeImmersifierEnableCard,
            self.instanceNameChallengeCountCard
        ])
        self.PowerGroup.addSettingCard(self.borrowEnableCard)
        # 将子卡片添加到 borrowEnableCard 的可展开区域
        self.borrowEnableCard.addSettingCards([
            self.borrowCharacterEnableCard,
            self.borrowFriendsCard,
            self.borrowScrollTimesCard
        ])
        # self.PowerGroup.addSettingCard(self.maxCalyxPerRoundNumOfAttempts)
        self.PowerGroup.addSettingCard(self.buildTargetEnableCard)
        self.buildTargetEnableCard.addSettingCards([
            self.buildTargetPlanarOrnamentWeeklyCountCard
        ])
        self.PowerGroup.addSettingCard(self.echoofwarEnableCard)
        self.echoofwarEnableCard.addSettingCards([
            self.echoofwarRunTimeCard
        ])
        # self.PowerGroup.addSettingCard(self.echoofwarStartDayOfWeekCard)
        # self.BorrowGroup.addSettingCard(self.borrowCharacterFromCard)
        # self.BorrowGroup.addSettingCard(self.borrowCharacterInfoCard)
        # self.BorrowGroup.addSettingCard(self.borrowCharacterCard)

        self.DailyGroup.addSettingCard(self.dailyEnableCard)
        self.dailyEnableCard.addSettingCards([
            self.dailyMaterialEnableCard,
            # self.dailyHimekoTryEnableCard,
            self.dailyMemoryOneEnableCard,
            self.dailyMemoryOneTeamCard,
            self.lastRunTimeCard
        ])
        self.DailyGroup.addSettingCard(self.activityEnableCard)
        self.activityEnableCard.addSettingCards([
            self.activityDailyCheckInEnableCard,
            self.activityGardenOfPlentyEnableCard,
            self.activityRealmOfTheStrangeEnableCard,
            self.activityPlanarFissureEnableCard
        ])
        self.DailyGroup.addSettingCard(self.rewardEnableCard)
        self.rewardEnableCard.addSettingCards([
            self.dispatchEnableCard,
            self.mailEnableCard,
            self.assistEnableCard,
            self.questEnableCard,
            self.srpassEnableCard,
            self.redemptionEnableCard,
            self.achievementEnableCard
        ])

        self.CurrencywarsGroup.addSettingCard(self.currencywarsEnableCard)
        self.CurrencywarsGroup.addSettingCard(self.currencywarsTypeCard)
        self.CurrencywarsGroup.addSettingCard(self.currencywarsRunTimeCard)

        self.UniverseGroup.addSettingCard(self.weeklyDivergentEnableCard)
        self.weeklyDivergentEnableCard.addSettingCards([
            self.weeklyDivergentTypeCard,
            self.weeklyDivergentRunTimeCard
        ])
        self.UniverseGroup.addSettingCard(self.universeEnableCard)
        self.universeEnableCard.addSettingCards([
            self.universeCategoryCard,
            self.divergentTypeCard,
            self.universeFrequencyCard,
            self.universeCountCard,
            self.universeFateCard,
            self.universeDifficultyCard,
            self.universeOperationModeCard,
            self.universeTimeoutCard,
            self.universeRunTimeCard,
        ])
        self.UniverseGroup.addSettingCard(self.divergentTeamTypeCard)
        self.UniverseGroup.addSettingCard(self.universeBonusEnableCard)
        self.UniverseGroup.addSettingCard(self.universeDisableGpuCard)

        self.FightGroup.addSettingCard(self.fightEnableCard)
        self.fightEnableCard.addSettingCards([
            self.fightOperationModeCard,
            self.fightTimeoutCard,
            self.FightRunTimeCard,
        ])
        self.FightGroup.addSettingCard(self.fightTeamEnableCard)
        # self.FightGroup.addSettingCard(self.fightTeamNumberCard)
        self.FightGroup.addSettingCard(self.fightAllowMapBuyCard)
        self.FightGroup.addSettingCard(self.fightAllowSnackBuyCard)
        self.FightGroup.addSettingCard(self.fightMainMapCard)

        self.ImmortalGameGroup.addSettingCard(self.forgottenhallEnableCard)
        self.forgottenhallEnableCard.addSettingCards([
            self.forgottenhallLevelCard,
            self.forgottenhallTeamsCard,
            self.forgottenhallRunTimeCard
        ])

        self.ImmortalGameGroup.addSettingCard(self.purefictionEnableCard)
        self.purefictionEnableCard.addSettingCards([
            self.purefictionLevelCard,
            self.purefictionTeamsCard,
            self.purefictionRunTimeCard
        ])

        self.ImmortalGameGroup.addSettingCard(self.ApocalypticEnableCard)
        self.ApocalypticEnableCard.addSettingCards([
            self.ApocalypticLevelCard,
            self.ApocalypticTeamsCard,
            self.ApocalypticRunTimeCard
        ])

        self.CloudGameGroup.addSettingCard(self.cloudGameEnableCard)
        self.CloudGameGroup.addSettingCard(self.browserTypeCard)
        self.browserTypeCard.addSettingCards([
            self.browserDownloadUseMirrorCard,
            self.browserPersistentCard,
            self.browserScaleCard,
            self.browserLaunchArgCard
        ])
        self.CloudGameGroup.addSettingCard(self.cloudGameFullScreenCard)
        self.CloudGameGroup.addSettingCard(self.browserHeadlessCard)
        self.CloudGameGroup.addSettingCard(self.cloudGameMaxQueueTimeCard)
        # self.CloudGameGroup.addSettingCard(self.cloudGameVideoQualityCard)
        # self.CloudGameGroup.addSettingCard(self.cloudGameSmoothFirstCard)
        # self.CloudGameGroup.addSettingCard(self.cloudGameShowStatusCard)
        # self.CloudGameGroup.addSettingCard(self.browserCookiesCard)
        # self.CloudGameGroup.addSettingCard(self.browserPersistentCard)
        # self.CloudGameGroup.addSettingCard(self.browserScaleCard)
        # self.CloudGameGroup.addSettingCard(self.browserLaunchArgCard)

        self.ProgramGroup.addSettingCard(self.logLevelCard)
        self.ProgramGroup.addSettingCard(self.gamePathCard)
        self.ProgramGroup.addSettingCard(self.updateViaLauncherEnableCard)
        self.updateViaLauncherEnableCard.addSettingCards([
            self.launcherPathCard,
            self.updateGameTimeoutCard
        ])
        self.ProgramGroup.addSettingCard(self.startGameTimeoutCard)
        # self.ProgramGroup.addSettingCard(self.importConfigCard)
        self.ProgramGroup.addSettingCard(self.pauseAfterSuccess)
        self.ProgramGroup.addSettingCard(self.exitAfterFailure)
        self.ProgramGroup.addSettingCard(self.afterFinishCard)
        self.afterFinishCard.addSettingCards([
            self.loopModeCard,
            self.scheduledCard,
            self.powerLimitCard,
            self.refreshHourEnableCard,
            self.ScriptPathCard
        ])
        self.ProgramGroup.addSettingCard(self.playAudioCard)
        self.ProgramGroup.addSettingCard(self.closeWindowActionCard)

        self.NotifyGroup.addSettingCard(self.testNotifyCard)
        self.testNotifyCard.addSettingCards([
            self.notifyLevelCard,
            self.notifyTemplateCard
        ])
        for value in self.notifyEnableGroup:
            self.NotifyGroup.addSettingCard(value)

        self.MiscGroup.addSettingCard(self.autoBattleDetectEnableCard)
        self.MiscGroup.addSettingCard(self.autoSetResolutionEnableCard)
        self.MiscGroup.addSettingCard(self.autoSetGamePathEnableCard)
        self.MiscGroup.addSettingCard(self.allScreensCard)
        self.MiscGroup.addSettingCard(self.StartMarch7thAssistantCard)
        self.MiscGroup.addSettingCard(self.hotkeyCard)

        self.AboutGroup.addSettingCard(self.githubCard)
        self.AboutGroup.addSettingCard(self.qqGroupCard)
        self.AboutGroup.addSettingCard(self.feedbackCard)
        self.AboutGroup.addSettingCard(self.aboutCard)
        self.AboutGroup.addSettingCard(self.updateSourceCard)
        self.updateSourceCard.addSettingCards([
            self.checkUpdateCard,
            self.updatePrereleaseEnableCard,
            self.updateFullEnableCard
        ])
        self.AboutGroup.addSettingCard(self.mirrorchyanCdkCard)

        self.addSubInterface(self.PowerGroup, 'PowerInterface', '개척력')
        # self.addSubInterface(self.BorrowGroup, 'BorrowInterface', '지원')
        self.addSubInterface(self.DailyGroup, 'DailyInterface', '일일')
        self.addSubInterface(self.CurrencywarsGroup, 'CurrencywarsInterface', '화폐 전쟁')
        self.addSubInterface(self.UniverseGroup, 'UniverseInterface', '차분화 우주')
        self.addSubInterface(self.FightGroup, 'FightInterface', '필드 토벌')
        self.addSubInterface(self.ImmortalGameGroup, 'ImmortalGameInterface', '빛 따라 금 찾아')

        self.pivot.addItem(
            routeKey='verticalBar',
            text="|",
            onClick=lambda: self.pivot.setCurrentItem(self.stackedWidget.currentWidget().objectName()),
        )

        self.addSubInterface(self.ProgramGroup, 'programInterface', '프로그램')
        self.addSubInterface(self.CloudGameGroup, "cloudGameInterface", '클라우드')
        self.addSubInterface(self.NotifyGroup, 'NotifyInterface', '알림')
        self.addSubInterface(self.MiscGroup, 'KeybindingInterface', '기타')
        self.addSubInterface(
            accounts_interface(self.tr, self.scrollWidget),
            'AccountsInterface',
            '계정'
        )
        self.addSubInterface(self.AboutGroup, 'AboutInterface', '정보')

        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.pivot.setCurrentItem(self.stackedWidget.currentWidget().objectName())
        self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height())

    def __connectSignalToSlot(self):
        # self.importConfigCard.clicked.connect(self.__onImportConfigCardClicked)
        self.gamePathCard.clicked.connect(self.__onGamePathCardClicked)
        self.launcherPathCard.clicked.connect(self.__onLauncherPathCardClicked)
        self.ScriptPathCard.clicked.connect(self.__onScriptPathCardClicked)
        # self.borrowCharacterInfoCard.clicked.connect(self.__openCharacterFolder())

        self.testNotifyCard.clicked.connect(lambda: start_task("notify"))

        self.afterFinishCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)

        self.githubCard.clicked.connect(self.__openUrl("https://github.com/moesnow/March7thAssistant"))
        self.qqGroupCard.clicked.connect(self.__openUrl("https://qm.qq.com/q/C3IryUWCQw"))
        self.feedbackCard.clicked.connect(self.__openUrl("https://github.com/moesnow/March7thAssistant/issues"))

        self.aboutCard.clicked.connect(lambda: checkUpdate(self.parent))

        # 连接可展开卡片的展开状态改变信号，在动画前调整 stackedWidget 高度
        self.borrowEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.buildTargetEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.dailyEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.activityEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.rewardEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.fightEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.weeklyDivergentEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.universeEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.forgottenhallEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.purefictionEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.ApocalypticEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.updateViaLauncherEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.updateSourceCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.testNotifyCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.instanceTypeCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.echoofwarEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.browserTypeCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)

    def addSubInterface(self, widget: QLabel, objectName, text):
        def remove_spacing(layout):
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if isinstance(item, QSpacerItem):
                    layout.removeItem(item)
                    break

        remove_spacing(widget.vBoxLayout)
        widget.titleLabel.setHidden(True)

        widget.setObjectName(objectName)
        self.stackedWidget.addWidget(widget)
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget)
        )

    def onCurrentIndexChanged(self, index):
        widget = self.stackedWidget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())

        self.verticalScrollBar().setValue(0)
        self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height())

    # def __onImportConfigCardClicked(self):
    #     configdir, _ = QFileDialog.getOpenFileName(self, "选取配置文件", "./", "Config Files (*.yaml)")
    #     if (configdir != ""):
    #         cfg._load_config(configdir)
    #         cfg.save_config()
    #         self.__showRestartTooltip()

    def __onGamePathCardClicked(self):
        game_path, _ = QFileDialog.getOpenFileName(self, "게임 경로 선택", "", "All Files (*)")
        if not game_path or cfg.game_path == game_path:
            return
        cfg.set_value("game_path", game_path)
        self.gamePathCard.setContent(game_path)

    def __onLauncherPathCardClicked(self):
        launcher_path, _ = QFileDialog.getOpenFileName(self, "미호요 런처 경로 선택", "", "All Files (*)")
        if not launcher_path or cfg.launcher_path == launcher_path:
            return
        cfg.set_value("launcher_path", launcher_path)
        self.launcherPathCard.setContent(launcher_path)

    # def __openCharacterFolder(self):
    #     return lambda: os.startfile(os.path.abspath("./assets/images/share/character"))

    def __openUrl(self, url):
        return lambda: QDesktopServices.openUrl(QUrl(url))

    # def __showRestartTooltip(self):
    #     InfoBar.success(
    #         '更新成功',
    #         '配置在重启软件后生效',
    #         duration=1500,
    #         parent=self
    #     )
    def __onScriptPathCardClicked(self):
        script_path, _ = QFileDialog.getOpenFileName(self, "스크립트 또는 프로그램 경로", "", "스크립트 또는 실행 파일 (*.ps1 *.bat *.exe)")
        if not script_path or cfg.script_path == script_path:
            return
        cfg.set_value("script_path", script_path)
        self.ScriptPathCard.setContent(script_path)

    def __onExpandableCardStateChanged(self, is_expanding: bool):
        """可展开卡片状态改变时，调整 stackedWidget 高度以包含子卡片"""
        # 获取发送信号的卡片对象
        sender_card = self.sender()

        # 根据展开的卡片获取其 viewLayout 的高度
        if sender_card:
            card_weight = sender_card.viewLayout.sizeHint().height()
        else:
            # 如果无法获取发送者，使用默认高度（向后兼容）
            card_weight = 0

        # 在动画执行前调整 stackedWidget 高度
        if is_expanding:
            self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height() + card_weight)
        else:
            self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height())
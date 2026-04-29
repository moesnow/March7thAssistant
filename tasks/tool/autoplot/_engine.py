"""
自动对话模块 — 核心引擎。

AutoPlot 是整个自动对话功能的主控制器，负责：
- 管理运行状态与生命周期（启动 / 停止 / 配置更新）
- 通过定时器轮询游戏窗口状态
- 协调场景检测与点击执行
- 核心策略：检测 continue 箭头，出现即代表对话文本已展示完毕，点击推进

架构说明：
    AutoPlot (QObject)          ← 主控制器，持有 QTimer
        ├── SceneDetector       ← 静态方法，场景识别
        └── _dialog_loop()      ← 对话点击循环（检测 Continue + 跳过 + 选项）

会话隔离机制：
    使用递增的 _dialog_session 计数器来取消过期的延迟回调。
    每次进入/退出对话场景时计数器递增，回调执行前检查 session
    是否匹配，不匹配则忽略（防止旧回调干扰新对话）。
"""

from __future__ import annotations

import time
from typing import Callable

import pygetwindow as gw
from PySide6.QtCore import QObject, QTimer

from module.automation import auto
from module.config import cfg
from module.logger import log

from ._config import (
    EngineState,
    Crop,
    Img,
    Threshold,
    Defaults,
)
from ._detector import SceneDetector


class AutoPlot(QObject):
    """自动对话引擎。

    使用方式:
        engine = AutoPlot(game_title_name)
        engine.update_options({...})   # 配置选项
        engine.start()                 # 启动
        engine.stop()                  # 停止

    信号:
        本类不直接发射信号；状态变化通过 log 输出。
        调用方可通过 is_running 属性查询运行状态。
    """

    # ========================================================================
    # 构造与初始化
    # ========================================================================

    def __init__(self, game_title_name: str) -> None:
        """初始化自动对话引擎。

        参数:
            game_title_name: 游戏窗口标题，用于判断窗口是否处于前台。
        """
        super().__init__()

        # --- 外部依赖 ---
        self._game_title_name: str = game_title_name

        # --- 运行状态 ---
        self.is_running: bool = False
        """外部可读：引擎是否已启动"""
        self._state: EngineState = EngineState.IDLE
        """内部状态机"""

        # --- 会话隔离 ---
        self._dialog_session: int = 0
        """递增计数器，用于取消过期的延迟回调"""

        # --- 自动战斗冷却 ---
        self._last_auto_battle_check: float = 0.0
        """上次检测自动战斗的时间戳（monotonic 秒）"""

        # --- 可配置选项（有默认值，可通过 update_options 覆盖）---
        self.auto_skip: bool = Defaults.AUTO_SKIP
        self.auto_click: bool = Defaults.AUTO_CLICK
        self.auto_battle_detect_enable: bool = Defaults.AUTO_BATTLE_DETECT
        self.auto_phone_detect_enable: bool = Defaults.AUTO_PHONE_DETECT

        # --- 定时器 ---
        self._monitor_timer = QTimer(self)
        self._monitor_timer.timeout.connect(self._monitor_loop)

    # ========================================================================
    # 公共 API：生命周期管理
    # ========================================================================

    def start(self) -> None:
        """启动自动对话引擎。

        启动 500ms 间隔的监控定时器，开始检测游戏窗口和对话场景。
        重复调用无副作用。
        """
        if self.is_running:
            return

        self.is_running = True
        self._transition_to(EngineState.MONITORING)
        self._invalidate_session()
        log.info("自动对话已启动")
        self._monitor_timer.start(Threshold.MONITOR_INTERVAL)

    def stop(self) -> None:
        """停止自动对话引擎。

        停止定时器，取消所有待执行的延迟回调（通过递增 session），
        重置内部状态。重复调用无副作用。
        """
        if not self.is_running:
            return

        self.is_running = False
        self._monitor_timer.stop()
        self._invalidate_session()
        self._transition_to(EngineState.IDLE)
        log.info("自动对话已停止")

    # ========================================================================
    # 公共 API：配置
    # ========================================================================

    def update_options(self, options: dict) -> None:
        """更新引擎配置选项。

        可在引擎运行中动态调用，新配置立即生效。
        仅更新传入的键，未传入的键保持原值。

        参数:
            options: 配置字典，支持的键：
                - auto_skip: bool
                - auto_click: bool
                - auto_battle_detect_enable: bool
        """
        if 'auto_skip' in options:
            self.auto_skip = bool(options['auto_skip'])
        if 'auto_click' in options:
            self.auto_click = bool(options['auto_click'])
        if 'auto_battle_detect_enable' in options:
            self.auto_battle_detect_enable = bool(options['auto_battle_detect_enable'])
        if 'auto_phone_detect_enable' in options:
            self.auto_phone_detect_enable = bool(options['auto_phone_detect_enable'])

        log.debug(f"自动对话配置已更新: {options}")

    # ========================================================================
    # 内部：状态管理
    # ========================================================================

    def _transition_to(self, new_state: EngineState) -> None:
        """状态迁移（目前仅用于日志追踪）。"""
        self._state = new_state

    def _invalidate_session(self) -> int:
        """使当前会话失效，取消所有待执行的延迟回调。

        返回:
            新的 session 值。
        """
        self._dialog_session += 1
        return self._dialog_session

    def _is_session_valid(self, session: int) -> bool:
        """检查给定的 session 是否仍然有效。

        对话活跃状态包括 DIALOG_ACTIVE 和 WAITING_OPTION（暂停等待用户选择）。
        """
        return (
            self.is_running
            and self._state in (EngineState.DIALOG_ACTIVE, EngineState.WAITING_OPTION)
            and session == self._dialog_session
        )

    # ========================================================================
    # 内部：延迟回调调度
    # ========================================================================

    def _schedule(self, delay_ms: int, callback: Callable[[int], None], session: int) -> None:
        """安排在 delay_ms 毫秒后执行回调，自动绑定 session 有效性检查。

        参数:
            delay_ms: 延迟毫秒数。
            callback: 签名为 callback(session: int) -> None 的回调。
            session: 当前会话标识，回调执行前会验证是否匹配。
        """

        def _guarded() -> None:
            if not self._is_session_valid(session):
                return
            callback(session)

        QTimer.singleShot(delay_ms, _guarded)

    # ========================================================================
    # 内部：窗口激活检测
    # ========================================================================

    def _is_game_window_active(self) -> bool:
        """检查游戏窗口是否处于前台激活状态。

        返回:
            True  游戏窗口在前台
            False 游戏窗口不在前台或未找到
        """
        windows = gw.getWindowsWithTitle(self._game_title_name)
        if not windows:
            return False
        return windows[0].isActive

    # ========================================================================
    # 监控主循环（每 500ms 触发一次）
    # ========================================================================

    def _monitor_loop(self) -> None:
        """监控定时器回调：主状态机入口。

        逻辑概览:
        1. 检查游戏窗口是否激活
           - 未激活 → 停止对话点击，等待下次轮询
        2. 检测是否处于对话场景
           - 是 → 启动对话点击循环
           - 否 → 执行非对话场景的辅助操作（自动战斗、手机页面等）
        """
        if not self.is_running:
            return

        # 1. 窗口激活检查
        window_active = self._is_game_window_active()
        if not window_active:
            if self._state in (EngineState.DIALOG_ACTIVE, EngineState.WAITING_OPTION):
                self._invalidate_session()
                self._transition_to(EngineState.MONITORING)
            return

        # 2. 对话场景检测 → 启动或停止对话循环
        if SceneDetector.is_dialog_scene():
            # 仅在尚未进入对话状态时启动新的对话循环
            if self._state not in (EngineState.DIALOG_ACTIVE, EngineState.WAITING_OPTION):
                self._transition_to(EngineState.DIALOG_ACTIVE)
                session = self._invalidate_session()
                self._schedule(
                    Threshold.DIALOG_LOOP_INITIAL_DELAY,
                    self._dialog_loop,
                    session,
                )
        else:
            # 非对话场景：如果之前在对话中（包括等待选项），则退出
            if self._state in (EngineState.DIALOG_ACTIVE, EngineState.WAITING_OPTION):
                self._invalidate_session()
                self._transition_to(EngineState.MONITORING)

            # 3. 非对话场景下的辅助操作
            self._handle_non_dialog_actions()

    # ========================================================================
    # 非对话场景辅助操作
    # ========================================================================

    def _handle_non_dialog_actions(self) -> None:
        """在非对话场景中执行辅助操作。

        按优先级：
        1. 自动战斗检测（10 秒冷却）
        2. 手机对话页面检测与关闭
        3. 通用关闭按钮
        """
        # 1. 自动战斗检测（带 10 秒冷却）
        if self.auto_battle_detect_enable and SceneDetector.is_auto_battle_off():
            now = time.monotonic()
            if now - self._last_auto_battle_check >= Threshold.AUTO_BATTLE_COOLDOWN:
                log.info("尝试开启自动战斗")
                auto.press_key(cfg.get_value("hotkey_auto_battle", "v"))
                self._last_auto_battle_check = now

        # 2. 手机对话页面（可通过开关控制）
        if self.auto_phone_detect_enable:
            SceneDetector.handle_phone_dialogs()

        # 3. 通用关闭
        SceneDetector.click_close()

    # ========================================================================
    # 对话点击循环
    # ========================================================================

    def _dialog_loop(self, session: int) -> None:
        """对话点击循环：检测 continue 箭头并点击推进对话。

        核心逻辑：
            Img.CONTINUE（continue 箭头）出现 = 对话文本已展示完毕，
            点击该位置即可推进到下一段对话。

        执行顺序：
        1. 若 auto_click 关闭且存在对话选项 → 暂停等待用户选择
        2. 若 auto_skip 开启 → 检测并点击跳过按钮
        3. 点击对话选项（如有）
        4. 检测 continue 箭头 → 点击推进（核心步骤）
        5. 调度下一次循环
        """
        if not self._is_session_valid(session):
            return

        # --- 1. 对话选项检测 ---
        # 若用户选择不自动选择对话选项，则检测到选项时暂停
        if not self.auto_click:
            if SceneDetector.has_dialog_options():
                log.debug("根据设置，暂停点击以等待用户选择对话选项")
                self._transition_to(EngineState.WAITING_OPTION)
                self._schedule(Threshold.MONITOR_INTERVAL, self._dialog_loop, session)
                return
            # 恢复为对话活跃状态（可能在之前被设为 WAITING_OPTION）
            if self._state == EngineState.WAITING_OPTION:
                self._transition_to(EngineState.DIALOG_ACTIVE)

        # --- 2. 跳过按钮检测 ---
        if self.auto_skip and SceneDetector.detect_skip_button():
            # 跳过成功后会弹出确认框，尝试点击确认
            if not SceneDetector.click_confirm():
                # 确认点击失败，移动鼠标避免干扰下次匹配
                SceneDetector.move_mouse_to_click_pos()
            self._schedule(Threshold.MONITOR_INTERVAL, self._dialog_loop, session)
            return

        # --- 3. 点击对话选项推进（优先 SELECT，不存在则尝试 EXIT）---
        SceneDetector.click_dialog_option()

        # --- 4. 核心：检测 continue 箭头并点击推进 ---
        # continue 箭头出现代表文本已展示完毕，点击推进到下一段
        if auto.click_element(
            Img.CONTINUE, "image", Threshold.CONTINUE_MATCH,
            crop=Crop.DIALOG_CONTINUE,
            action="down"
        ):
            # 短暂延迟确保游戏接收到按下事件
            time.sleep(0.2)
            # 鼠标释放
            auto.mouse_up()
            log.debug("检测到 continue 箭头，点击推进对话")

        # --- 5. 调度下一次循环 ---
        self._schedule(Threshold.DIALOG_LOOP_INTERVAL, self._dialog_loop, session)

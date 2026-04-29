"""
自动对话模块 — 常量、枚举与配置定义。

本模块集中管理所有裁剪区域、图片路径、阈值等"魔法数字"，
避免散落在业务逻辑中，便于调整分辨率适配参数和维护。
"""

from __future__ import annotations

from enum import Enum


# ============================================================================
# 枚举定义
# ============================================================================

class EngineState(Enum):
    """自动对话引擎的内部运行状态"""
    IDLE = "idle"                       # 未启动
    MONITORING = "monitoring"           # 监控中，等待进入对话场景
    DIALOG_ACTIVE = "dialog_active"     # 对话中，正在执行点击循环
    WAITING_OPTION = "waiting_option"   # 暂停点击，等待用户手动选择对话选项


# ============================================================================
# 裁剪区域常量 (基于 1920×1080 参考分辨率，使用比例值)
# 元组格式: (x_ratio, y_ratio, width_ratio, height_ratio)
# ============================================================================

class Crop:
    """截图裁剪区域的比例定义。

    所有坐标以 1920×1080 为基准分辨率的比例表示。
    实际像素 = 比例 × 当前屏幕宽/高。
    """

    # --- 对话场景检测 ---
    # 左上角区域：用于检测 start / start_ps5 / start_xbox 图标
    DIALOG_START: tuple[float, float, float, float] = (
        122.0 / 1920, 31.0 / 1080, 98.0 / 1920, 58.0 / 1080,
    )

    # 底部中央：continue 箭头图标
    DIALOG_CONTINUE: tuple[float, float, float, float] = (
        941.0 / 1920, 994.0 / 1080, 37.0 / 1920, 46.0 / 1080,
    )

    # 右上角：hide（隐藏UI）按钮
    DIALOG_HIDE: tuple[float, float, float, float] = (
        1801.0 / 1920, 47.0 / 1080, 36.0 / 1920, 25.0 / 1080,
    )

    # 右侧：对话选项区域
    DIALOG_OPTIONS: tuple[float, float, float, float] = (
        1290.0 / 1920, 442.0 / 1080, 74.0 / 1920, 400.0 / 1080,
    )

    # --- 跳过按钮 ---
    # 右上角：跳过按钮 YOLO 检测区域
    SKIP_BUTTON: tuple[float, float, float, float] = (
        1506 / 1920, 36 / 1080, 400 / 1920, 47 / 1080,
    )

    # --- 自动战斗检测 ---
    # 左下角：未开启自动战斗的图标
    NOT_AUTO: tuple[float, float, float, float] = (
        0.0 / 1920, 903.0 / 1080, 144.0 / 1920, 120.0 / 1080,
    )

    # --- 手机对话页面 ---
    # 手机消息区域（灰白色背景）
    PHONE_MSG: tuple[float, float, float, float] = (
        1146 / 1920, 694 / 1080, 610 / 1920, 51 / 1080,
    )
    # 另一种手机消息区域
    PHONE_MSG2: tuple[float, float, float, float] = (
        801 / 1920, 703 / 1080, 797 / 1920, 48 / 1080,
    )
    # 左上角白色小块（用于移动鼠标归位）
    WHITE_CORNER: tuple[float, float, float, float] = (
        6.0 / 1920, 5.0 / 1080, 12.0 / 1920, 14.0 / 1080,
    )
    # 关闭手机界面按钮
    CLOSE_PHONE: tuple[float, float, float, float] = (
        1542 / 1920, 186 / 1080, 259 / 1920, 86 / 1080,
    )

    # --- 通用点击位置 ---
    # 底部中央：推进对话的默认点击位置
    CLICK_POS: tuple[float, float, float, float] = (
        940 / 1920, 993 / 1080, 39 / 1920, 29 / 1080,
    )


# ============================================================================
# 图片路径常量
# ============================================================================

class Img:
    """模板图片与模型路径常量"""

    # 对话开始标识（键鼠 / PS5 / Xbox）
    START: tuple[str, ...] = (
        "./assets/images/share/plot/start.png",
        "./assets/images/share/plot/start_ps5.png",
        "./assets/images/share/plot/start_xbox.png",
    )

    # 对话中 continue 箭头
    CONTINUE: str = "./assets/images/share/plot/continue.png"

    # 隐藏 UI 按钮（右上角）
    HIDE: str = "./assets/images/share/plot/hide.png"

    # 对话选项相关
    SELECT: str = "./assets/images/share/plot/select.png"
    MESSAGE: str = "./assets/images/share/plot/message.png"
    EXIT: str = "./assets/images/share/plot/exit.png"
    PREV_PAGE: str = "./assets/images/share/plot/prev-page.png"

    # 检测对话选项存在的图片列表
    DIALOG_OPTIONS: tuple[str, ...] = (
        "./assets/images/share/plot/select.png",
        "./assets/images/share/plot/message.png",
        "./assets/images/share/plot/exit.png",
        "./assets/images/share/plot/prev-page.png",
    )

    # 跳过按钮 YOLO 模型
    SKIP_MODEL: dict = {
        "model_path": "./assets/model/skip.onnx",
        "names": ["skip"],
        "target_class": "skip",
    }

    # 自动战斗未开启标识
    NOT_AUTO: str = "./assets/images/share/base/not_auto.png"

    # 关闭手机界面
    CLOSE_PHONE: str = "./assets/images/share/plot/close_phone.png"

    # 通用关闭按钮
    CLICK_CLOSE: str = "./assets/images/zh_CN/base/click_close.png"

    # 确认按钮
    CONFIRM: str = "./assets/images/zh_CN/base/confirm.png"


# ============================================================================
# 阈值与计时常量
# ============================================================================

class Threshold:
    """匹配阈值与时间间隔常量"""

    # 模板匹配阈值
    START_MATCH: float = 0.9          # start / start_ps5 / start_xbox
    CONTINUE_MATCH: float = 0.9       # continue 箭头
    HIDE_MATCH: float = 0.8           # hide 按钮
    SELECT_MATCH: float = 0.9         # 对话选项
    DIALOG_OPTION_MATCH: float = 0.8  # 对话选项（检测是否存在）
    SKIP_YOLO: float = 0.25           # 跳过按钮 YOLO 阈值
    NOT_AUTO_MATCH: float = 0.8       # 未自动战斗图标
    CLOSE_PHONE_MATCH: float = 0.9    # 关闭手机按钮
    CLICK_CLOSE_MATCH: float = 0.8    # 通用关闭按钮
    CONFIRM_MATCH: float = 0.9        # 确认按钮

    # 手机消息区域 RGB 检测阈值
    PHONE_RGB: tuple[int, int, int] = (233, 233, 233)
    PHONE_RGB_RATIO: float = 0.6      # 手机消息区域颜色占比阈值
    PHONE2_RGB_RATIO: float = 0.65
    RGB_TOLERANCE: float = 0.01

    # 计时相关（毫秒）
    MONITOR_INTERVAL: int = 500       # 监控循环间隔（游戏窗口/对话场景检测）
    DIALOG_LOOP_INTERVAL: int = 200   # 对话循环轮询间隔（检测 continue 箭头的频率）
    DIALOG_LOOP_INITIAL_DELAY: int = 500  # 进入对话后首次循环延迟
    AUTO_BATTLE_COOLDOWN: float = 10.0  # 自动战斗检测冷却（秒）
    SKIP_WAIT_TIMEOUT: float = 1.0    # 跳过按钮消失等待超时（秒）
    SKIP_POLL_INTERVAL: float = 0.05  # 跳过按钮轮询间隔（秒）

    # 确认对话框重试
    CONFIRM_MAX_RETRIES: int = 30
    CONFIRM_RETRY_DELAY: float = 0.1


# ============================================================================
# 默认配置值
# ============================================================================

class Defaults:
    """AutoPlot 各选项的默认值"""
    AUTO_SKIP: bool = True
    AUTO_CLICK: bool = True
    AUTO_BATTLE_DETECT: bool = True
    AUTO_PHONE_DETECT: bool = True

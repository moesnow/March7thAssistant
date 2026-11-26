"""在游戏登录界面里切到目标账号的执行部分：截图、识别、点击。判断规则在 module/accounts/login_records.py。"""

import numpy as np

from module.accounts.login_records import RIGHT_BUTTONS, Line, LoginSwitch, find
from module.automation import auto
from module.logger import log
from module.ocr import ocr
from utils.pause import pause_ctl

DESIGN_WIDTH = 1920
# 选中的单选框是实心黄点，没选中只有灰色圆圈。
YELLOW_RATIO = 0.08
SCREENS = {
    "title": "标题页",
    "logout_dialog": "登出弹窗",
    "record_box": "登录框",
    "record_list": "登录记录列表",
    "welcome": "欢迎横幅",
    "logged_out": "未登录的标题页",
    "credentials": "账号密码或验证码登录页",
    "verification": "安全验证",
    "bilibili": "B 服登录",
    "other": "其他画面",
}


def _scale():
    """窗口宽度相对设计分辨率的倍数，和截图相对窗口的缩放。"""
    factor = auto.screenshot_scale_factor or 1
    return auto.screenshot_pos[2] / factor / DESIGN_WIDTH, factor


def frame():
    auto.take_screenshot()
    k, factor = _scale()
    auto.perform_ocr(raise_on_error=True)
    lines = []
    for box, (text, _confidence) in auto.ocr_result or []:
        (x1, y1), (x2, y2) = auto.calculate_text_position(box, True)
        lines.append(Line(text, x1 / k, y1 / k, (x2 - x1) / k, (y2 - y1) / k))
    if not (find(lines, "登出", RIGHT_BUTTONS, exact=True) or find(lines, "登入", RIGHT_BUTTONS, exact=True)):
        lines.extend(_right_buttons(k, factor))
    return lines


def _right_buttons(k, factor):
    """右侧按钮的字小，整图识别偶尔漏掉，裁出来放大两倍再认一次。"""
    scale = k * factor
    left, top, width, height = (round(value * scale) for value in RIGHT_BUTTONS)
    image = auto.screenshot.crop((left, top, left + width, top + height))
    image = image.resize((image.width * 2, image.height * 2))
    found = []
    for box, (text, _confidence) in ocr.recognize_multi_lines(np.array(image)) or []:
        (x1, y1), (x2, y2) = box[0], box[2]
        found.append(Line(text, (left + x1 / 2) / scale, (top + y1 / 2) / scale,
                          (x2 - x1) / 2 / scale, (y2 - y1) / 2 / scale))
    return found


def click(x, y):
    pause_ctl.checkpoint()
    k, _factor = _scale()
    left, top = auto.screenshot_pos[:2]
    point = (int(left + x * k), int(top + y * k))
    if auto.click_element_with_pos((point, point)) is False:
        raise RuntimeError("点击游戏登录界面失败")


def checked(keep, clear):
    """登出弹窗里「保留」「清除」两个单选框是否选中。圆点在两行文字左侧同一列。"""
    k, factor = _scale()
    scale = k * factor
    image = np.asarray(auto.screenshot.convert("RGB")).astype(int)
    left = min(keep.x, clear.x)

    def selected(line):
        x0, x1 = round((left - 30) * scale), round((left + 26) * scale)
        y0, y1 = round((line.cy - 14) * scale), round((line.cy + 14) * scale)
        region = image[max(y0, 0):y1, max(x0, 0):x1]
        if not region.size:
            return False
        red, green, blue = region[..., 0], region[..., 1], region[..., 2]
        return float(((red > 220) & (green > 160) & (blue < 150)).mean()) >= YELLOW_RATIO

    return selected(keep), selected(clear)


def game_login_switch(config):
    """按账号运行、并且在游戏登录框里切换时，返回这次启动用的切换流程，否则返回 None。"""
    layer = getattr(config, "_account_layer", None)
    mode = getattr(layer, "login_switch", None)
    if not isinstance(getattr(config, "bound_account", None), str) or mode not in ("logout", "keep"):
        return None
    row = layer.row
    allow_password = bool(row.get("auto_login")) and layer.store.password_status(layer.uid) == "saved"

    def expired():
        from module.accounts.runtime import mark_expired

        mark_expired(config)

    def trace(screen):
        log.info(f"游戏内切换账号：{SCREENS.get(screen, screen)}")

    if mode == "logout":
        log.info(f"启动后在游戏登录框里切换到「{row['name']}」（{row.get('login_hint') or '未填写登录记录'}）")
    return LoginSwitch(
        row.get("login_hint", ""),
        logout=mode == "logout",
        frame=frame,
        click=click,
        checked=checked,
        allow_password=allow_password,
        on_expired=expired,
        trace=trace,
    )

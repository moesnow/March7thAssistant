from module.screen import screen
from module.automation import auto
from module.config import cfg
from module.logger import log
from module.game import get_game_controller
from utils.color import red, green, yellow
import tasks.reward as reward
import pyperclip
import time
import json
import datetime
import sys
from typing import List, Dict, Optional
from module.notification import notif
from module.notification.notification import NotificationLevel


def load_codes(path: str) -> List[Dict]:
    """加载兑换码列表（来自 JSON 文件）。"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_codes_from_url(url: str) -> List[Dict]:
    """从指定 URL 加载兑换码列表（JSON 格式）。请求超时后重试最多 3 次；若仍失败，原样抛出异常。"""
    import requests
    from requests.exceptions import Timeout

    attempts = 0
    while True:
        try:
            response = requests.get(url, headers=cfg.useragent, timeout=10)
            response.raise_for_status()
            return response.json()
        except Timeout:
            attempts += 1
            if attempts >= 3:
                # 达到最大重试次数，原样抛出 Timeout 异常
                raise
            # 否则静默重试


def valid_codes_for_server(server: str, now: Optional[datetime.datetime] = None) -> List[str]:
    """
    返回指定服务器的未过期兑换码列表。
    expires_at 使用 ISO 8601 格式；为 null 表示不过期。
    """
    url = "https://m7a.top/assets/config/redemption_codes.json"
    path = "assets/config/redemption_codes.json"
    try:
        codes = load_codes_from_url(url)
    except Exception as e:
        log.warning(f"获取最新兑换码失败: {e}")
        codes = load_codes(path)

    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    res = []
    for c in codes:
        if c.get("server") != server:
            continue
        exp = c.get("expires_at")
        if exp is None:
            res.append(c.get("code"))
            continue
        if exp.endswith("Z"):
            exp = exp.replace("Z", "+00:00")
        try:
            dt = datetime.datetime.fromisoformat(exp)
        except ValueError:
            log.warning(f"无法解析过期时间: {exp}，跳过该兑换码")
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        if dt > now:
            res.append(c.get("code"))
    return res


class Redemption:
    @staticmethod
    def get():
        """尝试从本地或远程加载有效的兑换码，并兑换它们。"""
        log.hr("获取最新兑换码", 0)

        if sys.platform == 'win32':
            from utils.registry.star_rail_setting import get_server_by_registry
            server = get_server_by_registry()
            if server is None:
                log.error("无法判断游戏服务器类型，跳过兑换码任务")
                return False
        else:
            server = 'cn'  # 云游戏默认国服

        try:
            codes = valid_codes_for_server(server)
        except Exception as e:
            log.warning(f"获取兑换码失败: {e}")
            codes = []

        # 判断哪些兑换码是未使用过的
        try:
            used = cfg.already_used_codes
        except AttributeError:
            used = []
        if used is None:
            used = []
        codes = [code for code in codes if code not in used]

        if not codes:
            log.info("没有找到有效的兑换码")
            log.hr("完成", 2)
            return False

        log.info(f"当前服务器类型为{"国服" if server == "cn" else "国际服"}，找到{len(codes)}个有效兑换码，开始尝试兑换")
        log.hr("完成", 2)
        return Redemption.start(codes=codes, send_notification=True)

    @staticmethod
    def start(codes: Optional[List[str]] = None, send_notification: bool = False) -> bool:
        """使用给定的兑换码列表（若为 None，则使用配置中的 `cfg.redemption_code`）。"""
        log.hr("准备使用兑换码", 0)

        codes_to_use = cfg.redemption_code if codes is None else codes

        if not codes_to_use:
            log.error("兑换码列表为空, 跳过任务")
            return False

        # 将成功使用的兑换码加入已使用列表并保存配置
        try:
            used = cfg.already_used_codes
        except AttributeError:
            used = []
        if used is None:
            used = []

        successful_codes = []

        for idx, code in enumerate(codes_to_use, start=1):
            log.info(f"开始使用兑换码: {green(code)} ({idx}/{len(codes_to_use)})")
            screen.change_to('redemption')
            game = get_game_controller()
            game.copy(code)
            if auto.click_element("./assets/images/share/redemption/paste.png", "image", 0.9):
                time.sleep(0.5)
                if auto.find_element("./assets/images/share/redemption/clear.png", "image", 0.9):
                    time.sleep(0.5)
                    auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)
                    time.sleep(1)
                    if auto.find_element("兑换成功", "text"):
                        log.info(f"兑换码使用成功: {green(code)} ({idx}/{len(codes_to_use)})")
                        if code not in used:
                            used.append(code)
                            successful_codes.append(code)
                            cfg.set_value("already_used_codes", used)
                        auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)
                    elif auto.find_element(("兑换码已过期", "无效的兑换码", "兑换码已被使用"), "text", take_screenshot=False, include=True):
                        log.info(f"{auto.matched_text}: {yellow(code)} ({idx}/{len(codes_to_use)})")
                        if code not in used:
                            used.append(code)
                            cfg.set_value("already_used_codes", used)
                        auto.press_key("esc")
                    else:
                        log.error(f"兑换码使用失败: {red(code)} ({idx}/{len(codes_to_use)})")
                        auto.press_key("esc")
                    screen.wait_for_screen_change('menu')
                    time.sleep(3)

        if successful_codes:
            msg = f"成功使用了{len(successful_codes)}个兑换码: \n{'\n'.join(successful_codes)}"
            msg_parts = msg.split('\n')
            for part in msg_parts:
                if part.strip():  # 确保非空字符串
                    log.info(part.strip())
            if send_notification:
                notif.notify(content=msg, level=NotificationLevel.ALL)

            reward.start_specific("mail")
            log.hr("完成", 2)
            return True
        else:
            log.info("没有成功使用任何兑换码")
            log.hr("完成", 2)
            return False

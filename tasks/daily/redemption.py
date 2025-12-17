from module.screen import screen
from module.automation import auto
from module.config import cfg
from module.logger import log
from utils.color import red, green, yellow
import tasks.reward as reward
import pyperclip
import time
import json
import datetime
from typing import List, Dict, Optional
from utils.registry.star_rail_setting import get_server_by_registry


def load_codes(path: str) -> List[Dict]:
    """加载兑换码列表（来自 JSON 文件）。"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_codes_from_url(url: str) -> List[Dict]:
    """从指定 URL 加载兑换码列表（JSON 格式）。"""
    import requests
    response = requests.get(url, headers=cfg.useragent, timeout=30)
    response.raise_for_status()
    return response.json()


def valid_codes_for_server(server: str, now: Optional[datetime.datetime] = None) -> List[Dict]:
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
        dt = datetime.datetime.fromisoformat(exp)
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

        server = get_server_by_registry()
        if server is None:
            log.error("无法判断游戏服务器类型，跳过兑换码任务")
            return False

        try:
            codes = valid_codes_for_server(server)
        except Exception as e:
            log.warning(f"获取兑换码失败: {e}")
            codes = []

        if not codes:
            log.info("没有找到有效的兑换码")
            log.hr("完成", 2)
            return False

        # 判断哪些兑换码是未使用过的
        try:
            used = cfg.already_used_codes
        except AttributeError:
            used = []
        if used is None:
            used = []
        codes = [code for code in codes if code not in used]

        log.info(f"当前服务器类型为{"国服" if server == "cn" else "国际服"}，找到{len(codes)}个有效兑换码，开始尝试兑换")
        log.hr("完成", 2)
        return Redemption.start(codes=codes)

    @staticmethod
    def start(codes: Optional[List[str]] = None):
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

        for idx, code in enumerate(codes_to_use, start=1):
            log.info(f"开始使用兑换码: {green(code)} ({idx}/{len(codes_to_use)})")
            screen.change_to('redemption')
            pyperclip.copy(code)
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
                            cfg.set_value("already_used_codes", used)
                        auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)
                        screen.wait_for_screen_change('menu')
                        time.sleep(3)
                        continue
            log.error(f"兑换码使用失败: {red(code)} ({idx}/{len(codes_to_use)})")
            auto.press_key("esc")
            screen.wait_for_screen_change('menu')
            log.hr("完成", 2)
            return False

        reward.start_specific("mail")
        log.hr("完成", 2)
        return True

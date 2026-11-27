from module.screen import screen
from module.automation import auto
from module.config import cfg
from module.config.platform import get_control_backend
from module.logger import log
from module.game import get_game_controller
from module.game.adb_transport import AdbError
from utils.color import red, green, yellow
from tasks.base.task_steps import optional_reward
import time
import json
import datetime
import sys
from typing import List, Dict, Optional
from module.notification import notif
from module.notification.notification import NotificationLevel


TOUCH_BUTTONS = (300 / 1280, 440 / 720, 680 / 1280, 90 / 720)
TOUCH_INPUT = (245 / 1280, 325 / 720, 790 / 1280, 52 / 720)
TOUCH_RESULT = (260 / 1280, 290 / 720, 760 / 1280, 125 / 720)
TOUCH_RESULT_TITLE = (570 / 1280, 235 / 720, 140 / 1280, 40 / 720)
TOUCH_ERROR = (245 / 1280, 428 / 720, 790 / 1280, 36 / 720)
CLIPBOARD_PROMPT = ("请求从剪切板粘贴", "请求从剪贴板粘贴")
RESULTS = ("兑换成功", "兑换码已过期", "无效的兑换码", "兑换码已被使用")


def _wait_for_paste(touch):
    target = "./assets/images/share/redemption/clear.png"
    if not touch:
        return auto.find_element(target, "image", 0.9, max_retries=6, retry_delay=0.5)
    # 部分 Android 首次读取剪贴板会多一层粘贴确认；不重复点击兑换框中的粘贴图标。
    allowed = False
    for _ in range(6):
        if auto.find_element(target, "image", 0.9, crop=TOUCH_INPUT):
            return True
        if not allowed and auto.find_element(CLIPBOARD_PROMPT, "text", include=True, crop=TOUCH_RESULT):
            allowed = auto.click_element("粘贴", "text", crop=TOUCH_BUTTONS)
        time.sleep(0.5)
    return False


def _find_result(touch):
    if not touch:
        return auto.find_element(RESULTS, "text", include=True)
    # 成功弹窗与输入框下方的失败提示条位置不同，避开可能含中文的兑换码本身。
    if auto.find_element("兑换提示", "text", crop=TOUCH_RESULT_TITLE):
        return auto.find_element(RESULTS, "text", include=True, crop=TOUCH_RESULT)
    return auto.find_element(RESULTS[1:], "text", include=True, crop=TOUCH_ERROR)


def _dismiss(touch):
    if not touch:
        return auto.press_key("esc")
    if auto.find_element("兑换提示", "text", crop=TOUCH_RESULT_TITLE):
        return auto.click_element("确认", "text", crop=TOUCH_BUTTONS)
    if auto.find_element(CLIPBOARD_PROMPT, "text", include=True, crop=TOUCH_RESULT):
        auto.click_element("不粘贴", "text", crop=TOUCH_BUTTONS)
    return auto.click_element("取消", "text", crop=TOUCH_BUTTONS)


def load_codes(path: str) -> List[Dict]:
    """加载兑换码列表（来自 JSON 文件）。"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_codes_from_url(urls: list[str]) -> list[dict]:
    """
    并发从多个 URL 获取 JSON 数据：
    - 抗 DNS 劫持 / SNI 阻断 / 超时 / 证书错误 / 过滤非 JSON
    """
    import requests
    from requests.exceptions import (
        Timeout, ConnectionError, SSLError, TooManyRedirects
    )
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import json
    import threading

    stop_event = threading.Event()

    def fetch(url: str):
        if stop_event.is_set():
            return None
        try:
            resp = requests.get(url, headers=cfg.useragent, timeout=10)
            if stop_event.is_set():
                return None
            resp.raise_for_status()

            ct = resp.headers.get("Content-Type", "")
            mime = ct.split(";")[0].strip().lower()
            if mime not in ("application/json", "text/plain"):
                raise ValueError(f"非预期的 Content-Type: {ct}")

            try:
                data = resp.json()
            except json.JSONDecodeError:
                raise ValueError("JSON 解析失败")

            if not isinstance(data, list):
                raise ValueError("JSON 结构不符合预期")

            return data

        except (Timeout, ConnectionError, SSLError, TooManyRedirects) as e:
            if not stop_event.is_set():
                log.warning(f"[{url}] 网络错误: {e}")
        except Exception as e:
            if not stop_event.is_set():
                log.warning(f"[{url}] 数据异常: {e}")

        return None

    executor = ThreadPoolExecutor(max_workers=min(5, len(urls)))
    futures = {executor.submit(fetch, url): url for url in urls}

    try:
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                stop_event.set()
                executor.shutdown(wait=False, cancel_futures=True)
                return result
    except Exception:
        stop_event.set()
        executor.shutdown(wait=False, cancel_futures=True)
        raise

    executor.shutdown(wait=False)
    raise RuntimeError("所有 URL 均不可用（可能被 DNS 劫持 / SNI 阻断 / 网络异常）")


def valid_codes_for_server(server: str, now: Optional[datetime.datetime] = None) -> List[str]:
    """
    返回指定服务器的未过期兑换码列表。
    expires_at 使用 ISO 8601 格式；为 null 表示不过期。
    """
    url = [
        "https://m7a.top/assets/config/redemption_codes.json",
        "https://github.kotori.top/https://m7a.top/assets/config/redemption_codes.json",
        "https://raw.githubusercontent.com/moesnow/March7thAssistant/refs/heads/main/assets/config/redemption_codes.json"
    ]
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

        # 如果云游戏启用，默认使用国服
        if get_control_backend(cfg) in ("cloud", "adb"):
            server = 'cn'
        elif sys.platform == 'win32':
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
            return False

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
            return True

        log.info(f"当前服务器类型为{"国服" if server == "cn" else "国际服"}，找到{len(codes)}个有效兑换码，开始尝试兑换")
        log.hr("完成", 2)
        Redemption.start(codes=codes, send_notification=True)
        # 已使用、已过期等明确结果也会记录在已处理列表。超时或无法操作的兑换码留待下次。
        handled = set(getattr(cfg, "already_used_codes", None) or ())
        return handled.issuperset(codes)

    @staticmethod
    def start(codes: Optional[List[str]] = None, send_notification: bool = False, on_summary=None) -> bool:
        """使用给定的兑换码列表（若为 None，则使用配置中的 `cfg.redemption_code`）。on_summary 收到各类明确结果的个数。"""
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
        confirmed_count = 0
        outcomes = {}
        touch = get_control_backend(cfg) == "adb"
        confirm_options = {"crop": TOUCH_BUTTONS} if touch else {}
        paste_options = {"crop": TOUCH_INPUT, "max_retries": 3, "retry_delay": 0.5} if touch else {}

        for idx, code in enumerate(codes_to_use, start=1):
            log.info(f"开始使用兑换码: {green(code)} ({idx}/{len(codes_to_use)})")
            screen.change_to('redemption')
            game = get_game_controller()
            try:
                copied = game.copy(code)
            except AdbError as error:
                if error.code not in ("unsupported", "unknown_command"):
                    raise
                log.error(f"设备剪贴板不可用，跳过兑换码任务：{error}")
                return False
            if copied is False:
                log.error(f"复制兑换码失败，未执行粘贴: {red(code)} ({idx}/{len(codes_to_use)})")
                continue
            if auto.click_element("./assets/images/share/redemption/paste.png", "image", 0.9, **paste_options):
                time.sleep(0.5)
                # 兑换窗口刚打开时画面可能尚未更新，单次检测会漏判；不重复粘贴，以免输入框内容叠加
                if _wait_for_paste(touch):
                    time.sleep(0.5)
                    auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, **confirm_options)
                    time.sleep(1)
                    # 结果弹窗可能晚于 1 秒出现（实测约 2 秒），只看一次会把已兑换的码记成失败并按 esc；
                    # 每秒重新截图检测，最多约 10 秒
                    result = None
                    for _ in range(10):
                        if _find_result(touch):
                            result = auto.matched_text
                            break
                        time.sleep(1)
                    if result:
                        confirmed_count += 1
                        outcomes[result] = outcomes.get(result, 0) + 1
                    if result == "兑换成功":
                        log.info(f"兑换码使用成功: {green(code)} ({idx}/{len(codes_to_use)})")
                        if code not in used:
                            used.append(code)
                            successful_codes.append(code)
                            cfg.set_value("already_used_codes", used)
                        auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, **confirm_options)
                    elif result:
                        log.info(f"{result}: {yellow(code)} ({idx}/{len(codes_to_use)})")
                        if code not in used:
                            used.append(code)
                            cfg.set_value("already_used_codes", used)
                        _dismiss(touch)
                    else:
                        log.warning(f"兑换结果检测超时: {yellow(code)} ({idx}/{len(codes_to_use)})")
                        _dismiss(touch)
                    screen.wait_for_screen_change('menu')
                    time.sleep(3)
                else:
                    log.error(f"兑换码使用失败: {red(code)} ({idx}/{len(codes_to_use)})")
                    _dismiss(touch)
                    screen.wait_for_screen_change('menu')
                    time.sleep(3)
            else:
                log.error(f"兑换码使用失败: {red(code)} ({idx}/{len(codes_to_use)})")

        if successful_codes:
            msg = f"成功使用了{len(successful_codes)}个兑换码: \n{'\n'.join(successful_codes)}"
            msg_parts = msg.split('\n')
            for part in msg_parts:
                if part.strip():  # 确保非空字符串
                    log.info(part.strip())
            if send_notification:
                with optional_reward("兑换码成功通知"):
                    notif.notify(content=msg, level=NotificationLevel.ALL)

            with optional_reward("兑换码邮件奖励"):
                if touch:
                    from tasks.touch.rewards import claim_mail
                    claim_mail()
                else:
                    # 电脑版领奖模块不随安卓 App 打包，只在这条分支导入。
                    import tasks.reward as reward
                    reward.start_specific("mail")
        elif confirmed_count == len(codes_to_use):
            log.info("所有兑换码均已处理")
        else:
            log.info("没有成功使用任何兑换码")
        if confirmed_count < len(codes_to_use):
            log.warning(f"仍有{len(codes_to_use) - confirmed_count}个兑换码未确认结果，留待下次重试")
        if on_summary is not None and outcomes:
            names = sorted(outcomes, key=lambda name: RESULTS.index(name) if name in RESULTS else len(RESULTS))
            on_summary("，".join(f"{name} {outcomes[name]} 个" for name in names))
        log.hr("完成", 2)
        return confirmed_count == len(codes_to_use)

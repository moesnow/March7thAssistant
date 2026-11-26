"""游戏登录框里「保留的登录记录」：整理和比对脱敏账号，按一帧画面的文字决定下一步。

这里只处理文字和坐标，不碰游戏，坐标是 1920×1080 设计分辨率，对应国服电脑客户端：
标题页右侧「登出」→ 弹窗确认选中「退出并保留登录记录」→「退出」→ 登录框展开记录 → 点目标号码 →「进入游戏」。

安全规则：
- 不点「退出并清除登录记录」；保留那一项没选中时先选中，确认不了就取消登出。
- 记录列表只点号码文字。右侧同一列是各条记录的删除按钮，登录框右上角是关闭按钮，都不点。
- 标题页右侧最下面的「退出」是退出游戏，只在登出弹窗里找「退出」按钮。
- 出现安全验证、手机号或验证码页立即停下，保留现场。
"""

import re
import time
import unicodedata
from dataclasses import dataclass

from .errors import AccountError

# 区域：x, y, 宽, 高
RIGHT_BUTTONS = (1740, 0, 180, 620)  # 公告、设置、登出或登入，最下面的「退出」是退出游戏
DIALOG = (600, 300, 720, 700)  # 登录框、记录列表、登出弹窗
BANNER = (520, 110, 880, 150)  # 「账号，欢迎进入游戏」
BOTTOM = (520, 760, 880, 320)  # 「点击进入」「开始游戏」
CENTER = (400, 150, 1120, 800)  # 安全验证一类的弹窗
TRIANGLE_X = 1198  # 登录框号码右侧的下拉三角；展开后同一列往下是各条记录的删除按钮
ROW_CLICK_MAX_X = 940  # 点记录行时不越过登录框中线

STARS = str.maketrans({c: "*" for c in "＊∗⁎✱✲✳※٭"})
VERIFY_WORDS = ("安全验证", "滑块", "拼图", "图形验证", "人机验证", "完成验证", "依次点击", "拖动")
CREDENTIAL_WORDS = ("手机号", "验证码", "密码", "扫码", "二维码", "注册")
TIME_PATTERN = re.compile(r"刚刚|昨天|前天|\d+\s*(秒|分钟|小时|天|周|个月|月|年)前")
PHONE = re.compile(r"(?:\+?86)?(1\d{10})")
EMAIL = re.compile(r"([^@\s]+)@([^@\s]+\.[^@\s]+)")
EDGE = re.compile(r"^[^0-9a-z*]+|[^0-9a-z*]+$")
SWITCH_TIMEOUT = 180


def clean(text):
    """OCR 结果和用户输入统一成半角小写、去掉空白，星号的各种写法都当作 *。"""
    text = unicodedata.normalize("NFKC", str(text or "")).translate(STARS)
    return re.sub(r"\s+", "", text).lower()


def mask_hint(value):
    """把用户填写的账号整理成要保存的样子。完整的手机号和邮箱先遮挡，只留头尾。"""
    text = clean(value)
    if not text:
        return ""
    if len(text) > 64:
        raise ValueError("账号太长，请照游戏登录框里显示的样子填写")
    if "*" in text:
        parts = [part for part in re.split(r"\*+", text) if part]
        if text.startswith("*") or text.endswith("*") or len(parts) < 2 or sum(map(len, parts)) < 3:
            raise ValueError("请照游戏登录框里显示的样子填写，星号前后都要有字，合起来至少 3 个，例如 138******66")
        return text
    phone = PHONE.fullmatch(text.replace("-", ""))
    if phone:
        digits = phone.group(1)
        return f"{digits[:3]}******{digits[-2:]}"
    email = EMAIL.fullmatch(text)
    if email:
        local, domain = email.groups()
        return f"{local[:1]}***@{domain}"
    raise ValueError("请照游戏登录框里显示的样子填写，例如 138******66")


def _pattern(hint):
    text = clean(hint)
    parts = [re.escape(part) for part in re.split(r"\*+", text) if part]
    if not parts:
        return None
    return re.compile("^" + ".*".join(parts) + "$")


def same_account(hint, shown):
    """登录框里显示的账号是不是这条提示。只比星号两边露出来的部分，不比星号个数。"""
    pattern = _pattern(hint)
    text = EDGE.sub("", clean(shown))
    return bool(pattern and text and pattern.fullmatch(text))


def banner_account(text):
    """「137******20，欢迎进入游戏」里的账号部分。"""
    head = unicodedata.normalize("NFKC", str(text or "")).split(",", 1)[0]
    return "" if "欢迎" in head else head.strip()


@dataclass(frozen=True)
class Line:
    """一行 OCR 文字，坐标是 1920×1080 设计分辨率。"""

    text: str
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    def inside(self, area):
        left, top, width, height = area
        return left <= self.cx <= left + width and top <= self.cy <= top + height


def _plain(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(text or "")))


def find(lines, text, area=None, *, exact=False):
    for line in lines:
        plain = _plain(line.text)
        if (plain == text if exact else text in plain) and (area is None or line.inside(area)):
            return line
    return None


def accounts_in(lines):
    """登录框里像脱敏账号的行，从上到下。第一行是当前选中的账号。"""
    found = []
    for line in lines:
        text = clean(line.text)
        if line.inside(DIALOG) and ("*" in text or "@" in text) and "欢迎" not in text and any(c.isalnum() for c in text):
            found.append(line)
    return sorted(found, key=lambda line: line.cy)


def classify(lines):
    """按这一帧的文字判断在哪个画面。几个画面同时出现时，弹窗优先。"""
    central = [clean(line.text) for line in lines if line.inside(CENTER)]
    if any(word in text for text in central for word in VERIFY_WORDS):
        return "verification"
    if any("bilibili" in clean(line.text) or "哔哩哔哩" in line.text for line in lines):
        return "bilibili"
    dialog = [line for line in lines if line.inside(DIALOG)]
    if find(dialog, "退出登录") and find(dialog, "保留登录记录"):
        return "logout_dialog"
    if any(word in clean(line.text) for line in dialog for word in CREDENTIAL_WORDS):
        return "credentials"
    others = find(dialog, "登录其他账号")
    if others and any(TIME_PATTERN.search(_plain(line.text)) for line in dialog):
        return "record_list"
    if others and find(dialog, "进入游戏", exact=True):
        return "record_box"
    if find(lines, "欢迎进入游戏", BANNER):
        return "welcome"
    if find(lines, "登出", RIGHT_BUTTONS, exact=True) and (
        find(lines, "点击进入", BOTTOM) or find(lines, "开始游戏", BOTTOM)
    ):
        return "title"
    if find(lines, "登入", RIGHT_BUTTONS, exact=True):
        return "logged_out"
    return "other"


class LoginSwitch:
    """在游戏的登录界面里切到目标账号。每次 step 看一帧、最多点一下。

    step 返回 "acted"（点了东西，这一轮别再动）、"waiting"（不是切号要处理的画面，原流程只做通用弹窗）
    或 "done"（切号已经完成或不需要，交回原来的启动流程）。失败时抛出 AccountError。
    frame() 返回当前画面的 Line 列表；click(x, y) 点击设计坐标；
    checked(keep, clear) 返回两个单选框是否选中；on_expired() 在记录失效时记下登录过期；
    trace(screen) 在画面变化时记日志。
    """

    def __init__(self, hint, *, logout, frame, click, checked, allow_password=False, on_expired=None,
                 trace=None, clock=time.monotonic, timeout=SWITCH_TIMEOUT):
        self.hint = hint or ""
        self.need_logout = bool(logout)
        self.allow_password = allow_password
        self.entered = False  # 已对目标账号点过「进入游戏」
        self.saw_records = False
        self.password_fallback = False
        self._frame, self._click, self._checked = frame, click, checked
        self._on_expired, self._trace, self._traced = on_expired, trace, None
        self._clock, self._timeout = clock, timeout
        self._deadline = None
        self._tries, self._last = {}, {}

    def step(self):
        lines = self._frame()
        screen = classify(lines)
        if self._trace is not None and screen != self._traced:
            self._traced = screen
            self._trace(screen)
        if screen == "welcome":
            return self._on_welcome(lines)
        if (self.entered or not self.need_logout) and screen in ("other", "title"):
            # 不需要切号，或者已经对目标账号点过「进入游戏」：交回原来的启动流程。
            return "done"
        if screen != "other" and self._deadline is None:
            self._deadline = self._clock() + self._timeout
        if self._deadline is not None and self._clock() > self._deadline:
            raise AccountError("account_switch_failed", "游戏内切换账号超时，已保留游戏现场")
        return getattr(self, "_on_" + screen)(lines)

    def _act(self, key, limit, cooldown, x, y):
        now = self._clock()
        if now - self._last.get(key, float("-inf")) < cooldown:
            return "waiting"
        if self._tries.get(key, 0) >= limit:
            raise AccountError("account_switch_failed", "游戏内切换账号时，同一步重复多次没有反应，已保留游戏现场")
        self._tries[key] = self._tries.get(key, 0) + 1
        self._last[key] = now
        self._click(x, y)
        return "acted"

    def _require_hint(self):
        if not self.hint:
            raise AccountError(
                "account_no_login_record", "还没有填写「登录记录中的账号」，请在账号页的账号详情里填写"
            )

    def _on_other(self, lines):
        return "waiting"

    def _on_verification(self, lines):
        raise AccountError("account_verification", "游戏要求安全验证，请本人完成后再运行，已保留游戏现场")

    def _on_bilibili(self, lines):
        raise AccountError("account_unsupported", "B 服客户端不支持游戏内切换账号，请在账号页改用登录快照", 2)

    def _on_credentials(self, lines):
        if self.allow_password:
            # 账号开了「登录过期时自动填写账号密码」：交给原来的自动填写。
            self.password_fallback = True
            return "done"
        if self._on_expired is not None:
            self._on_expired()
        if self.entered:
            raise AccountError(
                "account_login_expired",
                f"登录记录「{self.hint}」已失效，请在游戏里重新登录这个账号，退出时选「退出并保留登录记录」",
            )
        raise AccountError(
            "account_record_missing",
            "游戏里没有可用的登录记录，请先在游戏里登录这个账号，退出时选「退出并保留登录记录」",
        )

    def _on_logout_dialog(self, lines):
        keep = find(lines, "退出并保留登录记录", DIALOG)
        clear = find(lines, "退出并清除登录记录", DIALOG)
        cancel = find(lines, "取消", DIALOG, exact=True)
        confirm = None
        if keep:
            confirm = next((line for line in lines if line.inside(DIALOG) and _plain(line.text) == "退出"
                            and line.cy > keep.cy), None)
        if not (keep and clear and confirm):
            return "waiting"
        if self.entered or not self.need_logout:
            # 不是这次切号要登出：关掉弹窗。
            return self._act("cancel", 2, 2, cancel.cx, cancel.cy) if cancel else "waiting"
        keep_on, clear_on = self._checked(keep, clear)
        if keep_on and not clear_on:
            return self._act("confirm_logout", 3, 3, confirm.cx, confirm.cy)
        if self._tries.get("keep", 0) < 2:
            return self._act("keep", 2, 1.5, keep.x + min(60, keep.w / 2), keep.cy)
        if cancel:
            self._click(cancel.cx, cancel.cy)
            raise AccountError(
                "account_switch_failed", "没能确认选中「退出并保留登录记录」，已取消登出，没有清除任何登录记录"
            )
        raise AccountError(
            "account_switch_failed", "没能确认选中「退出并保留登录记录」，已停止切换，没有点「退出」"
        )

    def _on_record_list(self, lines):
        self.saw_records = True
        self._require_hint()
        shown = accounts_in(lines)
        if not shown:
            return "waiting"
        rows = [line for line in shown[1:] if line.cy > shown[0].cy + 30]
        hits = [line for line in rows if same_account(self.hint, line.text)]
        if len(hits) > 1:
            raise AccountError(
                "account_record_ambiguous",
                f"登录记录里有 {len(hits)} 个账号都像「{self.hint}」，请在账号页补全开头和结尾",
            )
        if not hits:
            if not rows or self._tries.get("search", 0) < 2:
                # OCR 偶尔读错一帧，换一帧再找。
                self._tries["search"] = self._tries.get("search", 0) + 1
                return "waiting"
            raise AccountError(
                "account_record_missing",
                f"登录记录里没有「{self.hint}」，请在游戏里登录一次这个账号，退出时选「退出并保留登录记录」",
            )
        row = hits[0]
        return self._act("pick", 3, 2, min(row.x + min(40, row.w / 2), ROW_CLICK_MAX_X), row.cy)

    def _on_record_box(self, lines):
        self.saw_records = True
        self._require_hint()
        shown = accounts_in(lines)
        enter = find(lines, "进入游戏", DIALOG, exact=True)
        if not shown or not enter:
            return "waiting"
        if same_account(self.hint, shown[0].text):
            result = self._act("enter", 3, 5, enter.cx, enter.cy)
            if result == "acted":
                self.entered = True
            return result
        return self._act("open", 3, 2, TRIANGLE_X, shown[0].cy)

    def _on_welcome(self, lines):
        banner = find(lines, "欢迎进入游戏", BANNER)
        shown = banner_account(banner.text) if banner else ""
        if self.hint and shown:
            same = same_account(self.hint, shown)
            if self.entered and not same:
                raise AccountError("account_mismatch", f"进入的是「{shown}」，不是「{self.hint}」，已停止本账号任务")
            if not self.entered:
                # 游戏自动登录的是谁，决定还要不要登出。
                self.need_logout = not same
        # 横幅还在时别让原流程点「开始游戏」，等它消失后由标题页交回。
        return "done" if self.entered or not self.need_logout else "waiting"

    def _on_title(self, lines):
        if self.entered or not self.need_logout:
            return "done"
        button = find(lines, "登出", RIGHT_BUTTONS, exact=True)
        return self._act("logout", 4, 3, button.cx, button.cy)

    def _on_logged_out(self, lines):
        button = find(lines, "登入", RIGHT_BUTTONS, exact=True)
        return self._act("login", 3, 3, button.cx, button.cy)

"""快捷启动迁移所需的旧主页卡片和内置文案。"""
from module.localization import tr
from utils.tasks import AVAILABLE_TASKS

# 仅主页可用的特殊操作（不在 AVAILABLE_TASKS 中）
HOME_EXTRA_TASKS = {
    "_reset_universe_config": "重置模拟宇宙配置文件",
    "_open_universe_dir": "打开模拟宇宙目录",
    "_open_universe_homepage": "打开模拟宇宙项目主页",
    "_reset_fight_config": "重置锄大地配置文件",
    "_open_fight_dir": "打开锄大地程序目录",
    "_open_fight_homepage": "打开锄大地项目主页",
}

# 合并所有可选任务（值为中文原文 msgid，显示时再 tr()）
ALL_TASKS = {**AVAILABLE_TASKS, **HOME_EXTRA_TASKS}


DEFAULT_CARDS = [
    {
        "icon": "./assets/app/images/March7th.jpg",
        "title": "完整运行",
        "action_type": "single",
        "task_id": "main",
        "menu_items": []
    },
    {
        "icon": "./assets/app/images/JingYuan.jpg",
        "title": "日常",
        "action_type": "menu",
        "task_id": "",
        "menu_items": [
            {"label": "日常", "task_id": "routine"},
            {"label": "每日实训", "task_id": "daily"},
            {"label": "清体力", "task_id": "power"}
        ]
    },
    {
        "icon": "./assets/app/images/Yanqing.jpg",
        "title": "货币战争",
        "action_type": "menu",
        "task_id": "",
        "menu_items": [
            {"label": "运行一次", "task_id": "currencywars"},
            {"label": "循环运行", "task_id": "currencywarsloop"},
            {"label": "货币战争中途接管", "task_id": "currencywarstemp"},
        ]
    },
    {
        "icon": "./assets/app/images/Herta.jpg",
        "title": "差分宇宙",
        "action_type": "menu",
        "task_id": "",
        "menu_items": [
            {"label": "差分宇宙运行一次 ⭐", "task_id": "divergent"},
            {"label": "差分宇宙循环运行 ⭐", "task_id": "divergentloop"},
            {"label": "差分宇宙中途接管", "task_id": "divergenttemp"},
            {"label": "模拟宇宙快速启动（停止维护）", "task_id": "universe"},
            {"label": "模拟宇宙原版运行（停止维护）", "task_id": "universe_gui"},
            {"label": "更新模拟宇宙（停止维护）", "task_id": "universe_update"},
            {"label": "重置模拟宇宙配置文件（停止维护）", "task_id": "_reset_universe_config"},
            {"label": "打开模拟宇宙目录（停止维护）", "task_id": "_open_universe_dir"},
            {"label": "打开模拟宇宙项目主页（停止维护）", "task_id": "_open_universe_homepage"},
        ]
    },
    {
        "icon": "./assets/app/images/SilverWolf.jpg",
        "title": "锄大地",
        "action_type": "menu",
        "task_id": "",
        "menu_items": [
            {"label": "快速启动 ⭐", "task_id": "fight"},
            {"label": "原版运行", "task_id": "fight_gui"},
            {"label": "更新锄大地", "task_id": "fight_update"},
            {"label": "重置配置文件", "task_id": "_reset_fight_config"},
            {"label": "打开程序目录", "task_id": "_open_fight_dir"},
            {"label": "打开项目主页", "task_id": "_open_fight_homepage"},]
    },
    {
        "icon": "./assets/app/images/Bronya.jpg",
        "title": "逐光捡金",
        "action_type": "menu",
        "task_id": "",
        "menu_items": [
            {"label": "混沌回忆", "task_id": "forgottenhall"},
            {"label": "虚构叙事", "task_id": "purefiction"},
            {"label": "末日幻影", "task_id": "apocalyptic"}
        ]
    },
]

# 内置文案的中文原文集合：这些值可以被翻译，用户自定义文案则原样显示。
# 同时包含任务名（菜单项会自动填入任务名），持久化时把界面文案还原成中文原文，
# 保证 config.yaml 里存的是语言无关的键，切语言/重启后依然正确。
BUILTIN_LABELS = frozenset(
    [card["title"] for card in DEFAULT_CARDS]
    + [item["label"] for card in DEFAULT_CARDS for item in card["menu_items"]]
    + list(ALL_TASKS.values())
)


def display_label(text: str, extra_labels=()) -> str:
    """按当前语言显示卡片/菜单项文案：内置文案走 tr()，用户自定义文案原样返回。"""
    if not text:
        return text
    return tr(text) if text in BUILTIN_LABELS or text in extra_labels else text


def stored_label(text: str, msgid: str | None, *, display=display_label) -> str:
    """把界面上的文案还原成可持久化的键。

    :param text:  界面上当前的文案（可能是译文，也可能被用户改过）
    :param msgid: 该控件原本承载的中文原文；用户新建的控件传 None

    只做「正向」比较：文案仍等于该 msgid 的当前语言显示时，存回 msgid。
    这样 config.yaml 里存的是语言无关的键，切语言/重启后依然正确。
    注意不能按译文反查 msgid —— 不同原文可能有相同译文（如日文的「更新锄大地」与
    「锄大地更新」），反查会串味。
    """
    if msgid and text == display(msgid):
        return msgid
    return text


def legacy_label_map(labels=BUILTIN_LABELS) -> dict:
    """旧版本配置遗留的「译文 -> 中文原文」还原表（仅内置文案闭集）。

    旧版本在非中文界面保存卡片时会把译文写进 config.yaml；这里按 5 语言目录反查还原。
    **歧义译文（多个内置文案同译）不收录**——如日文里「更新锄大地」与「锄大地更新」同译，
    反查会串味，宁可原样保留交由用户重新选择。
    """
    from module.localization import translations_of

    reverse: dict[str, str] = {}
    ambiguous: set[str] = set()
    for msgid in sorted(labels):
        for translated in translations_of(msgid).values():
            # 同文、或译文本身就是某个内置原文的值无需还原（display_label 已能识别）
            if not translated or translated == msgid or translated in labels:
                continue
            if translated in reverse and reverse[translated] != msgid:
                ambiguous.add(translated)
            else:
                reverse[translated] = msgid
    for text in ambiguous:
        reverse.pop(text, None)
    return reverse


def migrate_home_cards(cards, reverse=None) -> bool:
    """把旧版本写进配置的译文还原为中文原文（原地修改、幂等）。

    识别范围仅限「等于内置文案某个译文」的遗留值；用户自定义文案与歧义译文不动。
    返回是否有改动，供调用方决定是否写回配置。
    """
    if not isinstance(cards, list):
        return False
    if reverse is None:
        reverse = legacy_label_map()
    changed = False
    for card in cards:
        if not isinstance(card, dict):
            continue
        title = card.get("title", "")
        if isinstance(title, str) and title in reverse:
            card["title"] = reverse[title]
            changed = True
        items = card.get("menu_items")
        for item in items if isinstance(items, list) else ():
            if not isinstance(item, dict):
                continue
            label = item.get("label", "")
            if isinstance(label, str) and label in reverse:
                item["label"] = reverse[label]
                changed = True
    return changed

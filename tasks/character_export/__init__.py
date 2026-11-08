"""角色面板导出：遍历角色详情页，把属性、光锥、星魂、技能和遗器写成 JSON。"""
import json
import os
from collections import Counter
from datetime import datetime

from module.logger import log
from module.screen import screen

from . import parser
from .reader import CharacterReader, PageError

OUTPUT = "./characters.json"
PARTIAL = "./characters.partial.json"
SCHEMA_VERSION = 1

MAX_PAGES = 40
MAX_RESTARTS = 8
MAX_BACK_DRAGS = 3
# 同一个角色读取失败这么多次就跳过，不影响后面的角色
MAX_ATTEMPTS = 2


def _finish(pending, finish, retry):
    """解析读取结果；读不准就重读一次，还不行就把问题交给调用方写进 warnings。"""
    try:
        data, problems = finish(pending)
    except parser.ParseError as e:
        data, problems = None, [str(e)]
    if not problems:
        return data, []
    log.debug(f"重新读取：{problems}")
    try:
        return retry(data)
    except parser.ParseError as e:
        return data, [*problems, str(e)]


def _public_piece(piece):
    return {key: value for key, value in piece.items() if key != "set_count"}


class CharacterExport:
    def __init__(self, reader=None, output=OUTPUT, partial=PARTIAL):
        self.reader = reader or CharacterReader()
        self.output = output
        self.partial = partial
        self.characters = []
        self.seen = set()
        self.attempts = Counter()
        self.failed = []
        self.interrupted_character = False

    def run(self):
        try:
            complete = self._walk_with_restarts()
            if not self.characters:
                raise RuntimeError("没有读取到角色，当前仅支持简体中文客户端")
            complete = complete and not self.failed
            self._save(self.output, complete)
            if os.path.exists(self.partial):
                os.remove(self.partial)
            warnings = sum(bool(character["warnings"]) for character in self.characters)
            log.info(f"角色面板已导出到 {os.path.abspath(self.output)}，共 {len(self.characters)} 个角色，"
                     f"{warnings} 个有警告，{len(self.failed)} 个读取失败")
            screen.change_to("menu")
            return complete
        finally:
            self.reader.close()

    def _walk_with_restarts(self):
        attempt = 0
        while attempt < MAX_RESTARTS:
            progress = len(self.characters) + len(self.failed)
            try:
                # 总是从手机重新进入：顶栏回到左端、页签回到详情，已读过的角色按名字跳过
                screen.change_to("menu")
                screen.change_to("character")
                self._walk()
                return True
            except (PageError, parser.ParseError) as e:
                # 有角色读完或按上限跳过就继续走；全程累计会让几个坏角色耗尽后续角色的机会。
                if len(self.characters) + len(self.failed) > progress:
                    attempt = 0
                attempt += 1
                log.warning(f"读取中断（连续 {attempt}/{MAX_RESTARTS}）：{e}")
        return False

    def _walk(self):
        self.reader.reset()
        slots = self.reader.avatar_slots()
        for _ in range(MAX_PAGES):
            self._read_page(slots)
            if not self._next_page():
                return
            slots = self.reader.avatar_slots()[1:]
        raise PageError("顶栏翻页次数过多")

    def _read_page(self, slots):
        checking = True
        for x in slots:
            self.reader.select_avatar(x, required=not checking)
            # 翻页后开头的头像已经读过，要逐个确认；遇到新角色后就不等 OCR，直接开始读
            if checking:
                summary = self._current_summary()
                if self._known(summary) or self._give_up(summary):
                    continue
                checking = False
            try:
                self.read_character()
            except (PageError, parser.ParseError):
                self.interrupted_character = True
                raise

    def _next_page(self):
        """翻页，已经到头时返回 False。第一格必须是读过的角色，否则就是拖过头了，退回去才不会漏人。"""
        self.reader.open_tab("detail")
        if not self.reader.next_avatars():
            return False
        for _ in range(MAX_BACK_DRAGS):
            self.reader.select_avatar(self.reader.avatar_slots()[0])
            if self._known(self._current_summary()):
                return True
            log.warning("顶栏拖过头了，退回一段")
            self.reader.previous_avatars()
        raise PageError("顶栏无法定位到读过的角色")

    def _known(self, summary):
        return (summary["name"], summary["path"]) in self.seen

    def _give_up(self, summary):
        """中断后重新走到的第一个新角色，就是上次读到一半的角色。"""
        key = (summary["name"], summary["path"])
        if self.interrupted_character:
            self.attempts[key] += 1
            self.interrupted_character = False
        if self.attempts[key] < MAX_ATTEMPTS:
            return False
        log.error(f"{summary['name']}（{summary['path']}）读取失败，已跳过")
        self.seen.add(key)
        self.failed.append({"name": summary["name"], "path": summary["path"]})
        return True

    def _current_summary(self):
        self.reader.open_tab("detail")
        return self._load_summary(self.reader.begin_summary())

    def _load_summary(self, future):
        try:
            return parser.parse_summary(future.result())
        except parser.ParseError as e:
            log.debug(f"重新读取：{e}")
            self.reader.open_tab("detail")
            self.reader.grab()
            return parser.parse_summary(self.reader.begin_summary().result())

    def read_character(self):
        """读取当前选中的角色。"""
        reader = self.reader
        steps = {
            "detail": reader.begin_detail,
            "traces": reader.open_traces,
            "light_cone": reader.begin_light_cone,
            "relics": reader.begin_relics,
            "eidolon": self._read_eidolon,
        }
        # 上一个角色停在星魂页时，这个角色从星魂页读回详情页，每个角色少切一次页签
        order = reversed(steps) if reader.tab == "eidolons" else steps
        pending = {name: steps[name]() for name in order}

        detail = pending["detail"]
        element, switchable, stats = detail["element"], detail["switchable"], detail["stats"]
        summary = self._load_summary(detail["summary"])
        if self._known(summary):
            return
        skills = reader.begin_traces(summary["path"], pending["traces"])
        light_cone, relics, eidolon = pending["light_cone"], pending["relics"], pending["eidolon"]
        totals = summary["totals"]
        if len(totals) < len(parser.TOTAL_LABELS):
            totals = self._reread_totals(totals)

        warnings = []
        if element is None:
            warnings.append("未能识别属性")
        # 暴击率和暴击伤害弹窗里就有，缺了不影响数据；基础属性的总值要由弹窗的两列相加得到
        missing = [label for label in parser.BASE_STATS if label not in totals]
        if missing:
            warnings.append(f"详情页没有读到{'、'.join(missing)}，未能交叉校验")
        stats, problems = _finish(stats, lambda pending: reader.finish_stats(pending, totals),
                                  lambda _: self._reread_stats(totals))
        warnings += problems
        skills, problems = _finish(skills, reader.finish_traces, lambda _: reader.read_skills_by_panel())
        warnings += problems
        light_cone, problems = _finish(light_cone, reader.finish_light_cone,
                                       lambda _: reader.finish_light_cone(reader.begin_light_cone()))
        warnings += problems
        relics, problems = _finish(relics, reader.finish_relics,
                                   lambda first: reader.finish_relics(reader.begin_relics(), first["by_slot"]))
        warnings += problems

        character = {
            "name": summary["name"],
            "is_trailblazer": parser.is_trailblazer(summary["name"], switchable),
            "path_switchable": switchable,
            "path": summary["path"],
            "element": element,
            "level": summary["level"],
            "max_level": summary["max_level"],
            "eidolon": eidolon,
            "stats": stats,
            "light_cone": light_cone,
            "skills": skills or [],
            "relics": {"sets": relics["sets"], "pieces": [_public_piece(piece) for piece in relics["pieces"]]},
            "warnings": warnings,
        }
        self.seen.add((summary["name"], summary["path"]))
        self.characters.append(character)
        self._save(self.partial, False)
        log.info(f"[{len(self.characters)}] {summary['name']}（{summary['path']}/{element}）"
                 f"{summary['level']} 级 {eidolon} 魂")
        for warning in warnings:
            log.warning(f"{summary['name']}：{warning}")

    def _reread_totals(self, totals):
        """重新识别详情页的总值。只需要一次 OCR，比重读属性详情快得多。"""
        self.reader.open_tab("detail")
        self.reader.grab()
        try:
            return {**parser.parse_summary(self.reader.begin_summary().result())["totals"], **totals}
        except parser.ParseError:
            return totals

    def _reread_stats(self, totals):
        # 总值不符时可能是详情页读错了，弹窗的背景更干净，所以总值以这次重新识别的为准
        fresh = self._reread_totals({})
        return self.reader.finish_stats(self.reader.begin_stats(careful=True), {**totals, **fresh})

    def _read_eidolon(self):
        try:
            return self.reader.read_eidolon()
        except parser.ParseError as e:
            log.debug(f"重新读取：{e}")
            return self.reader.read_eidolon()

    def _save(self, path, complete):
        data = {
            "schema_version": SCHEMA_VERSION,
            "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "complete": complete,
            "characters": self.characters,
            "failed": self.failed,
        }
        temporary = f"{path}.tmp"
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(temporary, path)


def run():
    if not CharacterExport().run():
        raise RuntimeError("角色面板导出未完成，请检查 characters.json 中的 complete、failed 和运行日志")
    return True

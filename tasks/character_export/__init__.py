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
TRAILBLAZER_NAME = "开拓者"
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


def _character_key(summary):
    # 开拓者的昵称可能时有时无，重试和翻页始终使用同一个身份。
    return (None if summary["is_trailblazer"] else summary["name"], summary["path"])


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
                # 总是从手机重新进入：顶栏回到左端、页签回到详情，已读过的角色按身份跳过
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
        return _character_key(summary) in self.seen

    def _give_up(self, summary):
        """中断后重新走到的第一个新角色，就是上次读到一半的角色。"""
        key = _character_key(summary)
        if self.interrupted_character:
            self.attempts[key] += 1
            self.interrupted_character = False
        if self.attempts[key] < MAX_ATTEMPTS:
            return False
        name = summary["name"] or TRAILBLAZER_NAME
        log.error(f"{name}（{summary['path']}）读取失败，已跳过")
        self.seen.add(key)
        self.failed.append({"name": name, "path": summary["path"]})
        return True

    def _current_summary(self):
        self.reader.open_tab("detail")
        return self._load_summary(self.reader.begin_summary())

    def _load_summary(self, pending):
        first = None
        try:
            first = self.reader.finish_summary(pending)
        except parser.ParseError as e:
            log.debug(f"重新读取：{e}")
        if first is not None:
            if first["name"]:
                return self._resolve_summary(first)
            log.debug("未能识别角色名，重新读取详情页")
        self.reader.open_tab("detail")
        self.reader.grab()
        try:
            fresh = self.reader.finish_summary(self.reader.begin_summary())
        except parser.ParseError:
            if first is None:
                raise
        else:
            if first is None:
                first = fresh
            elif first["path"] == fresh["path"] and (first["is_trailblazer"], fresh["is_trailblazer"]) != (True, False):
                if fresh["is_trailblazer"] is None:
                    fresh["is_trailblazer"] = first["is_trailblazer"]
                first = fresh
        return self._resolve_summary(first)

    def _resolve_summary(self, summary):
        if summary["is_trailblazer"] is None:
            identified = self.reader.read_trailblazer_intro()
            if identified is None and summary["name"]:
                identified = parser.is_trailblazer(summary["name"], summary["switchable"])
            summary["is_trailblazer"] = identified is True
        if not summary["name"] and not summary["is_trailblazer"]:
            raise parser.ParseError("详情页读取失败：未能识别角色名或确认开拓者身份")
        return summary

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
        element, stats = detail["element"], detail["stats"]
        summary = self._load_summary(detail["summary"])
        if self._known(summary):
            return
        skills = reader.begin_traces(summary["path"], pending["traces"])
        light_cone, relics, eidolon = pending["light_cone"], pending["relics"], pending["eidolon"]
        totals = summary["totals"]
        if len(totals) < len(parser.TOTAL_LABELS):
            totals = self._reread_totals(totals)

        warnings = []
        name = summary["name"] or TRAILBLAZER_NAME
        if not summary["name"]:
            warnings.append("未能识别开拓者昵称，使用默认名称「开拓者」")
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
            "name": name,
            "is_trailblazer": summary["is_trailblazer"],
            "path_switchable": summary["switchable"],
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
        self.seen.add(_character_key(summary))
        self.characters.append(character)
        self._save(self.partial, False)
        log.info(f"[{len(self.characters)}] {name}（{summary['path']}/{element}）"
                 f"{summary['level']} 级 {eidolon} 魂")
        for warning in warnings:
            log.warning(f"{name}：{warning}")

    def _reread_totals(self, totals):
        """重新识别详情页的总值。只需要一次 OCR，比重读属性详情快得多。"""
        self.reader.open_tab("detail")
        self.reader.grab()
        try:
            return {**self.reader.finish_summary(self.reader.begin_summary())["totals"], **totals}
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

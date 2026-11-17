"""PC 快速刷取适配器。单次事务：识别副本、校验消费、一次提交、真实回执。

仅支持已观察的简体中文 PC 界面。找不到明确入口时保留原清体力流程；
提交后或无法安全取消时抛出致命恢复错误，不猜测、不自动补扣。
"""
from dataclasses import dataclass
import re
import time
import unicodedata

from tasks.power.fuel_ticket import (
    FuelTicketReceipt, FuelTicketSettlementUnknown, execute_fuel_ticket_batch,
    parse_clear_progress, plan_fuel_ticket_batch,
)


def normalized(text):
    return re.sub(r"[\s·•「」『』™\-—]", "", unicodedata.normalize("NFKC", text or ""))


@dataclass(frozen=True)
class Word:
    text: str
    x: float
    y: float
    confidence: float = 1.0


def exact(words, text, *, region=(0, 0, 1, 1)):
    l, t, r, b = region
    matches = [w for w in words if w.confidence >= .75 and
               normalized(w.text) == normalized(text) and
               l <= w.x <= r and t <= w.y <= b]
    return matches[0] if len(matches) == 1 else None


def entry_button(words, category, name, display_name):
    """Match the actual name/location row to its own Enter label."""
    red = category == "拟造花萼（赤）"
    target = name if red else display_name
    def row_text(value):
        # The location pin is sometimes recognized as a leading '?' by OCR.
        # Limit this correction to the red-calyx location label only.
        return normalized(value).lstrip("?") if red else normalized(value)
    targets = [w for w in words if row_text(w.text) == row_text(target)
               and w.confidence >= .75 and .34 < w.x < .60 and .25 < w.y < .81]
    if not targets:
        return None
    for target_word in sorted(targets, key=lambda w: w.y):
        # 赤萼：地点在副本名称下方，必须验证同一行的蕾名。
        if red and not any(normalized(w.text) == normalized(display_name)
                           and w.confidence >= .75 and abs(w.x-target_word.x) < .13
                           and .009 < target_word.y-w.y < .065 for w in words):
            continue
        buttons = [w for w in words if normalized(w.text) == "进入"
                   and w.confidence >= .75 and .70 < w.x < .93
                   and abs(w.y-target_word.y) < .036]
        if len(buttons) == 1:
            return buttons[0]
    return None


def ticket_icon(image, entry):
    """Orange ticket glyph immediately left of the verified Enter label.

    Detection uses a bounded row-local color component, not a blind fixed click.
    No color match, multiple components or malformed image => no input.
    """
    import cv2
    import numpy as np
    width, height = image.size
    if width < 600 or height < 340 or not 1.69 < width / height < 1.82:
        return None
    x1, x2 = int((entry.x-.105)*width), int((entry.x-.036)*width)
    y1, y2 = int((entry.y-.024)*height), int((entry.y+.024)*height)
    rgb = np.asarray(image.convert("RGB").crop((x1, y1, x2, y2)))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, (5, 115, 135), (32, 255, 255))
    count, _, stats, centers = cv2.connectedComponentsWithStats(mask, 8)
    candidates = []
    for i in range(1, count):
        _, _, w, h, area = stats[i]
        if (max(3, width*.004) <= w <= width*.032
                and max(3, height*.004) <= h <= height*.039
                and area >= max(5, width*height*.000007)
                and .55 <= w/h <= 5):
            cx, cy = centers[i]
            candidates.append(((x1+cx)/width, (y1+cy)/height))
    return candidates[0] if len(candidates) == 1 else None


def _costs(words, anchor):
    # Two separately visible integer OCR boxes to the right of 消耗.
    # Refuse combined/ambiguous numbers rather than synthesizing from plan.
    nums = sorted((w for w in words if w.confidence >= .75 and
                   re.fullmatch(r"[0-9]{1,3}", normalized(w.text)) and
                   anchor.x+.012 < w.x < anchor.x+.20 and abs(w.y-anchor.y)<.018),
                  key=lambda w:w.x)
    # OCR can combine the label and first cost; this version deliberately declines.
    return tuple(int(normalized(w.text)) for w in nums) if len(nums)==2 else None


def confirm_dialog(words, batch, display_name):
    title = exact(words, "快速刷取", region=(.3,.13,.7,.40))
    cancel = exact(words, "取消", region=(.22,.48,.52,.88))
    confirm = exact(words, "确认", region=(.5,.48,.79,.88))
    if not (title and cancel and confirm and abs(cancel.y-confirm.y)<.025):
        return None
    prompt = normalized("是否快速刷取"+display_name+batch.instance_type+"难度")
    if len([w for w in words if w.confidence>=.75 and .3<w.x<.7
            and title.y<w.y<cancel.y and normalized(w.text).startswith(prompt)]) != 1:
        return None
    count = [w for w in words if w.confidence>=.75 and
             re.fullmatch(r"刷取次数1",normalized(w.text))
             and title.y<w.y<cancel.y]
    # Accept split count label/number only when they are paired on the same row.
    if not count:
        n = exact(words,"刷取次数",region=(.3,title.y,.65,cancel.y))
        if not n or not any(w.confidence>=.75 and normalized(w.text)=="1"
                            and .005<w.x-n.x<.075 and abs(w.y-n.y)<.015 for w in words):
            return None
    cost = exact(words,"消耗",region=(.30,title.y,.65,cancel.y))
    if not cost or _costs(words,cost)!=(batch.power,batch.tickets):
        return None
    return confirm


def receipt_dialog(words, batch, display_name):
    title = exact(words,"快速刷取",region=(.30,.06,.70,.38))
    close = exact(words,"关闭",region=(.16,.55,.56,.98))
    again = exact(words,"再来一次",region=(.44,.55,.84,.98))
    if not(title and close and again and abs(close.y-again.y)<.035):
        return None
    progress_words = [w for w in words if w.confidence>=.75 and title.y<w.y<close.y
                      and .27<w.x<.73]
    progress = parse_clear_progress(" ".join(w.text for w in sorted(progress_words,key=lambda w:(round(w.y,2),w.x))))
    # For split OCR boxes, only use explicitly labelled, spatially paired progress.
    if progress is None:
        anchor = exact(progress_words,"刷取次数")
        if anchor:
            values = [w for w in progress_words if abs(w.y-anchor.y)<.025
                      and .0<w.x-anchor.x<.20 and re.fullmatch(r"1\s*/\s*1", w.text.strip())]
            if len(values)==1:
                progress=(1,1)
    if progress!=(1,1) or batch.waves!=1:
        return None
    # The result itself must show the selected displayed title and category.
    label = normalized(display_name+batch.instance_type)
    if len([w for w in words if w.confidence>=.75 and label==normalized(w.text)
            and title.y<w.y<close.y])!=1:
        return None
    row = next((w for w in words if normalized(w.text)=="第1次刷取"
                and w.confidence>=.75),None)
    cost = exact(words,"消耗",region=(.55,title.y,.90,close.y))
    if not(row and cost and abs(row.y-cost.y)<.026
           and _costs(words,cost)==(batch.power,batch.tickets)):
        return None
    return FuelTicketReceipt(batch.instance_type,batch.name,1,1,batch.power,batch.tickets)


class PCFuelTicketScreen:
    def __init__(self, auto, instance, display_name, *, sleep=time.sleep):
        self.auto=auto
        self.instance=instance
        self.display_name=display_name
        self.sleep=sleep

    def _frame(self):
        from module.ocr import ocr
        image, origin, scale=self.auto.take_screenshot()
        if not image or not scale:
            raise RuntimeError("未取得速刷画面")
        width,height=image.size
        words=[]
        for box,(text,confidence) in ocr.recognize_multi_lines(image) or []:
            xs=[float(p[0]) for p in box]; ys=[float(p[1]) for p in box]
            words.append(Word(text,(min(xs)+max(xs))/2/width,
                              (min(ys)+max(ys))/2/height,float(confidence)))
        return image,origin,scale,words

    def _click(self, frame, x, y):
        image,origin,scale,_=frame
        px=int(origin[0]+x*image.width/scale)
        py=int(origin[1]+y*image.height/scale)
        return self.auto.click_element_with_pos(((px-1,py-1),(px+1,py+1)))

    def _fatal(self, message):
        from tasks.base.task_steps import GameRecoveryError
        raise GameRecoveryError(message)

    def _cancel(self):
        frame=self._frame()
        words=frame[3]
        title=exact(words,"快速刷取",region=(.3,.13,.7,.40))
        cancel=exact(words,"取消",region=(.22,.48,.52,.88))
        if not(title and cancel and self._click(frame,cancel.x,cancel.y)):
            self._fatal("助燃券速刷弹窗未能安全取消")
        self.sleep(.5)
        words=self._frame()[3]
        if not any(normalized(w.text)=="进入" for w in words):
            self._fatal("取消助燃券速刷后未确认返回副本列表")
        return False

    def prepare(self,batch):
        from tasks.base.list_drag import drag_list
        from tasks.power.instance import ENTRY_ROWS
        self.instance.select_category(batch.instance_type)
        for i in range(12):
            frame=self._frame(); words=frame[3]
            # Do not use icon matching against arbitrary dialog or wrong category.
            button=entry_button(words,batch.instance_type,batch.name,self.display_name)
            if button:
                icon=ticket_icon(frame[0],button)
                if not icon:
                    return False
                if not self._click(frame,*icon):
                    self._fatal("未确认助燃券入口点击结果")
                self.sleep(.6)
                for _ in range(5):
                    f=self._frame()
                    if confirm_dialog(f[3],batch,self.display_name):
                        return True
                    if exact(f[3],"快速刷取",region=(.3,.13,.7,.4)):
                        if exact(f[3],"取消",region=(.22,.48,.52,.88)):
                            return self._cancel()
                    self.sleep(.25)
                self._fatal("助燃券入口点击后未识别到可安全取消的确认页")
            if i==11:
                return False
            if not drag_list(self.auto,(1125/1920,810/1080),(1125/1920,410/1080),
                             crop=ENTRY_ROWS,end_pause=.2,settle=.45):
                return False
        return False

    def submit(self,batch):
        frame=self._frame()
        button=confirm_dialog(frame[3],batch,self.display_name)
        if not button:
            self._fatal("助燃券消费确认页发生变化，未提交")
        if not self._click(frame,button.x,button.y):
            self._fatal("助燃券确认点击结果不明，停止后续消耗")

    def read_receipt(self):
        batch=self.batch
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            frame=self._frame()
            if receipt:=receipt_dialog(frame[3],batch,self.display_name):
                return receipt
            self.sleep(.6)
        self._fatal("助燃券已提交但无法核对真实结算，停止后续消耗")

    def close_receipt(self):
        frame=self._frame()
        if not receipt_dialog(frame[3],self.batch,self.display_name):
            self._fatal("已记账但结算页变化，停止后续刷取")
        button=exact(frame[3],"关闭",region=(.16,.55,.56,.98))
        if not button or not self._click(frame,button.x,button.y):
            self._fatal("已记账但未能关闭速刷结算")
        self.sleep(.5)
        if not any(normalized(w.text)=="进入" for w in self._frame()[3]):
            self._fatal("速刷后未确认返回副本列表")

    def run_one(self,category,name,available):
        # Single transaction verified by the dialog. Do not guess ticket inventory:
        # an orange enabled entry and an exact, affordable one-run cost must be observed.
        # The 1/3 here bounds the requested transaction, NOT an observed stock reading.
        budget=3 if category=="凝滞虚影" else 1
        self.batch=plan_fuel_ticket_batch(category,name,1,available,budget,enabled=True)
        if self.batch is None:
            return 0
        try:
            return execute_fuel_ticket_batch(self,self.batch)
        except FuelTicketSettlementUnknown as e:
            self._fatal(str(e))
        except Exception as e:
            from tasks.base.task_steps import FATAL_GAME_ERRORS
            if isinstance(e,FATAL_GAME_ERRORS):
                raise
            self._fatal("助燃券流程结果不明，禁止自动回退："+str(e))

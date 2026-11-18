"""PC 快速刷取适配器。单次事务：识别副本、校验消费、一次提交、真实回执。

仅支持已观察的简体中文 PC 界面。找不到明确入口时保留原清体力流程；
提交后或无法安全取消时抛出致命恢复错误，不猜测、不自动补扣。
"""
from dataclasses import dataclass
import re
import time
import unicodedata

from tasks.power.fuel_ticket import (
    FuelTicketBatch, FuelTicketReceipt, FuelTicketSettlementUnknown, verify_fuel_ticket_receipt,
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


def refine_cost_words(image, words, recognize):
    """Read small numbers again from the SAME frame, never from plan data."""
    anchor = exact(words, "消耗", region=(.26,.15,.86,.90))
    if not anchor or _costs(words, anchor) is not None:
        return words
    width,height=image.size
    # Different UI panels render the small ticket count against slightly
    # different backgrounds. Try two bounded crops; conflicting reads fail.
    options=[]
    prior=[w for w in words if w.confidence>=.75 and
           re.fullmatch(r"[0-9]{1,3}",normalized(w.text)) and
           anchor.x+.012<w.x<anchor.x+.16 and abs(w.y-anchor.y)<.018]
    regions=[(anchor.x-left,anchor.y-half,anchor.x+right,anchor.y+half,False)
             for left,right,half in ((.025,.155,.020),(.030,.144,.022))]
    # Observed 1920x1080 PC single-result panel; only when its cost label
    # is in the verified position. A separate grayscale read guards tiny digits.
    if .665<anchor.x<.685 and .36<anchor.y<.38:
        regions.extend(((.645,.348,.818,.392,False),(.646,.345,.800,.394,True)))
    for left,top,right,bottom,contrast in regions:
        x1,x2=max(0,round(left*width)),min(width,round(right*width))
        y1,y2=max(0,round(top*height)),min(height,round(bottom*height))
        if x2<=x1 or y2<=y1:
            continue
        crop=image.crop((x1,y1,x2,y2))
        enlarged=crop.resize((crop.width*4,crop.height*4))
        if contrast:
            from PIL import ImageOps
            enlarged=ImageOps.autocontrast(enlarged.convert("L")).convert("RGB")
        refined=[Word(w.text,(x1+w.x*crop.width)/width,(y1+w.y*crop.height)/height,w.confidence)
                 for w in recognize(enlarged)]
        label=exact(refined,"消耗")
        if not label or abs(label.x-anchor.x)>.018 or abs(label.y-anchor.y)>.012:
            continue
        values=_costs(refined,label)
        if values is None:
            continue
        if any(not any(normalized(w.text)==normalized(old.text) and abs(w.x-old.x)<.015
                       for w in refined) for old in prior):
            return words
        options.append((values,refined,(x1,y1,x2,y2)))
    if not options or len({v for v,_,_ in options})!=1:
        return words
    _,refined,(x1,y1,x2,y2)=options[0]
    return [w for w in words if not (x1/width<=w.x<=x2/width and y1/height<=w.y<=y2/height)]+refined


def stock_reading(words):
    """Confirmed dialog/receipt top bar: tickets may exceed the storage cap."""
    def pair(region, cap):
        l,t,r,b=region
        values=set()
        for w in words:
            if w.confidence<.75 or not(l<w.x<r and t<w.y<b):
                continue
            m=re.fullmatch(r"(\d{1,6})/"+str(cap),normalized(w.text))
            if m:
                values.add(int(m[1]))
        return next(iter(values)) if len(values)==1 else None
    tickets=pair((.63,.035,.738,.085),1000)
    power=pair((.83,.035,.93,.085),300)
    if tickets is None or power is None:
        return None
    return (tickets,power)


def count_plus(words):
    """Known PC slider geometry, independent of OCR reading the plus glyph.

    Only use after the actual target/single-run confirmation has been verified.
    The count label must still be in the known slider row.
    """
    labels = [w for w in words if w.confidence >= .75
              and .30 < w.x < .65 and .43 < w.y < .55
              and re.fullmatch(r"刷取次数[0-9]{0,2}", normalized(w.text))]
    return (.698, .546) if len(labels) == 1 else None


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
             re.fullmatch(r"刷取次数"+str(batch.waves),normalized(w.text))
             and title.y<w.y<cancel.y]
    # Accept split count label/number only when they are paired on the same row.
    if not count:
        n = exact(words,"刷取次数",region=(.3,title.y,.65,cancel.y))
        if not n or not any(w.confidence>=.75 and normalized(w.text)==str(batch.waves)
                            and .005<w.x-n.x<.075 and abs(w.y-n.y)<.015 for w in words):
            return None
    cost = exact(words,"消耗",region=(.30,title.y,.65,cancel.y))
    if not cost:
        return None
    costs = _costs(words,cost)
    if costs != (batch.power,batch.tickets):
        # The tiny coupon digit may disappear in OCR. A clearly read stamina
        # amount plus sufficient observed coupon inventory is enough; never
        # accept a contradictory pair of visible costs.
        nums = [w for w in words if w.confidence >= .75
                and re.fullmatch(r"[0-9]{1,3}", normalized(w.text))
                and cost.x+.012 < w.x < cost.x+.20 and abs(w.y-cost.y)<.018]
        stock = stock_reading(words)
        if (costs is not None or len(nums)!=1 or int(normalized(nums[0].text))!=batch.power
                or not stock or stock[0]<batch.tickets or stock[1]<batch.power):
            return None
    return confirm


def receipt_dialog(words, batch, display_name, *, before_stock=None, after_stock=None):
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
                      and .0<w.x-anchor.x<.20 and re.fullmatch(r"\d{1,2}\s*/\s*\d{1,2}", w.text.strip())]
            if len(values)==1:
                progress=tuple(int(v.strip()) for v in values[0].text.split("/"))
    if progress!=(batch.waves,batch.waves):
        return None
    if batch.waves > 1:
        # Large receipts scroll: the full set of reward rows and the final
        # row need not be visible. The labelled N/N progress is authoritative.
        # Cross-check the selected reward name or real stock movement, not
        # the number of OCR boxes. A known contradictory reward is not valid.
        label = normalized(display_name+batch.instance_type)
        targets = [w for w in words if w.confidence >= .75 and title.y < w.y < close.y
                   and any(normalized(w.text).endswith(normalized(kind)) for kind in
                           ("拟造花萼（金）", "拟造花萼（赤）", "凝滞虚影"))]
        if any(normalized(w.text)!=label for w in targets):
            return None
        stock_ok = (before_stock is not None and after_stock is not None
                    and before_stock[0]-after_stock[0] == batch.tickets
                    and before_stock[1]-after_stock[1] in (batch.power,batch.power-1))
        if not targets and not stock_ok:
            return None
        # A visible per-wave cost is useful but need not be on-screen.
        for cost in (w for w in words if normalized(w.text)=="消耗"
                     and w.confidence>=.75 and .55<w.x<.9 and title.y<w.y<close.y):
            nums=sorted((w for w in words if w.confidence>=.75
                         and cost.x+.012<w.x<cost.x+.115 and abs(w.y-cost.y)<.018
                         and re.fullmatch(r"[0-9]{1,3}",normalized(w.text))),key=lambda w:w.x)
            if nums and int(normalized(nums[0].text))!=batch.power//batch.waves:
                return None
        # The confirmed dialog established unit cost; N/N establishes the
        # actual completed count. Do not depend on OCR of every reward row.
        return FuelTicketReceipt(batch.instance_type,batch.name,progress[0],progress[1],
                                 progress[0]*(batch.power//batch.waves),
                                 progress[0]*(batch.tickets//batch.waves))
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
        def recognize(frame):
            width,height=frame.size
            words=[]
            for box,(text,confidence) in ocr.recognize_multi_lines(frame) or []:
                xs=[float(p[0]) for p in box]; ys=[float(p[1]) for p in box]
                words.append(Word(text,(min(xs)+max(xs))/2/width,
                                  (min(ys)+max(ys))/2/height,float(confidence)))
            return words
        words=refine_cost_words(image,recognize(image),recognize)
        if (exact(words,"快速刷取",region=(.3,.06,.7,.4))
                and stock_reading(words) is None):
            for rect in ((.627,.037,.738,.085),(.827,.035,.932,.085)):
                l,t,r,b=rect
                x1,y1,x2,y2=round(l*image.width),round(t*image.height),round(r*image.width),round(b*image.height)
                crop=image.crop((x1,y1,x2,y2))
                enlarged=crop.resize((crop.width*4,crop.height*4))
                words.extend(Word(w.text,(x1+w.x*crop.width)/image.width,
                                  (y1+w.y*crop.height)/image.height,w.confidence)
                             for w in recognize(enlarged))
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
                    if batch.waves>1:
                        single=FuelTicketBatch(batch.instance_type,batch.name,1,
                                               batch.power//batch.waves,batch.tickets//batch.waves)
                        if confirm_dialog(f[3],single,self.display_name):
                            balances=stock_reading(f[3])
                            if balances:
                                chosen=plan_fuel_ticket_batch(batch.instance_type,batch.name,
                                    batch.waves,min(batch.power,balances[1]),balances[0],enabled=True)
                                if chosen is None:
                                    return self._cancel()
                                self.batch=chosen
                                batch=chosen
                            if batch.waves==1:
                                return True
                            pos=count_plus(f[3])
                            if not pos or not 1.69<f[0].width/f[0].height<1.82:
                                return self._cancel()
                            # All these inputs are non-paying slider clicks.
                            # Verify the actual count and total before confirming.
                            for _ in range(batch.waves-1):
                                if not self._click(f,*pos):
                                    return self._cancel()
                                self.sleep(.12)
                            self.sleep(.5)
                            for _ in range(3):
                                selected=self._frame()
                                if confirm_dialog(selected[3],batch,self.display_name):
                                    return True
                                self.sleep(.3)
                            return self._cancel()
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
        self.before_stock=stock_reading(frame[3])
        if batch.waves>1 and self.before_stock and (self.before_stock[0]<batch.tickets or self.before_stock[1]<batch.power):
            self._fatal("助燃券批量库存不能核实，未提交")
        if not self._click(frame,button.x,button.y):
            self._fatal("助燃券确认点击结果不明，停止后续消耗")

    def read_receipt(self):
        batch=self.batch
        deadline=time.monotonic()+max(30, 10+3*batch.waves)
        while time.monotonic()<deadline:
            frame=self._frame()
            if receipt:=receipt_dialog(frame[3],batch,self.display_name,before_stock=self.before_stock,after_stock=stock_reading(frame[3])):
                return receipt
            self.sleep(.6)
        self._fatal("助燃券已提交但无法核对真实结算，停止后续消耗")

    def close_receipt(self):
        frame=self._frame()
        if not receipt_dialog(frame[3],self.batch,self.display_name,before_stock=self.before_stock,after_stock=stock_reading(frame[3])):
            self._fatal("已记账但结算页变化，停止后续刷取")
        button=exact(frame[3],"关闭",region=(.16,.55,.56,.98))
        if not button or not self._click(frame,button.x,button.y):
            self._fatal("已记账但未能关闭速刷结算")
        self.sleep(.5)
        if not any(normalized(w.text)=="进入" for w in self._frame()[3]):
            self._fatal("速刷后未确认返回副本列表")

    def run_batch(self,category,name,available,requested):
        # Request all affordable waves up to the game's per-dialog limit.
        # Actual inventory is read from the opened dialog and can reduce this.
        cost=30 if category=="凝滞虚影" else 10
        batch=plan_fuel_ticket_batch(category,name,requested,available,available//10,enabled=True)
        if batch is not None and batch.waves>1:
            result=self._run(batch)
            if result:
                return result
        return self.run_one(category,name,available)

    def run_one(self,category,name,available):
        # Single transaction verified by the dialog. Do not guess ticket inventory:
        # an orange enabled entry and an exact, affordable one-run cost must be observed.
        # The 1/3 here bounds the requested transaction, NOT an observed stock reading.
        budget=3 if category=="凝滞虚影" else 1
        batch=plan_fuel_ticket_batch(category,name,1,available,budget,enabled=True)
        if batch is None:
            return 0
        return self._run(batch)

    def _run(self,batch):
        self.batch=batch
        self.before_stock=None
        try:
            if not self.prepare(self.batch):
                return 0
            self.submit(self.batch)
            return verify_fuel_ticket_receipt(self.batch,self.read_receipt())
        except FuelTicketSettlementUnknown as e:
            self._fatal(str(e))
        except Exception as e:
            from tasks.base.task_steps import FATAL_GAME_ERRORS
            if isinstance(e,FATAL_GAME_ERRORS):
                raise
            self._fatal("助燃券流程结果不明，禁止自动回退："+str(e))

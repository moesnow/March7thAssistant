"""Read only unread, unlocked stories in the Amphoreus chronicle."""
from pathlib import Path
import time

import cv2
import numpy as np

from module.automation.screenshot import Screenshot
from module.logger import log


class HeroChronicleReader:
    def __init__(self, click, title):
        self.click = click
        self.title = title
        self.templates = {}
        folder = Path('assets/images/autoplot/hero_chronicle')
        for name in ('header', 'directory', 'return', 'read', 'unread', 'locked', 'next_arrow', 'ending'):
            raw = np.fromfile(folder / (name + '.png'), dtype=np.uint8)
            self.templates[name] = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        self.reset()

    def reset(self):
        self.hero = 0
        self.visited = set()
        self.current_row = None
        self.phase = 'directory'
        self.deadline = 0
        self.finished = False
        self.completed = False
        self.last_signature = None
        self.stalled = 0
        self.stories = 0

    def score(self, frame, name, box):
        x1, y1, x2, y2 = box
        image = frame[y1:y2, x1:x2]
        template = self.templates[name]
        if image.shape[0] < template.shape[0] or image.shape[1] < template.shape[1]:
            return 0
        return float(cv2.minMaxLoc(cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED))[1])

    @staticmethod
    def page_dots(frame):
        """Recognize grey page dots and the gold active-page ring."""
        strip = frame[1008:1031, 350:1400]
        hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
        grey = cv2.inRange(hsv, (0, 0, 95), (179, 75, 195))
        gold = cv2.inRange(hsv, (8, 80, 110), (38, 255, 255))
        dots = []
        for mask, active in ((grey, False), (gold, True)):
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                area = cv2.contourArea(contour)
                perimeter = cv2.arcLength(contour, True)
                circularity = 4 * np.pi * area / max(1, perimeter * perimeter)
                if 9 <= w <= 19 and 9 <= h <= 19 and circularity > 0.65:
                    dots.append((x + w / 2, active))
        dots.sort()
        # Discard duplicate contours belonging to the same ring.
        unique = []
        for x, active in dots:
            if unique and x - unique[-1][0] < 12:
                unique[-1] = (x, active or unique[-1][1])
            else:
                unique.append((x, active))
        if not unique or sum(active for _, active in unique) != 1:
            return None
        return next(i for i, (_, active) in enumerate(unique) if active), len(unique)

    def act(self, point, delay=2.2):
        self.click(point)
        self.deadline = time.monotonic() + delay

    def tick(self):
        if self.finished or time.monotonic() < self.deadline:
            return self.phase != 'directory' and not self.finished
        result = Screenshot.take_screenshot(self.title)
        if not result:
            return False
        image, region, scale = result
        frame = cv2.cvtColor(np.array(image.resize((1920, 1080))), cv2.COLOR_RGB2BGR)
        if self.score(frame, 'header', (20, 15, 350, 120)) < 0.8:
            return False
        # Coordinates are recalculated from this fresh capture on every action.
        self.region = (region[0], region[1], region[2] / scale, region[3] / scale)
        is_directory = self.score(frame, 'directory', (350, 420, 540, 530)) > 0.88
        if is_directory:
            if self.hero >= 12:
                self.finished = True
                self.completed = True
                log.info(f'翁法罗斯英雄纪阅读完成：已阅读 {self.stories} 篇未读故事；已读及未解锁故事已跳过')
                return True
            self.visited.clear()
            self.current_row = None
            self.phase = 'chapters'
            x = 460 + 213 * (self.hero % 6)
            y = 608 + 268 * (self.hero // 6)
            self.act((x, y))
            log.info(f'翁法罗斯英雄纪：打开第 {self.hero + 1}/12 位英雄')
            return True
        if self.score(frame, 'return', (1360, 40, 1650, 125)) < 0.88:
            return True  # Wait for book/page animations; never click an unknown layout.
        if self.phase == 'directory':
            # Starting halfway through any hero must go to the full index first.
            # Otherwise we cannot know which hero the current page belongs to.
            self.act((1510, 85))
            return True
        available = []
        known_chapters = False
        for row, y in enumerate((375, 442, 510, 577, 644)):
            box = (925, y - 23, 978, y + 23)
            scores = {name: self.score(frame, name, box) for name in ('read', 'unread', 'locked')}
            best = max(scores, key=scores.get)
            if scores[best] > 0.9:
                known_chapters = True
                if best == 'unread':
                    available.append((row, y))
        if known_chapters:
            self.stalled = 0
            for row, y in available:
                if row not in self.visited:
                    self.current_row = row
                    self.phase = 'reading'
                    self.last_signature = None
                    self.act((1280, y))
                    log.info(f'翁法罗斯英雄纪：阅读第 {self.hero + 1} 位英雄第 {row + 1} 篇故事')
                    return True
            log.info(f'翁法罗斯英雄纪：第 {self.hero + 1} 位英雄没有剩余可阅读的未读篇章，跳过')
            self.hero += 1
            self.phase = 'directory'
            self.act((1510, 85))
            return True
        dots = self.page_dots(frame)
        if dots:
            if self.current_row is None:
                # Starting in a reading page: return to chapter overview first.
                self.act((1740, 245))
                return True
            signature = (self.hero, self.current_row, dots)
            self.stalled = self.stalled + 1 if signature == self.last_signature else 0
            self.last_signature = signature
            if self.stalled >= 120:
                self.finished = True
                log.error('翁法罗斯英雄纪翻页无进展，阅读已停止。请检查游戏窗口，重新关闭/开启阅读选项重试')
                return True
            next_visible = self.score(frame, 'next_arrow', (1660, 965, 1740, 1025)) > 0.88
            ending_visible = self.score(frame, 'ending', (1160, 960, 1400, 1030)) > 0.88
            if dots[0] == dots[1] - 1 and (next_visible or ending_visible):
                self.visited.add(self.current_row)
                self.stories += 1
                self.current_row = None
                self.act((1740, 245))
            elif not next_visible:
                # Unread stories reveal text in several beats; the page-turn
                # arrow appears only after the narration on this page finishes.
                self.act((1250, 900), delay=0.45)
            else:
                self.act((1705, 995), delay=0.8)
            return True
        # A chapter with all stories locked, or unsupported layout: do not guess.
        self.stalled += 1
        if self.stalled >= 8:
            self.finished = True
            log.error('翁法罗斯英雄纪页面无法确认，阅读已停止；没有把未确认的故事标记为完成')
        self.deadline = time.monotonic() + 1
        return True

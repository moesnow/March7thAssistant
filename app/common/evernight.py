"""Logo and overview-mascot click sequences, and the first-unlock animation state."""
from collections import deque
from time import monotonic


EVEY_ANIMATION = './assets/app/images/evernight/evey-floating.png'
# 来源 -> (连点几下出提示, 这几下要在几秒内)。总览小人点了本来就会弹，随手连点的人多，门槛比 LOGO 高。
WARNING_CLICKS = {'logo': (5, 5), 'mascot': (10, 10)}
UNLOCK_CLICKS = 5
WARNING_SECONDS = 5  # 提示持续的时间，与问候区提示的动画时长一致


class _ClickSequence:
    def __init__(self, clicks, seconds):
        self._needed, self._seconds = clicks, seconds
        self.reset()

    def reset(self):
        self.clicks = deque(maxlen=self._needed)
        self.warning_until = None

    def record(self, now):
        if self.warning_until is not None and now > self.warning_until:
            self.reset()
        self.clicks.append(now)
        if self.warning_until is not None:
            return 'unlocked' if len(self.clicks) == UNLOCK_CLICKS else None
        if len(self.clicks) == self._needed and now - self.clicks[0] <= self._seconds:
            self.clicks = deque(maxlen=UNLOCK_CLICKS)
            self.warning_until = now + WARNING_SECONDS
            return 'warning'
        return None


class EvernightEasterEgg:
    def __init__(self, clock=monotonic, *, unlocked=False):
        self._clock = clock
        self._sequences = {source: _ClickSequence(*rule) for source, rule in WARNING_CLICKS.items()}
        self.unlocked = unlocked
        self.selected = False
        self.animation_played = unlocked

    def record_click(self, source='logo'):
        """Quick clicks warn (logo: 5 within 5 s, mascot: 10 within 10 s); 5 more within the warning unlock.

        Each source keeps its own count. Once unlocked, no source counts any more."""
        if self.unlocked:
            return None
        result = self._sequences[source].record(self._clock())
        if result == 'unlocked':
            self.unlocked = True
            for sequence in self._sequences.values():
                sequence.reset()
        return result

    def consume_animation(self, selected):
        """Claim the first-unlock animation while the theme is selected."""
        if not selected or not self.unlocked or self.animation_played:
            return False
        self.animation_played = True
        return True

"""Logo click sequence and Evernight theme state."""
from collections import deque
from time import monotonic


EVEY_ANIMATION = './assets/app/images/evernight/evey-floating.png'


class EvernightEasterEgg:
    def __init__(self, clock=monotonic, *, unlocked=False):
        self._clock = clock
        self._clicks = deque(maxlen=5)
        self._warning_until = None
        self.unlocked = unlocked
        self.selected = False
        self.animation_pending = False

    def reset_clicks(self):
        self._clicks.clear()
        self._warning_until = None

    def record_click(self):
        """Five quick clicks warn; five more within the warning trigger the egg."""
        if self.selected:
            return None
        now = self._clock()
        if self._warning_until is not None and now > self._warning_until:
            self.reset_clicks()
        self._clicks.append(now)
        if len(self._clicks) == 5 and now - self._clicks[0] <= 5:
            self._clicks.clear()
            if self._warning_until is None:
                self._warning_until = now + 5
                return 'warning'
            self._warning_until = None
            return 'triggered'
        return None

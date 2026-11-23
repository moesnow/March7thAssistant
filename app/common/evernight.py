"""Logo click sequence and first-unlock animation state."""
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
        self.animation_played = unlocked

    def record_click(self):
        """Five quick clicks warn; five more within the warning unlock the egg."""
        if self.unlocked:
            return None
        now = self._clock()
        if self._warning_until is not None and now > self._warning_until:
            self._warning_until = None
            self._clicks.clear()
        self._clicks.append(now)
        if len(self._clicks) == 5 and now - self._clicks[0] <= 5:
            self._clicks.clear()
            if self._warning_until is None:
                self._warning_until = now + 5
                return 'warning'
            self.unlocked = True
            self._warning_until = None
            return 'unlocked'
        return None

    def consume_animation(self, selected):
        """Claim the first-unlock animation while the theme is selected."""
        if not selected or not self.unlocked or self.animation_played:
            return False
        self.animation_played = True
        return True

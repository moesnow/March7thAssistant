"""Session-only Easter egg state; system theme changes never count as clicks."""
from collections import deque
from time import monotonic


EVERNIGHT_BANNER = './assets/app/images/evernight/banner.png'
EVERNIGHT_AVATAR = './assets/app/images/dark/Evernight.png'
EVEY_ANIMATION = './assets/app/images/evernight/evey-floating.png'


class EvernightEasterEgg:
    def __init__(self, clock=monotonic):
        self._clock = clock
        self._clicks = deque(maxlen=5)
        self._warning_until = None
        self.unlocked = False
        self.selected = False
        self.animation_played = False

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
        """Claim the one playback only when the session theme is selected."""
        if not selected or not self.unlocked or self.animation_played:
            return False
        self.animation_played = True
        return True

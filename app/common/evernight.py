"""Session-only Easter egg state; system theme changes never count as clicks."""
from collections import deque
from time import monotonic


EVERNIGHT_BANNER = './assets/app/images/evernight/banner.png'
EVERNIGHT_AVATAR = './assets/app/images/evernight/avatar.png'
EVEY_ANIMATION = './assets/app/images/evernight/evey-floating.png'


class EvernightEasterEgg:
    def __init__(self, clock=monotonic):
        self._clock = clock
        self._toggles = deque(maxlen=3)
        self.unlocked = False
        self.animation_played = False

    def record_manual_toggle(self):
        if self.unlocked:
            return
        now = self._clock()
        self._toggles.append(now)
        if len(self._toggles) == 3 and now - self._toggles[0] <= 5:
            self.unlocked = True
            self._toggles.clear()

    def consume_animation(self, dark):
        """Claim the one playback only when the unlocked dark UI is visible."""
        if not dark or not self.unlocked or self.animation_played:
            return False
        self.animation_played = True
        return True

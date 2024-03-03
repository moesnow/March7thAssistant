from .memoryofchaos import MemoryOfChaos
from .memoryone import MemoryOne
from .purefiction import PureFiction
from typing import Literal
from managers.config_manager import config


class ChallengeManager:
    def __init__(self):
        self.game_modes = {
            "memoryofchaos": MemoryOfChaos(config.forgottenhall_team1, config.forgottenhall_team2, config.forgottenhall_level, config.hotkey_technique, config.auto_battle_detect_enable),
            "purefiction": PureFiction(config.purefiction_team1, config.purefiction_team2, config.purefiction_level, config.hotkey_technique, config.auto_battle_detect_enable),
            "memoryone": MemoryOne(config.daily_memory_one_team, config.hotkey_technique, config.auto_battle_detect_enable),
        }

    def run(self, mode: Literal["memoryofchaos", "purefiction", "memoryone"], count=1):
        game_mode = self.game_modes.get(mode)
        if mode == "memoryone":
            return game_mode.run(count)
        else:
            game_mode.run()


def start(mode: Literal["memoryofchaos", "purefiction", "memoryone"], count=1):
    challenge_manager = ChallengeManager()
    challenge_manager.run(mode, count)


def start_memory_one(count=1):
    if config.daily_memory_one_enable:
        challenge_manager = ChallengeManager()
        return challenge_manager.run("memoryone", count)

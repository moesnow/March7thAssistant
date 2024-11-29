from .memoryofchaos import MemoryOfChaos
from .memoryone import MemoryOne
from .purefiction import PureFiction
from .apocalyptic import Apocalyptic
from typing import Literal
from module.config import cfg


class ChallengeManager:
    def __init__(self):
        self.game_modes = {
            "memoryofchaos": MemoryOfChaos(cfg.forgottenhall_team1, cfg.forgottenhall_team2, cfg.forgottenhall_level, cfg.hotkey_technique, cfg.auto_battle_detect_enable),
            "purefiction": PureFiction(cfg.purefiction_team1, cfg.purefiction_team2, cfg.purefiction_level, cfg.hotkey_technique, cfg.auto_battle_detect_enable),
            "memoryone": MemoryOne(cfg.daily_memory_one_team, cfg.hotkey_technique, cfg.auto_battle_detect_enable),
            "apocalyptic": Apocalyptic(cfg.apocalyptic_team1, cfg.apocalyptic_team2, cfg.apocalyptic_level, cfg.hotkey_technique, cfg.auto_battle_detect_enable),
        }

    def run(self, mode: Literal["memoryofchaos", "purefiction", "memoryone", "apocalyptic"], count=1):
        game_mode = self.game_modes.get(mode)
        if mode == "memoryone":
            return game_mode.run(count)
        else:
            game_mode.run()


def start(mode: Literal["memoryofchaos", "purefiction", "memoryone"], count=1):
    challenge_manager = ChallengeManager()
    challenge_manager.run(mode, count)


def start_memory_one(count=1):
    if cfg.daily_memory_one_enable:
        challenge_manager = ChallengeManager()
        return challenge_manager.run("memoryone", count)

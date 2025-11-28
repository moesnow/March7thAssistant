from module.game.cloud import CloudGameController
from module.config import cfg
from module.game.base import GameControllerBase
from module.game.local import LocalGameController
from module.logger import log

cloud_game: CloudGameController = CloudGameController(cfg=cfg, logger=log)
local_game: LocalGameController = LocalGameController(cfg=cfg, logger=log)

def get_game_controller() -> GameControllerBase:
    if cfg.cloud_game_enable:
        return cloud_game
    else:
        return local_game
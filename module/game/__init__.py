from module.config import cfg
from module.config.platform import ControlBackend, get_control_backend
from module.localization import tr
from module.logger import log
from module.game.base import GameControllerBase
from module.game.cloud import CloudGameController
from module.game.local import LocalGameController

cloud_game: CloudGameController = CloudGameController(cfg=cfg, logger=log)
local_game: LocalGameController = LocalGameController(cfg=cfg, logger=log)


class AdbBackendUnavailableError(NotImplementedError):
    def __init__(self):
        super().__init__(tr("ADB 后端尚未实现"))


def _get_local_controller() -> LocalGameController:
    local_game.reload_config(cfg)
    return local_game


def _get_adb_controller() -> GameControllerBase:
    raise AdbBackendUnavailableError()


_CONTROLLER_FACTORIES = {
    "local": _get_local_controller,
    "cloud": lambda: cloud_game,
    "adb": _get_adb_controller,
}


def get_game_controller(backend: ControlBackend | None = None) -> GameControllerBase:
    if backend is None:
        backend = get_control_backend(cfg)
    return _CONTROLLER_FACTORIES[backend]()

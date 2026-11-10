from module.config import cfg
from module.config.platform import ControlBackend, get_control_backend
from module.logger import log
from module.game.adb import AdbGameController
from module.game.adb_transport import AdbError
from module.game.base import GameControllerBase
from module.game.cloud import CloudGameController
from module.game.local import LocalGameController
from module.localization import tr

cloud_game: CloudGameController = CloudGameController(cfg=cfg, logger=log)
local_game: LocalGameController = LocalGameController(cfg=cfg, logger=log)

adb_game = AdbGameController(cfg=cfg, logger=log)


def require_desktop_task(config, task: str) -> None:
    if get_control_backend(config) == "adb":
        raise AdbError("desktop_task_unsupported", tr(
            "ADB 模式不支持「{task}」，请使用本地或云游戏后端"
        ).format(task=task))


def _get_local_controller() -> LocalGameController:
    local_game.reload_config(cfg)
    return local_game


_CONTROLLER_FACTORIES = {
    "local": _get_local_controller,
    "cloud": lambda: cloud_game,
    "adb": lambda: adb_game,
}


def get_game_controller(backend: ControlBackend | None = None) -> GameControllerBase:
    if backend is None:
        backend = get_control_backend(cfg)
    return _CONTROLLER_FACTORIES[backend]()

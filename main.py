from tasks.game.game import Game
from tasks.power.power import Power
from tasks.daily.daily import Daily
from tasks.version.version import Version
from managers.notify_manager import notify
from managers.logger_manager import logger
from tasks.daily.fight import Fight
from tasks.weekly.universe import Universe
from tasks.weekly.forgottenhall import ForgottenHall
import pyuac
import sys
import os


def main(action=None):
    if action is None or action == "main":
        while True:
            Version.check()
            Game.start()
            Power.start()
            Daily.start()
            Game.stop()
    else:
        Version.check()
        Game.start()
        if action == "fight":
            Fight.start()
        elif action == "universe":
            Universe.start()
        elif action == "forgottenhall":
            ForgottenHall.start()
        else:
            logger.warning(f"Unknown action: {action}")
            os.system("pause")
            exit(1)
        os.system("pause")
        exit(0)


if __name__ == "__main__":
    if not pyuac.isUserAdmin():
        sys.exit(pyuac.runAsAdmin(wait=False))
    else:
        try:
            main(sys.argv[1]) if len(sys.argv) > 1 else main()
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            notify.notify(f"An error occurred: {e}")

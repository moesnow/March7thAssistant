from tasks.game.game import Game
from tasks.power.power import Power
from tasks.daily.daily import Daily
from tasks.version.version import Version
from managers.notify_manager import notify
from managers.logger_manager import logger
from tasks.daily.fight import Fight
from tasks.weekly.universe import Universe
from tasks.weekly.forgottenhall import ForgottenHall
import sys


def perform_action(action):
    # Implement your logic here based on the provided action
    if action == "fight":
        Fight.start()
    elif action == "universe":
        Universe.start()
    elif action == "forgottenhall":
        ForgottenHall.start()
    elif action == "main":
        main()
    else:
        print("Unknown action")


def main(action=None):
    if action is None:
        while True:
            Version.check()
            Game.start()
            Power.start()
            Daily.start()
            Game.stop()
    else:
        perform_action(action)


if __name__ == "__main__":
    try:
        main(sys.argv[1]) if len(sys.argv) > 1 else main()
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        notify.notify(f"An error occurred: {e}")

from tasks.game.game import Game
from tasks.power.power import Power
from tasks.daily.daily import Daily
from managers.notify_manager import notify
from managers.logger_manager import logger


def main():
    while True:
        Game.start()
        Power.start()
        Daily.start()
        Game.stop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        notify.notify(f"An error occurred: {e}")

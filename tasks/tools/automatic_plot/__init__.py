from managers.logger_manager import logger
from .autoclick import AutoClick
import tkinter as tk
import multiprocessing


def run_gui():
    try:
        root = tk.Tk()
        AutoClick(root)
        root.mainloop()
    except Exception as e:
        logger.error(e)


def automatic_plot():
    gui_process = multiprocessing.Process(target=run_gui)
    gui_process.start()

from managers.logger import logger
from .autoclick import AutoClick
import tkinter as tk
import threading


def run_gui():
    try:
        root = tk.Tk()
        AutoClick(root)
        root.mainloop()
    except Exception as e:
        logger.error(e)


def automatic_plot():
    gui_thread = threading.Thread(target=run_gui)
    gui_thread.start()

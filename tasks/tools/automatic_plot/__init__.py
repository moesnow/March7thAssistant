from .autoclick import AutoClick
import tkinter as tk


def automatic_plot():
    try:
        root = tk.Tk()
        app = AutoClick(root)
        root.mainloop()
    except Exception:
        pass

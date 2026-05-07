import os
import sys


os.chdir(
    os.path.dirname(sys.executable)
    if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__))
)

from module.update.helper_app import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

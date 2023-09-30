from managers.ocr_manager import check_path
from tasks.weekly.universe import Universe
from tasks.daily.fight import Fight

if __name__ == "__main__":
    check_path()
    Universe.check_path()
    Fight.check_path()

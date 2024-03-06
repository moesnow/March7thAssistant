from managers.logger import logger
from managers.ocr import OCRInstaller
from tasks.weekly.universe import Universe
from tasks.daily.fight import Fight

if __name__ == "__main__":
    ocr_installer = OCRInstaller(logger)
    ocr_installer.check_and_install()
    Universe.check_path()
    Fight.check_path()

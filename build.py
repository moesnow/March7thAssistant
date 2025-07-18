from module.logger import log
from module.ocr import OCRInstaller
from tasks.weekly.universe import Universe
from tasks.daily.fight import Fight

if __name__ == "__main__":
    ocr_installer = OCRInstaller(log)
    ocr_installer.check_and_install()
    Universe.update()
    Fight.update()

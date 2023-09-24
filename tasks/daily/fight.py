from tasks.base.download import download_with_progress
from managers.screen_manager import screen
from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _
from tasks.base.base import Base
from tasks.base.pythonchecker import PythonChecker
from tasks.base.runsubprocess import RunSubprocess
import subprocess
import shutil
import os


class Fight:
    @staticmethod
    def start():
        logger.hr(_("准备锄大地"), 2)

        if PythonChecker.run(config.python_path):
            python_path = os.path.abspath(config.python_path)
            if not os.path.exists(config.fight_path):
                logger.error(_("锄大地路径不存在: {path}").format(path=config.fight_path))
                if not Fight.update():
                    Base.send_notification_with_screenshot(_("⚠️锄大地未完成⚠️"))
                    return False

            if config.fight_team_enable:
                Base.change_team(config.fight_team_number)

            screen.change_to('main')

            logger.info(_("开始安装依赖"))
            if RunSubprocess.run(f"set PATH={python_path};{python_path}\\Scripts;%PATH% && cd {config.fight_path} && pip install -i {config.pip_mirror} -r requirements.txt", 3600):
                logger.info(_("开始锄大地"))
                if RunSubprocess.run(f"set PATH={python_path};{python_path}\\Scripts;%PATH% && cd {config.fight_path} && python Fast_Star_Rail.py", config.fight_timeout * 3600):
                    config.save_timestamp("fight_timestamp")
                    Base.send_notification_with_screenshot(_("🎉锄大地已完成🎉"))
                    return
                else:
                    logger.info(_("锄大地失败"))
            else:
                logger.info(_("依赖安装失败"))
        Base.send_notification_with_screenshot(_("⚠️锄大地未完成⚠️"))

    @staticmethod
    def gui():
        if PythonChecker.run(config.python_path):
            python_path = os.path.abspath(config.python_path)
            if not os.path.exists(config.fight_path):
                logger.error(_("锄大地路径不存在: {path}").format(path=config.fight_path))
                if not Fight.update():
                    return False
            if subprocess.run(f"set PATH={python_path};{python_path}\\Scripts;%PATH% && cd {config.fight_path} && pip install -i {config.pip_mirror} -r requirements.txt", shell=True, check=True):
                if subprocess.run(f"set PATH={python_path};{python_path}\\Scripts;%PATH% && cd {config.fight_path} && start 点我点我.exe", shell=True, check=True):
                    return True
        return False

    @staticmethod
    def update():
        url = f"{config.github_mirror}https://github.com/linruowuyin/Fhoe-Rail/archive/master.zip"
        destination = '.\\3rdparty\\Fhoe-Rail.zip'
        extracted_folder_path = '.\\3rdparty'

        try:
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            logger.info(_("开始下载：{url}").format(url=url))
            download_with_progress(url, destination)
            logger.info(_("下载完成：{destination}").format(destination=destination))

            shutil.unpack_archive(destination, extracted_folder_path, 'zip')
            logger.info(_("解压完成：{path}").format(path=extracted_folder_path))

            folder = '.\\3rdparty\\Fhoe-Rail-master'
            Fight.copy_and_replace_folder_contents(config.fight_path, folder)
            logger.info(_("更新完成：{path}").format(path=config.fight_path))

            os.remove(destination)
            shutil.rmtree(folder)
            logger.info(_("清理完成：{path}").format(path=destination))
            return True
        except Exception as e:
            logger.error(_("下载失败：{e}").format(e=e))
            return False

    @staticmethod
    def copy_and_replace_folder_contents(folder_a, folder_b):
        # 检查 folder_a 是否存在，如果不存在则创建它
        if not os.path.exists(folder_a):
            os.makedirs(folder_a)
        # 复制文件夹B中的所有文件到文件夹A，直接覆盖同名文件
        for item in os.listdir(folder_b):
            source = os.path.join(folder_b, item)
            destination = os.path.join(folder_a, item)

            # 如果文件夹A中已经存在同名文件，就删除它
            if os.path.exists(destination):
                if os.path.isdir(destination):
                    shutil.rmtree(destination)
                else:
                    os.remove(destination)

            # 复制文件或文件夹，直接覆盖同名文件
            if os.path.isdir(source):
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)

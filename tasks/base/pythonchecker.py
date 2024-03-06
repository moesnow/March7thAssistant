from tasks.base.download import download_with_progress
from managers.logger import logger
from managers.config import config
from utils.command import subprocess_with_stdout
from utils.gamecontroller import GameController
from packaging.version import parse
import subprocess
import tempfile
import sys
import os


class PythonChecker:
    @staticmethod
    def run():
        if config.python_exe_path != '' and PythonChecker.check(config.python_exe_path):
            return
        else:
            paths = subprocess_with_stdout(["where", "python.exe"])
            if paths is not None:
                for path in paths.split("\n"):
                    if PythonChecker.check(path):
                        config.set_value("python_exe_path", path)
                        logger.debug(f"Python 路径更新成功: {path}")
                        return

        logger.warning("没有在环境变量中找到可用的 Python 路径")
        logger.warning("如果已经修改了环境变量，请尝试重启程序，包括图形界面")
        logger.warning("可以通过在 cmd 中输入 python -V 自行判断是否成功")
        logger.warning("也可卸载后重新运行或在 config.yaml 中手动修改 python_exe_path")
        input("按回车键开始自动安装 Python 3.11.5 64bit")

        PythonChecker.install()

    @staticmethod
    def install():
        download_url = "http://mirrors.huaweicloud.com/python/3.11.5/python-3.11.5-amd64.exe"
        download_file_path = os.path.join(tempfile.gettempdir(), os.path.basename(download_url))
        destination_path = os.path.join(os.getenv('LocalAppData'), r'Programs\Python\Python311\python.exe')

        while True:
            try:
                os.makedirs(os.path.dirname(download_file_path), exist_ok=True)
                logger.info(f"开始下载: {download_url}")
                download_with_progress(download_url, download_file_path)
                logger.info(f"下载完成: {download_file_path}")
                break
            except Exception as e:
                logger.error(f"下载失败: {e}")
                input("按回车键重试. . .")

        while True:
            try:
                if not subprocess.run(f"{download_file_path} /passive InstallAllUsers=0 PrependPath=1 Include_launcher=0 Include_test=0", check=True):
                    raise Exception
                logger.info("安装完成")
                break
            except Exception as e:
                logger.error(f"安装失败: {e}")
                input("按回车键重试. . .")

        try:
            os.remove(download_file_path)
            logger.info(f"清理完成: {download_file_path}")
        except Exception as e:
            logger.error(f"清理失败: {e}")

        if PythonChecker.check(destination_path):
            config.set_value("python_exe_path", destination_path)
            game = GameController(config.game_path, config.game_process_name, config.game_title_name, 'UnityWndClass', logger)
            game.switch_to_game()
            return

        logger.info("安装完成，请重启程序，包括图形界面")
        input("按回车键关闭窗口. . .")
        sys.exit(0)

    @staticmethod
    def check(path):
        # 检查 Python 和 pip 是否可用
        python_result = subprocess_with_stdout([path, '-V'])
        if python_result is not None and python_result[0:7] == "Python ":
            python_version = python_result.split(' ')[1]
            if parse(python_version) < parse("3.7"):
                logger.error(f"Python 版本过低: {python_version} < 3.7")
                return False
            else:
                logger.debug(f"Python 版本: {python_version}")
                python_arch = subprocess_with_stdout([path, '-c', 'import platform; print(platform.architecture()[0])'])
                logger.debug(f"Python 架构: {python_arch}")
                if "32" in python_arch:
                    logger.error("不支持 32 位 Python")
                    return False
            pip_result = subprocess_with_stdout([path, "-m", "pip", '-V'])
            if pip_result is not None and pip_result[0:4] == "pip ":
                pip_version = pip_result.split(' ')[1]
                logger.debug(f"pip 版本: {pip_version}")
                return True
            else:
                logger.debug("开始安装 pip")
                from tasks.base.fastest_mirror import FastestMirror
                if subprocess.run([path, ".\\assets\\config\\get-pip.py", "-i", FastestMirror.get_pypi_mirror()], check=True):
                    logger.debug("pip 安装完成")
                    return True
                else:
                    logger.error("pip 安装失败")
                    return False
        return False

from tasks.base.download import download_with_progress
from managers.logger_manager import logger
from managers.config_manager import config
from managers.translate_manager import _
from tasks.base.runsubprocess import RunSubprocess
from tasks.base.windowswitcher import WindowSwitcher
from tasks.base.command import run_command
import os


class PythonChecker:
    @staticmethod
    def run(python_path=config.python_path):
        if python_path != '' and PythonChecker.check(python_path):
            return True
        else:
            paths = run_command("where python")
            if paths is not None:
                for path in paths.split("\n"):
                    path_dir = os.path.dirname(path)
                    if PythonChecker.check(path_dir):
                        config.set_value("python_path", path_dir)
                        logger.debug(_("Python路径更新成功：{path}").format(path=path))
                        return True
            logger.warning(_("没有在环境变量中找到可用的 Python 路径"))
            logger.warning(_("如果已经修改了环境变量，请尝试重启程序，包括图形界面"))

        logger.warning(_("Python路径不存在: {path}").format(path=python_path))

        url = "http://mirrors.huaweicloud.com/python/3.11.5/python-3.11.5-amd64.exe"
        destination = '.\\3rdparty\\python-3.11.5-amd64.exe'

        local_app_data = os.getenv('LocalAppData')
        destination_path = os.path.join(local_app_data, 'Programs\Python\Python311')
        # extracted_folder_path = '.\\3rdparty\\python-3.11.5-embed-amd64'

        try:
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            logger.info(_("开始下载：{url}").format(url=url))
            download_with_progress(url, destination)
            logger.info(_("下载完成：{destination}").format(destination=destination))

            os.system(f"{destination} /passive InstallAllUsers=0 PrependPath=1 Include_launcher=0 Include_test=0")
            logger.info(_("安装完成"))

            WindowSwitcher.check_and_switch(config.game_title_name)

            # shutil.unpack_archive(destination, extracted_folder_path, 'zip')
            # logger.info(_("解压完成：{path}").format(path=extracted_folder_path))

            os.remove(destination)
            # os.remove(f"{extracted_folder_path}\\python311._pth")
            logger.info(_("清理完成：{path}").format(path=destination))

            if PythonChecker.check(destination_path):
                config.set_value("python_path", destination_path)
                return True

            logger.error(_("仍未找到可用的 Python 路径，请尝试重启程序，包括图形界面"))
            logger.error(_("也可卸载后重新运行或在 config.yaml 中手动修改 python_path（文件夹）"))
            return False
        except Exception as e:
            logger.error(_("下载失败：{e}").format(e=e))
            return False

    @staticmethod
    def check(python_path):
        python_result = run_command([f"{python_path}\\python.exe", '-V'])
        if python_result is not None and python_result[0:7] == "Python ":
            logger.debug(_("Python 路径: {path}").format(path=python_path))
            python_version = python_result.split(' ')[1]
            if python_version < "3.11":
                logger.warning(_("Python 版本: {version} < 3.11 若出现异常请尝试升级").format(version=python_version))
            else:
                logger.debug(_("Python 版本: {version}").format(version=python_version))
            pip_result = run_command([f"{python_path}\\Scripts\\pip.exe", '-V'])
            if pip_result is not None and pip_result[0:4] == "pip ":
                pip_version = pip_result.split(' ')[1]
                logger.debug(_("pip 版本: {version}").format(version=pip_version))
                return True
            else:
                logger.debug(_("开始安装 pip"))
                if RunSubprocess.run(f"{python_path}\\python.exe .\\assets\\config\\get-pip.py -i {config.pip_mirror} --no-warn-script-location", 600):
                    logger.debug(_("pip 安装完成"))
                    return True
                else:
                    logger.error(_("pip 安装失败"))
                    return False
        return False

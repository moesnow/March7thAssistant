from managers.logger_manager import logger
from managers.config_manager import config
from managers.translate_manager import _
from tasks.base.runsubprocess import RunSubprocess
import subprocess
import requests
import zipfile
import os


class PythonChecker:
    @staticmethod
    def run(python_path):
        if PythonChecker.check(python_path):
            return True
        else:
            path_dirs = os.environ["PATH"].split(os.pathsep)
            for path_dir in path_dirs:
                if "Python" in path_dir:
                    if PythonChecker.check(path_dir):
                        config.set_value("python_path", path_dir)
                        logger.debug(_("Python路径更新成功：{path}").format(path=path_dir))
                        return True

        logger.error(_("Python路径不存在: {path}").format(path=python_path))

        url = "https://mirrors.huaweicloud.com/python/3.11.5/python-3.11.5-embed-amd64.zip"
        destination = '.\\3rdparty\\python-3.11.5-embed-amd64.zip'

        logger.info(_("开始下载：{url}").format(url=url))
        response = requests.get(url)
        if response.status_code == 200:
            with open(destination, 'wb') as file:
                file.write(response.content)
                logger.info(_("下载完成：{destination}").format(destination=destination))
        else:
            logger.error(_("下载失败：{code}").format(code=response.status_code))
            return False

        extracted_folder_path = '.\\3rdparty\\python-3.11.5-embed-amd64'
        with zipfile.ZipFile(destination, 'r') as zip_ref:
            zip_ref.extractall(extracted_folder_path)
        logger.info(_("解压完成：{path}").format(path=extracted_folder_path))

        os.remove(destination)
        os.remove(f"{extracted_folder_path}\\python311._pth")
        logger.info(_("清理完成：{path}").format(path=destination))

        if PythonChecker.check(extracted_folder_path):
            config.set_value("python_path", extracted_folder_path)
            return True
        return False

    @staticmethod
    def check(python_path):
        python_result = PythonChecker.run_command([f"{python_path}\\python.exe", '-V'])
        if python_result[0:7] == "Python ":
            logger.debug(f"Python 版本: {python_result.split(' ')[1]}")
            pip_result = PythonChecker.run_command([f"{python_path}\\Scripts\\pip.exe", '-V'])
            if pip_result[0:4] == "pip ":
                logger.debug(f"pip 版本: {pip_result.split(' ')[1]}")
                return True
            else:
                logger.debug("开始安装pip")
                if RunSubprocess.run(f"{python_path}\\python.exe .\\assets\\config\\get-pip.py -i {config.pip_mirror} --no-warn-script-location", 600):
                    logger.debug(_("pip安装完成"))
                    return True
                else:
                    logger.error(_("pip安装失败"))
                    return False
        return False

    @staticmethod
    def run_command(command):
        try:
            # 使用subprocess运行命令并捕获标准输出
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # 检查命令是否成功执行
            if result.returncode == 0:
                # 返回标准输出的内容
                return result.stdout.strip()
            else:
                # 如果命令执行失败，返回错误信息
                return f"Command execution failed with error: {result.stderr.strip()}"
        except Exception as e:
            return str(e)

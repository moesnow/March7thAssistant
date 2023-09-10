from managers.logger_manager import logger
from managers.translate_manager import _
import subprocess


class PythonChecker:
    @staticmethod
    def check():
        python_result = PythonChecker.run_command(['python', '-V'])
        if python_result[0:7] == "Python ":
            logger.debug(f"Python version: {python_result.split(' ')[1]}")
            pip_result = PythonChecker.run_command(['pip', '-V'])
            if pip_result[0:4] == "pip ":
                logger.debug(f"pip version: {pip_result.split(' ')[1]}")
                return True
            else:
                logger.error(_("未安装pip或未正确设置环境变量"))
        else:
            logger.error(_("未安装Python环境或未正确设置环境变量"))
        logger.info(_("视频教程：https://www.bilibili.com/video/BV13h4y1m7VP?t=115"))
        logger.info(_("可以从 QQ 群文件(855392201)获取 Python 3.11.5 安装包"))
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

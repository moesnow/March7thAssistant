import subprocess
from module.logger import log


def subprocess_with_timeout(command, timeout, working_directory=None, env=None):
    process = None
    try:
        process = subprocess.Popen(command, cwd=working_directory, env=env)
        process.communicate(timeout=timeout)
        if process.returncode == 0:
            return True
    except subprocess.TimeoutExpired:
        log.error(f"超时停止")
        if process is not None:
            process.terminate()
            process.wait()
    return False


def subprocess_with_stdout(command):
    try:
        # 使用subprocess运行命令并捕获标准输出
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # 检查命令是否成功执行
        if result.returncode == 0:
            # 返回标准输出的内容
            return result.stdout.strip()
        return None
    except Exception:
        return None

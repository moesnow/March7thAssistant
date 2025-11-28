import atexit
import concurrent.futures
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
from packaging.version import parse
from tqdm import tqdm
import requests
import psutil
import urllib.request
from urllib.request import urlopen
from urllib.error import URLError
from utils.color import red, green
from utils.logger.logger import Logger


class Updater:
    """应用程序更新器，负责检查、下载、解压和安装最新版本的应用程序。"""

    def __init__(self, logger: Logger, download_url=None, file_name=None):
        self.logger = logger
        self.process_names = ["March7th Assistant.exe", "March7th Launcher.exe", "flet.exe", "gui.exe"]
        self.api_urls = [
            "https://api.github.com/repos/moesnow/March7thAssistant/releases/latest",
            "https://github.kotori.top/https://api.github.com/repos/moesnow/March7thAssistant/releases/latest",
        ]
        self.temp_path = os.path.abspath("./temp")
        os.makedirs(self.temp_path, exist_ok=True)
        self.download_url = download_url
        self.file_name = file_name
        self.cover_folder_path = os.path.abspath("./")
        self.exe_path = os.path.abspath("./assets/binary/7za.exe")
        self.aria2_path = os.path.abspath("./assets/binary/aria2c.exe")
        self.delete_folder_path = os.path.join("./3rdparty/Fhoe-Rail", "map")

        self.logger.hr("获取下载链接", 0)
        if download_url is None:
            self.download_url = self.get_download_url()
            self.logger.info(f"下载链接: {green(self.download_url)}")
            self.logger.hr("完成", 2)
            input("按回车键开始更新")
        else:
            self.logger.info(f"下载链接: {green(self.download_url)}")
            self.logger.hr("完成", 2)
        # 兼容外部仅传入 download_url 的情况
        if not self.file_name and self.download_url:
            self.file_name = os.path.basename(self.download_url)
        if not self.file_name:
            raise ValueError("无法确定更新文件名(file_name)")
        self.download_file_path = os.path.join(self.temp_path, self.file_name)
        self.extract_folder_path = os.path.join(self.temp_path, self.file_name.rsplit(".", 1)[0])

    def get_download_url(self):
        """检测更新并获取下载URL。"""
        self.logger.info("开始检测更新")
        fastest_mirror = self.find_fastest_mirror(self.api_urls)
        try:
            with urlopen(fastest_mirror, timeout=10) as response:
                if response.getcode() == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return self.process_release_data(data)
        except URLError as e:
            self.logger.error(f"检测更新失败: {red(e)}")
            input("按回车键重试...")
            return self.get_download_url()

    def process_release_data(self, data):
        """处理发布数据，获取下载URL并比较版本。"""
        version = data["tag_name"]
        download_url = None
        for asset in data["assets"]:
            if "full" in asset["browser_download_url"]:
                download_url = asset["browser_download_url"]
                self.file_name = asset["name"]
                break

        if download_url is None:
            raise Exception("没有找到合适的下载URL")

        self.compare_versions(version)
        return download_url

    def compare_versions(self, version):
        """比较本地版本和远程版本。"""
        try:
            with open("./assets/config/version.txt", 'r', encoding='utf-8') as file:
                current_version = file.read().strip()
            if parse(version.lstrip('v')) > parse(current_version.lstrip('v')):
                self.logger.info(f"发现新版本: {current_version} ——> {version}")
            else:
                self.logger.info(f"本地版本: {current_version}")
                self.logger.info(f"远程版本: {version}")
                self.logger.info("当前已是最新版本")
        except Exception as e:
            self.logger.info(f"本地版本获取失败: {e}")
            self.logger.info(f"最新版本: {version}")

    def find_fastest_mirror(self, mirror_urls, timeout=5):
        """测速并找到最快的镜像。"""
        def check_mirror(mirror_url):
            try:
                start_time = time.time()
                response = requests.head(mirror_url, timeout=timeout, allow_redirects=True)
                end_time = time.time()
                if response.status_code == 200:
                    return mirror_url, end_time - start_time
            except Exception:
                pass
            return None, None

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(check_mirror, url) for url in mirror_urls]
            fastest_mirror, _ = min((future.result() for future in concurrent.futures.as_completed(futures)), key=lambda x: (x[1] is not None, x[1]), default=(None, None))

        return fastest_mirror if fastest_mirror else mirror_urls[0]

    def download_with_progress(self):
        """下载文件并显示进度条。"""
        self.logger.hr("下载", 0)
        proxies = urllib.request.getproxies()
        if not self.download_url:
            raise ValueError("download_url 未设置")
        url = self.download_url
        while True:
            try:
                self.logger.info("开始下载...")
                if os.path.exists(self.aria2_path):
                    command = [
                        self.aria2_path,
                        "--disable-ipv6=true",
                        "--dir={}".format(os.path.dirname(self.download_file_path)),
                        "--out={}".format(os.path.basename(self.download_file_path)),
                        url
                    ]

                    if "github.com" in url:
                        command.insert(2, "--max-connection-per-server=16")
                        # 仅在下载 GitHub 资源时启用断点续传，避免416错误
                        if os.path.exists(self.download_file_path):
                            command.insert(2, "--continue=true")
                    # 代理设置
                    for scheme, proxy in proxies.items():
                        if scheme in ("http", "https", "ftp"):
                            command.append(f"--{scheme}-proxy={proxy}")
                    subprocess.run(command, check=True)

                else:
                    response = requests.head(url, allow_redirects=True)
                    response.raise_for_status()
                    file_size = int(response.headers.get('Content-Length', 0))

                    with tqdm(total=file_size, unit='B', unit_scale=True, unit_divisor=1024) as pbar:
                        with requests.get(url, stream=True) as r:
                            with open(self.download_file_path, 'wb') as f:
                                for chunk in r.iter_content(chunk_size=1024):
                                    if chunk:
                                        f.write(chunk)
                                        pbar.update(len(chunk))

                self.logger.info(f"下载完成: {green(self.download_file_path)}")
                break

            except Exception:
                self.logger.error(red('下载失败: 请检查网络连接是否正常，或切换更新源后重试。'))
                input("按回车键重试. . .")
        self.logger.hr("完成", 2)

    def extract_file(self):
        """解压下载的文件。"""
        self.logger.hr("解压", 0)
        while True:
            try:
                self.logger.info("开始解压...")
                if os.path.exists(self.exe_path):
                    subprocess.run([self.exe_path, "x", self.download_file_path, f"-o{self.temp_path}", "-aoa"], check=True)
                else:
                    shutil.unpack_archive(self.download_file_path, self.temp_path)
                self.logger.info(f"解压完成: {green(self.extract_folder_path)}")
                self.logger.hr("完成", 2)
                return True
            except Exception as e:
                self.logger.error(f"解压失败: {red(e)}")
                self.logger.hr("完成", 2)
                input("按回车键重新下载. . .")
                if os.path.exists(self.download_file_path):
                    os.remove(self.download_file_path)
                return False

    def cover_folder(self):
        """覆盖安装最新版本的文件。"""
        self.logger.hr("覆盖", 0)
        while True:
            try:
                self.logger.info("开始覆盖...")
                if "full" in (self.file_name or "") and os.path.exists(self.delete_folder_path):
                    shutil.rmtree(self.delete_folder_path)
                shutil.copytree(self.extract_folder_path, self.cover_folder_path, dirs_exist_ok=True)
                self.logger.info(f"覆盖完成: {green(self.cover_folder_path)}")
                break
            except Exception as e:
                self.logger.error(f"覆盖失败: {red(e)}")
                input("按回车键重试. . .")
        self.logger.hr("完成", 2)

    def terminate_processes(self):
        """终止相关进程以准备更新。"""
        self.logger.hr("终止进程", 0)
        self.logger.info("开始终止进程...")
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            if proc.info['name'] in self.process_names:
                try:
                    proc.terminate()
                    proc.wait(10)
                except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied):
                    pass
        self.logger.info(green("终止进程完成"))
        self.logger.hr("完成", 2)

    def cleanup(self):
        """清理下载和解压的临时文件。"""
        self.logger.hr("清理", 0)
        self.logger.info("开始清理...")
        # 增强删除：重试 + 延时脚本 + 重启后删除兜底
        archive_ok = self._robust_remove(self.download_file_path, is_dir=False)
        extract_ok = self._robust_remove(self.extract_folder_path, is_dir=True)

        if archive_ok:
            self.logger.info(f"清理完成: {green(self.download_file_path)}")
        else:
            self.logger.error(f"清理失败(被占用): {self.download_file_path}")
            self._schedule_delayed_delete(self.download_file_path)

        if extract_ok:
            self.logger.info(f"清理完成: {green(self.extract_folder_path)}")
        else:
            self.logger.error(f"清理失败(被占用): {self.extract_folder_path}")
            self._schedule_delayed_delete(self.extract_folder_path)

        self.logger.hr("完成", 2)

    # ---------------- 内部工具方法 -----------------
    def _robust_remove(self, path, is_dir=False, retries=6, base_delay=0.3):
        """带重试与指数退避删除文件/目录。返回True表示成功删除或不存在。"""
        if not path:
            return True
        if not os.path.exists(path):
            return True
        for attempt in range(retries):
            try:
                if is_dir:
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                return True
            except PermissionError:
                # 文件被占用，等待后重试
                time.sleep(base_delay * (2 ** attempt))
            except OSError as e:
                # 其它错误直接跳出（例如路径错误）
                if e.winerror == 32:  # 占用同样重试
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                return False
        # 最终失败，注册进程退出再试一次
        atexit.register(self._final_attempt_delete, path, is_dir)
        # 兜底：安排重启后删除
        self._schedule_delete_on_reboot(path)
        return False

    def _final_attempt_delete(self, path, is_dir):
        try:
            if is_dir and os.path.exists(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass

    def _schedule_delayed_delete(self, path):
        """创建一个延时执行的批处理文件，进程结束后自动尝试删除。"""
        if not os.path.exists(path):
            return
        bat_name = f"del_{int(time.time())}.bat"
        bat_path = os.path.join(self.temp_path, bat_name)
        # 使用 ping 延时，尝试多次删除，最后自删脚本
        script = (
            "@echo off\r\n"
            "REM 延时等待占用的进程释放文件句柄\r\n"
            "ping 127.0.0.1 -n 6 >nul\r\n"
            f"if exist \"{path}\" del /f /q \"{path}\"\r\n"
            f"if exist \"{path}\" (ping 127.0.0.1 -n 6 >nul & del /f /q \"{path}\")\r\n"
            "REM 如果仍存在则保持等待再尝试一次\r\n"
            f"if exist \"{path}\" (ping 127.0.0.1 -n 10 >nul & del /f /q \"{path}\")\r\n"
            f"if exist \"{path}\" echo 未能删除: {path}\r\n"
            f"del /f /q \"%~f0\"\r\n"
        )
        try:
            with open(bat_path, 'w', encoding='utf-8') as f:
                f.write(script)
            subprocess.Popen(['cmd.exe', '/c', bat_path], creationflags=subprocess.DETACHED_PROCESS)
            self.logger.info(f"已安排延时删除: {green(path)}")
        except Exception as e:
            self.logger.error(f"延时删除脚本创建失败: {e}")

    def _schedule_delete_on_reboot(self, path):
        """使用 Win32 MoveFileEx 在重启后删除（最后兜底）。"""
        if not os.path.exists(path):
            return
        try:
            MOVEFILE_DELAY_UNTIL_REBOOT = 0x4
            ctypes.windll.kernel32.MoveFileExW(path, None, MOVEFILE_DELAY_UNTIL_REBOOT)
            self.logger.info(f"注册重启后删除: {green(path)}")
        except Exception:
            # 在某些限制环境可能失败，忽略
            pass

    def run(self):
        """运行更新流程。"""
        while True:
            self.download_with_progress()
            if self.extract_file():
                break
        self.terminate_processes()
        self.cover_folder()
        self.cleanup()
        try:
            if sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
                input("按回车键退出并打开软件")
        except Exception:
            pass
        if os.system(f'cmd /c start "" "{os.path.abspath("./March7th Launcher.exe")}"'):
            subprocess.Popen(os.path.abspath("./March7th Launcher.exe"))


def check_temp_dir_and_run():
    """检查临时目录并运行更新程序。"""
    temp_path = os.path.abspath("./temp")

    # 开发/未打包环境：直接运行，便于调试或回退启动
    if not getattr(sys, 'frozen', False):
        download_url = sys.argv[1] if len(sys.argv) >= 2 else None
        file_name = sys.argv[2] if len(sys.argv) >= 3 else None
        logger = Logger()
        updater = Updater(logger, download_url, file_name)
        updater.run()
        return

    # 打包环境：复制到 temp 后以独立进程执行，避免文件句柄占用
    file_path = sys.argv[0]
    destination_path = os.path.join(temp_path, os.path.basename(file_path))

    if file_path != destination_path:
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path)
        if os.path.exists("./Update.exe"):
            os.remove("./Update.exe")
        os.makedirs(temp_path, exist_ok=True)
        shutil.copy(file_path, destination_path)
        args = [destination_path] + sys.argv[1:]
        subprocess.Popen(args, creationflags=subprocess.DETACHED_PROCESS)
        sys.exit(0)

    download_url = sys.argv[1] if len(sys.argv) >= 2 else None
    file_name = sys.argv[2] if len(sys.argv) >= 3 else None
    logger = Logger()
    updater = Updater(logger, download_url, file_name)
    updater.run()


if __name__ == '__main__':
    check_temp_dir_and_run()

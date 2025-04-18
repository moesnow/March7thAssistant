import concurrent.futures
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
        return self.find_fastest_mirror([download_url, f"https://github.kotori.top/{download_url}"])

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
                self.logger.info(f"当前已是最新版本")
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
        while True:
            try:
                self.logger.info("开始下载...")
                if os.path.exists(self.aria2_path):
                    command = [self.aria2_path, "--dir={}".format(os.path.dirname(self.download_file_path)),
                               "--out={}".format(os.path.basename(self.download_file_path)), self.download_url]
                    if "github.com" in self.download_url:
                        command.insert(2, "--max-connection-per-server=16")
                    if os.path.exists(self.download_file_path):
                        command.insert(2, "--continue=true")
                    subprocess.run(command, check=True)
                else:
                    response = requests.head(self.download_url)
                    file_size = int(response.headers.get('Content-Length', 0))

                    with tqdm(total=file_size, unit='B', unit_scale=True, unit_divisor=1024) as pbar:
                        with requests.get(self.download_url, stream=True) as r:
                            with open(self.download_file_path, 'wb') as f:
                                for chunk in r.iter_content(chunk_size=1024):
                                    if chunk:
                                        f.write(chunk)
                                        pbar.update(len(chunk))
                self.logger.info(f"下载完成: {green(self.download_file_path)}")
                break
            except Exception as e:
                self.logger.error(f"下载失败: {red(e)}")
                input("按回车键重试. . .")
                if os.path.exists(self.download_file_path):
                    os.remove(self.download_file_path)
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
                if "full" in self.file_name and os.path.exists(self.delete_folder_path):
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
        try:
            os.remove(self.download_file_path)
            self.logger.info(f"清理完成: {green(self.download_file_path)}")
            shutil.rmtree(self.extract_folder_path)
            self.logger.info(f"清理完成: {green(self.extract_folder_path)}")
        except Exception as e:
            self.logger.error(f"清理失败: {e}")
        self.logger.hr("完成", 2)

    def run(self):
        """运行更新流程。"""
        self.terminate_processes()
        while True:
            self.download_with_progress()
            if self.extract_file():
                break
        self.cover_folder()
        self.cleanup()
        input("按回车键退出并打开软件")
        if os.system(f'cmd /c start "" "{os.path.abspath("./March7th Launcher.exe")}"'):
            subprocess.Popen(os.path.abspath("./March7th Launcher.exe"))


def check_temp_dir_and_run():
    """检查临时目录并运行更新程序。"""
    if not getattr(sys, 'frozen', False):
        print("更新程序只支持打包成exe后运行")
        sys.exit(1)

    temp_path = os.path.abspath("./temp")
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

    download_url = sys.argv[1] if len(sys.argv) == 3 else None
    file_name = sys.argv[2] if len(sys.argv) == 3 else None
    logger = Logger()
    updater = Updater(logger, download_url, file_name)
    updater.run()


if __name__ == '__main__':
    check_temp_dir_and_run()

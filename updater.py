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
from time import sleep


class Updater:
    """应用程序更新器，负责检查、下载、解压和安装最新版本的应用程序。"""

    def __init__(self, logger: Logger, download_url=None, file_name=None, auto_mode=False, max_try=-1, autostart=False):
        self.auto_mode = auto_mode
        self.max_try = max_try
        self.logger = logger
        self.process_names = ["March7th Assistant.exe", "March7th Launcher.exe", "flet.exe", "gui.exe"]
        another = os.getenv("m7a_another", "moesnow")
        repo = os.getenv("m7a_repo", "March7thAssistant")
        self.api_urls = [
            f"https://api.github.com/repos/{another}/{repo}/releases/latest",
            #f"https://github.kotori.top/https://api.github.com/repos/{another}/{repo}/releases/latest",
            f"https://gh-proxy.com/https://api.github.com/repos/{another}/{repo}/releases/latest",
        ]
        self.temp_path = os.path.abspath("./temp")
        os.makedirs(self.temp_path, exist_ok=True)
        self.download_url = download_url
        self.file_name = file_name
        self.cover_folder_path = os.path.abspath("./")
        self.exe_path = os.path.abspath("./assets/binary/7za.exe")
        self.aria2_path = os.path.abspath("./assets/binary/aria2c.exe")
        self.delete_folder_path = os.path.join("./3rdparty/Fhoe-Rail", "map")

        self.use_patch = False
        self.patch_file_name = None
        self.patch_download_url = None
        self.local_version = None

        self.autostart = autostart
        self.latest_version = None
        self.is_latest = False

        self.logger.hr("获取下载链接", 0)
        if download_url is None:
            self.download_url, self.file_name = self.get_download_url_and_filename()
            self.logger.info(f"下载链接: {green(self.download_url)}")
            self.logger.hr("完成", 2)
            if not self.auto_mode and not self.autostart:
                input("按回车键开始更新")
        else:
            self.logger.info(f"下载链接: {green(self.download_url)}")
            self.logger.hr("完成", 2)
        self.download_file_path = os.path.join(self.temp_path, self.file_name)
        self.extract_folder_path = os.path.join(self.temp_path, self.file_name.rsplit(".", 1)[0])

    def get_download_url_and_filename(self):
        """检测更新并获取下载URL和文件名，优先使用增量包。"""
        self.logger.info("开始检测更新")
        fastest_mirror = self.find_fastest_mirror(self.api_urls)
        self.logger.info(f"最快的镜像: {green(fastest_mirror)}")
        try:
            with urlopen(fastest_mirror, timeout=10) as response:
                if response.getcode() == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return self.process_release_data_with_patch(data)
        except URLError as e:
            self.logger.error(f"检测更新失败: {red(e)}")
            if not self.auto_mode and not self.autostart:
                input("按回车键重试...")
            if self.max_try == 0:
                self.logger.info(f"已停止自动重试")
                sys.exit(1)
            else:
                self.logger.info(f"重试中")
                self.max_try -= 1
            return self.get_download_url_and_filename()

    def process_release_data_with_patch(self, data):
        """处理发布数据，优先查找增量包，否则回退到full包。"""
        version = data["tag_name"]
        self.latest_version = version
        self.local_version = self.get_local_version()
        patch_name = f"March7thAssistant_patch_{self.local_version}_to_{version}.zip"
        patch_url = None
        full_url = None
        full_name = None

        for asset in data["assets"]:
            if asset["name"] == patch_name:
                patch_url = asset["browser_download_url"]
                self.patch_file_name = patch_name
            if "full" in asset["browser_download_url"]:
                full_url = asset["browser_download_url"]
                full_name = asset["name"]

        self.is_latest = self.compare_versions(version)
        # 优先使用增量包
        if patch_url:
            self.use_patch = True
            self.patch_download_url = self.find_fastest_mirror([patch_url, f"https://gh-proxy.com/{patch_url}"])
            return self.patch_download_url, patch_name
        elif full_url:
            self.use_patch = False
            return self.find_fastest_mirror([full_url, f"https://gh-proxy.com/{full_url}"]), full_name
        else:
            raise Exception("没有找到合适的下载URL")

    def get_local_version(self):
        """获取本地版本号"""
        try:
            with open("./assets/config/version.txt", 'r', encoding='utf-8') as file:
                return file.read().strip()
        except Exception:
            return "unknown"

    def compare_versions(self, version):
        """比较本地版本和远程版本。返回是否为最新。"""
        try:
            with open("./assets/config/version.txt", 'r', encoding='utf-8') as file:
                current_version = file.read().strip()
            if parse(version.lstrip('v')) > parse(current_version.lstrip('v')):
                self.logger.info(f"发现新版本: {current_version} ——> {version}")
                return False
            else:
                self.logger.info(f"本地版本: {current_version}")
                self.logger.info(f"远程版本: {version}")
                self.logger.info(f"当前已是最新版本")
                if self.auto_mode and not self.autostart:
                    sys.exit(0)
                return True
        except Exception as e:
            self.logger.info(f"本地版本获取失败: {e}")
            self.logger.info(f"最新版本: {version}")
            if self.auto_mode and not self.autostart:
                sys.exit(0)
            return True

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
                if not self.auto_mode:
                    input("按回车键重试. . .")
                    
                if self.max_try == 0:
                    self.logger.info(f"已停止自动重试")
                    sys.exit(1)
                else:
                    self.logger.info(f"重试中")
                    self.max_try -= 1
                
                
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
                if not self.auto_mode:
                    input("按回车键重新下载. . .")
                if self.max_try == 0:
                    self.logger.info(f"已停止自动重试")
                    sys.exit(1)
                else:
                    self.logger.info(f"重试中")
                    self.max_try -= 1
                if os.path.exists(self.download_file_path):
                    os.remove(self.download_file_path)
                return False

    def cover_folder(self):
        """覆盖安装最新版本的文件。"""
        self.logger.hr("覆盖", 0)
        while True:
            try:
                self.logger.info("开始覆盖...")
                if self.use_patch:
                    # 增量包：apply patch
                    self.apply_patch()
                else:
                    # 全量包
                    if "full" in self.file_name and os.path.exists(self.delete_folder_path):
                        shutil.rmtree(self.delete_folder_path)
                    shutil.copytree(self.extract_folder_path, self.cover_folder_path, dirs_exist_ok=True)
                self.logger.info(f"覆盖完成: {green(self.cover_folder_path)}")
                break
            except Exception as e:
                self.logger.error(f"覆盖失败: {red(e)}")
                if not self.auto_mode:
                    input("按回车键重试. . .")
                if self.max_try == 0:
                    self.logger.info(f"已停止自动重试")
                    sys.exit(1)
                else:
                    self.logger.info(f"重试中")
                    self.max_try -= 1
        self.logger.hr("完成", 2)

    def apply_patch(self):
        """应用增量包：复制变更文件，删除removefile.txt中列出的文件。"""
        patch_dir = self.extract_folder_path
        # 1. 删除removefile.txt中列出的文件
        removefile_path = os.path.join(patch_dir, "removefile.txt")
        if os.path.exists(removefile_path):
            with open(removefile_path, "r", encoding="utf-8") as f:
                for line in f:
                    rel_path = line.strip()
                    if not rel_path:
                        continue
                    abs_path = os.path.join(self.cover_folder_path, rel_path)
                    if os.path.exists(abs_path):
                        try:
                            if os.path.isfile(abs_path) or os.path.islink(abs_path):
                                os.remove(abs_path)
                            elif os.path.isdir(abs_path):
                                shutil.rmtree(abs_path)
                            self.logger.info(f"删除文件: {abs_path}")
                        except Exception as e:
                            self.logger.error(f"删除文件失败: {abs_path} - {e}")
        # 2. 复制patch内容（除removefile.txt）到目标目录
        for root, dirs, files in os.walk(patch_dir):
            self.logger.info(f"Root Dirs Files: {root} {dirs} {files}")
            for file in files:
                rel_dir = os.path.relpath(root, patch_dir)
                self.logger.info(f"正在处理文件: {file}")
                if file == "removefile.txt":
                    continue
                src_file = os.path.join(root, file)
                
                if rel_dir == ".":
                    dst_file = os.path.join(self.cover_folder_path, file)
                else:
                    dst_file = os.path.join(self.cover_folder_path, rel_dir, file)
                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                self.logger.info(f"源文件;真实目录;完整目录: {src_file} {rel_dir} {dst_file}")
                shutil.copy2(src_file, dst_file)

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
        if self.autostart:
            # autostart模式下，若已是最新则直接启动主程序
            if self.is_latest:
                self.logger.info("已是最新版本，直接启动 March7th Assistant.exe")
                self.start_main_app()
                return
            else:
                self.logger.info("检测到新版本，开始自动更新")
        while True:
            self.download_with_progress()
            if self.extract_file():
                break
        self.terminate_processes()
        self.cover_folder()
        self.cleanup()
        # autostart和auto_mode都要自动启动主程序
        if self.autostart or self.auto_mode:
            self.start_main_app()
        elif not self.auto_mode:
            return

    def start_main_app(self):
        """启动 March7th Assistant.exe 并退出"""
        exe_path = os.path.abspath("./March7th Assistant.exe")
        try:
            if os.path.exists(exe_path):
                # 使用管理员权限启动独立进程
                if sys.platform == "win32":
                    import ctypes
                    params = ""
                    ctypes.windll.shell32.ShellExecuteW(
                        None, "runas", exe_path, params, None, 1
                    )
                else:
                    subprocess.Popen([exe_path], creationflags=subprocess.DETACHED_PROCESS)
            else:
                self.logger.error(f"未找到 {exe_path}")
        except Exception as e:
            self.logger.error(f"启动主程序失败: {e}")
        sleep(10)  # Debug
        sys.exit(0)


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
    max_try = -1
    auto_mode = False
    autostart = False
    # 检查是否以静默模式或autostart模式启动
    if len(sys.argv) == 2:
        if sys.argv[1] == "/q":
            auto_mode = True
            max_try = 5
        elif sys.argv[1] == "autostart":
            autostart = True
            max_try = 5
    if len(sys.argv) == 4:
        download_url = sys.argv[1]
        file_name = sys.argv[2]
        if sys.argv[3] == "/q":
            auto_mode = True
            max_try = 5
        elif sys.argv[3] == "autostart":
            autostart = True
            max_try = 5
    logger = Logger()
    updater = Updater(logger, download_url, file_name, auto_mode, max_try, autostart)
    updater.run()


if __name__ == '__main__':
    check_temp_dir_and_run()

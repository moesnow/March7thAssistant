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
import urllib.request
from urllib.request import urlopen
from urllib.error import URLError
from utils.color import red, green
from utils.logger.logger import Logger


class Updater:
    """应用程序更新器，负责检查、下载、解压和安装最新版本的应用程序。"""

    def __init__(self, logger: Logger, download_url=None, file_name=None):
        self.logger = logger
        self.process_names = ["March7th Assistant.exe", "March7th Launcher.exe", "flet.exe", "gui.exe", "Fhoe-Rail.exe", "chromedriver.exe", "PaddleOCR-json.exe"]
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
        proxies = urllib.request.getproxies()
        while True:
            try:
                self.logger.info("开始下载...")
                if os.path.exists(self.aria2_path):
                    command = [
                        self.aria2_path,
                        "--disable-ipv6=true",
                        "--dir={}".format(os.path.dirname(self.download_file_path)),
                        "--out={}".format(os.path.basename(self.download_file_path)),
                        self.download_url
                    ]

                    if "github.com" in self.download_url:
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
                    response = requests.head(self.download_url, allow_redirects=True)
                    response.raise_for_status()
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
                self.logger.error(f"下载失败: {red('请检查网络连接是否正常，或切换更新源后重试。')}")
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

    def is_file_locked(self, file_path):
        """
        检测单个文件是否被占用
        返回 True 表示被占用
        """
        if not os.path.exists(file_path):
            return False

        try:
            fd = os.open(file_path, os.O_RDWR | os.O_EXCL)
            os.close(fd)
            return False
        except OSError:
            return True

    def is_folder_locked(self, folder_path):
        """
        检测文件夹下是否有任何文件被占用
        返回 True 表示文件夹内有文件被占用
        返回占用的文件列表
        """
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            return False, []

        locked_files = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                full_path = os.path.join(root, file)
                if self.is_file_locked(full_path):
                    locked_files.append(full_path)

        return len(locked_files) > 0, locked_files

    def get_files_to_overwrite(self):
        """
        收集 extract_folder_path 下将被覆盖（复制到 cover_folder_path）的所有文件，返回 (src_path, dest_path) 列表。
        仅包含文件（不包含目录）；目标路径按相对路径映射到 cover_folder_path。
        """
        items = []
        if not os.path.isdir(self.extract_folder_path):
            return items

        for root, dirs, files in os.walk(self.extract_folder_path):
            for fname in files:
                src = os.path.join(root, fname)
                rel = os.path.relpath(src, self.extract_folder_path)
                dest = os.path.join(self.cover_folder_path, rel)
                items.append((src, dest))

        return items

    def check_target_files_locked(self, files_to_overwrite):
        """
        给定 (src, dest) 列表，检查 dest 是否存在且被 is_file_locked 标记为被占用。
        返回被占用的目标路径字符串列表。
        """
        locked = []
        # 排除当前运行程序自身路径（sys.argv[0]）的检测，避免把自身视为被占用
        try:
            self_path = os.path.normcase(os.path.normpath(os.path.abspath(sys.argv[0])))
        except Exception:
            self_path = None

        for src, dest in files_to_overwrite:
            try:
                norm_dest = os.path.normcase(os.path.normpath(os.path.abspath(dest)))
            except Exception:
                norm_dest = None

            # 如果目标路径是当前运行文件，跳过检测
            if self_path and norm_dest and norm_dest == self_path:
                continue

            if os.path.exists(dest) and self.is_file_locked(dest):
                locked.append(str(dest))
        return locked

    def get_locked_display_list(self, locked_paths, limit: int = 10):
        """
        将被占用的路径列表限制显示个数，返回 (display_list, remaining_count)。
        用于日志输出时避免一次性打印过多条目。
        """
        if not locked_paths:
            return [], 0
        display = locked_paths[:limit]
        remaining = max(0, len(locked_paths) - len(display))
        return display, remaining

    def ensure_self_renamed_if_target(self, files_to_overwrite) -> bool:
        """
        检查文件列表中的目标路径是否包含当前运行的可执行文件（sys.argv[0]）。
        如果包含，尝试将当前可执行文件重命名为 <name>.old 以避免被覆盖。
        返回 True 表示要么不涉及自身，要么重命名成功；返回 False 表示尝试失败
        """
        try:
            self_path = os.path.abspath(sys.argv[0])
        except Exception:
            # 无法获取当前路径，跳过重命名逻辑
            return True

        # 标准化路径比较
        norm_self = os.path.normcase(os.path.normpath(self_path))
        targets = [os.path.normcase(os.path.normpath(dest)) for _, dest in files_to_overwrite]

        if norm_self not in targets:
            return True

        # 将 .old 插入到扩展名前：foo.exe -> foo.old.exe
        root, ext = os.path.splitext(self_path)
        backup_path = f"{root}.old{ext}"

        # 如果备份文件已经存在，尝试先删除以便创建新的备份
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except Exception:
                # 无法删除旧的 .old 文件，失败并通知上层
                self.logger.error(f"无法删除旧的备份文件: {backup_path}")
                return False

        try:
            # 尝试重命名自身文件为 .old
            os.replace(self_path, backup_path)
            # 记录备份路径，以便在更新完成后安排删除
            self.self_backup_path = backup_path
            return True
        except Exception as e:
            # 无法重命名，返回 False 以便提示用户手动处理
            self.logger.error(f"重命名自身失败: {e}")
            return False

    def cover_folder(self):
        """覆盖安装最新版本的文件。"""
        self.logger.hr("覆盖", 0)
        while True:
            files_to_overwrite = self.get_files_to_overwrite()
            locked = self.check_target_files_locked(files_to_overwrite)
            if locked:
                self.logger.info(f"以下目标文件被占用，无法覆盖:")
                display, remaining = self.get_locked_display_list(locked, limit=5)
                for f in display:
                    self.logger.info(red(f))
                if remaining > 0:
                    self.logger.info(red(f"...另外 {remaining} 个文件被占用（未显示）"))
                input("请手动关闭相关进程后按回车重新检测...")
                continue

            try:
                self.logger.info("开始覆盖...")

                # 按文件逐个复制，跳过当前运行的自身文件（self），最后再单独处理它。
                try:
                    self_path = os.path.normcase(os.path.normpath(os.path.abspath(sys.argv[0])))
                except Exception:
                    self_path = None

                others = []
                self_items = []
                for src, dest in files_to_overwrite:
                    try:
                        norm_dest = os.path.normcase(os.path.normpath(os.path.abspath(dest)))
                    except Exception:
                        norm_dest = None

                    if self_path and norm_dest and norm_dest == self_path:
                        self_items.append((src, dest))
                    else:
                        others.append((src, dest))

                # 复制除自身外的其他文件
                for src, dest in others:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    shutil.copy2(src, dest)

                # 如果覆盖目标包含正在运行的程序自身，尝试重命名自身以避免被覆盖
                if not self.ensure_self_renamed_if_target(files_to_overwrite):
                    # 如果无法重命名自身则提示用户并继续重试流程
                    input("无法为当前执行文件创建备份（.old），请手动关闭相关进程或释放文件后按回车重试...")
                    continue

                # 复制自身（如果存在于更新包内），此时 ensure_self_renamed_if_target 已经将正在运行的文件改名为 .old
                for src, dest in self_items:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    shutil.copy2(src, dest)

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
        while True:
            file = self.is_file_locked(self.download_file_path)
            if file:
                self.logger.info(f"文件被占用: {red(self.download_file_path)}")
                input("请手动关闭相关进程后按回车重新检测...")
                continue

            locked, files = self.is_folder_locked(self.extract_folder_path)
            if locked:
                self.logger.info(f"文件夹被占用: {red(self.extract_folder_path)}")
                display, remaining = self.get_locked_display_list(files, limit=5)
                for f in display:
                    self.logger.info(f"被占用文件: {red(f)}")
                if remaining > 0:
                    self.logger.info(red(f"...另外 {remaining} 个文件被占用（未显示）"))
                input("请手动关闭相关进程后按回车重新检测...")
                continue

            try:
                os.remove(self.download_file_path)
                self.logger.info(f"清理完成: {green(self.download_file_path)}")
                shutil.rmtree(self.extract_folder_path)
                self.logger.info(f"清理完成: {green(self.extract_folder_path)}")
                break
            except Exception as e:
                self.logger.error(f"清理失败: {e}")
                input("按回车键重试. . .")

        self.logger.hr("完成", 2)

    def run(self):
        """运行更新流程。"""
        while True:
            self.download_with_progress()
            if self.extract_file():
                break
        self.terminate_processes()
        self.cover_folder()
        self.cleanup()
        # input("按回车键退出并打开软件")
        launcher_path = os.path.abspath("./March7th Launcher.exe")
        if os.system(f'cmd /c start "" "{launcher_path}"'):
            subprocess.Popen(launcher_path)

        # 循环尝试删除直到成功为止，然后删除脚本自身
        try:
            backup_to_delete = getattr(self, 'self_backup_path', None)
            if backup_to_delete and os.path.exists(backup_to_delete):
                # 创建临时 .bat 文件
                bat_path = os.path.join(self.temp_path, f"cleanup_delete_{int(time.time())}.bat")
                bat_content = (
                    f"@echo off\n"
                    f":loop\n"
                    f"del /F /Q \"{backup_to_delete}\" >nul 2>&1\n"
                    f"if exist \"{backup_to_delete}\" (\n"
                    f"  timeout /T 1 /NOBREAK >nul\n"
                    f"  goto loop\n"
                    f")\n"
                    f"del /F /Q \"%~f0\" >nul 2>&1\n"
                )
                with open(bat_path, 'w', encoding='utf-8') as bf:
                    bf.write(bat_content)

                try:
                    subprocess.Popen(f'cmd /c "{bat_path}"', shell=True)
                except Exception as e:
                    self.logger.warning(f"无法执行 bat 脚本: {e}")
                    # 删除临时 bat 文件
                    try:
                        if os.path.exists(bat_path):
                            os.remove(bat_path)
                    except Exception as ex:
                        self.logger.error(f"删除临时 bat 脚本失败: {ex}")
                    # 将 backup_to_delete 移动到 temp_path 下
                    try:
                        dest_path = os.path.join(self.temp_path, os.path.basename(backup_to_delete))
                        shutil.move(backup_to_delete, dest_path)
                        # self.logger.info(f"已将 {backup_to_delete} 移动到 {dest_path}")
                    except Exception as ex:
                        self.logger.error(f"移动文件失败: {ex}")

        except Exception as e:
            self.logger.error(f"删除 .old 备份时出错: {e}")


def check_temp_dir_and_run():
    """检查临时目录并运行更新程序。"""
    if not getattr(sys, 'frozen', False):
        print("更新程序只支持打包成exe后运行")
        sys.exit(1)

    temp_path = os.path.abspath("./temp")
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path)
    # file_path = sys.argv[0]
    # destination_path = os.path.join(temp_path, os.path.basename(file_path))

    # if file_path != destination_path:
    #     if os.path.exists(temp_path):
    #         shutil.rmtree(temp_path)
    #     if os.path.exists("./Update.exe"):
    #         os.remove("./Update.exe")
    #     os.makedirs(temp_path, exist_ok=True)
    #     shutil.copy(file_path, destination_path)
    #     args = [destination_path] + sys.argv[1:]
    #     subprocess.Popen(args, creationflags=subprocess.DETACHED_PROCESS)
    #     sys.exit(0)

    download_url = sys.argv[1] if len(sys.argv) == 3 else None
    file_name = sys.argv[2] if len(sys.argv) == 3 else None
    logger = Logger()
    updater = Updater(logger, download_url, file_name)
    updater.run()


if __name__ == '__main__':
    check_temp_dir_and_run()

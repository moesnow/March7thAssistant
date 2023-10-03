from packaging.version import parse
import concurrent.futures
import subprocess
import tempfile
import shutil
import psutil
import json
import sys
import time
import requests
import os

from tqdm import tqdm
import urllib.request
from urllib.parse import urlparse


class Update:
    def __init__(self, download_url=None):
        self.process_name = ("March7th Assistant.exe", "March7th Launcher.exe")
        self.api_urls = [
            "https://api.github.com/repos/moesnow/March7thAssistant/releases/latest",
            "https://cdn.jsdelivr.net/gh/moesnow/March7thAssistant@release/latest.json",
            "https://ghproxy.com/https://raw.githubusercontent.com/moesnow/March7thAssistant/release/latest.json",
            "https://github.moeyy.xyz/https://raw.githubusercontent.com/moesnow/March7thAssistant/release/latest.json",
        ]

        self.temp_path = tempfile.gettempdir()
        if download_url is None:
            self.__get_download_url()
        else:
            self.download_url = download_url
            self.extract_folder_path = os.path.join(self.temp_path, os.path.basename(self.download_url).rsplit(".", 1)[0])
        self.download_file_path = os.path.join(self.temp_path, os.path.basename(self.download_url))
        self.cover_folder_path = os.path.abspath("./")

    def __find_fastest_mirror(self, mirror_urls, timeout=5):
        def check_mirror(mirror_url):
            try:
                start_time = time.time()
                response = requests.head(mirror_url, timeout=timeout, allow_redirects=True)
                end_time = time.time()
                if response.status_code == 200:
                    response_time = end_time - start_time
                    # print(f"镜像: {urlparse(mirror_url).netloc} 响应时间: {response_time}")
                    return mirror_url
            except Exception:
                pass
            return None

        # print("开始测速")
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_mirror = {executor.submit(check_mirror, mirror_url): mirror_url for mirror_url in mirror_urls}

            for future in concurrent.futures.as_completed(future_to_mirror):
                result = future.result()
                if result:
                    executor.shutdown()
                    # print(f"测速完成，最快的镜像为: {urlparse(result).netloc}")
                    return result

        # print(f"测速失败，使用默认镜像：{urlparse(mirror_urls[0]).netloc}")
        return mirror_urls[0]

    def __get_download_url(self):
        print("开始检测更新")
        while True:
            try:
                with urllib.request.urlopen(self.__find_fastest_mirror(self.api_urls), timeout=10) as response:
                    if response.getcode() == 200:
                        data = json.loads(response.read().decode('utf-8'))
                        break
                    print("检测更新失败")
            except urllib.error.URLError as e:
                print(f"检测更新失败: {e}")
            input("按任意键重试. . .")

        # 获取最新版本
        version = data["tag_name"]
        for asset in data["assets"]:
            if "full" in asset["browser_download_url"]:
                continue
            else:
                self.download_url = asset["browser_download_url"]
                self.extract_folder_path = os.path.join(self.temp_path, os.path.basename(self.download_url).rsplit(".", 1)[0])
                break

        # 比较本地版本
        try:
            with open("./assets/config/version.txt", 'r', encoding='utf-8') as file:
                current_version = file.read()
            if parse(version.lstrip('v')) > parse(current_version.lstrip('v')):
                print(f"发现新版本：{current_version} ——> {version}")
            else:
                print(f"当前已是最新版本: {current_version}")
        except Exception:
            print(f"本地版本获取失败")
            print(f"最新版本: {version}")

        # 设置镜像
        api_endpoints = [
            self.download_url,
            f"https://ghproxy.com/{self.download_url}",
            f"https://github.moeyy.xyz/{self.download_url}",
        ]
        self.download_url = self.__find_fastest_mirror(api_endpoints)

        print(f"下载地址：{self.download_url}")
        input("按任意键开始更新")

    def __download_with_progress(self, download_url, save_path):
        # 获取文件大小
        response = urllib.request.urlopen(download_url)
        file_size = int(response.info().get('Content-Length', -1))

        # 使用 tqdm 创建进度条
        with tqdm(total=file_size, unit='B', unit_scale=True, unit_divisor=1024) as pbar:
            def update_bar(block_count, block_size, total_size):
                if pbar.total != total_size:
                    pbar.total = total_size
                downloaded = block_count * block_size
                pbar.update(downloaded - pbar.n)

            urllib.request.urlretrieve(download_url, save_path, reporthook=update_bar)

    def __terminate_process(self):
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            for name in self.process_name:
                if name in proc.info['name']:
                    try:
                        process = psutil.Process(proc.info['pid'])
                        process.terminate()
                        process.wait(timeout=10)
                    except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied):
                        pass

    def __download_file(self):
        print("开始下载...")
        while True:
            try:
                self.__download_with_progress(self.download_url, self.download_file_path)
                print(f"下载完成：{self.download_file_path}")
                break
            except Exception as e:
                print(f"下载失败：{e}")
                input("按任意键重试. . .")

    def __extract_file(self):
        print("开始解压...")
        while True:
            try:
                shutil.unpack_archive(self.download_file_path, self.temp_path)
                print(f"解压完成：{self.extract_folder_path}")
                break
            except Exception as e:
                print(f"解压失败：{e}")
                input("按任意键重试. . .")

    def __cover_folder(self):
        print("开始覆盖...")
        while True:
            try:
                shutil.copytree(self.extract_folder_path, self.cover_folder_path, dirs_exist_ok=True)
                print(f"覆盖完成：{self.cover_folder_path}")
                break
            except Exception as e:
                print(f"覆盖失败：{e}")
                input("按任意键重试. . .")

    def __delete_files(self):
        print("开始清理...")
        try:
            os.remove(self.download_file_path)
            print(f"清理完成：{self.download_file_path}")
        except Exception as e:
            print(f"清理失败：{e}")
        try:
            shutil.rmtree(self.extract_folder_path)
            print(f"清理完成：{self.extract_folder_path}")
        except Exception as e:
            print(f"清理失败：{e}")

    def run(self):
        print("开始终止进程...")
        self.__terminate_process()
        print("终止进程完成")

        self.__download_file()

        self.__extract_file()

        self.__cover_folder()

        self.__delete_files()

        input("按任意键关闭窗口")


def check_temp_dir():
    if not getattr(sys, 'frozen', False):
        print("更新程序只支持打包成exe后运行")
        sys.exit(1)

    temp_path = tempfile.gettempdir()
    file_path = os.path.abspath(sys.argv[0])
    file_name = os.path.basename(file_path)
    destination_path = os.path.join(temp_path, file_name)

    if not file_path == destination_path:
        while True:
            try:
                shutil.copy(file_path, os.path.join(temp_path, file_name))
                break
            except Exception as e:
                print(f"复制更新程序到临时目录失败：{e}")
                input("按任意键重试. . .")
        subprocess.run(["start", os.path.join(temp_path, file_name)] + sys.argv[1:], shell=True)
        sys.exit(0)


if __name__ == '__main__':
    check_temp_dir()

    if len(sys.argv) == 2:
        update = Update(sys.argv[1])
    else:
        update = Update()

    update.run()

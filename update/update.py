import subprocess
import tempfile
import shutil
import psutil
import json
import sys
import yaml
import os

from tqdm import tqdm
import urllib.request


class Update:
    def __init__(self, download_url=None):
        self.process_name = "March7th Assistant.exe"
        self.api_url = "https://api.github.com/repos/moesnow/March7thAssistant/releases/latest"
        self.api_mirror_url = "https://api.kkgithub.com/repos/moesnow/March7thAssistant/releases/latest"

        if download_url is None:
            self.__get_download_url()
        else:
            self.download_url = download_url
            self.update_directory = os.path.basename(self.download_url).rsplit(".", 1)[0]

        self.save_path = "./March7thAssistant.zip"

    def __get_download_url(self):
        print("开始检测更新")
        try:
            with urllib.request.urlopen(self.api_url, timeout=10) as response:
                if response.getcode() != 200:
                    print("检测更新失败")
                    input("按任意键关闭窗口")
                    sys.exit(1)
                data = json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError as e:
            print(f"检测更新失败: {e}")
            print("开始尝试备用镜像")
            try:
                with urllib.request.urlopen(self.api_mirror_url, timeout=10) as response:
                    if response.getcode() != 200:
                        print("检测更新失败")
                        input("按任意键关闭窗口")
                        sys.exit(1)
                    data = json.loads(response.read().decode('utf-8'))
            except urllib.error.URLError as e:
                print(f"检测更新失败: {e}")
                print(f"GitHub偶尔无法访问是很正常的情况，拜托请不要反馈此类问题了")
                input("按任意键关闭窗口")
                sys.exit(1)

        # 获取最新版本
        version = data["tag_name"]
        for asset in data["assets"]:
            if "full" in asset["browser_download_url"]:
                continue
            else:
                self.download_url = asset["browser_download_url"]
                self.update_directory = os.path.basename(self.download_url).rsplit(".", 1)[0]
                break

        # 比较本地版本
        try:
            with open("./assets/config/version.txt", 'r', encoding='utf-8') as file:
                current_version = file.read()
            if version > current_version:
                print(f"发现新版本：{current_version} ——> {version}")
            else:
                print(f"当前已是最新版本: {current_version}")
        except Exception:
            print(f"本地版本获取失败")
            print(f"最新版本: {version}")

        # 设置镜像
        try:
            with open("./config.yaml", 'r', encoding='utf-8') as file:
                config = yaml.load(file, Loader=yaml.FullLoader)
                self.download_url = config["github_mirror"] + self.download_url
        except (FileNotFoundError, KeyError):
            pass

        print(f"下载地址：{self.download_url}")
        input("按任意键开始更新")

    def __download_with_progress(self):
        # 获取文件大小
        response = urllib.request.urlopen(self.download_url)
        file_size = int(response.info().get('Content-Length', -1))

        # 使用 tqdm 创建进度条
        with tqdm(total=file_size, unit='B', unit_scale=True, unit_divisor=1024) as pbar:
            def update_bar(block_count, block_size, total_size):
                if pbar.total != total_size:
                    pbar.total = total_size
                downloaded = block_count * block_size
                pbar.update(downloaded - pbar.n)

            urllib.request.urlretrieve(self.download_url, self.save_path, reporthook=update_bar)

    def __terminate_process(self):
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            if self.process_name in proc.info['name']:
                try:
                    process = psutil.Process(proc.info['pid'])
                    process.terminate()
                    process.wait(timeout=10)
                except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied):
                    pass

    def __copy_files(self):
        for root, dirs, files in os.walk(self.update_directory):
            for file in files:
                src_path = os.path.join(root, file)
                dest_path = os.path.join('.', os.path.relpath(src_path, self.update_directory))

                # 检查目标目录是否存在，如果不存在则创建
                dest_dir = os.path.dirname(dest_path)
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)

                shutil.copy2(src_path, dest_path)

    def __delete_files(self):
        shutil.rmtree(self.update_directory)
        os.remove(self.save_path)

    def run(self):
        try:
            print("下载中...")
            self.__download_with_progress()
            print("下载完成")

            print("开始解压...")
            shutil.unpack_archive(self.save_path, './')
            print("解压完成")

            # 关闭图形界面
            self.__terminate_process()

            print("开始更新...")
            self.__copy_files()
            print("更新完成")

            print("开始清理...")
            self.__delete_files()
            print("清理完成")

            input("按任意键关闭窗口")

        except KeyboardInterrupt:
            print("手动强制停止")
            input("按任意键关闭窗口")
        except Exception as e:
            print(f"更新出错: {e}")
            print("请尝试重试或手动更新")
            input("按任意键关闭窗口")


def check_temp_dir():
    temp_path = tempfile.gettempdir()
    file_path = os.path.abspath(sys.argv[0])
    file_name = os.path.basename(file_path)
    destination_path = os.path.join(temp_path, file_name)

    if not file_path == destination_path:
        shutil.copy2(file_path, os.path.join(temp_path, file_name))
        subprocess.run(["start", os.path.join(temp_path, file_name)] + sys.argv[1:], shell=True)
        sys.exit(0)


if __name__ == '__main__':
    check_temp_dir()

    if len(sys.argv) == 2:
        update = Update(sys.argv[1])
    else:
        update = Update()

    update.run()

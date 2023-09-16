import subprocess
import tempfile
import requests
import shutil
import json
import sys
import os

from tqdm import tqdm
import urllib.request


try:
    def download_with_progress(download_url, save_path):
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

    temp_path = tempfile.gettempdir()
    file_path = os.path.abspath(sys.argv[0])
    file_name = os.path.basename(file_path)
    destination_path = os.path.join(temp_path, file_name)

    # 移动程序到临时目录，避免占用导致更新失败
    if not file_path == destination_path:
        shutil.copy2(file_path, os.path.join(temp_path, file_name))
        subprocess.run(["start", os.path.join(temp_path, file_name)] + sys.argv[1:], shell=True)
        sys.exit(0)

    # 获取下载地址和更新目录作为命令行参数
    if len(sys.argv) != 3:
        url = "https://api.github.com/repos/moesnow/March7thAssistant/releases/latest"
        print("开始检测更新")
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            print("检测更新失败")
            input("按任意键关闭窗口")
            sys.exit(1)

        data = json.loads(res.text)
        version = data["tag_name"]

        try:
            with open("./assets/config/version.txt", 'r', encoding='utf-8') as file:
                current_version = file.read()
            if version > current_version:
                print(f"发现新版本：{current_version} ——> {version}")
            else:
                print(f"当前是最新版本: {current_version}")
        except Exception:
            print(f"本地版本获取失败")
            print(f"最新版本: {version}")
        input("按任意键开始更新")

        for asset in data["assets"]:
            if "full" in asset["browser_download_url"]:
                continue
            else:
                download_url = asset["browser_download_url"]
                update_directory = asset["name"].rsplit(".", 1)[0]
                break
        download_url = "https://github.moeyy.cn/" + download_url
    else:
        input("关闭 March7thAssistant 后按任意键继续")

        download_url = sys.argv[1]
        update_directory = sys.argv[2]

    print(f"下载地址：{download_url}")
    # 下载文件
    print("下载中...")
    download_with_progress(download_url, './March7thAssistant.zip')
    # urllib.request.urlretrieve(download_url, './March7thAssistant.zip')
    print("下载完成")

    # 解压文件
    print("开始解压...")
    shutil.unpack_archive('./March7thAssistant.zip', './', 'zip')
    print("解压完成")

    # 开始更新
    print("开始更新...")
    for root, dirs, files in os.walk(update_directory):
        for file in files:
            src_path = os.path.join(root, file)
            dest_path = os.path.join('.', os.path.relpath(src_path, update_directory))

            # 检查目标目录是否存在，如果不存在则创建
            dest_dir = os.path.dirname(dest_path)
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)

            shutil.copy2(src_path, dest_path)
    print("更新完成")

    # 删除文件和临时压缩文件
    shutil.rmtree(update_directory)
    os.remove('./March7thAssistant.zip')

    input("按任意键关闭窗口")
except KeyboardInterrupt:
    print("手动强制停止")
    input("按任意键关闭窗口")
except Exception as e:
    print(f"更新出错: {e}")
    print("请尝试重试或手动更新")
    input("按任意键关闭窗口")

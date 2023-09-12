import urllib.request
import requests
import shutil
import json
import sys
import os

try:
    # 获取下载地址和更新目录作为命令行参数
    if len(sys.argv) != 3:
        url = "https://api.github.com/repos/moesnow/March7thAssistant/releases/latest"
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            print("检测更新失败")
            input("按任意键关闭窗口")
            sys.exit(1)

        data = json.loads(res.text)
        version = data["tag_name"]

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

    # 下载文件
    print("下载中...")
    urllib.request.urlretrieve(download_url, './March7thAssistant.zip')
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

except Exception as e:
    print(f"更新出错: {e}")
    input("按任意键关闭窗口")

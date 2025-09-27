from tqdm import tqdm
import urllib.request
import subprocess
import os


def download_with_progress(download_url, save_path):

    aria2_path = os.path.abspath("./assets/binary/aria2c.exe")
    proxies = urllib.request.getproxies()

    if os.path.exists(aria2_path):
        command = [
            aria2_path,
            "--disable-ipv6=true",
            "--dir={}".format(os.path.dirname(save_path)),
            "--out={}".format(os.path.basename(save_path)),
            download_url
        ]
        if "github.com" in download_url:
            command.insert(2, "--max-connection-per-server=16")
            if os.path.exists(save_path):
                command.insert(2, "--continue=true")
        for scheme, proxy in proxies.items():
            if scheme in ("http", "https", "ftp"):
                command.append(f"--{scheme}-proxy={proxy}")
        process = subprocess.Popen(command)
        process.wait()
        if process.returncode != 0:
            raise Exception
    else:
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

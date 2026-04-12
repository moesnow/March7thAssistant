from tqdm import tqdm
import urllib.request
import subprocess
import requests
import os

from module.update.download_proxy import get_update_download_aria2_args, get_update_download_requests_proxies


def download_with_progress(download_url, save_path, use_update_proxy=False):

    aria2_path = os.path.abspath("./assets/binary/aria2c.exe")
    proxies = urllib.request.getproxies() if not use_update_proxy else {}
    aria2_proxy_args = get_update_download_aria2_args() if use_update_proxy else []
    request_proxies = get_update_download_requests_proxies() if use_update_proxy else None

    if os.path.exists(aria2_path):
        command = [
            aria2_path,
            "--disable-ipv6=true",
            "--dir={}".format(os.path.dirname(save_path)),
            "--out={}".format(os.path.basename(save_path)),
        ]
        if "github.com" in download_url:
            command.insert(2, "--max-connection-per-server=16")
            if os.path.exists(save_path):
                command.insert(2, "--continue=true")
        if use_update_proxy:
            command.extend(aria2_proxy_args)
        else:
            for scheme, proxy in proxies.items():
                if scheme in ("http", "https", "ftp"):
                    command.append(f"--{scheme}-proxy={proxy}")
        command.append(download_url)
        subprocess.run(command, check=True)
    else:
        if use_update_proxy:
            with requests.get(download_url, stream=True, timeout=(10, 30), proxies=request_proxies) as response:
                response.raise_for_status()
                file_size = int(response.headers.get("Content-Length", 0)) or None

                with tqdm(total=file_size, unit='B', unit_scale=True, unit_divisor=1024) as pbar:
                    with open(save_path, "wb") as file:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                file.write(chunk)
                                pbar.update(len(chunk))
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

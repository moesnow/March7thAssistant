from tqdm import tqdm
import urllib.request
import subprocess
import os


def download_with_progress(download_url, save_path):


    # 检查 gh-proxy 和 github 原始链接的可用性
    test_urls = [
        "https://gh-proxy.com/https://github.com/github/github-mcp-server/raw/refs/heads/main/README.md",
        "https://github.com/github/github-mcp-server/raw/refs/heads/main/README.md"
    ]
    proxy_available = False
    origin_available = False

    try:
        with urllib.request.urlopen(test_urls[0], timeout=5) as resp:
            if resp.status == 200:
                proxy_available = True
    except Exception:
        pass

    try:
        with urllib.request.urlopen(test_urls[1], timeout=5) as resp:
            if resp.status == 200:
                origin_available = True
    except Exception:
        pass

    # 如果都可用，优先用 gh-proxy
    if proxy_available and origin_available:
        if download_url.startswith("https://github.com/"):
            download_url = "https://gh-proxy.com/" + download_url

    aria2_path = os.path.abspath("./assets/binary/aria2c.exe")

    if os.path.exists(aria2_path):
        command = [aria2_path, f"--dir={os.path.dirname(save_path)}", f"--out={os.path.basename(save_path)}", f"{download_url}"]
        if "github.com" in download_url:
            command.insert(2, "--max-connection-per-server=16")
        if os.path.exists(save_path):
            command.insert(2, "--continue=true")
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
from tqdm import tqdm
import urllib.request
import subprocess
import os


def download_with_progress(download_url, save_path):

    aria2_path = os.path.abspath("./assets/aria2/aria2c.exe")

    if os.path.exists(aria2_path):
        if os.path.exists(save_path):
            command = [aria2_path, "--max-connection-per-server=16", "--continue=true",
                       f"--dir={os.path.dirname(save_path)}", f"--out={os.path.basename(save_path)}", f"{download_url}"]
        else:
            command = [aria2_path, "--max-connection-per-server=16",
                       f"--dir={os.path.dirname(save_path)}", f"--out={os.path.basename(save_path)}", f"{download_url}"]
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

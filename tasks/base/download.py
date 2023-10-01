

def download_with_progress(download_url, save_path):
    from tqdm import tqdm
    import urllib.request
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

from managers.config_manager import config
from managers.translate_manager import _
from urllib.parse import urlparse
import requests
import time


class FastestMirror:
    @staticmethod
    def get_github_mirror(download_url, timeout=10):
        mirror_urls = [
            download_url,
            f"https://github.moeyy.xyz/{download_url}",
        ]
        return FastestMirror.find_fastest_mirror(mirror_urls, timeout)

    @staticmethod
    def get_github_api_mirror(user, repo, file, timeout=5):
        mirror_urls = [
            f"https://api.github.com/repos/{user}/{repo}/releases/latest",
            f"https://cdn.jsdelivr.net/gh/moesnow/March7thAssistant@release/{file}",
            f"https://github.moeyy.xyz/https://raw.githubusercontent.com/moesnow/March7thAssistant/release/{file}",
        ]
        return FastestMirror.find_fastest_mirror(mirror_urls, timeout)

    @staticmethod
    def get_pypi_mirror(timeout=5):
        return FastestMirror.find_fastest_mirror(config.pypi_mirror_urls, timeout)

    @staticmethod
    def find_fastest_mirror(mirror_urls, timeout=5):
        from managers.logger_manager import logger
        import concurrent.futures

        def check_mirror(mirror_url):
            try:
                start_time = time.time()
                response = requests.head(mirror_url, timeout=timeout, allow_redirects=True)
                end_time = time.time()
                if response.status_code == 200:
                    response_time = end_time - start_time
                    logger.debug(_("镜像: {mirror} 响应时间: {time}").format(mirror=urlparse(mirror_url).netloc, time=response_time))
                    return mirror_url
            except Exception:
                pass
            return None

        logger.info(_("开始测速"))
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_mirror = {executor.submit(check_mirror, mirror_url): mirror_url for mirror_url in mirror_urls}

            for future in concurrent.futures.as_completed(future_to_mirror):
                result = future.result()
                if result:
                    executor.shutdown()
                    logger.info(_("最快的镜像为: {mirror}").format(mirror=urlparse(result).netloc))
                    return result

        logger.warning(_("测速失败，使用默认镜像：{mirror}").format(mirror=urlparse(mirror_urls[0]).netloc))
        return mirror_urls[0]

import re
import urllib.request

_PROXY_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def normalize_proxy_url(proxy: str | None) -> str | None:
    """规范化代理地址，缺少协议时默认按 http 处理。"""
    if proxy is None:
        return None

    proxy = str(proxy).strip()
    if not proxy:
        return None

    if not _PROXY_SCHEME_RE.match(proxy):
        proxy = f"http://{proxy}"

    return proxy


def get_manual_update_download_proxy() -> str | None:
    """获取手动配置的更新下载代理。"""
    try:
        from module.config import cfg
        return normalize_proxy_url(getattr(cfg, "update_download_proxy", None))
    except FileNotFoundError:
        return None


def get_system_download_proxies() -> dict[str, str]:
    """获取并规范化系统代理配置。"""
    raw_proxies = urllib.request.getproxies() or {}
    proxies: dict[str, str] = {}

    all_proxy = normalize_proxy_url(raw_proxies.get("all"))
    if all_proxy is not None:
        return {"http": all_proxy, "https": all_proxy, "ftp": all_proxy}

    for scheme in ("http", "https", "ftp"):
        proxy = normalize_proxy_url(raw_proxies.get(scheme))
        if proxy is not None:
            proxies[scheme] = proxy

    return proxies


def get_update_download_requests_proxies() -> dict[str, str] | None:
    """获取 requests 使用的更新下载代理，手动配置优先于系统代理。"""
    manual_proxy = get_manual_update_download_proxy()
    if manual_proxy is not None:
        return {"http": manual_proxy, "https": manual_proxy}

    proxies = get_system_download_proxies()
    requests_proxies = {scheme: proxies[scheme] for scheme in ("http", "https") if scheme in proxies}

    if "http" not in requests_proxies and "https" in requests_proxies:
        requests_proxies["http"] = requests_proxies["https"]
    if "https" not in requests_proxies and "http" in requests_proxies:
        requests_proxies["https"] = requests_proxies["http"]

    return requests_proxies or None


def get_update_download_aria2_args() -> list[str]:
    """获取 aria2 使用的更新下载代理参数，手动配置优先于系统代理。"""
    manual_proxy = get_manual_update_download_proxy()
    if manual_proxy is not None:
        return [f"--all-proxy={manual_proxy}"]

    proxies = get_system_download_proxies()
    if not proxies:
        return []

    unique_proxies = set(proxies.values())
    if len(unique_proxies) == 1:
        return [f"--all-proxy={next(iter(unique_proxies))}"]

    args = []
    for scheme in ("http", "https", "ftp"):
        proxy = proxies.get(scheme)
        if proxy is not None:
            args.append(f"--{scheme}-proxy={proxy}")

    return args

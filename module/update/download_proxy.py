import re
import urllib.request
from urllib.parse import urlsplit, urlunsplit

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


def redact_proxy_url(proxy: str | None) -> str | None:
    """脱敏代理地址中的认证信息，避免日志输出凭据。"""
    if not proxy:
        return None

    parts = urlsplit(proxy)
    if parts.username is None:
        return proxy

    host = parts.hostname or ""
    if host and ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parts.port is not None:
        host = f"{host}:{parts.port}"

    userinfo = "***:***" if parts.password is not None else "***"
    netloc = f"{userinfo}@{host}" if host else userinfo
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def format_proxy_mapping(proxies: dict[str, str] | None) -> str | None:
    """将代理映射格式化为适合日志输出的文本。"""
    if not proxies:
        return None

    return ", ".join(
        f"{scheme}={redact_proxy_url(proxy) or proxy}"
        for scheme, proxy in sorted(proxies.items())
    )


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


def get_update_requests_proxy_description() -> str | None:
    """获取 requests 更新流量使用的代理描述文本。"""
    manual_proxy = get_manual_update_download_proxy()
    if manual_proxy is not None:
        return f"手动代理: http={redact_proxy_url(manual_proxy)}, https={redact_proxy_url(manual_proxy)}"

    requests_proxies = get_update_download_requests_proxies()
    if not requests_proxies:
        return None

    mapping = format_proxy_mapping(requests_proxies)
    return f"系统代理: {mapping}" if mapping else None


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


def get_update_aria2_proxy_description() -> str | None:
    """获取 aria2 更新下载使用的代理描述文本。"""
    manual_proxy = get_manual_update_download_proxy()
    if manual_proxy is not None:
        masked = redact_proxy_url(manual_proxy)
        return f"手动代理: all={masked}"

    proxies = get_system_download_proxies()
    if not proxies:
        return None

    unique_proxies = {proxy for proxy in proxies.values() if proxy}
    if len(unique_proxies) == 1:
        only_proxy = redact_proxy_url(next(iter(unique_proxies)))
        return f"系统代理: all={only_proxy}"

    mapping = format_proxy_mapping(proxies)
    return f"系统代理: {mapping}" if mapping else None

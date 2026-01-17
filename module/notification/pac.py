import sys
if sys.platform == 'win32':
    import winreg

PAC_REG_KEY = "Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings"


def query_system_pac_settings() -> str | None:
    r"""
    Query system pac settings from registry.
    :return: pac url or None
    """
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, PAC_REG_KEY)
        value, _ = winreg.QueryValueEx(key, "AutoConfigURL")
        winreg.CloseKey(key)
        if value:
            return value
        else:
            return None
    except FileNotFoundError:
        return None


def macth_pac_settings(url: str, pac_url: str):
    r"""
    Match pac settings from pac url.
    :param url: url
    :param pac_url: pac url
    :return: proxy or None
    """
    import pypac
    pac = pypac.get_pac(url=pac_url)
    if pac is None:
        pac_result = None
    else:
        pac_result = pac.find_proxy_for_url(url=url, host="0.0.0.0")
    if isinstance(pac_result, str):
        pac_result = pac_result.split(";")
        pac_result = map(lambda x: x.strip(), pac_result)
        pac_result = filter(lambda x: x, pac_result)
        pac_result = list(pac_result)
        if len(pac_result) > 0:
            pac_result = pac_result[0]
            if pac_result == "DIRECT":
                return None
            if pac_result.startswith("PROXY"):
                pac_result = pac_result.split(" ")
                if len(pac_result) == 2:
                    pac_result = pac_result[1]
                    pac_result = pac_result.split(":")
                    if len(pac_result) == 2:
                        return f"{pac_result[0]}:{pac_result[1]}"


def match_proxy(proxies_param: str | None, api_url: str) -> dict | None:
    r"""
    Match proxy from system pac settings or proxies param
    :param proxies_param: proxies_param
    :param url: url
    :return: proxies
    """
    if proxies_param is not None:
        return {"http": proxies_param, "https": proxies_param}
    pac_url = query_system_pac_settings()
    if pac_url is not None:
        proxy = macth_pac_settings(api_url, pac_url)
        if proxy is not None:
            return {"http": proxy, "https": proxy}
    return None


def match_proxy_url(proxy: str | None, api_url: str) -> dict | None:
    r"""
    Match proxy from system pac settings or proxies param
    :param proxies_param: proxies_param
    :param url: url
    :return: proxies
    """
    if proxy is not None:
        return proxy
    pac_url = query_system_pac_settings()
    if pac_url is not None:
        proxy = macth_pac_settings(api_url, pac_url)
        if proxy is not None:
            proxy
    return None


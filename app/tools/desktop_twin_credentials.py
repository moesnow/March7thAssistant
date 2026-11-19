"""为本机子会话使用用户主动创建的小助手专用 Windows 通用凭据。"""

import pywintypes
import win32cred

from module.localization import tr


CREDENTIAL_TARGET = "March7thAssistant/DesktopTwin/localhost"


def apply_saved_credential(client):
    if client.Server.casefold() != "localhost":
        raise ValueError(tr("分身密码仅用于本机连接"))
    try:
        entry = win32cred.CredRead(CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC, 0)
    except pywintypes.error as exc:
        # 缺少条目、当前登录会话无凭据库或不允许读取时，沿用系统交互登录。
        if exc.winerror in (5, 1168, 1312):
            return
        raise RuntimeError(tr("无法读取分身专用凭据，请检查 Windows 凭据管理器")) from None

    account = entry["UserName"] or ""
    domain, separator, username = account.rpartition("\\")
    try:
        password = entry["CredentialBlob"].decode("utf-16-le")
    except (AttributeError, UnicodeError):
        password = ""
    if not username or (separator and not domain) or not password or "\0" in password:
        raise ValueError(tr("分身凭据格式有误，请在 Windows 凭据管理器中编辑或删除该条目"))
    try:
        client.Domain = domain
        client.UserName = username
        client.AdvancedSettings8.ClearTextPassword = password
    except Exception:
        # 底层异常可能包含调用参数。只将固定错误信息交给上层日志。
        raise RuntimeError(tr("无法向本机分身提供已保存的凭据")) from None

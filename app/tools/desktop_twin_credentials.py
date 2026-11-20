"""管理用户为本机分身保存的 Windows 通用凭据。"""

import ctypes
from ctypes import wintypes

import pywintypes
import win32api
import win32con
import win32cred
from PySide6.QtCore import QLockFile, QStandardPaths

from module.localization import tr


CREDENTIAL_TARGET = "March7thAssistant/DesktopTwin/localhost"
_EDIT_LOCK_PATH = (QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation)
                   + "/March7thAssistant-DesktopTwin-credential.lock")


def saved_account():
    """None 表示没有条目；即使旧条目的用户名已损坏，也允许删除。"""
    try:
        return win32cred.CredRead(CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC, 0)["UserName"] or ""
    except pywintypes.error as exc:
        if exc.winerror == 1168:
            return None
        raise RuntimeError(tr("无法读取分身密码，请检查 Windows 凭据服务。")) from None


def current_account():
    try:
        sam = win32api.GetUserNameEx(win32con.NameSamCompatible)
        domain, _, name = sam.partition("\\")
        if domain.casefold() == win32api.GetComputerName().casefold():
            return _linked_microsoft_account(name) or sam
        return sam
    except pywintypes.error:
        return ""


def _linked_microsoft_account(name):
    # 已关联 Microsoft 账户的本地用户有两个名称：SAM 短名和登录用的邮箱。
    # pywin32 的 NetUserGetInfo 包装器不支持 USER_INFO_24。
    class UserInfo24(ctypes.Structure):
        _fields_ = [("is_internet", wintypes.BOOL), ("flags", wintypes.DWORD),
                    ("provider", wintypes.LPWSTR), ("principal", wintypes.LPWSTR), ("sid", ctypes.c_void_p)]

    netapi = ctypes.WinDLL("netapi32")
    entry = ctypes.POINTER(UserInfo24)()
    netapi.NetUserGetInfo.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(type(entry)))
    netapi.NetApiBufferFree.argtypes = (ctypes.c_void_p,)
    if netapi.NetUserGetInfo(None, name, 24, ctypes.byref(entry)) != 0:
        return None
    try:
        info = entry.contents
        if info.is_internet and (info.provider or "").casefold() == "microsoftaccount" and info.principal:
            return f"MicrosoftAccount\\{info.principal}"
        return None
    finally:
        netapi.NetApiBufferFree(entry)


def _account_parts(account):
    domain, separator, username = account.rpartition("\\")
    if not username or (separator and not domain) or "\\" in domain or "\0" in account:
        raise ValueError(tr("请填写有效的 Windows 账户名。"))
    return domain, username


def save_credential(account, password):
    account = account.strip()
    _account_parts(account)
    if not password or "\0" in password:
        raise ValueError(tr("请输入 Windows 账户密码"))
    try:
        win32cred.CredWrite({
            "Type": win32cred.CRED_TYPE_GENERIC,
            "TargetName": CREDENTIAL_TARGET,
            "UserName": account,
            # pywin32 写入时接收 str 并转成 UTF-16；CredRead 返回 bytes。
            "CredentialBlob": password,
            "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
        }, 0)
    except (pywintypes.error, ValueError, TypeError):
        raise RuntimeError(tr("无法保存分身密码，请检查账户名和 Windows 凭据服务。")) from None


def forget_credential():
    try:
        win32cred.CredDelete(CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC, 0)
    except pywintypes.error as exc:
        if exc.winerror != 1168:
            raise RuntimeError(tr("无法删除已保存的分身密码，请检查 Windows 凭据服务。")) from None


def change_credential(expected_account, account, password):
    """返回操作后的已存账户及是否执行了操作。不同安装的分身窗口共用同一把锁。"""
    lock = QLockFile(_EDIT_LOCK_PATH)
    if not lock.tryLock(0):
        raise RuntimeError(tr("暂时无法更改分身密码，请稍后重试。"))
    try:
        current = saved_account()
        if current != expected_account:
            return current, False
        if current is None:
            save_credential(account, password)
            return account, True
        forget_credential()
        return None, True
    finally:
        lock.unlock()


def apply_saved_credential(client):
    if client.Server.casefold() != "localhost":
        raise ValueError(tr("分身密码仅用于本机连接"))
    try:
        entry = win32cred.CredRead(CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC, 0)
    except pywintypes.error as exc:
        # 缺少条目、当前登录会话无凭据库或不允许读取时，沿用系统交互登录。
        if exc.winerror in (5, 1168, 1312):
            return
        raise RuntimeError(tr("无法读取分身密码，请检查 Windows 凭据服务。")) from None

    account = entry["UserName"] or ""
    try:
        domain, username = _account_parts(account)
        password = entry["CredentialBlob"].decode("utf-16-le")
    except (AttributeError, ValueError):
        password = ""
    if not password or "\0" in password:
        raise ValueError(tr("已保存的凭据格式有误。请在「自动登录」中删除密码后重新保存。"))
    try:
        client.Domain = domain
        client.UserName = username
        client.AdvancedSettings8.ClearTextPassword = password
    except Exception:
        # 底层异常可能包含调用参数。只将固定错误信息交给上层日志。
        raise RuntimeError(tr("无法向本机分身提供已保存的凭据")) from None

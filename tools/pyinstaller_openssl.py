"""打包时的 OpenSSL 处理，供仓库根目录的三个 .spec 共用。"""
import os
import sys

OPENSSL_DLLS = ("libssl-3-x64.dll", "libcrypto-3-x64.dll")

OPENSSL_RUNTIME_HOOKS = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "pyi_rth_openssl_env.py")]


def python_openssl_binaries() -> list[tuple[str, str]]:
    """返回构建解释器 DLLs 目录下的 OpenSSL，作为 Analysis 的 binaries 条目。

    PyInstaller 的 hook-PySide6.QtNetwork 按 PATH 查找同名 DLL，结果取决于构建机：
    GitHub runner 上收进过 Oracle 签名、启用 uplink 的版本（设置 SSLKEYLOGFILE 时进程直接退出），
    Git Bash 下则是 Git 自带的旧版本（_ssl 导入失败）。同名条目先到先得，hook 的条目又排在
    _ssl.pyd 的依赖之前；Analysis 的 binaries 参数排在所有条目之前，hook 的条目会在依赖分析前被丢弃。

    文件不存在时 PyInstaller 会报错中止构建，不会退回 PATH 查找。
    """
    dll_dir = os.path.join(sys.base_prefix, "DLLs")
    return [(os.path.join(dll_dir, name), ".") for name in OPENSSL_DLLS]

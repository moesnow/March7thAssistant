"""PyInstaller runtime hook：打包程序启动时移除用户环境中影响 OpenSSL 的变量。

这些变量通常是给其他软件设置的：SSLKEYLOGFILE 的路径不可写、OPENSSL_CONF 没有启用 default
provider 时，程序内所有 HTTPS 请求都会失败，更新器还会误报已是最新版本。

不能放到入口脚本里：pyi_rth_setuptools 会连带导入 hashlib，OpenSSL 这时就读取了 OPENSSL_CONF，
之后再移除不起作用。自定义 hook 排在 PyInstaller 自带的 hook 之前，也早于 module.config 导入，
所以 cfg.env 快照和子进程都不会带上这些变量。
"""
import os

for _key in ("SSLKEYLOGFILE", "OPENSSL_CONF"):
    os.environ.pop(_key, None)

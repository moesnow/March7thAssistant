import os
import sys


# 更新器/清理器只是旁观进程：只读取配置、绝不写入。
# 必须在导入 module.*（连带 module.config）之前声明，避免启动时与主程序并发写配置。
os.environ["MARCH7TH_CONFIG_READONLY"] = "1"

os.chdir(
    os.path.dirname(sys.executable)
    if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__))
)

from module.update.helper_app import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

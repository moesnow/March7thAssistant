# ------------------- 测试调用 -------------------
import sys
from tasks.power.schedule import check_schedule
from module.logger import log

if __name__ == "__main__":
    result = None
    if len(sys.argv) > 1:
        result = check_schedule(sys.argv[1])
    else:
        result = check_schedule()
    if result:
        log.info("今天要执行的计划: " + str(result))
    else:
        log.info("今天没有计划")
    
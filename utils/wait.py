import time


def wait_until(condition, timeout, period=1):
    """等待直到条件满足或超时。"""
    end_time = time.monotonic() + timeout
    while time.monotonic() < end_time:
        if condition():
            return True
        time.sleep(period)
    return False

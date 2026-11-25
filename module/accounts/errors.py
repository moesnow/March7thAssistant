"""共享任务流程可使用的账号异常，不依赖桌面账号管理。"""


class AccountError(RuntimeError):
    def __init__(self, reason, message, code=1):
        self.reason, self.exit_code = reason, code
        super().__init__(message)

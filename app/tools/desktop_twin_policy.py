"""用户确认后调整本机分身所需的账户验证策略，并保留恢复记录。"""

import json
from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import QLockFile, QStandardPaths

from module.localization import tr
from utils.data_files import atomic_json


_LSA_KEY = r"SYSTEM\CurrentControlSet\Control\Lsa"


class TwinAuthPolicy:
    def __init__(self, record_path=None):
        self.record_path = Path(record_path) if record_path is not None else (
            Path(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation))
            / "March7thAssistant" / "desktop-twin-auth-policy.json"
        )

    @property
    def restore_available(self):
        return self.record_path.is_file()

    @contextmanager
    def _lock(self):
        self.record_path.parent.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(self.record_path) + ".lock")
        if not lock.tryLock(0):
            raise RuntimeError(tr("账户验证设置正在其他窗口中调整，请稍后重试。"))
        try:
            yield
        finally:
            lock.unlock()

    @staticmethod
    def guest_only():
        try:
            import winreg
        except ImportError:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _LSA_KEY, 0,
                                winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY) as key:
                value, kind = winreg.QueryValueEx(key, "ForceGuest")
        except FileNotFoundError:
            return False
        return kind == winreg.REG_DWORD and value == 1

    def use_classic(self):
        import winreg

        with self._lock(), winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, _LSA_KEY, 0,
            winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY,
        ) as key:
            # 提示出现后，用户或其他程序可能已经更改了这项设置。
            try:
                original, kind = winreg.QueryValueEx(key, "ForceGuest")
            except FileNotFoundError:
                return False
            if kind == winreg.REG_DWORD and original == 0:
                return False
            if kind != winreg.REG_DWORD or original != 1:
                raise RuntimeError(tr("账户验证设置已在其他位置更改，请在 Windows 安全策略中核对。"))
            had_record = self.restore_available
            # 先保存原值；记录失败时不触碰系统设置。所有安装共用此记录和编辑锁。
            atomic_json(self.record_path, {"version": 1, "original": original})
            try:
                winreg.SetValueEx(key, "ForceGuest", 0, winreg.REG_DWORD, 0)
            except OSError:
                if not had_record:
                    self.record_path.unlink(missing_ok=True)
                raise
            if winreg.QueryValueEx(key, "ForceGuest") != (0, winreg.REG_DWORD):
                raise RuntimeError(tr("账户验证设置未生效，可能受组织策略管理，请联系管理员。"))
            return True

    def restore(self):
        import winreg

        with self._lock():
            try:
                record = json.loads(self.record_path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                return
            except ValueError:
                raise RuntimeError(tr("恢复记录有误，请在 Windows 安全策略中检查账户验证设置。")) from None
            if record != {"version": 1, "original": 1}:
                raise RuntimeError(tr("恢复记录有误，请在 Windows 安全策略中检查账户验证设置。"))
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, _LSA_KEY, 0,
                winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY,
            ) as key:
                value, kind = winreg.QueryValueEx(key, "ForceGuest")
                if kind != winreg.REG_DWORD or value not in (0, 1):
                    raise RuntimeError(tr("账户验证设置已在其他位置更改，请在 Windows 安全策略中核对。"))
                if value == 0:
                    winreg.SetValueEx(key, "ForceGuest", 0, winreg.REG_DWORD, record["original"])
                if winreg.QueryValueEx(key, "ForceGuest") != (1, winreg.REG_DWORD):
                    raise RuntimeError(tr("账户验证设置未生效，可能受组织策略管理，请联系管理员。"))
            self.record_path.unlink()

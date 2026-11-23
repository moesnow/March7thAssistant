from copy import deepcopy
from secrets import randbelow

from PySide6.QtCore import QObject, QRunnable, QThread, QThreadPool, QTimer, Signal, Slot
from qfluentwidgets import InfoBar, MessageBox, StateToolTip

from app.card.messagebox_custom import MessageBoxTutorial
from module.channel_catalog import CHANNEL_BY_ID
from module.config import cfg
from module.localization import tr
from module.notification import channels, init_notifiers, results
from .settings_state import config_events


class _TestSignals(QObject):
    done = Signal(str, bool, str)


class _Test(QRunnable):
    def __init__(self, config, channel_id, draft):
        super().__init__()
        self.config = config
        self.channel_id = channel_id
        self.draft = deepcopy(draft)
        self.signals = _TestSignals()

    def run(self):
        try:
            result = channels.send_test(self.config, self.channel_id, self.draft)
        except Exception as exc:
            message = tr(results.REASONS.get(results.failure_code(exc), results.REASONS["failed"]))
            self.signals.done.emit(self.channel_id, False, message)
        else:
            self.signals.done.emit(self.channel_id, result.success, result.reason)


class QqBotBindThread(QThread):
    resultSignal = Signal(bool, str, str)

    def __init__(self, appid, client_secret, mode, code):
        super().__init__()
        self.appid, self.client_secret = appid, client_secret
        self.mode, self.code = mode, code

    def run(self):
        from module.notification.qqbot import QqBotOpenIdBinder
        try:
            binder = QqBotOpenIdBinder({"appid": self.appid, "client_secret": self.client_secret})
            value = binder.capture(self.mode, self.code)
        except Exception as exc:
            message = tr("绑定超时，请重新发起绑定") if isinstance(exc, TimeoutError) else tr("绑定失败，请检查机器人凭据和网络")
            self.resultSignal.emit(False, self.mode, message)
        else:
            self.resultSignal.emit(True, self.mode, value)


# A language change can destroy a page while the bounded binding listener is active.
_bindings = set()


class NotifyModel(QObject):
    changed = Signal()
    testFinished = Signal(str, bool, str)
    bound = Signal(bool, str, str)  # success, full form key, ID or safe explanation

    def __init__(self, window, config=cfg):
        super().__init__(window)
        self.window, self.config = window, config
        self._testing = set()
        self._thread = None
        self._tooltip = None
        self._history = results.read_results()
        self._timer = QTimer(self, interval=2000)
        self._timer.timeout.connect(self._reload_results)
        self._timer.start()
        config_events(config).changed.connect(self._on_config)

    @property
    def binding_pending(self):
        return self._thread is not None

    def _on_config(self, keys):
        if any(k.startswith(("notify_", "notification_")) for k in keys):
            self.changed.emit()

    def _reload_results(self):
        history = results.read_results()
        if history != self._history:
            self._history = history
            self.changed.emit()

    def available(self):
        return channels.available()

    def added(self):
        return channels.added(self.config, self._history)

    def form(self, channel_id):
        return channels.form(self.config, channel_id)

    def _apply(self, errors):
        if not errors:
            init_notifiers()
            self.changed.emit()
        return errors

    def save(self, channel_id, draft):
        return self._apply(channels.save(self.config, channel_id, draft))

    def remove(self, channel_id):
        return self._apply(channels.remove(self.config, channel_id))

    def set_enabled(self, channel_id, enabled):
        return self._apply(channels.set_enabled(self.config, channel_id, enabled))

    def test(self, channel_id, draft):
        if channel_id in self._testing:
            return False
        job = _Test(self.config, channel_id, {**self.form(channel_id), **draft})
        job.signals.done.connect(self._tested)
        self._testing.add(channel_id)
        QThreadPool.globalInstance().start(job)
        return True

    @Slot(str, bool, str)
    def _tested(self, channel_id, success, message):
        self._testing.discard(channel_id)
        self.testFinished.emit(channel_id, success, message)

    def tutorial(self, channel_id):
        channel = CHANNEL_BY_ID[channel_id]
        if not channel.tutorial:
            return False
        MessageBoxTutorial(tr("{name} 配置教程").format(name=tr(channel.name)), channel.tutorial, self.window).exec()
        return True

    def bind_qq(self, mode, draft=None):
        from module.notification.qqbot import QqBotOpenIdBinder
        if mode not in ("user", "group") or _bindings:
            return False
        values = self.form("qqbot")
        values.update(draft or {})
        appid, secret = values["notify_qqbot_appid"], values["notify_qqbot_client_secret"]
        if not appid or not secret:
            InfoBar.warning(tr("无法绑定"), tr("请先填写机器人 AppID 与 AppSecret"), parent=self.window)
            return False
        code = f"{randbelow(10000):04d}"
        tip = (tr("点击「开始监听」后，请在 {seconds} 秒内用 QQ 私聊机器人并发送验证码 {code}") if mode == "user" else
               tr("点击「开始监听」后，请在 {seconds} 秒内在群聊中 @ 机器人发送验证码 {code}，或将机器人拉进目标群"))
        tip = tip.format(seconds=QqBotOpenIdBinder.BIND_TIMEOUT, code=code)
        confirm = MessageBox(tr("自动绑定收件标识"), tip, self.window)
        confirm.yesButton.setText(tr("开始监听"))
        confirm.cancelButton.setText(tr("取消"))
        if not confirm.exec():
            return False
        thread = QqBotBindThread(appid, secret, mode, code)
        self._thread = thread
        self._save_binding = draft is None
        _bindings.add(thread)
        thread.resultSignal.connect(self._bound)
        thread.finished.connect(lambda: _bindings.discard(thread))
        thread.finished.connect(thread.deleteLater)
        self._tooltip = StateToolTip(tr("自动绑定收件标识"), tip, self.window)
        self._tooltip.closeButton.hide()
        self._tooltip.move(self._tooltip.getSuitablePos())
        self._tooltip.show()
        thread.start()
        return True

    @Slot(bool, str, str)
    def _bound(self, success, mode, value):
        self._thread = None
        key = "notify_qqbot_openid" if mode == "user" else "notify_qqbot_group_openid"
        if success and self._save_binding:
            self.config.set_value(key, value)
            init_notifiers()
        if self._tooltip:
            self._tooltip.setContent(tr("绑定成功") if success else tr("绑定失败"))
            self._tooltip.setState(True)
            self._tooltip = None
        self.bound.emit(success, key, value)

"""账号页的对话框：添加、改名、账号密码、打开多账号和删除。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, LineEdit, MessageBoxBase, PasswordLineEdit, PushButton,
                            StrongBodyLabel, SubtitleLabel)

from app.common.mascot import Mascot, load_mascot
from app.pages.common import NoticeStrip, is_evernight, secondary, style_primary
from module.accounts.login_records import mask_hint
from module.localization import tr
from .account_list import server_text
from .avatar import Avatar

MASCOT_HEIGHT = 108


class AccountDialog(MessageBoxBase):
    """标题、说明和右侧的 Q 版插画；表单放进 form。"""

    def __init__(self, title, yes, parent, *, pose=None, width=460):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title, self.widget)
        self.textLabel = secondary(BodyLabel(self.widget))
        self.textLabel.setWordWrap(True)
        self.textLabel.hide()
        column = QVBoxLayout()
        column.setSpacing(8)
        column.addWidget(self.titleLabel)
        column.addWidget(self.textLabel)
        column.addStretch(1)
        head = QHBoxLayout()
        head.setSpacing(16)
        head.addLayout(column, 1)
        self.mascotLabel = None
        if pose is not None:
            self.mascotLabel = QLabel(self.widget)
            self.mascotLabel.setPixmap(load_mascot(pose, MASCOT_HEIGHT, self.devicePixelRatioF(), evernight=is_evernight()))
            head.addWidget(self.mascotLabel, 0, Qt.AlignmentFlag.AlignTop)
        self.form = QVBoxLayout()
        self.form.setSpacing(8)
        self.viewLayout.addLayout(head)
        self.viewLayout.addLayout(self.form)
        self.widget.setMinimumWidth(width)
        self.yesButton.setText(yes)
        self.cancelButton.setText(tr("取消"))
        style_primary(self.yesButton, is_evernight())

    def setText(self, text):
        self.textLabel.setText(text)
        self.textLabel.setVisible(bool(text))

    def addField(self, label, widget):
        self.form.addWidget(StrongBodyLabel(label, self.widget))
        self.form.addWidget(widget)
        return widget

    def addNotice(self, text, kind="warning"):
        notice = NoticeStrip(self.widget, kind=kind)
        notice.setKind(kind, is_evernight())
        notice.setText(text)
        self.form.addWidget(notice)
        return notice


class HintField(QWidget):
    """登录框里显示的账号：输入框和说明，输入不对时说明换成原因。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.edit = LineEdit(self)
        self.edit.setPlaceholderText(tr("例如 138******66"))
        self.edit.setMaxLength(64)
        self.noteLabel = secondary(CaptionLabel(self))
        self.noteLabel.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.edit)
        layout.addWidget(self.noteLabel)
        self.edit.textChanged.connect(self.validate)
        self.validate()

    def validate(self):
        """返回能否保存。空着不算错，但不能保存。"""
        note = tr("游戏登录框里这个账号显示的样子，换号时用它找保留的登录记录。也可以填完整手机号或邮箱，只保存遮挡后的样子。")
        try:
            masked = mask_hint(self.edit.text())
            valid = bool(masked)
            if valid and "*" not in self.edit.text().replace("＊", "*"):
                note = tr("会保存为「{hint}」，换号时用它在游戏登录框里找保留的登录记录。").format(hint=masked)
        except ValueError as error:
            valid, note = False, tr(str(error))
        self.noteLabel.setText(note)
        return valid

    def text(self):
        return self.edit.text().strip()


class AddAccountDialog(AccountDialog):
    """从游戏当前的登录添加账号。detect() 返回当前登录，没有登录返回 None。
    method_for(server) 返回这个服务器的切换方式；在游戏登录框里切换时要填写登录框里显示的账号。"""

    def __init__(self, detect, parent, method_for=None):
        super().__init__(tr("添加账号"), tr("添加"), parent)
        self._detect = detect
        self._method_for = method_for
        self._game = False
        self.login = None
        self.box = QWidget(self.widget)
        self.avatar = Avatar(40, self.box)
        self.uidLabel = StrongBodyLabel(self.box)
        self.stateLabel = secondary(CaptionLabel(self.box))
        self.stateLabel.setWordWrap(True)
        self.retryButton = PushButton(tr("重新检测"), self.box)
        self.retryButton.clicked.connect(self.refresh)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.addWidget(self.uidLabel)
        texts.addWidget(self.stateLabel)
        row = QHBoxLayout(self.box)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(12)
        row.addWidget(self.avatar)
        row.addLayout(texts, 1)
        row.addWidget(self.retryButton)
        self.form.addWidget(self.box)
        self.nameEdit = LineEdit(self.widget)
        self.nameEdit.setPlaceholderText(tr("例如：小号"))
        self.nameEdit.setMaxLength(30)
        self.addField(tr("备注名"), self.nameEdit)
        self.hintLabel = StrongBodyLabel(tr("登录框里显示的账号"), self.widget)
        self.hintField = HintField(self.widget)
        self.hintField.edit.textChanged.connect(self._check)
        self.form.addWidget(self.hintLabel)
        self.form.addWidget(self.hintField)
        self.addNotice(tr("请先完全进入游戏（看到角色）再添加。否则读到的是上一个账号的 UID，保存的登录和账号会对不上。"))
        self.refresh()

    def _check(self):
        found = self.login is not None
        self.yesButton.setEnabled(found and (not self._game or self.hintField.validate()))

    def refresh(self):
        self.login = self._detect()
        found = self.login is not None
        self._game = bool(found and self._method_for and self._method_for(self.login.server) == "game")
        self.hintLabel.setVisible(self._game)
        self.hintField.setVisible(self._game)
        self.avatar.setVisible(found)
        self.nameEdit.setEnabled(found)
        self._check()
        if not found:
            self.uidLabel.setText(tr("没有检测到登录"))
            self.stateLabel.setText(tr("请先启动游戏并登录要添加的账号，进入游戏后点「重新检测」。"))
            return
        self.avatar.setAccount(self.login.color, self.login.name or self.login.masked)
        server = server_text(self.login.server)
        self.uidLabel.setText(" · ".join(filter(None, (f"UID {self.login.masked}", server))))
        if self._game:
            saved = tr("已经添加过，会更新它的资料")
        else:
            saved = tr("已经保存过，会更新它的登录快照")
        self.stateLabel.setText(saved if self.login.saved else tr("游戏当前登录的账号"))
        self.yesButton.setText(tr("更新") if self.login.saved else tr("添加"))
        if self.login.saved and not self.nameEdit.text():
            self.nameEdit.setText(self.login.name)
        if self._game and self.login.hint and not self.hintField.text():
            self.hintField.edit.setText(self.login.hint)

    def name(self):
        return self.nameEdit.text().strip()

    def hint(self):
        """在游戏登录框里切换时返回填写的账号，否则返回 None。"""
        return self.hintField.text() if self._game else None


class HintDialog(AccountDialog):
    def __init__(self, name, hint, parent):
        super().__init__(tr("登录记录中的账号"), tr("保存"), parent, width=440)
        self.setText(tr("「{name}」在游戏登录框里显示的账号。换号时在保留的登录记录里找这一条，只比较星号两边露出来的部分。")
                     .format(name=name))
        self.hintField = HintField(self.widget)
        self.hintField.edit.setText(hint)
        self.hintField.edit.textChanged.connect(lambda: self.yesButton.setEnabled(self.hintField.validate()))
        self.form.addWidget(self.hintField)
        self.yesButton.setEnabled(self.hintField.validate())
        self.hintField.edit.setFocus()

    def hint(self):
        return self.hintField.text()


class MethodDialog(AccountDialog):
    """切换国服账号的切换方式前，说明要做的准备。"""

    def __init__(self, method, parent):
        if method == "game":
            super().__init__(tr("改为在游戏登录框里切换？"), tr("改用游戏登录记录"), parent, pose=Mascot.SERIOUS, width=520)
            lines = (tr("· 换号时关闭游戏，启动后在标题页登出，再在登录框里选目标账号保留的登录记录，不再写回注册表。"),
                     tr("· 请先在游戏里把每个国服账号登录一次，退出时选「退出并保留登录记录」。"),
                     tr("· 在每个账号的「登录记录中的账号」填写登录框里显示的账号，例如 138******66。"),
                     tr("· 已保存的登录快照会留着，但不再使用；国际服账号仍用登录快照。"))
        else:
            super().__init__(tr("改用登录快照？"), tr("改用登录快照"), parent, pose=Mascot.SERIOUS, width=520)
            lines = (tr("· 换号时关闭游戏，写回账号页保存的注册表快照。"),
                     tr("· 之前保存的国服快照可能已经过期，写回会冲掉游戏保留的登录记录，所以每个国服账号要重新保存后才会切换。"),
                     tr("· 多个国服账号轮流时，快照可能在几天后让登录过期。"))
        self.setText("\n".join(lines))
        self.textLabel.setMinimumWidth(320)


class RenameDialog(AccountDialog):
    def __init__(self, name, parent):
        super().__init__(tr("修改备注名"), tr("确认"), parent, width=380)
        self.nameEdit = LineEdit(self.widget)
        self.nameEdit.setMaxLength(30)
        self.nameEdit.setText(name)
        self.nameEdit.selectAll()
        self.form.addWidget(self.nameEdit)
        self.nameEdit.textChanged.connect(lambda text: self.yesButton.setEnabled(bool(text.strip())))
        self.nameEdit.setFocus()

    def name(self):
        return self.nameEdit.text().strip()


class CredentialsDialog(AccountDialog):
    def __init__(self, name, parent):
        super().__init__(tr("填写账号密码"), tr("保存"), parent, pose=Mascot.SERIOUS)
        self.setText(tr("「{name}」的登录过期时，小助手会在登录界面自动输入下面的账号密码。").format(name=name))
        self.accountEdit = LineEdit(self.widget)
        self.accountEdit.setPlaceholderText(tr("手机号、邮箱或用户名"))
        self.passwordEdit = PasswordLineEdit(self.widget)
        self.addField(tr("账号"), self.accountEdit)
        self.addField(tr("密码"), self.passwordEdit)
        self.addNotice(tr("使用 Windows 加密保存在本机，仅当前 Windows 用户可以解密。自动输入密码有一定风险，需要验证码时仍要你自己处理。"))
        for edit in (self.accountEdit, self.passwordEdit):
            edit.textChanged.connect(self._check)
        self._check()
        self.accountEdit.setFocus()

    def _check(self):
        self.yesButton.setEnabled(bool(self.accountEdit.text().strip() and self.passwordEdit.text()))

    def values(self):
        return self.accountEdit.text().strip(), self.passwordEdit.text()


class EnableDialog(AccountDialog):
    def __init__(self, name, parent, method="snapshot"):
        super().__init__(tr("打开多账号轮流？"), tr("启用"), parent, pose=Mascot.SERIOUS, width=500)
        switching = (tr("· 轮流运行时按顺序切换：关闭游戏，启动后在登录框里选登录记录，进入游戏后核对 UID。")
                     if method == "game" else tr("· 轮流运行时按顺序切换：关闭游戏、写回登录、重新启动并核对 UID。"))
        self.setText("\n".join((
            tr("· 「{name}」沿用现在的完成状态，其他账号从空的状态开始。").format(name=name),
            tr("· 现在的任务设置成为共享方案，每个账号可以改用独立方案。"),
            switching)))
        self.textLabel.setMinimumWidth(320)


class DeleteDialog(AccountDialog):
    def __init__(self, name, parent):
        super().__init__(tr("删除「{name}」？").format(name=name), tr("删除账号"), parent, pose=Mascot.BOX)
        self.setText(tr("会删除它的登录快照、保存的密码、独立方案和完成状态。抽卡记录和运行记录不受影响，游戏账号本身也不受影响。"))
        self.cancelButton.setFocus()


class ClearLoginDialog(AccountDialog):
    def __init__(self, parent, method="snapshot"):
        super().__init__(tr("清除游戏登录信息？"), tr("清除"), parent, pose=Mascot.BOX)
        self.setText(tr("这会清除该游戏的登录信息、保留的登录记录和画质、分辨率等设置，之后要在游戏里重新登录每个账号。确定继续吗？")
                     if method == "game" else tr("这会清除该游戏的登录信息和画质、分辨率等设置。确定继续吗？"))
        self.cancelButton.setFocus()

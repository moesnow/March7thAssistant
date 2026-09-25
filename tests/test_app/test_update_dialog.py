# coding:utf-8
"""更新弹窗测试：长更新日志可滚动，更新卡片与按钮固定可见可点。"""
import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or not hasattr(sys, 'getwindowsversion'),
    reason="GUI 测试仅在 Windows 平台运行"
)


LONG_CHANGELOG = (
    '<style>a {color: #f18cb9; font-weight: bold;}</style>'
    '<h2>v2026.9.25 更新日志</h2><ul>'
    + ''.join(f'<li>第 {i} 条很长很长的更新内容，用于把弹窗撑到超出窗口高度</li>' for i in range(200))
    + '</ul><p>详见 <a href="https://github.com">GitHub</a></p>'
)
SHORT_CHANGELOG = '<p>短日志</p>'


@pytest.fixture(scope="session")
def qapp():
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        return app
    except ImportError:
        pytest.skip("PySide6 未安装")


def _pump(qapp, seconds):
    import time
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        qapp.processEvents()
        time.sleep(0.01)


def _build_dialog(qapp, content, theme=None):
    from PySide6.QtWidgets import QWidget

    from app.card.messagebox_custom import MessageBoxUpdate

    parent = QWidget()
    parent.resize(952, 635)
    parent.show()
    dlg = MessageBoxUpdate("发现新版本：1.0 ——> 2.0", content, parent)
    dlg.show()
    _pump(qapp, 0.6)  # 等淡入动画结束（opacity 回到 1）再断言/采样
    return dlg, parent


class TestUpdateDialogLayout:

    def test_long_changelog_keeps_buttons_and_cards_visible(self, qapp):
        dlg, parent = _build_dialog(qapp, LONG_CHANGELOG)
        try:
            # 整体不超出遮罩窗口（遮罩尺寸跟随父窗口）
            assert dlg.widget.height() <= dlg.height()

            widget_geo = dlg.widget.geometry()
            # 两张更新卡片固定在滚动区外、完整可见
            for card in (dlg.githubUpdateCard, dlg.mirrorchyanUpdateCard):
                card_bottom = widget_geo.y() + card.geometry().y() + card.height()
                assert card_bottom <= dlg.height()
            # 底部按钮完整可见（布局算术，不用 mapToGlobal）
            buttons_geo = dlg.buttonGroup.geometry()
            button_bottom = widget_geo.y() + buttons_geo.y() + buttons_geo.height()
            assert button_bottom <= dlg.height()
        finally:
            dlg.deleteLater()
            parent.deleteLater()

    def test_only_changelog_scrolls_cards_are_pinned(self, qapp):
        dlg, parent = _build_dialog(qapp, LONG_CHANGELOG)
        try:
            scroll = dlg._scroll
            assert scroll is not None
            # 更新日志在滚动区内
            assert dlg.contentLabel in scroll.widget().findChildren(type(dlg.contentLabel))
            # 两张更新卡片在滚动区之外（固定布局位置）
            assert dlg.textLayout.indexOf(dlg.githubUpdateCard) != -1
            assert dlg.textLayout.indexOf(dlg.mirrorchyanUpdateCard) != -1
            assert dlg.githubUpdateCard not in scroll.widget().findChildren(type(dlg.githubUpdateCard))
            assert dlg.mirrorchyanUpdateCard not in scroll.widget().findChildren(type(dlg.mirrorchyanUpdateCard))
            # 长内容时滚动区受限高约束（内部滚动而非撑破窗口）
            assert scroll.maximumHeight() > 0
            assert scroll.height() <= scroll.maximumHeight()
        finally:
            dlg.deleteLater()
            parent.deleteLater()

    def test_fade_split_applies(self, qapp):
        dlg, parent = _build_dialog(qapp, LONG_CHANGELOG)
        try:
            dlg._start_fade(0.5, 0.5, 5000, None)
            # 整窗挂效果是动画内容突兀闪现的根因，绝不能出现
            assert dlg.graphicsEffect() is None
            assert dlg.widget.graphicsEffect() is not None
            assert dlg._scroll.widget().graphicsEffect() is not None
            dlg._stop_fade()
            assert dlg._scroll.widget().graphicsEffect() is None
        finally:
            dlg.deleteLater()
            parent.deleteLater()


class TestUpdateDialogScrollBackground:
    """滚动区底色必须与面板同色（回归：容器自填底与外框割裂）。"""

    @pytest.mark.parametrize("theme_name", ["light", "dark"])
    def test_scroll_bg_matches_panel(self, qapp, theme_name):
        from PySide6.QtCore import QPoint
        from qfluentwidgets import Theme, qconfig, setTheme

        old_theme = qconfig.theme
        setTheme(Theme.LIGHT if theme_name == "light" else Theme.DARK)
        dlg = parent = None
        try:
            dlg, parent = _build_dialog(qapp, SHORT_CHANGELOG)
            img = dlg.grab().toImage()
            container = dlg._scroll.widget()
            # 滚动区内日志右侧的空白区（底色透出点；短日志很矮，
            # 必须横向取空白，采到字形边缘会得到次像素彩边导致误报）
            p_scroll = container.mapTo(dlg, QPoint(container.width() - 30, container.height() // 2))
            # 滚动区之外的面板底色（按钮区上方）
            p_panel = QPoint(dlg.widget.x() + dlg.widget.width() // 2,
                             dlg.widget.y() + dlg.buttonGroup.y() - 12)
            c_scroll = img.pixelColor(p_scroll)
            c_panel = img.pixelColor(p_panel)
            delta = max(abs(c_scroll.red() - c_panel.red()),
                        abs(c_scroll.green() - c_panel.green()),
                        abs(c_scroll.blue() - c_panel.blue()))
            assert delta <= 2, (
                f"{theme_name} 主题下滚动区底色 {c_scroll.name()} 与面板 {c_panel.name()} 不一致"
            )
        finally:
            if dlg is not None:
                dlg.deleteLater()
            if parent is not None:
                parent.deleteLater()
            setTheme(old_theme)

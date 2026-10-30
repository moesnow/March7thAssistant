# coding:utf-8
"""帮助页：后台运行标签位于常见问题之后；文档里的站内链接换成官网地址，界面中才能打开。"""
import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or not hasattr(sys, 'getwindowsversion'),
    reason="GUI 测试仅在 Windows 平台运行"
)


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


def test_background_tab_follows_faq_and_links_open_on_site(qapp):
    from app.help_interface import HelpInterface
    page = HelpInterface()
    try:
        order = [page.stackedWidget.widget(i).objectName() for i in range(page.stackedWidget.count())]
        assert order == ['tutorialLabel', 'workflowLabel', 'faqLabel', 'backgroundLabel', 'tasksLabel', 'changelogLabel']
        html = page.backgroundLabel.toHtml()
        assert 'href="/assets/docs/' not in html
        assert 'https://m7a.top/docs/#/assets/docs/Docker' in html
    finally:
        page.deleteLater()


def test_site_links_cover_localized_docs_only():
    from app.help_interface import HelpInterface
    text = '[a](/assets/docs/Background_en_US.md) [b](/assets/docs/Docker.md) [c](https://example.com/x.md)'
    assert HelpInterface._site_links(text) == (
        '[a](https://m7a.top/docs/#/assets/docs/Background_en_US) '
        '[b](https://m7a.top/docs/#/assets/docs/Docker) [c](https://example.com/x.md)')


def test_website_button_opens_current_tab_doc_and_stays_right_aligned(qapp):
    from app.help_interface import DOC_OF_TAB, HelpInterface
    from module.localization.languages import localized_doc_path
    page = HelpInterface()
    try:
        opened = []
        page.open_url = opened.append
        page.resize(1100, 700)
        page.show()
        qapp.processEvents()
        button = page.websiteButton.geometry()
        assert page.width() - button.right() - 1 == 36 and button.y() == 36
        for name, base in DOC_OF_TAB.items():
            page.stackedWidget.setCurrentWidget(getattr(page, name))
            page.websiteButton.click()
            doc = localized_doc_path(base).rsplit('/', 1)[-1][:-len('.md')]
            assert opened[-1] == f'https://m7a.top/docs/#/assets/docs/{doc}'
        assert set(DOC_OF_TAB) == {page.stackedWidget.widget(i).objectName()
                                   for i in range(page.stackedWidget.count())}
    finally:
        page.close()
        page.deleteLater()

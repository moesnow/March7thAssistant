import os
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


class TestUiIconEnum:
    def test_has_expected_members(self, qapp):
        from app.common.icon import UiIcon
        assert hasattr(UiIcon, 'FLASH')
        assert hasattr(UiIcon, 'GIFT')
        assert hasattr(UiIcon, 'PEOPLE_TEAM')

    def test_path_returns_string(self, qapp):
        from app.common.icon import UiIcon
        p = UiIcon.FLASH.path()
        assert isinstance(p, str)
        assert p.endswith(".svg")

    def test_path_contains_value(self, qapp):
        from app.common.icon import UiIcon
        p = UiIcon.PEOPLE_TEAM.path()
        assert "people-team" in p


class TestBrandIconEnum:
    def test_has_expected_members(self, qapp):
        from app.common.icon import BrandIcon
        assert hasattr(BrandIcon, 'TELEGRAM')
        assert hasattr(BrandIcon, 'DINGTALK')
        assert hasattr(BrandIcon, 'WECOM')

    def test_path_contains_value(self, qapp):
        from app.common.icon import BrandIcon
        p = BrandIcon.TELEGRAM.path()
        assert "telegram" in p
        assert p.endswith(".svg")


class TestIconAssets:
    """校验所有自定义图标的黑白双版文件都存在且可渲染。"""

    def _all_icons(self):
        from app.common.icon import UiIcon, BrandIcon
        return list(UiIcon) + list(BrandIcon)

    def test_svg_files_exist(self, qapp):
        missing = []
        for icon in self._all_icons():
            for theme_name in ("black", "white"):
                folder = "ui" if icon.__class__.__name__ == "UiIcon" else "brand"
                p = f"./assets/app/images/icons/{folder}/{icon.value}_{theme_name}.svg"
                if not os.path.exists(p):
                    missing.append(p)
        assert not missing, f"缺少图标文件: {missing}"

    def test_svg_files_render(self, qapp):
        from PySide6.QtGui import QIcon
        broken = []
        for icon in self._all_icons():
            for theme_name in ("black", "white"):
                folder = "ui" if icon.__class__.__name__ == "UiIcon" else "brand"
                p = f"./assets/app/images/icons/{folder}/{icon.value}_{theme_name}.svg"
                pm = QIcon(p).pixmap(16, 16)
                if pm.isNull():
                    broken.append(p)
        assert not broken, f"图标渲染为空: {broken}"

    def test_black_white_variants_differ(self, qapp):
        same = []
        for icon in self._all_icons():
            folder = "ui" if icon.__class__.__name__ == "UiIcon" else "brand"
            black = f"./assets/app/images/icons/{folder}/{icon.value}_black.svg"
            white = f"./assets/app/images/icons/{folder}/{icon.value}_white.svg"
            with open(black, encoding="utf-8") as f1, open(white, encoding="utf-8") as f2:
                if f1.read() == f2.read():
                    same.append(icon.value)
        assert not same, f"黑白两版内容相同（颜色未生效）: {same}"

    def test_viewbox_matches_source_grid(self, qapp):
        """回归测试：viewBox 必须使用图标源网格尺寸（曾因写死 24 导致 48 网格图标被裁切）。"""
        import json
        import re
        with open("./assets/app/images/icons/sources.json", encoding="utf-8") as f:
            manifest = json.load(f)
        wrong = []
        for icon in self._all_icons():
            folder = "ui" if icon.__class__.__name__ == "UiIcon" else "brand"
            key = f"{folder}/{icon.value}"
            if key not in manifest:
                wrong.append(f"{key}: 不在 sources.json 中")
                continue
            w, h = manifest[key]["grid"]
            p = f"./assets/app/images/icons/{folder}/{icon.value}_black.svg"
            with open(p, encoding="utf-8") as f:
                head = f.read(200)
            m = re.search(r'viewBox="0 0 (\d+) (\d+)"', head)
            if not m or (int(m.group(1)), int(m.group(2))) != (w, h):
                wrong.append(f"{key}: viewBox={m.groups() if m else None} 期望 {(w, h)}")
        assert not wrong, f"viewBox 与源网格不一致: {wrong}"

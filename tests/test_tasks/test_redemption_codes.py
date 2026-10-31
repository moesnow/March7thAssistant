import importlib.util
import sys
import threading
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import requests


class FakeLog:
    def __init__(self):
        self.warnings = []

    def warning(self, message, *args, **kwargs):
        self.warnings.append(message)

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def _stub_module(name, **attributes):
    module = ModuleType(name)
    for attribute, value in attributes.items():
        setattr(module, attribute, value)
    return module


def _load_redemption_module(log):
    cfg = SimpleNamespace(useragent={})
    stub_modules = {
        "module.screen": _stub_module("module.screen", screen=object()),
        "module.automation": _stub_module("module.automation", auto=object()),
        "module.config": _stub_module("module.config", cfg=cfg),
        "module.logger": _stub_module("module.logger", log=log),
        "module.game": _stub_module("module.game", get_game_controller=lambda: None),
        "utils.color": _stub_module("utils.color", red=str, green=str, yellow=str),
        "tasks.reward": _stub_module("tasks.reward"),
        "module.notification": _stub_module("module.notification", notif=object()),
        "module.notification.notification": _stub_module(
            "module.notification.notification", NotificationLevel=SimpleNamespace(ALL="all")
        ),
    }
    path = Path(__file__).parents[2] / "tasks" / "daily" / "redemption.py"
    spec = importlib.util.spec_from_file_location("redemption_under_test", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stub_modules):
        spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, data, content_type="application/json"):
        self._data = data
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        pass

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


STALE = [{"server": "cn", "code": "OLD", "expires_at": None}]
FRESH = [
    {"server": "cn", "code": "OLD", "expires_at": None},
    {"server": "cn", "code": "NEW", "expires_at": None},
]


class TestLoadCodesFromUrl(unittest.TestCase):
    def setUp(self):
        self.log = FakeLog()
        self.module = _load_redemption_module(self.log)

    def _run(self, responses):
        stale_returned = threading.Event()

        def fake_get(url, headers=None, timeout=None):
            result = responses[url]
            if url == "stale":
                stale_returned.set()
            elif url == "fresh" and "stale" in responses:
                # 让缓存了旧清单的镜像先返回，复现它赢得竞速的情形
                stale_returned.wait(timeout=1)
            if isinstance(result, Exception):
                raise result
            return result

        with patch.object(requests, "get", side_effect=fake_get):
            return self.module.load_codes_from_url(list(responses))

    def test_new_codes_from_slower_mirror_are_kept(self):
        codes = self._run({"fresh": FakeResponse(FRESH), "stale": FakeResponse(STALE)})

        self.assertEqual({c["code"] for c in codes}, {"OLD", "NEW"})

    def test_duplicate_code_takes_entry_from_earlier_url(self):
        first = [{"server": "cn", "code": "OLD", "expires_at": "2099-01-01T00:00:00+08:00"}]
        codes = self._run({"first": FakeResponse(first), "fresh": FakeResponse(FRESH)})

        old = [c for c in codes if c["code"] == "OLD"]
        self.assertEqual(old, first)

    def test_failed_mirror_is_skipped(self):
        codes = self._run({
            "broken": FakeResponse("<html>", content_type="text/html"),
            "fresh": FakeResponse(FRESH),
        })

        self.assertEqual({c["code"] for c in codes}, {"OLD", "NEW"})
        self.assertTrue(any("broken" in w for w in self.log.warnings))

    def test_all_mirrors_failing_raises(self):
        with self.assertRaisesRegex(RuntimeError, "所有 URL 均不可用"):
            self._run({
                "a": requests.ConnectionError("offline"),
                "b": FakeResponse("<html>", content_type="text/html"),
            })


if __name__ == "__main__":
    unittest.main()

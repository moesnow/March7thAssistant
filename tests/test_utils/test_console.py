import os
from utils.console import is_gui_started, is_docker_started, should_skip_pause


class TestConsole:
    def test_is_gui_started_true(self, monkeypatch):
        monkeypatch.setenv("MARCH7TH_GUI_STARTED", "true")
        assert is_gui_started() is True

    def test_is_gui_started_false(self, monkeypatch):
        monkeypatch.delenv("MARCH7TH_GUI_STARTED", raising=False)
        assert is_gui_started() is False

    def test_is_gui_started_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("MARCH7TH_GUI_STARTED", "TRUE")
        assert is_gui_started() is True

    def test_is_docker_started_true(self, monkeypatch):
        monkeypatch.setenv("MARCH7TH_DOCKER_STARTED", "true")
        assert is_docker_started() is True

    def test_is_docker_started_false(self, monkeypatch):
        monkeypatch.delenv("MARCH7TH_DOCKER_STARTED", raising=False)
        assert is_docker_started() is False

    def test_should_skip_pause_gui(self, monkeypatch):
        monkeypatch.setenv("MARCH7TH_GUI_STARTED", "true")
        monkeypatch.delenv("MARCH7TH_DOCKER_STARTED", raising=False)
        assert should_skip_pause() is True

    def test_should_skip_pause_docker(self, monkeypatch):
        monkeypatch.delenv("MARCH7TH_GUI_STARTED", raising=False)
        monkeypatch.setenv("MARCH7TH_DOCKER_STARTED", "true")
        assert should_skip_pause() is True

    def test_should_skip_pause_neither(self, monkeypatch):
        monkeypatch.delenv("MARCH7TH_GUI_STARTED", raising=False)
        monkeypatch.delenv("MARCH7TH_DOCKER_STARTED", raising=False)
        assert should_skip_pause() is False

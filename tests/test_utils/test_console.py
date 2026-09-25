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


class TestGuiStartedEnvContract:
    """读写契约：所有 MARCH7TH_GUI_STARTED 写入方的值必须被 is_gui_started 认可。

    一旦失配（如历史上的 "1" vs "true"），GUI 启动的子进程会被误判为终端程序，
    报错路径的 pause_on_error() 阻塞在 input() 上，GUI 侧表现为任务永不结束。
    """

    def test_all_written_values_are_recognized(self, monkeypatch):
        import re
        from pathlib import Path
        source = (Path(__file__).resolve().parents[2] / 'app' / 'log_interface.py').read_text(encoding='utf-8')
        written = re.findall(r'env\.insert\("MARCH7TH_GUI_STARTED", "([^"]+)"\)', source)
        assert written, "app/log_interface.py 中应存在 MARCH7TH_GUI_STARTED 写入点"
        for value in written:
            monkeypatch.setenv("MARCH7TH_GUI_STARTED", value)
            assert is_gui_started() is True, f"写入值 {value!r} 未被 is_gui_started() 认可"

    def test_documented_reader_contract(self, monkeypatch):
        # 记录读端契约：只认 "true" 族；因此写入方禁止再写 "1"
        monkeypatch.setenv("MARCH7TH_GUI_STARTED", "1")
        assert is_gui_started() is False

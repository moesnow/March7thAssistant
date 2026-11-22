import os
import sys
from unittest.mock import DEFAULT, Mock, call

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows Core Audio")


class FakeVolume:
    def __init__(self, muted=False):
        self._muted = muted

    def muted(self):
        return self._muted

    def set_muted(self, value):
        self._muted = bool(value)


def make_muter(sessions, marker=None):
    from app.tools.process_audio import ProcessAudioMuter

    def visit(pid, apply):
        for instance, volume in list(sessions.items()):
            apply(instance, volume)

    return ProcessAudioMuter(pid=1, visit_sessions=visit, marker=marker)


def test_mute_keeps_original_state_and_respects_manual_unmute(tmp_path):
    marker = tmp_path / "muted"
    sessions = {"a": FakeVolume(), "b": FakeVolume(muted=True)}
    muter = make_muter(sessions, str(marker))

    muter.mute()
    assert all(volume.muted() for volume in sessions.values()) and marker.exists()
    sessions["a"].set_muted(False)  # 用户在音量合成器里手动取消静音
    sessions["c"] = FakeVolume()  # 隐藏期间新出现的会话
    muter.mute()
    assert not sessions["a"].muted() and sessions["c"].muted()

    muter.restore()
    assert [sessions[key].muted() for key in "abc"] == [False, True, False]
    assert not muter.muting and not marker.exists()


@pytest.mark.parametrize("stale", [False, True], ids=["normal", "stale-marker"])
def test_restore_keeps_failed_session_and_skips_restored_sessions(tmp_path, monkeypatch, stale):
    marker = tmp_path / "muted"
    if stale:
        marker.write_text("1", encoding="utf-8")
    sessions = {"a": FakeVolume(), "b": FakeVolume(), "c": FakeVolume()}
    muter = make_muter(sessions, str(marker))
    muter.mute()
    restore_b = Mock(wraps=sessions["b"].set_muted, side_effect=[OSError("restore failed"), DEFAULT])
    monkeypatch.setattr(sessions["b"], "set_muted", restore_b)

    with pytest.raises(OSError, match="restore failed"):
        muter.restore()
    assert marker.exists() and not muter.muting
    assert [volume.muted() for volume in sessions.values()] == [False, True, False]

    sessions["a"].set_muted(True)  # 已恢复的会话由用户重新静音。
    muter.clear_stale()
    assert [volume.muted() for volume in sessions.values()] == [True, True, False]
    muter.restore()
    assert [volume.muted() for volume in sessions.values()] == [True, False, False]
    assert restore_b.call_args_list == [call(False), call(False)]
    assert not marker.exists()


def test_mute_left_by_a_killed_process_is_cleared(tmp_path):
    marker = tmp_path / "muted"
    marker.write_text("1", encoding="utf-8")
    sessions = {}
    muter = make_muter(sessions, str(marker))
    assert muter.stale

    muter.clear_stale()  # 还没开始播放声音，没有会话：保留标记，稍后再试
    assert muter.stale and marker.exists()
    sessions["a"] = FakeVolume(muted=True)  # Windows 记住并带过来的静音
    muter.clear_stale()
    assert not sessions["a"].muted() and not muter.stale and not marker.exists()


def test_hiding_before_stale_cleanup_restores_to_unmuted(tmp_path):
    marker = tmp_path / "muted"
    marker.write_text("1", encoding="utf-8")
    sessions = {"a": FakeVolume(muted=True)}
    muter = make_muter(sessions, str(marker))

    muter.mute()
    muter.restore()
    assert not sessions["a"].muted() and not muter.stale and not marker.exists()


def test_core_audio_enumeration_runs_on_this_machine():
    """真实的 Core Audio 调用：本进程通常没有会话；没有音频服务的机器上跳过。"""
    from app.tools.process_audio import visit_process_sessions

    try:
        visit_process_sessions(os.getpid(), lambda instance, volume: volume.muted())
    except OSError as error:
        pytest.skip(f"音频服务不可用：{error}")

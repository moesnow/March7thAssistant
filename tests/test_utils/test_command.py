from unittest.mock import patch, MagicMock
import subprocess
from utils.command import subprocess_with_timeout, subprocess_with_stdout


class TestSubprocessWithTimeout:
    @patch("utils.command.subprocess.Popen")
    def test_success(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        result = subprocess_with_timeout(["echo", "hello"], timeout=5)
        assert result is True

    @patch("utils.command.subprocess.Popen")
    def test_failure(self, mock_popen):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        result = subprocess_with_timeout(["false"], timeout=5)
        assert result is False

    @patch("utils.command.subprocess.Popen")
    def test_timeout(self, mock_popen):
        mock_process = MagicMock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=5)
        mock_popen.return_value = mock_process
        result = subprocess_with_timeout(["sleep", "100"], timeout=5)
        assert result is False
        mock_process.terminate.assert_called_once()


class TestSubprocessWithStdout:
    @patch("utils.command.subprocess.run")
    def test_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "hello world\n"
        mock_run.return_value = mock_result
        result = subprocess_with_stdout(["echo", "hello"])
        assert result == "hello world"

    @patch("utils.command.subprocess.run")
    def test_failure(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        result = subprocess_with_stdout(["false"])
        assert result is None

    @patch("utils.command.subprocess.run")
    def test_exception(self, mock_run):
        mock_run.side_effect = Exception("command not found")
        result = subprocess_with_stdout(["nonexistent"])
        assert result is None

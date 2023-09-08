import subprocess


class Subprocess:
    @staticmethod
    def run(command, timeout):
        process = None
        try:
            process = subprocess.Popen(command, shell=True)
            process.communicate(timeout=timeout)
            if process.returncode == 0:
                return True
        except subprocess.TimeoutExpired:
            if process is not None:
                process.terminate()
                process.wait()
        return False

# 调用 PaddleOCR-json.exe 的 Python Api
# 项目主页：
# https://github.com/hiroi-sora/PaddleOCR-json

import os
import socket  # 套接字
import subprocess  # 进程，管道
from json import loads as jsonLoads, dumps as jsonDumps
from sys import platform as sysPlatform  # popen静默模式
from base64 import b64encode  # base64 编码

# 为了在父进程被强制结束时让子进程也退出，分别实现：
# - Windows: 使用 Job Object 并设置 JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
# - Linux: 在子进程 preexec_fn 中调用 prctl(PR_SET_PDEATHSIG, SIGTERM)
import ctypes
import signal


def _set_pdeathsig():
    """在 Linux 子进程中设置父进程死亡信号，父进程退出时子进程将收到 SIGTERM。"""
    try:
        libc = ctypes.CDLL("libc.so.6")
        PR_SET_PDEATHSIG = 1
        libc.prctl(PR_SET_PDEATHSIG, signal.SIGTERM)
    except Exception:
        # 不影响主流程，失败则忽略
        pass


def _assign_process_to_jobobj(popen_obj):
    """在 Windows 下将进程分配到一个 Job 对象，并设置在 Job 关闭时杀死子进程的标志。
    返回 True 表示成功，失败返回 False（不抛出异常）。"""
    try:
        if "win32" not in str(sysPlatform).lower():
            return False
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        JobObjectExtendedLimitInformation = 9
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('PerProcessUserTimeLimit', ctypes.c_longlong),
                ('PerJobUserTimeLimit', ctypes.c_longlong),
                ('LimitFlags', ctypes.c_uint32),
                ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t),
                ('ActiveProcessLimit', ctypes.c_uint32),
                ('Affinity', ctypes.c_size_t),
                ('PriorityClass', ctypes.c_uint32),
                ('SchedulingClass', ctypes.c_uint32),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ('ReadOperationCount', ctypes.c_ulonglong),
                ('WriteOperationCount', ctypes.c_ulonglong),
                ('OtherOperationCount', ctypes.c_ulonglong),
                ('ReadTransferCount', ctypes.c_ulonglong),
                ('WriteTransferCount', ctypes.c_ulonglong),
                ('OtherTransferCount', ctypes.c_ulonglong),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ('IoInfo', IO_COUNTERS),
                ('ProcessMemoryLimit', ctypes.c_size_t),
                ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t),
                ('PeakJobMemoryUsed', ctypes.c_size_t),
            ]

        CreateJobObject = kernel32.CreateJobObjectW
        CreateJobObject.restype = ctypes.c_void_p
        SetInformationJobObject = kernel32.SetInformationJobObject
        SetInformationJobObject.restype = ctypes.c_bool
        AssignProcessToJobObject = kernel32.AssignProcessToJobObject
        AssignProcessToJobObject.restype = ctypes.c_bool

        job = CreateJobObject(None, None)
        if not job:
            return False
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        res = SetInformationJobObject(job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info))
        if not res:
            return False
        # 尝试直接使用 Popen 的内部 handle，否则使用 OpenProcess
        try:
            process_handle = ctypes.c_void_p(popen_obj._handle)
        except Exception:
            PROCESS_ALL_ACCESS = (0x000F0000 | 0x00100000 | 0xFFF)
            OpenProcess = kernel32.OpenProcess
            OpenProcess.restype = ctypes.c_void_p
            process_handle = OpenProcess(PROCESS_ALL_ACCESS, False, popen_obj.pid)
            if not process_handle:
                return False
        ok = AssignProcessToJobObject(job, process_handle)
        if ok:
            # 保留 job 对象句柄以免被回收，确保在父进程句柄关闭时 Job 被关闭从而杀死子进程
            popen_obj._job_object = job
            return True
    except Exception:
        return False
    return False


class PPOCR_pipe:
    """调用OCR（管道模式）"""

    def __init__(self, exePath: str, argument: dict = None):
        """初始化识别器（管道模式）。\n
        `exePath`: 识别器`PaddleOCR_json.exe`的路径。\n
        `argument`: 启动参数，字典`{"键":值}`。参数说明见 https://github.com/hiroi-sora/PaddleOCR-json
        """
        cwd = os.path.abspath(os.path.join(exePath, os.pardir))  # 获取exe父文件夹
        # 处理启动参数
        if not argument is None:
            for key, value in argument.items():
                if isinstance(value, str):  # 字符串类型的值加双引号
                    exePath += f' --{key}="{value}"'
                else:
                    exePath += f" --{key}={value}"
        # 设置子进程启用静默模式，不显示控制台窗口
        creationflags = 0
        if "win32" in str(sysPlatform).lower():
            creationflags = subprocess.CREATE_NO_WINDOW
        # 在 Linux 下希望子进程在父进程死亡时收到 SIGTERM
        preexec_fn = None
        if "linux" in str(sysPlatform).lower():
            preexec_fn = _set_pdeathsig
        # 通过 kwargs 传递可选参数以保持兼容
        popen_kwargs = dict(cwd=cwd,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
        if creationflags:
            popen_kwargs['creationflags'] = creationflags
        if preexec_fn is not None:
            popen_kwargs['preexec_fn'] = preexec_fn
        self.ret = subprocess.Popen(
            exePath,
            **popen_kwargs
        )
        # Windows 下将子进程与 Job 对象绑定，确保父进程句柄关闭时杀死子进程
        try:
            _assign_process_to_jobobj(self.ret)
        except Exception:
            pass
        # 启动子进程
        while True:
            if not self.ret.poll() is None:  # 子进程已退出，初始化失败
                raise Exception(f"OCR init fail.")
            initStr = self.ret.stdout.readline().decode("utf-8", errors="ignore")
            if "OCR init completed." in initStr:  # 初始化成功
                break

    def runDict(self, writeDict: dict):
        """传入指令字典，发送给引擎进程。\n
        `writeDict`: 指令字典。\n
        `return`:  {"code": 识别码, "data": 内容列表或错误信息字符串}\n"""
        # 检查子进程
        if not self.ret.poll() is None:
            return {"code": 901, "data": f"子进程已崩溃。"}
        # 输入信息
        writeStr = jsonDumps(writeDict, ensure_ascii=True, indent=None) + "\n"
        try:
            self.ret.stdin.write(writeStr.encode("utf-8"))
            self.ret.stdin.flush()
        except Exception as e:
            return {"code": 902, "data": f"向识别器进程传入指令失败，疑似子进程已崩溃。{e}"}
        # 获取返回值
        try:
            getStr = self.ret.stdout.readline().decode("utf-8", errors="ignore")
        except Exception as e:
            return {"code": 903, "data": f"读取识别器进程输出值失败。异常信息：[{e}]"}
        try:
            return jsonLoads(getStr)
        except Exception as e:
            return {"code": 904, "data": f"识别器输出值反序列化JSON失败。异常信息：[{e}]。原始内容：[{getStr}]"}

    def run(self, imgPath: str):
        """对一张本地图片进行文字识别。\n
        `exePath`: 图片路径。\n
        `return`:  {"code": 识别码, "data": 内容列表或错误信息字符串}\n"""
        writeDict = {"image_path": imgPath}
        return self.runDict(writeDict)

    def runClipboard(self):
        """立刻对剪贴板第一位的图片进行文字识别。\n
        `return`:  {"code": 识别码, "data": 内容列表或错误信息字符串}\n"""
        return self.run("clipboard")

    def runBase64(self, imageBase64: str):
        """对一张编码为base64字符串的图片进行文字识别。\n
        `imageBase64`: 图片base64字符串。\n
        `return`:  {"code": 识别码, "data": 内容列表或错误信息字符串}\n"""
        writeDict = {"image_base64": imageBase64}
        return self.runDict(writeDict)

    def runBytes(self, imageBytes):
        """对一张图片的字节流信息进行文字识别。\n
        `imageBytes`: 图片字节流。\n
        `return`:  {"code": 识别码, "data": 内容列表或错误信息字符串}\n"""
        imageBase64 = b64encode(imageBytes).decode('utf-8')
        return self.runBase64(imageBase64)

    def exit(self):
        """关闭引擎子进程"""
        self.ret.kill()  # 关闭子进程

    @staticmethod
    def printResult(res: dict):
        """用于调试，格式化打印识别结果。\n
        `res`: OCR识别结果。"""

        # 识别成功
        if res["code"] == 100:
            index = 1
            for line in res["data"]:
                print(f"{index}-置信度：{round(line['score'], 2)}，文本：{line['text']}")
                index += 1
        elif res["code"] == 100:
            print("图片中未识别出文字。")
        else:
            print(f"图片识别失败。错误码：{res['code']}，错误信息：{res['data']}")

    def __del__(self):
        self.exit()


class PPOCR_socket(PPOCR_pipe):
    """调用OCR（套接字模式）"""

    def __init__(self, exePath: str, argument: dict = None):
        """初始化识别器（套接字模式）。\n
        `exePath`: 识别器`PaddleOCR_json.exe`的路径。\n
        `argument`: 启动参数，字典`{"键":值}`。参数说明见 https://github.com/hiroi-sora/PaddleOCR-json
        """
        # 处理参数
        if not argument:
            argument = {}
        argument["port"] = 0  # 随机端口号
        argument["addr"] = "loopback"  # 本地环回地址
        super().__init__(exePath, argument)  # 父类构造函数
        # 再获取一行输出，检查是否成功启动服务器
        initStr = self.ret.stdout.readline().decode("utf-8", errors="ignore")
        if not self.ret.poll() is None:  # 子进程已退出，初始化失败
            raise Exception(f"Socket init fail.")
        if "Socket init completed. " in initStr:  # 初始化成功
            splits = initStr.split(":")
            self.ip = splits[0].split("Socket init completed. ")[1]
            self.port = int(splits[1])   # 提取端口号
            self.ret.stdout.close()  # 关闭管道重定向，防止缓冲区填满导致堵塞
            print(f"套接字服务器初始化成功。{self.ip}:{self.port}")
            return
        # 异常
        self.exit()
        raise Exception(f"Socket init fail.")

    def runDict(self, writeDict: dict):
        """传入指令字典，发送给引擎进程。\n
        `writeDict`: 指令字典。\n
        `return`:  {"code": 识别码, "data": 内容列表或错误信息字符串}\n"""
        # 检查子进程
        if not self.ret.poll() is None:
            return {"code": 901, "data": f"子进程已崩溃。"}
        # 通信
        writeStr = jsonDumps(writeDict, ensure_ascii=True, indent=None) + "\n"
        try:
            # 创建TCP连接
            clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            clientSocket.connect((self.ip, self.port))
            # 发送数据
            clientSocket.sendall(writeStr.encode())
            # 接收数据
            resData = b''
            while True:
                chunk = clientSocket.recv(1024)
                if not chunk:
                    break
                resData += chunk
            getStr = resData.decode()
        except ConnectionRefusedError:
            return {"code": 902, "data": "连接被拒绝"}
        except TimeoutError:
            return {"code": 903, "data": "连接超时"}
        except Exception as e:
            return {"code": 904, "data": f"网络错误：{e}"}
        finally:
            clientSocket.close()  # 关闭连接
        # 反序列输出信息
        try:
            return jsonLoads(getStr)
        except Exception as e:
            return {"code": 905, "data": f"识别器输出值反序列化JSON失败。异常信息：[{e}]。原始内容：[{getStr}]"}


def GetOcrApi(exePath: str, argument: dict = None, ipcMode: str = "pipe"):
    """获取识别器API对象。\n
    `exePath`: 识别器`PaddleOCR_json.exe`的路径。\n
    `argument`: 启动参数，字典`{"键":值}`。参数说明见 https://github.com/hiroi-sora/PaddleOCR-json\n
    `ipcMode`: 进程通信模式，可选值为套接字模式`socket` 或 管道模式`pipe`。用法上完全一致。
    """
    if ipcMode == "socket":
        return PPOCR_socket(exePath, argument)
    elif ipcMode == "pipe":
        return PPOCR_pipe(exePath, argument)
    else:
        raise Exception(f'ipcMode可选值为 套接字模式"socket" 或 管道模式"pipe" ，不允许{ipcMode}。')

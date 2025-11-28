import sys
import time
import json
import threading
from collections import deque
from utils.color import green
from utils.singleton import SingletonMeta
from utils.logger.logger import Logger
from typing import Optional
from module.automation import auto
from module.config import cfg


class Screen(metaclass=SingletonMeta):
    """
    界面管理类
    """

    def __init__(self, config_path, logger: Optional[Logger] = None):
        """
        初始化界面管理器。
        :param config_path: 界面配置文件的路径。
        :param logger: 日志管理器实例，用于记录日志。
        """
        self.logger = logger
        self.current_screen = None  # 当前显示的界面
        self.current_screen_threshold = 0  # 当前界面的阈值
        self.screen_map = {}  # 存储界面信息的字典
        self.wait_screen_change_time = 0.5
        self.lock = threading.Lock()  # 创建一个锁，用于线程同步
        self._setup_screens_from_config(config_path)

    def _add_screen(self, id, name, image_path, actions):
        """
        添加一个新界面到界面管理器。
        :param id: 新界面的唯一标识。
        :param name: 新界面的名称。
        :param image_path: 用于识别界面的图片路径。
        :param actions: 可切换的目标界面及操作序列。
        """
        self.screen_map[id] = {'name': name, 'image_path': image_path, 'actions': actions}

    def _setup_screens_from_config(self, config_path):
        """
        从配置文件加载界面配置信息。
        :param config_path: 配置文件路径。
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                configs = json.load(file)
                for config in configs:
                    self._add_screen(config["id"], config["name"], config["image_path"], config["actions"])
        except FileNotFoundError:
            self.logger.error(f"配置文件不存在：{config_path}")
            raise
        except Exception as e:
            self.logger.error(f"配置文件解析失败：{e}")
            raise

    def _reset_screen_state(self):
        """
        重置当前界面状态。
        """
        self.current_screen = None
        self.current_screen_threshold = 0

    def _handle_autotry(self):
        """
        处理自动重试逻辑，包括按ESC键和处理特定的异常情况。
        """
        self.logger.warning("未识别出任何界面，请确保游戏画面干净，按ESC后重试")
        auto.press_key("esc")
        time.sleep(2)  # 等待屏幕变化

        auto.take_screenshot()
        # 处理与服务器断开连接的异常情况
        if auto.find_element("./assets/images/zh_CN/exception/relogin.png", "image", 0.9, take_screenshot=False):
            auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, take_screenshot=False)
            time.sleep(20)

        # 处理登录异常情况
        if auto.find_element("./assets/images/zh_CN/exception/retry.png", "image", 0.9, take_screenshot=False):
            auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, take_screenshot=False)
            time.sleep(20)

    def get_current_screen(self, autotry=True, max_retries=10):
        """
        通过多次尝试来识别并获取当前界面。
        :param autotry: 如果自动重试启用，则在未识别到界面时尝试按ESC键。
        :param max_retries: 最大重试次数。
        :return: 如果成功识别到界面则返回True，否则返回False。
        """

        # 定义内部函数用于在线程中识别界面
        def find_screen(screen_name, screen):
            try:
                result = auto.find_element(screen['image_path'], "image_threshold", 0.9, take_screenshot=False)
                if result:
                    with self.lock:
                        if not self.current_screen or self.current_screen_threshold < result:
                            self.current_screen = screen_name
                            self.current_screen_threshold = result
            except Exception as e:
                self.logger.debug(f"识别界面出错：{e}")

        if self.current_screen is not None and auto.find_element(self.screen_map[self.current_screen]['image_path'], "image_threshold", 0.9):
            return True

        for i in range(max_retries):
            auto.take_screenshot()
            self._reset_screen_state()

            threads = [threading.Thread(target=find_screen, args=(name, screen)) for name, screen in self.screen_map.items()]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            if self.current_screen:
                return True

            if autotry:
                self._handle_autotry()
            else:
                self.logger.debug("未识别出任何界面，请确保游戏画面干净")
                break

        self.logger.error("当前界面：未知")
        return False

    def find_shortest_path(self, start, end):
        """
        使用宽度优先搜索（BFS）算法在界面图中查找从 start 到 end 的最短路径。
        :param start: 起始界面的ID。
        :param end: 目标界面的ID。
        :return: 最短路径列表，格式为界面的ID列表。如果不存在路径，则返回 None。
        """
        if start == end:
            # 如果起始界面和目标界面相同，直接返回目标界面
            return [end]

        visited = set()  # 用于记录已访问的界面
        queue = deque([(start, [])])  # 队列中存储的元素为(当前界面, 到达当前界面的路径列表)

        while queue:
            current_screen, path = queue.popleft()  # 取出队列中的第一个元素
            visited.add(current_screen)  # 标记当前界面为已访问

            for action in self.screen_map[current_screen]['actions']:
                next_screen = action["target_screen"]
                if next_screen not in visited:
                    new_path = path + [current_screen]  # 更新路径
                    if next_screen == end:
                        # 如果找到目标界面，返回包含目标界面的完整路径
                        return new_path + [end]
                    queue.append((next_screen, new_path))  # 将下一个界面及其路径加入队列

        # 如果遍历完所有可能的路径都没有找到目标界面，返回 None
        return None

    def get_name(self, id):
        """
        根据界面ID获取界面名称。
        :param id: 界面的唯一标识。
        :return: 界面的名称。
        """
        return self.screen_map[id]["name"]

    def check_screen(self, target_screen):
        """
        检查当前界面是否是指定的目标界面。

        :param target_screen: 目标界面的标识符。
        :return: 如果当前界面是目标界面，则返回True；否则返回False。
        """
        if auto.find_element(self.screen_map[target_screen]['image_path'], "image", 0.9):
            # 如果找到了目标界面的图像，则更新当前界面状态为目标界面
            self.current_screen = target_screen
            return True
        return False

    def log_and_raise(self, log_message, error_message):
        """
        记录错误日志并抛出异常
        """
        self.logger.error(log_message)
        self.logger.error("如果游戏是从本地启动：")
        self.logger.error("请确保游戏画面干净，关闭帧率监控HUD、网速监控等一切可能影响游戏界面截图的组件")
        self.logger.error("如果是多显示器，游戏需要放在主显示器运行，且不支持HDR或游戏滤镜")
        self.logger.error("如果是云·星穹铁道：")
        self.logger.error("请确保网络正常，浏览器能正常加载游戏画面")
        raise Exception(error_message)

    def ensure_current_screen_is_clean(self):
        """
        确保当前游戏界面可以被正确识别
        """
        if not self.get_current_screen():
            self.log_and_raise("无法识别当前游戏界面", "无法识别当前游戏界面")

    def get_operations(self, current_screen, next_screen):
        """
        获取从当前界面到下一个界面的操作序列
        """
        return [action["actions_list"] for action in self.screen_map[current_screen]['actions'] if action["target_screen"] == next_screen][0]

    def perform_operations(self, operations):
        """
        执行一系列操作，每个操作是一个可执行的函数调用字符串
        :param operations: 包含可执行函数调用的字符串列表
        """
        for operation_str in operations:
            try:
                # 使用eval执行字符串表示的函数调用，提供配置变量的访问
                eval(
                    operation_str,
                    {
                        "__builtins__": __builtins__,
                        "auto": auto,
                        "time": time,
                        "cfg": cfg,
                    },
                )
                self.logger.debug("执行了一个操作")
            except Exception as e:
                self.logger.debug(f"未知的操作: {e}")

    def wait_for_screen_change(self, next_screen, max_recursion=2):
        """
        等待界面切换，如果未成功则根据重试次数决定是否重试
        """
        for _ in range(20):
            self.logger.debug(f"等待：{self.get_name(next_screen)}")
            if self.check_screen(next_screen):
                self.logger.info(f"切换到：{green(self.get_name(next_screen))}")
                time.sleep(self.wait_screen_change_time)
                break
            time.sleep(0.5)
        else:
            self.wait_screen_change_time = 1
            if max_recursion > 0:
                self.logger.warning(f"切换到 {self.get_name(next_screen)} 超时，准备重试")
                self.change_to(next_screen, max_recursion=max_recursion - 1)
            else:
                self.log_and_raise(f"无法切换到 {self.get_name(next_screen)}", "无法切换到指定游戏界面")

    def _switch_screen(self, current_screen, next_screen, max_recursion):
        """
        执行从当前界面到下一个界面的切换操作，并处理重试逻辑
        """
        operations = self.get_operations(current_screen, next_screen)
        self.perform_operations(operations)
        self.wait_for_screen_change(next_screen, max_recursion)

    def _navigate_through_path(self, path, max_recursion):
        """
        沿着找到的路径导航，执行切换操作
        """
        count = len(path) - 1
        if count:
            self.logger.info(f"当前界面：{green(self.get_name(self.current_screen))}")
            for i in range(count):
                self._switch_screen(path[i], path[i + 1], max_recursion)

    def change_to(self, target_screen, max_recursion=2):
        """
        切换到目标界面，，如果失败则退出进程
        :param target_screen: 目标界面
        :param max_recursion: 重试次数
        """

        self.ensure_current_screen_is_clean()

        path = self.find_shortest_path(self.current_screen, target_screen)
        if not path:
            self.log_and_raise(f"无法从 {self.get_name(self.current_screen)} 切换到 {self.get_name(target_screen)}", "无法切换到指定游戏界面")

        self._navigate_through_path(path, max_recursion)
        self.current_screen = target_screen

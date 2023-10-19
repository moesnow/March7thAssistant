from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
from collections import deque
import threading
import time
import json
import sys


class Screen:
    def __init__(self, config_path):
        self.current_screen = None
        self.screen_map = {}
        self.lock = threading.Lock()  # 创建一个锁，用于线程同步
        self._setup_screens_from_config(config_path)
        self.green = "\033[92m"
        self.reset = "\033[0m"

    def _setup_screens_from_config(self, config_path):
        """
        从配置文件路径中获取界面配置信息，并添加到界面管理器
        :param config_path: 配置文件路径
        """

        def add_screen(self, id, name, image_path, actions):
            """
            添加一个新界面到界面管理器，并指定其识别图片路径、可切换的目标界面及操作序列
            :param id: 新界面的唯一标识
            :param name: 新界面的名称
            :param image_path: 用于识别界面的图片路径
            :param actions: 可切换的目标界面及操作序列
            """
            self.screen_map[id] = {'name': name, 'image_path': image_path, 'actions': actions}

        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                for config in json.load(file):
                    id = config["id"]
                    name = config["name"]
                    image_path = config["image_path"]
                    actions = config["actions"]
                    add_screen(self, id, name, image_path, actions)
        except FileNotFoundError:
            logger.error(_("配置文件不存在：{path}").format(path=config_path))
            input(_("按回车键关闭窗口. . ."))
            sys.exit(1)
        except Exception as e:
            logger.error(_("配置文件解析失败：{e}").format(e=e))
            input(_("按回车键关闭窗口. . ."))
            sys.exit(1)

    def get_name(self, id):
        return self.screen_map[id]["name"]

    def find_shortest_path(self, start, end):
        """
        在界面图中查找从 start 到 end 的最短路径
        :param start: 起始界面
        :param end: 目标界面
        :return: 找到的最短路径列表，如果不存在则返回 None
        """
        if start == end:
            return [end]

        visited = set()
        queue = deque([(start, [])])  # 每个元素为 (当前界面, 到达当前界面的路径)

        while queue:
            current_screen, path = queue.popleft()
            visited.add(current_screen)

            for action in self.screen_map[current_screen]['actions']:
                next_screen = action["target_screen"]
                if next_screen not in visited:
                    new_path = path + [current_screen]
                    if next_screen == end:
                        return new_path + [end]
                    queue.append((next_screen, new_path))

        return None

    def perform_operations(self, operations):
        """
        执行一系列操作，包括按键操作和鼠标点击操作
        :param operations: 操作序列，每个操作是一个元组 (函数名, 参数)
        """
        def parse_args(args):
            parsed_args = []
            kwargs = {}
            for arg in args:
                if isinstance(arg, str):
                    if "=" in arg:
                        key, value = arg.split("=")
                        kwargs[key] = eval(value)
                        continue
                parsed_args.append(arg)
            return parsed_args, kwargs

        for operation in operations:
            function_name = operation["action"]
            args = operation["args"]
            parsed_args, kwargs = parse_args(args)
            if hasattr(self, function_name):
                func = getattr(self, function_name)
                func(*parsed_args, **kwargs)
                logger.debug(_("执行了一个操作"))
            else:
                module_name, method_name = function_name.split('.')
                module = globals().get(module_name)
                if module and hasattr(module, method_name):
                    method = getattr(module, method_name)
                    method(*parsed_args, **kwargs)
                    logger.debug(_("执行了一个操作"))
                else:
                    logger.debug(_("未知的操作: {function_name}").format(function_name=function_name))

    def get_current_screen(self, autotry=True, max_retries=10):
        """
        获取当前界面
        :param autotry: 未识别出任何界面自动按ESC
        :param max_retries: 重试次数
        :return: True，如果查找失败则返回 False
        """

        def find_screen(self, screen_name, screen):
            try:
                if auto.find_element(screen['image_path'], "image", 0.9, take_screenshot=False):
                    with self.lock:  # 使用锁来保护对共享变量的访问
                        self.current_screen = screen_name
            except Exception as e:
                logger.debug(_("识别界面出错：{e}").format(e=e))

        for i in range(max_retries):
            auto.take_screenshot()
            self.current_screen = None

            threads = []
            for screen_name, screen in self.screen_map.items():
                thread = threading.Thread(target=find_screen, args=(self, screen_name, screen))
                threads.append(thread)
                thread.start()
            for thread in threads:
                thread.join()

            if self.current_screen:
                logger.info(_("当前界面：{screen_name}").format(screen_name=self.green + self.get_name(self.current_screen) + self.reset))
                return True

            if autotry:
                logger.warning(_("未识别出任何界面，请确保游戏画面干净，按ESC后重试"))
                auto.press_key("esc")
                time.sleep(1)
            else:
                logger.debug(_("未识别出任何界面，请确保游戏画面干净"))
                break
        logger.error(_("当前界面：未知"))
        return False

    def check_screen(self, target_screen):
        if auto.find_element(self.screen_map[target_screen]['image_path'], "image", 0.9):
            self.current_screen = target_screen
            return True
        return False

    def change_to(self, target_screen, max_recursion=2):
        """
        切换到目标界面，，如果失败则退出进程
        :param target_screen: 目标界面
        :param max_recursion: 重试次数
        """
        if self.check_screen(target_screen):
            logger.debug(_("已经在 {target_screen} 界面").format(target_screen=self.get_name(target_screen)))
            return

        if not self.get_current_screen():
            logger.info(_("请确保游戏画面干净，关闭帧率监控HUD、网速监控等一切可能影响游戏界面截图的组件"))
            logger.info(_("如果是多显示器，游戏需要放在主显示器运行，且不支持HDR"))
            input(_("按回车键关闭窗口. . ."))
            sys.exit(1)

        path = self.find_shortest_path(self.current_screen, target_screen)
        if path:
            for i in range(len(path) - 1):
                current_screen = path[i]
                next_screen = path[i + 1]

                operations = [action["actions_list"]
                              for action in self.screen_map[current_screen]['actions']
                              if action["target_screen"] == next_screen][0]
                self.perform_operations(operations)

                for i in range(20):
                    logger.debug(_("等待：{next_screen}").format(next_screen=self.get_name(next_screen)))
                    if self.check_screen(next_screen):
                        break
                    else:
                        time.sleep(1)

                if self.current_screen != next_screen:
                    if max_recursion > 0:
                        logger.warning(_("切换到 {next_screen} 超时，准备重试").format(next_screen=self.get_name(next_screen)))
                        self.change_to(next_screen, max_recursion=max_recursion - 1)
                    else:
                        logger.error(_("无法切换到 {next_screen}").format(next_screen=self.get_name(next_screen)))
                        logger.info(_("请确保游戏画面干净，关闭帧率监控HUD、网速监控等一切可能影响游戏界面截图的组件"))
                        logger.info(_("如果是多显示器，游戏需要放在主显示器运行，且不支持HDR"))
                        input(_("按回车键关闭窗口. . ."))
                        sys.exit(1)

                logger.info(_("切换到：{next_screen}").format(next_screen=self.green + self.get_name(next_screen) + self.reset))
                time.sleep(1)
            self.current_screen = target_screen  # 更新当前界面
            return

        logger.debug(_("无法从 {current_screen} 切换到 {target_screen}").format(
            current_screen=self.get_name(self.current_screen), target_screen=self.get_name(target_screen)))
        input(_("按回车键关闭窗口. . ."))
        sys.exit(1)

from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
from collections import deque
import threading
import time
import json


class Screen:
    def __init__(self, config_path):
        self.current_screen = None
        self.screen_map = {}
        self.lock = threading.Lock()  # 创建一个锁，用于线程同步
        self.setup_screens_from_config(config_path)

    def add_screen(self, name, image_path, actions):
        """
        添加一个新界面到界面管理器，并指定其识别图片路径、可切换的目标界面及操作序列
        :param name: 新界面的名称
        :param image_path: 用于识别界面的图片路径
        :param actions: 可切换的目标界面及操作序列
        """
        self.screen_map[name] = {'image_path': image_path, 'actions': actions}

    def setup_screens_from_config(self, config_path):
        with open(config_path, 'r', encoding='utf-8') as file:
            screens_config = json.load(file)

        for screen_config in screens_config["screens"]:
            name = screen_config["name"]
            image_path = screen_config["image_path"]
            actions = screen_config["actions"]
            self.add_screen(name, image_path, actions)

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

    def parse_args(self, args):
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

    def perform_operations(self, operations):
        """
        执行一系列操作，包括按键操作和鼠标点击操作
        :param operations: 操作序列，每个操作是一个元组 (函数名, 参数)
        """
        for operation in operations:
            function_name = operation["action"]
            args = operation["args"]
            parsed_args, kwargs = self.parse_args(args)
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

    def change_to(self, target_screen, max_retries=10, max_recursion=3):
        # self.get_current_screen()
        self.display_current_screen()
        if target_screen == self.current_screen:
            # logger.debug(_("already on {target_screen}").format(target_screen=target_screen))
            logger.debug(_("已经在 {target_screen} 界面").format(target_screen=target_screen))
            return True
        path = self.find_shortest_path(self.current_screen, target_screen)
        if path:
            for i in range(len(path) - 1):
                current_screen = path[i]
                next_screen = path[i + 1]

                operations = [action["actions_list"]
                              for action in self.screen_map[current_screen]['actions'] if action["target_screen"] == next_screen][0]
                self.perform_operations(operations)
                time.sleep(1)

                for i in range(max_retries):
                    if self.check_screen(next_screen):
                        break
                    logger.debug(_("继续等待 {next_screen}").format(next_screen=next_screen))
                    # logger.debug(_("keep waiting for {next_screen}").format(next_screen=next_screen))

                if self.current_screen != next_screen:
                    if max_recursion > 0:
                        self.change_to(next_screen, max_recursion=max_recursion - 1)
                    else:
                        logger.debug(_("无法切换到 {next_screen}"))
                        # logger.debug(_("cannot change to {next_screen}"))
                        break
                # logger.debug(_("change to {next_screen}").format(next_screen=next_screen))
                logger.debug(_("切换到 {next_screen}").format(next_screen=next_screen))
            self.current_screen = target_screen  # 更新当前界面
            # logger.debug(_("current screen: {current_screen}").format(current_screen=self.current_screen))
            logger.debug(_("当前界面：{current_screen}").format(current_screen=self.current_screen))
            return True
        logger.debug(_("无法从 {current_screen} 切换到 {target_screen}").format(current_screen=self.get_current_screen(), target_screen=target_screen))
        return False
        # logger.debug(_("cannot change from {current_screen} to {target_screen}").format(current_screen=self.get_current_screen(), target_screen=target_screen))

    def check_screen(self, target_screen):
        if auto.find_element(self.screen_map[target_screen]['image_path'], "image", 0.9):
            self.current_screen = target_screen
            return True
        return False

    def display_current_screen(self):
        if self.get_current_screen():
            # logger.debug(_("current screen: {current_screen}").format(current_screen=self.current_screen))
            logger.debug(_("当前界面：{current_screen}").format(current_screen=self.current_screen))
            return
        logger.debug(_("当前界面：未知"))
        # logger.debug(_("current screen: unknown"))

    def find_screen(self, screen_name, screen):
        # logger.debug(f"对比图片 {screen_name}")
        try:
            if auto.find_element(screen['image_path'], "image", 0.9, take_screenshot=False):
                with self.lock:  # 使用锁来保护对共享变量的访问
                    self.current_screen = screen_name
                    logger.debug(_("{screen_name} 匹配成功").format(screen_name=screen_name))
                    # logger.debug(_("{screen_name} matched successfully").format(screen_name=screen_name))
                return True
            # logger.debug(f"{screen_name} 匹配失败")
        except Exception as e:
            logger.debug(_("查找界面出错：{e}").format(e=e))
        return False

    def get_current_screen(self, max_retries=10):
        for i in range(max_retries):
            auto.take_screenshot()
            # logger.debug("截图完成")
            # logger.debug("screenshot complete")
            threads = []
            self.current_screen = None
            for screen_name, screen in self.screen_map.items():
                thread = threading.Thread(target=self.find_screen, args=(screen_name, screen))
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            if self.current_screen is not None:
                return True
            logger.debug(_("没找到任何界面，按ESC后重试"))
            # logger.debug(_("no screen found, press ESC to retry"))
            auto.press_key("esc")
            time.sleep(1)
        return False

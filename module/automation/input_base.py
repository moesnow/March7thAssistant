from abc import ABC, abstractmethod

class InputBase(ABC):

    @abstractmethod
    def mouse_click(self, x, y):
        '''在屏幕上的（x，y）位置执行鼠标点击操作'''
        pass

    @abstractmethod
    def mouse_down(self, x, y):
        '''在屏幕上的（x，y）位置按下鼠标按钮'''
        pass

    @abstractmethod
    def mouse_up(self):
        '''释放鼠标按钮'''
        pass

    @abstractmethod
    def mouse_move(self, x, y):
        '''将鼠标光标移动到屏幕上的（x，y）位置'''
        pass

    @abstractmethod
    def mouse_scroll(self, count, direction=-1, pause=True):
        '''滚动鼠标滚轮，方向和次数由参数指定'''
        pass

    @abstractmethod
    def press_key(self, key, wait_time=0.2):
        '''模拟键盘按键，可以指定按下的时间'''
        pass

    @abstractmethod
    def secretly_press_key(self, key, wait_time=0.2):
        '''(不输出具体键位)模拟键盘按键，可以指定按下的时间'''
        pass

    @abstractmethod
    def press_mouse(self, wait_time=0.2):
        '''模拟鼠标左键的点击操作，可以指定按下的时间'''
        pass

    @abstractmethod
    def secretly_write(self, text, interval = 0.1):
        '''模拟键盘输入字符串，可以指定字符输入间隔'''
        pass
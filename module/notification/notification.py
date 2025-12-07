import io
from PIL import Image
from typing import Optional
from utils.logger.logger import Logger
from utils.singleton import SingletonMeta
from .notifier import Notifier


class NotificationLevel:
    """
    通知级别常量定义，用于对通知进行分级。
    """
    ALL = "all"  # 所有通知
    ERROR = "error"  # 仅错误和异常通知
    # 用于展示的中文本地化名称
    DISPLAY = {
        ALL: "全部",
        ERROR: "仅错误",
    }


class Notification(metaclass=SingletonMeta):
    """
    通知管理类，负责管理和发送不同类型的通知。
    """

    def __init__(self, title: str, logger: Optional[Logger] = None):
        """
        初始化通知管理类。

        :param title: 通知标题。
        :param logger: 用于记录日志的Logger对象，可选。
        """
        self.title = title
        self.logger = logger
        self.notifiers = {}  # 存储不同类型的通知发送者实例
        self.level_filter = NotificationLevel.ALL  # 默认发送所有通知

    def _localize_level(self, level: Optional[str]) -> str:
        """
        将内部级别常量转换为对用户友好的中文描述。

        :param level: 内部级别字符串（例如 'all' 或 'error'）
        :return: 中文描述（如果找不到对应项则返回原始值或空串）
        """
        if level is None:
            return ""
        return NotificationLevel.DISPLAY.get(level, str(level))

    def set_notifier(self, notifier_name: str, notifier: Notifier):
        """
        设置或更新一个通知发送者实例。

        :param notifier_name: 通知发送者的名称。
        :param notifier: 通知发送者的实例，应当实现Notifier接口。
        """
        self.notifiers[notifier_name] = notifier

    def set_level_filter(self, level: str):
        """
        设置通知级别过滤器。

        :param level: 通知级别，应为 NotificationLevel 中定义的常量。
        :raises ValueError: 如果提供的级别不是有效的 NotificationLevel 常量。
        """
        if level not in [NotificationLevel.ALL, NotificationLevel.ERROR]:
            allowed = (
                f"{NotificationLevel.ALL}（{self._localize_level(NotificationLevel.ALL)}）",
                f"{NotificationLevel.ERROR}（{self._localize_level(NotificationLevel.ERROR)}）",
            )
            raise ValueError(f"无效的通知级别: {level}. 可选值: {allowed[0]} 或 {allowed[1]}")
        self.level_filter = level

    def _process_image(self, image: Optional[io.BytesIO | str | Image.Image], max_size: tuple = (1920, 1080), quality: int = 85) -> Optional[io.BytesIO]:
        """
        根据image的类型处理图片，并进行压缩优化，确保它是io.BytesIO对象。

        :param image: 可以是io.BytesIO对象、文件路径字符串或PIL.Image对象，可选。
        :param max_size: 图片最大尺寸(宽, 高)，默认1920x1080。
        :param quality: JPEG压缩质量，范围1-95，默认85。
        :return: io.BytesIO对象或None（如果image为None或处理失败）。
        """
        pil_image = None

        # 第一步：将所有类型转换为PIL.Image对象
        if isinstance(image, str):
            try:
                pil_image = Image.open(image)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"图片读取失败: {e}")
                return None
        elif isinstance(image, io.BytesIO):
            try:
                image.seek(0)
                pil_image = Image.open(image)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"图片解析失败: {e}")
                return None
        elif isinstance(image, Image.Image):
            pil_image = image
        else:
            return None

        # 第二步：压缩处理
        try:
            # 转换为RGB模式（JPEG不支持透明通道）
            if pil_image.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', pil_image.size, (255, 255, 255))
                if pil_image.mode == 'P':
                    pil_image = pil_image.convert('RGBA')
                background.paste(pil_image, mask=pil_image.split()[-1] if pil_image.mode in ('RGBA', 'LA') else None)
                pil_image = background
            elif pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')

            # 调整图片尺寸（如果超过最大尺寸）
            if pil_image.width > max_size[0] or pil_image.height > max_size[1]:
                pil_image.thumbnail(max_size, Image.Resampling.LANCZOS)
                if self.logger:
                    self.logger.info(f"图片已调整大小至: {pil_image.size}")

            # 保存为压缩后的JPEG格式
            img_byte_arr = io.BytesIO()
            pil_image.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
            img_byte_arr.seek(0)

            # 记录压缩后的大小
            compressed_size = img_byte_arr.getbuffer().nbytes
            if self.logger:
                self.logger.info(f"图片压缩完成，大小: {compressed_size / 1024:.2f} KB")

            return img_byte_arr
        except Exception as e:
            if self.logger:
                self.logger.error(f"图片压缩失败: {e}")
            return None

    def notify(self, content: str = "", image: Optional[io.BytesIO | str] = None, level: str = NotificationLevel.ALL):
        """
        遍历所有设置的通知发送者，发送通知。

        :param content: 通知的内容。
        :param image: 通知的图片，可以是io.BytesIO对象或文件路径字符串，可选。
        :param level: 通知级别，默认为 ALL。当 level_filter 为 ERROR 时，只有 ERROR 级别的通知会被发送。
        """
        # 检查是否应该发送此通知
        if self.level_filter == NotificationLevel.ERROR and level != NotificationLevel.ERROR:
            if self.logger:
                localized_level = self._localize_level(level)
                localized_filter = self._localize_level(self.level_filter)
                self.logger.info(f"通知被过滤（级别：{localized_level}，过滤器：{localized_filter}）")
                self.logger.info(f"内容: {content}")
            return

        for notifier_name, notifier in self.notifiers.items():
            processed_image = self._process_image(image)  # 根据image的类型进行处理
            try:
                if processed_image and notifier.supports_image:
                    notifier.send(self.title, content, processed_image)
                else:
                    notifier.send(self.title, content)
                if self.logger:
                    self.logger.info(f"{notifier_name} 通知发送完成")
            except Exception as e:
                if self.logger:
                    self.logger.error(f"{notifier_name} 通知发送失败: {e}")

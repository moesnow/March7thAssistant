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
        self.image_enable = True  # 是否在推送消息时发送图片
        self._batch_mode = False  # 是否处于合并通知模式
        self._batch_messages = []  # 合并模式下收集的通知内容
        self._batch_images = []  # 合并模式下收集的图片
        self._batch_has_error = False  # 合并模式下是否包含错误级别通知

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

    def _has_image_notifier(self) -> bool:
        """
        判断当前已启用的通知发送者中，是否存在支持图片的渠道。

        :return: 存在支持图片的通知器时返回True，否则返回False。
        """
        return any(notifier.supports_image for notifier in self.notifiers.values())

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

    def set_image_enable(self, enable: bool):
        """
        设置是否在推送消息时发送图片。

        :param enable: True 发送图片，False 不发送图片。
        """
        self.image_enable = enable

    def start_batch(self):
        """
        开启通知合并模式。在此模式下，notify() 调用不会立即发送通知，
        而是将内容收集起来，等待 flush_batch() 时合并为一条通知发送。
        """
        self._batch_mode = True
        self._batch_messages = []
        self._batch_images = []
        self._batch_has_error = False

    def flush_batch(self, extra_content: str = "", level: str = NotificationLevel.ALL):
        """
        结束通知合并模式并发送合并后的通知。

        :param extra_content: 额外的内容，追加到合并通知的末尾（如最终状态信息）。
        :param level: 额外内容的通知级别，默认为 ALL。
        """
        was_batching = self._batch_mode
        self._batch_mode = False
        messages = self._batch_messages
        images = self._batch_images
        has_error = self._batch_has_error
        self._batch_messages = []
        self._batch_images = []
        self._batch_has_error = False

        image_supported = self.image_enable and self._has_image_notifier()
        merged_image = self._merge_images(images) if image_supported and images else None
        # 合并图片仅限制宽度，不限制高度，以保留长截图完整内容
        if merged_image is not None:
            merged_image = self._process_image(merged_image, max_size=None)

        if was_batching and (messages or extra_content):
            merged_items = list(messages)
            if extra_content:
                merged_items.append(extra_content)
            numbered = [f"{i}. {msg}" for i, msg in enumerate(merged_items, 1)]
            merged = "\n".join(numbered)
            batch_level = NotificationLevel.ERROR if has_error else level
            self.notify(content=merged, image=merged_image, level=batch_level, _image_already_processed=True)
        elif extra_content:
            self.notify(content=extra_content, image=merged_image, level=level, _image_already_processed=True)

    def _to_pil_image(self, image: Optional[io.BytesIO | str | Image.Image]) -> Optional[Image.Image]:
        """
        将各种类型的图片转换为PIL.Image对象。

        :param image: 可以是io.BytesIO对象、文件路径字符串或PIL.Image对象，可选。
        :return: PIL.Image对象或None。
        """
        if isinstance(image, str):
            try:
                return Image.open(image)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"图片读取失败: {e}")
                return None
        elif isinstance(image, io.BytesIO):
            try:
                image.seek(0)
                return Image.open(image)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"图片解析失败: {e}")
                return None
        elif isinstance(image, Image.Image):
            return image
        return None

    def _get_processed_image(self, image: Optional[io.BytesIO | str | Image.Image], image_already_processed: bool = False) -> Optional[io.BytesIO | str | Image.Image]:
        """
        仅在存在已启用且支持图片的通知器时处理图片，避免无意义的压缩。

        :param image: 原始图片对象。
        :param image_already_processed: 图片是否已完成处理。
        :return: 处理后的图片对象，或None。
        """
        if image is None or not self.image_enable or not self._has_image_notifier():
            return None
        if image_already_processed:
            return image
        return self._process_image(image)

    def _merge_images(self, images: list) -> Optional[Image.Image]:
        """
        将多张图片垂直合并为一张长截图。
        按照所有图片中最大的宽度进行等比缩放后再拼接。

        :param images: 图片列表，每项可以是io.BytesIO、文件路径或PIL.Image。
        :return: 合并后的PIL.Image对象，或None。
        """
        pil_images = []
        for img in images:
            pil = self._to_pil_image(img)
            if pil is not None:
                pil_images.append(pil)
        if not pil_images:
            return None
        if len(pil_images) == 1:
            return pil_images[0]

        try:
            max_width = max(img.width for img in pil_images)
            resized = []
            for img in pil_images:
                if img.width != max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                resized.append(img)

            total_height = sum(img.height for img in resized)
            merged = Image.new('RGB', (max_width, total_height), (255, 255, 255))
            y_offset = 0
            for img in resized:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                merged.paste(img, (0, y_offset))
                y_offset += img.height

            if self.logger:
                self.logger.debug(f"图片合并完成，共 {len(resized)} 张，尺寸: {merged.size}")
            return merged
        except Exception as e:
            if self.logger:
                self.logger.error(f"图片合并失败: {e}")
            return None

    def _process_image(self, image: Optional[io.BytesIO | str | Image.Image], max_size: tuple = (1920, 1080), quality: int = 85) -> Optional[io.BytesIO]:
        """
        根据image的类型处理图片，并进行压缩优化，确保它是io.BytesIO对象。

        :param image: 可以是io.BytesIO对象、文件路径字符串或PIL.Image对象，可选。
        :param max_size: 图片最大尺寸(宽, 高)，默认1920x1080。传入None则不限制尺寸。
        :param quality: JPEG压缩质量，范围1-95，默认85。
        :return: io.BytesIO对象或None（如果image为None或处理失败）。
        """
        pil_image = self._to_pil_image(image)
        if pil_image is None:
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
            if max_size and (pil_image.width > max_size[0] or pil_image.height > max_size[1]):
                pil_image.thumbnail(max_size, Image.Resampling.LANCZOS)
                if self.logger:
                    self.logger.debug(f"图片已调整大小至: {pil_image.size}")

            # 保存为压缩后的JPEG格式
            img_byte_arr = io.BytesIO()
            pil_image.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
            img_byte_arr.seek(0)

            # 记录压缩后的大小
            compressed_size = img_byte_arr.getbuffer().nbytes
            if self.logger:
                self.logger.debug(f"图片压缩完成，大小: {compressed_size / 1024:.2f} KB")

            return img_byte_arr
        except Exception as e:
            if self.logger:
                self.logger.error(f"图片压缩失败: {e}")
            return None

    def notify(self, content: str = "", image: Optional[io.BytesIO | str] = None, level: str = NotificationLevel.ALL, _image_already_processed: bool = False):
        """
        遍历所有设置的通知发送者，发送通知。

        :param content: 通知的内容。
        :param image: 通知的图片，可以是io.BytesIO对象或文件路径字符串，可选。
        :param level: 通知级别，默认为 ALL。当 level_filter 为 ERROR 时，只有 ERROR 级别的通知会被发送。
        :param _image_already_processed: 内部参数，标记图片是否已经过处理，避免重复压缩。
        """
        # 合并通知模式：收集内容而不立即发送
        if self._batch_mode:
            if content:
                self._batch_messages.append(content)
            if image is not None:
                self._batch_images.append(image)
            if level == NotificationLevel.ERROR:
                self._batch_has_error = True
            return

        # 检查是否应该发送此通知
        if self.level_filter == NotificationLevel.ERROR and level != NotificationLevel.ERROR:
            if self.logger:
                localized_level = self._localize_level(level)
                localized_filter = self._localize_level(self.level_filter)
                self.logger.info(f"通知被过滤（级别：{localized_level}，过滤器：{localized_filter}）")
                self.logger.info(f"内容: {content}")
            return

        processed_image = self._get_processed_image(image, _image_already_processed)

        for notifier_name, notifier in self.notifiers.items():
            try:
                will_send_image = bool(processed_image and notifier.supports_image)
                if self.logger:
                    self.logger.info(
                        f"准备发送 {notifier_name} 通知（级别：{self._localize_level(level)}，图片：{'是' if will_send_image else '否'}）"
                    )
                if processed_image and notifier.supports_image:
                    if isinstance(processed_image, io.BytesIO):
                        processed_image.seek(0)
                    notifier.send(self.title, content, processed_image)
                else:
                    notifier.send(self.title, content)
                if self.logger:
                    self.logger.info(f"{notifier_name} 通知发送完成")
            except Exception as e:
                if self.logger:
                    self.logger.error(f"{notifier_name} 通知发送失败: {e}")

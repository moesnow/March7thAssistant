from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import QThread, pyqtSignal
from ..card.messagebox_custom import MessageBoxAnnouncement
from module.config import cfg
from io import BytesIO
from enum import Enum
import requests
import qrcode


def download_image(image_url):
    response = requests.get(image_url)
    if response.status_code == 200:
        return QImage.fromData(response.content)
    else:
        raise Exception("Failed to download image.")


def generate_qr_code(url):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=7,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    return QImage.fromData(img_byte_arr)


class AnnouncementStatus(Enum):
    SUCCESS = 1
    UPDATE_AVAILABLE = 2
    FAILURE = 0


class AnnouncementThread(QThread):
    announcementSignal = pyqtSignal(AnnouncementStatus)

    def __init__(self):
        super().__init__()
        self.title = ""
        self.content = ""
        self.image = None

    def run(self):
        try:
            url = "https://api.kotori.top/moesnow/March7thAssistant/announcement.json"
            response = requests.get(url, headers=cfg.useragent)
            response.raise_for_status()

            data = response.json()
            if not data['hasAnnouncement']:
                return

            announcement = data['announcement']

            self.title = announcement['title']
            self.content = announcement['content']
            if 'image' in announcement and announcement['image']:
                image = announcement['image']
                image_type = image['type']
                image_url = image['url']

                if image_type == "qrCode":
                    qimage = generate_qr_code(image_url)
                elif image_type == "normal":
                    qimage = download_image(image_url)
                else:
                    raise ValueError("Invalid image type.")
                self.image = QPixmap.fromImage(qimage)

            self.announcementSignal.emit(AnnouncementStatus.SUCCESS)
        except:
            return


def checkAnnouncement(self):
    def handle_announcement(status):
        if status == AnnouncementStatus.SUCCESS:
            message_box = MessageBoxAnnouncement(
                self.announcement_thread.title,
                self.announcement_thread.content,
                self.announcement_thread.image,
                self.window()
            )
            message_box.exec()

    self.announcement_thread = AnnouncementThread()
    self.announcement_thread.announcementSignal.connect(handle_announcement)
    self.announcement_thread.start()

import base64

import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import requests
from onepush import get_notifier
from managers.logger_manager import logger
from managers.translate_manager import _
from ruamel.yaml import comments

class Notify:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.notifiers = {
                "winotify": False,
                "bark": False,
                "custom": False,
                "gocqhttp": False,
                "gotify": False,
                "dingtalk": False,
                "discord": False,
                "pushplus": False,
                "pushdeer": False,
                "qmsg": False,
                "serverchan": False,
                "serverchanturbo": False,
                "smtp": False,
                "telegram": False,
                "wechatworkapp": False,
                "wechatworkbot": False,
                "lark": False
            }
        return cls._instance

    def set_notifier(self, notifier_name, enable, params=None):
        self.notifiers[notifier_name] = enable

        if params:
            setattr(self, notifier_name, params)

    def _send_notification(self, notifier_name, title, content):
        if self.notifiers.get(notifier_name, False):

            if notifier_name == "winotify":
                self._send_notification_by_winotify(title, content)
                return

            if notifier_name == "gotify":
                self._send_notification_by_gotify(title, content)
                return

            if notifier_name == "pushplus":
                content = '.' if content is None or content == '' else content

            notifier_params = getattr(self, notifier_name, None)
            if notifier_params:
                n = get_notifier(notifier_name)
                try:
                    response = n.notify(**notifier_params,
                                        title=title, content=content)
                    logger.info(_("{notifier_name} 通知发送完成").format(
                        notifier_name=notifier_name.capitalize()))
                except Exception as e:
                    logger.error(_("{notifier_name} 通知发送失败").format(
                        notifier_name=notifier_name.capitalize()))
                    logger.error(f"{e}")

    def _send_notification_with_image(self, notifier_name, title, content, image_io):
        if not self.notifiers.get(notifier_name, False):
            return

        if notifier_name == "telegram":
            notifier_params = getattr(self, notifier_name, None)
            if notifier_params:
                token = notifier_params["token"]
                chat_id = notifier_params["userid"]
                api_url = notifier_params["api_url"] if "api_url" in notifier_params else "api.telegram.org"
                tgurl = f"https://{api_url}/bot{token}/sendPhoto"
                message = content
                if title and content:
                    message = '{}\n\n{}'.format(title, content)
                if title and not content:
                    message = title
                files = {
                    'photo': ('merged_image.jpg', image_io.getvalue(), 'image/jpeg'),
                    'chat_id': (None, chat_id),
                    'caption': (None, message)
                    # 'text': (None, " ")
                }
                try:
                    response = requests.post(tgurl, files=files)
                    logger.info(_("{notifier_name} 通知发送完成").format(notifier_name=notifier_name.capitalize()))
                except Exception as e:
                    logger.error(_("{notifier_name} 通知发送失败").format(notifier_name=notifier_name.capitalize()))
                    logger.error(f"{e}")

        elif notifier_name == "gocqhttp":
            notifier_params = getattr(self, notifier_name, None)
            if notifier_params:
                n = get_notifier(notifier_name)
                base64_str = base64.b64encode(image_io.getvalue()).decode()
                cq_code = f"[CQ:image,file=base64://{base64_str}]"
                content = content + cq_code if content else cq_code
                try:
                    response = n.notify(**notifier_params, title=title, content=content)
                    logger.info(_("{notifier_name} 通知发送完成").format(notifier_name=notifier_name.capitalize()))
                except Exception as e:
                    logger.error(_("{notifier_name} 通知发送失败").format(notifier_name=notifier_name.capitalize()))
                    logger.error(f"{e}")

        elif notifier_name == "smtp":
            notifier_params = getattr(self, notifier_name, None)
            if notifier_params:
                host = notifier_params["host"]
                user = notifier_params["user"]
                password = notifier_params["password"]
                From = notifier_params["From"] if "From" in notifier_params else user
                To = notifier_params["To"] if "To" in notifier_params else user
                port = notifier_params["port"] if "port" in notifier_params else 465
                ssl = notifier_params["ssl"] if "ssl" in notifier_params else True
                msg = MIMEMultipart('related')
                boby = f'<p>{content}<br><img src="cid:image1"></br></p>'
                msg['Subject'] = Header(title, 'utf-8')
                msg['From'] = From
                receivers = To
                toclause = receivers.split(',')
                msg['To'] = ",".join(toclause)
                with open(r"./smtp_temp.bin", "wb") as file:
                    file.write(image_io.getvalue())
                f=open(r"./smtp_temp.bin", "rb")
                img_data = f.read()
                f.close()
                img = MIMEImage(img_data)
                img.add_header('Content-ID', f'<image1>') 
                msg.attach(img)
                msg.attach(MIMEText(boby, "html", "utf-8"))
                if ssl:
                    smtp = smtplib.SMTP_SSL(host, port)
                else:
                    smtp = smtplib.SMTP(host, port)
                smtp.login(user, password)
                try:
                    response = smtp.sendmail(From, toclause, msg.as_string())
                    smtp.quit()
                    logger.info(_("{notifier_name} 通知发送完成").format(notifier_name=notifier_name.capitalize()))
                except Exception as e:
                    logger.error(_("{notifier_name} 通知发送失败").format(notifier_name=notifier_name.capitalize()))
                    logger.error(f"{e}")

    def _send_notification_by_winotify(self, title, content):
        import os
        from winotify import Notification, audio

        message = content
        if title and content:
            message = '{}\n{}'.format(title, content)
        if title and not content:
            message = title

        toast = Notification(app_id="March7thAssistant",
                             title="三月七小助手|･ω･)",
                             msg=message,
                             icon=os.getcwd() + "\\assets\\app\\images\\March7th.jpg")
        toast.set_audio(audio.Mail, loop=False)
        toast.show()
        logger.info(_("{notifier_name} 通知发送完成").format(notifier_name="winotify"))

    def _send_notification_by_gotify(self, title, content):
        notifier_params = getattr(self, "gotify", None)
        if notifier_params:
            n = get_notifier("gotify")
            try:
                message = content
                response = n.notify(**notifier_params, title=title, message=message)
                logger.info(_("{notifier_name} 通知发送完成").format(notifier_name="gotify"))
            except Exception as e:
                logger.error(_("{notifier_name} 通知发送失败").format(notifier_name="gotify"))
                logger.error(f"{e}")

    def comment_init(self,d):
        try:
            if isinstance(d,comments.CommentedMap):
                d = dict(d)
                for k,v in d.items():
                    d[k] = self.comment_init(v)
            elif isinstance(d,comments.CommentedSeq):
                d = list(d)
                for i in d:
                    d[d.index(i)] = self.comment_init(i)
            return d
        except Exception as e:
            logger.error(e)
    
    def comment_format(self, d, *args, **kwargs):
        try:
            if isinstance(d,dict):
                for k, v in d.items():
                    if k in args:
                         v = v.format(**kwargs)
                    d[k] = self.comment_format(v,*args,**kwargs)
            elif isinstance(d,list):
                for i in d:
                    d[d.index(i)] = self.comment_format(i,*args,**kwargs)
            return d
        except Exception as e:
            logger.error(e)

    def _send_notification_by_custom(self,notifier_name,title,content,image_io):
        notifier_params = getattr(self, notifier_name, None)
        base64_str = base64.b64encode(image_io.getvalue()).decode()
        if notifier_params:
            n = get_notifier(notifier_name)
            # text = "text"
            # file = "file"
            if notifier_params["datatype"] == "json":
                raw_data = self.comment_init(notifier_params["data"])
                data = self.comment_format(raw_data,"text","file",title=title,content=content,image=base64_str)
                notifier_params["data"] = data
            try:
                response = n.notify(**notifier_params)
                logger.info(_("{notifier_name} 通知发送完成").format(notifier_name=notifier_name.capitalize()))
            except Exception as e:
                logger.error(_("{notifier_name} 通知发送失败").format(notifier_name=notifier_name.capitalize()))
                logger.error(f"{e}")



    def notify(self, title="", content="", image_io=None):
        for notifier_name in self.notifiers:
            if image_io and notifier_name in ["telegram", "gocqhttp", "smtp"]:
                self._send_notification_with_image(notifier_name, title, content, image_io)
            elif image_io and notifier_name == "custom":
                self._send_notification_by_custom(notifier_name, title, content, image_io)
            else:
                self._send_notification(notifier_name, title, content)

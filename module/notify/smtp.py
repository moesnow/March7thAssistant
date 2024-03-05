import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from .notifier import Notifier


class SMTPNotifier(Notifier):
    def _get_supports_image(self):
        return True

    def send(self, title: str, content: str, image_io=None):
        host = self.params["host"]
        user = self.params["user"]
        password = self.params["password"]
        From = self.params.get("From", user)
        To = self.params.get("To", user)
        port = self.params.get("port", 465)
        ssl = self.params.get("ssl", True)

        msg = MIMEMultipart('related')
        body = f'<p>{content}<br>'
        if image_io:
            body += '<img src="cid:image1">'
        body += '</br></p>'
        msg['Subject'] = Header(title, 'utf-8')
        msg['From'] = From
        msg['To'] = To
        if image_io:
            img = MIMEImage(image_io.getvalue())
            img.add_header('Content-ID', '<image1>')
            msg.attach(img)
        msg.attach(MIMEText(body, "html", "utf-8"))

        if ssl:
            smtp = smtplib.SMTP_SSL(host, port)
        else:
            smtp = smtplib.SMTP(host, port)
        smtp.login(user, password)
        smtp.sendmail(From, To, msg.as_string())
        smtp.quit()

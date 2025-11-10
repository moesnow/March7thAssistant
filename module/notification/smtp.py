import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from .notifier import Notifier
import ssl


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
        starttls = self.params.get("starttls", False)
        ssl_unverified = self.params.get("ssl_unverified", False)


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

        if starttls:
            smtp = smtplib.SMTP(host, port)
            smtp.starttls(context=sslcontext(ssl_unverified))
        elif ssl:
            smtp = smtplib.SMTP_SSL(host, port, context=sslcontext(ssl_unverified))
        else:
            smtp = smtplib.SMTP(host, port)
        if user != '':
            smtp.login(user, password)
        smtp.sendmail(From, To, msg.as_string())
        smtp.quit()

def sslcontext(ssl_unverified):
    if ssl_unverified:
        return ssl._create_unverified_context()
    return None

import smtplib
from typing import List
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
import ssl
from email.mime.base import MIMEBase
from email.utils import formatdate
from email import encoders
from datetime import datetime


class mailClient:
    def __init__(self, smtpconnection, username, password, fromAdd):
        self.server = smtpconnection
        self.login_un = username
        self.login_pw = password
        self.fromAdd = fromAdd

    def send_message(self, toAdd, subject, message):
        try:
            smtpObj = smtplib.SMTP(self.server, 25)
            # smtpObj.starttls()
            smtpObj.ehlo()
            # smtpObj.login(self.login_un, self.login_pw)
            compiledmessage = "Subject:" + subject + "\r\n\n" + message
            smtpObj.sendmail(self.fromAdd, toAdd, compiledmessage)
        except Exception as e:
            print(e)
        finally:
            smtpObj.quit()

    def send_HTML_message(self, toAdd, subject, body):
        try:
            smtpObj = smtplib.SMTP(self.server, 25)
            smtpObj.ehlo()
            message = MIMEMultipart()
            message['Subject'] = subject
            message['From'] = self.fromAdd
            message['To'] = toAdd
            body_content = body
            message.attach(MIMEText(body_content, "html"))
            msg_body = message.as_string()
            smtpObj.sendmail(message['From'], message['To'], msg_body)
        except Exception as e:
            print(e)
        finally:
            smtpObj.quit()

    def send_HTML_message_with_image(self, toAdd, subject, body, image_attachment = ""):
        #try:
            smtpObj = smtplib.SMTP(self.server, 25)
            smtpObj.ehlo()
            message = MIMEMultipart()
            message['Subject'] = subject
            message['From'] = self.fromAdd
            message['To'] = toAdd
            body_content = body
            message.attach(MIMEText(body_content, "html"))
            if image_attachment:
                with open(image_attachment, 'rb') as fp:
                    msgImage = MIMEImage(fp.read())
                msgImage.add_header('Content-ID', '<{}>'.format(image_attachment))
                message.attach(msgImage)
            msg_body = message.as_string()
            smtpObj.sendmail(message['From'], message['To'], msg_body)
        #except Exception as e:
            #print(e)
        #finally:
            #smtpObj.quit()

    def send_HTML_message_with_excel(self, toAdd, subject, body, urgency, projname, excel_attachment = ""):
        smtpObj = smtplib.SMTP(self.server, 25)
        smtpObj.ehlo()
        message = MIMEMultipart()
        message['Subject'] = subject
        message['From'] = self.fromAdd
        message['To'] = toAdd
        message['X-Priority'] = urgency
        body_content = body
        message.attach(MIMEText(body_content, "html"))
        if excel_attachment:
            part = MIMEBase('application', "octet-stream")
            part.set_payload(open(excel_attachment, "rb").read())
            encoders.encode_base64(part)
            tme = int(datetime.now().strftime('%Y%m%d'))
            part.add_header('Content-Disposition', f'attachment; filename="{projname}_{tme}.xlsx"')
            message.attach(part)
        msg_body = message.as_string()
        
        smtpObj.sendmail(message['From'], message['To'], msg_body)


    def send_mass_message(self, toAdds: List, subject, message):
        try:
            smtpObj = smtplib.SMTP(self.server, 25)
            # smtpObj.starttls()
            smtpObj.ehlo()
            # smtpObj.login(self.login_un, self.login_pw)
            compiledmessage = "Subject:" + subject + "\r\n\n" + message
            for address in toAdds:
                smtpObj.sendmail(self.fromAdd, address, compiledmessage)
        except Exception as e:
            print(e)
        finally:
            smtpObj.quit()





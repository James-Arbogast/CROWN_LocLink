## SEGA of America

# The tool monitor is a class that stores information, then sends it to the tool caretaker at the end of the process.

from typing import List
from util.data_tracking.mailClient import mailClient
from datetime import datetime
from util.preferences.preferences import Preferences

class ToolMonitor:
    def __init__(self, loginlist: List, preferences: Preferences):
        self.messages = []
        self.email_un = loginlist[0]
        self.email_pw = loginlist[1]
        self.fromAdd = loginlist[2]
        self.caretaker_email_list = preferences.tool_admin_email_list
        self.projectname = preferences.project_codename

    def add_event(self, event: str):
        print(event)
        self.messages.append(MonitorMessage(event))

    def compile_message(self):
        compiledmessage = "This is LocLink for %s.\n\nI just ran successfully; here is the log:\n" % self.projectname
        for item in self.messages:
            compiledmessage += "\n" + item.time.strftime("%Y/%m/%d %H:%M:%S") + "\t" + item.message
        return compiledmessage

    def send_report(self):
        mail_handler = mailClient('10.30.100.69', self.email_un, self.email_pw, self.fromAdd)
        for email in self.caretaker_email_list:
            mail_handler.send_message(email, "[%s] Automated Report from LocLink" % self.projectname, self.compile_message())


class MonitorMessage:
    def __init__(self, message: str):
        self.time = datetime.now()
        self.message = message

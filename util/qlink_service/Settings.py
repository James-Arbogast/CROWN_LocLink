from datetime import datetime


class GeneralSettings:
    def __init__(self):
        self.memoQ_project_data = []  # type: list[memoQProjectData]
        self.admin_email_list = []

    @classmethod
    def from_json(cls, data):
        created = cls()
        created.memoQ_project_data = [memoQProjectData.from_json(item) for item in data["memoQ_project_data"]]
        created.admin_email_list = data["admin_email_list"]
        return created

    def to_json(self):
        return {"memoQ_project_data": [item.to_json() for item in self.memoQ_project_data],
                "admin_email_list": self.admin_email_list}


class memoQProjectData:
    def __init__(self):
        self.name = ""
        self.ID = ""
        self.usage = []

    @classmethod
    def from_json(cls, data):
        created = cls()
        created.name = data["name"]
        created.ID = data["ID"]
        created.usage = data["usage"]
        return created

    def to_json(self):
        return {"name": self.name,
                "ID": self.ID,
                "usage": self.usage}


class ReportingSettings:
    def __init__(self):
        self.reporting_email_list = []
        self.last_report = None  # type - datetime
        self.report_frequency = 7 # Days

    @classmethod
    def from_json(cls, data):
        created = cls()
        created.reporting_email_list = data["reporting_email_list"]
        created.last_report = datetime.strptime(data["last_report"], datetimeformat)
        created.report_frequency = data["report_frequency"]
        return created

    def to_json(self):
        return {"reporting_email_list": self.reporting_email_list,
                "last_report": self.last_report.strftime(datetimeformat),
                "report_frequency": self.report_frequency}


datetimeformat = "%d-%m-%Y %H:%M:%S"

def grab_list():
    switch = True
    var = []
    while switch:
        email = input("Enter an email. Enter nothing to stop.")
        if email:
            var.append(email)
        else:
            switch = False
    return var


class SegmentStatus:
    Translated = "t"
    R1 = "r1"
    R2 = "r2"
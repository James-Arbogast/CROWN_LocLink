from util.data_tracking.mailClient import mailClient
import pandas as pd
from util.data_tracking.pretty_html_table import build_table
from util.preferences.preferences import Preferences
from pathlib import Path

class ComplianceChecker:
    def __init__(self, preferences: Preferences, mail_client: mailClient):
        self.noncompliant_strings = {}
        self.preferences = preferences
        self.mail_client = mail_client

    def check_for_compliance(self, file: Path, id: str, target_text: str):
        noncompliant = self.mismatched_brackets(target_text)
        if noncompliant:
            index = len(self.noncompliant_strings)
            self.noncompliant_strings[index] = [str(file), id, target_text]
            return True
        return False

    def mismatched_brackets(self, target_text: str):
        opening_bracket_count = target_text.count("<")
        closing_bracket_count = target_text.count(">")

        if opening_bracket_count > closing_bracket_count:
            return True
        return False

    def noncompliant_strings_found(self):
        if len(self.noncompliant_strings) > 0:
            return True

    def send_report(self):
        dataframe = pd.DataFrame.from_dict(self.noncompliant_strings, orient = "index", columns=["File", "ID", "String"])
        table = build_table(dataframe, "orange_light", font_size="small", font_family="Calibri")
        with open(str(self.preferences.compliance_check_template), "r") as template_file:
            template = template_file.read()
        email_data = template.format(noncompliant_strings = table)
        #mail_handler = mailClient('10.30.100.69', 'AKIA6MYNKSLTF4CMKS4L', 'BFxgt15QWemeGTUknhoJxUsTHf5YiKn8JyvuKFeljMca', 'memoq@segaamerica.com')
        self.mail_client.send_HTML_message(", ".join(self.preferences.progress_alert_email_list), 
                                       f"[{self.preferences.memoQ_project_name}] Noncompliant Strings Found",
                                       email_data)
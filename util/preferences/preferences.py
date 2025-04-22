## Very simple console prompt to set up Connor-TBX and save all necessary info as a JSON

import json
from datetime import datetime
from pathlib import Path
from gooey import Gooey, GooeyParser
import sys, os
import bcrypt
import base64
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

class Preferences:
    def __init__(self):
        self.loclink_location = Path()
        self.json_location = Path()
        self.resources_location = Path()
        self.project_codename = ""
        self.textbridge_repo_location = Path()
        self.textbridge_tool_location = Path()
        self.github_backup_folder = Path()
        self.conflict_check_db = Path()
        self.conflict_check_template = Path()
        self.conflict_check_excel = Path()
        self.compliance_check_template = Path()
        self.churn_db_location = Path()
        self.churn_db = Path()
        self.svn_url = Path()
        self.memoQ_folder = Path()
        self.tool_admin_email_list = []
        self.churn_alert_email_list = []
        self.progress_alert_email_list = []
        self.enAudioPrefix = ""
        self.lxvbfFolder = ""
        self.voice_only_folder = ""
        self.voice_script_suffix = ""
        self.memoQ_server_address = ""
        self.memoQ_project_name = ""
        self.project_startdate = {}
        self.project_deadline = {}
        self.qlink_db = Path()
        self.loclink_created_files = []

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        return

    @property
    def memoQ_inbox(self):
        return self.memoQ_folder / inbox

    @property
    def memoQ_outbox(self):
        return self.memoQ_folder / outbox

    @property
    def JPVO_inbox(self):
        return self.memoQ_folder / JPVO / inbox

    @property
    def JPVO_outbox(self):
        return self.memoQ_folder / JPVO / outbox

    @property
    def ENVO_inbox(self):
        return self.memoQ_folder / ENVO / inbox

    @property
    def ENVO_outbox(self):
        return self.memoQ_folder / ENVO / outbox

    #saves json in format that works with preference object
    def save_json(self):
        json_data = {"loclink_location":str(self.loclink_location),
                     "json_location":str(self.json_location),
                     "resources_location":str(self.resources_location),
                     "project_codename":self.project_codename,
                     "textbridge_repo_location":str(self.textbridge_repo_location),
                     "github_backup_folder":str(self.github_backup_folder),
                     "conflict_check_db":str(self.conflict_check_db),
                     "conflict_check_template":str(self.conflict_check_template),
                     "conflict_check_excel":str(self.conflict_check_excel),
                     "compliance_check_template":str(self.compliance_check_template),
                     "churn_db_location":str(self.churn_db_location),
                     "churn_db":str(self.churn_db),
                     "lxvbf_folder":self.lxvbfFolder,
                     "voice_only_folder":self.voice_only_folder,
                     "voice_script_suffix":self.voice_script_suffix,
                     "en_audio_prefix":self.enAudioPrefix,
                     "svn_url":str(self.svn_url),
                     "memoQ_folder":str(self.memoQ_folder),
                     "tool_admin_email_list":self.tool_admin_email_list,
                     "churn_alert_email_list":self.churn_alert_email_list,
                     "progress_alert_email_list":self.progress_alert_email_list,
                     "memoQ_server_address":self.memoQ_server_address,
                     "memoQ_project_name":self.memoQ_project_name,
                     "project_startdate":self.project_startdate,
                     "project_deadline":self.project_deadline,
                     "qlink_db":self.qlink_db,
                     "loclink_created_files":self.loclink_created_files}
        with open(self.json_location, "w") as write_file:
            json.dump(json_data, write_file)

    #takes preferences from already existing json file
    @classmethod
    def from_existing(cls, json_location):
        created = Preferences()
        with open(json_location, "r", encoding='utf-8') as read_file:
            data = json.load(read_file)
        created.loclink_location = Path(data["loclink_location"])
        created.json_location = Path(data["json_location"])
        created.resources_location = Path(data["resources_location"])
        created.project_codename = data["project_codename"]
        created.textbridge_repo_location = Path(data["textbridge_repo_location"])
        created.textbridge_tool_location = Path(data["textbridge_tool_location"])
        created.github_backup_folder = Path(data["github_backup_folder"])
        created.churn_db_location = Path(data["churn_db_location"])
        created.churn_db = Path(data["churn_db"])
        created.conflict_check_db = Path(data["conflict_check_db"])
        created.conflict_check_template = Path(data["conflict_check_template"])
        created.conflict_check_excel = Path(data["conflict_check_excel"])
        created.compliance_check_template = Path(data["compliance_check_template"])
        created.svn_url = Path(data["svn_url"])
        created.memoQ_folder = Path(data["memoQ_folder"])
        created.tool_admin_email_list = data["tool_admin_email_list"]
        created.churn_alert_email_list = data["churn_alert_email_list"]
        created.progress_alert_email_list = data["progress_alert_email_list"]
        created.enAudioPrefix = data["en_audio_prefix"]
        created.lxvbfFolder = data["lxvbf_folder"]
        created.voice_only_folder = data["voice_only_folder"]
        created.voice_script_suffix = data["voice_script_suffix"]
        created.memoQ_server_address = data["memoQ_server_address"]
        created.memoQ_project_name = data["memoQ_project_name"]
        created.project_startdate = data["project_startdate"]
        created.project_deadline = data["project_deadline"]
        created.qlink_db = Path(data["qlink_db"])
        created.loclink_created_files = data["loclink_created_files"]
        return created

inbox = "01 INBOX"
outbox = "02 OUTBOX"
JPVO = "Japanese VO"
ENVO = "English VO"


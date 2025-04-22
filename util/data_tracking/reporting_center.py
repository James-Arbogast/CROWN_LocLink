# James Arbogast james.arbogast@segaamerica.com
# Reporting Center is a class the defines and connects the appropriate reporting data to a tool that displays all projects progress and other data

from genericpath import exists
from pathlib import Path
import os
from datetime import date, datetime
from util.preferences.preferences import Preferences
import json
from util.qlink_service.QlinkProgressDatabase import FileProgress
from util.qlink_service.Settings import GeneralSettings, ReportingSettings, datetimeformat, grab_list, memoQProjectData
import shutil
from util.preferences.reporting_preferences import Reporting_Preferences
import subprocess

#object that connects LocLink to Frost
class ReportingCenter:
    def __init__(self, root_filepath: Path, proj_name: str, preferences: Reporting_Preferences):
        self.preferences = preferences
        self.root = root_filepath
        self.dashboard = preferences.dashboard
        self.proj_name = proj_name
        self.current_report = self.gather_data() # type - ReportDelivery

    def gather_data(self):
        return self.from_existing(preferences=self.preferences)
            
    def from_existing(self, preferences: Reporting_Preferences):
        created = ReportDelivery(self.preferences)
        created.proj_name = preferences 
        created.progress_db = preferences.resources_location / f'qlink\\qlink_json_db.json'
        created.progress_chart = preferences.resources_location / f'reports\\{self.proj_name}_four_week_fig.png'
        created.change_tracker_db = preferences.resources_location / f'reports\\change_tracking_data.json'
        return created
    
    def create_frost_proj(self):
        command = f'cd {self.root} \n CREATE_PROJ.bat'
        subprocess.Popen(command)

#object that contains data of actual reports to be delivered to Frost
class ReportDelivery:
    def __init__(self, preferences: Reporting_Preferences, center: ReportingCenter):
        self.report_center = center
        self.preferences = preferences
        self.proj_name = ''
        self.progress_db = Path()
        self.progress_chart = Path()
        self.change_tracker_db = Path()

    def copy_data_to_center(self):
        print('Copying data to center.')
        if not Path(self.preferences.projects_location / self.proj_name).exists():
            self.report_center.create_frost_proj()
        try:
            shutil.copyfile(Path(self.progress_db), Path(self.preferences.projects_location / f'{self.proj_name}\\Data\\ProgressTracking\\qlink_json_db.json'))
            shutil.copyfile(Path(self.progress_chart), Path(self.preferences.projects_location / f'{self.proj_name}\\ProgressCharts\\{self.proj_name}_four_week_fig.png'))
            shutil.copyfile(Path(self.change_tracker_db), Path(self.preferences.projects_location / f'{self.proj_name}\\Data\\ChangeTracking\\change_tracking_data.json'))
        except Error as err:
            print(err)


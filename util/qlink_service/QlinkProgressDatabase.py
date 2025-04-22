'''
Classes that contain progress data, to be saved to a JSON.
Handles:
- storing data
- reading data
- saving/loading JSON
- backing up JSON regularly (daily)

'''
import suds
from pathlib import Path
from datetime import datetime, timedelta
from typing import List
from util.qlink_service.Settings import GeneralSettings, ReportingSettings, datetimeformat, grab_list, memoQProjectData
import json
from shutil import copyfile
import xlsxwriter
from util.qlink_service.QLinkService import QLinkService, MemoQFileStatsData
import sys
import re
from util.preferences.preferences import Preferences

today = datetime.today()
today = today.date()


class QLinkProgressTracker:
    def __init__(self):
        self.json_location = Path()  # type - Path
        self.general_settings = None  # type - GeneralSettings
        self.reporting_settings = None  # type - ReportingSettings
        self.progress_data = {}  # type - Dict("project_name": List[FileProgress])
        self.last_updated = None  # type - datetime
        self.memoQ_server_address = ""
        self.lxvbf_folder = ""
        self.voice_only_folder = ""
        self.voice_script_suffix = ""

    #@property
    def data_by_relativepath(self, projName: str):
        return {f.relative_filepath: f for f in self.progress_data[projName]}

    #@property
    def data_by_filename(self, projName: str):
        return {f.relative_filepath.name: f for f in self.progress_data[projName]}

    #@property
    def data_by_date(self, projName: str):
        # returns a dict of lists by date
        created = {}
        try:
            for f in self.progress_data[projName]:
                # go through each entry in the file
                for timestamp in f.entries_by_timestamp:
                    if timestamp.date() not in created:
                        created[timestamp.date()] = []
                    created[timestamp.date()].append(f.entries_by_timestamp[timestamp])
            return created
        except KeyError:
            return created
        
    def file_progress_on_date(self, projName: str, path, date):
        #Return the progress of the given file on the given date.
        #If no data exists for the exact date given,
        #use data from the previous extant date for that file.

        #Grab the entry for that file
        file_data = self.data_by_relativepath(projName)[path]

        #Find the last date we have date for
        last_date = file_data.date_entries[-1].timestamp.date()
        #If the file doesn't exist anymore and the requested date is later than the final entry, don't count this file
        if file_data.still_exists == False and date >= last_date:
            return ProgressSnapshot()
        
        #Loop through all the date entries and find the one that matches today's date.
        #If there isn't one for the requested date, return the last data before that date.
        #If there are multiple entries for the same day, return the latest one.
        return_data = ProgressSnapshot()
        for d in file_data.date_entries:
            entry_date = d.timestamp.date()
            if entry_date <= date:
                return_data = d
            elif entry_date > date:
                break
        return return_data

    #@property
    def earliest_date(self, projName: str):
        earliest_date = today
        # iterate through all snaps to find the earliest date
        try:
            for f in self.progress_data[projName]:
                file_earliest = min([entry.timestamp for entry in f.date_entries])
                if file_earliest.date() < earliest_date:
                    earliest_date = file_earliest.date()
            return earliest_date
        except KeyError:
            return earliest_date

    def printDataEntries(self, projName: str):
        newQLS = QLinkService(self.memoQ_server_address)
        docList = newQLS.memoQ_project_service.ListProjectTranslationDocuments(newQLS.name_to_GUID(projName))
        for item in docList[0]:
            print(item.DocumentName)

    def fix_character_totals(self, projName: str):
        for fileentry in self.progress_data[projName]:  # type - FileProgress
            for entry in fileentry.date_entries:  # type - ProgressSnapshot
                if entry.total_characters != fileentry.character_count:
                    entry.total_characters = fileentry.character_count

    def find_churn(self, projName: str):
        for fileentry in self.progress_data[projName]:
            if len(fileentry.date_entries) > 1:
                if fileentry.date_entries[-1].total_characters != fileentry.date_entries[-2].total_characters:
                    difference = fileentry.date_entries[-1].total_characters - fileentry.date_entries[-2].total_characters
                    if difference > 0:
                        print('Plus churn found')
                        fileentry.date_entries[-1].churn = '+' + str(difference)
                    if difference < 0:
                        print('Negative churn found')
                        fileentry.date_entries[-1].churn = '-' + str(difference)
                    else:
                        fileentry.date_entries[-1].churn = ""
                else:
                    fileentry.date_entries[-1].churn = ""

    def test_totals(self, projName: str):
        qlink_service = QLinkService(self.memoQ_server_address)
        for project in self.general_settings.memoQ_project_data:
            if project.name == projName:
                totalsList = qlink_service.retrieve_project_file_progress_data(project.ID)
                break
        return[sum([entry.total for entry in totalsList]),sum([entry.confirmed_cc for entry in totalsList]),sum([entry.r1_cc for entry in totalsList]),sum([entry.r2_cc for entry in totalsList])]

    def recent_data(self, projName: str):
        self.check_file_exist(r'M:\Projects\Edge\TextBridge\trunk\Docs', 'Edge')
        returnlist = []
        count = 0
        total = 0
        fileEntryTotal = 0
        entryCount = 0
        for fileentry in self.progress_data[projName]:
            if fileentry.still_exists == False:
                continue
            fileEntryTotal += fileentry.character_count
            #print(f'Filename: {fileentry.relative_filepath} FileEntry Date: {fileentry.date_entries[-1].T_characters}')
            returnlist.append(fileentry.date_entries[-1])
            total += fileentry.character_count
            entryCount += 1
            count += 1
        return returnlist

    def purge_entries_before_date(self, targetdate, projName: str):
        for fileentry in self.progress_data[projName]:
            newentries = []
            for entry in fileentry.date_entries:
                if entry.timestamp > targetdate:
                    newentries.append(entry)
            fileentry.date_entries = newentries

    def purge_entries_on_date(self, targetdate, projName: str):
        for fileentry in self.progress_data[projName]:
            newentries = []
            for entry in fileentry.date_entries:
                if entry.timestamp.date() != targetdate:
                    newentries.append(entry)
            fileentry.date_entries = newentries

    @classmethod
    def from_new(cls, json_location: Path):
        created = cls()
        created.json_location = json_location
        created.last_updated = datetime.now()
        created.general_settings = GeneralSettings()
        # General data
        print("Enter emails for the admin email list.")
        created.general_settings.admin_email_list = grab_list()
        projectcount = input("Are there 1 or 2 projects to pull from?")
        for x in range(0, int(projectcount)):
            createdpjsettings = memoQProjectData()
            createdpjsettings.name = input("Enter project name. Must match memoQ.")
            createdpjsettings.usage = input("What is this used for? t, r1, r2?")
            created.general_settings.memoQ_project_data.append(createdpjsettings)
        created.reporting_settings = ReportingSettings()
        # Reporting Data
        created.reporting_settings.last_report = datetime.now()
        print("Enter emails for members who should receive reports.")
        created.reporting_settings.reporting_email_list = grab_list()
        created.reporting_settings.report_frequency = input("How often, in days, should reports be sent? Default is 7.")
        created.to_json(json_location)

        return created

    def to_json(self, filename: Path):
        filedata = {}
        #print(filename)
        for projName in self.progress_data:
            filedata[projName] = []
            for item in self.progress_data[projName]:
                if re.search(r'(.*):(.*)', str(item.relative_filepath)):
                    item.relative_filepath = Path(re.search(r'(.*):(.*)', str(item.relative_filepath)).group(1))
                    filedata[projName].append(item.to_json())
                else:
                    filedata[projName].append(item.to_json())
        #filedata = {projName : [item.to_json() for item in self.progress_data[projName]] for projName in self.progress_data}
        data = {"json_location": str(self.json_location),
                "general_settings": self.general_settings.to_json(),
                "reporting_settings": self.reporting_settings.to_json(),
                "progress_data": filedata,
                "last_updated": self.last_updated.strftime(datetimeformat)}
        with open(str(filename), "w", encoding="utf-8") as write_file:
            json.dump(data, write_file, ensure_ascii = False)

    def get_ready_jpc(self, projName: str):
        total_ready_jpc = 0
        for file_data in self.progress_data[projName]:
            if file_data.still_exists == False:
                continue
            total_ready_jpc += file_data.ready_count
        return total_ready_jpc

    def get_ready_game_text_jpc(self, projName: str):
        total_ready_jpc = 0
        for file_data in self.progress_data[projName]:
            if file_data.still_exists == False:
                continue
            if file_data.voice_only:
                continue
            try:
                total_ready_jpc += file_data.ready_count
            except AttributeError:
                pass
        return total_ready_jpc

    @classmethod
    def from_json(cls, preferences: Preferences):
        created = cls()
        created.json_location = preferences.qlink_db
        with open(str(created.json_location), "r", encoding="utf-8") as read_json:
            data = json.load(read_json)
        created.general_settings = GeneralSettings.from_json(data["general_settings"])
        created.reporting_settings = ReportingSettings.from_json(data["reporting_settings"])
        created.progress_data = {projName : [FileProgress.from_json(filedata) for filedata in data["progress_data"][projName]] for projName in data["progress_data"]}
        created.last_updated = datetime.strptime(data["last_updated"], datetimeformat)
        created.memoQ_server_address = preferences.memoQ_server_address
        created.lxvbf_folder = preferences.lxvbfFolder
        created.voice_only_folder = preferences.voice_only_folder
        created.voice_script_suffix = preferences.voice_script_suffix
        return created

    def save_json(self):
        if self.json_location.exists():
            self.perform_json_backup()
        self.to_json(self.json_location)

    def perform_json_backup(self):
        overwritepath = self.json_location
        newpath = overwritepath.parent / "qlink_backups" / (
                    overwritepath.stem + "_backup_" + datetime.now().strftime("%Y-%m-%d") + overwritepath.suffix)
        if not newpath.exists():
            copyfile(overwritepath, newpath)
            # Ensures only one backup is taken per day

    def update_via_qlink(self):
        print('Updating via qlink')
        self.last_updated = datetime.now()
        qlink_service = QLinkService(self.memoQ_server_address)
        # go per project
        for project in self.general_settings.memoQ_project_data:
            project_data = {}
            # populate GUID on first run
            if not project.ID:
                project.ID = qlink_service.name_to_GUID(project.name)
                if not project.ID:
                    raise KeyError
            # retrieve data
            project_data[project.name] = {project.usage : qlink_service.retrieve_project_file_progress_data(project.ID)}
            # repackage data so T data and R1/R2 data are married
            repackaged_data = self.repackage_qlink_data(project_data)

            # iterate through files to add data
            for qlinkdata in repackaged_data:
                # see if file is in database
                import_path_simplified = Path(re.search(r'(.*):(.*)', str(qlinkdata.import_path)).group(1))
                if import_path_simplified in self.data_by_relativepath(project.name):
                    matched_dbdata = self.data_by_relativepath(project.name)[import_path_simplified]
                else:
                    # create a new one
                    matched_dbdata = FileProgress.from_new(import_path_simplified, qlinkdata, self.lxvbf_folder, self.voice_only_folder)
                    self.progress_data[project.name].append(matched_dbdata)
                # create a new snapshot for that dbdata and add if it's updated
                matched_dbdata.add_snapshot(qlinkdata)
                matched_dbdata.character_count = qlinkdata.total
                matched_dbdata.ready_count = qlinkdata.ready_total

    @staticmethod
    def repackage_qlink_data(project_data):
        repackaged_database = []
        repackageCount = 0
        repack_T = 0
        repack_R1 = 0
        repack_R2 = 0
        # create dict of edit data
        for pName in project_data:
            for item in project_data[pName]:
                for stats in project_data[pName][item]:
                    repackaged_data = MemoQFileStatsData()
                    repackaged_data.filename = stats.filename
                    repackaged_data.import_path = stats.import_path
                    repackaged_data.confirmed_cc = stats.confirmed_cc
                    repack_T += stats.confirmed_cc
                    repackaged_data.r1_cc = stats.r1_cc
                    repack_R1 += stats.r1_cc
                    repackaged_data.r2_cc = stats.r2_cc
                    repack_R2 += stats.r2_cc
                    repackaged_data.total = stats.total
                    repackaged_data.ready_total = stats.ready_total
                    repackaged_database.append(repackaged_data)
                    repackageCount += 1
        #print("repackageCount:",repackageCount, repack_T, repack_R1, repack_R2)

        # return
        return repackaged_database

    def check_file_exist(self, root_directory: Path, projName: str, loclink_files):
        for entry in self.progress_data[projName]:
            if self.lxvbf_folder in str(entry.relative_filepath):
                combined_path = root_directory / Path(str(entry.relative_filepath).replace('.xliff', '.lxvbf'))
                combined_path = Path(str(combined_path).replace(self.voice_script_suffix, ""))
            else:
                combined_path = root_directory / Path(str(entry.relative_filepath).replace('.xliff', '.lxtxt'))
            if combined_path.exists() or entry.relative_filepath.stem in loclink_files:
                entry.still_exists = True
            else:
                entry.still_exists = False
    
    def check_file_voiced(self, root_directory: Path, projName: str):
        for entry in self.progress_data[projName]:
            combined_path = root_directory / entry.relative_filepath
            entry.voiced = True if self.lxvbf_folder in str(combined_path) else False

    def check_file_voice_only(self, root_directory: Path, projName: str):
        for entry in self.progress_data[projName]:
            combined_path = root_directory / entry.relative_filepath
            entry.voice_only = True if self.voice_only_folder in str(combined_path) else False
            
    def current_qlink_to_excel(self, savepath: Path):
        self.last_updated = datetime.now()
        qlink_service = QLinkService(self.memoQ_server_address)
        project_data = {}
        # go per project
        for project in self.general_settings.memoQ_project_data:
            # populate GUID on first run
            if not project.ID:
                project.ID = qlink_service.name_to_GUID(project.name)
                if not project.ID:
                    raise KeyError
            # retrieve data
            project_data[project.usage] = qlink_service.retrieve_project_file_progress_data(project.ID)

        # repackage data so T data  and R1/R2 data are married uwu
        repackaged_data = []
        for entry in project_data:
            if 'r1' in entry:
                repackaged_data.append(project_data[entry]) #originally: repackaged_data = project_data[entry]

        # print repackaged data to Excel
        filetoprint = xlsxwriter.Workbook(savepath)
        printToSheet = filetoprint.add_worksheet("Data")
        printToSheet.freeze_panes(1, 0)
        A_style = filetoprint.add_format()
        A_style.set_fg_color("53a9f9")
        A_style.set_bold()
        A_style.set_bottom(6)
        A_style.set_left(1)
        A_style.set_right(1)
        A_style.set_align('center')
        # Write columns
        printToSheet.write(0, 0, "File Path", A_style)
        printToSheet.set_column(0, 0, 10)
        printToSheet.write(0, 1, "Total", A_style)
        printToSheet.write(0, 2, "T", A_style)
        printToSheet.write(0, 3, "R1", A_style)
        printToSheet.write(0, 4, "R2", A_style)
        currow = 0
        # Iterate through list
        for proj in repackaged_data: # type - MemoQFileStatsData
            for entry in proj:
                currow += 1
                printToSheet.write(currow, 0, str(re.search(r'(.*):(.*)', str(entry.import_path)).group(1)))
                printToSheet.write(currow, 1, entry.total)
                printToSheet.write(currow, 2, entry.confirmed_cc)
                printToSheet.write(currow, 3, entry.r1_cc)
                printToSheet.write(currow, 4, entry.r2_cc)
        filetoprint.close()

class FileProgress:
    def __init__(self):
        self.relative_filepath = Path()
        self.still_exists = True
        self.character_count = 0
        self.ready_count = 0
        self.date_entries = []
        self.voiced = False
        self.voice_only = False

    @property
    def entries_by_timestamp(self):
        return {entry.timestamp: entry for entry in self.date_entries}

    @property
    def entries_by_date(self):
        return {entry.timestamp.date(): entry for entry in self.date_entries}

    @property
    def most_recent_snapshot(self):
        if self.date_entries:
            return max([entry.timestamp for entry in self.date_entries])
        else:
            return None

    def add_snapshot(self, qlinkdata):
        # adds a snapshot if it doesn't exist in its progress data
        newshot = ProgressSnapshot.from_qlink(qlinkdata)
        self.date_entries.append(newshot)

    def to_json(self):
        return {"relative_filepath": str(self.relative_filepath),
                "still_exists": self.still_exists,
                "character_count": self.character_count,
                "ready_count": self.ready_count,
                "voiced": self.voiced,
                "voice_only": self.voice_only,
                "progress_data": [entry.to_json() for entry in self.date_entries]}

    @classmethod
    def from_json(cls, json_data):
        created = cls()
        created.relative_filepath = Path(json_data["relative_filepath"])
        created.still_exists = json_data["still_exists"]
        created.character_count = json_data["character_count"]
        try:
            created.ready_count = json_data["ready_count"]
        except KeyError:
            created.ready_count = 0
        try:
            created.voiced = json_data["voiced"]
        except KeyError:
            created.voiced = False
        try:
            created.voice_only = json_data["voice_only"]
        except KeyError:
            created.voice_only = False
        created.date_entries = [ProgressSnapshot.from_json(entry) for entry in json_data["progress_data"]]
        return created

    @classmethod
    def from_new(cls, relative_filepath, qlink_data, voice_folder, voice_only_folder):
        created = cls()
        created.relative_filepath = relative_filepath
        created.character_count = qlink_data.total
        created.ready_count = qlink_data.ready_total
        created.voiced = True if voice_folder in str(relative_filepath) else False
        created.voice_only = True if voice_only_folder in str(relative_filepath) else False
        created.date_entries = []
        return created


class ProgressSnapshot:
    def __init__(self):
        self.timestamp = None  # type - datetime
        self.T_characters = 0
        self.R1_characters = 0
        self.R2_characters = 0
        self.total_characters = 0
        self.ready_characters = 0
        self.churn = ''

    def to_json(self):
        return {"timestamp": self.timestamp.strftime(datetimeformat),
                "T_characters": self.T_characters,
                "R1_characters": self.R1_characters,
                "R2_characters": self.R2_characters,
                "total_characters": self.total_characters,
                "ready_characters": self.ready_characters,
                "churn" : self.churn}

    @classmethod
    def from_qlink(cls, qlink_data: MemoQFileStatsData):
        created = cls()
        created.timestamp = datetime.now()
        created.T_characters = qlink_data.confirmed_cc
        created.R1_characters = qlink_data.r1_cc
        created.R2_characters = qlink_data.r2_cc
        created.total_characters = qlink_data.total
        created.ready_characters = qlink_data.ready_total
        return created

    @classmethod
    def from_json(cls, json_data):
        created = cls()
        created.timestamp = datetime.strptime(json_data["timestamp"], datetimeformat)
        created.T_characters = json_data["T_characters"]
        created.R1_characters = json_data["R1_characters"]
        created.R2_characters = json_data["R2_characters"]
        created.total_characters = json_data["total_characters"]
        try:
            created.ready_characters = json_data["ready_characters"]
        except KeyError:
            created.ready_characters = 0
        if "churn" in json_data.keys():
            created.churn = json_data["churn"]
        return created


    def __eq__(self, other):
        if isinstance(other, ProgressSnapshot):
            return self.T_characters == other.T_characters \
                   and self.R1_characters == other.R1_characters \
                   and self.R2_characters == other.R2_characters \
                   and self.total_characters == other.total_characters \
                   and self.ready_characters == other.ready_characters

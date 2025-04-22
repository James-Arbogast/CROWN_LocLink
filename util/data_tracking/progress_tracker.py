"""
Progress Tracker is a revamped version of the Progress Reporter.
This version was created for Connor-TBX and operates exclusively on LXTXTDatabase and MemoQDatabase databases.


The object:
- compares the progress between XLIFF and LXTXT to double-check Connor's conversion work
- determines the progress of each file in the project
- stores progress data per file in a .json
- keeps a simple history (1 version back) of progress in files
- can alert users if any files have reached 100% progress
"""

from datetime import datetime
from pathlib import Path
from util.LanguageCodes import Language
import csv
from util.data_tracking.mailClient import mailClient
from util.data_tracking.pretty_html_table import build_table
from util.lxtxt import FileInterface as LXTXT
from util.data_tracking.count_JPC import count_JPC
from shutil import copyfile
from util.xliff.xliff import File as XLIFF
import json


class ProgressTracker:
    def __init__(self, json_location, file_progress_list):
        self.json_location = json_location
        self.file_progress_list = file_progress_list
        self.file_progress_by_path = None
        self.source_language = None

    @classmethod
    def create_new_from_lxtxt_dir(cls, json_location, lxtxt_dir: Path):
        file_list = [FileProgressData.new_from_lxtxt(filepath) for filepath in lxtxt_dir.glob("**/*.lxtxt")]
        created = ProgressTracker(json_location, file_list)
        created.file_progress_by_path = {item.original_filepath: item for item in created.file_progress_list}
        created.source_language = Language.Japanese
        return created

    @classmethod
    def new_from_existing(cls, json_filepath: Path):
        #read in json
        with open(str(json_filepath), "r") as read_json:
            data = json.load(read_json)
        file_list = [FileProgressData.from_json(item) for item in data["filedata"]]
        created = ProgressTracker(json_filepath, file_list)
        created.file_progress_by_path = {item.original_filepath: item for item in created.file_progress_list}
        created.source_language = data["source_language"]

    def to_json(self, filename: Path):
        filedata = [item.to_json() for item in self.file_progress_list]
        data = {"source_language":self.source_language, "filedata":filedata}
        with open(str(filename), "w") as write_file:
            json.dump(data, write_file)

    def save_new_json(self):
        write_path = self.json_location / ("progress_" + datetime.today().strftime("%Y%m%d_%H%M") + ".json")
        if write_path.exists():
            self.perform_json_backup(write_path)  # Backs up json if done at the same time. Safety feature.
        self.to_json(write_path)

    @staticmethod
    def perform_json_backup(write_path):
        copyfile(str(write_path), str(write_path) + write_path.stem + "_backup.json")

    def get_total_progress_percent(self, language):
        return self.get_total_complete(language) / self.total_source_strings

    def get_total_complete(self, language):
        totalcomplete = 0
        for filedata in self.file_progress_list:
            retrieved = filedata.data_by_language[language]
            totalcomplete += retrieved.complete_cells
        return totalcomplete

    def get_total_JPC_complete(self, language):
        return self.get_total_progress_percent(language) * self.total_project_JPC

    @property
    def total_source_strings(self):
        return self.get_total_complete(self.source_language)

    @property
    def total_project_JPC(self):
        return sum([fileboy.file_JPC for fileboy in self.file_progress_list])


class FileProgressData:
    def __init__(self):
        self.original_filepath = None
        self.data_by_language = {}
        self.file_JPC = 0

    @classmethod
    def new_from_lxtxt(cls, filepath):
        created = FileProgressData()
        created.original_filepath = filepath
        created.update_lxtxt()
        return created

    def update_lxtxt(self):
        lxtxt_file = LXTXT.from_file(self.original_filepath)
        langdict = self.data_by_language
        fileJPC = 0
        # COYOTE ONLY
        for row in lxtxt_file.text_rows:
            # COYOTE ONLY: ENVO IS ITS OWN LANGUAGE
            if "message_for_audio_language_en" in row.label:
                if "en-vo" not in langdict.keys():
                    langdict["en-vo"] = LanguageProgressData("en-vo")
                langdict["en-vo"].total_cells += 1
                if row.get_language_cell("en").is_ready_for_translation():
                    langdict["en-vo"].complete_cells += 1
                continue
            # read all languages
            for lang_cell in row.language_cells:
                # build dict
                if lang_cell.language not in langdict.keys():
                    langdict[lang_cell.language] = LanguageProgressData(lang_cell.language)
                # add 1 to total count
                langdict[lang_cell.language].total_cells += 1
                # add to complete count
                if lang_cell.is_ready_for_translation(): # Marked "complete" in TextBridge
                    langdict[lang_cell.language].complete_cells += 1
                # Add JPC
                if lang_cell.language == Language.Japanese and lang_cell.text is not None:
                    fileJPC += count_JPC(lang_cell.text)

        # update current data
        for item in langdict.keys():
            langdict[item].update()
        self.file_JPC = fileJPC

    @classmethod
    def new_from_xliff(cls, filepath):
        created = FileProgressData()
        created.original_filepath = filepath
        created.update_xliff()
        return created

    def update_xliff(self):
        xliff_file = XLIFF.from_file(self.original_filepath)
        langdict = self.data_by_language
        fileJPC = 0
        for contextid, unit in xliff_file.trans_units.items():
            # setup
            if xliff_file.source_language not in langdict.keys():
                langdict[xliff_file.source_language] = LanguageProgressData(xliff_file.source_language)
            if xliff_file.target_language not in langdict.keys():
                langdict[xliff_file.target_language] = LanguageProgressData(xliff_file.target_language)
            # processing
            if not unit.locked:
                langdict[xliff_file.source_language].totalcells += 1
                langdict[xliff_file.source_language].completecells += 1 # All XLIFFs generate with source
                langdict[xliff_file.target_language].totalcells += 1
                if not any(unit.target == item for item in [None, ""]):
                    langdict[xliff_file.target_language].completecells += 1  # As long as target is populated, counts as complete. MemoQ cannot export statuses correctly
                #JPC
                fileJPC += count_JPC(unit.source)
        # update current data
        for item in langdict.keys():
            langdict[item].update()
        self.file_JPC = fileJPC

    def to_json(self):
        return {"original_filepath": str(self.original_filepath),
                "file_JPC": self.file_JPC,
                "langdata": [self.data_by_language[langkey].to_json() for langkey in self.data_by_language.keys()]}

    @classmethod
    def from_json(cls,json_data):
        created = FileProgressData()
        created.original_filepath = Path(json_data["original_filepath"])
        created.file_JPC = json_data["file_JPC"]
        progdatalist = [LanguageProgressData.from_json(data) for data in json_data["langdata"]]
        created.data_by_language = {item.language:item for item in progdatalist}
        pass

class LanguageProgressData:
    def __init__(self, language):
        self.language = language
        self.total_cells = 0
        self.complete_cells = 0
        self.current_version_completion = 0
        self.current_version_date = datetime.today()
        self.previous_version_completion = 0
        self.previous_version_date = datetime.today()

    def update(self):
        self.previous_version_completion = self.current_version_completion
        self.previous_version_date = self.current_version_date
        self.current_version_completion = self.complete_cells / self.total_cells
        self.current_version_date = datetime.today()

    def to_json(self):
        return {"language": self.language,
                "total_cells":self.total_cells,
                "complete_cells":self.complete_cells,
                "current_version_completion":self.current_version_completion,
                "current_version_date":self.current_version_date.strftime("%m/%d/%Y %H:%M:%S"),
                "previous_version_completion":self.previous_version_completion,
                "previous_version_date":self.previous_version_date.strftime("%m/%d/%Y %H:%M:%S")}

    @classmethod
    def from_json(cls,json_data):
        created = LanguageProgressData(json_data["language"])
        created.total_cells = json_data["total_cells"]
        created.complete_cells = json_data["complete_cells"]
        created.current_version_date = json_data["current_version_date"]
        created.current_version_completion = json_data["current_version_completion"]
        created.previous_version_date = json_data["previous_version_date"]
        created.previous_version_completion = json_data["previous_version_completion"]
        return created


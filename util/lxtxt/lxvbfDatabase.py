#SEGA of America
#dan.sunstrum@segaamerica.com

from pathlib import Path
import clr
from util.data_tracking.count_JPC import count_JPC
from util.preferences.preferences import Preferences
from util.LanguageCodes import Language

with Preferences.from_existing(r"resources\project_preferences.json") as pref:
    clr.AddReference(str(pref.textbridge_tool_location / "LxSdk"))
clr.AddReference("System")

from LxSdk import LxVoiceBridgeFile
from LxSdk import LxCellStatus

class LXVBF_Container:
    def __init__(self, filepath):
        self.interface = LxVoiceBridgeFile()
        self.interface.LoadFromFile(str(filepath))
        self.path = filepath
        self.has_been_edited = False

class LXVBFDatabase:
    def __init__(self, preferences: Preferences):
        self.assets_root = preferences.textbridge_repo_location if isinstance(preferences.textbridge_repo_location, Path) else Path(preferences.textbridge_repo_location)
        self.voice_only_folder = preferences.voice_only_folder
        self.files = []
        self.speaker_dict = {}
        self.translation_requested = set()
        self.update()

    def update(self):
        for filepath in self.assets_root.rglob("*.lxvbf"):
            self.files.append(LXVBF_Container(filepath))
        for lxvbf in self.files:
            for row in lxvbf.interface.Rows:
                self.speaker_dict[row.Cells["ja"].Speaker] = ""
                if self.voice_only_folder not in str(lxvbf.path):
                    continue
                #A cell being TranslationRequested acts as a trigger for the corresponding segment
                #to get unconfirmed in memoQ, so we need to change the status so it doesn't
                #repeatedly unconfirm segments people are working on.
                #The IDs that were in TranslationRequested status are stored in a list for later usage.
                ENcell = row.Cells[Language.English]
                if ENcell and ENcell.Text.Status == LxCellStatus.TranslationRequested:
                    relpath = lxvbf.path.relative_to(self.assets_root)
                    if ENcell.VoiceFileName:
                        contextID = str(relpath) + "-" + ENcell.VoiceFileName
                    else:
                        contextID = str(relpath) + "-" + row.Label
                    self.translation_requested.add(contextID)
                    ENcell.Text.Status = LxCellStatus.Editing
                    lxvbf.has_been_edited = True
    
    def save_changes(self):
        changelist = []
        if any(file.has_been_edited for file in self.files):
            for file in self.files:
                if file.has_been_edited:
                    file.interface.SaveToFile(str(file.path), True, None)
                    file.has_been_edited = False
                    try:
                        changelist.append(file.path.relative_to(self.assets_root))
                    except ValueError:
                        changelist.append(file.path)
        return changelist

    def count_total_JPC(self):
        #return sum([file.count_file_JPC() for file in self.files])
        sum = 0
        out_file = open("lxvbf_total.txt","w", encoding = "utf8")
        for file in self.files:
            file_sum = 0
            for row in file.interface.Rows:
                if not row.Cells[Language.English].VoiceFileRequired:
                    continue
                if row.Cells[Language.Japanese]:
                    sum += count_JPC(row.Cells[Language.Japanese].Text.Text)
                    file_sum +=count_JPC(row.Cells[Language.Japanese].Text.Text)
            out_file.write(str(file.path) + "\t" + str(file_sum) + "\n")
        return sum

    def count_finished_JPC(self):
        #return sum([file.count_finished_JPC(language) for file in self.files])
        sum = 0
        out_file = open("lxvbf_finished.txt", "w", encoding = "utf8")
        for file in self.files:
            file_sum = 0
            for row in file.interface.Rows:
                cell = row.Cells[Language.English]
                if not cell.VoiceFileRequired:
                    continue
                #LxSdk currently does not expose Voice Bridge cell status
                #so I'm counting it as "done" if it has English text
                if cell and len(cell.Text.Text) > 0:
                    if row.Cells[Language.Japanese]:
                        sum += count_JPC(row.Cells[Language.Japanese].Text.Text)
                        file_sum += count_JPC(row.Cells[Language.Japanese].Text.Text)
            out_file.write(str(file.path) + "\t" + str(file_sum) + "\n")
        return sum

    def produce_JPC_count_list(self):
        printlist = [[file.original_filepath,file.count_finished_JPC(),file.count_file_JPC()] for file in self.files]
        return printlist
# SEGA of America
# dan.sunstrum@segaamerica.com
from util.LanguageCodes import Language
from util.data_tracking.count_JPC import count_JPC
from pathlib import Path
import clr
from util.preferences.preferences import Preferences

with Preferences.from_existing(r"resources\project_preferences.json") as pref:
    clr.AddReference(str(pref.textbridge_tool_location / "LxSdk"))
clr.AddReference("System")

from LxSdk import LxMessageFile
from LxSdk import LxCellStatus

class LXTXT_Container:
    def __init__(self, filepath):
        self.interface = LxMessageFile()
        self.interface.LoadFromFile(str(filepath))
        self.path = filepath
        self.has_been_edited = False

class LXTXTDatabase:
    TotalJPCIncludedStatuses = [LxCellStatus.NotStarted,LxCellStatus.Editing,LxCellStatus.ParentLanguageEditing,LxCellStatus.TranslationRequested,LxCellStatus.Completed]

    def __init__(self, assets_root: Path):
        self.assets_root = assets_root if isinstance(assets_root, Path) else Path(assets_root)
        self.files = []
        self.speaker_dict = {}
        self.translation_requested = set()
        self.update()

    def update(self):
         # update list of files
        for filepath in self.assets_root.rglob("*.lxtxt"):
            self.files.append(LXTXT_Container(filepath))
        # read speaker names and bustup params
        for lxtxt in self.files:
            for row in lxtxt.interface.Rows:
                if row.AttributeCells["Speaker"]:
                    self.speaker_dict[row.AttributeCells["Speaker"].Text] = ""  # Blank translation
                #A cell being TranslationRequested acts as a trigger for the corresponding segment
                #to get unconfirmed in memoQ, so we need to change the status so it doesn't
                #repeatedly unconfirm segments people are working on.
                #The IDs that were in TranslationRequested status are stored in a list for later usage.
                if row.LanguageCells[Language.English] and row.LanguageCells[Language.English].Status == LxCellStatus.TranslationRequested:
                    relpath = lxtxt.path.relative_to(self.assets_root)
                    contextID = str(relpath) + "-" + row.Label
                    self.translation_requested.add(contextID)
                    row.LanguageCells[Language.English].Status = LxCellStatus.Editing
                    lxtxt.has_been_edited = True

    def save_changes(self):
        changelist = []
        if any(file.has_been_edited for file in self.files):
            for file in self.files:
                if file.has_been_edited:
                    file.interface.SaveToFile(str(file.path), True)
                    file.has_been_edited = False
                    try:
                        changelist.append(file.path.relative_to(self.assets_root))
                    except ValueError:
                        changelist.append(file.path)
        return changelist

    # Counts JPC in source and returns # of JPC
    def count_total_JPC(self):
        #return sum([file.count_file_JPC() for file in self.files])
        sum = 0
        out_file = open("lxtxt_total.txt", "w", encoding = "utf8")
        for file in self.files:
            file_sum = 0
            for row in file.interface.Rows:
                jpCell = row.LanguageCells[Language.Japanese]
                if jpCell and jpCell.Status in self.TotalJPCIncludedStatuses:
                    file_sum += count_JPC(row.LanguageCells[Language.Japanese].Text)
                    sum += count_JPC(row.LanguageCells[Language.Japanese].Text)
            out_file.write(str(file.path) + "\t" + str(file_sum) + "\n")
        return sum

    # Counts English segments that are marked as complete.
    def count_finished_JPC(self):
        sum = 0
        out_file = open("lxtxt_finished.txt","w", encoding = "utf8")
        for file in self.files:
            file_sum = 0
            for row in file.interface.Rows:
                enCell = row.LanguageCells[Language.English]
                jpCell = row.LanguageCells[Language.Japanese]
                if enCell and enCell.Status == LxCellStatus.Completed:
                    if jpCell:
                        file_sum += count_JPC(jpCell.Text)
                        sum += count_JPC(jpCell.Text)
            out_file.write(str(file.path) + "\t" + str(file_sum) + "\n")
        return sum
                
   # this creates snap shots of the asian languages in the lxtxtdb to make sure that our tooling didn't change anything
    def asian_lang_db_snapshot(self):
        asian_langs = [Language.Japanese, Language.ChineseSimp, Language.ChineseTrad, Language.Korean]
        snap_dict = {}
        for file in self.files:
            if file.path not in snap_dict.keys():
                snap_dict[file.path] = {}
            for row in file.interface.Rows:
                if row.Label not in snap_dict.keys():
                    snap_dict[file.path][row.Label] = {}
                for lang_cell in row.LanguageCells:
                    if lang_cell.Language in asian_langs:
                        if lang_cell.Language not in snap_dict[file.path][row.Label].keys():
                            snap_dict[file.path][row.Label][lang_cell.Language] = {}
                        lang_text = str(row.LanguageCells[lang_cell.Language].Text)
                        snap_dict[file.path][row.Label][lang_cell.Language] = lang_text


    def produce_JPC_count_list(self):
        #produce list
        printlist = [[file.path,file.count_finished_JPC(),file.count_file_JPC()] for file in self.files]
        return printlist

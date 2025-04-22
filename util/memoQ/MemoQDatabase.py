# SEGA of America

import util.xliff.xliff as xliff
from util.xliff.xliff import Note, RefNote
from typing import List
#from util.debug_logger import Log, LoggerDefinition
from pathlib import Path
import datetime
import shutil
from util.data_tracking.change_tracker import Tracker
import os
from memoq import MemoQServer
from memoq.util import response_object_to_dict
from memoq.webservice import MemoQFileManagerService
from tqdm import tqdm
from util.data_tracking.count_JPC import count_JPC
import json
from threading import Thread
import time
import numpy as np
import math
import stat
from util.preferences.preferences import Preferences

class MemoQDatabase:
    def __init__(self, preferences: Preferences):
        # memoQ INBOX 01
        inbox = preferences.memoQ_inbox if isinstance(preferences.memoQ_inbox, Path) else Path(preferences.memoQ_inbox)
        self.input_folder = inbox
        # memoQ OUTBOX 02
        outbox = preferences.memoQ_outbox if isinstance(preferences.memoQ_outbox, Path) else Path(preferences.memoQ_outbox)
        self.output_folder = outbox

        self.lxvbf_folder = preferences.lxvbfFolder
        self.voice_script_suffix = preferences.voice_script_suffix
        # checking if folders are valid directories
        if not self.input_folder.is_dir():
            raise ValueError("MemoQDB requires a valid directory as the input folder: " + str(self.input_folder))
        if not self.output_folder.is_dir():
            raise ValueError("MemoQDB requires a valid directory as the output folder: " + str(self.output_folder)) 
        # Objects for interacting with memoQ server
        if preferences.memoQ_server_address:
            self.memoQ_server = MemoQServer(preferences.memoQ_server_address)
            self.memoQ_file_manager = MemoQFileManagerService(preferences.memoQ_server_address)
            self.memoQ_project_service = self.memoQ_server._server_project_service
            self.memoQ_project_name = preferences.memoQ_project_name
            self.project_guid = self.get_project_guid()
        else:
            self.memoQ_server = None
            self.memoQ_file_manager = None
            self.memoQ_project_service = None
            self.memoQ_project_name = None
            self.project_guid = None
        self.input_files = [xliff.File.from_file(file, self.input_folder) for file in self.input_folder.rglob('*.xliff')]

        self.ReadyToPushStatuses = ["Review2NotStarted","Review2InProgress","Completed"]
        self.Review1CompleteStatuses = ["Review2NotStarted", "Review2InProgress", "Completed"]
        # Dictionary that pairs a relative file path to its memoQ workflow status
        self.file_statuses = {}
        self.get_workflow_statuses()
        # Dictionary that pairs a relative file path to an exported memoQ XLIFF file object
        self.exported_files = {}

    def get_project_guid(self):
        projects = [response_object_to_dict(project) for project in self.memoQ_server.active_projects]
        for p in projects:
            if p["Name"] == self.memoQ_project_name:
                return p["ServerProjectGuid"]

    def save_file_to_input(self, file: xliff.File, tracker: Tracker):
        # check if the file exists already, if it does - we see if it's changed at all.
        # only actually overwrite it if the contents have changed.
        filepath = self.input_folder.joinpath(file.relative_filepath)  # type: Path
        if filepath.exists():
            existing_file = xliff.File.from_file(filepath, self.input_folder)
            if existing_file == file:
                return  # avoid re-saving a file that hasn't changed. It confuses memoQ and causes unwanted re-imports.
            else:
                # tracks changes from old to new xliff file
                tracker.add_xliff_comparison(existing_file, file)
        else:
            # tracks if new file was added
            tracker.add_new_file(file)
        file.save_in_directory(self.input_folder)

    # returns files living in the memoQ OUTBOX 02
    @staticmethod
    def output_files(directory: Path) -> List[xliff.File]: # Returns a list of XLIFF files
        return [xliff.File.from_file(filepath, directory)
                for filepath in directory.rglob("*.xliff")]
    
    # clears memoQ OUTBOX 02
    def clear_output(self):
        # Remove files
        for filepath in self.output_folder.rglob("*.xliff"):
            if "memoQ" not in filepath.stem:
                filepath.unlink()  # Unlink deletes the filepath in the folder.
        #Remove folders
        walk = list(os.walk(str(self.output_folder)))
        for root, _, _ in walk[::-1]:
            if root == str(self.output_folder):
                continue
            if not os.access(root, os.W_OK):
                os.chmod(root, stat.S_IWUSR)
            shutil.rmtree(root)

    # backs up memoQ OUTBOX 02
    def backup_output(self, subdir: str):
        backup_dir = Path(self.output_folder.parents[0] / "XLIFF Backups/" / subdir / datetime.datetime.now().strftime("%Y_%m_%d %H_%M_%S"))
        ##### Backup_dir: .parents[0] is one folder back, then in "XLIFF Backups/subdir", and creates a new folder with the date/time.
        for filepath in self.output_folder.rglob("*.xliff"):
            dest = backup_dir.joinpath(filepath.relative_to(self.output_folder))
            dest.parent.mkdir(exist_ok=True, parents=True)
            shutil.copy(str(filepath), str(dest))

    # backs up memoQ INBOX 01
    def backup_input(self, subdir: str):
        backup_dir = Path(self.input_folder.parents[0] / "XLIFF Backups/" / "Input_Backups" / datetime.datetime.now().strftime("%Y_%m_%d %H_%M_%S"))
        ##### Backup_dir: .parents[0] is one folder back, then in "XLIFF Backups/subdir", and creates a new folder with the date/time.
        for filepath in self.input_folder.rglob("*.xliff"):
            print(filepath)
            dest = backup_dir.joinpath(filepath.relative_to(self.input_folder))
            dest.parent.mkdir(exist_ok=True, parents=True)
            print(dest)
            shutil.copy(str(filepath), str(dest))

    ###CREATE A METHOD THAT REMOVES XLIFF BACKUP FOLDERS AFTER A CERTAIN LENGTH HAS PASSED

    # Counts JPC in source and returns # of JPC
    def count_finished_and_total_JPC(self):
        finishedJPC = 0
        totalJPC = 0
        # Iterate through XLIFF files counting Source JPC and Source JPC that has a Target.
        for xliffFile in self.output_files(self.output_folder):
            for context_id, xliff_unit in xliffFile.trans_units.items():
                # DO NOT COUNT SPEAKER NAMES OR VO COMMENTS
                if "SPEAKER" not in context_id and "VOCOMMENT" not in context_id:
                    # count JPC in source
                    unitJPC = count_JPC(xliff_unit.source)
                    totalJPC += unitJPC
                    if xliff_unit.target != "":
                        finishedJPC += unitJPC
        return [finishedJPC, totalJPC]
    
    ###CREATE A METHOD THAT GATHERS ROUGH TRANSLATIONS FROM NEW ROUGH T DB AND ADDS TO COMMENTS
    def add_rough_t_comments(self, xliff_file, contextID, commentList):
        if 'memoQ_speaker_list' in os.path.abspath(xliff_file.relative_filepath) or 'memoQ_bustup_list' in os.path.abspath(xliff_file.relative_filepath):
            return
        if 'SPEAKERNAME' in contextID:
            return
        edited = False
        #self.rough_t_data = dict populated from rough translation json file
        rough_T = self.rough_t_data[f'{xliff_file.relative_filepath}'][contextID]['en'].popitem()[0]
        #print(contextID,rough_T)
        if rough_T != None and rough_T != '<NoText>' and rough_T != '':
            commentList.append(f'%%Raw TL: {rough_T}')
    
    def chunks(self, lst, num_lists):
            block_size = int(math.ceil(len(lst) / num_lists))
            for i in range(0, len(lst), block_size):
                yield lst[i:i + block_size]
    
    def filter_doc_list(self, doc_list, only_these):
        filtered_doc_list = []
        for d in doc_list:
            export_path_no_ext = Path(d["ExportPath"][:d["ExportPath"].rfind(".")])
            if self.lxvbf_folder in str(export_path_no_ext):
                export_path_no_ext = Path(str(export_path_no_ext) + self.voice_script_suffix)
            if str(export_path_no_ext) in only_these or "memoQ" in export_path_no_ext.stem:
                filtered_doc_list.append(d)
        return filtered_doc_list

    def export_doc_list(self, doc_list: List, only_these: set, bar_num, guid):
        if only_these:
            doc_list = self.filter_doc_list(doc_list, only_these)
        t = tqdm(doc_list, leave = False, position = bar_num, total = len(doc_list))
        for doc in t:
            try:
                export_path = doc["ExportPath"]
                if export_path[0] == "\\":
                    export_path = export_path[1:]
                export_path_no_ext = Path(export_path[:export_path.rfind(".")])
                #if only_these:
                #    if str(export_path_no_ext) not in only_these and "memoQ" not in export_path_no_ext.stem:
                #        continue
                self.file_statuses[export_path_no_ext] = doc["WorkflowStatus"]
                #Request an export from the server
                export_info = self.memoQ_project_service.ExportTranslationDocument(guid, doc["DocumentGuid"])
                #Ask the server to start sending data chunks
                file_data = self.memoQ_file_manager.BeginChunkedFileDownload(export_info["FileGuid"], False)
                #Open a file for writing
                file_name = self.output_folder / export_path
                os.makedirs(os.path.dirname(file_name), exist_ok = True)
                output_file = open(file_name, "wb", buffering=0)
                #Write each chunk to the file
                while True:
                    #1,048,576 is 1024 x 1024 bytes, or 1 MB.
                    chunk = self.memoQ_file_manager.GetNextFileChunk(file_data["BeginChunkedFileDownloadResult"], 1048576)
                    if not chunk:
                        break
                    output_file.write(chunk)
                #End process to free up server resources
                self.memoQ_file_manager.EndChunkedFileDownload(file_data["BeginChunkedFileDownloadResult"])
                #print(Path(self.output_folder / export_path))
                self.exported_files[export_path_no_ext] = xliff.File.from_file(Path(self.output_folder / export_path),self.output_folder)
            except Exception as error:
                print(type(error).__name__ + " - " + doc["ExportPath"])
                continue
        print(" 100% |\n", end="\r")

    # Uses memoQ API to export all files from the project and create a dictionary of file:status
    def export_all_files(self, only_these: set):
        time0 = time.time()
        #Get list of all documents in project
        doc_list = self.memoQ_project_service.ListProjectTranslationDocuments(self.project_guid)
        #If the project is empty then don't do anything
        if not doc_list:
            return
        divide_num = 4
        split_lists =  self.chunks(doc_list, divide_num)
        thread_list = []
        thread_num = 0
        for small_list in split_lists:
            thread = Thread(name=f'Thread {thread_num + 1}', target=self.export_doc_list, args=(small_list, only_these, thread_num, self.project_guid), daemon=True)
            thread_num += 1
            thread_list.append(thread)
        for i in range(0,len(thread_list)):
            thread_list[i].start()
        for i in range(0,len(thread_list)):
            thread_list[i].join()
        time_done = time.time()
        total = time_done-time0
        print(total)

    def get_workflow_statuses(self):
        doc_list = self.memoQ_project_service.ListProjectTranslationDocuments(self.project_guid)
        if not doc_list:
            return
        for doc in doc_list:
            export_path = doc["ExportPath"]
            if export_path[0] == "\\":
                export_path = export_path[1:]
            export_path_no_ext = Path(export_path[:export_path.rfind(".")])
            self.file_statuses[export_path_no_ext] = doc["WorkflowStatus"]

    def get_speaker_file(self) -> xliff:
        #try:
        return self.exported_files[Path("memoQ_speaker_list")]
        #except KeyError:
            #return None
        
    def get_voice_script_speaker_file(self) -> xliff:
        try:
            return self.exported_files[Path("memoQ_voice_script_speaker_list")]
        except KeyError:
            return None
    
    def get_bustup_file(self):
        try:
            return self.exported_files[Path("memoQ_bustup_list")]
        except KeyError:
            return None

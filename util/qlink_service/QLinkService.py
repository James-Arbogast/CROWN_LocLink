"""
Complex Function.
Handles interfacing with the memoQ API to retrieve progress information to store in a ProgressDatabase.

Takes the memoQ Project name/ID info, returns data from memoQ for the Qlink database to parse


"""

from suds.client import Client
from memoq import MemoQServer
from memoq.util import response_object_to_dict
from memoq.webservice import MemoQFileManagerService
from pathlib import Path
from base64 import b64decode
from datetime import datetime
import sys
import xlsxwriter
import re


class QLinkService:
    def __init__(self, memoQ_server_address):
        self.memoQ_server = MemoQServer(memoQ_server_address)
        self.memoQ_file_manager = MemoQFileManagerService(memoQ_server_address)
        self.memoQ_project_service = self.memoQ_server._server_project_service

    def retrieve_project_file_progress_data(self, project_GUID: str):
        # returns a list of MemoQFileStatsData objects
        project_file_data = self.memoQ_project_service.ListProjectTranslationDocuments(project_GUID)
        returnlist = []
        totalChars = 0
        totalT = 0
        totalR1 = 0
        totalR2 = 0
        if len(project_file_data) == 0:
            return returnlist
        for item in project_file_data:
            newfiledata = MemoQFileStatsData()
            newfiledata.filename = item.DocumentName
            import_path = item.ImportPath
            newfiledata.import_path = Path(import_path)
            newfiledata.confirmed_cc = item.ConfirmedCharacterCount
            newfiledata.r1_cc = item.Reviewer1ConfirmedCharacterCount
            newfiledata.r2_cc = item.ProofreadCharacterCount
            totalT += item.ConfirmedCharacterCount
            totalR1 += item.Reviewer1ConfirmedCharacterCount
            totalR2 += item.ProofreadCharacterCount
            totalChars += item.TotalCharacterCount
            newfiledata.total = item.TotalCharacterCount
            newfiledata.ready_total = item.TotalCharacterCount - item.LockedCharacterCount
            returnlist.append(newfiledata)
        return returnlist  # Returns list of MemoQFileStatsData

    def current_memoQ_to_excel(self, savepath: Path, project_GUID: str):
        project_file_data = self.memoQ_project_service.ListProjectTranslationDocuments(project_GUID)
        self.last_updated = datetime.now()
        returnlist = []
        totalChars = 0
        for item in project_file_data:
            newfiledata = MemoQFileStatsData()
            newfiledata.filename = item.DocumentName
            import_path = item.ImportPath
            newfiledata.import_path = Path(import_path)
            newfiledata.confirmed_cc = item.ConfirmedCharacterCount
            newfiledata.r1_cc = item.Reviewer1ConfirmedCharacterCount
            newfiledata.r2_cc = item.ProofreadCharacterCount
            totalChars += item.TotalCharacterCount
            newfiledata.total = item.TotalCharacterCount
            returnlist.append(newfiledata)
        # go per project

        # repackage data so T data  and R1/R2 data are married uwu
        repackaged_data = []
        for entry in returnlist:
            repackaged_data.append(entry) #originally: repackaged_data = project_data[entry]

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
        for entry in repackaged_data: # type - MemoQFileStatsData
            currow += 1
            printToSheet.write(currow, 0, str(re.search(r'(.*):(.*)', str(entry.import_path)).group(1)))
            printToSheet.write(currow, 1, entry.total)
            printToSheet.write(currow, 2, entry.confirmed_cc)
            printToSheet.write(currow, 3, entry.r1_cc)
            printToSheet.write(currow, 4, entry.r2_cc)

        filetoprint.close()

    def name_to_GUID(self, project_name):
        projectlist = [response_object_to_dict(project) for project in self.memoQ_server.active_projects]
        for PJ in projectlist:
            if project_name == PJ["Name"]:
                return PJ["ServerProjectGuid"]


class MemoQFileStatsData:
    def __init__(self):
        self.filename = ""
        self.import_path = ""
        self.confirmed_cc = 0
        self.r1_cc = 0
        self.r2_cc = 0
        self.total = 0
        self.ready_total = 0
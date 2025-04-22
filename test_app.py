# SEGA of America
# dan.sunstrum@segaamerica.com
from util.LanguageCodes import Language
from util.preferences.preferences import Preferences
from util.converter import FileConverter
from util.lxtxt.lxtxtDatabase import LXTXTDatabase
from util.lxtxt.lxvbfDatabase import LXVBFDatabase
from util.memoQ.MemoQDatabase import MemoQDatabase
from util.data_tracking.change_tracker import Tracker
from util.data_tracking.tool_monitor import ToolMonitor
from util.data_tracking.progress_reporting import ProgressReporter
from util.fileshare.svn import Handler
from pathlib import Path
from typing import List
from datetime import date
from util.LanguageCodes import Language
from util.file_list import FileList
from util.conflict_check import ConflictChecker

print("Reading Project Preferences.")
preferences = Preferences.from_existing(r"resources\project_preferences.json")
print("Creating Tracker objects.")
maillogin = ['AKIA6MYNKSLTF4CMKS4L', 'BFxgt15QWemeGTUknhoJxUsTHf5YiKn8JyvuKFeljMca', 'memoq@segaamerica.com']
curmonitor = ToolMonitor(maillogin, preferences)
print("Creating LXTXT Database.")
lxtxtDB = LXTXTDatabase(preferences.textbridge_repo_location)
graphicDB = LXTXTDatabase(preferences.graphic_text_repo_location)
print("Creating LXVBF Database.")
lxvbfDB = LXVBFDatabase(preferences.textbridge_repo_location)
print("Creating memoQ Database.")
memoQDB = MemoQDatabase(preferences.memoQ_inbox,
                            preferences.memoQ_outbox,
                            preferences.memoQ_server_address,
                            preferences.memoQ_project_name)

#file_list = FileList(Path(r'resources\Filelist\filelist.xlsx'), memoQDB, lxtxtDB)
#file_list.create_file_list(True)

        # creates a conflict checker 
conflict_checker = ConflictChecker(preferences.conflict_check_db, 
                                    memoQDB, 
                                    lxtxtDB, 
                                    preferences.conflict_check_template,
                                    preferences.conflict_check_excel,
                                    'en',
                                    preferences,
                                    svnHandler=None,
                                    update_svn=False,
                                    lxvbfDB=lxvbfDB)


'''
print("Creating converter.")
fileConverter = FileConverter(lxtxtDB, graphicDB, lxvbfDB, memoQDB, Language.Japanese, Language.English, tooltracker, preferences.enAudioPrefix, preferences.lxvbfFolder, preferences.graphicFolder)
fileConverter.update_DBs(["memoQ_speaker_list.xliff"])
curmonitor.add_event("Created converter object.")

if push_into_TextBridge:
    if export_memoQ:
        print("Exporting memoQ files")
        memoQDB.export_all_files(only_these)
    else:
        curmonitor.add_event("Skipped memoQ export")
    print("Porting XLIFF data into the LXTXT Database.")
    fileConverter.update_DBs(only_these)
    curmonitor.add_event("Ported English text into lxtxtDB.")
    print("Pushing changes to Text Bridge")
    fileConverter.save_changes()
    if update_svn:
        print("Committing to SVN.")
        svnHandler.commit_changes("Automated commit from SOA. Please contact dan.sunstrum@segaamerica.com if any issues arise.")
        svnHandler_graphic.commit_changes("Automated commit from SOA. Please contact dan.sunstrum@segaamerica.com if any issues arise.")
        curmonitor.add_event("Changes committed to SVN.")
    else:
        curmonitor.add_event("Changes not committed to SVN.")
    print("Backing up XLIFF data.")
    memoQDB.backup_output("")
    curmonitor.add_event("Backed up XLIFF data.")
    if not preserve_exported_files:
        print("Clearing out output folders.")
        memoQDB.clear_output()
        curmonitor.add_event("Cleared out output folders.")
    else:
        ("Output folders not cleared.")

if pull_into_memoQ:
    print("Converting LXTXT data to XLIFF for memoQ.")
    fileConverter.convert_to_xliff(only_these)
    curmonitor.add_event("Converted LXTXT data to XLIFF.")
    print("Removing deleted files.")
    fileConverter.remove_deleted_files()
    curmonitor.add_event("Removed deleted files.")

else:
    print("memoQ conversion skipped.")

# Reporting: Sends email if changes logged.
if send_emails and tooltracker.changes_logged():
    tooltracker.export_summary()

# Progress Tracking
if date.today().weekday() < 5:  # 0 is monday, if it's not a weekend, send a daily update.
    progresstracker.add_new_snapshot_data([lxtxtDB.count_total_JPC(), lxtxtDB.count_finished_JPC(), lxvbfDB.count_total_JPC(), lxvbfDB.count_finished_JPC()])
    # removed memoQDB.count_finished_and_total_JPC()
    if send_emails:
        progresstracker.notify_users()
    progresstracker.save_csv_data()

try:
    if send_emails:
        curmonitor.send_report()
        print("Emails sent")
except Exception as e:
    print("Exception thrown while sending emails: \n" + str(e))
    #If this doesn't print the important info, a few other suggestions in here: https://stackoverflow.com/questions/1483429/how-do-i-print-an-exception-in-python
'''
# SEGA of America
from util.LanguageCodes import Language
from util.lxtxt.lxvbfDatabase import LXVBFDatabase
from util.preferences.preferences import Preferences
from util.converter import FileConverter
from util.lxtxt.lxtxtDatabase import LXTXTDatabase
from util.memoQ.MemoQDatabase import MemoQDatabase
from util.data_tracking.change_tracker import Tracker
from util.data_tracking.tool_monitor import ToolMonitor
from util.data_tracking.progress_reporting import ProgressReporter
from util.fileshare.svn import Handler
from pathlib import Path
from typing import List
from datetime import date
from util.LanguageCodes import Language
from util.qlink_service.QLinkAnalyzerReporter import QlinkAnalyzerReporter
from util.data_tracking.reporting_center import ReportingCenter
from jobs import add_rough_TL_to_churn_file, add_rough_ED_to_churn_file, add_backups_to_churn_data, backup_xliffs_to_github
from util.data_tracking.mailClient import mailClient
from shutil import copy2
import os, traceback
from util.conflict_check.conflict_check import ConflictChecker
from util.compliance_check import ComplianceChecker

def run(push_into_TextBridge: bool = False, pull_into_memoQ: bool = False, update_svn: bool = False, send_emails: bool = False, only_these_file: str = "", export_memoQ: bool = False, preserve_exported_files: bool = False, github: bool = False, debug: bool = False, reporting: bool = False, novoice: bool = False):
    ###TO DO
    ###CREATE A PROGRESS BAR FOR FULL TOOLING PROCESS 
    
    # reads in preferences and pathings from a json file in the resources folder
    print("Reading project preferences.")
    # IF DEBUGGING TOOL DEBUG PREFS BECOME PREFS
    if debug:
        preferences = Preferences.from_existing(r"resources\debug_project_preferences.json")
    else:
        preferences = Preferences.from_existing(r"resources\project_preferences.json")
        
    try:
        # make a set of the relative filepaths in the only these file
        only_these = set()
        if only_these_file:
            with open(only_these_file[0], "r", encoding="utf8") as file:
                for line in file:
                    only_these.add(line.replace("\n",""))
                    
        # creates an object that records tooling runs and sends out emails to indicate when things have run
        print("Creating Tracker objects.")
        maillogin = ['AKIA6MYNKSLTF4CMKS4L', 'BFxgt15QWemeGTUknhoJxUsTHf5YiKn8JyvuKFeljMca', 'memoq@segaamerica.com']
        mail_handler = mailClient('10.30.100.69', maillogin[0], maillogin[1], maillogin[2])
        curmonitor = ToolMonitor(maillogin, preferences)
        tooltracker = Tracker.create_empty(preferences,
                                        Path(r"resources"),
                                        preferences.memoQ_folder / "XLIFF Backups",
                                        maillogin, preferences.churn_alert_email_list)
        
        # creates a database of xliff files that are located in memoQ
        print("Creating memoQ Database.")
        memoQDB = MemoQDatabase(preferences)
        curmonitor.add_event("Created memoQ DB.")
        
        #backup_status_dict - used for email reporting on xliff backup, churn json, rough t json, rough e json
        
        if export_memoQ:
            print("Exporting memoQ files.")
            memoQDB.export_all_files(only_these)
                
        if github:
            backup_status_dict = {"github_backup":False,"churn_json":False,"rough_t":False,"rough_e":False}
            #Add R2-complete files to github backup folder
            for outbox_file in memoQDB.output_folder.rglob("*.xliff"):
                rel_path = Path(str(outbox_file.relative_to(memoQDB.output_folder))[:-6])#relative path without extension
                if rel_path in memoQDB.file_statuses.keys():
                    if memoQDB.file_statuses[rel_path] in memoQDB.Review1CompleteStatuses:
                        parentFolder = outbox_file.relative_to(memoQDB.output_folder).parent
                        new_dir = str(preferences.github_backup_folder)+"\\"+str(parentFolder)
                        if not os.path.exists(new_dir):
                            os.makedirs(new_dir)
                        copy2(str(outbox_file.absolute()),new_dir)

            github_backup_return_status = 0
            backup_status_dict["github_backup"] = True if github_backup_return_status == 0 else False

            churn_json_return_status = add_backups_to_churn_data.add_to_data("ja","en",preferences.churn_db,preferences.github_backup_folder)
            backup_status_dict["churn_json"] = True if churn_json_return_status == 0 else False

            #Tracking whether the XLIFF backup functions ran into any issues deleting files
            deletion_statuses = []

            rough_t_return_status = add_rough_TL_to_churn_file.add_to_data("ja","en",preferences.rough_t_db, preferences.rough_t_xliff_folder)
            backup_status_dict["rough_t"] = True if rough_t_return_status == 0 else False
            if backup_status_dict["rough_t"]:
                deletion_statuses.append(add_rough_TL_to_churn_file.clear_folder(Path(preferences.rough_t_xliff_folder)))

            rough_e_return_status = add_rough_ED_to_churn_file.add_to_data("ja","en",preferences.rough_e_db, preferences.rough_e_xliff_folder)
            backup_status_dict["rough_e"] = True if rough_e_return_status == 0 else False
            if backup_status_dict["rough_e"]:
                deletion_statuses.append(add_rough_ED_to_churn_file.clear_folder(Path(preferences.rough_e_xliff_folder)))

            json_backup_return_status = backup_xliffs_to_github.github_backup(preferences.churn_db_location)
            backup_status_dict["json_backup"] = True if json_backup_return_status == 0 else False


        print("Pulling down changes from SVN server.")
        svnHandler = Handler(preferences.textbridge_repo_location)
        
        if update_svn:
            svnHandler.update_to_latest()
            curmonitor.add_event("Updated local SVN repo.")
        else:
            curmonitor.add_event("Did not update local SVN repo.")

        # creates two databases; one for Lxtxt files (non-voiced files) and a seperate DB for lxvbf files which are voiced
        print("Creating LXTXT Database.")
        lxtxtDB = LXTXTDatabase(preferences.textbridge_repo_location)

        # takes a dict snapshot of asian languages in order to compare to files being committed
        asn_lang_snapshot1 = lxtxtDB.asian_lang_db_snapshot()

        if novoice:
            lxvbfDB = None
            print("LXVBF Database not created.")
        else:
            lxvbfDB = LXVBFDatabase(preferences)
            print("Creating LXVBF Database created.")
        curmonitor.add_event("Created LXTXT + LXVBF DBs.")

        # creates a conflict checker 
        conflict_checker = ConflictChecker(preferences.conflict_check_db, 
                                  memoQDB, 
                                  lxtxtDB, 
                                  preferences.conflict_check_template,
                                  preferences.conflict_check_excel,
                                  'en',
                                  preferences,
                                  svnHandler,
                                  update_svn=False,
                                  lxvbfDB=lxvbfDB)
        
        compliance_checker = ComplianceChecker(preferences, mail_handler)
        curmonitor.add_event("Created Conflict and Compliance checkers.")

        # creates a converter object that has the capability to convert XLIFF -> LXTXT/LXVBF or LXTXT/LXVBF -> XLIFF
        print("Creating converter.")
        fileConverter = FileConverter(lxtxtDB, lxvbfDB, memoQDB, Language.Japanese, Language.English, tooltracker, preferences, conflict_checker, novoice, compliance_checker)
        fileConverter.populate_memoQ_xliff_dicts()
        curmonitor.add_event("Created converter object.")

        if push_into_TextBridge:
            # updating svn/textbridge database with memoQ translations and data
            # the list added arguement in update_dbs causes the method to ignore that file
            print("Porting XLIFF data into the LXTXT Database.")
            fileConverter.update_DBs(only_these)
            curmonitor.add_event("Ported English text into lxtxtDB.")

            # create a second asian language snap shot to compare to the first 
            # before confirming that you can commit the files to textbridge
            asn_lang_snapshot2 = lxtxtDB.asian_lang_db_snapshot()

            if asn_lang_snapshot1 == asn_lang_snapshot2:
                print('Asian language check confirmed.')
                # makes updates save inside of svn/textbridge
                print("Pushing changes to Text Bridge")
                fileConverter.save_changes(novoice)
                curmonitor.add_event("Lxtxt DB files saved.")

            # The files have been updated and saved 
            if update_svn:
                print("Committing to SVN.")
                svnHandler.commit_changes("Automated commit from SOA. Please contact dan.sunstrum@segaamerica.com if any issues arise.")
                curmonitor.add_event("Changes committed to SVN.")
            else:
                curmonitor.add_event("Changes not committed to SVN.")

            # backs up xliff data in an archive folder not connected to memoQ    
            print("Backing up XLIFF data.")
            memoQDB.backup_output("")
            curmonitor.add_event("Backed up XLIFF data.")

        # if you would like the files that were exported from memoQ to stay in the outbox keep as True
        if not preserve_exported_files:
            print("Clearing out output folders.")
            memoQDB.clear_output()
            curmonitor.add_event("Cleared out output folders.")
        else:
            ("Output folders not cleared.")

        #if you would like new data to be imported into memoQ make True
        if pull_into_memoQ:
            print("Converting LXTXT data to XLIFF for memoQ.")
            fileConverter.convert_to_xliff(only_these, True)
            curmonitor.add_event("Converted LXTXT data to XLIFF.")

            # remove files from memoQ that have had their corresponding lxtxt/lxvbf deleted
            #print("Removing deleted files.")
            #fileConverter.remove_deleted_files()
            #curmonitor.add_event("Removed deleted files.")
        else:
            print("memoQ conversion skipped.")

        if reporting:

            # reporting center is the location of a global tool called Frost used on all projects for reporting visualizaiton
            #print("Connecting to reporting ceneter.")
            #reporting_center = ReportingCenter(preferences.reporting_center_root, preferences.memoQ_project_name, preferences)

            # Reporting: Updates json database from memoQ API and creates report on progress
            # creates a qlink reporter object which utilizes the memoQ API to get accurate reporting data directly from memoQ
            print("Creating QLink Reporting Tool")
            curmonitor.add_event("QLink reporter created.")
            qlar = QlinkAnalyzerReporter(preferences, ["testUN","testPW","testFromAdd"], backup_status_dict=None)
            print("Updating QLink data.")
            qlar.update_qlinkdb()
            if send_emails:
                print("Creating QLink report.")
                qlar.create_report([preferences.project_codename], deletion_statuses=None)
                curmonitor.add_event("Qlink report created.")

            # Reporting: Sends email if changes logged.
            if tooltracker.changes_logged() and send_emails:
                print("Exporting and sending summary of logged changes.")
                tooltracker.export_summary()
                curmonitor.add_event("Tooltracker summary emailed.")

            conflict_checker.create_conflict_report()
            
            if compliance_checker.noncompliant_strings_found() and send_emails:
                compliance_checker.send_report()
            # Reporting: Deliver new reporting to reporting center
            #print("Copying reporting data to Frost.")
            #reporting_center.current_report.copy_data_to_center()
            #curmonitor.add_event("Reporting data sent to Frost.")

    except Exception as e:
        if send_emails:
            print("Sending Unhandled Exception Email...")
            exception_email_template = preferences.resources_location / 'qlink' / "error_email_template.txt"
            with open(str(exception_email_template), 'r') as myfile:
                template = myfile.read()
            email_data = template.format(error_traceback = traceback.format_exc())
            for email in preferences.tool_admin_email_list:
                mail_handler.send_HTML_message_with_image(email, "[%s] Loclink Unhandled Exception" % preferences.project_codename, email_data)
        else:
            raise e

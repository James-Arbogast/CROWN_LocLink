'''
Class that works with a database to analyze data and send out reports.

'''

from datetime import datetime, timedelta, date
from pathlib import Path
from sqlite3 import Timestamp
from turtle import width
from typing import List
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from pandas.tseries.offsets import BDay
import pandas as pd
from util.data_tracking.mailClient import mailClient
from util.data_tracking.pretty_html_table import build_table
from util.qlink_service.QlinkProgressDatabase import QLinkProgressTracker
from util.qlink_service.QLinkService import QLinkService
from util.preferences.preferences import Preferences
import sys
import base64
from util.data_tracking.ChurnTracker import Churn_Tracker

class QlinkAnalyzerReporter:
    def __init__(self, preferences: Preferences, loginlist: List, backup_status_dict: dict):
        self.preferences = preferences
        self.project_name = preferences.project_codename
        self.resource_dir = preferences.resources_location
        self.progress_data_by_date = {}
        self.qlinkdb = QLinkProgressTracker.from_json(preferences) # / "qlink_database.json"
        self.qlinkdb.check_file_exist(preferences.textbridge_repo_location,preferences.project_codename,preferences.loclink_created_files)
        self.qlinkdb.check_file_voiced(preferences.textbridge_repo_location, preferences.project_codename)
        self.qlinkdb.check_file_voice_only(preferences.textbridge_repo_location, preferences.project_codename)
        self.template = self.resource_dir / 'qlink' / "progress_track_template.txt" # /  "report_template_image.txt"
        self.email_un = loginlist[0]
        self.email_pw = loginlist[1]
        self.fromAdd = loginlist[2]
        self.notifyemails = preferences.progress_alert_email_list
        self.admin_email_list = preferences.tool_admin_email_list
        self.testTotals = {}
        self.backup_statuses = backup_status_dict
        self.memoQ_server_address = preferences.memoQ_server_address
        self.voice_only_folder = preferences.voice_only_folder

    def update_qlinkdb(self):
        self.qlinkdb.update_via_qlink()
        self.qlinkdb.save_json()

    def total_JPC(self, targetdatetime, projName: str):
        # add total JPC for snapshots that were current as of that date:
        return sum([fileentry.character_count for fileentry in self.qlinkdb.progress_data[projName] if fileentry.still_exists])

    def voice_only_JPC(self, projName: str):
        return sum([fileentry.ready_count for fileentry in self.qlinkdb.progress_data[projName] if fileentry.voice_only and fileentry.still_exists])

    def list_total_JPC(self, projName: str):
        # creates a dict of {date:total JPC} for all dates in project
        return {date_entry: self.total_JPC(date_entry) for date_entry in self.qlinkdb.data_by_date(projName)}

    def calculate_total_completed_JPC(self, targetdate, projName: str):
        self.last_updated = datetime.now()
        qlink_service = QLinkService(self.memoQ_server_address)
        # go per project
        for project in self.qlinkdb.general_settings.memoQ_project_data:
            project_data = {}
            # populate GUID on first run
            if not project.ID:
                project.ID = qlink_service.name_to_GUID(project.name)
                if not project.ID:
                    raise KeyError
            # retrieve data
            project_data[project.name] = {project.usage : qlink_service.retrieve_project_file_progress_data(project.ID)}

            # repackage data so T data  and R1/R2 data are married uwu
            repackaged_data = self.qlinkdb.repackage_qlink_data(project_data)
        #return self.testTotals[projName]
        if isinstance(targetdate, datetime):
            targetdate = targetdate.date()
        # get sum of all three metrics, then divide by total JPC
        total_JPC = 0
        T_total = 0
        R1_total = 0
        R2_total = 0
        # retrieve data
        for date_data in repackaged_data:  # A list, but every entry is one file
            total_JPC += date_data.total
            T_total += date_data.confirmed_cc
            R1_total += date_data.r1_cc
            R2_total += date_data.r2_cc
        # return array
        for item in [total_JPC, T_total, R1_total, R2_total]:
            if item == 0:
                item = None
        return [int(total_JPC),
                int(T_total),
                int(R1_total),
                int(R2_total)]
    
    def calculate_voice_only_completed_JPC(self, targetdate, projName: str):
        project = self.qlinkdb.progress_data[projName]
        T_count = 0
        R1_count = 0
        R2_count = 0
        for file in project:
            if not file.voice_only or not file.still_exists:
                continue
            snap = self.qlinkdb.file_progress_on_date(projName, file.relative_filepath, targetdate.date())
            T_count += snap.T_characters
            R1_count += snap.R1_characters
            R2_count += snap.R2_characters
        return [T_count, R1_count, R2_count]


    def get_churn_report(self, targetdate, projname: str):
        if isinstance(targetdate, datetime):
            targetdate = targetdate.date()

        total_characters_added = 0
        total_characters_removed = 0
        churn_file_list = []

        project = self.qlinkdb.progress_data[projname]
        for file in project:
            for snap in file.date_entries:
                #print(snap.total_characters)
                pass
        return None

    def calculate_total_completed_game_text_json(self, targetdate, projName: str):

        if isinstance(targetdate, datetime):
            targetdate = targetdate.date()

        # get sum of all three metrics, then divide by total JPC
        total_JPC = 0
        T_total = 0
        R1_total = 0
        R2_total = 0

        full_history_data = self.qlinkdb.progress_data
        proj_data = full_history_data[projName]
        progress_data_to_add = {}

        for file in proj_data:
            if file.voice_only:
                continue
            progress_data_to_add[file.relative_filepath] = {}
            for entry in file.date_entries:
                if isinstance(entry.timestamp, datetime):
                    date = entry.timestamp.date()
                if date != targetdate:
                    continue
                progress_data_to_add[file.relative_filepath] = {'T_characters' : entry.T_characters,
                                                'R1_characters' : entry.R1_characters,
                                                'R2_characters' : entry.R2_characters,
                                                'total_characters' : entry.total_characters}

        for file in progress_data_to_add.keys():
            if 'total_characters' in progress_data_to_add[file].keys():
                total_JPC += progress_data_to_add[file]['total_characters']
            if 'T_characters' in progress_data_to_add[file].keys():
                T_total += progress_data_to_add[file]['T_characters']
            if 'R1_characters' in progress_data_to_add[file].keys():
                R1_total += progress_data_to_add[file]['R1_characters']
            if 'R2_characters' in progress_data_to_add[file].keys():
                R2_total += progress_data_to_add[file]['R2_characters']
    
        for item in [total_JPC, T_total, R1_total, R2_total]:
            if item == 0:
                item = None
        return [int(total_JPC),
                int(T_total),
                int(R1_total),
                int(R2_total)]
    
    #Includes all text, both game text and voice only
    def calculate_total_ready_JPC_json(self, targetdate, projName: str):

        if isinstance(targetdate, datetime):
            targetdate = targetdate.date()

        ready_JPC = 0
        T_total = 0
        R1_total = 0
        R2_total = 0

        proj_data = self.qlinkdb.progress_data[projName]
        progress_data_to_add = {}

        for file in proj_data:
            if file.voice_only:
                continue
            progress_data_to_add[file.relative_filepath] = {}
            file_data = self.qlinkdb.file_progress_on_date(projName, file.relative_filepath, targetdate)
            progress_data_to_add[file.relative_filepath]  = {'T_characters' : file_data.T_characters,
                                                'R1_characters' : file_data.R1_characters,
                                                'R2_characters' : file_data.R2_characters,
                                                'ready_characters' : file_data.ready_characters}

        for file in progress_data_to_add.keys():
            if 'ready_characters' in progress_data_to_add[file].keys():
                ready_JPC += progress_data_to_add[file]['ready_characters']
            if 'T_characters' in progress_data_to_add[file].keys():
                T_total += progress_data_to_add[file]['T_characters']
            if 'R1_characters' in progress_data_to_add[file].keys():
                R1_total += progress_data_to_add[file]['R1_characters']
            if 'R2_characters' in progress_data_to_add[file].keys():
                R2_total += progress_data_to_add[file]['R2_characters']
    
        return [int(ready_JPC),
                int(T_total),
                int(R1_total),
                int(R2_total)]

    def make_negative_burn_zeroes(self, array):
        for i, v in enumerate(array):
            if v < 0:
                array[i] = 0
        return array

    def calculate_burn(self, olderdate, newerdate, projName: str):
        # take the results of completion percents between two dates, then return the difference
        older_results = self.calculate_total_ready_JPC_json(olderdate,projName)
        newer_results = self.calculate_total_ready_JPC_json(newerdate,projName)
        #Include R1 and R2 burn for T, and R2 for R1
        older_results[1] += older_results[2] + older_results[3]
        older_results[2] += older_results[3]
        newer_results[1] += newer_results[2] + newer_results[3]
        newer_results[2] += newer_results[3]
        older_array = np.array(older_results)
        newer_array = np.array(newer_results)
        result = np.subtract(newer_array, older_array)
        result = self.make_negative_burn_zeroes(result)
        return result

    def calculate_avg_daily_burn_rate_bw_dates(self, old_date: datetime.date, new_date: datetime.date, projName: str):
        if isinstance(new_date, datetime):
            new_date = new_date.date()
        if isinstance(old_date, datetime):
            old_date = old_date.date()
        burn = self.calculate_burn(old_date, new_date, projName)
        day_delta = np.busday_count(old_date, new_date)
        return np.divide(burn, day_delta)

    def calculate_finish_date_T(self, projName: str):  # Uses Translation
        # use four week average
        # if less data than four weeks, use average of all possible dates
        old_date = (self.qlinkdb.last_updated - BDay(20)).date()  # 20 business days = 5d x 4weeks
        new_date = self.qlinkdb.last_updated.date()  # this only runs on business days. we OK.
        if old_date < self.qlinkdb.earliest_date(projName):
            old_date = self.qlinkdb.earliest_date(projName)
        if new_date <= old_date:
            return None
        # get average daily burn between today and that date
        average_daily_burn = self.calculate_avg_daily_burn_rate_bw_dates(old_date,
                                                                         new_date,projName)  # Returns a list of [T, R1, R2]
        # #determine JPC remaining
        # PRF: Calculate by Translation
        average_T_burn = average_daily_burn[1]
        current_progress = self.calculate_total_ready_JPC_json(self.qlinkdb.last_updated,projName)
        translated_JPC = current_progress[1] + current_progress[2] + current_progress[3]
        JPC_remaining = current_progress[0] - translated_JPC

        # #determine date to complete
        if average_T_burn > 0:
            days_left = JPC_remaining / average_T_burn
            return np.busday_offset(self.qlinkdb.last_updated.date(), days_left, roll='forward')
        else:
            return None

    def calculate_finish_date_R1(self, projName: str):  # Uses Translation
        # use four week average
        # if less data than four weeks, use average of all possible dates
        old_date = (self.qlinkdb.last_updated - BDay(20)).date()  # 20 business days = 5d x 4weeks
        new_date = self.qlinkdb.last_updated.date()  # this only runs on business days. we OK.
        if old_date < self.qlinkdb.earliest_date(projName):
            old_date = self.qlinkdb.earliest_date(projName)
        if new_date <= old_date:
            return None
        # get average daily burn between today and that date
        average_daily_burn = self.calculate_avg_daily_burn_rate_bw_dates(old_date,
                                                                         new_date,projName)  # Returns a list of [T, R1, R2]
        # #determine JPC remaining
        # PRF: Calculate by Translation
        average_T_burn = average_daily_burn[2]
        current_progress = self.calculate_total_ready_JPC_json(self.qlinkdb.last_updated,projName)
        translated_JPC = current_progress[2] + current_progress[3]
        JPC_remaining = current_progress[0] - translated_JPC

        # #determine date to complete
        if average_T_burn > 0:
            days_left = JPC_remaining / average_T_burn
            return np.busday_offset(self.qlinkdb.last_updated.date(), days_left, roll='forward')
        else:
            return None

    def calculate_finish_date_R2(self, projName: str):  # Uses Translation
        # use four week average
        # if less data than four weeks, use average of all possible dates
        old_date = (self.qlinkdb.last_updated - BDay(20)).date()  # 20 business days = 5d x 4weeks
        new_date = self.qlinkdb.last_updated.date()  # this only runs on business days. we OK.
        if old_date < self.qlinkdb.earliest_date(projName):
            old_date = self.qlinkdb.earliest_date(projName)
        if new_date <= old_date:
            return None
        # get average daily burn between today and that date
        average_daily_burn = self.calculate_avg_daily_burn_rate_bw_dates(old_date,
                                                                         new_date,projName)  # Returns a list of [T, R1, R2]
        # #determine JPC remaining
        # PRF: Calculate by Translation
        average_T_burn = average_daily_burn[3]
        current_progress = self.calculate_total_ready_JPC_json(self.qlinkdb.last_updated,projName)
        translated_JPC = current_progress[3]
        JPC_remaining = current_progress[0] - translated_JPC

        # #determine date to complete
        if average_T_burn > 0:
            days_left = JPC_remaining / average_T_burn
            return np.busday_offset(self.qlinkdb.last_updated.date(), days_left, roll='forward')
        else:
            return None

    def save_four_week_plot(self, projName: str, T_finish_date, R1_finish_date, R2_finish_date):
        plot_dates = []  # list of values
        plot_JPCdata_total = []  # list of values
        plot_unTdata_total = []
        plot_JPCdata_remaining_T = []  # list of values
        plot_JPCdata_remaining_R1 = []  # list of values
        plot_JPCdata_remaining_R2 = []  # list of values

        # list of target dates
        old_date = self.qlinkdb.last_updated - BDay(20)  # 20 business days = 5d x 4weeks
        old_date = old_date.date()
        new_date = self.qlinkdb.last_updated.date()  # this only runs on business days. we OK.
        graph_dates = [old_date + timedelta(days=x) for x in range((new_date - old_date).days + 1)]

        current_ready_volume = self.calculate_total_ready_JPC_json(new_date, projName)[0]

        # add data to those lists
        for snapshot_date in graph_dates:
            # X axis.
            plot_dates.append(snapshot_date)
            # Y axis.
            # Data for that date.
            curdate_burn_data = self.calculate_total_ready_JPC_json(snapshot_date,projName)
            plot_JPCdata_total.append(curdate_burn_data[0])
            plot_unTdata_total.append(current_ready_volume - curdate_burn_data[1] - curdate_burn_data[2] - curdate_burn_data[3])
            plot_JPCdata_remaining_T.append(current_ready_volume - curdate_burn_data[1] - curdate_burn_data[2] - curdate_burn_data[3])
            plot_JPCdata_remaining_R1.append(current_ready_volume - curdate_burn_data[2] - curdate_burn_data[3])
            plot_JPCdata_remaining_R2.append(current_ready_volume - curdate_burn_data[3])

        fig, ax = plt.subplots()
        #print(projName)
        #ax.set_title('%s Project Volume' % self.project_name)
        ax.set_title('%s Project Volume' % projName)
        ax.set_xlabel('Date')
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m-%d"))
        ax.set_ylabel('JPC')
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ',')))
        ax.plot(plot_dates, plot_JPCdata_total, color='red', label="Ready JPC")
        ax.plot(plot_dates, plot_JPCdata_remaining_T, color='blue', label="T Remaining")
        ax.plot(plot_dates, plot_JPCdata_remaining_R1, color='orange', label="R1 Remaining")
        ax.plot(plot_dates, plot_JPCdata_remaining_R2, color='green', label="R2 Remaining")
        #Plot expected completion dates at current four-week average burn rate
        if T_finish_date != None:
            ax.plot([self.qlinkdb.last_updated.date(),T_finish_date],[plot_JPCdata_remaining_T[-1],0],color='blue',dashes=(2,5),alpha=0.75)
        if R1_finish_date != None:
            ax.plot([self.qlinkdb.last_updated.date(),R1_finish_date],[plot_JPCdata_remaining_R1[-1],0],color='orange',dashes=(2,5),alpha=0.75)
        if R2_finish_date != None:
            ax.plot([self.qlinkdb.last_updated.date(),R2_finish_date],[plot_JPCdata_remaining_R2[-1],0],color='green',dashes=(2,5),alpha=0.75)

        #This is necessary so the Y-axis label doesn't get cut off
        fig.tight_layout()

        plt.xlim(left=(datetime.today() - timedelta(days=28)),
                 right=(datetime.today() + timedelta(days=14)))
        plt.ylim(bottom=0)
        plt.legend()
        plt.savefig(self.resource_dir / 'reporting_center' / f"{projName}_four_week_fig.png")
        with open(self.resource_dir / 'reporting_center' / f"{projName}_four_week_fig.png", "rb") as image:
            encoded_string = base64.b64encode(image.read())
        decoded_string = encoded_string.decode('utf-8')
        return '<img src="data:image/png;base64,' + decoded_string + '"/>'

    def create_report(self,projNames: list,deletion_statuses: list): #returns report, which will be later sent in a combined report email
        churny = Churn_Tracker(r'M:\Projects\Crown\Tooling\CROWN_LocLink\resources\churn_data\preferences_crown.json')
        # All numbers have been fixed.
        # Do calculations for notification email.
        self.qlinkdb.fix_character_totals(self.project_name)
        with open(str(self.template), 'r') as myfile:
            template = myfile.read()
        # Total
        dataDict = {}
        readyDict = {}
        graphDict = {}
        churnDict = {}
        for pName in projNames:
            #Ready JPC
            current_ready = self.qlinkdb.get_ready_jpc(pName)
            #Voice Only JPC
            current_voice_only = self.voice_only_JPC(pName)
            #Game Text JPC
            current_game_text = current_ready - current_voice_only
            # Finished JPC: [total_JPC, T_total, R1_total, R2_total]
            game_text_complete = self.calculate_total_completed_game_text_json(self.qlinkdb.last_updated, pName)
            voice_only_complete = self.calculate_voice_only_completed_JPC(self.qlinkdb.last_updated, pName)

            #current_complete = [500,300,100,100]
            finished_JPC_string_T = "{:,}".format(int(game_text_complete[3]) + int(game_text_complete[2]) + int(game_text_complete[1]))
            finished_JPC_string_R1 = "{:,}".format(int(game_text_complete[2]) + int(game_text_complete[3]))
            finished_JPC_string_R2 = "{:,}".format(int(game_text_complete[3]))
            #Percent Ready Complete
            if current_ready > 0:
                pct_ready_complete = (int(game_text_complete[3]) + int(game_text_complete[2]) + int(game_text_complete[1])) / current_game_text
                pct_ready_R1 = (int(game_text_complete[3]) + int(game_text_complete[2])) / current_game_text
                pct_ready_R2 = int(game_text_complete[3]) / current_game_text

            else:
                pct_ready_complete = 0
                pct_ready_R1 = 0
                pct_ready_R2 = 0

            #Percent Voice Only Complete
            if current_voice_only > 0:
                voice_only_T_JPC = voice_only_complete[0] + voice_only_complete[1] + voice_only_complete[2]
                voice_only_R1_JPC = voice_only_complete[1] + voice_only_complete[2]
                voice_only_R2_JPC = voice_only_complete[2]
                pct_voice_only_T = voice_only_T_JPC / current_voice_only
                pct_voice_only_R1 = voice_only_R1_JPC / current_voice_only
                pct_voice_only_R2 = voice_only_R2_JPC / current_voice_only
            else:
                voice_only_T_JPC = 0
                voice_only_R1_JPC = 0
                voice_only_R2_JPC = 0
                pct_voice_only_T = 0
                pct_voice_only_R1 = 0
                pct_voice_only_R2 = 0

            pct_ready_complete_string = "{:.1%}".format(pct_ready_complete)
            pct_ready_R1_string = "{:.1%}".format(pct_ready_R1)
            pct_ready_R2_string = "{:.1%}".format(pct_ready_R2)

            voice_only_T_JPC_string = "{:,}".format(voice_only_T_JPC)
            voice_only_R1_JPC_string = "{:,}".format(voice_only_R1_JPC)
            voice_only_R2_JPC_string = "{:,}".format(voice_only_R2_JPC)
            pct_voice_only_T_string = "{:.1%}".format(pct_voice_only_T)
            pct_voice_only_R1_string = "{:.1%}".format(pct_voice_only_R1)
            pct_voice_only_R2_string = "{:.1%}".format(pct_voice_only_R2)
            # Average Daily Team Burn (5 Days)
            avg_week = self.calculate_avg_daily_burn_rate_bw_dates(self.qlinkdb.last_updated - BDay(5),
                                                                self.qlinkdb.last_updated,pName)
            avg_week_string_T = "%s" % "{:,}".format(int(avg_week[1]))
            avg_week_string_R1 = "%s" % "{:,}".format(int(avg_week[2]))
            avg_week_string_R2 = "%s" % "{:,}".format(int(avg_week[3]))
            # Average Daily Team Burn (4 weeks)
            avg_month = self.calculate_avg_daily_burn_rate_bw_dates(self.qlinkdb.last_updated - BDay(20),
                                                                    self.qlinkdb.last_updated,pName)
            avg_month_string_T = "{:,}".format(int(avg_month[1]))
            avg_month_string_R1 = "{:,}".format(int(avg_month[2]))
            avg_month_string_R2 = "{:,}".format(int(avg_month[3]))
            # Estimated Completion Date
            T_finish_date = self.calculate_finish_date_T(pName)
            R1_finish_date = self.calculate_finish_date_R1(pName)
            R2_finish_date = self.calculate_finish_date_R2(pName)
            progress_graph = self.save_four_week_plot(pName, T_finish_date, R1_finish_date, R2_finish_date)
            
            # Churn Data
            if churny:
                # Returns dictionary of churn data
                churn_report = churny.full_report()

            ready_data = {1: ["Total JPC", "{:,}".format(current_ready)],
                        7: ["Game Text", "{:,}".format(current_game_text)],
                        8: ["Voice Only", "{:,}".format(current_voice_only)]}
            table_data = {3: ["Game Text Progress", pct_ready_complete_string, pct_ready_R1_string, pct_ready_R2_string],
                        2: ["Game Text JPC", finished_JPC_string_T, finished_JPC_string_R1, finished_JPC_string_R2],
                        9: ["Voice Only Progress", pct_voice_only_T_string, pct_voice_only_R1_string, pct_voice_only_R2_string],
                        10: ["Voice Only JPC", voice_only_T_JPC_string, voice_only_R1_JPC_string, voice_only_R2_JPC_string],
                        4: ["Average Daily Team Burn (last 5 days)", avg_week_string_T, avg_week_string_R1, avg_week_string_R2],
                        5: ["Average Daily Team Burn (last 4 weeks)", avg_month_string_T, avg_month_string_R1, avg_month_string_R2],
                        6: ["Estimated Completion Date", T_finish_date, R1_finish_date, R2_finish_date]}
            churn_data = {11: ["Total Churn", churn_report['Total']],
                        12: ["Total Churn - No DESC", churn_report['Total No DESC']],
                        13: ["Total Voiced Churn", churn_report['Total Voiced']],
                        14: ["Total Non-Voiced Churn", churn_report['Total Non-Voiced']],
                        15: ["Weekly Churn", churn_report['Weekly']],
                        16: ["Weekly DESC Churn", churn_report['Weekly DESC']],
                        17: ["Weekly Voiced Churn", churn_report['Weekly Voiced']],
                        18: ["Weekly Non-Voiced No DESC Churn", churn_report['Weekly Non-Voiced No DESC']],
                        19: ["Daily Churn", churn_report['Daily']],
                        20: ["Daily DESC Churn", churn_report['Daily DESC']],
                        21: ["Daily Voiced Churn", churn_report['Daily Voiced']],
                        22: ["Daily Non-Voiced No DESC Churn", churn_report['Daily Non-Voiced No DESC']],
                        }
            
            readyframe = pd.DataFrame.from_dict(ready_data, orient='index', columns=["Metric", "JPC"])
            dataframe = pd.DataFrame.from_dict(table_data, orient='index', columns=["Metric", "Count (T)", "Count (R1)", "Count (R2)"])
            churnframe = pd.DataFrame.from_dict(churn_data, orient='index', columns=["Metric", "JPC"])
            printtable = build_table(dataframe, 'orange_light', font_size="small", font_family='Calibri')
            readytable = build_table(readyframe, 'orange_light', font_size="small", font_family='Calibri')
            churntable = build_table(churnframe, 'orange_light', font_size="small", font_family='Calibri')
            dataDict[pName] = table_data
            readyDict[pName] = ready_data
            graphDict[pName] = printtable
            churnDict[pName] = churntable
            graphDict[pName + "_ready"] = readytable

        """readyboy = ready_template.format(totalJPC = readyDict[1][1],
                                            readyJPC = readyDict[2][1],
                                            readyDoneT = readyDict[3][1],
                                            readyDoneR1 = readyDict[4][1],

                                            totalPercent = readyDict[1][2],
                                            readyPercent = readyDict[2][2],
                                            readyDoneTPercent = readyDict[3][2],
                                            readyDoneR1Percent = readyDict[4][2])"""
        # slot data into message template.
        #data = {"progress-data": printtable, "project-name": self.project_name}
        databoy = template.format(#totalVunT = dataDict[self.project_name][1][1], #V = Voiced, U = Unvoiced
                                            progress_graphV = progress_graph, 
                                            progress_dataV = graphDict[self.project_name],
                                            progress_readydata = graphDict[self.project_name + "_ready"],
                                            progress_churn = churnDict[self.project_name],

                                            #github_backup_status = "Success" if self.backup_statuses["github_backup"] else "Failed",
                                            #churn_json_status = "Success" if self.backup_statuses["churn_json"] else "Failed",
                                            #rough_t_status = "Success" if self.backup_statuses["rough_t"] else "Failed",
                                            #rough_e_status = "Success" if self.backup_statuses["rough_e"] else "Failed",
                                            #json_backup_status = "Success" if self.backup_statuses["json_backup"] else "Failed",
                                            #backup_status_color = "green" if self.backup_statuses["github_backup"] else "red",
                                            #churn_status_color = "green" if self.backup_statuses["churn_json"] else "red",
                                            #rough_t_status_color = "green" if self.backup_statuses["rough_t"] else "red",
                                            #rough_e_status_color = "green" if self.backup_statuses["rough_e"] else "red",
                                            #json_backup_status_color = "green" if self.backup_statuses["json_backup"] else "red",
                                            
                                            #tl_deletion_status = deletion_statuses[0],
                                            #ed_deletion_status = deletion_statuses[1]) 
                                )
        mail_handler = mailClient('10.30.100.69', 'AKIA6MYNKSLTF4CMKS4L', 'BFxgt15QWemeGTUknhoJxUsTHf5YiKn8JyvuKFeljMca', 'memoq@segaamerica.com')
        
        for email in self.notifyemails:
            mail_handler.send_HTML_message(email, "[%s] Progress Update" % self.project_name, databoy)
        
        print("QLink report sent!")

    def send_progress_report(self):
        # All numbers have been fixed.
        # Do calculations for notification email.
        with open(str(self.template), 'r') as myfile:
            template = myfile.read()
        # Total
        current_total = int(self.total_JPC(self.qlinkdb.last_updated))
        # Finished JPC
        current_complete = self.calculate_total_completed_JPC(self.qlinkdb.last_updated)
        finished_JPC_string_T = "{:,}".format(int(current_complete[1]))
        finished_JPC_string_R1 = "{:,}".format(int(current_complete[2]))
        # Percent Complete
        pct_complete = current_complete[1] / current_total
        pct_complete_string_T = "{:.1%}".format(pct_complete)
        pct_complete_R1 = current_complete[2] / current_total
        pct_complete_string_R1 = "{:.1%}".format(pct_complete_R1)
        # Average Daily Team Burn (5 Days)
        avg_week = self.calculate_avg_daily_burn_rate_bw_dates(self.qlinkdb.last_updated - BDay(5),
                                                               self.qlinkdb.last_updated)
        avg_week_string_T = "%s" % "{:,}".format(int(avg_week[1]))
        avg_week_string_R1 = "%s" % "{:,}".format(int(avg_week[2]))
        # Average Daily Team Burn (4 weeks)
        avg_month = self.calculate_avg_daily_burn_rate_bw_dates(self.qlinkdb.last_updated - BDay(20),
                                                                self.qlinkdb.last_updated)
        avg_month_string_T = "{:,}".format(int(avg_month[1]))
        avg_month_string_R1 = "{:,}".format(int(avg_month[2]))
        # Estimated Completion Date (
        table_data = {1: ["Total JPC", "{:,}".format(current_total), "{:,}".format(current_total)],
                      2: ["Finished JPC", finished_JPC_string_T, finished_JPC_string_R1],
                      3: ["% Complete", pct_complete_string_T, pct_complete_string_R1],
                      4: ["Average Daily Team Burn (last 5 days)", avg_week_string_T, avg_week_string_R1],
                      5: ["Average Daily Team Burn (last 4 weeks)", avg_month_string_T, avg_month_string_R1],
                      6: ["Estimated Completion Date", self.calculate_finish_date_T(), self.calculate_finish_date_R1()]}
        dataframe = pd.DataFrame.from_dict(table_data, orient='index', columns=["Metric", "Count (T)", "Count (R1)"])
        printtable = build_table(dataframe, 'orange_light', font_size="small", font_family='Calibri')
        # slot data into message template.
        data = {"progress-data": printtable, "project-name": self.project_name}
        databoy = template.format(**data)
        # Generate image
        self.save_four_week_plot()
        # Send as email
        mail_handler = mailClient('10.30.100.69', self.email_un, self.email_pw, self.fromAdd)
        for email in self.notifyemails:
            mail_handler.send_HTML_message_with_image(email, "[%s] Progress Update" % self.project_name,
                                                      databoy, self.resource_dir / "Crown_four_week_fig.png")

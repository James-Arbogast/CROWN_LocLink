# Progress Reporter is a class that stores data in a .csv file and calculates burn / progress.

from datetime import datetime, timedelta
from pathlib import Path
from tokenize import String
from typing import Dict, List
import csv
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from util.data_tracking.mailClient import mailClient
import pandas as pd
from util.data_tracking.pretty_html_table import build_table
from math import floor



class StatSnapshot:
    def __init__(self, snapshot_date: datetime, total_JPC: int, finished_JPC: int):
        self.snapshot_date = snapshot_date.date()
        self.total_JPC = total_JPC
        self.finished_JPC = finished_JPC

    @classmethod
    def create_new(cls, total_JPC: int, finished_JPC: int):
        snap = StatSnapshot(datetime.now(), total_JPC, finished_JPC)
        return snap

    @classmethod
    def from_csv_data(cls, row: List):
        try:
            snap = StatSnapshot(datetime.strptime(row[0], '%Y-%m-%d'), int(row[1]), int(row[2]))
            return snap
        except IndexError:
            return cls.create_new(0,0)


# noinspection PyTypeChecker
class ProgressReporter:
    def __init__(self, resource_dir: Path, loginlist: List, notifylist: List, deadline: Dict, codename: String):
        self.resource_dir = resource_dir
        self.csv_file = self.resource_dir / "progress_data.csv"
        self.template = self.resource_dir / "progress_track_template_image.txt"
        self.codename = codename
        self.data = []
        self.most_recent = None
        self.previous = None
        self.desired_date = datetime(deadline["year"], deadline["month"], deadline["day"])
        self.data_by_date = {}
        self.email_un = loginlist[0]
        self.email_pw = loginlist[1]
        self.fromAdd = loginlist[2]
        self.notifyemails = notifylist
        self.read_csv_data()
        self.update()

    def update(self):
        try:
            self.data_by_date = {shot.snapshot_date: shot for shot in self.data}
            self.most_recent = self.data[-1]
            self.previous = self.data[-2]
        except IndexError: #If there's no data.
            pass

    def add_new_snapshot_data(self, datalist: List):
        totalJPC = datalist[0] + datalist[2]
        finishedJPC = datalist[1] + datalist[3]
        self.data.append(StatSnapshot.create_new(totalJPC, finishedJPC))
        self.update()

    def read_csv_data(self):
        with open(self.csv_file, 'r', newline='') as csvdata:
            csvreader = csv.reader(csvdata, delimiter=' ', quotechar='|')
            for row in csvreader:
                self.data.append(StatSnapshot.from_csv_data(row))

    def save_csv_data(self):
        with open(self.csv_file, 'w', newline='') as csvdata:
            csvwriter = csv.writer(csvdata, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)
            #only saves the most recent one, since it only adds one new node every time.
            for snapshot in self.data:
                csvwriter.writerow([snapshot.snapshot_date,
                                    snapshot.total_JPC,
                                    snapshot.finished_JPC])
        pass

    def calculate_completion_percent(self):
        raw_percent = self.most_recent.finished_JPC / self.most_recent.total_JPC
        percent = floor(raw_percent * 1000) / 1000
        return percent

    def calculate_avg_daily_burn_rate_bw_shots(self, NewerShot: StatSnapshot, OlderShot: StatSnapshot):
        #calculate total JPC changed
        burn_int = self.calculate_burn(NewerShot, OlderShot)
        #calculate business days
        days = np.busday_count(OlderShot.snapshot_date.date(), NewerShot.snapshot_date.date())
        return burn_int / days

    @staticmethod
    def calculate_burn(NewerShot: StatSnapshot, OlderShot: StatSnapshot):
        try:
            return NewerShot.finished_JPC - OlderShot.finished_JPC
        except AttributeError:
            return None

    def calculate_necessary_burn(self):
        # grab how many jpc are left
        remaining = self.most_recent.total_JPC - self.most_recent.finished_JPC
        # grab how many business days to self.desired_date
        today = datetime.now()
        desired_days = np.busday_count(today.date(),self.desired_date.date())
        # calculate needed jpc/day to get to self.desired date
        necessary_burn = remaining / desired_days
        return int(necessary_burn)

    def calculate_avg_daily_burn_rate_bw_dates(self, new_date: datetime, old_date: datetime):
        # first, find the entry at that datetime
        try:
            NewerShot = self.data_by_date[new_date]
            OlderShot = self.data_by_date[old_date]
        except KeyError:
            return None
        total_burn = self.calculate_burn(NewerShot, OlderShot)
        days = np.busday_count(OlderShot.snapshot_date, NewerShot.snapshot_date)
        return floor(total_burn / days)

    def calculate_finish_date(self):
        #verify there are at least 2 points of data
        if len(self.data) < 2:
            return None
        #get daily average
        NewerShot = self.most_recent.snapshot_date
        CompShot = NewerShot - timedelta(days=28)
        dailyavg = self.calculate_avg_daily_burn_rate_bw_dates(NewerShot, CompShot)
        if dailyavg is None:
            dailyavg = self.calculate_avg_daily_burn_rate_bw_dates(NewerShot, NewerShot - timedelta(days=1))
        #determine #JPC remaining
        remaining = self.most_recent.total_JPC - self.most_recent.finished_JPC
        #determine how many business days to complete
        if dailyavg is None or dailyavg == 0:
            days_left = 0
        else:
            days_left = remaining / dailyavg
        if days_left > 0:
            return np.busday_offset(self.most_recent.snapshot_date, days_left, roll='forward')
        else:
            return "N/A"

    def save_four_week_plot(self):
        plot_dates = []  # list of values
        plot_JPCdata_total = []  # list of values
        plot_JPCdata_remaining = []  # list of values

        # add data to those lists
        for snapshot_date in self.data_by_date.keys():
            # if date isn't within the last four weeks, disregard
            if snapshot_date < (datetime.today().date() - timedelta(days=28)):
                continue
            # X axis.
            plot_dates.append(snapshot_date)
            # Y axis.
            plot_JPCdata_total.append(self.data_by_date[snapshot_date].total_JPC)
            plot_JPCdata_remaining.append(self.data_by_date[snapshot_date].total_JPC -
                                          self.data_by_date[snapshot_date].finished_JPC)
        fig, ax = plt.subplots()
        ax.set_title(self.codename + ' Project Volume')
        ax.set_xlabel('Date')
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m-%d"))
        ax.set_ylabel('JPC in Project')
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ',')))
        ax.plot(plot_dates, plot_JPCdata_total, color='red', label="Total JPC")
        ax.plot(plot_dates, plot_JPCdata_remaining, color='blue', label="JPC Remaining")
        # let's plot a trendline
        conv_dates = matplotlib.dates.date2num(plot_dates)
        trendline = np.polyfit(conv_dates, plot_JPCdata_remaining, 1)
        trendline_plot = np.poly1d(trendline)
        trend_dates = plot_dates
        for x in range(1, 14):
            trend_dates.append(datetime.today().date() + timedelta(days=x))
        trend_dates = matplotlib.dates.date2num(trend_dates)
        ax.plot(trend_dates, trendline_plot(trend_dates), ":", color='cornflowerblue', alpha=0.8)

        plt.xlim(left=(datetime.today().date() - timedelta(days=28)),
                 right=(datetime.today().date() + timedelta(days=14)))
        #plt.ylim(bottom=0)W
        plt.ylim(bottom = 0, top = int(self.most_recent.total_JPC * 1.1))
        #
        plt.legend()
        plt.savefig(self.resource_dir / "four_week_fig.png")

    def notify_users(self):
        with open(str(self.template), 'r') as myfile:
            template = myfile.read()
        table_data = {1:["Total JPC",self.most_recent.total_JPC],
                      2:["Finished JPC",self.most_recent.finished_JPC],
                      3:["% Complete","{:.1%}".format(self.calculate_completion_percent())],
                      4:["Yesterday's Team Burn",self.calculate_burn(self.most_recent, self.previous)],
                      5:["Average Daily Team Burn (last 5 days)",self.calculate_avg_daily_burn_rate_bw_dates(self.most_recent.snapshot_date, self.most_recent.snapshot_date - timedelta(days=7))],
                      6:["Average Daily Team Burn (last 4 weeks)",self.calculate_avg_daily_burn_rate_bw_dates(self.most_recent.snapshot_date, self.most_recent.snapshot_date - timedelta(days=28))],
                      7:["Estimated Completion Date",self.calculate_finish_date()],
                      8:["Desired Completion Date",self.desired_date.date()],
                      9:["Daily Team Burn Needed",self.calculate_necessary_burn()]}
        dataframe = pd.DataFrame.from_dict(table_data, orient='index', columns=["Metric","Count"])
        printtable = build_table(dataframe, 'orange_light', font_size="small", font_family='Calibri')
        # slot data into message template.
        data = {"progress-data": printtable}
        databoy = template.format(**data)
        # Generate image
        self.save_four_week_plot()
        #Send as email
        mail_handler = mailClient('10.30.100.69', self.email_un, self.email_pw, self.fromAdd)
        for email in self.notifyemails:
            mail_handler.send_HTML_message_with_image(email, "[" + self.codename + "] Progress Update", databoy, self.resource_dir / "four_week_fig.png")

    def create_new_csv(self):
        # create blank CSV file.
        with open(self.csv_file, 'w', newline='') as newfile:
            writer = csv.writer(newfile)


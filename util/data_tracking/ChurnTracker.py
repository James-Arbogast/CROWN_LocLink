import clr
from pathlib import Path
from Levenshtein import distance
import os
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import ticker
import re
from threading import Thread
import shutil
import pprint
from datetime import datetime, timedelta, date
import csv
import json
import subprocess
from tqdm import tqdm
import concurrent.futures
clr.AddReference(f'M:\\Voice Bridge Churn Tracker\\tools\\LxSdk')
clr.AddReference("System")

from LxSdk import LxMessageFile # type: ignore

class Churn_Tracker:

    def __init__(self, pref_path: str):
        self.pref_path = pref_path
        self.textbridge_tool_path = Path()
        self.data_file_path = Path()
        self.text_log = ""
        self.ignore_users = []
        self.start_revision = 0
        self.end_revision = 0
        self.hi_rev_dict = {}
        self.vo_dict = {}
        self.appending = False
        self.most_recent_rev = 0
        self.textbridge_repo_path_1 = Path()
        self.textbridge_repo_path_2 = Path()
        self.textbridge_repo_path_3 = Path()
        self.textbridge_repo_path_4 = Path()
        self.textbridge_repo_path_5 = Path()
        self.textbridge_repo_path_6 = Path()
        self.textbridge_repo_path_7 = Path()
        self.textbridge_repo_path_8 = Path()
        self.textbridge_repo_path_9 = Path()
        self.textbridge_repo_path_10 = Path()
        self.textbridge_repo_path_11 = Path()
        self.textbridge_repo_path_12 = Path()
        self.update()
        
    def update(self):
        with open(self.pref_path, "r", encoding='utf8') as pref_file:
            json_data = json.load(pref_file)
            self.textbridge_repo_path_1 = Path(json_data["textbridge_repo_location_1"])
            self.textbridge_repo_path_2 = Path(json_data["textbridge_repo_location_2"])
            self.textbridge_repo_path_3 = Path(json_data["textbridge_repo_location_3"])
            self.textbridge_repo_path_4 = Path(json_data["textbridge_repo_location_4"])
            self.textbridge_repo_path_5 = Path(json_data["textbridge_repo_location_5"])
            self.textbridge_repo_path_6 = Path(json_data["textbridge_repo_location_6"])
            self.textbridge_repo_path_7 = Path(json_data["textbridge_repo_location_7"])
            self.textbridge_repo_path_8 = Path(json_data["textbridge_repo_location_8"])
            self.textbridge_repo_path_9 = Path(json_data["textbridge_repo_location_9"])
            self.textbridge_repo_path_10 = Path(json_data["textbridge_repo_location_10"])
            self.textbridge_repo_path_11 = Path(json_data["textbridge_repo_location_11"])
            self.textbridge_repo_path_12 = Path(json_data["textbridge_repo_location_12"])
            self.textbridge_tool_path = Path(json_data["textbridge_tool_location"])
            self.text_log = Path(json_data["text_log"])
            self.ignore_users = json_data["ignore_users"]
            self.data_file_path = Path(json_data["data_file"])
            self.start_revision = json_data["start_revision"]
            self.end_revision = json_data["end_revision"]
            self.vo_dict = self.create_vo_dict()

    def remove_non_numberics(self, s):
        return re.sub('[^0-9]+', '0', str(s))
    
    def create_vo_dict(self):
        for file in self.textbridge_repo_path_1.rglob('*.lxtxt'):
            lxtxt_file = LxMessageFile()
            lxtxt_file.LoadFromFile(str(file))
            #Create ID/JP dictionary pairs
            for row in lxtxt_file.Rows:
                if row.AttributeCells['VoiceFileName'] and row.LanguageCells['ja']:
                    self.vo_dict[row.Label] = 1
        #print(self.vo_dict)
        return self.vo_dict

    def RevisionNeedsToBeCounted(self, rev, start_revision, end_revision, path):
        '''
        if self.appending:
            fixed_path = str(path.relative_to(self.textbridge_repo_path_1))
            if fixed_path in self.hi_rev_dict:
                if int(rev) > int(self.hi_rev_dict[fixed_path]):
                    return True
                else:
                    return False 
        '''          
        #Check every revision
        if start_revision <= 0 and end_revision <= 0:
            return True
        #Only start revision specified
        if start_revision > 0 and end_revision <= 0 and rev >= start_revision:
            return True
        #Only end revision specified
        if end_revision > 0 and start_revision <= 0 and rev <= end_revision:
            return True
        #Both start and end specified
        if start_revision > 0 and end_revision > 0 and start_revision <= rev <= end_revision:
            return True
        return False

    def full_report(self):
        total_churn = self.get_churn_by_rev_range(1, 1000000, False, True)
        #print(f'Total churn: {total_churn} JPC')
        total_no_desc = self.get_churn_by_rev_range(1, 1000000, False, False)
        #print(f'Total churn (no DESC): {total_no_desc} JPC')
        total_voiced = self.get_churn_by_rev_range(1,1000000, True, False)
        #print(f'Total voiced churn: {total_voiced} JPC')
        total_non_voiced = total_churn-total_voiced
        #print(f'Total non-voiced churn: {total_non_voiced} JPC')
        weekly = self.get_churn_by_date_range((date.today()-timedelta(days=7)).strftime("%Y-%m-%d"),date.today().strftime("%Y-%m-%d"), False, True)
        #print(f'Total weekly (no desc) churn: {weekly} JPC')
        weekly_desc = weekly - self.get_churn_by_date_range((date.today()-timedelta(days=7)).strftime("%Y-%m-%d"),date.today().strftime("%Y-%m-%d"), False, False)
        #print(f'Total weekly DESC churn: {weekly_desc} JPC')
        weekly_voiced = self.get_churn_by_date_range((date.today()-timedelta(days=7)).strftime("%Y-%m-%d"),date.today().strftime("%Y-%m-%d"), True, False)
        #print(f'Total weekly voiced churn: {weekly_voiced} JPC')
        weekly_non_voiced_no_desc = weekly - (weekly_desc + weekly_voiced)
        #print(f'Total weekly non-voiced (no DESC) churn: {weekly_non_voiced_no_desc} JPC')
        daily = self.get_daily_churn(False, True)
        #print(f'Daily churn: {daily} JPC')
        daily_desc = daily - self.get_daily_churn(False, False)
        #print(f'Daily DESC churn: {daily_desc} JPC')
        daily_voiced = self.get_daily_churn(True, False)
        #print(f'Daily churn: {daily_voiced} JPC')
        daily_non_voiced_no_desc = daily - (daily_desc + daily_voiced)
        #print(f'Daily churn: {daily_non_voiced_no_desc} JPC')
        report_dict = {
            'Total' : total_churn,
            'Total No DESC' : total_no_desc,
            'Total Voiced' : total_voiced,
            'Total Non-Voiced' : total_non_voiced,
            'Weekly' : weekly,
            'Weekly DESC' : weekly_desc,
            'Weekly Voiced' : weekly_voiced,
            'Weekly Non-Voiced No DESC' : weekly_non_voiced_no_desc,
            'Daily' : daily,
            'Daily DESC' : daily_desc,
            'Daily Voiced' : daily_voiced,
            'Daily Non-Voiced No DESC' : daily_non_voiced_no_desc,
        }
        return report_dict
        


    def get_churn_by_date_range(self, start_date: str, end_date: str, voiced: bool = True, desc: bool = True):
        total_churn = 0
        date_format = r"%Y-%m-%d" 
        # format dates given in parameters
        #start_date = datetime.strptime(start_date, "%Y-%m-%d").timestamp()
        #start_date = pd.to_datetime(start_date)
        print(f'Start:{start_date}')
        #end_date = datetime.strptime(end_date, "%Y-%m-%d").timestamp()
        #end_date = pd.to_datetime(end_date)
        print(f'End:{end_date}')
        # open churn tracker db in Read mode
        data_file = open(str(self.data_file_path),"r",encoding="utf8")
        print(self.data_file_path)
        # turn txt into pandas df
        data = pd.read_csv(data_file, delimiter='\t', quoting=csv.QUOTE_NONE, encoding='utf-8', on_bad_lines='skip')
        #sort values by revision number
        data = data.sort_values(by=['Date'], ascending=True)
        # get sub df with only file revisions within date range
        data['Date'] = pd.to_datetime(data['Date'])
        #datetimes = data['Date']
        #datetimes = pd.to_datetime(data['Date'])
        
        #pprint.pprint(f'Date time series: \n{datetimes}')
        if voiced:
            filtered_df = data.loc[(data['Date'] >= start_date) & (data['Date'] <= end_date)]
            skip_first_row = True
            for index, row in filtered_df.iterrows():
                if skip_first_row:
                    skip_first_row = False
                    continue  # Skip the first row
                if row['ID'] not in self.vo_dict.keys():
                    filtered_df = filtered_df.drop(index)
        else:
            filtered_df = data.loc[(data['Date'] >= start_date) & (data['Date'] <= end_date)] 
        if not filtered_df.empty:
            for val in filtered_df['Churn']:
                total_churn+=int(val)
        return total_churn
        
    def get_churn_by_rev_range(self, start_rev: float, end_rev: float, voiced: bool = True, desc: bool = True):
        total_churn = 0
        # open churn tracker db in Read mode
        data_file = open(str(self.data_file_path),"r",encoding="utf8")
        # turn txt into pandas df
        data = pd.read_csv(data_file, delimiter='\t', encoding='utf-8', on_bad_lines='warn')
        # get sub df with only file revisions within rev range
        data['Rev'] = data['Rev'].apply(self.remove_non_numberics)
        rev_s = data['Rev'].astype(float)
        if voiced:
            if not desc:
                filtered_df = data[(rev_s >= start_rev) & (rev_s <= end_rev) & ('DESC' not in data['ID'])]
            else:
                filtered_df = data[(rev_s >= start_rev) & (rev_s <= end_rev)]
            skip_first_row = True
            for index, row in filtered_df.iterrows():
                if skip_first_row:
                    skip_first_row = False
                    continue  # Skip the first row
                if row['ID'] not in self.vo_dict.keys():
                    filtered_df = filtered_df.drop(index)
        elif not desc:
            filtered_df = data[(rev_s >= start_rev) & (rev_s <= end_rev) & ('DESC' not in data['ID'])]
        else:
            filtered_df = data[(rev_s >= start_rev) & (rev_s <= end_rev)]
        if not filtered_df.empty:
            for val in filtered_df['Churn']:
                total_churn+=int(val)
        return total_churn

    def ProcessFileList(self, folder:Path, paths:list, bar_num:int, color:str):
        main_bar_num = bar_num * 2
        sub_bar_num = bar_num * 2 + 1
        churn = 0
        churn_data = []       
        with tqdm(paths, leave = False, position = main_bar_num, colour = color) as t:
            for path in t:
                #print(str(path.relative_to(folder)).replace('\\', '\\\\'))
                #if self.appending:
                #    if str(path.relative_to(folder)).replace('\\', '\\\\') not in self.hi_rev_dict.keys():
                #        print(str(path.relative_to(folder)).replace('\\', '\\\\') + " not in hi rev dict.")
                #        continue
                t.set_description(str(path))            
                truepath = folder / path
                result = self.CalculateFileChurn(truepath, sub_bar_num, folder)
                churn += result["churn"]
                for d in result["data"]:
                    churn_data.append(d)
        return {"churn": churn, "data": churn_data}

    def get_daily_churn(self, voiced: bool = True, desc: bool = True):
        total_churn = 0
        yesterday = date.today() - timedelta(days=1)
        yesterday = yesterday.strftime("%Y-%m-%d")
        # open churn tracker db in Read mode
        data_file = open(str(self.data_file_path),"r",encoding="utf8")
        # turn txt into pandas df
        data = pd.read_csv(data_file, delimiter='\t', quoting=csv.QUOTE_NONE, encoding='utf-8', on_bad_lines='skip')
        #sort values by revision number
        if voiced:
            if not desc:
                filtered_df = data[(data['Date'] == yesterday) & ('DESC' not in data['ID'])]
            else:
                filtered_df = data[(data['Date'] == yesterday)]
            skip_first_row = True
            for index, row in filtered_df.iterrows():
                if skip_first_row:
                    skip_first_row = False
                    continue  # Skip the first row
                if row['ID'] not in self.vo_dict.keys():
                    filtered_df = filtered_df.drop(index)
        else:
            if not desc:
                filtered_df = data[(data['Date'] == yesterday) & ('DESC' not in data['ID'])]                
            else:
               filtered_df = data[(data['Date'] == yesterday)]
        if not filtered_df.empty:
            for val in filtered_df['Churn']:
                total_churn+=int(val)
        return total_churn

    def CalculateFileChurn(self, path:Path, bar_num:int, folder:Path):
        with open(self.text_log,"w",encoding="utf8") as text_log:
            text_log.flush()
            churn = 0
            try:
                log_result = subprocess.run("svn log \"" + str(path) + "\"", capture_output = True, encoding = "shift-jis")
            except:
                text_log.write("Could not fetch log for " + str(path) + "\n")
                text_log.flush()
                return {"churn": 0, "data": []}
            #test_std = ""
            #log_result = subprocess.run("svn log \"" + str(path) + "\"", stdout=test_std, encoding="utf8")
            # SAMPLE RESULT
            # CompletedProcess(args='svn log "C:\\Users\\dan.sunstrum\\Desktop\\Text Bridge\\SVN Churn Test\\db\\a01_0100.lxtxt"',
            # returncode=0,
            # stdout='------------------------------------------------------------------------\n
            # r4 | soa_dan_sunstrum | 2023-05-17 14:29:36 -0700 (Wed, 17 May 2023) | 1 line\n
            # \n
            # Corrected typo\n
            # ------------------------------------------------------------------------\n
            # r3 | soa_dan_sunstrum | 2023-05-17 14:28:56 -0700 (Wed, 17 May 2023) | 1 line\n
            # \n
            # Added VoiceBridge folder, moved text file to its own subfolder\n
            # ------------------------------------------------------------------------\n',
            # stderr='')
            revs = []
            for line in log_result.stdout.split("\n"):
                sp = line.split(" | ")
                #Look for lines with a pipe since those are the ones that have the revision numbers
                if len(sp) <= 1:
                    continue
                #If the commit is from a user we want to skip
                if sp[1] in self.ignore_users:
                    continue
                #Take the first member of the split, then everything from second character on is the revision number.
                rev = sp[0][1:]
                date = sp[2][:10]
                if self.appending:
                    fixed_path = str(path.relative_to(self.textbridge_repo_path_1))
                    if fixed_path in self.hi_rev_dict:
                        if int(rev) <= int(self.hi_rev_dict[fixed_path]):
                            continue 
                if self.RevisionNeedsToBeCounted(int(rev), self.start_revision, self.end_revision, path):
                    revs.append([rev, date])

            #If there's only one revision or no applicable revisions, skip this file
            if len(revs) <= 1:
                return {"churn": 0, "data": []}
            
            #Establish containers for old/new revisions
            old_rev = {}
            new_rev = {}

            #Pull first revision
            try:
                svn_result = subprocess.run("svn up \"" + str(path) + "\" -q -r " + str(revs[-1]), capture_output = True, encoding = "shift-jis")
            except:
                pass
            if len(svn_result.stderr) > 0:
                text_log.write(svn_result.stderr)
                text_log.flush()

            lxtxt_file = LxMessageFile()
            lxtxt_file.LoadFromFile(str(path))
            #Create ID/JP dictionary pairs
            for row in lxtxt_file.Rows:
                old_rev[row.Label] = row.LanguageCells["ja"].Text
            #We already have the oldest revision, so remove it from the list
            revs = revs[:-1]

            churn_data = []

            #For each revision beyond the first. The revisions are listed newest first, so we have to go backwards for chronological order.
            with tqdm(reversed(revs), leave = False, position = bar_num, total = len(revs)) as t:
                for rev in t:
                    t.set_description(str(rev))
                    #Pull current rev
                    subprocess.run("svn up \"" + str(path) + "\" -q -r " + str(rev[0]), capture_output = True, encoding = "shift-jis")
                    if len(svn_result.stderr) > 0:
                        text_log.write(svn_result.stderr)
                        text_log.flush()
                    new_file = LxMessageFile()
                    text_log.write(str(rev[0]) + ": " + str(path) + "\n")
                    text_log.flush()
                    new_file.LoadFromFile(str(path))
                    #Create ID/JP dictionary pairs
                    #for row in lxtxt_file.Rows:
                    new_rev = {}
                    for row in new_file.Rows:
                        new_rev[row.Label] = row.LanguageCells["ja"].Text
                    #For each ID in new rev
                    for id in new_rev.keys():
                        #Pull JP text from old/new revs
                        try:
                            old_text = old_rev[id]
                        except:
                            continue
                        new_text = new_rev[id]
                        #If text is identical
                        if old_text == new_text:
                            continue
                        #Otherwise calculate edit distance
                        #d = distance(old_text,new_text)
                        if len(old_text) > len(new_text):
                            d = len(old_text)
                        else:
                            d = len(new_text)
                        #Add to file's churn
                        churn += d
                        new_datum = ChurnDatum(str(path.relative_to(folder)), rev[0], id, old_text, new_text, d, rev[1])
                        churn_data.append(new_datum)
                    old_rev = new_rev

            #Revert file to latest state
            subprocess.run("svn up \"" + str(path) + "\" -q -r head", capture_output = True, encoding = "shift-jis")
            if len(svn_result.stderr) > 0:
                text_log.write(svn_result.stderr)
                text_log.flush()
            text_log.write(str(path) + ": " + str(churn) + "\n")
            text_log.flush()
        return {"churn": churn, "data": churn_data}

    def add_to_existing_churn_data(self): 
        self.appending = True
        # open churn tracker db in Read mode
        print('Opening data file to read')
        data_file = open(str(self.data_file_path),"r",encoding="utf8")
        # turn txt into pandas df
        print('Creating dataframe')
        df = pd.read_csv(data_file, delimiter='\t',encoding='utf-8', on_bad_lines='skip')
        # sort df by filename
        print('Sorting df by file.')
        df = df.sort_values(by=['Rev'], ascending=False)
        # create dictionary of each file and their most recent version 
        # iterrate through df and get the highest revision of each file in the existing data
        print('Populating hi rev dict')
        for index, row in df.iterrows():
            if str(row['File']) in self.hi_rev_dict.keys():
                if row['Rev'] > self.hi_rev_dict[row['File']]:        
                    self.hi_rev_dict[row['File']] = row['Rev']
                else:
                    continue
            else:
                self.hi_rev_dict[row['File']] = row['Rev']
        print('Hi Rev dict created.')
        print('Opening text log.')
        text_log = open(self.text_log,"w",encoding="utf8")   
        text_log.flush()
        
        total_churn = 0
        churn_data = []

        paths = self.textbridge_repo_path_1.rglob("*.lxtxt")
        paths1 = []
        paths2 = []
        paths3 = []
        paths4 = []
        paths5 = []
        paths6 = []
        paths7 = []
        paths8 = []
        paths9 = []
        paths10 = []
        paths11 = []
        paths12 = []

        while True:
            try:
                paths1.append(next(paths).relative_to(self.textbridge_repo_path_1))
                paths2.append(next(paths).relative_to(self.textbridge_repo_path_1))
                paths3.append(next(paths).relative_to(self.textbridge_repo_path_1))
                paths4.append(next(paths).relative_to(self.textbridge_repo_path_1))
                paths5.append(next(paths).relative_to(self.textbridge_repo_path_1))
                paths6.append(next(paths).relative_to(self.textbridge_repo_path_1))
                paths7.append(next(paths).relative_to(self.textbridge_repo_path_1))
                paths8.append(next(paths).relative_to(self.textbridge_repo_path_1))
                paths9.append(next(paths).relative_to(self.textbridge_repo_path_1))
                paths10.append(next(paths).relative_to(self.textbridge_repo_path_1))
                paths11.append(next(paths).relative_to(self.textbridge_repo_path_1))
                paths12.append(next(paths).relative_to(self.textbridge_repo_path_1))
            except:
                break
            
        svn_result = subprocess.run("svn cleanup \"" + str(self.textbridge_repo_path_1) + "\" -q", capture_output = True, encoding = "shift-jis")
        if len(svn_result.stderr) > 0:
            text_log.write(svn_result.stderr)
            text_log.flush()
        svn_result = subprocess.run("svn cleanup \"" + str(self.textbridge_repo_path_2) + "\" -q", capture_output = True, encoding = "shift-jis")
        if len(svn_result.stderr) > 0:
            text_log.write(svn_result.stderr)
            text_log.flush()
        svn_result = subprocess.run("svn cleanup \"" + str(self.textbridge_repo_path_3) + "\" -q", capture_output = True, encoding = "shift-jis")
        if len(svn_result.stderr) > 0:
            text_log.write(svn_result.stderr)
            text_log.flush()
        svn_result = subprocess.run("svn cleanup \"" + str(self.textbridge_repo_path_4) + "\" -q", capture_output = True, encoding = "shift-jis")
        if len(svn_result.stderr) > 0:
            text_log.write(svn_result.stderr)
            text_log.flush()
        svn_result = subprocess.run("svn cleanup \"" + str(self.textbridge_repo_path_5) + "\" -q", capture_output = True, encoding = "shift-jis")
        if len(svn_result.stderr) > 0:
            text_log.write(svn_result.stderr)
            text_log.flush()
        svn_result = subprocess.run("svn cleanup \"" + str(self.textbridge_repo_path_6) + "\" -q", capture_output = True, encoding = "shift-jis")
        if len(svn_result.stderr) > 0:
            text_log.write(svn_result.stderr)
            text_log.flush()
        svn_result = subprocess.run("svn cleanup \"" + str(self.textbridge_repo_path_7) + "\" -q", capture_output = True, encoding = "shift-jis")
        if len(svn_result.stderr) > 0:
            text_log.write(svn_result.stderr)
            text_log.flush()
        svn_result = subprocess.run("svn cleanup \"" + str(self.textbridge_repo_path_8) + "\" -q", capture_output = True, encoding = "shift-jis")
        if len(svn_result.stderr) > 0:
            text_log.write(svn_result.stderr)
            text_log.flush()
        svn_result = subprocess.run("svn cleanup \"" + str(self.textbridge_repo_path_9) + "\" -q", capture_output = True, encoding = "shift-jis")
        if len(svn_result.stderr) > 0:
            text_log.write(svn_result.stderr)
            text_log.flush()
        svn_result = subprocess.run("svn cleanup \"" + str(self.textbridge_repo_path_10) + "\" -q", capture_output = True, encoding = "shift-jis")
        if len(svn_result.stderr) > 0:
            text_log.write(svn_result.stderr)
            text_log.flush()
        svn_result = subprocess.run("svn cleanup \"" + str(self.textbridge_repo_path_11) + "\" -q", capture_output = True, encoding = "shift-jis")
        if len(svn_result.stderr) > 0:
            text_log.write(svn_result.stderr)
            text_log.flush()
        svn_result = subprocess.run("svn cleanup \"" + str(self.textbridge_repo_path_12) + "\" -q", capture_output = True, encoding = "shift-jis")
        if len(svn_result.stderr) > 0:
            text_log.write(svn_result.stderr)
            text_log.flush()

        print('Starting to process files.')
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            #threads = {executor.submit(CalculateFileChurn, path):path for path in textbridge_repo_path.rglob("*.lxtxt")}
            thread1 = executor.submit(self.ProcessFileList,self.textbridge_repo_path_1,paths1,0,"red")
            #thread2 = executor.submit(self.ProcessFileList,self.textbridge_repo_path_2,paths2,1,"blue")
            #thread3 = executor.submit(self.ProcessFileList,self.textbridge_repo_path_3,paths3,2,"green")
            #thread4 = executor.submit(self.ProcessFileList,self.textbridge_repo_path_4,paths4,3,"magenta")
            #thread5 = executor.submit(self.ProcessFileList,self.textbridge_repo_path_5,paths5,4,"pink")
            #thread6 = executor.submit(self.ProcessFileList,self.textbridge_repo_path_6,paths6,5,"teal")
            #thread7 = executor.submit(self.ProcessFileList,self.textbridge_repo_path_7,paths7,6,"purple")
            #thread8 = executor.submit(self.ProcessFileList,self.textbridge_repo_path_8,paths8,7,"yellow")
            #thread9 = executor.submit(self.ProcessFileList,self.textbridge_repo_path_9,paths9,8,"brown")
            #thread10 = executor.submit(self.ProcessFileList,self.textbridge_repo_path_10,paths10,9,"blue")
            #thread11 = executor.submit(self.ProcessFileList,self.textbridge_repo_path_11,paths11,10,"orange")
            #thread12 = executor.submit(self.ProcessFileList,self.textbridge_repo_path_12,paths12,11,"gray")
            result1 = thread1.result()
            #result2 = thread2.result()
            #result3 = thread3.result()
            #result4 = thread4.result()
            #result5 = thread5.result()
            #result6 = thread6.result()
            #result7 = thread7.result()
            #result8 = thread8.result()
            #result9 = thread9.result()
            #result10 = thread10.result()
            #result11 = thread11.result()
            #result12 = thread12.result()
            total_churn += result1["churn"]
            #total_churn += result2["churn"]
            #total_churn += result3["churn"]
            #total_churn += result4["churn"]
            #total_churn += result5["churn"]
            #total_churn += result6["churn"]
            #total_churn += result7["churn"]
            #total_churn += result8["churn"]
            #total_churn += result9["churn"]
            #total_churn += result10["churn"]
            #total_churn += result11["churn"]
            #total_churn += result12["churn"]
            churn_data += result1["data"]
            #churn_data += result2["data"]
            #churn_data += result3["data"]
            #churn_data += result4["data"]
            #churn_data += result5["data"]
            #churn_data += result6["data"]
            #churn_data += result7["data"]
            #churn_data += result8["data"]
            #churn_data += result9["data"]
            #churn_data += result10["data"]
            #churn_data += result11["data"]
            #churn_data += result12["data"]

        print('Iterating through Churn data.')
        # create dataframe of existing churntracker
        for datum in churn_data:
            new_row = {'File': str(datum.path), 'Rev': int(datum.rev), 'ID': str(datum.id), 'Old': datum.old.replace('\t', ' '), \
                       'New': datum.new.replace('\t', ' '), 'Churn': str(datum.churn), 'Date': str(datum.date)}
            print('Appending new row.')
            df = df.append(new_row, ignore_index=True)
            #df.index = df.index + 1
            #df = df.sort_index()
        
        print('Writing updated df back into text file.')
        #write update df to text_file
        df = df.sort_values(by=['Rev'], ascending=True)
        df.to_csv(self.data_file_path, sep='\t', encoding='utf-8', index=False)
        
        #Print total churn and filewise churn
        text_log.write("Total Churn: " + str(total_churn))
        text_log.flush()
        self.appending = False

class ChurnDatum:
    def __init__(self, path:str, rev:int, id:str, old:str, new:str, churn:int, date:str):
        self.path = path
        self.rev = str(rev)
        self.id = id
        self.date = date

        #Escape quotation marks
        if "\"" in old:
            old = old.replace ("\"","\"\"")
        if "\"" in new:
            new = new.replace("\"", "\"\"")

        #Add quotation marks to multi-line strings
        if "\n" in old:
            old = "\"" + old + "\""
        if "\n" in new:
            new = "\"" + new + "\""

        self.old = old
        self.new = new
        self.churn = str(churn)  
         
#ct = Churn_Tracker(r'M:\Voice Bridge Churn Tracker\preferences_edge.json', )
#ct.full_report()
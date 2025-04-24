from util.memoQ.MemoQDatabase import MemoQDatabase
from util.lxtxt.lxtxtDatabase import LXTXTDatabase
from util.lxtxt.lxvbfDatabase import LXVBFDatabase
from util.fileshare.svn import Handler as SVN
import datetime
import time
from util.LanguageCodes import Language
from pathlib import Path
import json
import os
import pprint
from util.data_tracking.mailClient import mailClient
import pandas as pd
from util.data_tracking.pretty_html_table import build_table
import re, sys

class ConflictChecker:
    #debug init made in case a separate functionality needs to be tested more quickly
    def __init__(self, debug: int):
        self.debug = debug
    
    def __init__(self, json_database: Path, memoQDB: MemoQDatabase, lxtxtDB: LXTXTDatabase, template, excel: Path, lang: str, preferences, svn: SVN = None, update_svn: bool = False, lxvbfDB: LXVBFDatabase = None):
        self.db = json_database
        self.memoQDB = memoQDB
        self.lxtxtDB = lxtxtDB
        self.lxvbfDB = lxvbfDB
        self.e_template = template
        self.e_excel = excel
        self.lang = lang
        self.prefs = preferences
        self.svn = svn
        self.update_svn = update_svn
        self.data_dict = self.from_json(lang) if not self.is_db_empty() else self.update()

    def update(self):
        # create new json db from updated files
        return self.create_from_files(self.lang)
    
    # reads the db directly from the json file   
    def from_json(self, lang):

        ###FOR DEBUGGING
            
        #Pull in the DB if it exists
        try:
            with open(self.db, "r", encoding='utf-8') as stored_db:
                json_db = json.load(stored_db)
        #Otherwise, create a dummy old DB
        except:
            json_db = {
                        "DB": {
                                "Conflict": False,
                                "Last Update": 0.0,
                                },
                            "Files": {}
                        }
            
        #Create the new DB
        data = {
                "DB": {
                        "Conflict": False,
                        "Last Update": 0.0,
                        },
                    "Files": {}
                }

        with open(r'M:\Projects\Crown\Tooling\CROWN_LocLink\resources\conflict_check\conflict_check_compare.txt', "w", encoding="utf8") as compare_file:
            #For each LXTXT
            for file in self.lxtxtDB.files:
                id_relpath = str(file.path.relative_to(self.lxtxtDB.assets_root))
                relpath = str(file.path.relative_to(self.lxtxtDB.assets_root).with_suffix(''))
                data['Files'][relpath] = {'Conflict' : False,
                                                'Strings' : {}}
                try:
                    json_file = json_db["Files"][relpath]
                except:
                    json_file = None
                for row in file.interface.Rows:
                    if not row.LanguageCells[lang]:
                            continue
                    string_ID = f'{id_relpath}-{row.Label}'
                    data['Files'][relpath]['Strings'][string_ID] = {
                                                                    "Conflict": False,
                                                                    "TB": "",
                                                                    "TB Status": ""
                                                                    }
                    try:
                        json_row = json_file['Strings'][string_ID]
                    except:
                        json_row = ""
                    
                    textbridge_text = row.LanguageCells[lang].Text.replace("\r","")
                    textbridge_status = str(row.LanguageCells[lang].Status)

                    if json_row:
                        data['Files'][relpath]['Strings'][string_ID]['Conflict'] = True if textbridge_text != json_row['TB'] else False
                        if json_row['TB'] != textbridge_text:
                            compare_file.write(f'JSON: {json_row["TB"]} | VB: {textbridge_text}\n')
                        if data['Files'][relpath]['Strings'][string_ID]['Conflict'] == True:           
                            data['Files'][relpath]['Conflict'] = True
                        if data['Files'][relpath]['Conflict'] == True:
                            data['DB']['Conflict'] = True
                    else:
                        data['Files'][relpath]['Strings'][string_ID]['Conflict'] = False

                    data['Files'][relpath]['Strings'][string_ID]['TB'] = textbridge_text
                    data['Files'][relpath]['Strings'][string_ID]['TB Status'] = textbridge_status
                    
            if self.lxvbfDB:
                for file in self.lxvbfDB.files:
                    id_relpath = str(file.path.relative_to(self.lxvbfDB.assets_root))
                    relpath = str(file.path.relative_to(self.lxvbfDB.assets_root).with_suffix(''))
                    data["Files"][relpath] = {"Conflict": False,
                                                "Strings": {}}
                    try:
                        json_file = json_db["Files"][relpath]
                    except:
                        json_file = None
                    for row in file.interface.Rows:
                        if not row.Cells[lang]:
                            continue
                        string_ID = f'{id_relpath}-{row.Label}' if row.Cells[lang].VoiceFileName == "" else f'{id_relpath}-{row.Cells[lang].VoiceFileName}'
                        data["Files"][relpath]["Strings"][string_ID] = {
                                                                        "Conflict": False,
                                                                        "TB": "",
                                                                        "TB Status": ""
                                                                        }
                        try:
                            json_row = json_file["Strings"][string_ID]
                        except:
                            json_row = ""
                        
                        voicebridge_text = row.Cells[lang].Text.Text.replace("\r","")
                        voicebridge_status = str(row.Cells[lang].Text.Status)

                        if json_row and voicebridge_text:
                            data["Files"][relpath]["Strings"][string_ID]["Conflict"] = True if voicebridge_text != json_row["TB"] else False
                            if json_row["TB"] != voicebridge_text:
                                compare_file.write(f'JSON: {json_row["TB"]} | VB: {voicebridge_text}\n')
                            if data["Files"][relpath]["Strings"][string_ID]["Conflict"] == True:
                                data["Files"][relpath]["Conflict"] = True
                            if data["Files"][relpath]["Conflict"] == True:
                                data["DB"]["Conflict"] = True
                        else:
                            data["Files"][relpath]["Strings"][string_ID]["Conflict"] = False

                        data["Files"][relpath]["Strings"][string_ID]["TB"] = voicebridge_text
                        data["Files"][relpath]["Strings"][string_ID]["TB Status"] = voicebridge_status

            with open(self.db, "w", encoding='utf-8') as stored_db:
                json.dump(data, stored_db, ensure_ascii=False)
            return data

    def update_conflict_status(self, relpath, context_id, en_text):
        if en_text != self.data_dict["Files"][relpath]['Strings'][context_id]['TB']:
            self.data_dict["Files"][relpath]['Strings'][context_id]["Conflict"] = True
            self.data_dict["Files"][relpath]['Conflict'] = True
            self.data_dict['DB']['Conflict'] = True

    # creates a new db from the Textbridge English and memoQ inbox files
    def create_from_files(self):
        self.data_dict = {'DB' : 
                                {'Conflict' : False,
                                 'Last Update' : ''},
                          'Files' : {}}
        # Check if DB is empty or not
        if not self.is_db_empty():
            print('DB is already created.')
        self.data_dict['DB']['Last Update'] = time.mktime(datetime.datetime.now().timetuple())
        db_dict = self.data_dict['Files']
        # Update TB databases svn
        if self.svn:
            if self.update_svn:
                self.svn.update_to_latest()
        # Get Current Data from TB
        for file in self.lxtxtDB.files:
            id_relpath = str(file.path.relative_to(self.lxtxtDB.assets_root))
            relpath = str(file.path.relative_to(self.lxtxtDB.assets_root).with_suffix(''))
            db_dict[relpath] = {'Conflict' : False,
                                'Strings' : {}}
            for row in file.interface.Rows:
                string_ID = f'{id_relpath}-{row.Label}'.replace('\\', '')
                if string_ID not in db_dict.keys():
                    db_dict[relpath]['Strings'][string_ID] = {'Conflict' : False,
                                                              'TB Status' : '',
                                                              'TB' : ''}
                if row.LanguageCells[self.lang]:
                    db_dict[relpath]['Strings'][string_ID]['TB'] = row.LanguageCells[self.lang].Text.replace("\r","")
                    db_dict[relpath]['Strings'][string_ID]['TB Status'] = str(row.LanguageCells[self.lang].Status)

        if self.lxvbfDB:
            for file in self.lxvbfDB.files:
                id_relpath = str(file.path.relative_to(self.lxvbfDB.assets_root))
                relpath = str(file.path.relative_to(self.lxvbfDB.assets_root).with_suffix(''))
                db_dict[relpath] = {'Conflict' : False,
                                    'Strings' : {}}
                for row in file.interface.Rows:
                    string_ID = f'{id_relpath}-{row.Label}'.replace('\\', '')
                    if string_ID not in db_dict.keys():
                        db_dict[relpath]['Strings'][string_ID] = {'Conflict' : False,
                                                                'TB Status' : '',
                                                                'TB' : ''}
                    if row.Cells[self.lang]:
                        db_dict[relpath]['Strings'][string_ID]['TB'] = row.Cells[self.lang].Text.Text.replace("\r","")
                        db_dict[relpath]['Strings'][string_ID]['TB Status'] = str(row.Cells[self.lang].Text.Status)

                    db_dict[relpath]['Strings'][string_ID]['Conflict'] = True if row.Cells[self.lang].Text.Text.replace("\r","") != db_dict[relpath]['Strings'][string_ID]['TB'] else False
                    if db_dict[relpath]['Strings'][string_ID]['Conflict'] == True:
                        db_dict[relpath]['Conflict'] = True
                    if db_dict[relpath]['Conflict'] == True:
                        self.data_dict['DB']['Conflict'] = True                  
        
        ####Save new dict to JSON file 
        with open(self.db, 'w', encoding='utf8') as db:
            json.dump(self.data_dict, db, ensure_ascii=False)
        return self.data_dict
    
    # creates a new db from the Textbridge English and memoQ inbox files
    def create_from_files(self, lang:str):
        self.data_dict = {'DB' : 
                                {'Conflict' : False,
                                 'Last Update' : ''},
                          'Files' : {}}
        # Check if DB is empty or not
        if not self.is_db_empty():
            print('DB is already created.')
        self.data_dict['DB']['Last Update'] = time.mktime(datetime.datetime.now().timetuple())
        db_dict = self.data_dict['Files']
        # Update TB databases svn
        if self.svn:
            if self.update_svn:
                self.svn.update_to_latest()
        # Get Current Data from TB
        for file in self.lxtxtDB.files:
            id_relpath = str(file.path.relative_to(self.lxtxtDB.assets_root))
            relpath = str(file.path.relative_to(self.lxtxtDB.assets_root).with_suffix(''))
            db_dict[relpath] = {'Conflict' : False,
                                'Strings' : {}}
            for row in file.interface.Rows:
                string_ID = f'{id_relpath}-{row.Label}'.replace('\\', '')
                if string_ID not in db_dict.keys():
                    db_dict[relpath]['Strings'][string_ID] = {'Conflict' : False,
                                                              'TB Status' : '',
                                                              'TB' : ''}
                if row.LanguageCells[lang]:
                    db_dict[relpath]['Strings'][string_ID]['TB'] = row.LanguageCells[lang].Text.replace("\r","")
                    db_dict[relpath]['Strings'][string_ID]['TB Status'] = str(row.LanguageCells[lang].Status)

        if self.lxvbfDB:
            for file in self.lxvbfDB.files:
                id_relpath = str(file.path.relative_to(self.lxvbfDB.assets_root))
                relpath = str(file.path.relative_to(self.lxvbfDB.assets_root).with_suffix(''))
                db_dict[relpath] = {'Conflict' : False,
                                    'Strings' : {}}
                for row in file.interface.Rows:
                    string_ID = f'{id_relpath}-{row.Label}'.replace('\\', '')
                    if string_ID not in db_dict.keys():
                        db_dict[relpath]['Strings'][string_ID] = {'Conflict' : False,
                                                                'TB Status' : '',
                                                                'TB' : ''}
                    if row.Cells[lang]:
                        db_dict[relpath]['Strings'][string_ID]['TB'] = row.Cells[lang].Text.Text.replace("\r","")
                        db_dict[relpath]['Strings'][string_ID]['TB Status'] = str(row.Cells[lang].Text.Status)
                    try:
                        db_dict[relpath]['Strings'][string_ID]['Conflict'] = True if row.Cells[lang].Text.Text.replace("\r","") != db_dict[relpath]['Strings'][string_ID]['TB'] else False
                        if db_dict[relpath]['Strings'][string_ID]['Conflict'] == True:
                            db_dict[relpath]['Conflict'] = True
                        if db_dict[relpath]['Conflict'] == True:
                            self.data_dict['DB']['Conflict'] = True
                    except:
                        print(lang, string_ID)                 
        
        ####Save new dict to JSON file 
        with open(self.db, 'w', encoding='utf8') as db:
            json.dump(self.data_dict, db, ensure_ascii=False)
        return self.data_dict
    
    def create_conflict_report(self):
        conflict_list = []
        if not self.data_dict['DB']['Conflict']:
            print(f'No conflicts found!')
        for file in self.data_dict['Files'].keys():
            if self.data_dict['Files'][file]['Conflict']:
                for id in self.data_dict['Files'][file]['Strings'].keys():
                    if self.data_dict['Files'][file]['Strings'][id]['Conflict']:
                        ####get the Textbridge specific ID for clarity
                        id_regex = re.search(r'\.(lxtxt|lxvbf)-(.*)', id)
                        file_extension = str(id_regex.group(1))
                        fixed_id = str(id_regex.group(2))
                        conflict_list.append([f'{file}.{file_extension}', fixed_id, f'{self.data_dict["Files"][file]["Strings"][id]["TB"]}', f'{self.data_dict["Files"][file]["Strings"][id]["TB Status"]}'])
        self.create_email_report(conflict_list)
        
    def is_db_empty(self):
        # return true if length is 0.
        return os.path.getsize(self.db) == 0
    
    def create_email_report(self, conflict_list):
        table_data = {}
        table_idx = 1
        with open(str(self.e_template), 'r') as myfile:
            template = myfile.read()
        for conf in conflict_list:
            table_data[table_idx] = conf
            table_idx+=1
        dataframe = pd.DataFrame.from_dict(table_data, orient='index', columns=['Filename', 'ID', 'TextBridge String', 'TextBridge Status'])
        xl = dataframe.to_excel(self.prefs.resources_location / 'conflict_check\\conflict_check.xlsx', index=False)
        p_table = build_table(dataframe, 'orange_light', font_size='small', font_family='Calibri')
        if table_idx >= 300:
            p_table = "See Attachment for details"
        #don't send email if there are no conflicts found
        if table_idx-1 > 0:
            e_data = template.format(conflict_list = p_table, conf_num = table_idx-1)
            mail_handler = mailClient('10.30.100.69', 'AKIA6MYNKSLTF4CMKS4L', 'BFxgt15QWemeGTUknhoJxUsTHf5YiKn8JyvuKFeljMca', 'memoq@segaamerica.com')
            ###add in excel file no matter what
            for email in self.prefs.progress_alert_email_list:
                mail_handler.send_HTML_message_with_excel(email,
                                                        f"{self.prefs.memoQ_project_name.upper()} CONFLICT REPORT",
                                                            e_data,
                                                            '2', 
                                                            f'{self.prefs.memoQ_project_name.upper()}',
                                                            excel_attachment=self.prefs.resources_location / 'conflict_check\\conflict_check.xlsx')
        
        
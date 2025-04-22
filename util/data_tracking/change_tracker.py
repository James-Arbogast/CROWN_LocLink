# XLIFF Change Tracker is a class that stores Change data and spits it out into different types of log files.

from pathlib import Path
from typing import List
from util.xliff.xliff import File as xliffFile
from util.xliff.xliff import TransUnit
from util.data_tracking.count_JPC import count_JPC
from util.preferences.preferences import Preferences
from math import ceil
import re
import pandas as pd
import difflib
from util.data_tracking.pretty_html_table import build_table
from util.data_tracking.mailClient import mailClient
from shutil import copyfile
import json
from datetime import datetime
from util.data_tracking.progress_reporting import ProgressReporter
from Levenshtein import distance

#tracks changes to files
class Tracker:
    def __init__(self, preferences: Preferences, resource_dir: Path, savepath: Path, changelist: List, loginlist: List, notifylist: List):
        self.project_preferences = preferences
        self.resource_dir = resource_dir
        self.change_template = self.resource_dir / "export_summary_template.txt"
        self.churn_alert_template = self.resource_dir / "churn_alert_template.txt"
        self.json_data = self.resource_dir / "change_tracking_data.json"
        self.data = []  # Data is stored by date
        self.load_json_data()
        self.save_dest = savepath
        self.changelist = changelist
        self.pushlist = []
        self.voiceIDlist = VoiceIDErrors()
        # need to add encryption
        self.email_un = loginlist[0]
        self.email_pw = loginlist[1]
        self.fromAdd = loginlist[2]
        self.notifyemails = notifylist

    def export_summary(self):
        print("exporting txt summary")
        # import message from template
        with open(str(self.change_template), 'r', encoding = "utf_8_sig") as myfile:
            template = myfile.read()
        data = {"Changes": "", "Pushes": ""}
        datachange = False

        #First prints newlyunlocked files
        #Then prints changes in files
        datadict = {}
        table_columns = ["Filepath",
                         "Churn"]
        
        # changelist will be added to in converter process
        for changedfile in self.changelist:
            if changedfile.changes_tracked():
                datachange = True
                # Compile data into a table.
                cur_filepath = str(changedfile.filepath)
                cur_adddel = "+" + str(changedfile.additions) + "/-" + str(changedfile.deletions)
                cur_majordelta_changed = str(changedfile.MajorChanges[0])
                cur_majordelta_affected = str(changedfile.MajorChanges[1])
                cur_minordelta_changed = str(changedfile.MinorChanges[0])
                cur_minordelta_affected = str(changedfile.MinorChanges[1])
                cur_hybrid_churn = str(changedfile.hybrid_churn)
                datadict[cur_filepath] = [cur_filepath, cur_adddel, cur_majordelta_changed, cur_majordelta_affected,
                                          cur_minordelta_changed, cur_minordelta_affected, cur_hybrid_churn]

        # Now we put that datadict into a badass TABLE.
        simplified_dict = {key : [datadict[key][0], datadict[key][-1]] for key in datadict.keys()} #datadict[key][0] = filepath, datadict[key][-1] = hybrid churn
        dataframe = pd.DataFrame.from_dict(simplified_dict, orient='index', columns=table_columns)
        printtable = build_table(dataframe, 'orange_light', font_size="small", font_family="Calibri")
        printtable = bold_filenames(printtable)
        data["Changes"] = printtable

        # Grab any file push data.
        if self.pushlist:
            newlist = sorted(self.pushlist, key=lambda pathboy: str(pathboy).lower())
            for item in newlist:
                data["Pushes"] += str(item) + "<br>"
        # Send message
        if datachange or self.pushlist:  # Prevents tool from sending a blank message.
            self.save_to_json(datadict)
            databoy = template.format(**data)
            # Send it as an email to the stored email adds
            mail_handler = mailClient('10.30.100.69', self.email_un, self.email_pw, self.fromAdd)
            toobig = False
            # sends html email to all emails in notifyemails list
            for email in self.notifyemails:
                result = mail_handler.send_HTML_message(email, "[%s] Automated Update Processed" % self.project_preferences.project_codename, databoy)
            if result:
                toobig = True
            if toobig:
                # Save hard copy.
                savepath = self.resource_dir / (datetime.now().strftime("%m-%d-%Y") + "_report.html")
                with open(str(savepath),"w",encoding='utf-8') as f:
                    f.write(databoy)

    def calculate_churn_to_date(self):
        # Calculates how many JPC of churn there has been since the starting date.
        start_date = self.project_preferences.project_startdate # Use the startdate specified in prefs
        churn_by_date = {}
        existing_filelist = []
        file_additions_dict = {}
        # Read all entries in JSON, summing up the total churn.
        for entry in self.data:
            entrydate = datetime.strptime(entry[0]["date"],"%m/%d/%Y %H:%M:%S")
            if entrydate < start_date:
                continue # Skip anything before the current date
            churn_by_date[entrydate] = 0
            entrylist = entry[1]
            for filename in entrylist:
                filechurn = 0
                curentry = entrylist[filename]
                #Additions and Subtractions (normalized)
                # Stylized as "+0/-0"
                addsub = curentry[1]
                filechurn += sum([abs(int(x)) for x in addsub.split("/")])

                ### Identifying if it's new or not
                if filename not in existing_filelist:
                    #It was added on this date
                    existing_filelist.append(filename)
                    #Add its churn data to file additions.
                    if entrydate not in file_additions_dict:
                        file_additions_dict[entrydate] = 0
                    file_additions_dict[entrydate] += filechurn
                else:
                    # Major and Minor Changes
                    filechurn += int(curentry[2])
                    filechurn += int(curentry[4])
                    churn_by_date[entrydate] += filechurn

        return churn_by_date, file_additions_dict

    def send_churn_alert(self):
        # import template
        with open(str(self.churn_alert_template), 'r', encoding="utf8") as myfile:
            template = myfile.read()
        data = {"Status": "", "ChurnToDate": "", "AdditionsToDate": ""}
        # Calculate Churn to Date, Additions to Date
        churn_by_date, file_additions_dict = self.calculate_churn_to_date()
        churn_sum = sum([churn_by_date[date] for date in churn_by_date])
        addition_sum = sum([file_additions_dict[date] for date in file_additions_dict])
        data["ChurnToDate"] = f"{churn_sum:,d} JPC"
        data["AdditionsToDate"] = f"{addition_sum:,d} JPC"
        # Check against the data provided by Scott
        churn_limit = 320000
        churn_percent = churn_sum / churn_limit
        if churn_percent < 0.6:
            alert_level = '<span style="background-color: #00FF00">GREEN (%s)</span>' % f"{churn_percent:.2%}"
        elif 0.6 <= churn_percent < 0.8:
            alert_level = '<span style="background-color: #FFF000">YELLOW (%s)</span>' % f"{churn_percent:.2%}"
        else:
            alert_level = '<span style="background-color: #FF0000">RED (%s)</span>' % f"{churn_percent:.2%}"
        data["Status"] = alert_level
        #Send Alert.
        databoy = template.format(**data)
        # Send it as an email to the stored email adds
        mail_handler = mailClient('10.30.100.69', self.email_un, self.email_pw, self.fromAdd)
        for email in self.notifyemails:
            mail_handler.send_HTML_message(email,
                                           "[%s] Churn Alert" % self.project_preferences.project_codename,
                                           databoy)

    def sort_data_by_filename(self):
        # Takes self.data and returns a dict of filename:{date:data}
        data_by_filename = {}
        for entry in self.data:
            entrydate = datetime.strptime(entry[0]["date"],"%m/%d/%Y %H:%M:%S")
            entrylist = entry[1]
            for filename in entrylist:
                if filename not in data_by_filename:
                    data_by_filename[filename] = {}
                data_by_filename[filename][entrydate] = entrylist[filename]
        return data_by_filename

    @classmethod
    def create_empty(cls, preferences: Preferences, template : Path, savepath: Path, loginlist: List, notifylist: List):
        created = cls(preferences, template, savepath, [], loginlist, notifylist)
        return created

    def add_xliff_comparison(self, oldfile: xliffFile, newfile: xliffFile):
        self.changelist.append(FileChanges.create_from_xliffs(oldfile, newfile))

    def add_new_file(self, file: xliffFile):
        self.changelist.append(FileChanges.create_from_new_xliff(file))

    def changes_logged(self):
        if self.changelist or self.pushlist:
            return True
        else:
            return False

    def add_lxtxt_list(self, itemlist):
        for item in itemlist:
            if item not in self.pushlist:
                self.pushlist.append(item)

    def add_push_list(self, itemlist):
        for item in itemlist:
            if item not in self.pushlist:
                self.pushlist.append(item)

    def load_json_data(self):
        try:
            with open(str(self.json_data), "r") as read_file:
                data = json.load(read_file)
            # backup JSON
            self.perform_json_backup()
            self.data = data
        except FileNotFoundError:
            pass # Catches, will remain as [] from class def

    def save_to_json(self, datadict: dict):
        # Append new data to JSON
        cur_shot = [{"date": datetime.now().strftime("%m/%d/%Y %H:%M:%S")}, datadict]
        self.data.append(cur_shot)
        with open(str(self.json_data), "w") as write_file:
            json.dump(self.data, write_file)

    def perform_json_backup(self):
        copyfile(str(self.json_data), str(self.json_data.parent) + self.json_data.stem + "_backup.json")


class FileChanges:
    def __init__(self, filepath: Path, changes: List):
        self.filepath = filepath
        self.changes = changes
        self.hybrid_churn = 0
        self.additions = 0  # Total JPC
        self.deletions = 0  # Total JPC
        self.unlocks = 0  # Total JPC
        self.MajorChanges = [0, 0]  # Changed JPC, Affected JPC
        self.MinorChanges = [0, 0]  # Changed JPC, Affected JPC
        self.CommentChanges = [0]
        # list of JPC counts strings that had comments updated, taking a len() gets # of strings affected

    def changes_tracked(self):
        myvals = [self.additions, self.deletions, self.MajorChanges[0], self.MajorChanges[1], self.MinorChanges[0],
                  self.MinorChanges[1]]
        if any(item != 0 for item in myvals):
            return True
        return False

    @classmethod
    def create_from_json(cls, jsondata):
        # jsondata looks like ["current_to_soa\\message\\field\\npc_CLIFF_SUSPECT_D.xliff", "+366/-0", "510", "366", "0", "0"]
        # [cur_filepath, cur_adddel, cur_majordelta_changed, cur_majordelta_affected,
        #                                           cur_minordelta_changed, cur_minordelta_affected]
        created = cls(jsondata[0],[]) # we aren't going to use the total list of changes for now, sorry future me.\
        addsub = jsondata[1]
        #filechurnlist = addsub.split("/")
        filechurn = [abs(int(x)) for x in addsub.split("/")]
        created.additions = filechurn[0]
        created.deletions = filechurn[1]
        created.MajorChanges = [jsondata[2],jsondata[3]]
        created.MinorChanges = [jsondata[4],jsondata[5]]
        return created

    @classmethod
    def create_from_xliffs(cls, oldfile: xliffFile, newfile: xliffFile):
        oldfilepath = oldfile.relative_filepath
        # find additions and changes to new one
        additioncount = 0
        deletioncount = 0
        newunlock = 0
        commentchange = []
        changelog = []
        indexno = 0
        for context_id, newunit in newfile.trans_units.items():
            indexno += 1
            # skip if speaker or addition or metadata on our end.
            if any(x in context_id for x in ["SPEAKER","ADDITION","METADATA", "DIRECTION"]):
                continue
            try:
                # Try to get the same one from the old file.
                oldunit = oldfile.trans_units[context_id]
                # If you can, and it's different, track the difference.
                if oldunit != newunit:
                    # Source = "Source"
                    if oldunit.source != newunit.source:
                        changelog.append(ChangeUnit.from_change(indexno,
                                                                VarChangeType.Source, oldunit.source, newunit.source))
                    # Locked = "Locked"
                    if oldunit.locked != newunit.locked:
                        changelog.append(ChangeUnit.from_change(indexno,
                                                                VarChangeType.Locked, str(oldunit.locked),
                                                                str(newunit.locked)))
                        newunlock += count_JPC(newunit.source)
                    # Comment = "Comment"
                    if any(pair[0] != pair[1] for pair in zip(oldunit.notes, newunit.notes)):
                        commentchange.append(count_JPC(newunit.source))
            except KeyError:
                # If you can't, it's an addition.
                # additionlog.append(ChangeUnit.from_addition(indexno, newunit))
                additioncount += count_JPC(newunit.source)
        # Check for deletions by seeing if all the units in the old one exist in the new one.
        for context_id, oldunit in oldfile.trans_units.items():
            try:
                newunit = newfile.trans_units[context_id]
            except KeyError:
                deletioncount += count_JPC(oldunit.source)

        # sort them by position in xliff file
        changelog.sort(key=lambda x: x.indexno)

        created = cls(oldfilepath, changelog)
        created.additions = additioncount  # of new JPC added
        created.deletions = deletioncount  # of JPC deleted
        created.CommentChanges = commentchange
        created.analyze_changes()
        return created

    @classmethod  # Handles new files.
    def create_from_new_xliff(cls, file: xliffFile):
        filepath = file.relative_filepath
        changelog = []
        indexno = 0
        additioncount = 0
        for context_id, unit in file.trans_units.items():
            # skip if speaker or addition or metadata on our end.
            if any(x in context_id for x in ["SPEAKER","ADDITION","METADATA", "DIRECTION"]):
                continue
            indexno += 1
            changelog.append(ChangeUnit.from_addition(indexno, unit))
            additioncount += count_JPC(unit.source)
        created = cls(filepath, changelog)
        created.additions = additioncount
        return created

    def analyze_changes(self):
        # Iterate through the change list and edit self:
        major_changed = 0
        major_affected = 0
        minor_changed = 0
        minor_affected = 0
        hybrid = 0
        # Iterate through change list.
        for changeboy in self.changes:
            # IF the change is it's new, we don't want to return anything
            if changeboy.changeType is not ChangeType.Change:
                continue
            delta = calculate_string_delta(changeboy.prev, changeboy.new)  # returns [-, +] in characters
            # Determine # of delta to flag as major
            if len(changeboy.prev) > len(changeboy.new):
                major_class = ceil(len(changeboy.prev) * 0.05)
            else:
                major_class = ceil(len(changeboy.new) * 0.05)
            # Determine if string delta is major or minor
            if any(x >= major_class for x in delta):
                # Major
                major_changed += max(delta)
                major_affected += count_JPC(changeboy.new)
            else:
                # Minor
                minor_changed += max(delta)
                minor_affected += count_JPC(changeboy.new)
            low_churn = distance(changeboy.prev,changeboy.new)
            high_churn = len(changeboy.new)
            if high_churn > low_churn:
                hybrid = high_churn
            else:
                hybrid = low_churn
            self.hybrid_churn += hybrid

        self.MajorChanges = [major_changed, major_affected]  # Changed JPC, Affected JPC
        self.MinorChanges = [minor_changed, minor_affected]


class ChangeUnit:
    def __init__(self, indexno, changeType, varchanged, prev, new):
        self.indexno = indexno
        self.changeType = changeType
        self.varchanged = varchanged
        self.prev = prev
        self.new = new

    @classmethod
    def from_addition(cls, indexno, trans_unit: TransUnit):
        changeType = ChangeType.Addition
        vartype = "All (Addition)"
        prev = ""
        new = trans_unit.source
        return cls(indexno, changeType, vartype, prev, new)

    @classmethod
    def from_change(cls, indexno, vartype: str, oldunit: str, newunit: str):
        changeType = ChangeType.Change
        return cls(indexno, changeType, vartype, oldunit, newunit)

    @classmethod
    def from_change_comments(cls, indexno, vartype: str, oldunit: List, newunit: List):  # list of Note objects
        changeType = ChangeType.Change
        # Glom all comments into one string.
        oldunitlist = '\n'.join([item.text for item in oldunit])
        newunitlist = '\n'.join([item.text for item in newunit])
        return cls(indexno, changeType, vartype, oldunitlist, newunitlist)

    @classmethod
    def from_deletion(cls, indexno, trans_unit: TransUnit):
        changeType = ChangeType.Deletion
        vartype = "All (Deletion)"
        prev = trans_unit.source
        new = ""
        return cls(indexno, changeType, vartype, prev, new)


class VoiceIDErrors:
    def __init__(self):
        self.idDict = {}  # A dictionary of IDs: [path, path, path]

    @classmethod
    def from_new(cls, ID: str, filepath: str):
        newobj = cls()
        newobj.idDict[ID] = []
        newobj.idDict[ID].append(filepath)
        return newobj

    def retrieve_paths(self, ID: str):
        return self.idDict[ID]

    def add_ID(self, ID: str, filepath: str):
        if ID not in self.idDict.keys():
            self.idDict[ID] = []
        self.idDict[ID].append(filepath)


class ChangeType:
    Addition = "Addition"
    Change = "Change"
    Deletion = "Deletion"


class VarChangeType:
    Source = "Source"
    Locked = "Locked"
    Comment = "Comment"


def calculate_string_delta(stringA, stringB):
    minuscount = 0
    pluscount = 0
    for i, s, in enumerate(difflib.ndiff(stringA, stringB)):
        if s[0] == "+":
            pluscount += 1
        elif s[0] == "-":
            minuscount += 1
    return [minuscount, pluscount]


def bold_filenames(stringboy: str):
    # finds filenames and bolds them then returns a string
    matcher = r"([\w]+.xliff)"
    replacement = r"<b>\1"
    return re.sub(matcher, replacement, stringboy)

expected_text_volume = 3200000
allowed_churn = 320000
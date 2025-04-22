from pathlib import Path
import sys
from util.xliff.xliff import File as XLIFF
import json
from datetime import datetime, timedelta

#**********20231211 UPDATE: {Filename: {ID: {Language: {Text : [Unix time]}}}}************

def check_for_matching_entry(trg,source_subentry):#source_subentry = jsonDict["Data"][cid][source]
    max_target_unix_time = max(source_subentry[trg])

    other_times = []

    for t in source_subentry:
        if trg != t:
            other_times.append(max(source_subentry[t]))
    if other_times:
        max_other_times = max(other_times)
    else:
        return True

    return True if max_target_unix_time > max_other_times else False
def add_to_data(sourceLang, targetLang, churn_db, github_backup_folder):
    xliff_folder = github_backup_folder
    churn_data_path = churn_db

    #exit_flag = 0
    edit_flag = 0

    try:
        with open(churn_data_path,encoding='utf8') as f:
            jsonDict = json.load(f)
            for x_file in xliff_folder.rglob("*.xliff"):
                xliffDict = {}
                xliff_file = XLIFF.from_file(x_file.absolute(),x_file.parent)
                for context_id, trans_unit in xliff_file.trans_units.items():
                    xliffDict[context_id] = trans_unit
        #******************************************************************
                filename = str(x_file.relative_to(xliff_folder))
                if filename not in jsonDict["Data"]:
                    jsonDict["Data"][filename] = {}
                    edit_flag = 1
                
                for cid in xliffDict:
                    source = str(xliffDict[cid].source)
                    target = str(xliffDict[cid].target)
                    current_unix_time = int((datetime.now() - datetime(1970, 1, 1)).total_seconds())

                    if cid not in jsonDict["Data"][filename]:
                        jsonDict["Data"][filename][cid] = {sourceLang : {source : [current_unix_time]}, targetLang : {target : [current_unix_time]}}
                        edit_flag = 1
                    else:
                        if sourceLang not in jsonDict["Data"][filename][cid]:
                            jsonDict["Data"][filename][cid][sourceLang] = {source : [current_unix_time]}
                            edit_flag = 1
                        else:
                            if source not in jsonDict["Data"][filename][cid][sourceLang]:
                                jsonDict["Data"][filename][cid][sourceLang][source] = [current_unix_time]
                                edit_flag = 1
                            else:
                                #keep json from being cluttered with unnecessary unix times (i.e. only add if current target != old target)
                                #current target = target with the highest recorded unix time
                                if check_for_matching_entry(source,jsonDict["Data"][filename][cid][sourceLang]) == False:
                                    jsonDict["Data"][filename][cid][sourceLang][source].append(current_unix_time)
                                    edit_flag = 1
                                
                                #else:
                                #    print("No source added for",cid)

                        if targetLang not in jsonDict["Data"][filename][cid]:
                            jsonDict["Data"][filename][cid][targetLang] = {target : [current_unix_time]}
                            edit_flag = 1
                        else:
                            if target not in jsonDict["Data"][filename][cid][targetLang]:
                                jsonDict["Data"][filename][cid][targetLang][target] = [current_unix_time]
                                edit_flag = 1
                            else:
                                #keep json from being cluttered with unnecessary unix times (i.e. only add if current target != old target)
                                #current target = target with the highest recorded unix time
                                if check_for_matching_entry(target,jsonDict["Data"][filename][cid][targetLang]) == False:
                                    jsonDict["Data"][filename][cid][targetLang][target].append(current_unix_time)
                                    edit_flag = 1
                                #else:
                                #    print("No target added for",cid)
    except:
        print("An error occurred while attempting to update churn data structure")
        return 1
                    
    #******************************************************************
        """for cid in xliffDict:
            source = str(xliffDict[cid].source)
            target = str(xliffDict[cid].target)
            current_unix_time = int((datetime.now() - datetime(1970, 1, 1)).total_seconds())

            if cid not in jsonDict["Data"]:
                jsonDict["Data"][cid] = {source : {target : [current_unix_time]}}
                edit_flag = 1
            else:
                if source not in jsonDict["Data"][cid]:
                    jsonDict["Data"][cid][source] = {target : [current_unix_time]}
                    edit_flag = 1
                else:
                    if target not in jsonDict["Data"][cid][source]:
                        jsonDict["Data"][cid][source][target] = [current_unix_time]
                        edit_flag = 1
                    else:
                        #keep json from being cluttered with unnecessary unix times (i.e. only add if current target != old target)
                        #current target = target with the highest recorded unix time
                        if check_for_matching_target(target,jsonDict["Data"][cid][source]) == False:
                            jsonDict["Data"][cid][source][target].append(current_unix_time)
                            edit_flag = 1
                        else:
                            print("No entry added for",cid)"""

        #except:
        #    print("lol")
        #    exit_flag = 1

    #print("edit_flag:",edit_flag)
    if edit_flag:
        try:
            with open(churn_data_path,"w",encoding='utf8') as f:
                json.dump(jsonDict,f,ensure_ascii=False)
        except:
            print("An error occurred while attempting to save updated churn to json file")
            return 1
    return 0#Success is dependent on if an exception is thrown, not on if the json file receives edits

#if __name__ == "__main__":
#    add_to_data("ja","en")
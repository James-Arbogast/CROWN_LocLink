from pathlib import Path
import sys
from util.xliff.xliff import File as XLIFF
import json
from datetime import datetime, timedelta
import os, shutil
import stat

#**********20231211 UPDATE: {Filename: {ID: {Language: {Text : [Unix time]}}}}************

def clear_folder(folder_path):
    return_value = True
    for filepath in folder_path.rglob("*.xliff"):
        #if "memoQ" not in filepath.stem:
        try:
            filepath.unlink()  # Unlink deletes the filepath in the folder.
        except:
            return_value = False
    #Remove folders
    walk = list(os.walk(str(folder_path)))
    for root, _, _ in walk[::-1]:
        if root == str(folder_path):
            continue
        if not os.access(root, os.W_OK):
            os.chmod(root, stat.S_IWUSR)
        try:
            shutil.rmtree(root)
        except:
            return_value = False
    return return_value

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
def add_to_data(sourceLang, targetLang, rough_e_db, rough_e_xliff_folder):
    xliff_folder = rough_e_xliff_folder
    churn_data_path = rough_e_db

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
    except:
        print("An error occurred while attempting to update rough E data structure")
        return 1
                    
    #******************************************************************

        #except:
        #    print("lol")
        #    exit_flag = 1

    #print("edit_flag:",edit_flag)
    if edit_flag:
        try:
            with open(churn_data_path,"w",encoding='utf8') as f:
                json.dump(jsonDict,f,ensure_ascii=False)
        except:
            print("An error occurred while attempting to save rough E to json file")
            return 1
    return 0#Success is dependent on if an exception is thrown, not on if the json file receives edits

#if __name__ == "__main__":
#    add_to_data("ja","en")
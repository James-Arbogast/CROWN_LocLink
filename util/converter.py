# SEGA of America
# dan.sunstrum@segaamerica.com
from util.lxtxt.lxtxtDatabase import LXTXTDatabase
from util.lxtxt.lxvbfDatabase import LXVBFDatabase
from util.memoQ.MemoQDatabase import MemoQDatabase
from util.data_tracking.change_tracker import Tracker
import os
import shutil
from util.xliff.xliff import File as XLIFFFile
from util.xliff.xliff import TransUnit
from pathlib import Path
from typing import List
import re
from util.LanguageCodes import Language
import clr
from util.preferences.preferences import Preferences
from util.conflict_check.conflict_check import ConflictChecker
from util.compliance_check import ComplianceChecker
import json

with Preferences.from_existing(r"resources\project_preferences.json") as pref:
    clr.AddReference(str(pref.textbridge_tool_location / "LxSdk"))
clr.AddReference("System")

from LxSdk import LxCellStatus #type: ignore
from LxSdk import LxLanguageCell #type: ignore
from LxSdk import LxAttributeCell #type: ignore
from LxSdk import LxCommentCell #type: ignore
from LxSdk import LxVoiceCell #type: ignore
from LxSdk import LxSummaryCell #type: ignore
from System import DateTime #type: ignore

class ModificationUser:
    default = 'james.arbogast:SOA-MEMQ1'

#If a cell has any of these statuses,
#"<SOURCE TEXT NOT FINALIZED>" will be added to the beginning of the source text.
unfinalizedStatuses = [LxCellStatus.NotStarted,\
                        LxCellStatus.Editing,\
                        LxCellStatus.ParentLanguageEditing,\
                        LxCellStatus.TranslationRequested]

#XLIFF statuses that determine what cells will be marked Completed in TextBridge
statusesForCompletedInTextBridge = ["signed-off", "final"]

#If a cell has any of these statuses, the memoQ segment will be locked.
#These values correspond to None, Unused, and Error.
#Since "None" is a keyword in Python, LxCellStatus.None is invalid syntax.
#Therefore we have to check for that with LxCellStatus(0).
unusedStatuses = [LxCellStatus(0), LxCellStatus.Unused, LxCellStatus.Error]

class FileConverter():
    def __init__(self,
                 lxtxtDB: LXTXTDatabase,
                 lxvbfDB: LXVBFDatabase,
                 memoQDB: MemoQDatabase,
                 source_language: str,
                 target_language: str,
                 tracker: Tracker,
                 preferences: Preferences,
                 conflict_checker: ConflictChecker,
                 novoice: bool,
                 compliance_checker: ComplianceChecker):
        self.lxtxtDB = lxtxtDB
        self.lxvbfDB = lxvbfDB
        self.memoQDB = memoQDB
        self.source_language = source_language
        self.target_language = target_language
        self.change_tracker = tracker
        self.conflict_checker = conflict_checker
        self.enAudioPrefix = preferences.enAudioPrefix
        self.lxvbfFolder = preferences.lxvbfFolder
        self.voice_only_folder = preferences.voice_only_folder
        self.voice_script_suffix = preferences.voice_script_suffix
        self.type_labels = {}
        self.memoQ_xliff_text_dict = {}
        self.memoQ_xliff_voice_dict = {}
        self.compliance_checker = compliance_checker
        self.locked_file_list = set()
        self.populate_speaker_dict()
        if novoice:
            return
        self.populate_voice_script_speaker_dict()
    
    def convert_to_xliff(self, only_these: List = [], include_target: bool = False):
        for file in self.convert_lxtxt_to_xliff(only_these, include_target):
            self.memoQDB.save_file_to_input(file, self.change_tracker)
        #for file in self.convert_graphic_to_xliff(only_these, include_target):
            #self.memoQDB.save_file_to_input(file, self.change_tracker)
        for file in self.convert_lxvbf_to_xliff(only_these, include_target):
            self.memoQDB.save_file_to_input(file, self.change_tracker)
        # upon convert to XLIFF, also export a new version of the Speaker Name List.

    def populate_locked_file_list(self, file):
        with open(file, "r", encoding="utf8") as f:
            for line in f:
                self.locked_file_list.add(line.replace("\n",""))

    def populate_memoQ_xliff_dicts(self):
        for xliffFile in self.memoQDB.output_files(self.memoQDB.output_folder):
            if self.lxvbfFolder in str(xliffFile.relative_filepath):
                for context_id, xliff_unit in xliffFile.trans_units.items():
                    self.memoQ_xliff_voice_dict[context_id] = xliff_unit
            else:
                for context_id, xliff_unit in xliffFile.trans_units.items():
                    self.memoQ_xliff_text_dict[context_id] = xliff_unit

    def update_DBs(self, only_these: List = [], novoice: bool = False):
        self.update_lxtxt_from_xliff(only_these)
        if novoice:
            return
        self.update_lxvbf_from_xliff(only_these)

    def remove_deleted_files(self):
        # if a file in the xliff db doesn't exist in the lxtxt db anymore, delete the xliff.
        for filepath in self.memoQDB.input_folder.rglob("*.xliff"):
            #ignore the memoQ speaker list!
            if "memoQ_speaker_list" in filepath.stem:
                continue
            relpath = filepath.relative_to(self.memoQDB.input_folder)
            if self.enAudioPrefix + "\\" in str(relpath):
                relpath = Path(str(relpath).replace(self.enAudioPrefix + "\\",""))
            elif self.lxvbfFolder + "\\" in str(relpath):
                lxpath = self.lxtxtDB.assets_root.joinpath(relpath).with_suffix(".lxvbf")
            lxpath = self.lxtxtDB.assets_root.joinpath(relpath).with_suffix(".lxtxt")
            if not lxpath.exists():
                print(f'If I had this turned on it would unlink this file. {filepath}')
                #filepath.unlink()
        #Remove any empty folders that are leftover
        #walk = list(os.walk(self.memoQDB.input_folder))
        #for path, _, _ in walk[::-1]:
            #if len(os.listdir(path)) == 0:
                #shutil.rmtree(path)

    @staticmethod
    def is_xliff_finished(xliffFile: XLIFFFile):
        # return true if every row has target text that's not ""
        # else return false
        for _, xliff_unit in xliffFile.trans_units.items():
            if xliff_unit.target == "" and xliff_unit.source != "":
                return False
        return True

    def convert_lxtxt_to_xliff(self, only_these: List, include_target: bool = False, novoice: bool = False):
        converted_files = []
        envo_prefix = Path(self.enAudioPrefix)
        last_text = ""
        checker_edited = False
        conflict_lines = {} # key = context ID, value = "MQ" string in conflict DB. Purpose = overwrite xliff with "MQ" string (aka updated EN from dev)
        checker_dict = self.conflict_checker.data_dict['Files']
        for lxtxt_file in self.lxtxtDB.files:
            relpath = lxtxt_file.path.relative_to(self.lxtxtDB.assets_root)
            relpath_no_ext = relpath.parents[0] / relpath.stem
            
            # conflict checker for conflict between English strings
            check_file = checker_dict[str(relpath_no_ext)]
            if check_file['Conflict']:
                for cid in checker_dict[str(relpath_no_ext)]['Strings']:
                    if checker_dict[str(relpath_no_ext)]['Strings'][cid]['Conflict']:
                        conflict_lines[cid] = 1
            
            # See if this is the one we want to work on, if necessary
            if only_these:
                if str(relpath_no_ext) not in only_these:
                    continue

            # Create the new save path.
            new_file = XLIFFFile.create(relpath.with_suffix(".xliff"), self.source_language, self.target_language)
            envo_file = XLIFFFile.create(envo_prefix / relpath.with_suffix(".xliff"), self.source_language, self.target_language)

            # Iterate through units in the lxtxt and retrieve the right stuff.
            for textrow in lxtxt_file.interface.Rows:
                # Create unique ID for LXTXT.
                contextID = str(relpath) + "-" + textrow.Label
                locked = True if str(relpath_no_ext) in self.locked_file_list else False
                # Retrieve the line.
                try:
                    if "for_audio_language_en" in contextID:
                        cursource = last_text
                    else:
                        cursource = textrow.LanguageCells[Language.Japanese].Text
                        last_text = cursource
                except AttributeError:
                    # If there's no Japanese string in this row, skip it.
                    continue

                #LxSdk reads in line breaks as \r\n, but we only need the \n
                cursource = cursource.replace("\r","")

                #Check the status of the JP line.
                #If it's not ready to translate, lock it.
                if textrow.LanguageCells[Language.Japanese].Status in unfinalizedStatuses:
                    locked = True

                #If the JP line is unused or one of those header lines, prepend a tag to the source.
                #unused = False
                if textrow.LanguageCells[Language.Japanese].Status in unusedStatuses:
                    locked = True

                curtarget = ""
                curState = "needs-translation"
                oldSource = ""
                oldTarget = ""
                oldState = "needs-translation"

                #If this file exists in memoQ already
                if relpath_no_ext in self.memoQDB.exported_files.keys():
                    #Pull corresponding memoQ XLIFF
                    memoq_xliff = self.memoQDB.exported_files[relpath_no_ext]
                    #Fill in text from previous version and store status
                    for id, unit in memoq_xliff.trans_units.items():
                        if id == contextID:
                            oldSource = unit.source
                            oldTarget = unit.target
                            oldState = unit.status
                            break

                if include_target:
                    curtarget = oldTarget

                conflict_id = contextID
                if conflict_id in conflict_lines and include_target:
                    curtarget = textrow.LanguageCells[Language.English].Text
                    print("Conflicted line will be moved to memoQ:",contextID)

                if curtarget:
                    curtarget = curtarget.replace("\r","")

                #If the source hasn't changed and translation has not been requested, preserve status from previous export
                if cursource == oldSource and contextID not in self.lxtxtDB.translation_requested:
                    curState = oldState

                #### Comment handling #####
                commentlist = []

                try:
                    commentlist.append("%% Label: " + textrow.Label)
                except AttributeError:
                    pass

                try:
                    if textrow.GetCommentCell(Language.Japanese).Comment:
                        commentlist.append("[JP Developers] " + textrow.GetCommentCell(Language.Japanese).Comment)
                except AttributeError:
                    pass
                try:
                    if textrow.GetCommentCell(Language.English).Comment:
                        commentlist.append("[EN Comment]" + textrow.GetCommentCell(Language.English).Comment)
                except AttributeError:
                    pass

                try:
                    if textrow.AttributeCells["Gender"].Text:
                        commentlist.append("%% Gender: " + textrow.AttributeCells["Gender"].Text)
                except AttributeError:
                    pass
                
                #Get the text box type to add to speaker segment
                if textrow.AttributeCells["Talk/Type"]:
                    if textrow.AttributeCells["Talk/Type"].Text:
                        typetext = " <TYPE: " + textrow.AttributeCells["Talk/Type"].Text + ">"
                        #cursource = typetext + cursource
                        if textrow.AttributeCells["wav_name"]:
                            self.type_labels[textrow.AttributeCells["wav_name"].Text] = typetext
                else:
                    typetext = ""

                # If Label has "speech" in it, include the Label before the trans_unit for reference.
                try:
                    if "speech" in textrow.Label or textrow.AttributeCells["Speaker"]:
                        # handling for both
                        if textrow.AttributeCells["Speaker"]:
                            source_speaker = textrow.AttributeCells["Speaker"].Text
                            # Translate speaker
                            try:
                                translated_speaker = self.lxtxtDB.speaker_dict[textrow.AttributeCells["Speaker"].Text]
                                if translated_speaker == "":
                                    translated_speaker = "Untranslated"
                            except KeyError:
                                translated_speaker = "Untranslated"
                            translated_speaker += typetext
                            VO_note_unit = TransUnit.create(Language.Japanese,
                                                            Language.English,
                                                            contextID + "-SPEAKERNAME",
                                                            "<SPEAKER: " + source_speaker + ">",
                                                            translated_speaker,
                                                            [],
                                                            True,
                                                            "final")
                            if "for_audio_language_en" in contextID:
                                envo_file.trans_units.set_value(VO_note_unit)
                            else:
                                new_file.trans_units.set_value(VO_note_unit)
                except AttributeError:
                    pass

                #Add main text
                new_trans_unit = TransUnit.create(Language.Japanese,
                                                  Language.English,
                                                  contextID,
                                                  cursource,
                                                  curtarget,
                                                  commentlist,
                                                  locked,
                                                  curState)
                
                # update conflict checker accordingly
                if contextID in checker_dict[str(relpath_no_ext)]['Strings'] and checker_dict[str(relpath_no_ext)]['Strings'][contextID]['Conflict']:
                    checker_dict[str(relpath_no_ext)]['Strings'][contextID]['TB'] = curtarget
                    checker_edited = True

                if "for_audio_language_en" in contextID:
                    envo_file.trans_units.set_value(new_trans_unit)
                else:
                    new_file.trans_units.set_value(new_trans_unit)

            converted_files.append(new_file)

        converted_files.append(self.create_memoQ_speaker_XLIFF())    
        if not novoice:
            converted_files.append(self.create_voice_script_speaker_XLIFF())
            
        # if checker is edited update json DB
        if checker_edited:
            self.conflict_checker.data_dict['Files'] = checker_dict
            with open(self.conflict_checker.db, 'w', encoding='utf8') as db:
                json.dump(self.conflict_checker.data_dict, db, ensure_ascii=False)
        return converted_files
    
    def convert_graphic_to_xliff(self, only_these: List, include_target: bool = False,):
        converted_files = []
        envo_prefix = Path(self.enAudioPrefix)
        last_text = ""
        for lxtxt_file in self.graphicDB.files:
            # See if this is the one we want to work on, if necessary
            if only_these:
                #if lxtxt_file.path.stem not in only_these:
                relpath = str(lxtxt_file.path.relative_to(self.graphicDB.assets_root))
                relpath_with_stem = relpath[:relpath.rfind(".")]
                if relpath_with_stem not in only_these:
                    continue
            # See if it has translatable strings.
            #if not lxtxt_file.has_translatable_strings:
            #    continue
            # Create the new save path.
            newrelpath = Path(lxtxt_file.path).relative_to(self.graphicDB.assets_root)
            new_file = XLIFFFile.create(self.graphicFolder / newrelpath.with_suffix(".xliff"), self.source_language, self.target_language)
            envo_file = XLIFFFile.create(envo_prefix / newrelpath.with_suffix(".xliff"), self.source_language, self.target_language)

            # Iterate through units in the lxtxt and retrieve the right stuff.
            for textrow in lxtxt_file.interface.Rows:
                # Create unique ID for LXTXT.
                contextID = str(newrelpath) + "-" + textrow.Label
                locked = False
                # Retrieve the line.
                try:
                    if "for_audio_language_en" in contextID:
                        cursource = last_text
                    else:
                        cursource = textrow.LanguageCells[Language.Japanese].Text
                        last_text = cursource
                    # if source is blank, skip
                    #if cursource is None or cursource == "":
                        #continue
                except AttributeError:
                    # If there's no Japanese string in this row, skip it.
                    continue

                #LxSdk reads in line breaks as \r\n, but we only need the \n
                cursource = cursource.replace("\r","")

                #Check the status of the JP line.
                #If it's not ready to translate, add a tag at the beginning of the source text.
                if textrow.LanguageCells[Language.Japanese].Status in unfinalizedStatuses:
                    cursource = "<SOURCE TEXT NOT FINALIZED>\n" + cursource

                #If the JP line is unused or one of those header lines, prepend a tag to the source.
                unused = False
                if textrow.LanguageCells[Language.Japanese].Status.value__ in unusedStatuses:
                    cursource = "<UNUSED>\n" + cursource
                    unused = True

                #Always import a blank XLIFF with state as needs-translation. memoQ will auto-populate through XTranslate.
                curtarget = ""
                curState = "needs-translation"

                #Fill in target text from TB if the user specifies that
                if include_target:
                    try:
                        curtarget = textrow.LanguageCells[Language.English].Text
                        curState = ConvertToXLIFFStatus(textrow.LanguageCells[Language.English].Status)
                    except AttributeError:
                        pass

                #### Comment handling #####
                commentlist = []

                try:
                    commentlist.append("%% Label: " + textrow.Label)
                except AttributeError:
                    pass

                try:
                    if textrow.GetCommentCell(Language.Japanese).Comment:
                        commentlist.append("[JP Developers] " + textrow.GetCommentCell(Language.Japanese).Comment)
                except AttributeError:
                    pass
                try:
                    if textrow.GetCommentCell(Language.English).Comment:
                        commentlist.append("[EN Comment]" + textrow.GetCommentCell(Language.English).Comment)
                except AttributeError:
                    pass

                try:
                    if textrow.AttributeCells["Gender"].Text:
                        commentlist.append("%% Gender: " + textrow.AttributeCells["Gender"].Text)
                except AttributeError:
                    pass

        
                #Get the text box type to add to speaker segment
                #typetext = ""
                #if textrow.AttributeCells["Talk/Type"]:
                #    if textrow.AttributeCells["Talk/Type"].Text:
                #        typetext = " <TYPE: " + textrow.AttributeCells["Talk/Type"].Text + ">"
                #        #cursource = typetext + cursource
                #        if textrow.AttributeCells["wav_name"]:
                #            self.type_labels[textrow.AttributeCells["wav_name"].Text] = typetext

                # If Label has "speech" in it, include the Label before the trans_unit for reference.
                #try:
                #    if "speech" in textrow.Label or textrow.AttributeCells["Speaker"]:
                #        # handling for both
                #        if textrow.AttributeCells["Speaker"]:
                #            source_speaker = textrow.AttributeCells["Speaker"].Text
                #            # Translate speaker
                #            try:
                #                translated_speaker = self.lxtxtDB.speaker_dict[textrow.AttributeCells["Speaker"].Text]
                #                if translated_speaker == "":
                #                    translated_speaker = "Untranslated"
                #            except KeyError:
                #                translated_speaker = "Untranslated"
                #            translated_speaker += typetext
                #            VO_note_unit = TransUnit.create(Language.Japanese,
                #                                            Language.English,
                #                                            contextID + "-SPEAKERNAME",
                #                                            "<SPEAKER: " + source_speaker + ">",
                #                                            translated_speaker,
                #                                            [],
                #                                            True,
                #                                            "final")
                #            if "for_audio_language_en" in contextID:
                #                envo_file.trans_units.set_value(VO_note_unit)
                #            else:
                #                new_file.trans_units.set_value(VO_note_unit)
                #except AttributeError:
                #    pass
                    
                #Add main text
                new_trans_unit = TransUnit.create(Language.Japanese,
                                                  Language.English,
                                                  contextID,
                                                  cursource,
                                                  curtarget,
                                                  commentlist,
                                                  locked,
                                                  curState)
                if "for_audio_language_en" in contextID:
                    envo_file.trans_units.set_value(new_trans_unit)
                else:
                    new_file.trans_units.set_value(new_trans_unit)
            if len(new_file.trans_units):
                converted_files.append(new_file)
            if len(envo_file.trans_units):
                converted_files.append(envo_file)
            converted_files.append(self.create_memoQ_speaker_XLIFF())
        return converted_files

    def convert_lxvbf_to_xliff(self, only_these: List, include_target: bool = False):
        converted_files = []
        conflict_lines = {}
        checker_edited = False
        checker_dict = self.conflict_checker.data_dict['Files']
        #For every file
        for file in self.lxvbfDB.files:
            if self.voice_only_folder not in str(file.path):
                continue
            relpath = str(file.path.relative_to(self.lxvbfDB.assets_root))
            relpath_no_ext = relpath[:relpath.rfind(".")]
            #If the user wants to process only certain files
            if only_these:
                #If the current file isn't on the list
                #if file.path.stem not in only_these:
                if relpath_no_ext not in only_these:
                    #Skip it
                    continue

            # check for conflict    
            check_file = checker_dict[str(relpath_no_ext)]
            if check_file['Conflict']:
                for cid in checker_dict[str(relpath_no_ext)]['Strings']:
                    if checker_dict[str(relpath_no_ext)]['Strings'][cid]['Conflict']:
                        conflict_lines[cid] = 1

            #Create path for XLIFF
            path, filename = os.path.split(relpath_no_ext)
            newfilename = filename + self.voice_script_suffix
            newrelpath = Path(os.path.join(path, newfilename))
            new_file = XLIFFFile.create(newrelpath.with_suffix(".xliff"), "ja", "en")

            for voicerow in file.interface.Rows:
                JPcell = voicerow.Cells[Language.Japanese]
                ENcell = voicerow.Cells[Language.English]
                if JPcell.VoiceFileName == "":
                    contextID = str(relpath) + "-" + voicerow.Label
                else:
                    contextID = str(relpath) + "-" + JPcell.VoiceFileName
                locked = True if str(relpath_no_ext) in self.locked_file_list else False
                try:
                    cursource = JPcell.Text.Text
                    #LxSdk reads in line breaks as \r\n, but we only need the \n
                    cursource = cursource.replace("\r","")
                except AttributeError:
                    continue

                #if not JPcell.Text.Status == LxCellStatus.Completed:
                #    locked = True

                curState = "needs-translation"

                #if not ENcell.VoiceFileRequired:
                if not voicerow.VoiceFileRequired:
                    cursource = "<NO VOICE>" + cursource
                #else:
                #    curtarget = ""
                curtarget = ""
                curState = "needs-translation"
                oldTarget = ""
                oldState = "needs-translation"

                oldDescriptionSource = None
                oldDescriptionTarget = ""
                oldDescriptionStatus = "needs-translation"
                oldDirectionTarget = " "
                oldDirectionStatus = "needs-translation"
                oldDataFound = False

                #If this file exists in memoQ already
                if newrelpath in self.memoQDB.exported_files.keys():
                    #Pull corresponding memoQ XLIFF
                    memoQ_xliff = self.memoQDB.exported_files[newrelpath]
                    #Fill in text from previous version and store status
                    for id, unit in memoQ_xliff.trans_units.items():
                        if id == contextID + "-DESCRIPTION":
                            oldDescriptionSource = unit.source
                            oldDescriptionTarget = unit.target
                            oldDescriptionStatus = unit.status
                        if id == contextID + "-DIRECTION":
                            oldDirectionTarget = unit.target
                            oldDirectionStatus = unit.status
                        if id == contextID:
                            oldTarget = unit.target
                            if cursource == unit.source and contextID not in self.lxvbfDB.translation_requested:
                                oldState = unit.status
                            oldDataFound = True
                        #We've passed all relevant IDs in this file, so stop searching
                        if oldDataFound and contextID not in id:
                            break

                if include_target:
                    curtarget = oldTarget
                    curState = oldState
                
                commentlist = []

                try:
                    commentlist.append("%% Label: " + voicerow.Label)
                except AttributeError:
                    pass

                if JPcell.Comment.Comment:
                    commentlist.append("[JP Developers] " + JPcell.Comment.Comment)

                if ENcell.Comment.Comment: 
                    commentlist.append("[EN Comment]" + ENcell.Comment.Comment)

                try:
                    if voicerow.Category:
                        commentlist.append("[Category]" + voicerow.Category)
                except AttributeError:
                    pass

                #Add stage direction trans unit
                if JPcell.StageDirection.Text:
                    direction = JPcell.StageDirection.Text.replace("\r","")
                    stage_direction_unit = TransUnit.create(Language.Japanese,
                                                            Language.English,
                                                            contextID + "-DESCRIPTION",
                                                            direction,
                                                            "",
                                                            [],
                                                            False,
                                                            curState)
                    new_file.trans_units.set_value(stage_direction_unit)

                #Get text box type from text label
                if voicerow.Label in self.type_labels.keys():
                    text_type = self.type_labels[voicerow.Label]
                else:
                    text_type = ""
                #Add speaker name trans unit
                speaker_unit = None
                try:
                    if JPcell.Speaker:
                        try:
                            translated_speaker = self.lxvbfDB.speaker_dict[JPcell.Speaker]
                            if translated_speaker == "":
                                translated_speaker = "Untranslated"
                        except KeyError:
                            translated_speaker = "Untranslated"
                        translated_speaker += text_type
                        VO_note_unit = TransUnit.create(Language.Japanese,
                                                        Language.English,
                                                        contextID + "-SPEAKERNAME",
                                                        "<SPEAKER: " + JPcell.Speaker + ">",
                                                        translated_speaker,
                                                        [],
                                                        True,
                                                        "final")
                except AttributeError:
                    VO_note_unit =  TransUnit.create(Language.Japanese,
                                                    Language.English,
                                                    contextID + "-SPEAKERNAME",
                                                    "<Missing JP Speaker>",
                                                    "Missing JP Speaker",
                                                    [],
                                                    True,
                                                    "final")
                if speaker_unit is not None:
                    new_file.trans_units.set_value(speaker_unit)
            
                #Add main line trans unit
                new_trans_unit = TransUnit.create(Language.Japanese,
                                                    Language.English,
                                                    contextID,
                                                    cursource,
                                                    curtarget,
                                                    commentlist,
                                                    locked,
                                                    curState)
                new_file.trans_units.set_value(new_trans_unit)
                
                if contextID in checker_dict[str(relpath_no_ext)]['Strings'].keys():
                    if checker_dict[str(relpath_no_ext)]['Strings'][contextID]['Conflict']:
                        checker_dict[str(relpath_no_ext)]['Strings'][contextID]['TB'] = curtarget
                        checker_edited = True

                #Add voice direction trans unit only if voice required
                if ENcell.VoiceFileRequired:
                    voice_direction_unit = TransUnit.create(Language.Japanese,
                                                            Language.English,
                                                            contextID + "-DIRECTION",
                                                            "<Voice Direction for " + contextID + ">",
                                                            " ",
                                                            [],
                                                            False,
                                                            curState)
                    new_file.trans_units.set_value(voice_direction_unit)

                #Add summary trans unit
                if JPcell.Summary.Text:
                    summary_unit = TransUnit.create(Language.Japanese,
                                                    Language.English,
                                                    contextID + "-SUMMARY",
                                                    JPcell.Summary.Text,
                                                    "",
                                                    [],
                                                    False,
                                                    curState)
                    new_file.trans_units.set_value(summary_unit)

            if len(new_file.trans_units):
                converted_files.append(new_file)
            converted_files.append(self.create_memoQ_speaker_XLIFF())

        # update conflict checker json if checker was updated    
        if checker_edited:
            self.conflict_checker.data_dict['Files'] = checker_dict
            with open(self.conflict_checker.db, 'w', encoding='utf8') as db:
                json.dump(self.conflict_checker.data_dict, db, ensure_ascii=False)

        return converted_files



    def update_lxtxt_from_xliff(self, only_these: List = []):
        checker_edited = False
        checker_dict = self.conflict_checker.data_dict['Files']
        for lxtxt_file in self.lxtxtDB.files:
            relpath = str(lxtxt_file.path.relative_to(self.lxtxtDB.assets_root))
            relpath_no_ext = relpath[:relpath.rfind(".")]
            # check for conflicts in the file using the conflict_checker
            check_file = checker_dict[relpath_no_ext]
            # only_these handling
            if only_these and relpath_no_ext not in only_these:
                continue

            # For every ID in the file
            for row in lxtxt_file.interface.Rows:
                # Convert label to uniqueID.
                newrelpath = lxtxt_file.path.relative_to(self.lxtxtDB.assets_root)
                contextID = str(newrelpath) + "-" + row.Label

                # See if this uniqueID exists. If not, pass.
                if contextID not in self.memoQ_xliff_text_dict.keys():
                    continue

                # Pull the XLIFF data for that ID.
                matchedData = self.memoQ_xliff_text_dict[contextID]  # transunit object

                conflict_found = False
                non_compliant_found = False

                # Check if ID exists in Checker DB
                try:
                    if check_file['Strings'][contextID]['Conflict']:
                        print("Conflict found at",contextID)
                        conflict_found = True
                except KeyError:
                    print("ID Not Found in Conflict DB:",contextID)

                ### NON COMPLIANT STRING CHECK ###
                non_compliant_found = self.compliance_checker.check_for_compliance(newrelpath, row.Label, matchedData.target)

                if conflict_found or non_compliant_found:
                    continue

                # Convert generatedID to Label.
                sourcedata = matchedData.source
                sourcedata = sourcedata.replace('<SOURCE TEXT NOT FINALIZED>\n', '')
                sourcedata = sourcedata.replace("<UNUSED>\n","")
                
                # Populate Speaker
                # See if this string has an associated speaker.
                if row.AttributeCells["Speaker"]:
                    # Retrieve speaker from Dict
                    JPspeaker = row.AttributeCells["Speaker"].Text
                    if JPspeaker:
                        try:
                            ENSpeaker = self.lxtxtDB.speaker_dict[JPspeaker]
                        except KeyError as e:
                            print(e)
                            ENSpeaker = ""
                        if row.AttributeCells["Speaker_EN"]:
                            if ENSpeaker != row.AttributeCells["Speaker_EN"].Text:
                                row.AttributeCells["Speaker_EN"].Text = ENSpeaker
                                self.update_change_metadata('Attribute', row.AttributeCells["Speaker_EN"], True, False)
                                lxtxt_file.has_been_edited = True
                        else:
                            new_attribute_cell = LxAttributeCell()
                            new_attribute_cell.Name = "Speaker_EN"
                            new_attribute_cell.Text = ENSpeaker
                            row.AttributeCells.Add(new_attribute_cell)
                            self.update_change_metadata('Attribute', new_attribute_cell, True, False)
                            lxtxt_file.has_been_edited = True

                #Remove extra line break for comparisons with XLIFF text
                jpCell = row.LanguageCells[Language.Japanese]
                lxtxt_jp = jpCell.Text.replace("\r","")
                try:
                    enCell = row.LanguageCells[Language.English]
                    lxtxt_en = enCell.Text.replace("\r","")
                except AttributeError:
                    new_language_cell = LxLanguageCell()
                    new_language_cell.Language = Language.English
                    new_language_cell.Text = ""
                    if jpCell.Status in unusedStatuses:
                        new_language_cell.Status = jpCell.Status
                    else:
                        new_language_cell.Status = LxCellStatus.Editing
                    self.update_change_metadata("Text", new_language_cell, True, True)
                    row.LanguageCells.Add(new_language_cell)
                    enCell = new_language_cell
                    lxtxt_file.has_been_edited = True
                    lxtxt_en = ""

                ###STATUS HANDLING
                #If JP cell is unused, make EN that status as well
                if jpCell.Status in unusedStatuses:
                    if enCell.Status != jpCell.Status:
                        enCell.Status = jpCell.Status
                        enCell.StatusModified.UserName = ModificationUser.default
                        enCell.StatusModified.Time = DateTime.Now
                        lxtxt_file.has_been_edited = True
                #If JP unfinalized, make EN Editing
                elif jpCell.Status in unfinalizedStatuses:
                    if enCell.Status != LxCellStatus.Editing:
                        enCell.Status = LxCellStatus.Editing
                        enCell.StatusModified.UserName = ModificationUser.default
                        enCell.StatusModified.Time = DateTime.Now
                        lxtxt_file.has_been_edited = True
                #If JP finalized and EN editing complete, mark Completed
                elif matchedData.status in statusesForCompletedInTextBridge:
                    if enCell.Status != LxCellStatus.Completed:
                        enCell.Status = LxCellStatus.Completed
                        enCell.StatusModified.UserName = ModificationUser.default
                        enCell.StatusModified.Time = DateTime.Now
                        lxtxt_file.has_been_edited = True
                #If JP finalized and EN editing not complete, mark Editing
                else:
                    if enCell.Status != LxCellStatus.Editing:
                        enCell.Status = LxCellStatus.Editing
                        enCell.StatusModified.UserName = ModificationUser.default
                        enCell.StatusModified.Time = DateTime.Now
                        lxtxt_file.has_been_edited = True        

                #If the source has changed, then skip
                #EN Audio text goes in anyway since the JP source is always "different" from the xliff since it's blank in TB
                #and nothing translates off the EN Audio (so far) so it doesn't hurt to push it every time.

                # Target handling
                # If no target exists, add it in.
                #if row.LanguageCells[Language.English] is None:
                #    lxtxtData.insert_new(Language.English)
                #    lxtxt_file.has_been_edited = True

                #Search linguist comments marked with two slashes and remove
                slashComment = ""
                commentSearch = re.search(r" ?//(.+)$",matchedData.target,re.DOTALL)
                if commentSearch:
                    slashComment = commentSearch.group(1)
                    matchedData.target = matchedData.target.replace(commentSearch.group(0),"")
                #If we used the <NoText> tag, leave the segment blank
                if "<NoText>" in matchedData.target:
                    matchedData.target = ""
                #If we used the <doubleslash> tag, replace with two slashes
                if "<doubleslash>" in matchedData.target:
                    matchedData.target = matchedData.target.replace("<doubleslash>","//")
                # Change the target and status if the text has been updated.
                # If the text hasn't been updated, don't mess with it.
                if lxtxt_en != matchedData.target:
                    # Use the text checker to see if the (memoQ English) is the same as TB English
                    if checker_dict[relpath_no_ext]['Strings'][contextID]['Conflict'] == True:
                        print(f' File: {relpath}, ID: {contextID} has a conflict and could not be updated.')
                        continue
                    # Set the text to the XLIFF data.
                    enCell.Text = matchedData.target
                    self.update_change_metadata('Language', row.LanguageCells[Language.English], True, True)

                    if enCell.Status == LxCellStatus.Completed:
                        for lang in Language.FIGScodes:
                            if row.LanguageCells[lang]:
                                row.LanguageCells[lang].Status = LxCellStatus.TranslationRequested
                    lxtxt_file.has_been_edited = True
                    checker_dict[relpath_no_ext]['Strings'][contextID]['TB'] = matchedData.target
                    checker_edited = True
                #If the target text hasn't changed but the status is not completed, make it completed.
                elif lxtxt_en == matchedData.target and row.LanguageCells[Language.English].Status in unfinalizedStatuses:
                    row.LanguageCells[Language.English].Status = LxCellStatus.Completed
                    self.update_change_metadata('Language', row.LanguageCells[Language.English], False, True)
                    lxtxt_file.has_been_edited = True

                # Comment Handling Change: 7/2020
                ref_comments = matchedData.ref_notes if len(matchedData.ref_notes) else None
                new_comments = matchedData.notes if len(matchedData.notes) else None

                # --> clean up XLIFF <note> unit
                # Identify automated comments and store them for stripping.
                storedcommentsforpurge = []
                if ref_comments is not None:
                    for comment in ref_comments:
                        if any(comment.text.startswith(item) for item in
                               ["[JP", "%%"]):  # Get rid of comments not from this lang
                            storedcommentsforpurge.append(comment.text)

                # ----> remove garbo we inserted (use <ref-note>?)
                # ----> return new_comment without insertions (so only our notes)
                new_comment = ""
                if new_comments is not None:
                    # merge all the comments together
                    mergedcomment = new_comments[0].text
                    # purge the stored comments
                    for item in storedcommentsforpurge:
                        mergedcomment = mergedcomment.replace(item, "")
                    splitcomment = mergedcomment.splitlines(True)
                    for comment in splitcomment:
                        if not comment.startswith("%%") and comment != "\n":  # Strips out blank lines and the %% LABEL
                            new_comment += comment
                new_comment += slashComment

                # --> read in LXTXT comment_cell
                # -----> no comment? just add new and put in
                # -----> yes comment? remove and replace with new one with new_comment

                #if row.GetCommentCell(Language.English):
                # check that content is not identical. if it is, skip.
                if row.CommentCells[Language.English]:
                    en_comment = row.CommentCells[Language.English].Comment.replace("\r","")
                    if en_comment != new_comment:
                        row.CommentCells[Language.English].Comment = new_comment
                        self.update_change_metadata('Comment', row.CommentCells[Language.English], True, False)
                        lxtxt_file.has_been_edited = True
                #If no comment cell exists but we have a comment
                elif new_comment:
                    #Create the cell
                    new_comment_cell = LxCommentCell()
                    new_comment_cell.Language = Language.English
                    new_comment_cell.Comment = new_comment
                    new_comment_cell.CommentModified.UserName = ModificationUser.default
                    new_comment_cell.CommentModified.Time = DateTime.Now
                    row.CommentCells.Add(new_comment_cell)
                    self.update_change_metadata('Comment', new_comment_cell, True, True)
                    lxtxt_file.has_been_edited = True

        #if checker has been edited dump the updated conflict checker db into json file            
        if checker_edited:
            self.conflict_checker.data_dict['Files'] = checker_dict
            with open(self.conflict_checker.db, 'w', encoding='utf8') as db:
                json.dump(self.conflict_checker.data_dict, db, ensure_ascii=False)

    def update_change_metadata(self, type: str, cell, text: bool, status: bool):
        if type == 'Language':
            if text:
                cell.TextModified.UserName = ModificationUser.default
                cell.TextModified.Time = DateTime.Now
            if status:
                cell.StatusModified.UserName = ModificationUser.default
                cell.StatusModified.Time = DateTime.Now
        if type == 'Comment':
            if text:
                cell.CommentModified.UserName = ModificationUser.default
                cell.CommentModified.Time = DateTime.Now   
        if type == 'Attribute':
            if text:
                cell.TextModified.UserName = ModificationUser.default
                cell.TextModified.Time = DateTime.Now

    def populate_speaker_dict(self):
        # We need a speaker dict option for FIGS
        speaker_file = self.memoQDB.get_speaker_file()
        if not speaker_file:
            return
        for _, unit in speaker_file.trans_units.items():
            if unit.source in self.lxtxtDB.speaker_dict:
                self.lxtxtDB.speaker_dict[unit.source] = unit.target
        return
    
    def create_voice_script_speaker_XLIFF(self) -> XLIFFFile:
        relsavepath = Path("memoQ_voice_script_speaker_list.xliff")
        speaker_file = XLIFFFile.create(relsavepath, Language.Japanese, Language.English)
        old_statuses = self.retrieve_old_voice_script_speaker_statuses()
        for entry in self.lxvbfDB.speaker_dict.keys():
            if entry is None or entry == "":
                continue
            id = "Speaker: " + entry
            try:
                status = old_statuses[id]
            except:
                status = "needs-translation"
            new_trans_unit = TransUnit.create(Language.Japanese,
                                              Language.English,
                                              id,
                                              entry,
                                              self.lxvbfDB.speaker_dict[entry],
                                              [],
                                              False,
                                              status)
            speaker_file.trans_units.set_value(new_trans_unit)
        return speaker_file     

    def update_lxvbf_from_xliff(self, only_these: List = []):
        checker_edited = False  
        checker_dict = self.conflict_checker.data_dict['Files']       
        for file in self.lxvbfDB.files:
            relpath = str(file.path.relative_to(self.lxvbfDB.assets_root))
            relpath_no_ext = relpath[:relpath.rfind(".")]
            check_file = checker_dict[relpath_no_ext]
            if only_these:
                #if file.path.stem not in only_these:
                if relpath_no_ext not in only_these:
                    continue
            # check for conflicts in the file using the conflict_checker
            # check for conflicts in the file using the conflict_checker
            for row in file.interface.Rows:

                JPcell = row.Cells[Language.Japanese]
                ENcell = row.Cells[Language.English]
                
                #If the EN cell doesn't exist, create it
                if ENcell == None:
                    new_voice_cell = create_new_voice_cell(Language.English, JPcell.VoiceFileName)
                    row.Cells.Add(new_voice_cell)
                    ENcell = new_voice_cell

                JPspeaker = JPcell.Speaker
                if JPspeaker:
                    ENspeaker = self.lxvbfDB.speaker_dict[JPspeaker]
                    if ENspeaker != ENcell.Speaker:
                        ENcell.Speaker = ENspeaker
                        file.has_been_edited = True

                currentLabel = row.Label
                newrelpath = Path(file.path).relative_to(self.lxvbfDB.assets_root)
                if JPcell.VoiceFileName == "":
                    contextID = str(newrelpath) + "-" + currentLabel
                else:
                    contextID = str(newrelpath) + "-" + JPcell.VoiceFileName

                if contextID not in self.memoQ_xliff_voice_dict.keys():
                    continue
                
                matchedData = self.memoQ_xliff_voice_dict[contextID]

                sourcedata = matchedData.source
                sourcedata = re.sub("<NO VOICE> ?","",sourcedata)
                
                #Remove extra line break for comparisons with XLIFF text
                jp_text = JPcell.Text.Text.replace("\r","")

                #Remove line breaks completely from EN text as we don't want them in the voice script
                en_text = ENcell.Text.Text.replace("\r","")
                en_text = en_text.replace("\n"," ")
                matchedData.target = matchedData.target.replace("\n"," ")
                matchedData.target = matchedData.target.replace("<NO VOICE>", "")

                JPspeaker = JPcell.Speaker
                if JPspeaker:
                    ENspeaker = self.lxvbfDB.speaker_dict[JPspeaker]
                    if ENspeaker != ENcell.Speaker:
                        ENcell.Speaker = ENspeaker
                        file.has_been_edited = True
                
                if matchedData.target == "" or sourcedata != jp_text:
                    continue

                #If no target cell exists
                #Not sure if this is an issue with LXVBFs; dummied out for now
                if ENcell is None:
                    raise

                #Extract double slash comment
                #Since the summary, comment, and direction columns are all being used
                #there's currently no place to store this comment.
                #Theoretically an extra column could be added to VB to hold this,
                #but it doesn't exist yet.
                slashComment = ""
                commentSearch = re.search(r" ?//(.+)$",matchedData.target,re.DOTALL)
                if commentSearch:
                    slashComment = commentSearch.group(1)
                    matchedData.target = matchedData.target.replace(commentSearch.group(0),"")
                #If we used the <NoText> tag, leave the segment blank
                if "<NoText>" in matchedData.target:
                    matchedData.target = ""
                #If we used the <doubleslash> tag, replace with two slashes
                if "<doubleslash>" in matchedData.target:
                    matchedData.target = matchedData.target.replace("<doubleslash>","//")
                #Line
                if en_text != matchedData.target and jp_text == sourcedata:
                    ENcell.Text.Text = matchedData.target
                    ENcell.Text.TextModified.UserName = ModificationUser.default
                    ENcell.Text.TextModified.Time = DateTime.Now
                    #LXTXT version sets cell to complete here.
                    #However, LxSdk does not currently expose LXVBF cell statuses
                    file.has_been_edited = True
                    checker_dict[relpath_no_ext]['Strings'][contextID]['TB'] = matchedData.target
                    checker_edited = True

                 ###STATUS HANDLING
                #If JP cell is unused, make EN that status as well
                if JPcell.Text.Status in unusedStatuses:
                    if ENcell.Text.Status != JPcell.Status:
                        ENcell.Text.Status = JPcell.Status
                        file.has_been_edited = True
                #If JP unfinalized, make EN Editing
                elif JPcell.Text.Status in unfinalizedStatuses:
                    if ENcell.Text.Status != LxCellStatus.Editing:
                        ENcell.Text.Status = LxCellStatus.Editing
                        file.has_been_edited = True
                #If JP finalized and EN editing complete, mark Completed
                elif matchedData.status in statusesForCompletedInTextBridge:
                    if ENcell.Text.Status != LxCellStatus.Completed:
                        ENcell.Text.Status = LxCellStatus.Completed
                        file.has_been_edited = True
                #If JP finalized and EN editing not complete, mark Editing
                else:
                    if ENcell.Text.Status != LxCellStatus.Editing:
                        ENcell.Text.Status = LxCellStatus.Editing
                        file.has_been_edited = True

                #Remove extra line break for comparisons with XLIFF text
                jp_direction = JPcell.StageDirection.Text.replace("\r","")
                en_summary = ENcell.Summary.Text.replace("\r","")
                #JP Stage Direction > EN Summary
                if contextID + "-DESCRIPTION" in self.memoQ_xliff_voice_dict.keys():
                    description_data = self.memoQ_xliff_voice_dict[contextID + "-DESCRIPTION"]
                    if description_data.source == jp_direction and description_data.target != en_summary:
                        ENcell.Summary.Text = description_data.target
                        file.has_been_edited = True
                
                en_direction = ENcell.StageDirection.Text.replace("\r","")
                #memoQ Voice Direction > EN Stage Direction
                if contextID + "-DIRECTION" in self.memoQ_xliff_voice_dict.keys():
                    direction_data = self.memoQ_xliff_voice_dict[contextID + "-DIRECTION"]
                    if direction_data.target != en_direction:
                        ENcell.StageDirection.Text = direction_data.target
                        ENcell.StageDirection.TextModified.UserName = ModificationUser.default
                        ENcell.StageDirection.TextModified.Time = DateTime.Now
                        ENcell.StageDirection.Status = LxCellStatus.Completed
                        file.has_been_edited = True

                en_comment = ENcell.Comment.Comment.replace("\r","")
                #JP Summary > EN Comment
                if contextID + "-SUMMARY" in self.memoQ_xliff_voice_dict.keys():
                    summary_data = self.memoQ_xliff_voice_dict[contextID + "-SUMMARY"]
                    if summary_data.target != en_comment:
                        ENcell.Comment.Comment = summary_data.target
                        ENcell.Comment.CommentModified.UserName = ModificationUser.default
                        ENcell.Comment.CommentModified.Time = DateTime.Now
                        file.has_been_edited = True

        # dump checker data back into json            
        if checker_edited:
            self.conflict_checker.data_dict['Files'] = checker_dict
            with open(self.conflict_checker.db, 'w', encoding='utf8') as db:
                json.dump(self.conflict_checker.data_dict, db, ensure_ascii=False)

    def retrieve_old_voice_script_speaker_statuses(self):
        speaker_file = self.memoQDB.get_voice_script_speaker_file()
        if not speaker_file:
            return {}
        statuses = {}
        for _, unit in speaker_file.trans_units.items():
            statuses["Speaker: " + unit.source] = unit.status
        return statuses

    def populate_voice_script_speaker_dict(self):
        # Takes the Speaker file and adds definitions to the dict.
        speaker_file = self.memoQDB.get_voice_script_speaker_file()
        if not speaker_file:
            return
        for _, unit in speaker_file.trans_units.items():
            if unit.source in self.lxvbfDB.speaker_dict:
                self.lxvbfDB.speaker_dict[unit.source] = unit.target
        return

    def create_memoQ_speaker_XLIFF(self):  # -> XLIFFFile
        relsavepath = Path("memoQ_speaker_list.xliff")  # saves to root
        speaker_file = XLIFFFile.create(relsavepath, Language.Japanese, Language.English)
        combined_dict = {}
        for entry in self.lxtxtDB.speaker_dict.keys():
            combined_dict[entry] = self.lxtxtDB.speaker_dict[entry]
        for entry in self.lxvbfDB.speaker_dict.keys():
            if entry not in combined_dict.keys():
                combined_dict[entry] = self.lxvbfDB.speaker_dict[entry]
        for entry in combined_dict.keys():
            if entry is None:
                continue
            new_trans_unit = TransUnit.create(Language.Japanese,
                                              Language.English,
                                              "Speaker:" + entry,
                                              entry,
                                              "",
                                              [],
                                              False,
                                              "needs-translation")
            speaker_file.trans_units.set_value(new_trans_unit)
        return speaker_file

    def save_changes(self, novoice: bool):
        changelist = []
        changelist = self.lxtxtDB.save_changes()
        if not novoice:
            for item in self.lxvbfDB.save_changes():
                changelist.append(item)
        if changelist:
            self.change_tracker.add_lxtxt_list(changelist)
        return

def ConvertToXLIFFStatus(lxtxtstatus):
    conversiondict = {"None": "notyet",
                      "": "notyet",
                      "NotStarted": "needs-translation",
                      "Editing": "needs-translation",
                      "ParentLanguageEditing": "notyet",
                      "TranslationRequested": "needs-translation",
                      "Completed": "final",
                      "Unused": "notused"}
    return conversiondict[lxtxtstatus]

def ConvertLXVBFToXLIFFStatus(lxvbfstatus):
    conversiondict = {0: "notyet", #None
                      1: "needs-translation", #NotStarted
                      2: "needs-translation", #Editing
                      3: "notyet", #ParentLanguageEditing
                      4: "needs-translation", #TranslationRequested
                      5: "final", #Completed
                      6: "notused", #Unused
                      7: "notused"} #Error
    return conversiondict[lxvbfstatus.value__]

def create_new_voice_cell(lang, voice_file_name) -> LxVoiceCell:
    new_voice_cell = LxVoiceCell()
    new_voice_cell.Language = lang
    new_voice_cell.VoiceFileName = voice_file_name
    new_voice_cell.Text.Text = ""
    new_voice_cell.Speaker = ""
    new_voice_cell.Actor = ""
    #SUMMARY
    summary_cell = LxSummaryCell()
    summary_cell.Text = ""
    new_voice_cell.Summary = summary_cell
    #STAGE DIRECTION
    stage_direction_cell = LxLanguageCell()
    stage_direction_cell.Language = lang
    stage_direction_cell.Text = ""
    stage_direction_cell.TextModified.UserName = ModificationUser.default
    stage_direction_cell.TextModified.Time = DateTime.Now
    stage_direction_cell.StatusModified.UserName = ModificationUser.default
    stage_direction_cell.StatusModified.Time = DateTime.Now
    new_voice_cell.StageDirection = stage_direction_cell
    #COMMENT
    comment_cell = LxCommentCell()
    comment_cell.Language = lang
    comment_cell.Comment = ""
    comment_cell.CommentModified.UserName = ModificationUser.default
    comment_cell.CommentModified.Time = DateTime.Now
    new_voice_cell.Comment = comment_cell
    #EFFECT DESCRIPTION
    effect_cell = LxCommentCell()
    effect_cell.Language = lang
    effect_cell.Comment = ""
    effect_cell.CommentModified.UserName = ModificationUser.default
    effect_cell.CommentModified.Time = DateTime.Now
    new_voice_cell.EffectDescription = effect_cell
    
    return new_voice_cell
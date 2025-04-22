from pathlib import Path
import os
import openpyxl as pxl
from util.lxtxt.lxtxtDatabase import LXTXTDatabase

aston_tb = Path(r'M:\Projects\Aston\TextBridge3\trunk\db')
sparrow_tb = Path(r'M:\Projects\Sparrow\SVN\trunk\db')
elvis_tb = Path(r'')

tb_list = [aston_tb, sparrow_tb]
langs = ['en', 'fr', 'it', 'de', 'es']

for tb_path in tb_list:
    db_dict = {}
    wkbk = pxl.Workbook()
    sh = wkbk.active
    sh[f'A1'].value = 'File'
    sh[f'B1'].value = 'ID'
    sh[f'C1'].value = 'Speaker'
    sh[f'D1'].value = 'EN'
    sh[f'E1'].value = 'FR'
    sh[f'F1'].value = 'IT'
    sh[f'G1'].value = 'DE'
    sh[f'H1'].value = 'ES'
    sh[f'I1'].value = 'Comment'
    lxtxt_db = LXTXTDatabase(tb_path)
    for file in lxtxt_db.files:
        if file not in db_dict.keys():
            db_dict[file.path] = {}
        for textrow in file.interface.Rows:
            if textrow.Label not in db_dict[file.path].keys():
                db_dict[file.path][textrow.Label] = {
                    'en':[],
                    'fr':[],
                    'it':[],
                    'de':[],
                    'es':[]
                }
            for lang in langs:
                if lang in textrow.LanguageCells.keys():
                    if textrow.LanguageCells[lang].Text:
                        text = textrow.LanguageCells[lang].Text 
                    else:
                        text = ""      
                if f'Speaker_{lang.upper()}' in textrow.AttributeCells.keys():
                    spkr = textrow.AttributeCells[f'Speaker_{lang.upper()}'].Text
                else:
                    spkr = ""
                if lang in textrow.CommentCells.keys():
                    if textrow.CommentCells[lang].Text:
                        cmt = textrow.CommentCells[lang].Text
                db_dict[file.path][textrow.Label][lang] = [file, textrow.Label, spkr, text, cmt]
                
print(db_dict)
    
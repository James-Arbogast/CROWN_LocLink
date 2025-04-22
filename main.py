# SEGA of America
# dan.sunstrum@segaamerica.com

from jobs import application
import argparse

parser = argparse.ArgumentParser(description = \
    "Automation tool for Project Crown. Converts Text Bridge and Voice Bridge files for import \
    into memoQ and processes changed text back into TB/VB.")
parser.add_argument("-t", "--push_into_TextBridge", action = "store_true", \
    help = "Export files from memoQ and reflect changes into Text Bridge.")
parser.add_argument("-m", "--pull_into_memoQ", action = "store_true", \
    help = "Convert Text Bridge files to XLIFF for memoQ.")
parser.add_argument("-s", "--update_svn", action = "store_true", \
    help = "Enable SVN interaction (both push and pull).")
parser.add_argument("-e", "--send_emails", action = "store_true", \
    help = "Send an email summarizing what was updated.")
parser.add_argument("-o", "--only_these", nargs = "+", \
    help = "Process only files that match the names given with this flag (relative path, no extension, no leading backslash).")
parser.add_argument("-x", "--export_memoQ", action = "store_true", \
    help = "Export from memoQ any files that are in R2 status.")
parser.add_argument("-p", "--preserve_exported_files", action = "store_true", \
    help = "If files were exported from memoQ, do not delete them afterwards.")
parser.add_argument("-g", "--github", action = "store_true", \
    help = "Backup files with github")
parser.add_argument("-d", "--debug", action = "store_true", \
    help = "Use debug preferences instead of main preferences.")
parser.add_argument("-r", "--reporting", action = "store_true", \
    help = "Run reports on progress and churn in project and deliver to Frost.")
parser.add_argument("--novoice", action = "store_true", \
    help = "Disable VoiceBridge handling.")
args = parser.parse_args()

application.run(args.push_into_TextBridge, args.pull_into_memoQ, args.update_svn, args.send_emails, args.only_these, args.export_memoQ, args.preserve_exported_files, args.github, args.debug, args.reporting, args.novoice)


import git
from git import Repo
from git.exc import GitCommandError
import sys
from pathlib import Path
from util.memoQ.MemoQDatabase import MemoQDatabase
from util.preferences.preferences import Preferences
from datetime import datetime

def github_backup(github_backup_folder):

    repo_path = github_backup_folder
    only_these = []

    """print("Setting up preferences and memoQ DB...")
    preferences =  Preferences.from_existing(r"resources\project_preferences.json")
    memoQDB = MemoQDatabase(preferences.memoQ_inbox,
                                repo_path,
                                preferences.memoQ_server_address,
                                preferences.project_codename)
    print("Exporting memoQ files...")
    memoQDB.test_export(only_these)"""

    #test_branch = [b for b in repo_object.branches if b.name == "master"][0]
    #test_branch.checkout()
    #print(vars(repo_object))
    #sys.exit()
    print("Committing XLIFF Backups...")
    repo_object = Repo(repo_path)
    try:
        repo_object.git.add("-A")
    except GitCommandError:
        print("An error occured while attempting the /'git add/' command")
        return 1

    try:
        repo_object.git.commit(m = "Automated Backup - "+str(datetime.today().strftime('%Y-%m-%d')))
    except GitCommandError as e:
        if "nothing to commit, working tree clean" in e.stdout:
            return 0
        else:
            print("An error occured while attempting the /'git commit/' command")
            return 1

    # try:
    #     repo_object.git.push("--set-upstream","origin")
    # except GitCommandError:
    #     print("An error occured while attempting the /'git push/' command")
    #     return 1

    #print("Finished!")
    return 0

def test_github_backup(confirm_test = False):
    if confirm_test:
        repo_path = Path(r"M:\Projects\Crown\Github\Crown_XLIFF_Backup")
        only_these = []

        #test_branch = [b for b in repo_object.branches if b.name == "master"][0]
        #test_branch.checkout()
        #print(vars(repo_object))
        #sys.exit()
        print("Committing...")
        repo_object = Repo(repo_path)
        try:
            repo_object.git.add("-A")
        except GitCommandError:
            print("An error occured while attempting the /'git add/' command")
            return
        try:
            repo_object.git.commit(m = "TEST Automated Backup - "+str(datetime.today().strftime('%Y-%m-%d')))
        except GitCommandError:
            print("An error occured while attempting the /'git commit/' command")
            return
        try:
            repo_object.git.push("--set-upstream","origin")
        except GitCommandError:
            print("An error occured while attempting the /'git push/' command")
            return
        print("Finished!")

#if __name__ == "__main__":
#    test_github_backup(True)
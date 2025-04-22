# SEGA Europe
# Gordon.Mckendrick@sega.co.uk
import subprocess
from pathlib import Path


class AuthDetails:
    """ Holder for the authentication details needed for SVN, optional depending on the configuration of the SVN """
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

class Handler:
    """Handles SVN actions for working directly with a developer's SVN repository
        assumes the working copy has already been checked out, which should be done manually.

       The usage process should be:
           Handler.update to latest
           <do merging>
           Handler.commit_changes
         nb: if multiple commits have happened at the same time, the commit will fail. Simply retry, including merging again.
               often the simplest way to handle this is just to exit the content connector process,
               and wait for the next time window where it can try again."""

    def __init__(self, working_directory: Path, authDetails: AuthDetails = None, svnurl: str = ""):
        self._svn_filepath = Path("svn") # path of the svn executable itself, or just "svn" if added to environment PATH variable
        self._working_directory = working_directory if isinstance(working_directory, Path) else Path(working_directory)
        self._authDetails = authDetails # optional authentication details
        self._svn_url = svnurl

    def checkout(self, svnurl: str = ""):
        #run checkout command
        if not svnurl:
            if self._svn_url:
                svnurl = self._svn_url
            else:
                return None
        self._run_command(("checkout", svnurl, self._svn_filepath))
        #update svnurl
        if svnurl != self._svn_url:
            self._svn_url = svnurl
        #update working directory to add /svn
        self._working_directory /= "svn"

    def update_to_latest(self):
        self._run_command(("cleanup",))  # unlock all locked files
        self._run_command(("revert", ".", "--recursive"))  # revert all files back to the latest changelist
        self._run_command(("cleanup", "--remove-unversioned"))  # remove all files that aren't versioned
        self._run_command(("update", "."))  # update all versioned files to the latest
        self.files = [str(f) for f in self._working_directory.glob("**/*.*")]
        #self.files = [str(f) for f in self._working_directory.glob(str(self._working_directory / "**/*.*"))]

    def commit_changes(self, message: str):
        current_files = list(str(f) for f in self._working_directory.glob("**/*.*")) # get an updated list of the actual files we have
       
       # remove deleted files
        for deleted_file in [file for file in self.files if file not in current_files]:
            self.delete_file(deleted_file)

        # add new files
        for added_file in [file for file in current_files if file not in self.files]:
            self.add_file(added_file)

        # commit changes
        self._run_command(("commit", "-m", message))

    def delete_file(self, filepath):
        self._run_command(("delete", str(filepath)))

    def add_file(self, filepath):
        self._run_command(("add", str(filepath)))

    def _run_command(self, command: tuple):
        if self._authDetails is not None:
            command += ("--username", self._authDetails.username, "--password", self._authDetails.password)
        command = (str(self._svn_filepath),) + command
        process = subprocess.Popen(command, cwd=str(self._working_directory))
        process.wait() # block until command is finished, otherwise SVN will get into a badly locked state
        pass


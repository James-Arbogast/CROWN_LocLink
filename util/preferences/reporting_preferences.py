import json
from pathlib import Path

class Reporting_Preferences:
    def __init__(self):
        self.reporting_center_location = Path()
        self.proj_name = ''
        self.json_location = Path()
        self.resources_location = Path()
        self.overview_location = Path()
        self.projects_location = Path()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        return

    #saves json in format that works with preference object
    def save_json(self):
        json_data = {"reporting_center_location":str(self.reporting_center_location),
                     "proj_name":str(self.proj_name),
                     "json_location":str(self.json_location),
                     "resources_location":str(self.resources_location),
                     "overview_location":str(self.overview_location),
                     "projects_location":self.projects_location}
        with open(self.json_location, "w") as write_file:
            json.dump(json_data, write_file)

    #takes preferences from already existing json file
    @classmethod
    def from_existing(cls, json_location):
        created = Reporting_Preferences()
        with open(json_location, "r") as read_file:
            data = json.load(read_file)
        created.reporting_center_location = Path(data["reporting_center_location"])
        created.json_location = Path(data["json_location"])
        created.resources_location = Path(data["resources_location"])
        created.overview_location = Path(data["overview_location"])
        created.projects_location = Path(data["projects_location"])
        return created

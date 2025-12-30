import json

class Data:
    def __init__(self):
        # Load all config from single file
        self.config_file = 'config.json'
        self.config = {}
        
        try:
            with open(self.config_file, 'r') as file:
                self.config = json.load(file)
        except FileNotFoundError:
            # Initialize with empty structure if file doesn't exist
            self.config = {
                "commands": {},
                "preferences": {},
                "telemetryFields": {}
            }
            self._save_config()
        
        self.preferences = self.config.get("preferences", {})
        self.telemetryFields = self.config.get("telemetryFields", {})
        self.commands = self.config.get("commands", {})

    def _save_config(self):
        """Save all config data to the single config.json file."""
        self.config["preferences"] = self.preferences
        self.config["telemetryFields"] = self.telemetryFields
        self.config["commands"] = self.commands
        with open(self.config_file, 'w') as file:
            json.dump(self.config, file, indent=4)

    def savePreferences(self):
        self._save_config()

    def getPreferences(self):
        return self.preferences
    
    def setPreference(self, key, value):
        self.preferences[key] = value
        self._save_config()

    def getPreference(self, key):
        return self.preferences.get(key, None)
    
    def addCommand(self, command):
        if "commands" not in self.preferences:
            self.preferences["commands"] = []
        self.preferences["commands"].append(command)
        self._save_config()

    def removeCommand(self, command):
        if "commands" in self.preferences and command in self.preferences["commands"]:
            self.preferences["commands"].remove(command)
            self._save_config()

    def clearCommands(self):
        self.preferences["commands"] = []
        self._save_config()

    def addField(self, field):
        if "fields" not in self.preferences:
            self.preferences["fields"] = []
        self.preferences["fields"].append(field)
        self._save_config()

    def removeField(self, field):
        if "fields" in self.preferences and field in self.preferences["fields"]:
            self.preferences["fields"].remove(field)
            self._save_config()

    def clear_fields(self):
        self.preferences["fields"] = []
        self._save_config()
    
    def getTelemetryFields(self):
        return self.telemetryFields
    
    def getTelemetryField(self, key):
        return self.telemetryFields.get(key, None)
    
    def setTelemetryField(self, key, value):
        self.telemetryFields[key] = value
        self._save_config()
    
    def saveTelemetryFields(self):
        self._save_config()

    def getCommands(self):
        """Return the commands mapping.
        Returns a dict mapping button label -> command string.
        """
        return self.commands
import json

class Data:
    def __init__(self):
        user_preferences = {}
        telemetryFields = {}

        with open('preferences.json', 'r') as file:
            loaded_preferences = json.load(file)
            user_preferences.update(loaded_preferences)
        self.preferences = user_preferences

        with open('telemetryFields.json', 'r') as file:
            loaded_fields = json.load(file)
            telemetryFields.update(loaded_fields)
        self.telemetryFields = telemetryFields

    def savePreferences(self):
        with open('preferences.json', 'w') as file:
            json.dump(self.preferences, file, indent=4)

    def getPreferences(self):
        return self.preferences
    
    def setPreference(self, key, value):
        self.preferences[key] = value
        self.savePreferences()

    def getPreference(self, key):
        return self.preferences.get(key, None)
    
    def addCommand(self, command):
        self.preferences["commands"].append(command)
        self.savePreferences()

    def removeCommand(self, command):
        if command in self.preferences["commands"]:
            self.preferences["commands"].remove(command)
            self.savePreferences()

    def clearCommands(self):
        self.preferences["commands"] = []
        self.savePreferences()

    def addField(self, field):
        self.preferences["fields"].append(field)
        self.savePreferences()

    def removeField(self, field):
        if field in self.preferences["fields"]:
            self.preferences["fields"].remove(field)
            self.savePreferences()

    def clear_fields(self):
        self.preferences["fields"] = []
        self.savePreferences()
    
    def getTelemetryFields(self):
        return self.telemetryFields
    
    def getTelemetryField(self, key):
        return self.telemetryFields.get(key, None)
    
    def setTelemetryField(self, key, value):
        self.telemetryFields[key] = value
        self.saveTelemetryFields()
    
    def saveTelemetryFields(self):
        with open('telemetryFields.json', 'w') as file:
            json.dump(self.telemetryFields, file, indent=4)
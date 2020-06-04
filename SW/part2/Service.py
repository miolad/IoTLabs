# Service class
from EndPoint import EndPoint

class Service:
    def __init__(self, uniqueID: str):
        self.uniqueID = uniqueID
        self.description = ""
        self.endPoints = []

    def addDescription(self, description: str):
        self.description = description

    def addEndPoint(self, endPoint: EndPoint):
        self.endPoints.append(endPoint)

    def serializeService(self) -> dict:
        # Serializes the current Service object and returns a dict representing the same entity
        return {"serviceID": self.uniqueID, "description": self.description, "endPoints": self.endPoints}
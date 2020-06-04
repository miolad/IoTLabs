# Service class
from EndPoint import EndPoint

class Service:
    def __init__(self, serviceID: str):
        self.serviceID = serviceID
        self.description = ""
        self.endPoints = []

    def addDescription(self, description: str):
        self.description = description

    def addEndPoint(self, endPoint: EndPoint):
        self.endPoints.append(endPoint)

    def serialize(self) -> dict:
        # Serializes the current Service object and returns a dict representing the same entity
        serializedEndPoints = []

        for e in self.endPoints:
            serializedEndPoints.append(e.serializeEndPoint())

        return {"serviceID": self.serviceID, "description": self.description, "endPoints": serializedEndPoints, "timestamp": self.timestamp}
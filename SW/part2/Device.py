# Device class
from EndPoint import EndPoint
 
class Device:
    def __init__(self, deviceID, availableResources):
        self.deviceID = deviceID
        self.endPoints = list()
        self.availableResources = availableResources
 
    def addEndPoint(self, endPoint: EndPoint):
        self.endPoints.append(endPoint)

    def serialize(self) -> dict:
        # Serializes the current Device object and returns a dict representing the same entity
        serializedEndPoints = []

        for e in self.endPoints:
            serializedEndPoints.append(e.serializeEndPoint())
        
        return {"deviceID": self.deviceID, "endPoints": serializedEndPoints, "availableResoureces": self.availableResources, "timestamp": self.timestamp}
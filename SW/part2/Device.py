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
        
        return {"deviceID": self.deviceID, "endPoints": serializedEndPoints, "resources": self.availableResources, "timestamp": self.timestamp}

    @staticmethod
    def parseDevice(deviceDesc: dict):
        # Check if every field is present, otherwise raise an exception
        if "deviceID" not in deviceDesc or "endPoints" not in deviceDesc or "resources" not in deviceDesc:
            raise ValueError("JSON doesn't contain necessary params")

        d = Device(deviceDesc["deviceID"], deviceDesc["resources"])

        # Now add the endpoints
        for endPointDesc in deviceDesc["endPoints"]:
            try:
                d.addEndPoint(EndPoint.parseEndPoint(endPointDesc))
            except:
                # Raise another exception with proper description
                raise ValueError("End point is not valid")
        
        return d
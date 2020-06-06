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

    @staticmethod
    def parseService(serviceDesc: dict):
        # Check if every field is present, otherwise raise an exception
        if "serviceID" not in serviceDesc or "description" not in serviceDesc or "endPoints" not in serviceDesc:
            raise ValueError("JSON doesn't contain necessary params")

        s = Service(serviceDesc["serviceID"])
        s.addDescription(serviceDesc["description"])

        # Now add the endpoints
        for endPointDesc in serviceDesc["endPoints"]:
            try:
                s.addEndPoint(EndPoint.parseEndPoint(endPointDesc))
            except:
                # Raise another exception with proper description
                raise ValueError("End point is not valid")
        
        return s
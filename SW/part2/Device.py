# Device class
from EndPoint import EndPoint
 
class Device:
    def __init__(self, deviceID, availableResources):
        self.deviceID = deviceID
        self.endPoints = list()
        self.availableResources = availableResources
 
    def addEndPoint(self, endPoint: EndPoint):
        self.endPoints.append(endPoint)
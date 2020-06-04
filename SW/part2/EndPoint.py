# EndPoint class

class EndPoint:
    TYPE_WEB_SERVICE = 0
    TYPE_MQTT_TOPIC = 1
    
    # Type must
    def __init__(self, service: str, type: bool):
        self.service = service
        self.type = type

    @staticmethod
    def parseEndPoint(endPointJSON: dict):
        pass
# EndPoint class

class EndPoint:
    TYPE_WEB_SERVICE    = 0
    TYPE_MQTT_TOPIC     = 1

    MQTT_PUBLISHER      = 0
    MQTT_SUBSCRIBER     = 1
    
    # Type must
    def __init__(self, service: str, endPointType: bool, mqttPublishOrSubscribe: bool = 0):
        self.service = service
        self.endPointType = endPointType
        self.mqttPublishOrSubscribe = mqttPublishOrSubscribe

    @staticmethod
    def parseEndPoint(endPointDict: dict):
        if "service" not in endPointDict or "type" not in endPointDict:
            raise SyntaxError("dict is not valid")

        endPoint = EndPoint(endPointDict["service"], endPointDict["type"])

        if endPoint.endPointType == EndPoint.TYPE_MQTT_TOPIC:
            if "mqttClientType" not in endPointDict:
                raise SyntaxError("dict is not valid")
                
            endPoint.mqttPublishOrSubscribe = endPointDict["mqttClientType"]

        return endPoint
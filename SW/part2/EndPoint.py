# EndPoint class

class EndPoint:
    TYPE_WEB_SERVICE    = "webService"
    TYPE_MQTT_TOPIC     = "mqttTopic"

    MQTT_PUBLISHER      = "publisher"
    MQTT_SUBSCRIBER     = "subscriber"
    
    def __init__(self, service: str, endPointType: bool):
        self.service = service
        self.endPointType = endPointType
        self.mqttPublishOrSubscribe = EndPoint.MQTT_PUBLISHER # Default option

    def serializeEndPoint(self) -> dict:
        e = {"service": self.service, "type": self.endPointType}
        if self.endPointType == EndPoint.TYPE_MQTT_TOPIC:
            e["mqttClientType"] = self.mqttPublishOrSubscribe

        return e

    @staticmethod
    def parseEndPoint(endPointDict: dict):
        if "service" not in endPointDict or "type" not in endPointDict:
            raise SyntaxError("dict is not valid")

        endPoint = EndPoint(endPointDict["service"], endPointDict["type"])

        if endPoint.endPointType == EndPoint.TYPE_MQTT_TOPIC:
            if "mqttClientType" not in endPointDict:
                raise SyntaxError("dict is not valid")
                
            if endPointDict["mqttClientType"] != EndPoint.MQTT_PUBLISHER and endPointDict["mqttClientType"] != EndPoint.MQTT_SUBSCRIBER:
                raise SyntaxError("dict is not valid")

            endPoint.mqttPublishOrSubscribe = endPointDict["mqttClientType"]

        return endPoint
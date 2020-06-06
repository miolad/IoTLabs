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
    def parseEndPoint(endPointDesc: dict):
        if "service" not in endPointDesc or "type" not in endPointDesc:
            raise ValueError("dict is not valid")

        endPoint = EndPoint(endPointDesc["service"], endPointDesc["type"])

        if endPoint.endPointType == EndPoint.TYPE_MQTT_TOPIC:
            if "mqttClientType" not in endPointDesc:
                raise ValueError("dict is not valid")
                
            if endPointDesc["mqttClientType"] != EndPoint.MQTT_PUBLISHER and endPointDesc["mqttClientType"] != EndPoint.MQTT_SUBSCRIBER:
                raise ValueError("dict is not valid")

            endPoint.mqttPublishOrSubscribe = endPointDesc["mqttClientType"]

        return endPoint
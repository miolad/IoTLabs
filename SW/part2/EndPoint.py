# EndPoint class

class EndPoint:
    TYPE_WEB_SERVICE    = "webService"
    TYPE_MQTT_TOPIC     = "mqttTopic"

    MQTT_PUBLISHER      = "publisher"
    MQTT_SUBSCRIBER     = "subscriber"

    # Whether the service is used to pass data/commands to the device/web service or to get data/information
    WEB_TYPE_PRODUCER   = "producer" # Use the service to get data
    WEB_TYPE_CONSUMER   = "consumer" # Use the service to give commands
    
    def __init__(self, service: str, endPointType: bool):
        self.service = service
        self.endPointType = endPointType

    def serializeEndPoint(self) -> dict:
        e = {"service": self.service, "type": self.endPointType}
        if self.endPointType == EndPoint.TYPE_MQTT_TOPIC:
            e["mqttClientType"] = self.mqttPublishOrSubscribe
        elif self.endPointType == EndPoint.TYPE_WEB_SERVICE:
            e["webType"] = self.webType

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

        elif endPoint.endPointType == EndPoint.TYPE_WEB_SERVICE:
            if "webType" not in endPointDesc:
                raise ValueError("dict is not valid")

            if endPointDesc["webType"] != EndPoint.WEB_TYPE_PRODUCER and endPointDesc["webType"] != EndPoint.WEB_TYPE_CONSUMER:
                raise ValueError("dict is not valid")

            endPoint.webType = endPointDesc["webType"]

        return endPoint
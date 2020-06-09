import paho.mqtt.client as PahoMQTT
import requests
import json
import threading

# Class to publish to the mqtt topic to control the LED connected to the Yun
class MQTTLedController:
    def __init__(self, catalogURL: str, catalogPORT: str, deviceID: str, period: float):
        self.catalogURL = catalogURL
        self.catalogPORT = catalogPORT
        self.deviceID = deviceID

        # Get the mqtt broker from the catalog
        try:
            response = requests.get(self.catalogURL + ":" + str(self.catalogPORT) + "/getMQTTMessageBroker")
            response.raise_for_status()
        except:
            raise ConnectionError("Unable to get mqtt broker from the catalog")

        try:
            responseDict = json.loads(response.text)
            if "url" not in responseDict or "port" not in responseDict:
                raise Exception()
        except:
            raise Exception("Response from catalog was invalid")

        self.brokerURL = responseDict["url"]
        self.brokerPORT = responseDict["port"]

        # Get the specified device from the catalog
        try:
            response = requests.get(self.catalogURL + ":" + str(self.catalogPORT) + "/getDevice", params = {"id": self.deviceID})
            response.raise_for_status()
        except:
            raise ConnectionError("Unable to get desired device from the catalog")

        try:
            device = json.loads(response.text)
        except:
            raise Exception("Response from catalog was invalid")

        # Find the end point corresponding to the resource we want to listen to (led)
        try:
            if "deviceID" not in device or device["deviceID"] != self.deviceID or "resources" not in device or "endPoints" not in device or len(device["resources"]) != len(device["endPoints"]):
                raise Exception()
            temperatureResourceIndex = device["resources"].index("led")
        except:
            raise Exception("Device descriptor invalid or incomplete")

        endPoint = device["endPoints"][temperatureResourceIndex] # This should be the end point we're interested in

        # We expect an mqtt topic set as 'subscriber'
        if "service" not in endPoint or "type" not in endPoint or endPoint["type"] != "mqttTopic" or "mqttClientType" not in endPoint or endPoint["mqttClientType"] != "subscriber":
            raise Exception("End point not as excepted")

        # Finally, we can get the topic to subscribe to
        self.ledTopic = endPoint["service"]

        # Now, setup the mqtt client
        self.mqttClient = PahoMQTT.Client("tiot19_Led_Controller", True)
        self.mqttClient.on_connect = self.onConnect
        
        try:
            self.mqttClient.connect(self.brokerURL, self.brokerPORT)
            self.mqttClient.loop_start()
        except:
            raise ConnectionError("Unable to connect to the MQTT message broker")

        # Registration period
        self.period = period
        self.stopThreadEvent = threading.Event()
        self.running = True
        self.subscribeThread = threading.Thread(target = self.subscribeAsService)
        self.subscribePayload = json.dumps(
            {
                "serviceID": "MQTTLedController",
                "description": "An MQTT client that receives user input and controls the LED connected to the Yun accordingly via MQTT",
                "endPoints": [{"service": self.ledTopic, "type": "mqttTopic", "mqttClientType": "publisher"}]
            })

    def onConnect(self, client, userdata, flags, rc):
        print("Connected to mqtt broker")

    def run(self, characterToExit: str):
        self.subscribeThread.start()
        print("Control the LED with 1 - on, or 0 - off")

        ledControllerSenML = {
            "bn": "Yun",
            "e": [{
                "n": "led",
                "v": 0,
                "t": None,
                "c": None
            }]
        }
        
        while True:
            c = input("> ")

            if c == characterToExit:
                break

            elif c == "0" or c == "1":
                # Shut the led down
                ledControllerSenML["e"][0]["v"] = int(c)
                self.mqttClient.publish(self.ledTopic, payload = json.dumps(ledControllerSenML), qos = 2)

        # Stop the thread
        self.running = False
        self.stopThreadEvent.set()
        self.subscribeThread.join()

    # Function to run in a separate thread that registers this as a web service to the catalog
    def subscribeAsService(self):
        while self.running:
            # Register to the service catalog
            try:
                response = requests.put(self.catalogURL + ":" + str(self.catalogPORT) + "/addService", data = self.subscribePayload)
                response.raise_for_status()
            except:
                print("Error registering service to catalog")

            self.stopThreadEvent.wait(timeout = self.period)

if __name__ == "__main__":
    try:
        temperatureReceiver = MQTTLedController("http://localhost", 8080, "Yun", 60)
    except Exception as e:
        print(str(e))
        exit(-1)

    temperatureReceiver.run("q")

    print("Exiting...")
import threading
import paho.mqtt.client as PahoMQTT
import requests
import json
import time

# Main class to handle periodic mqtt publishes to subscribe the emulated IoT device to the device catalog
class EdgeDeviceEmulator(threading.Thread):
    def __init__(self, catalogURL: str, catalogPORT: int, period: float, payload: str):
        threading.Thread.__init__(self)
        
        self.catalogURL = catalogURL
        self.catalogPORT = catalogPORT

        self.period = period
        self.payload = payload
        
        # Gather the mqtt broker from the catalog
        try:
            response = requests.get(self.catalogURL + ":" + str(self.catalogPORT) + "/getMQTTMessageBroker")
            response.raise_for_status()
        except Exception as e:
            # Raise another exception because we can't continue without the message broker
            raise ConnectionError("Unable to connect to the catalog: " + str(e))

        # Deserialize the response (if it raises an exception just pass it to the caller)
        responseDict = json.loads(response.text)
        
        # Check the response
        if "url" not in responseDict or "port" not in responseDict:
            raise ValueError("Response is not valid: " + str(responseDict))

        self.brokerURL = responseDict["url"]
        self.brokerPORT = responseDict["port"]

        # Initialize the mqtt client
        self.mqttClient = PahoMQTT.Client("tiot19_Device_Emulator", True)
        self.mqttClient.on_connect = self.onConnect

        try:
            self.mqttClient.connect(self.brokerURL, self.brokerPORT)
            self.mqttClient.loop_start()
        except Exception as e:
            raise ConnectionError("Unable to connect to the MQTT message broker: " + str(e))

        # If we got this far, the thread is about to start
        self.running = True
        self.stopEvent = threading.Event()

    def onConnect(self, client, userdata, flags, rc):
        print("Successfully connected to the MQTT broker")

    def run(self):
        while self.running:
            # Publish the subscription payload to the correct topic
            self.mqttClient.publish("/tiot/19/catalog/addDevice", self.payload, 2)
            
            self.stopEvent.wait(timeout = self.period)

    def stop(self):
        self.running = False
        self.stopEvent.set()

# Main function to test the device emulator
if __name__ == "__main__":
    payload = json.dumps({
        "deviceID": "emulatorDevice",
        "availableResources": ["humidityHTTP", "humidityMQTT", "temperatureHTTP", "temperatureMQTT"],
        "endPoints": [
            {"service": "localhost:8080/getHumidity", "type": "webService", "webType": "producer"},
            {"service": "/tiot/19/emulatorDevice/humidity", "type": "mqttTopic", "mqttClientType": "publisher"},
            {"service": "localhost:8080/getTemperature", "type": "webService", "webType": "producer"},
            {"service": "/tiot/19/emulatorDevice/temperature", "type": "mqttTopic", "mqttClientType": "publisher"}
        ]
    })
    
    try:
        deviceEmulator = EdgeDeviceEmulator("http://localhost", 8080, 60, payload)
    except Exception as e:
        print("Error occurred: " + str(e))
        exit(-1)

    deviceEmulator.start()
    
    # Let's give the device emulator 5 minutes, and then stop it
    time.sleep(5 * 60)
    
    deviceEmulator.stop()
    deviceEmulator.join()

    print("Exiting...")
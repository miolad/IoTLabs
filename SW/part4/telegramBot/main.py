import requests
import json
import threading
import time
import paho.mqtt.client as PahoMQTT
import telegram.ext as ext
import matplotlib.pyplot as plt

class TelegramBot:
    def __init__(self, catalogHOST: str, catalogPORT: int):
        self.catalogEndPoint = catalogHOST + ":" + catalogPORT

        # Get the broker from the catalog
        try:
            response = requests.get(self.catalogEndPoint + "/getMQTTMessageBroker")
            response.raise_for_status()
        except:
            raise ConnectionError("Unable to get mqtt broker from the catalog")

        try:
            responseDict = json.loads(response.text)
            if "url" not in responseDict or "port" not in responseDict:
                raise Exception()
        except:
            raise Exception("Response from catalog was invalid")

        self.brokerHOST = responseDict["url"]
        self.brokerPORT = responseDict["port"]

        # Initialize the thread for registration to the catalog
        self.registrationAndRetrivalThread = threading.Thread(target = self.registerAndRetrieveRagistrationsRunner)
        self.running = True
        self.subscribePayload = json.dumps(
            {
                "serviceID": "TelegramBot",
                "description": "A telegram bot that exposes the catalog to end users",
                "endPoints": [{"service": "https://t.me/tiot19ControlBot", "type": "webService", "webType": "producer"}]
            }
        )
        self.catalogAvailable = False
        self.registrationAndRetrivalThread.start()

    def registerAndRetrieveRagistrationsRunner(self):
        # Periodically registers to the service catalog and retrieves registered devices/services
        # to have an always up-to-date internal list of end points to monitor in order to have
        # an history of data and not just the latest communication
        while self.running:
            try:
                self.catalogAvailable = True
                response = requests.put(self.catalogEndPoint + "/addService", data = self.subscribePayload)
                response.raise_for_status()
            except:
                self.catalogAvailable = False

            # TODO: retrieve registered devices/services from the catalog

            time.sleep(60)
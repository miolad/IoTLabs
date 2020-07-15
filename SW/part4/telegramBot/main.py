import requests
import json
import threading
import time
import paho.mqtt.client as PahoMQTT
import telegram.ext as ext
import telegram
import matplotlib.pyplot as plt

class TelegramBot:
    def __init__(self, catalogHOST: str, catalogPORT: int, botToken: str):
        print("LOG: Telegram Bot initialization BEGIN")
        
        self.catalogEndPoint = catalogHOST + ":" + str(catalogPORT)
        self.availableDevices  = {}
        self.availableServices = {}

        self.telegramBotToken = botToken

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
        self.running = False
        self.subscribePayload = json.dumps(
            {
                "serviceID": "TelegramBot",
                "description": "A telegram bot that exposes the catalog to end users",
                "endPoints": [{"service": "https://t.me/tiot19ControlBot", "type": "webService", "webType": "producer"}]
            }
        )
        self.catalogAvailable = False
        self.retrieveRegistrationsLock = threading.Lock()

        # Initialize the Telegram Bot
        self.botUpdater = ext.Updater(token = self.telegramBotToken, use_context = True)
        self.botDispatcher = self.botUpdater.dispatcher
        self.botDispatcher.add_handler(ext.CommandHandler(command = "start", callback = self.botClbStart))

        print("LOG: Telegram Bot initialization END")

    def start(self):
        # Start the subscribing thread
        self.running = True
        self.registrationAndRetrivalThread.start()

        # Start the bot
        self.botUpdater.start_polling()

        print("LOG: Telegram Bot STARTED")

    def registerAndRetrieveRagistrationsRunner(self):
        # Periodically registers to the service catalog and retrieves registered devices/services
        # to have an always up-to-date internal list of end points to monitor in order to have
        # an history of data and not just the latest communication
        while self.running:
            try:
                self.catalogAvailable = True
                response = requests.put(self.catalogEndPoint + "/addService", data = self.subscribePayload)
                response.raise_for_status()

                self.retrieveRegistrations()
            except:
                self.catalogAvailable = False

            time.sleep(60)
    
    def retrieveRegistrations(self):
        # This piece of code will be executed by two distinct threads -> it must be synchronized
        self.retrieveRegistrationsLock.acquire(blocking = True)

        try:
            response = requests.get(self.catalogEndPoint + "/getDevices")
            response.raise_for_status()
            availableDevicesList = json.loads(response.text)

            response = requests.get(self.catalogEndPoint + "/getServices")
            response.raise_for_status()
            availableServicesList = json.loads(response.text)

            # Remove this service
            for s in availableServicesList:
                if s["serviceID"] == "TelegramBot":
                    availableServicesList.remove(s)
                    break
            
            print("LOG: updating available services and devices")
            
            # Update self.availableServices and self.availableDevices
            self.availableServices = {}
            self.availableDevices = {}
            
            for s in availableServicesList:
                print("Adding " + s["serviceID"])
                del s["timestamp"]
                self.availableServices[s["serviceID"]] = s

            for d in availableDevicesList:
                print("Adding " + d["deviceID"])
                del d["timestamp"]
                self.availableDevices[d["deviceID"]] = d

            print("LOG: update complete")
            
            self.retrieveRegistrationsLock.release()
        except:
            # Make sure to release the lock even in case of exceptions
            self.retrieveRegistrationsLock.release()
            raise Exception()

    def botClbStart(self, update: telegram.Update, context: ext.CallbackContext):
        print("LOG: Incoming 'start' command")
        
        # Send introductory message
        if not self.catalogAvailable:
            message = "Hi, currently the catalog is not available"
        else:
            self.retrieveRegistrations()
            message = "Hi, currently connected to the catalog at " + self.catalogEndPoint + \
                      ".\n\nAvailable devices: " + str(self.availableDevices) + \
                      "\n\nAvailable services: " + str(self.availableServices)
        
        context.bot.send_message(chat_id = update.effective_chat.id, text = message)

if __name__ == "__main__":
    bot = TelegramBot("http://localhost", 8080, "1229244529:AAGhUR_oqvcp-nToD4yPwhOk7NM_o57qbLQ")
    bot.start()
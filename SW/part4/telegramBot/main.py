import requests
import json
import threading
import time
import paho.mqtt.client as PahoMQTT
import telegram.ext as ext
import telegram
import matplotlib.pyplot as plt

# Takes an end point as a python dict and produces its string representation for displaying as a telegram menu button.
# Assumes the end point is valid
def endPointToMenuButton(endPoint) -> str:
    res = ""

    if endPoint["type"] == "webService":
        res += "HTTP"
        
        if endPoint["webType"] == "producer":
            res += " prod: "
        else:
            res += " cons: "
        
    else:
        res += "MQTT"

        if endPoint["mqttClientType"] == "subscriber":
            res += "sub: "
        else:
            res += "pub: "
    
    return res + endPoint["service"]

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
        self.botDispatcher.add_handler(ext.CallbackQueryHandler(self.botClbQueryHandler))

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
        # (if another thread is already executing this code, just wait for its completion and not do it again)
        if not self.retrieveRegistrationsLock.acquire(blocking = False):
            # Wait until the owner of the lock is done and then return
            self.retrieveRegistrationsLock.acquire(blocking = True)
            self.retrieveRegistrationsLock.release()
            return

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
            message = "Hi, currently connected to the catalog at " + self.catalogEndPoint
        
        context.bot.send_message(chat_id = update.effective_chat.id, text = message)

        if self.catalogAvailable:
            self.botMainMenu(update, context)

    def botMainMenu(self, update: telegram.Update, context: ext.CallbackContext):
        # Send the list of available devices and services as a button menu
        self.retrieveRegistrations()
        message = "Choose one of the available devices or services"
        context.bot.send_message(chat_id = update.effective_chat.id, text = message)

        # Build the menu
        # Services
        if len(self.availableServices) > 0:
            menu = []
            for s in self.availableServices.values():
                menu.append([telegram.InlineKeyboardButton(s["serviceID"], callback_data = "s_" + s["serviceID"])])
            
            context.bot.send_message(chat_id = update.effective_chat.id, text = "Services:", reply_markup = telegram.InlineKeyboardMarkup(menu))
        else:
            context.bot.send_message(chat_id = update.effective_chat.id, text = "No registered service")

        # Devices
        if len(self.availableDevices) > 0:
            menu = []
            for d in self.availableDevices.values():
                menu.append([telegram.InlineKeyboardButton(d["deviceID"], callback_data = "d_" + d["deviceID"])])
            
            context.bot.send_message(chat_id = update.effective_chat.id, text = "Devices:", reply_markup = telegram.InlineKeyboardMarkup(menu))
        else:
            context.bot.send_message(chat_id = update.effective_chat.id, text = "No registered device")
    
    def botClbQueryHandler(self, update: telegram.Update, context: ext.CallbackContext):
        data = update.callback_query.data
        
        # Discriminate between devices and services
        if data[0:1] == "s":
            # Service
            # Check if the service is still valid (could be an outdated request)
            print("Checking '" + data[2:] + "'")
            if data[2:] not in self.availableServices:
                context.bot.send_message(chat_id = update.effective_chat.id, text = "The selected service is no longer available")
                self.botMainMenu(update, context)
            
            self.botHandleServiceRequest(update, context, data[2:])

        elif data[0:1] == "d":
            # Device
            print("Checking '" + data[2:] + "'")
            if data[2:] not in self.availableDevices:
                context.bot.send_message(chat_id = update.effective_chat.id, text = "The selected device is no longer available")
                self.botMainMenu(update, context)

            self.botHandleDeviceRequest(update, context, data[2:])
        
        elif data[0:1] == "m":
            # Go to main menu
            self.botMainMenu(update, context)

        # Else it's an invalid request, ignore it
    
    def botHandleServiceRequest(self, update: telegram.Update, context: ext.CallbackContext, serviceID: str):
        print("Handling service request for " + serviceID)

        message = serviceID + "\n\nDescription:\n" + self.availableServices[serviceID]["description"]
        context.bot.send_message(chat_id = update.effective_chat.id, text = message)

        # Produce list of end points
        menu = []
        for (i, e) in enumerate(self.availableServices[serviceID]["endPoints"]):
            # Telegram API has a nasty 64 byte limitation on the callback_data, so I had to get creative
            menu.append([telegram.InlineKeyboardButton(endPointToMenuButton(e), callback_data = "e_s_" + serviceID + "_" + str(i))])
        
        # Append 'go back' button
        menu.append([telegram.InlineKeyboardButton("Go Back", callback_data = "m")])

        if len(menu) == 1:
            context.bot.send_message(chat_id = update.effective_chat.id, text = "No end point available", reply_markup = telegram.InlineKeyboardMarkup(menu))
        else:
            context.bot.send_message(chat_id = update.effective_chat.id, text = "Available end points:", reply_markup = telegram.InlineKeyboardMarkup(menu))

    def botHandleDeviceRequest(self, update: telegram.Update, context: ext.CallbackContext, deviceID: str):
        print("Handling device request for " + deviceID)

        message = deviceID + "\n\nResources:\n" + str(self.availableDevices[deviceID]["resources"])
        context.bot.send_message(chat_id = update.effective_chat.id, text = message)

        # Produce list of end points
        menu = []
        for (i, e) in enumerate(self.availableDevices[deviceID]["endPoints"]):
            menu.append([telegram.InlineKeyboardButton(endPointToMenuButton(e), callback_data = "e_d_" + deviceID + str(i))])
        
        # Append 'go back' button
        menu.append([telegram.InlineKeyboardButton("Go Back", callback_data = "m")])

        if len(menu) == 1:
            context.bot.send_message(chat_id = update.effective_chat.id, text = "No end point available", reply_markup = telegram.InlineKeyboardMarkup(menu))
        else:
            context.bot.send_message(chat_id = update.effective_chat.id, text = "Available end points:", reply_markup = telegram.InlineKeyboardMarkup(menu))

if __name__ == "__main__":
    bot = TelegramBot("http://localhost", 8080, "1229244529:AAGhUR_oqvcp-nToD4yPwhOk7NM_o57qbLQ")
    bot.start()
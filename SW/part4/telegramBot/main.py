import requests
import json
import threading
import time
import paho.mqtt.client as PahoMQTT
import telegram.ext as ext
import telegram
import matplotlib.pyplot as plt
import io

# Takes an end point as a python dict and produces its string representation for displaying as a telegram menu button.
# Assumes the end point is valid
def endPointToMenuButton(endPoint) -> str:
    res = ""

    try:
        if endPoint["type"] == "webService":
            res += "HTTP"
            
            if endPoint["webType"] == "producer":
                res += " prod: "
            elif endPoint["webType"] == "consumer":
                res += " cons: "
            else:
                raise Exception()
            
        elif endPoint["type"] == "mqttTopic":
            res += "MQTT"

            if endPoint["mqttClientType"] == "subscriber":
                res += " sub: "
            elif endPoint["mqttClientType"] == "publisher":
                res += " pub: "
            else:
                raise Exception()
        
        res = res + endPoint["service"]
    except:
        res = "INVALID ENDPOINT"
    
    return res

def endPointToCallbackData(endPoint) -> str:
    cbd = "e_"

    try:
        if endPoint["type"] == "webService":
            cbd += "w"
            
            if endPoint["webType"] == "producer":
                cbd += "p"
            elif endPoint["webType"] == "consumer":
                cbd += "c"
            else:
                raise Exception()
            
        elif endPoint["type"] == "mqttTopic":
            cbd += "m"

            if endPoint["mqttClientType"] == "subscriber":
                cbd += "s"
            elif endPoint["mqttClientType"] == "publisher":
                cbd += "p"
            else:
                raise Exception()
        
        cbd += "_" + endPoint["service"]
    except:
        cbd = ""

    return cbd

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
        self.botDispatcher.add_handler(ext.MessageHandler(ext.Filters.text, self.botMessageHandler))

        # Initialize MQTT
        self.mqttReceivedValues = {} # Store, for every device/service that produces mqtt messages, a list of values (the most recent 64), so that we can then
                                     # produce a nice chart of that data and send it as a Telegram image.
                                     # The only drawback is that we must assume a common syntax for every mqtt resource, and that will be SenML.
        self.mqttReceivedValuesThreshold = 64 # Keep only the newest 64 values and discard the rest

        self.pendingAlerts = {} # For pending inputs of alert thresholds
        
        self.mqttClient = PahoMQTT.Client("tiot19_Catalog_Telegram_Bot", True)
        self.mqttClient.on_message = self.mqttOnMessage

        try:
            self.mqttClient.connect(self.brokerHOST, self.brokerPORT)
            self.mqttClient.loop_start()
        except:
            raise ConnectionError("Unable to connect to the MQTT message broker")

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
        # (if another thread is already executing this code, just wait for its completion and don't do it again)
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
            availableServicesNew = {}
            availableDevicesNew = {}
            
            for s in availableServicesList:
                del s["timestamp"]
                availableServicesNew[s["serviceID"]] = s

            for d in availableDevicesList:
                del d["timestamp"]
                availableDevicesNew[d["deviceID"]] = d

            # Now we must compare available***New with self.available*** to check for differences, i.e. new devices/services that we must track,
            # or disconnected devices/services whose data we must delete

            # Check for new instances
            for s in availableServicesNew.keys():
                if s not in self.availableServices:
                    print("Adding service '" + s + "'")
                    
                    # Check if it has mqtt publisher end points
                    for e in availableServicesNew[s]["endPoints"]:
                        if e["type"] == "mqttTopic" and e["mqttClientType"] == "publisher":
                            if e["service"] not in self.mqttReceivedValues:
                                # Subscribe to this topic
                                self.mqttReceivedValues[e["service"]] = {"amt": 1, "values": [], "alerts": {}} # amt: "amount" -> how many different devices/services
                                                                                                               # publish on that topic
                                self.mqttClient.subscribe(e["service"], 2)
                            else:
                                self.mqttReceiveValues[e["service"]]["amt"] += 1
            
            for d in availableDevicesNew.keys():
                if d not in self.availableDevices:
                    print("Adding device '" + d + "'")
                    
                    for e in availableDevicesNew[d]["endPoints"]:
                        if e["type"] == "mqttTopic" and e["mqttClientType"] == "publisher":
                            if e["service"] not in self.mqttReceivedValues:
                                self.mqttReceivedValues[e["service"]] = {"amt": 1, "values": [], "alerts": {}}
                                self.mqttClient.subscribe(e["service"], 2)
                            else:
                                self.mqttReceiveValues[e["service"]]["amt"] += 1

            # Check for disconnected instances
            for s in self.availableServices.keys():
                if s not in availableServicesNew:
                    print("Removing service '" + s + "'")
                    
                    for e in self.availableServices[s]["endPoints"]:
                        if e["type"] == "mqttTopic" and e["mqttClientType"] == "publisher":
                            self.mqttReceivedValues[e["service"]]["amt"] -= 1
                            
                            if self.mqttReceivedValues[e["service"]]["amt"] == 0:
                                self.mqttClient.unsubscribe(e["service"])
                                del self.mqttReceivedValues[e["service"]]

            for d in self.availableDevices.keys():
                if d not in availableDevicesNew:
                    print("Removing device '" + d + "'")
                    
                    for e in self.availableDevices[d]["endPoints"]:
                        if e["type"] == "mqttTopic" and e["mqttClientType"] == "publisher":
                            self.mqttReceivedValues[e["service"]]["amt"] -= 1

                            if self.mqttReceivedValues[e["service"]]["amt"] == 0:
                                self.mqttClient.unsubscribe(e["service"])
                                del self.mqttReceivedValues[e["service"]]

            # Finally, swap the dicts
            self.availableServices = availableServicesNew
            self.availableDevices = availableDevicesNew

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
            message = "Hi, the catalog is currently unavailable"
        else:
            message = "Hi, currently connected to the catalog at " + self.catalogEndPoint
        
        context.bot.send_message(chat_id = update.effective_chat.id, text = message)

        if self.catalogAvailable:
            self.botMainMenu(update, context)

    def botMainMenu(self, update: telegram.Update, context: ext.CallbackContext):
        # Send the list of available devices and services as a button menu
        msg = context.bot.send_message(chat_id = update.effective_chat.id, text = "Fetching data...")
        
        try:
            if not self.catalogAvailable:
                raise Exception()

            self.retrieveRegistrations()
        except:
            print("ERROR: in botMainMenu -> retrieveRegistrations failed, it seems that the catalog is not really available")
            # context.bot.send_message(chat_id = update.effective_chat.id, text = "Ooops!\n\nIt seems that the catalog is not available. Please try again later.")
            context.bot.edit_message_text(chat_id = update.effective_chat.id,
                                          message_id = msg.message_id,
                                          text = "Ooops!\n\nIt seems that the catalog is not available. Please try again later.")

            return
            
        message = "Choose one of the available devices or services"
        # context.bot.send_message(chat_id = update.effective_chat.id, text = message)
        context.bot.edit_message_text(chat_id = update.effective_chat.id,
                                      message_id = msg.message_id,
                                      text = message)

        # Build the menu
        # Services
        if len(self.availableServices) > 0:
            menu = []
            for s in self.availableServices.values():
                menu.append([telegram.InlineKeyboardButton(s["serviceID"], callback_data = "s_" + s["serviceID"])])
            
            context.bot.send_message(chat_id = update.effective_chat.id, text = "Services:", reply_markup = telegram.InlineKeyboardMarkup(menu))
        else:
            context.bot.send_message(chat_id = update.effective_chat.id, text = "No registered services")

        # Devices
        if len(self.availableDevices) > 0:
            menu = []
            for d in self.availableDevices.values():
                menu.append([telegram.InlineKeyboardButton(d["deviceID"], callback_data = "d_" + d["deviceID"])])
            
            context.bot.send_message(chat_id = update.effective_chat.id, text = "Devices:", reply_markup = telegram.InlineKeyboardMarkup(menu))
        else:
            context.bot.send_message(chat_id = update.effective_chat.id, text = "No registered devices")
    
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
        
        # Main menu
        elif data[0:1] == "m":
            # Go to main menu
            self.botMainMenu(update, context)

        # End points
        elif data[0:1] == "e":
            self.botHandleEndPointRequest(update, context, data[2:])

        # Alerts
        elif data[0:1] == "a":
            # Add or remove alert?
            if data[1:2] == "a":
                # Add
                self.botAddAlert(update, context, data[3:])
            elif data[1:2] == "r":
                # Remove
                self.botRemoveAlert(update, context, data[3:])

        # Else it's an invalid request, ignore it
    
    def botHandleServiceRequest(self, update: telegram.Update, context: ext.CallbackContext, serviceID: str):
        print("Handling service request for " + serviceID)

        message = serviceID + "\n\nDescription:\n" + self.availableServices[serviceID]["description"]
        context.bot.send_message(chat_id = update.effective_chat.id, text = message)

        # Produce list of end points
        menu = []
        for e in self.availableServices[serviceID]["endPoints"]:
            # Telegram API has a nasty 64 byte limitation on the callback_data, so I had to get creative
            menu.append([telegram.InlineKeyboardButton(endPointToMenuButton(e), callback_data = endPointToCallbackData(e))])
        
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
        for e in self.availableDevices[deviceID]["endPoints"]:
            menu.append([telegram.InlineKeyboardButton(endPointToMenuButton(e), callback_data = endPointToCallbackData(e))])
        
        # Append 'go back' button
        menu.append([telegram.InlineKeyboardButton("Go Back", callback_data = "m")])

        if len(menu) == 1:
            context.bot.send_message(chat_id = update.effective_chat.id, text = "No end point available", reply_markup = telegram.InlineKeyboardMarkup(menu))
        else:
            context.bot.send_message(chat_id = update.effective_chat.id, text = "Available end points:", reply_markup = telegram.InlineKeyboardMarkup(menu))
    
    def botHandleEndPointRequest(self, update: telegram.Update, context: ext.CallbackContext, endPointID: str):
        print("Handling end point request for " + endPointID)
        endPoint = endPointID[3:]

        # MQTT publisher
        if endPointID[0:2] == "mp":
            if endPoint not in self.mqttReceivedValues:
                return
            
            # Build the button to allow the user to (un)subscribe to alerts for this resource
            if update.effective_chat.id in self.mqttReceivedValues[endPoint]["alerts"]:
                button = telegram.InlineKeyboardButton("Remove alert for " + endPoint, callback_data = "ar_" + endPoint)
            else:
                button = telegram.InlineKeyboardButton("Add alert for " + endPoint, callback_data = "aa_" + endPoint)
            
            menu = [[button]]
            
            context.bot.send_message(chat_id = update.effective_chat.id,
                                     text = "I collected " + str(len(self.mqttReceivedValues[endPoint]["values"])) + " value(s) for resource '" + endPoint + "'",
                                     reply_markup = telegram.InlineKeyboardMarkup(menu))

            if len(self.mqttReceivedValues[endPoint]["values"]) > 1:
                # Get the list of values
                values = []
                times = []
                eventBased = False
                
                for v in self.mqttReceivedValues[endPoint]["values"]:
                    for e in v["e"]:
                        times.append(e["t"])
                        
                        # Need to differentiate between resources with values (i.e. temperature) and event-based resources (i.e. sound or pir)
                        if e["v"] != None and e["u"] != None:
                            values.append(e["v"])
                        else:
                            values.append(1)
                            eventBased = True
                    
                # Generate the chart
                if eventBased:
                    plt.plot(times, values, "x")
                    unit = ""
                    plt.yticks([0, 1, 2], ["", "ON", ""])
                else:
                    plt.plot(times, values)
                    unit = " [" + self.mqttReceivedValues[endPoint]["values"][0]["e"][0]["u"] + "]"

                plt.ylabel(endPoint + unit)
                plt.xlabel("time [s]")
                plt.title("Latest " + str(len(values)) + " values for " + endPoint + ".")

                # Save the image in a buffer
                buf = io.BytesIO()
                plt.savefig(fname = buf, format = "png", dpi = 200, bbox_inches = "tight")
                plt.close()
                buf.seek(0)

                # Send the image via Telegram
                # context.bot.send_photo(chat_id = update.effective_chat.id, photo = open("tmp.png", "rb"))
                context.bot.send_photo(chat_id = update.effective_chat.id, photo = buf)
                buf.close()
    
    def botAddAlert(self, update: telegram.Update, context: ext.CallbackContext, endPoint: str):
        if endPoint not in self.mqttReceivedValues:
            return

        # We must ask the user for the threshold to trigger the alert (a numerical value)
        self.pendingAlerts[update.effective_chat.id] = endPoint

        context.bot.send_message(chat_id = update.effective_chat.id, text = "Please, input the desired threshold for the alert")

    def botRemoveAlert(self, update: telegram.Update, context: ext.CallbackContext, endPoint: str):
        if endPoint in self.mqttReceivedValues and update.effective_chat.id in self.mqttReceivedValues[endPoint]["alerts"]:
            del self.mqttReceivedValues[endPoint]["alerts"][update.effective_chat.id]

            context.bot.send_message(chat_id = update.effective_chat.id, text = "Correctly removed alert for resource " + endPoint)
    
    def botMessageHandler(self, update: telegram.Update, context: ext.CallbackContext):
        if update.effective_chat.id not in self.pendingAlerts or self.pendingAlerts[update.effective_chat.id] not in self.mqttReceivedValues:
            return

        # Try to parse the text as a number
        try:
            alertThreshold = float(update.message.text)
        except:
            context.bot.send_message(chat_id = update.effective_chat.id, text = "Invalid threshold. Please input a numerical value.")
            return

        self.mqttReceivedValues[self.pendingAlerts[update.effective_chat.id]]["alerts"][update.effective_chat.id] = alertThreshold
        del self.pendingAlerts[update.effective_chat.id]

        context.bot.send_message(chat_id = update.effective_chat.id, text = "Alert correctly configured.")
    
    def mqttOnMessage(self, client, userdata, message):
        # print("Received message number " + str(len(self.mqttReceivedValues[message.topic]["values"])) + " in topic " + message.topic)
        
        try:
            msg = json.loads(message.payload.decode())
        except:
            return

        self.mqttReceivedValues[message.topic]["values"].append(msg)
        
        # Remove any message that exceeds the predefined threshold (from the oldest)
        if len(self.mqttReceivedValues[message.topic]["values"]) > self.mqttReceivedValuesThreshold:
            self.mqttReceivedValues[message.topic]["values"].pop(0)

        # Check for alerts
        try:
            for e in msg["e"]:
                v = float(e["v"])
                for c, t in self.mqttReceivedValues[message.topic]["alerts"].items():
                    if v >= t:
                        # Send alert to chat c
                        self.botUpdater.bot.send_message(chat_id = c, text = "ALERT: Resource '" + message.topic + "' reported value " + str(v) + " " + e["u"] + \
                                                                             ", which is higher than the specified threshold of " + str(t) + " " + e["u"])
        except:
            pass

if __name__ == "__main__":
    bot = TelegramBot("http://localhost", 8080, "1229244529:AAGhUR_oqvcp-nToD4yPwhOk7NM_o57qbLQ")
    bot.start()
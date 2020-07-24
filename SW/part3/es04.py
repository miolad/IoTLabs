import cherrypy
import paho.mqtt.client as PahoMQTT
import json
import requests
import threading
import time

class RemoteSmartHomeController(cherrypy.process.plugins.SimplePlugin):
    exposed = True

    def __init__(self, catalogURL: str, catalogPORT: int, deviceID: str, subscribePeriod: float):
        cherrypy.process.plugins.SimplePlugin.__init__(self, cherrypy.engine)
        
        self.catalogEndPoint = catalogURL + ":" + str(catalogPORT)
        self.deviceID = deviceID

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

        self.brokerURL = responseDict["url"]
        self.brokerPORT = responseDict["port"]

        # Get the specified device from the catalog
        try:
            response = requests.get(self.catalogEndPoint + "/getDevice", params = {"id": self.deviceID})
            response.raise_for_status()
        except:
            raise ConnectionError("Unable to get desired device from the catalog")

        try:
            device = json.loads(response.text)
        except:
            raise Exception("Response from catalog was invalid")

        # Find the end points we want to subscribe to, and the ones we want to publish to
        try:
            if "deviceID" not in device or device["deviceID"] != self.deviceID or "resources" not in device or "endPoints" not in device or len(device["resources"]) != len(device["endPoints"]):
                raise Exception()
            
            temperatureResourceIndex = device["resources"].index("temperature")
            pirResourceIndex         = device["resources"].index("pir")
            soundResourceIndex       = device["resources"].index("sound")
            lcdResourceIndex         = device["resources"].index("lcd")
            actuationResourceIndex   = device["resources"].index("actuation")
        except:
            raise Exception("Device descriptor invalid or incomplete")

        endPoints = device["endPoints"]

        for i in [temperatureResourceIndex, pirResourceIndex, soundResourceIndex, lcdResourceIndex, actuationResourceIndex]:
            if "service" not in endPoints[i] or "type" not in endPoints[i] or endPoints[i]["type"] != "mqttTopic":
                raise Exception("End points not as expected")

        self.topics = {}
        self.topics["temperature"] = {"topic": endPoints[temperatureResourceIndex]["service"], "type": endPoints[temperatureResourceIndex]["mqttClientType"]}
        self.topics["pir"]         = {"topic": endPoints[pirResourceIndex]["service"], "type": endPoints[pirResourceIndex]["mqttClientType"]}
        self.topics["sound"]       = {"topic": endPoints[soundResourceIndex]["service"], "type": endPoints[soundResourceIndex]["mqttClientType"]}
        self.topics["lcd"]         = {"topic": endPoints[lcdResourceIndex]["service"], "type": endPoints[lcdResourceIndex]["mqttClientType"]}
        self.topics["actuation"]   = {"topic": endPoints[actuationResourceIndex]["service"], "type": endPoints[actuationResourceIndex]["mqttClientType"]}

        # Setup the mqtt client
        self.mqttClient = PahoMQTT.Client("tiot19_Remote_Smart_Home_Controller", True)
        self.mqttClient.on_connect = self.onConnect
        self.mqttClient.on_message = self.onMessage

        try:
            self.mqttClient.connect(self.brokerURL, self.brokerPORT)

            for t in self.topics.values():
                if t["type"] == "publisher":
                    self.mqttClient.subscribe(t["topic"], qos = 2)
            
            self.mqttClient.loop_start()
        except:
            raise ConnectionError("Unable to connect to the MQTT message broker")

        self.subscribePeriod = subscribePeriod
        self.stopThreadEvent = threading.Event()
        self.running = True
        self.subscribeThread = threading.Thread(target = self.subscribeAsService)
        self.subscribePayload = json.dumps(
            {
                "serviceID": "RemoteSmartHomeController",
                "description": "A remote implementation of the Smart Home Controller featuring the Yun as the edge node. POST to /changeSetPoint to edit set points, by using the desired params - such as 'ht' and 'ac' - together with the boolean 'person'",
                "endPoints": [{"service": "/changeSetPoint", "type": "webService", "webType": "consumer"}]
            })

        # Start the subscribing thread and subscribe this class as a cherrypy plugin
        self.subscribeThread.start()
        self.subscribe()

        self.initSmartHomeControllerStuff()

    def initSmartHomeControllerStuff(self):
        # Initialize the default set points
        # self.setPoints = {
        #     "AC": [{"min": 23, "max": 25}, {"min": 25, "max": 27}], # List for not person and person respectively
        #     "HT": [{"min": 21, "max": 25}, {"min": 23, "max": 27}]
        # }
        self.setPoints = {
            "AC": [{"min": 18, "max": 23}, {"min": 23, "max": 25}], # List for not person and person respectively
            "HT": [{"min": 21, "max": 25}, {"min": 23, "max": 27}]
        }

        self.person = {"global": False, "pir": False, "sound": False}
        self.timeoutPir = 30 * 60 # 30 minutes
        self.timeOfLastPirEvent = 0

        # Use a list of timestamps for the sound events
        self.soundEvents = []
        self.numSoundEvents = 50
        self.soundInterval = 10 * 60
        self.timeoutSound = 60 * 60

        self.currentTemperature = 0

        self.actuationDict = {
            "bn": "Yun",
            "e": [{
                "n": "",
                "v": 0
            }]
        }

        self.lastMessageTimestamp = 0

        self.lastLCDDwitchTimestamp = 0
        self.currentLCDMode = -1 # This is a placeholder, available modes are 0 and 1
        self.lcdSwitchPeriod = 5
        self.lcdChangeDict = {
            "bn": "Yun",
            "e": [{
                "n": 0,
                "v": ""
            }]
        }

        self.mainLoopPeriod = 2
        self.mainLoopThread = threading.Thread(target = self.mainLoop)
        self.mainLoopThread.start()

    def mainLoop(self):
        while self.running:
            if self.lastMessageTimestamp > self.timeOfLastPirEvent + self.timeoutPir:
                self.person["pir"] = False

            # Max will raise ValueError if the iterable is empty
            try:
                if self.lastMessageTimestamp > max(self.soundEvents) + self.timeoutSound:
                    self.person["sound"] = False
            except:
                pass

            self.person["global"] = self.person["pir"] or self.person["sound"]

            # Send actuation commands according to current temperature and presence of a person
            setPoints = {"AC": self.setPoints["AC"][self.person["global"]], "HT": self.setPoints["HT"][self.person["global"]]}

            percents = {
                "AC": max(min((self.currentTemperature - setPoints["AC"]["min"]) / (setPoints["AC"]["max"] - setPoints["AC"]["min"]), 1.0), 0.0),
                "HT": max(min((self.currentTemperature - setPoints["HT"]["min"]) / (setPoints["HT"]["max"] - setPoints["HT"]["min"]), 1.0), 0.0)
            }

            self.actuationDict["e"][0]["n"] = "ac"
            self.actuationDict["e"][0]["v"] = int(percents["AC"] * 255)
            self.mqttClient.publish(self.topics["actuation"]["topic"], payload = json.dumps(self.actuationDict), qos = 2)

            self.actuationDict["e"][0]["n"] = "ht"
            self.actuationDict["e"][0]["v"] = int(percents["HT"] * 255)
            self.mqttClient.publish(self.topics["actuation"]["topic"], payload = json.dumps(self.actuationDict), qos = 2)

            # Switch lcd modes if necessary
            if self.currentLCDMode == -1 or time.time() > self.lastLCDDwitchTimestamp + self.lcdSwitchPeriod:
                self.currentLCDMode = 0 if self.currentLCDMode == -1 else not self.currentLCDMode
                self.lastLCDDwitchTimestamp = time.time()

            # Update dynamic content on the lcd
            if self.currentLCDMode == 0:
                self.lcdChangeDict["e"][0]["n"] = 0 # First line
                self.lcdChangeDict["e"][0]["v"] = "T: " + str("%3.1f" % self.currentTemperature) + ", Pres: " + str(int(self.person["global"])) + " "
                self.mqttClient.publish(self.topics["lcd"]["topic"], payload = json.dumps(self.lcdChangeDict), qos = 2)
                self.lcdChangeDict["e"][0]["n"] = 1 # First line
                self.lcdChangeDict["e"][0]["v"] = "AC:" + str("%03d" % (percents["AC"] * 100)) + "%, HT:" + str("%03d" % (percents["HT"] * 100)) + "%"
                self.mqttClient.publish(self.topics["lcd"]["topic"], payload = json.dumps(self.lcdChangeDict), qos = 2)

            else:
                self.lcdChangeDict["e"][0]["n"] = 0 # First line
                self.lcdChangeDict["e"][0]["v"] = "AC m:" + str("%3.1f" % setPoints["AC"]["min"]) + " M:" + str("%3.1f" % setPoints["AC"]["max"])
                self.mqttClient.publish(self.topics["lcd"]["topic"], payload = json.dumps(self.lcdChangeDict), qos = 2)
                self.lcdChangeDict["e"][0]["n"] = 1 # First line
                self.lcdChangeDict["e"][0]["v"] = "HT m:" + str("%3.1f" % setPoints["HT"]["min"]) + " M:" + str("%3.1f" % setPoints["HT"]["max"])
                self.mqttClient.publish(self.topics["lcd"]["topic"], payload = json.dumps(self.lcdChangeDict), qos = 2)

            # Debug
            # print("Person: " + str(self.person["global"]))
            # print("Set points: " + str(setPoints))
            # print("T: " + str(self.currentTemperature))

            self.stopThreadEvent.wait(self.mainLoopPeriod) 

    def onConnect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Successfully connected to the MQTT broker")
        else:
            print("Connection to MQTT broker failed: rc = " + str(rc))

    def onMessage(self, client, userdata, message):
        # print("Received on topic " + message.topic + ": " + message.payload.decode())

        # Deserialize the message
        try:
            msg = json.loads(message.payload)
            timestamp = msg["e"][0]["t"]
            value = msg["e"][0]["v"]
        except:
            # Ignore invalid messages
            print("Received invalid MQTT message")
            return

        self.lastMessageTimestamp = timestamp

        # Differentiate the various topics
        if message.topic == self.topics["temperature"]["topic"]:
            self.currentTemperature = value
        
        elif message.topic == self.topics["pir"]["topic"]:
            self.person["pir"] = True
            self.timeOfLastPirEvent = timestamp

        elif message.topic == self.topics["sound"]["topic"]:
            self.soundEvents.append(timestamp)

            # Remove every sound event that is too old (considering the current message's timestamp as 'now')
            self.soundEvents = list(filter(lambda t: t > timestamp - self.soundInterval, self.soundEvents))
            
            if len(self.soundEvents) > self.numSoundEvents:
                self.person["sound"] = True

    def subscribeAsService(self):
        while self.running:
            try:
                requests.put(self.catalogEndPoint + "/addService", data = self.subscribePayload)
            except:
                # Ignore any possible exceptions
                pass

            self.stopThreadEvent.wait(timeout = self.subscribePeriod)

    def stop(self):
        # Stop the subscribing thread
        self.running = False
        self.stopThreadEvent.set()
        self.subscribeThread.join()
        self.mainLoopThread.join()

        # Stop the mqtt thread
        self.mqttClient.loop_stop(force = False)

        print("Exiting...")

    def GET(self, *uri, **params):
        # Safety shutdown for debugging to not have hundreds of processes at the end of the day
        if len(uri) == 1 and uri[0] == "shutdown":
            cherrypy.engine.exit()
            return ""

        cherrypy.response.status = 404 # Not Found
        return json.dumps({"result": "failure", "reason": "Not Found"})
        
    # Sintax: /changeSetPoint?sp=ac/ht&person=true/false&min=<min>&max=<max>
    def POST(self, *uri, **params):
        if len(uri) == 1 and uri[0] == "changeSetPoint":
            if len(params) != 4 or "sp" not in params or (params["sp"] != "ac" and params["sp"] != "ht") or "person" not in params or \
                (params["person"] != "true" and params["person"] != "false") or "min" not in params or "max" not in params:

                cherrypy.response.status = 400 # Bad Request
                return json.dumps({"result":"failure", "reason": "Bad Request"})
            
            try:
                person = 1 if params["person"] == "true" else 0
                self.setPoints[params["sp"].upper()][person]["min"] = float(params["min"])
                self.setPoints[params["sp"].upper()][person]["max"] = float(params["max"])
            except:
                cherrypy.response.status = 400 # Bad Request
                return json.dumps({"result":"failure", "reason": "Bad Request"})

            return json.dumps({"result": "success"})
        
        cherrypy.response.status = 404 # Not Found
        return json.dumps({"result":"failure", "reason": "Not Found"})

if __name__ == "__main__":
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True
        }
    }

    try:
        root = RemoteSmartHomeController("http://localhost", 8080, "Yun", 60)
    except Exception as e:
        print("ERROR:" + str(e))
        exit(-1)

    cherrypy.tree.mount(root, "/", conf)
    cherrypy.config.update({"server.socket_host": "0.0.0.0"})
    cherrypy.config.update({"server.socket_port": 8083})

    cherrypy.engine.start()
    cherrypy.engine.block()
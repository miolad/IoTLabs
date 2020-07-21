import cherrypy
import paho.mqtt.client as PahoMQTT
import json
import requests
import threading
import datetime

class AlarmClockRemoteController(cherrypy.process.plugins.SimplePlugin):
    exposed = True

    def __init__(self, catalogHOST: str, catalogPORT: int, deviceID: str, subscribePeriod: float):
        cherrypy.process.plugins.SimplePlugin.__init__(self, cherrypy.engine)
        
        self.catalogEndPoint = catalogHOST + ":" + str(catalogPORT)
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

        self.brokerHOST = responseDict["url"]
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

        # Find the end points we want to publish to
        try:
            if "deviceID" not in device or device["deviceID"] != self.deviceID or "resources" not in device or "endPoints" not in device or len(device["resources"]) != len(device["endPoints"]):
                raise Exception()
            
            timeSyncResourceIndex = device["resources"].index("timeUpdate")
            alarmTriggerResourceIndex = device["resources"].index("alarmTrigger")
        except:
            raise Exception("Device descriptor invalid or incomplete")

        endPoints = device["endPoints"]

        for i in [timeSyncResourceIndex, alarmTriggerResourceIndex]:
            if "service" not in endPoints[i] or "type" not in endPoints[i] or endPoints[i]["type"] != "mqttTopic" or endPoints[i]["mqttClientType"] != "subscriber":
                raise Exception("End points not as expected")

        # All the mqtt resources will be subscribers
        self.topics = {}
        self.topics["timeSync"] = endPoints[timeSyncResourceIndex]["service"]
        self.topics["alarmTrigger"] = endPoints[alarmTriggerResourceIndex]["service"]

        # Setup the mqtt client
        self.mqttClient = PahoMQTT.Client("tiot19_Alarm_Clock_Remote_Controller", True)
        self.mqttClient.on_connect = self.onConnect
        # self.mqttClient.on_message = self.onMessage # Won't need this

        try:
            self.mqttClient.connect(self.brokerHOST, self.brokerPORT)

            # for t in self.topics.values():
            #     self.mqttClient.subscribe(t, qos = 2)
            
            self.mqttClient.loop_start()
        except:
            raise ConnectionError("Unable to connect to the MQTT message broker")

        self.subscribePeriod = subscribePeriod
        self.stopThreadEvent = threading.Event()
        self.running = True
        self.subscribeThread = threading.Thread(target = self.subscribeAsService)
        self.subscribePayload = json.dumps(
            {
                "serviceID": "AlarmClockRemoteController",
                "description": "The remote service component of a Arduino-based alarm clock with configurable alarms. POST to /addAlarm?h=<hour>&m=<minute> to add an alarm, DELETE to /removeAllAlarms to remove all the alarms set.",
                "endPoints": [{"service": "/addAlarm", "type": "webService", "webType": "consumer"},
                              {"service": "/removeAllAlarms", "type": "webService", "webType": "consumer"}]
            })

        # Start the subscribing thread and subscribe this class as a cherrypy plugin
        self.subscribeThread.start()
        self.subscribe()

        # Alerts have 1 minute resoulution
        self.alarms = [] # All the alerts set, as number of minutes since midnight, integers

        self.mainLoopPeriod = 30
        self.mainLoopThread = threading.Thread(target = self.mainLoop)
        self.mainLoopThread.start()

    def mainLoop(self):
        while self.running:
            # Get the current time of day in seconds since 00:00:00
            timeOfDaySeconds = datetime.datetime.now()
            timeOfDaySeconds = (timeOfDaySeconds - timeOfDaySeconds.replace(hour = 0, minute = 0, second = 0, microsecond = 0)).seconds

            # Send the synchronization message
            self.mqttClient.publish(topic = self.topics["timeSync"], payload = json.dumps({
                "bn": "Yun",
                "e": [{"n": "ts", "u": None, "t": datetime.datetime.now().microsecond / 1000.0, "v": timeOfDaySeconds}]
            }), qos = 2)

            # Check for alarms
            timeOfDayMinutes = int(timeOfDaySeconds / 60)
            for a in self.alarms:
                if a <= timeOfDayMinutes:
                    # Send the alarm and remove it from the list
                    # We don't use SenML here because this message only serves the purpose of notifying the edge node, it doesn't carry any other information
                    self.mqttClient.publish(topic = self.topics["alarmTrigger"], payload = 1, qos = 2)
                    self.alarms.remove(a)
            
            self.stopThreadEvent.wait(self.mainLoopPeriod) 

    def onConnect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connected to the mqtt broker")
        else:
            print("Connection to MQTT broker failed: rc = " + str(rc))

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
        
    # Sintax: /addAlarm?h=<hour>&m=<minute>
    def POST(self, *uri, **params):
        if len(uri) == 1 and uri[0] == "addAlarm":
            if len(params) != 2 or "h" not in params or "m" not in params:

                cherrypy.response.status = 400 # Bad Request
                return json.dumps({"result":"failure", "reason": "Bad Request"})
            
            try:
                h = int(params["h"])
                m = int(params["m"])
                
                if h < 0 or h >= 24 or m < 0 or m >= 60:
                    raise Exception()
            except:
                cherrypy.response.status = 400 # Bad Request
                return json.dumps({"result":"failure", "reason": "Bad Request"})

            # Add the alarm
            self.alarms.append((h * 60) + m)

            return json.dumps({"result": "success"})
        
        cherrypy.response.status = 404 # Not Found
        return json.dumps({"result":"failure", "reason": "Not Found"})

    # Sintax: /removeAllAlarms
    def DELETE(self, *uri, **params):
        if len(uri) == 1 and uri[0] == "removeAllAlarms":
            self.alarms = []

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
        root = AlarmClockRemoteController("http://localhost", 8080, "Yun", 60)
    except Exception as e:
        print("ERROR: " + str(e))
        exit(-1)

    cherrypy.tree.mount(root, "/", conf)
    cherrypy.config.update({"server.socket_host": "0.0.0.0"})
    cherrypy.config.update({"server.socket_port": 8083})

    cherrypy.engine.start()
    cherrypy.engine.block()
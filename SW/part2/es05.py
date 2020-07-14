# Main class
from EndPoint import EndPoint
from Device import Device
from User import User
from Service import Service
from typing import *

import datetime
import threading
import time
import cherrypy
import json
import paho.mqtt.client as PahoMQTT

class RESTCatalog:
    exposed = True

    # Thread subclass to manage timeouts for RESTCatalog
    # It is an inner class because it's only purpose is to work together with the Catalog
    # Also, it is a class and not just a function to pass to threading.Thread because I needed a
    # class for a cherrypy plugin anyway (to be notified of shutdown)
    class TimeoutManagerRunner(threading.Thread, cherrypy.process.plugins.SimplePlugin):
        
        # timeout is the number of seconds after the last subscription of a service or device to the Catalog such that they must be removed then
        # period specifies (in seconds, too) the period to check for every device and service
        def __init__(self, catalog, bus, timeout: float, period: float):
            threading.Thread.__init__(self)
            cherrypy.process.plugins.SimplePlugin.__init__(self, bus)
            
            self.catalog = catalog
            self.timeout = timeout
            self.period = period
            
            self.running = True

            # Used to wake the thread up when it's time to shutdown
            self.wakeEvent = threading.Event()

        def run(self):
            while self.running:
                removed = False
                
                # Check all the devices
                for device in list(self.catalog.database["devices"].values()):
                    timestamp = datetime.datetime.strptime(device.timestamp, "%Y-%m-%d %H:%M:%S.%f")

                    if datetime.datetime.now() - datetime.timedelta(seconds = self.timeout) > timestamp:
                        print("Removing device " + device.deviceID)
                        self.catalog.database["devices"].pop(device.deviceID)

                        removed = True

                # Check all the services
                for service in list(self.catalog.database["services"].values()):
                    timestamp = datetime.datetime.strptime(service.timestamp, "%Y-%m-%d %H:%M:%S.%f")

                    if datetime.datetime.now() - datetime.timedelta(seconds = self.timeout) > timestamp:
                        print("Removing service " + service.serviceID)
                        self.catalog.database["services"].pop(service.serviceID)

                        removed = True

                if removed:
                    # If something's been removed, trigger a sync with the file storage
                    self.catalog.serializeCatalogToJSONFile()

                # Wait but be ready to be woken up to shutdown
                self.wakeEvent.wait(timeout = self.period)

        # To be called when cherrypy stops to stop the thread
        def stop(self):
            # cherrypy is stopping -> terminate the thread
            self.running = False

            # Notify the waiting thread
            self.wakeEvent.set()

            # Notify the mqtt subscriber of shutdown
            try:
                self.mqttSubscriber.stop()
            except:
                pass
    
    # MQTT subscriber class to listen for device subscriptions over the mqtt protocol, too
    class MQTTDeviceSubscriptionListener:
        def __init__(self, mqttBrokerURL: str, mqttBrokerPORT: int, clientID: str, topic: str, catalog):
            self.brokerURL = mqttBrokerURL
            self.brokerPORT = mqttBrokerPORT
            self.clientID = clientID
            self.topic = topic
            self.catalog = catalog

            # Create the mqtt client instance and register the callbacks
            self._paho_mqtt = PahoMQTT.Client(self.clientID, True) # Transient session
            self._paho_mqtt.on_connect = self.onConnect
            self._paho_mqtt.on_message = self.onMessage

            # Connect to the broker and subscribe to the assigned topic
            try:
                self._paho_mqtt.connect(self.brokerURL, self.brokerPORT)
                self._paho_mqtt.loop_start()
                self._paho_mqtt.subscribe(self.topic, 2)
            except:
                print("Error connecting to mqtt broker")

        def onConnect(self, client, userdata, flags, rc):
            if rc == 0:
                print("Successfully connected to the MQTT broker")
            else:
                print("Connection to MQTT broker failed: rc = " + str(rc))

        def onMessage(self, client, userdata, message):
             # Parse and add the device
            try:
                payload = json.loads(message.payload)
            except:
                print("MQTT: Received invalid JSON")
 
            try:
                d = Device.parseDevice(payload)
            except ValueError as e:
                print("MQTT: Invalid data in JSON: " + str(e))

            # Add timestamp
            d.timestamp = str(datetime.datetime.now())
 
            # Now insert the newly created device into the database
            self.catalog.database["devices"][d.deviceID] = d

            # Save the new JSON file
            self.catalog.serializeCatalogToJSONFile()

            print("MQTT: Device added/updated successfully")

        def stop(self):
            # Stop the MQTT susbcriber
            # Unsubscribe from the topic
            self._paho_mqtt.unsubscribe(self.topic)
            self._paho_mqtt.loop_stop()
            self._paho_mqtt.disconnect()
            print("Shutting down mqtt...")

    # Used to initialize the attributes
    def __init__(self):
        # Initialize the database
        self.database = {}
        
        self.database["MQTTGlobalMessageBrokerURL"] = "test.mosquitto.org"
        self.database["MQTTGlobalMessageBrokerPort"] = 1883 # Default MQTT port

        self.database["devices"]  = {}
        self.database["users"]    = {}
        self.database["services"] = {}

        # Initialize some commonly used jsons for responses
        self.responseSuccess = { "result": "success" }
        self.responseSuccessJSON = json.dumps(self.responseSuccess)
        self.responseFailure = { "result": "failure", "reason": "" }

        self.JSONFile = "catalog.json"

        # Initialize the json file
        self.serializeCatalogToJSONFile()

        # Initialize the thread
        self.timeoutManagerRunner = RESTCatalog.TimeoutManagerRunner(self, cherrypy.engine, 120, 60)
        self.timeoutManagerRunner.subscribe() # To be notified from cherrypy
        #self.timeoutManagerRunner.start()    # cherrypy calls the start() of its plugins, which happens to be the same method to start threads

        # Initialize the MQTT subscriber client
        self.mqttDeviceSubscriber = RESTCatalog.MQTTDeviceSubscriptionListener(self.database["MQTTGlobalMessageBrokerURL"],
            self.database["MQTTGlobalMessageBrokerPort"], "tiot19CatalogSubscriber", "/tiot/19/catalog/addDevice", self)

        # Register the MQTT subscriber client to the thread to be notified of shutdown, too
        self.timeoutManagerRunner.mqttSubscriber = self.mqttDeviceSubscriber

    # Custom serializer for json.dumps(...)
    def customSerializer(self, obj):
        if isinstance(obj, (Service, User, Device)):
            return obj.serialize()

        raise TypeError("Type is not serializable")

    def serializeCatalogToJSONFile(self):
        # Open the file for switing
        try:
            jsonFile = open(self.JSONFile, "w")
        except:
            # Could not open the file -> log the error
            print("ERROR: Couldn't open the file " + self.JSONFile + " for writing")

        try:
            jsonFile.write(json.dumps(self.database, default=self.customSerializer))
        except:
            # The database is somehow invalid or the file can't be written
            pass

        jsonFile.close()

    def GET(self, *uri, **params):
        # Used to shutdown the service for debugging purposes
        if len(uri) == 1 and uri[0] == "shutdown":
            cherrypy.engine.exit()
            return ""

        # No service has a uri with length other than 1
        if len(uri) != 1:
            cherrypy.response.status = 404 # Not Found
            self.responseFailure["reason"] = "Not Found"
            return json.dumps(self.responseFailure)

        if uri[0] == "getMQTTMessageBroker":
            if len(params) != 0:
                cherrypy.response.status = 404 # Bad Request
                self.responseFailure["reason"] = "Too many parameters"
                return json.dumps(self.responseFailure)
                
            return json.dumps({"url": self.database["MQTTGlobalMessageBrokerURL"], "port": self.database["MQTTGlobalMessageBrokerPort"]})

        if uri[0] == "getUser":
            if len(params) != 1 or "id" not in params:
                cherrypy.response.status = 404 # Bad Request
                self.responseFailure["reason"] = "Wrong parameters"
                return json.dumps(self.responseFailure)
            
            userID = params.get("id")
            if userID in self.database["users"]:
                return json.dumps(self.database["users"].get(userID), default=self.customSerializer)

            # Set the HTTP status
            cherrypy.response.status = 404 # Not Found
            self.responseFailure["reason"] = "No such user"
            return json.dumps(self.responseFailure)
           
        if uri[0] == "getUsers":
            if len(params) != 0:
                cherrypy.response.status = 404 # Bad Request
                self.responseFailure["reason"] = "Too many parameters"
                return json.dumps(self.responseFailure)
            
            return json.dumps(list(self.database["users"].values()), default=self.customSerializer)
 
        if uri[0] == "getDevice" and params!={}:
            if len(params) != 1 or "id" not in params:
                cherrypy.response.status = 404 # Bad Request
                self.responseFailure["reason"] = "Wrong parameters"
                return json.dumps(self.responseFailure)
            
            deviceID = params.get("id")
            if deviceID in self.database["devices"]:
                return json.dumps(self.database["devices"].get(deviceID), default=self.customSerializer)

            # Set the HTTP status
            cherrypy.response.status = 404 # Not Found
            self.responseFailure["reason"] = "No such device"
            return json.dumps(self.responseFailure)
           
        if uri[0] == "getDevices":
            if len(params) != 0:
                cherrypy.response.status = 404 # Bad Request
                self.responseFailure["reason"] = "Too many parameters"
                return json.dumps(self.responseFailure)
            
            return json.dumps(list(self.database["devices"].values()), default=self.customSerializer)
       
        if uri[0] == "getService":
            if len(params) != 1 or "id" not in params:
                cherrypy.response.status = 404 # Bad Request
                self.responseFailure["reason"] = "Wrong parameters"
                return json.dumps(self.responseFailure)
            
            serviceID = params.get("id")
            if serviceID in self.database["services"]:
                return json.dumps(self.database["services"].get(serviceID), default=self.customSerializer)
            
            # Set the HTTP status
            cherrypy.response.status = 404 # Not Found
            self.responseFailure["reason"] = "No such service"
            return json.dumps(self.responseFailure)
           
        if uri[0] == "getServices":
            if len(params) != 0:
                cherrypy.response.status = 404 # Bad Request
                self.responseFailure["reason"] = "Too many parameters"
                return json.dumps(self.responseFailure)
            
            return json.dumps(list(self.database["services"].values()), default=self.customSerializer)

        cherrypy.response.status = 404 # Not Found
        self.responseFailure["reason"] = "Not Found"
        return json.dumps(self.responseFailure)
    
    def PUT(self, *uri, **params):
        # Add Service
        if len(uri) == 1 and uri[0] == "addService":
            body = cherrypy.request.body.read()
            try:
                body = json.loads(body)
            except:
                cherrypy.response.status = 400 # Bad Request
                self.responseFailure["reason"] = "Invalid JSON"
                return json.dumps(self.responseFailure)

            # Parse the service
            try:
                s = Service.parseService(body)
            except ValueError as e:
                # There was an error parsing the service's json
                cherrypy.response.status = 400 # Bad Request
                self.responseFailure["reason"] = str(e)
                return json.dumps(self.responseFailure)

            # Add the timestamp
            s.timestamp = str(datetime.datetime.now())

            # Now insert the newly created service into the database
            self.database["services"][s.serviceID] = s

            # Save the new JSON file
            self.serializeCatalogToJSONFile()

            return self.responseSuccessJSON

        # Add User
        if len(uri) == 1 and uri[0] == "addUser":
            body = cherrypy.request.body.read()
            try:
                body = json.loads(body)
            except:
                cherrypy.response.status = 400 # Bad Request
                self.responseFailure["reason"] = "Invalid JSON"
                return json.dumps(self.responseFailure)

            try:
                u = User.parseUser(body)
            except ValueError as e:
                cherrypy.response.status = 400 # Bad Request
                self.responseFailure["reason"] = str(e)
                return json.dumps(self.responseFailure)

            # Insert the user into the global database
            self.database["users"][u.userID] = u

            # Save the new JSON file
            self.serializeCatalogToJSONFile()

            return self.responseSuccessJSON

        # Add Device
        if len(uri) == 1 and uri[0] == "addDevice":
            body = cherrypy.request.body.read()
            try:
                body = json.loads(body)
            except:
                cherrypy.response.status = 400 # Bad Request
                self.responseFailure["reason"] = "Bad Request: Invalid JSON"
                return json.dumps(self.responseFailure)
 
            try:
                d = Device.parseDevice(body)
            except ValueError as e:
                cherrypy.response.status = 400 # Bad Request
                self.responseFailure["reason"] = str(e)
                return json.dumps(self.responseFailure)

            # Add timestamp
            d.timestamp = str(datetime.datetime.now())
 
            # Now insert the newly created device into the database
            self.database["devices"][d.deviceID] = d

            # Save the new JSON file
            self.serializeCatalogToJSONFile()
 
            return self.responseSuccessJSON
                
        # The requested service does not exist
        cherrypy.response.status = 404 # Not Found
        self.responseFailure["reason"] = "Not Found"
        return json.dumps(self.responseFailure)

if __name__ == "__main__":
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True
        }
    }

    cherrypy.tree.mount(RESTCatalog(), "/", conf)
    cherrypy.config.update({"server.socket_host": "0.0.0.0"})

    cherrypy.engine.start()
    cherrypy.engine.block()
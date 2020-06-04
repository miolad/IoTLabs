# Main class
from EndPoint import EndPoint
from Device import Device
from User import User
from Service import Service

import datetime
import threading
import time

import cherrypy
import json

# Thread class to manage timeouts for RESTCatalog
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

            time.sleep(self.period)

    # To be called when cherrypy stops to stop the thread
    def stop(self):
        # cherrypy is stopping -> terminate the thread
        self.running = False

class RESTCatalog():
    exposed = True

    # Used to initialize the attributes
    def __init__(self):
        # Initialize the database
        self.database = {}
        
        self.database["MQTTGlobalMessageBrokerURL"] = "test.mosquitto.org"
        self.database["MQTTGlobalMessageBrokerPort"] = 1883 # Default MQTT port

        self.database["devices"]  = {}
        self.database["users"]    = {}
        self.database["services"] = {}

        self.JSONFile = "catalog.json"

        # Initialize the json file
        self.serializeCatalogToJSONFile()

        # Initialize the thread
        self.timeoutManagerRunner = TimeoutManagerRunner(self, cherrypy.engine, 120, 60)
        self.timeoutManagerRunner.subscribe() # To be notified from cherrypy
        #self.timeoutManagerRunner.start()    # cherrypy calls the start() of its plugins, which happens to be the same method to start threads

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
            # The database is somehow invalid
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
            return "Not Found"

        if uri[0] == "getMQTTMessageBroker":
            if len(params) != 0:
                cherrypy.response.status = 404 # Bad Request
                return "Too many parameters"
                
            return json.dumps({"url": self.database["MQTTGlobalMessageBrokerURL"], "port": self.database["MQTTGlobalMessageBrokerPort"]})

        if uri[0] == "getUser":
            if len(params) != 1 or "id" not in params:
                cherrypy.response.status = 404 # Bad Request
                return "Wrong parameters. Usage: getUser?id=<userID>"
            
            userID = params.get("id")
            if userID in self.database["users"]:
                return json.dumps(self.database["users"].get(userID), default=self.customSerializer)

            # Set the HTTP status
            cherrypy.response.status = 404 # Not Found
            return "No such user"
           
        if uri[0] == "getUsers":
            if len(params) != 0:
                cherrypy.response.status = 404 # Bad Request
                return "Too many parameters"
            
            return json.dumps(list(self.database["users"].values()), default=self.customSerializer)
 
        if uri[0] == "getDevice" and params!={}:
            if len(params) != 1 or "id" not in params:
                cherrypy.response.status = 404 # Bad Request
                return "Wrong parameters. Usage: getDevice?id=<deviceID>"
            
            deviceID = params.get("id")
            if deviceID in self.database["devices"]:
                return json.dumps(self.database["devices"].get(deviceID), default=self.customSerializer)

            # Set the HTTP status
            cherrypy.response.status = 404 # Not Found
            return "No such device"
           
        if uri[0] == "getDevices":
            if len(params) != 0:
                cherrypy.response.status = 404 # Bad Request
                return "Too many parameters"
            
            return json.dumps(list(self.database["devices"].values()), default=self.customSerializer)
       
        if uri[0] == "getService":
            if len(params) != 1 or id not in params:
                cherrypy.response.status = 404 # Bad Request
                return "Wrong parameters. Usage: getService?id=<serviceID>"
            
            serviceID = params.get("id")
            if serviceID in self.database["services"]:
                return json.dumps(self.database["services"].get(serviceID), default=self.customSerializer)
            
            # Set the HTTP status
            cherrypy.response.status = 404 # Not Found
            return "No such service"
           
        if uri[0] == "getServices":
            if len(params) != 0:
                cherrypy.response.status = 404 # Bad Request
                return "Too many parameters"
            
            return json.dumps(list(self.database["services"].values()), default=self.customSerializer)

        cherrypy.response.status = 404 # Not Found
        return "Not Found"
    
    def PUT(self, *uri, **params):
        # Add Service
        if len(uri) == 1 and uri[0] == "addService":
            body = cherrypy.request.body.read()
            try:
                body = json.loads(body)
            except:
                cherrypy.response.status = 400 # Bad Request
                return "Bad Request: invalid JSON"

            # Check if the json contains everything we need
            if "serviceID" not in body or "description" not in body or "endPoints" not in body:
                cherrypy.response.status = 400 # Bad Request
                return "Bad Request"

            s = Service(body["serviceID"])
            s.description = body["description"]

            # Get the end points
            for endPointDict in body["endPoints"]:
                try:
                    s.addEndPoint(EndPoint.parseEndPoint(endPointDict))
                except:
                    # Invalid endpoint
                    cherrypy.response.status = 400 # Bad Request
                    return "Bad Request: invalid end points!"

            # Add the timestamp
            s.timestamp = str(datetime.datetime.now())

            # Now insert the newly created service into the database
            self.database["services"][s.serviceID] = s

            # Save the new JSON file
            self.serializeCatalogToJSONFile()

            return "INSERT SERVICE SUCCESS"

        # Add User
        if len(uri) == 1 and uri[0] == "addUser":
            body = cherrypy.request.body.read()
            try:
                body = json.loads(body)
            except:
                cherrypy.response.status = 400 # Bad Request
                return "Bad Request: invalid JSON"

            if "userID" not in body or "name" not in body or "surname" not in body or "email" not in body:
                cherrypy.response.status = 400 # Bad Request

            u = User(body["userID"], body["name"], body["surname"], body["email"])

            # Insert the user into the global database
            self.database["users"][u.userID] = u

            # Save the new JSON file
            self.serializeCatalogToJSONFile()

            return "INSERT USER SUCCESS"

        # Add Device
        if len(uri) == 1 and uri[0] == "addDevice":
            body = cherrypy.request.body.read()
            try:
                body = json.loads(body)
            except:
                cherrypy.response.status = 400 # Bad Request
                return "Bad Request: invalid JSON"
 
            # Check if the json contains everything we need
            if "deviceID" not in body or "endPoints" not in body or "availableResources" not in body:
                cherrypy.response.status = 400 # Bad Request
                return "Bad Request"
 
            d = Device(body["deviceID"], body["availableResources"])
 
            # Get the end points
            for endPointDict in body["endPoints"]:
                try:
                    d.addEndPoint(EndPoint.parseEndPoint(endPointDict))
                except:
                    # Invalid endpoint
                    cherrypy.response.status = 400 # Bad Request
                    return "Bad Request: invalid end points!"

            # Add timestamp
            d.timestamp = str(datetime.datetime.now())
 
            # Now insert the newly created service into the database
            self.database["devices"][d.deviceID] = d

            # Save the new JSON file
            self.serializeCatalogToJSONFile()
 
            return "INSERT DEVICE SUCCESS"
                
        # The requested service does not exist
        cherrypy.response.status = 404 # Not Found
        return "Not Found"

    # def POST(self, *uri, **params):
    #     # The POST method is only used for setting the global message broker url and port
    #     # The information is expected to be passed via a JSON formatted string in the body of the request
    #     body = cherrypy.request.body.read()

    #     try:
    #         body = json.loads(body)
    #     except:
    #         # Set the correct HTTP status
    #         cherrypy.response.status = 400 # Bad Request
    #         return "Bad Request: invalid JSON"

    #     if "brokerURL" not in body or "brokerPORT" not in body:
    #         cherrypy.response.status = 400 # Bad Request
    #         return "Bad Request"

    #     # Finally, set the new url and port
    #     self.database["MQTTGlobalMessageBrokerURL"] = body["brokerURL"]
    #     self.database["MQTTGlobalMessageBrokerPort"] = body["brokerPORT"]

    #     return "POST SUCCESS"

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
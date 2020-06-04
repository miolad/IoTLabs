# Main class
from EndPoint import EndPoint
from Device import Device
from User import User
from Service import Service

import datetime

import cherrypy
import json

class RESTCatalog():
    exposed = True

    # Used to initialize the attributes
    def __init__(self):
        # Initialize the database
        self.database = {}
        
        self.database["MQTTGlobalMessageBrokerURL"] = ""
        self.database["MQTTGlobalMessageBrokerPort"] = 1883 # Default MQTT port

        self.database["devices"]  = {}
        self.database["users"]    = {}
        self.database["services"] = {}

    def GET(self, *uri, **params):
        if len(uri) == 1 and uri[0] == "shutdown":
            cherrypy.engine.exit()
            return ""

        if(uri[0] == "getUser" and params!={}):
            userID = params.get("id")
            if userID in self.database["users"]:
                return json.dumps(self.database["users"].get(userID))

            # Set the HTTP status
            cherrypy.response.status = 404 # Not Found
            return "No such user"
           
        if uri[0] == "getUsers":
            return json.dumps(list(self.database["users"]))
 
        if(uri[0] == "getDevice" and params!={}):
            deviceID = params.get("id")
            if deviceID in self.database["devices"]:
                return json.dumps(self.database["devices"].get(deviceID))

            # Set the HTTP status
            cherrypy.response.status = 404 # Not Found
            return "No such device"
           
        if(uri[0] == "getDevices" and params!={}):
            return json.dumps(list(self.database["devices"]))
       
        if(uri[0] == "getService" and params!={}):
            serviceID = params.get("id")
            if serviceID in self.database["services"]:
                return json.dumps(self.database["services"].get(serviceID))
            
            # Set the HTTP status
            cherrypy.response.status = 404 # Not Found
            return "No such service"
           
        if uri[0] == "getServices":
            return json.dumps(list(self.database["services"].values()))

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
                    s.addEndPoint(endPointDict)
                except:
                    # Invalid endpoint
                    cherrypy.response.status = 400 # Bad Request
                    return "Bad Request: invalid end points!"

            # Now insert the newly created service into the database
            self.database["services"][s.uniqueID] = s.serializeService()

            return "INSERT SERVICE SUCCESS"
                
        # The requested service does not exist
        cherrypy.response.status = 404 # Not Found
        return "Not Found"

    def POST(self, *uri, **params):
        # The POST method is only used for setting the global message broker url and port
        # The information is expected to be passed via a JSON formatted string in the body of the request
        body = cherrypy.request.body.read()

        try:
            body = json.loads(body)
        except:
            # Set the correct HTTP status
            cherrypy.response.status = 400 # Bad Request
            return "Bad Request: invalid JSON"

        if "brokerURL" not in body or "brokerPORT" not in body:
            cherrypy.response.status = 400 # Bad Request
            return "Bad Request"

        # Finally, set the new url and port
        self.MQTTGlobalMessageBrokerURL = body["brokerURL"]
        self.MQTTGlobalMessageBrokerPort = body["brokerPORT"]

        return "POST SUCCESS"

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
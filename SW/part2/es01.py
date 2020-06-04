# Main class
import EndPoint

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
            if "serviceID" not in body or "description" not in body or "endPoint" not in body:
                cherrypy.response.status = 400 # Bad Request
                return "Bad Request"

            EndPoint.EndPoint.parseEndPoint(3)
                
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
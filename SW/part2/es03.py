#es3
import cherrypy
import json
import requests
import threading

class IoTDevice():
    exposed = True

    # Inner Thread class for continuous subscription with the Device Catalog
    class SubscriberRunner(threading.Thread, cherrypy.process.plugins.SimplePlugin):

        # Payload is the json-formatted string to send the catalog every 'period' seconds
        def __init__(self, bus, period: float, payload: str, catalogURL: str):
            threading.Thread.__init__(self)
            cherrypy.process.plugins.SimplePlugin.__init__(self, bus)
            self.period = period
            self.payload = payload
            self.catalogURL = catalogURL
            
            self.running = True
            self.wakeEvent = threading.Event()

        def run(self):
            while self.running:
                # Perform the subscription
                print("Registering to the catalog...")
                try:
                    response = requests.put(self.catalogURL, data = self.payload)
                    response.raise_for_status()
                except:
                    print("An error occurred while performing the request to the device catalog.")
                else:
                    print("Registration successful, got " + response.text)

                self.wakeEvent.wait(self.period)

        def stop(self):
            # We have been notified from cherrypy that the server is shutting down
            # Stop the thread
            self.running = False
            self.wakeEvent.set()
    
    def __init__(self):
        # Register the cherrypy plugin (which is also the thread that must register this service to the catalog)
        self.payload = json.dumps(
            {
	            "deviceID": "pir",
	            "endPoints": [
                    {"service": "localhost:8080/thereIsPerson", "type": "webService", "webType": "producer"},
                    {"service": "localhost:8080/nonloso", "type":"webService", "webType": "consumer"}
		        ],
		        "resources": ["person", "nonloso"]
            }
        )
        print(self.payload)
        #change the port
        self.catalogSubscriber = IoTDevice.SubscriberRunner(cherrypy.engine, 60, self.payload, "http://localhost:8080/addDevice")
        self.catalogSubscriber.subscribe() # This also starts the thread

 
    def GET(self, *uri, **params):
        # Shutdown on "shutdown". Used for debugging purposes
        if len(uri) == 1 and uri[0] == "shutdown":
            cherrypy.engine.exit()
            return ""
    
        cherrypy.response.status = 404 # Not Found
        return "Command not supported!"

if __name__ == "__main__":
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True
        }
    }

    cherrypy.tree.mount(IoTDevice(), "/", conf)
    cherrypy.config.update({"server.socket_host": "0.0.0.0"})
    cherrypy.config.update({'server.socket_port': 8082}) # Change the port to run it simultaneously with the catalog on the same machine

    cherrypy.engine.start()
    cherrypy.engine.block()
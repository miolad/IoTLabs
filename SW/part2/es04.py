import cherrypy
import json
import conversions
import requests
import threading

class RESTWebService():
    exposed = True

    # Inner Thread class for continuous subscription with the Service Catalog
    class ServiceCatalogSubscriberRunner(threading.Thread, cherrypy.process.plugins.SimplePlugin):

        # subscriptionPayload is the json-formatted string to send the catalog every 'period' seconds
        def __init__(self, bus, period: float, subscriptionPayload: str, catalogURL: str):
            threading.Thread.__init__(self)
            cherrypy.process.plugins.SimplePlugin.__init__(self, bus)

            self.period = period
            self.subscriptionPayload = subscriptionPayload
            self.catalogURL = catalogURL
            
            self.running = True
            self.wakeEvent = threading.Event()

        def run(self):
            while self.running:
                # Perform the subscription
                print("Registering to the catalog...")
                
                try:
                    response = requests.put(self.catalogURL, data = self.subscriptionPayload)
                    response.raise_for_status()
                except:
                    print("An error occurred while performing the request to the service catalog.")
                else:
                    print("Registration successful, got " + response.text)

                self.wakeEvent.wait(self.period)

        def stop(self):
            # We have been notified from cherrypy that the server is shutting down
            # Stop the thread
            self.running = False
            self.wakeEvent.set()
    
    validUnits = ["C", "K", "F"]
    listValue = []

    def __init__(self):
        # Register the cherrypy plugin (which is also the thread that must register this service to the catalog)
        self.registerPayload = json.dumps(
            {
                "serviceID": "temperatureServiceV1",
                "description": "A temperature converter between C, F and K. Pass the temperatures as HTTP GET parameters: /converter?value=<original_value>&originalUnit=<original_unit>&targetUnit=<target_unit>. \
                    Additionally, get the current log of temperatures recorder by the edge sensor via HTTP GET at /log, or add to the log via HTTP POST at /log",
                "endPoints": [{"service": "http://localhost:8081/converter", "type": "webService"},
                {"service": "http://localhost:8081/log", "type": "webService"}]
            }
        )
        self.catalogURL = "http://localhost"
        self.catalogPORT = 8080
        self.catalogSubscriber = RESTWebService.ServiceCatalogSubscriberRunner(cherrypy.engine, 60, self.registerPayload,
            self.catalogURL + ":" + str(self.catalogPORT) + "/addService")
        self.catalogSubscriber.subscribe() # This also starts the thread

    def buildJSON(self, originalValue: float, originalUnit: str, targetValue: float, targetUnit: str) -> str:
        retJSON = {"originalValue": originalValue, "originalUnit": originalUnit, "targetValue": targetValue, "targetUnit": targetUnit}
        return json.dumps(retJSON)

    def GET(self, *uri, **params):
        if len(uri) != 1:
            # Whathever the uri was, it's not valid
            # Set the appropriate HTTP status
            cherrypy.response.status = 404 # Not Found
            return "Command not supported!"

        # Shutdown on "shutdown". Used for debugging purposes
        if uri[0] == "shutdown":
            cherrypy.engine.exit()
            return ""

        if uri[0] == "converter":
            # Check if the parameters are valid
            if len(params) != 3 or "value" not in params or "originalUnit" not in params or "targetUnit" not in params:
                cherrypy.response.status = 400 # Bad Request
                return "Wrong parameters!<br>Usage: converter?value=&lt;val&gt;&originalUnit=&lt;orig&gt;&targetUnit=&lt;trgt&gt;."

            originalUnit = params["originalUnit"].upper()
            targetUnit = params["targetUnit"].upper()

            # Check if the units are valid
            if originalUnit not in self.validUnits or targetUnit not in self.validUnits:
                cherrypy.response.status = 400 # Bad Request
                return "Invalid temperature unit!<br>Valid units are:<ul><li>C - Celsius</li><li>K - Kelvin</li><li>F - Fahrenheit</li></ul>"

            try:
                originalValue = float(params["value"])
            except:
                # The numerical value is invalid!
                cherrypy.response.status = 400 # Bad Request
                return "Invalid temperature value!"

            # Perform the conversion
            try:
                targetValue = conversions.convert(originalValue, originalUnit, targetUnit)
            except ValueError as e:
                cherrypy.response.status = 400 # Bad Request
                return str(e)

            return self.buildJSON(originalValue, originalUnit, targetValue, targetUnit)
        
        if uri[0] == "log":
            # Log all the temperature data received so far
            return json.dumps(self.listValue) # Use json.dumps to print the list instead of just converting
                                              # it into a string to print with the double quotes to be compliant with JSON

        # The command is not valid
        cherrypy.response.status = 404 # Not Found
        return "Command not supported!"
    
    def POST(self, *uri, **params):
        # Check if the uri is valid
        if len(uri) == 1 and uri[0] == "log":
            body = cherrypy.request.body.read()
            val = json.loads(body)

            # Check if the received JSON is correct
            if ("bn" not in val or val["bn"] != "Yun" or "e" not in val
                    or "n" not in val["e"][0] or val ["e"][0]["n"] != "temperature"
                    or "t" not in val["e"][0] or "v" not in val["e"][0] or "u" not in val["e"][0]):
                # The body is not what we expected -> reject it
                cherrypy.response.status = 400 # Bad Request
                return

            self.listValue.append(val)

if __name__ == "__main__":
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True
        }
    }

    cherrypy.tree.mount(RESTWebService(), "/", conf)
    cherrypy.config.update({"server.socket_host": "0.0.0.0"})
    cherrypy.config.update({'server.socket_port': 8081}) # Change the port to run it simultaneously with the catalog on the same machine

    cherrypy.engine.start()
    cherrypy.engine.block()
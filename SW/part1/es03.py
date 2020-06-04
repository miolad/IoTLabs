import cherrypy
import json
import conversions

class RESTWebService():
    exposed = True
    validUnits = ["C", "K", "F"]

    def GET(self, *uri, **params):
        # Shutdown on "shutdown". Used for debugging purposes
        if len(uri) == 1 and uri[0] == "shutdown":
            cherrypy.engine.exit()
        
        return ""

    def PUT(self, *uri, **params):
        # Check id the command is supported
        if len(uri) != 1 or uri[0] != "converter":
            return "Please choose a valid command!<br>Only 'converter' is implemented for now."

        # Get the body
        body = cherrypy.request.body.read().decode()

        #data = {}
        # Convert it to a python dict
        try:
            data = json.loads(body)
        except:
            return "Invalid body!<br>The provided body is not a valid JSON."

        # Check if the data is valid
        if len(data) != 3 or "values" not in data or "originalUnit" not in data or "targetUnit" not in data:
            return "Invalid body!"

        originalUnit = data["originalUnit"].upper()
        targetUnit = data["targetUnit"].upper()

        # Check if the units are valid
        if originalUnit not in self.validUnits or targetUnit not in self.validUnits:
            return "Invalid temperature units!"

        # Check if the values are numerical
        originalValues = data["values"]

        try:
            for v in originalValues:
                int(v)
        except:
            return "Invalid temperature values!"

        # Perform the conversion
        targetValues = conversions.convertMultiple(originalValues, originalUnit, targetUnit)

        # Create a new dict to have the desired order of the key-value pairs
        dataUpdated = {"values": data["values"], "originalUnit": originalUnit, "targetValues": targetValues, "targetUnit": targetUnit}

        return json.dumps(dataUpdated)

if __name__ == "__main__":
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True
        }
    }

    cherrypy.tree.mount(RESTWebService(), "/", conf)

    cherrypy.config.update({"server.socket_host": "0.0.0.0"})

    cherrypy.engine.start()
    cherrypy.engine.block()
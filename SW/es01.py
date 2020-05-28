import cherrypy
import json
import conversions

class RESTWebService():
    exposed = True
    validUnits = ["C", "K", "F"]

    def buildJSON(self, originalValue: float, originalUnit: str, targetValue: float, targetUnit: str) -> str:
        retJSON = {"originalValue": originalValue, "originalUnit": originalUnit, "targetValue": targetValue, "targetUnit": targetUnit}
        return json.dumps(retJSON)

    def GET(self, *uri, **params):
        # Shutdown on "shutdown". Used for debugging purposes
        if len(uri) == 1 and uri[0] == "shutdown":
            cherrypy.engine.exit()
            return ""

        # Check if the 'command' is valid
        if len(uri) != 1 or uri[0] != "converter":
            return "Please choose a valid command!<br>Only 'converter' is implemented for now."

        # Check if the parameters are valid
        if len(params) != 3 or "value" not in params or "originalUnit" not in params or "targetUnit" not in params:
            return "Wrong parameters!<br>Usage: converter?value=&lt;val&gt;&originalUnit=&lt;orig&gt;&targetUnit=&lt;trgt&gt;."

        originalUnit = params["originalUnit"].upper()
        targetUnit = params["targetUnit"].upper()

        # Check if the units are valid
        if originalUnit not in self.validUnits or targetUnit not in self.validUnits:
            return "Invalid temperature unit!<br>Valid units are:<ul><li>C - Celsius</li><li>K - Kelvin</li><li>F - Fahrenheit</li></ul>"

        try:
            originalValue = float(params["value"])
        except:
            # The numerical value is invalid!
            return "Invalid temperature value!"

        # Perform the conversion
        targetValue = conversions.convert(originalValue, originalUnit, targetUnit)

        return self.buildJSON(originalValue, originalUnit, targetValue, targetUnit)

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
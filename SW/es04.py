import cherrypy
import json
import os, os.path
from pathlib import Path

class FreeboardWebServer():
    exposed = True

    def GET(self, *uri, **params):
        if len(uri) == 1 and uri[0] == "shutdown":
            cherrypy.engine.exit()
        
        return ""

    def POST(self, *uri, **params):
        # It appears that the new dashboard json file is passed via the parameters to the POST request
        # Check if they are valid
        if "json_string" not in params:
            return "Invalid parameters."

        # Write the json to the 'freeboard/dashboard/dashboard.json' file
        try:
            dashboard = open(os.getcwd() + "/freeboard/dashboard/dashboard.json", "w")
        except:
            # Couldn't open the file
            return "ERROR: Couldn't open the file 'freeboard/dashboard/dashboard.json'"

        dashboard.write(params["json_string"])

        dashboard.close()

if __name__ == "__main__":
    conf = {
        "/": {
            "request.dispatch": cherrypy.dispatch.MethodDispatcher(),
            "tools.sessions.on": True,
            "tools.staticdir.root": os.path.abspath(os.getcwd()),
            "tools.staticdir.on": True,
            "tools.staticdir.dir": "./freeboard",
            "tools.staticdir.index": "./index.html"
        }
    }

    cherrypy.tree.mount(FreeboardWebServer(), "/", conf)

    cherrypy.config.update({"server.socket_host": "0.0.0.0"})

    cherrypy.engine.start()
    cherrypy.engine.block()
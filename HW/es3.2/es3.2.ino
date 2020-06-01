#include <ArduinoJson.h>
#include <Process.h>

// -------------- CONSTANTS --------------
#define TEMPERATURE_SENSOR_PIN  A0
#define RED_LED_PIN             6 // Red led

#define B 4275                                      // K
#define ANALOG_REFERENCE 1023.f                     // V
#define ONE_OVER_T0 1.f / (25.0 + 273.15)           // K
#define CELSIUS_OFFSET 273.15                       // K

#define MAIN_PERIOD_LENGTH 2500                           // ms

// -------------- VARIABLES --------------

int analogValue;
float RoverR0, T;

unsigned long previousIteration = 0;
bool forceLoop = true;

const int jsonCapacity = JSON_OBJECT_SIZE(2) + JSON_ARRAY_SIZE(1) + JSON_OBJECT_SIZE(4) + 40;
DynamicJsonDocument jsonDocument(jsonCapacity);

// Encodes the desired values as a SenML-compliant JSON String
String encodeSenML(String resource, float value, String unit)
{
    // Clear the global document
    jsonDocument.clear();

    // Build the JSON
    jsonDocument["bn"] = "Yun";

    jsonDocument["e"][0]["n"] = resource;
    jsonDocument["e"][0]["t"] = (double)millis() / 1000;
    jsonDocument["e"][0]["v"] = value;

    if (!unit.equals(""))
        jsonDocument["e"][0]["u"] = unit;
    else
        jsonDocument["e"][0]["u"] = (char*)NULL;

    String output;
    serializeJson(jsonDocument, output);
    return output;
}

// Sends the post request with the specified data to the
// preconfigured web-server.
// Returns the exit code of the 'curl' Linux command.
int sendPOSTRequest(String data)
{
    Process p;

    // Use the 'curl' command
    p.begin("curl");
    p.addParameter("-H");
    p.addParameter("Content-type: application/json");
    p.addParameter("-X");
    p.addParameter("POST");
    p.addParameter("-d");
    p.addParameter(data);
    p.addParameter(F("http://192.168.1.37:8080/log"));

    // Run the command
    p.run();

    return p.exitValue();
}

void setup()
{
    // Initialize pin modes
    pinMode(LED_BUILTIN, OUTPUT);

    // Initialize the Yùn bridge
    digitalWrite(LED_BUILTIN, LOW);
    Bridge.begin();
    digitalWrite(LED_BUILTIN, HIGH);

    // Initialize serial connection
    Serial.begin(9600);
}

void loop()
{
    unsigned long now = millis();

    if (now >= previousIteration + MAIN_PERIOD_LENGTH || forceLoop)
    {
        previousIteration = now;
        forceLoop = false;

        // Read temperature data from the sensor
        analogValue = analogRead(TEMPERATURE_SENSOR_PIN);
        RoverR0 = ANALOG_REFERENCE / analogValue - 1;
        T = 1.f / ((log(RoverR0) / B) + ONE_OVER_T0) - CELSIUS_OFFSET;

        // Send the HTTP POST request
        int retval = sendPOSTRequest(encodeSenML("temperature", T, "Cel"));
        
        if (retval)
        {
            Serial.print("curl error: ");
            Serial.println(retval);
        }
    }
}
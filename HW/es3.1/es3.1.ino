#include <Bridge.h>
#include <BridgeServer.h>
#include <BridgeClient.h>
#include <ArduinoJson.h>

// -------------- CONSTANTS --------------
#define TEMPERATURE_SENSOR_PIN  A0
#define RED_LED_PIN             6 // Red led

#define B 4275                                      // K
#define ANALOG_REFERENCE 1023.f                     // V
#define ONE_OVER_T0 1.f / (25.0 + 273.15)           // K
#define CELSIUS_OFFSET 273.15                       // K

// -------------- VARIABLES --------------

int analogValue;
float RoverR0, T;

bool redLedStatus = 0;

BridgeServer server;

const int jsonCapacity = JSON_OBJECT_SIZE(2) + JSON_ARRAY_SIZE(1) + JSON_OBJECT_SIZE(4) + 40;
DynamicJsonDocument jsonDocument(jsonCapacity);

void printResponse(BridgeClient client, int httpCode, String body)
{
    // Set the desired HTTP response code
    client.println("Status: " + String(httpCode));

    // On success, print the body, too
    if (httpCode == 200)
    {
        // Set the document type
        client.println(F("Content-type: application/json; charset=utf-8"));
        client.println();
        client.println(body);
    }
}

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

void processConnection(BridgeClient client)
{
    String cmd = client.readStringUntil('/');
    cmd.trim();

    // Parse the command
    if (cmd.equals("led"))
    {
        // Read the numeric value
        int val = client.parseInt();

        if (val == 0 || val == 1)
        {
            // Set the LED accordingly
            digitalWrite(RED_LED_PIN, val);

            printResponse(client, 200, encodeSenML("led", val, ""));
        }
        else
        {
            // Bad request
            printResponse(client, 400, "");
        }
    }
    else if (cmd.equals("temperature"))
    {
        printResponse(client, 200, encodeSenML("temperature", T, "Cel"));
    }
    else
    {
        // Invalid request
        printResponse(client, 404, "");
    }
}

void setup()
{
    // Initialize pin modes
    pinMode(LED_BUILTIN, OUTPUT);
    pinMode(RED_LED_PIN, OUTPUT);

    // Initialize the red led as OFF, initially
    digitalWrite(RED_LED_PIN, redLedStatus);

    // Initialize the Yùn bridge
    digitalWrite(LED_BUILTIN, LOW);
    Bridge.begin();
    digitalWrite(LED_BUILTIN, HIGH);

    server.listenOnLocalhost();
    server.begin();

    // Initialize serial connection
    Serial.begin(9600);
}

void loop()
{
    // Read the temperature
    analogValue = analogRead(TEMPERATURE_SENSOR_PIN);
    RoverR0 = ANALOG_REFERENCE / analogValue - 1;
    T = 1.f / ((log(RoverR0) / B) + ONE_OVER_T0) - CELSIUS_OFFSET;
    
    BridgeClient client = server.accept();

    if (client)
    {
        // Handle the request
        processConnection(client);
        client.stop();
    }

    delay(50);
}

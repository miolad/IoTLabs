#include <ArduinoJson.h>
#include <Bridge.h>
#include <MQTTclient.h>

// -------------- CONSTANTS --------------
#define TEMPERATURE_SENSOR_PIN  A0
#define RED_LED_PIN             6 // Red led

#define B 4275                                      // K
#define ANALOG_REFERENCE 1023.f                     // V
#define ONE_OVER_T0 1.f / (25.0 + 273.15)           // K
#define CELSIUS_OFFSET 273.15                       // K

// Period for polling for new messages
#define MAIN_PERIOD_LENGTH 500                      // ms

// Period for publishing new temperature readings
#define PUBLISH_PERIOD_LENGTH 10000                 // ms

#define SUBSCRIBE_TO_CATALOG_PERIOD_LENGTH 60000    // ms

#define DEVICE_SUBSCRIPTION_JSON_STRING     F("{\"deviceID\": \"Yun\", \"resources\": [\"temperature\", \"led\"], \"endPoints\": [{\"service\": \"/tiot/19/temperature\", \"type\": \"mqttTopic\", \"mqttClientType\": \"publisher\"}, {\"service\": \"/tiot/19/led\", \"type\": \"mqttTopic\", \"mqttClientType\": \"subscriber\"}]}")

const char BASE_TOPIC[] = "/tiot/19/";

// -------------- VARIABLES --------------

int analogValue;
float RoverR0, T;

unsigned long previousIteration = 0, previousPublishTime = 0, previousSubscribeTime = 0;
bool forceLoop = true, forceSubscription = true;

// Trying to use the least memory as possible, otherwise bad things will happen
const int jsonCapacity = 100;
char* jsonResult; // Used to store the result of the serialization

void mqttLedSubscribeCallback(const String& topic, const String& subtopic, const String& message)
{
    /*Serial.print(F("Received message on "));
    Serial.print(topic);
    Serial.print("/");Serial.print(subtopic);Serial.print(": ");
    Serial.println(message);*/

    // Deserialize the received Json
    DynamicJsonDocument jsonDocument(jsonCapacity);
    DeserializationError err = deserializeJson(jsonDocument, message);

    if (err)
    {
        Serial.print(F("Failed to deserialize json: "));
        Serial.print(message);
        Serial.print("; ");
        Serial.println(err.c_str());
        return;
    }

    // Check for completeness
    if (jsonDocument["bn"] != "Yun")
    {
        Serial.println(F("Invalid JSON received: not for this device"));
        return;
    }

    if (jsonDocument["e"][0]["n"] != "led")
    {
        Serial.println(F("Invalid JSON received: unknown function"));
        return;
    }

    // Now read the desired led state and validate it
    byte ledState = jsonDocument["e"][0]["v"];
    
    if (ledState > 1)
    {
        Serial.println(F("Invalid JSON received: led value should be either 1 or 0"));
        return;
    }

    // Set the led state
    digitalWrite(RED_LED_PIN, ledState);
}

// Encodes the desired values as a SenML-compliant JSON String
void encodeSenML(String resource, float value, String unit)
{
    DynamicJsonDocument jsonDocument(jsonCapacity);

    // Build the JSON
    jsonDocument["bn"] = "Yun";

    jsonDocument["e"][0]["n"] = resource;
    jsonDocument["e"][0]["t"] = (double)millis() / 1000;
    jsonDocument["e"][0]["v"] = value;

    if (!unit.equals(""))
        jsonDocument["e"][0]["u"] = unit;
    else
        jsonDocument["e"][0]["u"] = (char*)NULL;

    int dim = measureJson(jsonDocument) + 1;
    jsonResult = (char*)malloc(sizeof(char) * dim);

    serializeJson(jsonDocument, jsonResult, dim);
}

void setup()
{
    // Initialize pin modes
    pinMode(LED_BUILTIN, OUTPUT);
    pinMode(RED_LED_PIN, OUTPUT);

    // Initialize the red led as OFF, initially
    digitalWrite(RED_LED_PIN, LOW);

    // Initialize the Yùn bridge
    digitalWrite(LED_BUILTIN, LOW);
    Bridge.begin();
    digitalWrite(LED_BUILTIN, HIGH);

    // Initialize serial connection
    Serial.begin(9600);

    // Initialize the mqtt library
    mqtt.begin(F("test.mosquitto.org"), 1883);
    mqtt.subscribe(BASE_TOPIC + String("led"), mqttLedSubscribeCallback);
}

void loop()
{
    unsigned long now = millis();

    if (now >= previousIteration + MAIN_PERIOD_LENGTH || forceLoop)
    {
        previousIteration = now;
        forceLoop = false;
            
        // Monitor for incoming messages
        mqtt.monitor();
    }
    if (now >= previousPublishTime + PUBLISH_PERIOD_LENGTH)
    {
        previousPublishTime = now;

        // Get the current temperature
        analogValue = analogRead(TEMPERATURE_SENSOR_PIN);
        RoverR0 = ANALOG_REFERENCE / analogValue - 1;
        T = 1.f / ((log(RoverR0) / B) + ONE_OVER_T0) - CELSIUS_OFFSET;

        // Publish the SenML readings
        encodeSenML("temperature", T, "Cel");

        mqtt.publish(BASE_TOPIC + String("temperature"), jsonResult);

        // Immediately free the char buffer
        free(jsonResult);
    }
    if (now >= previousSubscribeTime + SUBSCRIBE_TO_CATALOG_PERIOD_LENGTH || forceSubscription)
    {
        previousSubscribeTime = now;
        forceSubscription = false;

        mqtt.publish(BASE_TOPIC + String("catalog/addDevice"), DEVICE_SUBSCRIPTION_JSON_STRING);
    }
}

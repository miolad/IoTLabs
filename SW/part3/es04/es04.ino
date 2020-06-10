#include <ArduinoJson.h>
#include <MQTTclient.h>
// #include <Bridge.h>
// #include <Process.h>
#include <LiquidCrystal_PCF8574.h>

// -------------- CONSTANTS --------------
#define TEMPERATURE_SENSOR_PIN  A0
#define FAN_MODULE_PWM_PIN      9
#define HEATER_LED_PWM_PIN      6
#define PIR_SENSOR_PIN          10
#define NOISE_SENSOR_PIN        7

#define PERIOD_LENGTH_SENSORS   2500 // ms - period of sensor-polling main loop

#define SOUND_EVENTS_LEN_MIN    500  // ms - the minimum length of time that must pass between two valid sound events

#define SUBSCRIBE_TO_CATALOG_PERIOD_LENGTH 60000           // ms

#define B                       4275                       // K
#define ANALOG_REFERENCE        1023.f                     // V
#define ONE_OVER_T0             1.f / (25.0 + 273.15)      // K
#define CELSIUS_OFFSET          273.15                     // K

const char BASE_TOPIC[] = "/tiot/19/Yun/";

// -------------- VARIABLES --------------
int analogValue;
float RoverR0, T;

bool forceSensorLoop = true, forceSubscription = true;

volatile bool soundEventHappened = false;

// Used to time the main loop without using delay()
unsigned long timeOfLastLoopSensors = 0;
unsigned long timeOfLastValidSoundEvent = 0;
unsigned long timeOfLastSubscription = 0;

// Used to count how many times to call mqtt.monitor() in a loop
bool callbackRan = false;

LiquidCrystal_PCF8574 lcd(0x27);

StaticJsonDocument<100> jsonDocument;

void subscribeToDeviceCatalog()
{
    Process p;

    p.begin(F("/root/subscribeToCatalog.sh"));
    p.run();
}

template<typename T> void mqttPublishSenML(String topic, const char* resource, double timestamp, T value, const char* unit)
{
    // I'm going to trust (well, myself) to use a supported type for value (numeric or string type)
    //DynamicJsonDocument jsonDocument(JSON_OBJECT_SIZE(2) + JSON_ARRAY_SIZE(1) + JSON_OBJECT_SIZE(4) + 40);
    jsonDocument.clear();

    // Build the JSON
    jsonDocument["bn"] = "Yun";

    jsonDocument["e"][0]["n"] = resource;
    jsonDocument["e"][0]["t"] = timestamp;
    jsonDocument["e"][0]["v"] = value;
    jsonDocument["e"][0]["u"] = unit; // Automatic NULL unit

    String result;
    serializeJson(jsonDocument, result);

    // Pulish the resulting JSON
    mqtt.publish(BASE_TOPIC + String(topic), result);
}

void actuationCallback(const String& topic, const String& subtopic, const String& message)
{
    callbackRan = true;
    
    // Deserialize the received JSON
    //DynamicJsonDocument jsonDocument(JSON_OBJECT_SIZE(2) + JSON_ARRAY_SIZE(1) + JSON_OBJECT_SIZE(4) + 40);
    jsonDocument.clear();

    DeserializationError err = deserializeJson(jsonDocument, message);

    // Ignore invalid commands
    if (err)
    {
        Serial.println(F("Invalid JSON: cannot be deserialized"));
        return;
    }

    // Check if the JSON is valid
    if (jsonDocument["bn"] != "Yun")
    {
        Serial.println(F("Invalid JSON received: not for this device"));
        return;
    }
    if (jsonDocument["e"][0]["v"] < 0 || jsonDocument["e"][0]["v"] > 255)
    {
        Serial.println(F("Invalid JSON received: PWM value out of bounds"));
        return;
    }
    if (jsonDocument["e"][0]["n"] == "ht")
    {
        Serial.println(F("Changing HT"));

        analogWrite(HEATER_LED_PWM_PIN, jsonDocument["e"][0]["v"]);
        return;
    }
    if (jsonDocument["e"][0]["n"] == "ac")
    {
        Serial.println(F("Changing AC"));

        analogWrite(FAN_MODULE_PWM_PIN, jsonDocument["e"][0]["v"]);
        return;
    }
    
    // The function was invalid
    Serial.println(F("Invalid JSON received: unknown function"));
}

void lcdCallback(const String& topic, const String& subtopic, const String& message)
{
    callbackRan = true;
    
    // Deserialize the received JSON
    //StaticJsonDocument<100> jsonDocument;
    jsonDocument.clear();

    DeserializationError err = deserializeJson(jsonDocument, message);

    // Ignore invalid commands
    if (err)
    {
        Serial.println(F("Invalid JSON: cannot be deserialized"));
        return;
    }

    // Check if the JSON is valid
    if (jsonDocument["bn"] != "Yun")
    {
        Serial.println(F("Invalid JSON received: not for this device"));
        return;
    }
    
    if (jsonDocument["e"][0]["n"] < 0 || jsonDocument["e"][0]["n"] > 1)
    {
        Serial.println(F("Invalid JSON received: invalid line"));
        return;
    }

    lcd.setCursor(0, jsonDocument["e"][0]["n"]);
    String toPrint = jsonDocument["e"][0]["v"];
    lcd.print(toPrint);
}

void noiseSensorISR()
{
    // We want ISRs to be as short and quick as possible -> just set a flag and have the main loop do the work
    soundEventHappened = true;
}

void setup()
{
    Serial.begin(9600);

    // Set pin modes
    pinMode(TEMPERATURE_SENSOR_PIN, INPUT);
    pinMode(FAN_MODULE_PWM_PIN, OUTPUT);
    pinMode(HEATER_LED_PWM_PIN, OUTPUT);
    pinMode(PIR_SENSOR_PIN, INPUT);
    pinMode(NOISE_SENSOR_PIN, INPUT);
    pinMode(LED_BUILTIN, OUTPUT);

    // Initially set the fan module to off
    analogWrite(FAN_MODULE_PWM_PIN, LOW);

    // Initially also set the heater led to off
    analogWrite(HEATER_LED_PWM_PIN, LOW);

    // Set the ISR for the noise sensor
    attachInterrupt(digitalPinToInterrupt(NOISE_SENSOR_PIN), noiseSensorISR, FALLING);

    // Setup the lcd display
    lcd.begin(16, 2);
    lcd.setBacklight(255);
    lcd.home();
    lcd.clear();

    // Initialize the Yùn Bridge
    digitalWrite(LED_BUILTIN, LOW);
    Bridge.begin();
    digitalWrite(LED_BUILTIN, HIGH);

    // Initialize the mqtt library
    mqtt.begin(F("test.mosquitto.org"), 1883);

    // Subscribe to actuation commands
    mqtt.subscribe(BASE_TOPIC + String("actuation"), actuationCallback);

    // Subscribe to lcd updates
    mqtt.subscribe(BASE_TOPIC + String("lcd"), lcdCallback);
}

void loop()
{
    unsigned long now = millis();

    if (soundEventHappened && now >= timeOfLastValidSoundEvent + SOUND_EVENTS_LEN_MIN)
    {
        timeOfLastValidSoundEvent = now;

        Serial.println(F("New sound event!"));

        // Publish the new event on the designated mqtt topic
        mqttPublishSenML<char*>("sound", "sound", now / 1000.f, NULL, NULL);
    }

    soundEventHappened = false;
    
    if (now >= timeOfLastLoopSensors + PERIOD_LENGTH_SENSORS || forceSensorLoop)
    {
        timeOfLastLoopSensors = now;
        forceSensorLoop = false;

        // Every time mqtt.monitor() is called, only one message for every topic can be processed
        // With this method, mqtt.monitor() is only called one extra time to ensure that it is still called enough times to process every message
        callbackRan = true;
        while (callbackRan)
        {
            callbackRan = false;
            mqtt.monitor();
        }
        
        // Read the temperature
        analogValue = analogRead(TEMPERATURE_SENSOR_PIN);
        RoverR0 = ANALOG_REFERENCE / analogValue - 1;
        T = 1.f / ((log(RoverR0) / B) + ONE_OVER_T0) - CELSIUS_OFFSET;

        // Publish the temperature reading
        mqttPublishSenML<double>("temperature", "temperature", now / 1000.f, T, "Cel");

        // Read the PIR motion sensor
        int pirReading = digitalRead(PIR_SENSOR_PIN);
        if (pirReading)
        {
            // Publish the reading
            mqttPublishSenML<int>("pir", "pir", now / 1000.f, pirReading, NULL);
            Serial.println("PIR");
        }
    }
    if (now >= timeOfLastSubscription + SUBSCRIBE_TO_CATALOG_PERIOD_LENGTH || forceSubscription)
    {
        timeOfLastSubscription = now;
        forceSubscription = false;

        subscribeToDeviceCatalog();
    }
}
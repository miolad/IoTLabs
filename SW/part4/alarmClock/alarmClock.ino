#include <ArduinoJson.h>
#include <MQTTclient.h>
#include <LiquidCrystal_PCF8574.h>
#include <TimerOne.h>

// -------------- CONSTANTS --------------
#define FAN_MODULE_PWM_PIN      9
#define RED_LED_PIN             6
#define NOISE_SENSOR_PIN        7
#define PIR_SENSOR_PIN          10

#define SUBSCRIBE_TO_CATALOG_PERIOD_LENGTH 60000           // ms
#define SECONDS_LED_PERIOD                 1000000         // us
#define MAIN_LOOP_PERIOD                   1000            // ms

#define SOUND_EVENTS_LEN_MIN               150             // ms
#define SOUND_EVENTS_LEN_MAX               500             // ms

const char BASE_TOPIC[] = "/tiot/19/Yun/";

// -------------- VARIABLES --------------
bool forceMainLoop = true, forceSubscription = true;

volatile bool soundEventHappened = false;
bool secondsLedStatus = 0;
volatile unsigned long timeOfDaySeconds = 0;
bool alarm = false;

// Used to time the main loop without using delay()
unsigned long timeOfLastMainLoop = 0;
unsigned long timeOfLastValidSoundEvent = 0;
unsigned long timeOfLastSubscription = 0;

// Used to count how many times to call mqtt.monitor() in a loop
bool callbackRan = false;

LiquidCrystal_PCF8574 lcd(0x27);

StaticJsonDocument<100> jsonDocument;

void subscribeToDeviceCatalog()
{
    Process p;

    // TODO: Use personalized script
    p.begin(F("/root/subscribeToCatalogAlarmClock.sh"));
    p.run();
}

void mqttTimeSync(const String& topic, const String& subtopic, const String& message)
{
    callbackRan = true;
    
    // Deserialize the received JSON
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
    if (jsonDocument["e"][0]["v"] < 0 || jsonDocument["e"][0]["v"] > 86400)
    {
        Serial.println(F("Invalid JSON received: PWM value out of bounds"));
        return;
    }
    if (jsonDocument["e"][0]["n"] != "ts")
    {
        Serial.println(F("Invalid JSON received: unknown function"));
        return;
    }
    
    timeOfDaySeconds = jsonDocument["e"][0]["v"];
}

void mqttAlarmTrigger(const String& topic, const String& subtopic, const String& message)
{
    // TODO: Trigger an alarm
    callbackRan = true;
    alarm = true;
    analogWrite(FAN_MODULE_PWM_PIN, 255);
}

void noiseSensorISR()
{
    // We want ISRs to be as short and quick as possible -> just set a flag and have the main loop do the work
    soundEventHappened = true;
}

void timerOneISR()
{
    // Flip the seconds led status
    secondsLedStatus = !secondsLedStatus;
    digitalWrite(RED_LED_PIN, secondsLedStatus);

    // And increase the internal timer by one second
    ++timeOfDaySeconds;
}

void setup()
{
    Serial.begin(9600);

    // Set pin modes
    pinMode(RED_LED_PIN, OUTPUT);
    pinMode(FAN_MODULE_PWM_PIN, OUTPUT);
    pinMode(NOISE_SENSOR_PIN, INPUT);
    pinMode(LED_BUILTIN, OUTPUT);
    pinMode(PIR_SENSOR_PIN, INPUT);

    // Initially set the fan module to off
    analogWrite(FAN_MODULE_PWM_PIN, 0);
    digitalWrite(RED_LED_PIN, LOW);

    // Set the ISR for the noise sensor
    attachInterrupt(digitalPinToInterrupt(NOISE_SENSOR_PIN), noiseSensorISR, FALLING);

    // Initialize the ISR for updating the seconds led
    Timer1.initialize(SECONDS_LED_PERIOD);
    Timer1.attachInterrupt(timerOneISR);

    // Setup the lcd display
    lcd.begin(16, 2);
    lcd.setBacklight(0); // Initially off
    lcd.home();
    lcd.clear();

    // Initialize the Yùn Bridge
    digitalWrite(LED_BUILTIN, LOW);
    Bridge.begin();
    digitalWrite(LED_BUILTIN, HIGH);

    // Initialize the mqtt library
    mqtt.begin(F("test.mosquitto.org"), 1883);

    // Subscribe to time updates
    mqtt.subscribe(BASE_TOPIC + String("timeUpdate"), mqttTimeSync);

    // Subscribe to alarm triggers
    mqtt.subscribe(BASE_TOPIC + String("alarmTrigger"), mqttAlarmTrigger);
}

void loop()
{
    unsigned long now = millis();

    if (soundEventHappened && now >= timeOfLastValidSoundEvent + SOUND_EVENTS_LEN_MIN)
    {
        if (now <= timeOfLastValidSoundEvent + SOUND_EVENTS_LEN_MAX)
        {
            // A double clap happened
            alarm = false;
            analogWrite(FAN_MODULE_PWM_PIN, 0);
        }

        timeOfLastValidSoundEvent = now;
    }

    soundEventHappened = false;
    
    if (now >= timeOfLastMainLoop + MAIN_LOOP_PERIOD || forceMainLoop)
    {
        timeOfLastMainLoop = now;
        forceMainLoop = false;

        // Every time mqtt.monitor() is called, only one message for every topic can be processed
        // With this method, mqtt.monitor() is only called one extra time to ensure that it is still called enough times to process every message
        callbackRan = true;
        while (callbackRan)
        {
            callbackRan = false;
            mqtt.monitor();
        }

        // Use the pir sensor to determine if the lcd should be on or not
        // (use the hardware timeout of the pir sensor for a nice and automatic screen on duration)
        lcd.setBacklight(255 * digitalRead(PIR_SENSOR_PIN));

        // Update the display
        int h = timeOfDaySeconds / 3600;
        int m = (timeOfDaySeconds % 3600) / 60;
        int s = timeOfDaySeconds - (h * 3600) - (m * 60);

        lcd.setCursor(0, 0);
        if (h < 10) lcd.print("0");
        lcd.print(h);
        lcd.print(":");
        if (m < 10) lcd.print("0");
        lcd.print(m);
        lcd.print(":");
        if (s < 10) lcd.print("0");
        lcd.print(s);
    }

    if (now >= timeOfLastSubscription + SUBSCRIBE_TO_CATALOG_PERIOD_LENGTH || forceSubscription)
    {
        timeOfLastSubscription = now;
        forceSubscription = false;

        subscribeToDeviceCatalog();
    }
}
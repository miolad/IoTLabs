#include <IntegerArrayDeque.hpp>

// -------------- CONSTANTS --------------
#define TEMPERATURE_SENSOR_PIN  A0
#define FAN_MODULE_PWM_PIN      9
#define HEATER_LED_PWM_PIN      6
#define PIR_SENSOR_PIN          13
#define NOISE_SENSOR_PIN        7

#define PERIOD_LENGTH_SENSORS   2500 // ms - period of sensor-polling main loop

#define SOUND_EVENTS_MIN        10   // 50 events in timeoutSound to register a person
#define SOUND_EVENTS_LEN_MIN    500  // ms - the minimum length of time that must pass between two valid sound events

#define B 4275                                      // K
#define ANALOG_REFERENCE 1023.f                     // V
#define ONE_OVER_T0 1.f / (25.0 + 273.15)           // K
#define CELSIUS_OFFSET 273.15                       // K

// -------------- VARIABLES --------------
int analogValue;
float RoverR0, T;

bool person = false; // Global best guess at 'is there a person in the room?'

const long timeoutPir = 1800000;                     // 30 minutes in ms
unsigned int millisSinceLastPerson = 0;
bool personPir = false;

// TODO: change me
const unsigned long soundInterval = 15 * 1000;              // ms
const unsigned long timeoutSound = 10 * 1000;               // ms

// TODO: please optimize me
IntegerArrayDeque soundEventsBuffer(SOUND_EVENTS_MIN);
unsigned short numSoundEventsInBuffer = 0;
short lastSoundEventIndex = -1;
bool personSound = false;
volatile bool soundEventHappened = false;

// Used to time the main loop without using delay()
unsigned long timeOfLastLoopSensors = 0;

// -------------- Default temperature set points --------------
float setPointACPersonMin =          25.f;     // Celsius
float setPointACPersonMax =          27.f;     // Celsius
float setPointACNoPersonMin =        23.f;     // Celsius
float setPointACNoPersonMax =        25.f;     // Celsius

float setPointHTPersonMin =           23.f;     // Celsius
float setPointHTPersonMax =           27.f;     // Celsius
float setPointHTNoPersonMin =         21.f;     // Celsius
float setPointHTNoPersonMax =         25.f;     // Celsius

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

    pinMode(11, OUTPUT);

    // Initially set the fan module to off
    analogWrite(FAN_MODULE_PWM_PIN, 0);

    // Initially also set the heater led to off
    analogWrite(HEATER_LED_PWM_PIN, 0);

    // Set the ISR for the noise sensor
    attachInterrupt(digitalPinToInterrupt(NOISE_SENSOR_PIN), noiseSensorISR, FALLING);
}

void loop()
{
    unsigned long now = millis();

    // Shouldn't need special care for overflow edge cases
    if (soundEventHappened && now >= soundEventsBuffer.getFromTop() + SOUND_EVENTS_LEN_MIN)
    {
        digitalWrite(11, 1);

        // Detect overflows
        if (now < soundEventsBuffer.getFromTop())
            soundEventsBuffer.reset();

        // New sound event -> register it in the deque
        soundEventsBuffer.put(now);

        // Now let's purge the deque of all the events that occurred before now - soundInterval
        while (now > soundInterval && soundEventsBuffer.get() < now - soundInterval)
            soundEventsBuffer.pop();

        // If the deque is full, it means that we have registered at least enough sound events in the latest soundInterval
        // -> there is probably a person in the room
        if (soundEventsBuffer.isFull())
            personSound = true;

        // DEBUG: print number of events in buffer to serial
        Serial.print("noiseSensorISR: ");
        Serial.println(soundEventsBuffer.count());

        digitalWrite(11, 0);
    }

    // Reset the flag anyway
    soundEventHappened = false;
    
    if (now >= timeOfLastLoopSensors + PERIOD_LENGTH_SENSORS)
    {
        timeOfLastLoopSensors = now;
        
        // Read the analog value as a 10 bit integer
        analogValue = analogRead(TEMPERATURE_SENSOR_PIN);

        // Compute the resistance R
        RoverR0 = ANALOG_REFERENCE / analogValue - 1;

        // Get the temperature in Celsius
        T = 1.f / ((log(RoverR0) / B) + ONE_OVER_T0) - CELSIUS_OFFSET;

        // If enough time has passed since the last sound event, the person that (maybe) was in the room probably went away
        if (now >= soundEventsBuffer.getFromTop() + timeoutSound)
            personSound = false;

        // Read the PIR motion sensor
        if (digitalRead(PIR_SENSOR_PIN))
        {
            // There is a person in the room
            personPir = true;

            // Reset the time since last person
            millisSinceLastPerson = now;        
        }
        else if (now - millisSinceLastPerson >= timeoutPir)
        {
            // The timeout has passed, the person is probably not here anymore
            personPir = false;
        }

        // At this point, we can just OR the two contributes
        person = personPir | personSound;

        // Get the proper setpoints
        float setPointACMin = person ? setPointACPersonMin : setPointACNoPersonMin;
        float setPointACMax = person ? setPointACPersonMax : setPointACNoPersonMax;
        float setPointHTMin = person ? setPointHTPersonMin : setPointHTNoPersonMin;
        float setPointHTMax = person ? setPointHTPersonMax : setPointHTNoPersonMax;

        // Calculate the percent
        float tempPercentAC = constrain((T - setPointACMin) / (setPointACMax - setPointACMin), 0.f, 1.f);
        float tempPercentHT = constrain((T - setPointHTMin) / (setPointHTMax - setPointHTMin), 0.f, 1.f);

        // Set the corresponding PWM output for the fan module
        analogWrite(FAN_MODULE_PWM_PIN, 255 * tempPercentAC);

        // Set the 'heater' intensity according to ambient temperature
        analogWrite(HEATER_LED_PWM_PIN, 255 * tempPercentHT);
        
        Serial.print("TEMPERATURE: ");
        Serial.print(T);
        Serial.print(", ");
        Serial.print(tempPercentAC);
        Serial.print(", ");
        Serial.print(tempPercentHT);
        Serial.print(", personPir: ");
        Serial.print(personPir ? "true" : "false");
        Serial.print(", personSound: ");
        Serial.print(personSound ? "true" : "false");
        Serial.print(", setPointACMin = ");
        Serial.print(setPointACMin);
        Serial.print(", setPointACMax = ");
        Serial.println(setPointACMax);
    }
}
#define TEMPERATURE_SENSOR_PIN  A0
#define FAN_MODULE_PWM_PIN      9
#define HEATER_LED_PWM_PIN      6
#define PIR_SENSOR_PIN          13

#define PERIOD_LENGTH           2.5f // Seconds

// const int R0 = 100000;                      // Ohm
const int B = 4275;                            // K
const float analogReferenceV = 1023.f;         // V
const float oneOverT0 = 1.f / (25.0 + 273.15); // K
const float celsiusOffset = 273.15;            // K

const float TEMPERATURE_SET_POINT_FAN_MIN = 25.f;          // Celsius
const float TEMPERATURE_SET_POINT_FAN_MAX = 27.f;          // Celsius

const float TEMPERATURE_SET_POINT_HT_MIN = 24.f;          // Celsius
const float TEMPERATURE_SET_POINT_HT_MAX = 26.f;          // Celsius

int analogValue;
float RoverR0, T;

const float timeoutPir = 30 * 60 * 1000;             // 30 minutes in ms
float millisSinceLastPerson = 0.f;
bool person = false;

void setup()
{
    Serial.begin(9600);

    // Set pin modes
    pinMode(TEMPERATURE_SENSOR_PIN, INPUT);
    pinMode(FAN_MODULE_PWM_PIN, OUTPUT);
    pinMode(HEATER_LED_PWM_PIN, OUTPUT);
    pinMode(PIR_SENSOR_PIN, INPUT);

    // Initially set the fan module to off
    analogWrite(FAN_MODULE_PWM_PIN, 0);

    // Initially also set the heater led to off
    analogWrite(HEATER_LED_PWM_PIN, 0);
}

void loop()
{
    // Read the analog value as a 10 bit integer
    analogValue = analogRead(TEMPERATURE_SENSOR_PIN);

    // Compute the resistance R
    RoverR0 = analogReferenceV / analogValue - 1;

    // Get the temperature in Celsius
    T = 1.f / ((log(RoverR0) / B) + oneOverT0) - celsiusOffset;

    // Calculate the percent
    float tempPercentAC = constrain((T - TEMPERATURE_SET_POINT_FAN_MIN) / (TEMPERATURE_SET_POINT_FAN_MAX - TEMPERATURE_SET_POINT_FAN_MIN), 0.f, 1.f);
    float tempPercentHT = constrain((T - TEMPERATURE_SET_POINT_HT_MIN) / (TEMPERATURE_SET_POINT_HT_MAX - TEMPERATURE_SET_POINT_HT_MIN), 0.f, 1.f);

    // Set the corresponding PWM output for the fan module
    analogWrite(FAN_MODULE_PWM_PIN, 255 * tempPercentAC);

    // Set the 'heater' intensity according to ambient temperature
    analogWrite(HEATER_LED_PWM_PIN, 255 * tempPercentHT);

    // Read the PIR motion sensor
    if (digitalRead(PIR_SENSOR_PIN))
    {
        // There is a person in the room
        person = true;

        // Reset the time since last person
        millisSinceLastPerson = millis();        
    }
    else if (millis() - millisSinceLastPerson >= timeoutPir)
    {
        // The timeout has passed, the person is probably not here anymore
        person = false;
    }
    
    Serial.print("TEMPERATURE: ");
    Serial.print(T);
    Serial.print(", ");
    Serial.print(tempPercentAC);
    Serial.print(", ");
    Serial.print(tempPercentHT);
    Serial.print(", person: ");
    Serial.println(person ? "true" : "false");

    delay(PERIOD_LENGTH * 1e3);
}
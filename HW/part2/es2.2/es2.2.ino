const int TEMPERATURE_SENSOR_PIN = A0;
const int FAN_MODULE_PWM_PIN = 9;
const int HEATER_LED_PWM_PIN = 6;

const float

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

void setup()
{
    Serial.begin(9600);

    // Set pin modes
    pinMode(TEMPERATURE_SENSOR_PIN, INPUT);
    pinMode(FAN_MODULE_PWM_PIN, OUTPUT);
    pinMode(HEATER_LED_PWM_PIN, OUTPUT);

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

    Serial.print("TEMPERATURE: ");
    Serial.print(T);
    Serial.print(", ");
    Serial.print(tempPercentAC);
    Serial.print(", ");
    Serial.println(tempPercentHT);

    delay(1000);
}
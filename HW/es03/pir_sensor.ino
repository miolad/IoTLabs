const int LED_PIN = 12;
const int PIR_SENSOR_PIN = 7;

const float SERIAL_NOTIFICATION_PERIOD = 30; // In seconds

volatile int totCount = 0; // Counter of the times the sensor has triggered an interrupt

void pirSensorCallback()
{
    // Set the led status according to the status of the sensor's pin
    bool pin = digitalRead(PIR_SENSOR_PIN);

    digitalWrite(LED_PIN, pin);

    // Increment the counter if the pin is rising
    if (pin)
        ++totCount;
}

void setup()
{
    // Initialize the Serial connection
    Serial.begin(9600);

    pinMode(LED_PIN, OUTPUT);       // Set the LED pin to output
    pinMode(PIR_SENSOR_PIN, INPUT); // Set the pin for the motion sensor to input

    attachInterrupt(digitalPinToInterrupt(PIR_SENSOR_PIN), pirSensorCallback, CHANGE);
}

void loop()
{
    delay(SERIAL_NOTIFICATION_PERIOD * 1e3);

    // Notify the computer
    Serial.print("Total people count: ");
    Serial.println(totCount);
    Serial.flush();
}
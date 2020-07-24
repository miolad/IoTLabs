#include <LiquidCrystal_PCF8574.h>

const int TEMPERATURE_SENSOR_PIN = A0;
const float TIME_PERIOD = 5; // 5s

// const int R0 = 100000;                      // Ohm
const int B = 4275;                            // K
const float analogReferenceV = 1023.f;         // V
const float oneOverT0 = 1.f / (25.0 + 273.15); // K
const float celsiusOffset = 273.15;            // K

int analogValue;
float RoverR0, T;

LiquidCrystal_PCF8574 lcd(0x27);

void setup()
{
    // Setup the display
    lcd.begin(16, 2);
    lcd.setBacklight(255);
    lcd.home();
    lcd.clear();
    lcd.print("Temperature:");

    pinMode(TEMPERATURE_SENSOR_PIN, INPUT);
}

void loop()
{
    // Read the analog value as a 10 bit integer
    analogValue = analogRead(TEMPERATURE_SENSOR_PIN);

    // Compute the resistance R
    RoverR0 = analogReferenceV / analogValue - 1;

    // Get the temperature in Celsius
    T = 1.f / ((log(RoverR0) / B) + oneOverT0) - celsiusOffset;

    // Print the result to the lcd screen
    lcd.print(T);

    // Reset the cursor position for the next iteration
    lcd.setCursor(12, 0);

    delay(TIME_PERIOD * 1e3);
}
#include <TimerOne.h>

const int RLED_PIN = 12;
const int GLED_PIN = 11;

const float R_HALF_PERIOD = 1.5;
const float G_HALF_PERIOD = 3.5;

volatile int greenLedState = LOW; // this variable needs to be 'volatile' because it
                                  // is accessed both from an ISR (blinkGreen()), and from the main loop.
int redLedState = LOW;

void blinkGreen()
{
  greenLedState = !greenLedState;
  digitalWrite(GLED_PIN, greenLedState);
}

void setup() {
  // Setup Serial connection (the serial console must be opened for this program to start)
  Serial.begin(9600);
  while (!Serial); // Wait for serial connection to be established
  Serial.println("Lab 1.2 starting...");

  // Setup pins
  pinMode(RLED_PIN, OUTPUT);
  pinMode(GLED_PIN, OUTPUT);

  // Setup Timer1 library
  Timer1.initialize(G_HALF_PERIOD * 1e06);
  Timer1.attachInterrupt(blinkGreen);
}

void loop() {
  int byteFromSerial = -1;

  // Empty the serial buffer and maintain only the last byte
  while (Serial.available())
    byteFromSerial = Serial.read();

  switch (byteFromSerial)
  {
    case -1:
      // No data on serial port
      break;

    case 'R':
      Serial.print("RED Led Status: "); // Using '!' to display current info
      Serial.println(!redLedState);
      Serial.flush();
      break;
    
    case 'L':
      Serial.print("GREEN Led Status: ");
      Serial.println(greenLedState);
      Serial.flush();
      break;

    default:
      // Carattere non valido
      Serial.println("Invalid command");
  }

  redLedState = !redLedState;
  digitalWrite(RLED_PIN, redLedState);
  delay(R_HALF_PERIOD * 1e03);
}

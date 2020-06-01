const int FAN_MODULE_PWM_PIN = 9;
const int STEPS_TO_FULL = 8;

byte pwmValue = 0;
byte pwmStepIndex = 0;

void setup()
{
    // Setup serial connection
    Serial.begin(9600);

    // Set pin mode
    pinMode(FAN_MODULE_PWM_PIN, OUTPUT);

    // Initialize the pwm value to zero
    analogWrite(FAN_MODULE_PWM_PIN, pwmValue);
}

void loop()
{
    if (!Serial.available())
        return;
    
    unsigned char byteFromSerial = 0;

    // Consume all bytes in the buffer and keep only the last one
    while (Serial.available())
        byteFromSerial = Serial.read();

    switch (byteFromSerial)
    {
        case '+':
            if (pwmStepIndex >= STEPS_TO_FULL)
                Serial.println("Already at full!");
            else
            {           
                ++pwmStepIndex;
                pwmValue = 255 * ((float)pwmStepIndex / STEPS_TO_FULL);

                Serial.print("Increasing speed: ");
                Serial.println(pwmValue);
            }

            break;

        case '-':
            if (pwmStepIndex <= 0)
                Serial.println("Already at zero!");
            else
            {                
                --pwmStepIndex;
                pwmValue = 255 * ((float)pwmStepIndex / STEPS_TO_FULL);

                Serial.print("Decreasing speed: ");
                Serial.println(pwmValue);
            }

            break;

        default:
            Serial.println("Invalid command!");
    }

    Serial.flush();
        
    // Update pwm output
    analogWrite(FAN_MODULE_PWM_PIN, pwmValue);
}
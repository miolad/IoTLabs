// Initializes static content on the display based on the current mode
void printStaticContentLCD()
{
    switch (lcdStatus)
    {
    case 0:
        lcd.setCursor(0, 0);
        lcd.print("T: 00.0, Pres:0 ");
        lcd.setCursor(0, 1);
        lcd.print("AC:000%, HT:000%");
        break;

    case 1:
        lcd.setCursor(0, 0);
        lcd.print("AC m:     M:    ");
        lcd.setCursor(0, 1);
        lcd.print("HT m:     M:    ");
    }

    // Trigger an update of dynamic content
    forceSensorLoop = true;
}

void updateDynamicContentLCD(float setPointACMin, float setPointACMax, float setPointHTMin,
    float setPointHTMax, float T, bool person, byte tempPercentAC, byte tempPercentHT)
{
    if (lcdStatus)
        {
            // Update AC
            lcd.setCursor(5, 0);
            lcd.print(setPointACMin, 1);
            lcd.setCursor(12, 0);
            lcd.print(setPointACMax, 1);

            // Update HT
            lcd.setCursor(5, 1);
            lcd.print(setPointHTMin, 1);
            lcd.setCursor(12, 1);
            lcd.print(setPointHTMax, 1);
        }
        else
        {
            // Update temperature
            lcd.setCursor(3, 0);
            lcd.print(T, 1);

            // Update presence
            lcd.setCursor(14, 0);
            lcd.print(person);

            // The reason I'm doing all of this is because I want leading zeros on my percentages, but I don't want
            // to waste 5% of the available space for programs on the arduino to sprintf

            // Update AC
            lcd.setCursor(3, 1);
            lcd.print(tempPercentAC == 100);
            lcd.print((tempPercentAC = tempPercentAC % 100) > 9 ? (tempPercentAC / 10) : 0);
            lcd.print(tempPercentAC % 10);

            // Update HT
            lcd.setCursor(12, 1);
            lcd.print(tempPercentHT == 100);
            lcd.print((tempPercentHT = tempPercentHT % 100) > 9 ? (tempPercentHT / 10) : 0);
            lcd.print(tempPercentHT % 10);
        }
}

// First initialization of the i2c display
void initLCD()
{
    lcd.begin(16, 2);
    lcd.setBacklight(255);
    lcd.home();
    lcd.clear();

    // Initialize static content for the first screen
    printStaticContentLCD();
}
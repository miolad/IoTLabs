from typing import List

# Constants
CELSIUS_OFFSET = 273.15
FAHRENHEIT_CONST_1 = 32.0
FAHRENHEIT_CONST_2 = 5.0/9.0
FAHRENHEIT_CONST_3 = 459.67

# To Kelvin

def celsiusToKelvin(val: float) -> float:
    return val + CELSIUS_OFFSET

def fahrenheitToKelvin(val: float) -> float:
    return FAHRENHEIT_CONST_2 * (val - FAHRENHEIT_CONST_1) + CELSIUS_OFFSET

# From Kelvin

def kelvinToCelsius(val: float) -> float:
    return val - CELSIUS_OFFSET

def kelvinToFahrenheit(val: float) -> float:
    return val / FAHRENHEIT_CONST_2 - FAHRENHEIT_CONST_3

# Generic

# Converts the specified value from the original unit to the target unit.
# The units must be one of "K", "C", or "F". They must be uppercase.
def convert(val: float, originalUnit: str, targetUnit: str) -> float:
    # Assume the units are correct

    if originalUnit == targetUnit:
        # Nothing to do here
        return val

    # Convert to Kelvin first
    valKelvin = 0
    valTarget = 0

    if originalUnit == "K":
        valKelvin = val
    elif originalUnit == "C":
        valKelvin = celsiusToKelvin(val)
    else:
        valKelvin = fahrenheitToKelvin(val)

    # Then convert to targetUnit
    if targetUnit == "K":
        valTarget = valKelvin
    elif targetUnit == "C":
        valTarget = kelvinToCelsius(valKelvin)
    else:
        valTarget = kelvinToFahrenheit(valKelvin)

    return valTarget

# Converts a list of temperature values to the desired unit.
# The same precautions of convert(...) apply here.
def convertMultiple(vals: List[float], originalUnit: str, targetUnit: str) -> List[float]:
    if originalUnit == targetUnit:
        return vals

    valsTarget = []

    for v in vals:
        valsTarget.append(convert(v, originalUnit, targetUnit))

    return valsTarget
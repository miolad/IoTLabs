// Reads all the bytes from Serial and puts them in the global 'cmd' buffer.
// Returns true if a '\n'-terminated string has been read (and null-terminated).
bool readCommand()
{
    // Read all the bytes from serial
    while (Serial.available() && cmdBufferIndex < COMMAND_MAX_LENGTH)
    {
        cmd[cmdBufferIndex++] = Serial.read();

        if (cmd[cmdBufferIndex] == '\n')
            break;
    }

    // Check if the command is complete
    if (cmd[cmdBufferIndex - 1] == '\n')
    {
        // We have a new command
        // Substitute the trailing '\n' with a '\0'
        cmd[cmdBufferIndex - 1] = '\0';

        // Reset the command buffer
        cmdBufferIndex = 0;

        return true;
    }
    else if (cmdBufferIndex >= COMMAND_MAX_LENGTH)
    {
        // The command buffer is full -> empty it (the command will probably be wrong anyway)
        cmdBufferIndex = 0;
    }

    return false;
}

// Trims white spaces from the beginning of *str;
void trimSpaces(char** str)
{
    unsigned int i;
    for (i = 0; isspace((*str)[i]); ++i);
    
    *str += i;
}

// Essentially the opposite of trimSpaces, this one trims *until* a space
void skipToSpace(char** str)
{
    unsigned int i;
    for (i = 0; !isspace((*str)[i]); ++i);

    *str += i;
}

// Format: usp <set-point> <min> <max>
// where: <set-point> must be one of:
//      - 'ac[p]': ac set-point with or without a person;
//      - 'ht[p]': heater set-point with or without a person
// and <min>/<max> must be valid floating point temperatures in Celsius
//
// Note: before calling this function, make sure that cmd is null-terminated
void parseCommand()
{  
    // Command buffer as variable pointer
    char* cmdp = cmd;
    float* spMin, * spMax;

    // Trim white spaces from the front of cmdp
    trimSpaces(&cmdp);

    // Is the command valid?
    if (strncmp(cmdp, "usp ", 4))
    {
        // The command is not supported!
        Serial.println("ERROR: Command not found!");
        return;
    }

    cmdp += 4;
    trimSpaces(&cmdp);

    if (!strncmp(cmdp, "ac ", 3))
    {
        spMin = &setPointACNoPersonMin;
        spMax = &setPointACNoPersonMax;

        cmdp += 3;
    }
    else if (!strncmp(cmdp, "acp ", 4))
    {
        spMin = &setPointACPersonMin;
        spMax = &setPointACPersonMax;

        cmdp += 4;
    }
    else if (!strncmp(cmdp, "ht ", 3))
    {
        spMin = &setPointHTNoPersonMin;
        spMax = &setPointHTNoPersonMax;

        cmdp += 3;
    }
    else if (!strncmp(cmdp, "htp ", 4))
    {
        spMin = &setPointHTPersonMin;
        spMax = &setPointHTPersonMax;

        cmdp += 4;
    }
    else
    {
        // The command is invalid
        Serial.println("ERROR: Command not supported!");
        return;
    }
    
    // Finally, update the setpoints (atof automatically skips spaces)
    trimSpaces(&cmdp);
    *spMin = atof(cmdp);
    skipToSpace(&cmdp);
    *spMax = atof(cmdp);

    Serial.println("SUCCESS: Set points updated successfully!");
}
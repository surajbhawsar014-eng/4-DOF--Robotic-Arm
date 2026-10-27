
#include <Servo.h>
#include <string.h>
#include <stdlib.h>

const byte MOTOR_COUNT = 4;
const byte motorPins[MOTOR_COUNT] = {9, 10, 11, 12};

// Default positions from your screenshot
const int defaultAngles[MOTOR_COUNT] = {10, 90, 10, 0};

Servo motors[MOTOR_COUNT];
int currentAngles[MOTOR_COUNT] = {10, 90, 10, 0};

char inputBuffer[32];
byte inputIndex = 0;

void processCommand(char *cmd) {
  char *comma = strchr(cmd, ',');
  if (comma == NULL) return;

  *comma = '\0';

  char *end1;
  char *end2;

  long motorNumber = strtol(cmd, &end1, 10);
  long angle = strtol(comma + 1, &end2, 10);

  if (*end1 != '\0' || *end2 != '\0') return;
  if (motorNumber < 1 || motorNumber > MOTOR_COUNT) return;
  if (angle < 0 || angle > 180) return;

  byte index = motorNumber - 1;

  motors[index].write((int)angle);
  currentAngles[index] = (int)angle;

  Serial.print("OK,");
  Serial.print(motorNumber);
  Serial.print(",");
  Serial.println(angle);
}

void setup() {
  Serial.begin(115200);

  for (byte i = 0; i < MOTOR_COUNT; i++) {
    motors[i].attach(motorPins[i]);
    motors[i].write(defaultAngles[i]);
  }

  Serial.println("READY");
}

void loop() {
  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '\n') {
      inputBuffer[inputIndex] = '\0';

      if (inputIndex > 0) {
        processCommand(inputBuffer);
      }

      inputIndex = 0;
    }
    else if (c != '\r') {
      if (inputIndex < sizeof(inputBuffer) - 1) {
        inputBuffer[inputIndex++] = c;
      } else {
        inputIndex = 0;
      }
    }
  }
}
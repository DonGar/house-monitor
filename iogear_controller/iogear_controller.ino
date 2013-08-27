
//
// This sketch can be used to control a physically modified IOGear KVM.
//

// Pins connected to hot side of each KVM switch button.
// The KVM buttons activate when they reach ground. These GPIOs are set
// to output and will act like ground if they are LOW, but not when HIGH.
// Diodes are used to protect the KVM from our output voltage.
const int buttonPin[] = {3, 4, 5, 6};

// Pins connected to LEDs to display button pushing. HIGH to display, LOW
// for dark.
const int ledPin[] = {7, 8, 9, 10};

// Which button was pushed most recently. Might not be active on the KVM
// if the KVM switched for any other reason.
int active = 0;  // 0 - 3, not 1-4.

void setup() {

 // Setup our four output pins.
  for (int i = 0; i < 4; i++) {
    pinMode(buttonPin[i], OUTPUT);
    digitalWrite(buttonPin[i], HIGH);
    pinMode(ledPin[i], OUTPUT);
    digitalWrite(ledPin[i], LOW);
  }

  // Serial if you need it
  Serial.begin(9600);
  Serial.setTimeout(100);  // Never block reads more than 100 milliseconds

  runDiagnostic();

  // Move to default computer so we know active device.
  setActive(1);
  reportState();
}

void loop() {
  int received = Serial.read();
  if (received == -1)
    // Didn't receive anything.
    return;

  // Convert from ASCII to int.
  int target = received - '0';

  if (target >= 0 && target <= 3) {
    setActive(target);
  } else {
    runDiagnostic();
  }

  reportState();
}

void setActive(int i) {
  active = i;

  digitalWrite(buttonPin[i], LOW);
  digitalWrite(ledPin[i], HIGH);

  delay(1100);

  digitalWrite(buttonPin[i], HIGH);
  digitalWrite(ledPin[i], LOW);
}

void reportState() {
  // Print out the active computer (0-3)
  Serial.print(active);
  Serial.print("\n");
}

void runDiagnostic()
{
  // Flash all of the leds twice.
  for (int j = 0; j < 2; j++) {
    for (int i = 0; i < 4; i++)
      digitalWrite(ledPin[i], HIGH);

    delay(200);

    for (int i = 0; i < 4; i++)
      digitalWrite(ledPin[i], LOW);\

    delay(200);
  }
}


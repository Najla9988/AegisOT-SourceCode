#define GREEN_LED 12
#define RED_LED 11
#define YELLOW_LED 10
#define BLACK_LED 9
#define BUZZER_PIN 8
#define RESET_BUTTON 2
#define POT_PIN A0

String command = "";
String currentState = "NORMAL";

bool lastButtonState = HIGH;

const unsigned long ALERT_DURATION = 3000; // 3 seconds
unsigned long alertStartTime = 0;
bool alertRunning = false;

#define MAX_QUEUE 20
String alertQueue[MAX_QUEUE];
int queueStart = 0;
int queueEnd = 0;

void buzzerOff() {
  noTone(BUZZER_PIN);
}

void buzzerOnAlert() {
  tone(BUZZER_PIN, 1000);
}

void clearAlerts() {
  digitalWrite(RED_LED, LOW);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(BLACK_LED, LOW);
  buzzerOff();
}

void setNormalState() {
  currentState = "NORMAL";
  digitalWrite(GREEN_LED, HIGH);
  clearAlerts();
}

void setReplayState() {
  currentState = "REPLAY";
  digitalWrite(GREEN_LED, HIGH);
  clearAlerts();
  digitalWrite(RED_LED, HIGH);
  buzzerOnAlert();
}

void setRateState() {
  currentState = "RATE";
  digitalWrite(GREEN_LED, HIGH);
  clearAlerts();
  digitalWrite(YELLOW_LED, HIGH);
}

void setSequenceState() {
  currentState = "SEQUENCE";
  digitalWrite(GREEN_LED, HIGH);
  clearAlerts();
  digitalWrite(BLACK_LED, HIGH);
  buzzerOnAlert();
}

void setAclState() {
  currentState = "ACL";
  digitalWrite(GREEN_LED, HIGH);
  clearAlerts();
  digitalWrite(BLACK_LED, HIGH);
  digitalWrite(YELLOW_LED, HIGH);
}

void setTamperState() {
  currentState = "TAMPER";
  digitalWrite(GREEN_LED, HIGH);
  clearAlerts();
  digitalWrite(BLACK_LED, HIGH);
}

void setShutdownState() {
  currentState = "SHUTDOWN";
  digitalWrite(GREEN_LED, LOW);
  clearAlerts();
  digitalWrite(RED_LED, HIGH);
  digitalWrite(YELLOW_LED, HIGH);
  digitalWrite(BLACK_LED, HIGH);
  buzzerOnAlert();
}

bool queueIsEmpty() {
  return queueStart == queueEnd;
}

bool queueIsFull() {
  return ((queueEnd + 1) % MAX_QUEUE) == queueStart;
}

void enqueueAlert(String alert) {
  if (!queueIsFull()) {
    alertQueue[queueEnd] = alert;
    queueEnd = (queueEnd + 1) % MAX_QUEUE;
  } else {
    Serial.println("QUEUE_FULL:ALERT_DROPPED");
  }
}

String dequeueAlert() {
  String alert = alertQueue[queueStart];
  queueStart = (queueStart + 1) % MAX_QUEUE;
  return alert;
}

bool isAlertCommand(String cmd) {
  return cmd == "REPLAY" || cmd == "RATE" || cmd == "SEQUENCE" || cmd == "ACL" || cmd == "TAMPER" || cmd == "SHUTDOWN";
}

void startAlert(String alert) {
  if (alert == "REPLAY") {
    setReplayState();
    Serial.println("STATE:REPLAY_BLOCKED");
  }
  else if (alert == "RATE") {
    setRateState();
    Serial.println("STATE:RATE_LIMIT_BLOCKED");
  }
  else if (alert == "SEQUENCE") {
    setSequenceState();
    Serial.println("STATE:SEQUENCE_VIOLATION");
  }
  else if (alert == "ACL") {
    setAclState();
    Serial.println("STATE:ACL_DENIED");
  }
  else if (alert == "TAMPER") {
    setTamperState();
    Serial.println("STATE:LOG_TAMPER_DETECTED");
  }
  else if (alert == "SHUTDOWN") {
    setShutdownState();
    Serial.println("STATE:FORCED_SHUTDOWN");
  }

  alertStartTime = millis();
  alertRunning = true;
}

void clearQueue() {
  queueStart = 0;
  queueEnd = 0;
}

void setup() {
  Serial.begin(9600);

  pinMode(GREEN_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(BLACK_LED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(RESET_BUTTON, INPUT_PULLUP);

  setNormalState();

  Serial.println("AegisOT demo ready");
  Serial.println("Commands: ALLOW, REPLAY, RATE, SEQUENCE, ACL, TAMPER, SHUTDOWN, RESET, STATUS");
}

void loop() {
  if (Serial.available()) {
    command = Serial.readStringUntil('\n');
    command.trim();
    command.toUpperCase();

    if (command == "ALLOW") {
      if (!alertRunning && queueIsEmpty()) {
        setNormalState();
        Serial.println("STATE:NORMAL");
      }
    }
    else if (command == "RESET") {
      clearQueue();
      alertRunning = false;
      setNormalState();
      Serial.println("STATE:RESET_OK");
    }
    else if (command == "STATUS") {
      int potValue = analogRead(POT_PIN);
      Serial.print("STATUS:");
      Serial.print(currentState);
      Serial.print(",POT=");
      Serial.println(potValue);
    }
    else if (isAlertCommand(command)) {
      enqueueAlert(command);
    }
  }

  if (!alertRunning && !queueIsEmpty()) {
    String nextAlert = dequeueAlert();
    startAlert(nextAlert);
  }

  if (alertRunning && millis() - alertStartTime >= ALERT_DURATION) {
    clearAlerts();
    alertRunning = false;

    if (queueIsEmpty()) {
      setNormalState();
      Serial.println("STATE:NORMAL");
    }
  }

  bool currentButtonState = digitalRead(RESET_BUTTON);

  if (lastButtonState == HIGH && currentButtonState == LOW) {
    delay(30);
    if (digitalRead(RESET_BUTTON) == LOW) {
      clearQueue();
      alertRunning = false;
      setNormalState();
      Serial.println("STATE:MANUAL_RESET");
    }
  }

  lastButtonState = currentButtonState;

  delay(20);
}

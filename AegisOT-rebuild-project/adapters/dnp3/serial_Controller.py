import time

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    serial = None
    SERIAL_AVAILABLE = False


def command_from_gateway_response(resp):
    if resp.get("allowed") is True:
        return "ALLOW"

    reason = resp.get("reason", "").lower()

    if "replay" in reason:
        return "REPLAY"
    if "rate" in reason:
        return "RATE"
    if "sequence" in reason:
        return "SEQUENCE"
    if "acl" in reason:
        return "ACL"
    if "tamper" in reason or "merkle" in reason or "broken" in reason:
        return "TAMPER"

    return "TAMPER"


class SerialController:
    def __init__(self, port="/dev/ttyACM1", baudrate=9600, enabled=False):
        self.port = port
        self.baudrate = baudrate
        self.enabled = enabled
        self.ser = None
        self.connected = False

    def connect(self):
        if not self.enabled:
            print("[ARDUINO] Disabled - mock mode")
            return True

        if not SERIAL_AVAILABLE:
            print("[ARDUINO] pyserial missing. Run: pip install pyserial")
            self.enabled = False
            return True

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)

            while self.ser.in_waiting:
                self.ser.readline()

            self.connected = True
            print(f"[ARDUINO] Connected on {self.port}")
            return True

        except Exception as e:
            print(f"[ARDUINO] Connection failed: {e}")
            print("[ARDUINO] Falling back to mock mode")
            self.enabled = False
            return True

    def send(self, command):
        command = command.strip().upper()

        if not self.enabled:
            print(f"[ARDUINO MOCK] → {command}")
            return True

        try:
            self.ser.write((command + "\n").encode())
            time.sleep(0.1)

            if self.ser.in_waiting:
                response = self.ser.readline().decode(errors="ignore").strip()
                print(f"[ARDUINO] ← {response}")
            else:
                print(f"[ARDUINO] → {command}")

            return True

        except Exception as e:
            print(f"[ARDUINO] Send failed: {e}")
            return False

    def close(self):
        if self.ser:
            self.send("RESET")
            self.ser.close()
            self.ser = None
            self.connected = False


if __name__ == "__main__":
    ctrl = SerialController(enabled=True)
    ctrl.connect()

    for cmd in ["ALLOW", "REPLAY", "RATE", "SEQUENCE", "ACL", "TAMPER", "RESET"]:
        print(f"Testing {cmd}")
        ctrl.send(cmd)
        time.sleep(2)

    ctrl.close()

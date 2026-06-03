import json
import subprocess
from serial_Controller import SerialController

# tail -n 0 means start from new lines only, so we do not replay old log entries
AUDIT_CMD = [
    "docker", "exec", "-i", "aegisot_gateway",
    "sh", "-c", "tail -n 0 -F /app/logs/audit.jsonl"
]

USE_ARDUINO = True
SERIAL_PORT = "/dev/ttyACM1"
BAUDRATE = 9600


def extract_decision(obj: dict):
    if isinstance(obj.get("entry"), dict):
        inner = obj["entry"]
        if isinstance(inner.get("decision"), dict):
            d = inner["decision"]
            return d.get("allowed"), d.get("reason", "")

    if isinstance(obj.get("decision"), dict):
        d = obj["decision"]
        return d.get("allowed"), d.get("reason", "")

    return None, None


def map_reason_to_command(allowed, reason):
    if allowed is True:
        return "ALLOW"

    reason = (reason or "").lower()

    if "replay" in reason:
        return "REPLAY"

    if "rate" in reason:
        return "RATE"

    if "sequence" in reason:
        return "SEQUENCE"

    if "acl" in reason:
        return "ACL"

    if "tamper" in reason or "merkle" in reason:
        return "TAMPER"

    if allowed is False:
        return "ACL"   # fallback

    return None


def main():
    ctrl = SerialController(
        port=SERIAL_PORT,
        baudrate=BAUDRATE,
        enabled=USE_ARDUINO
    )
    ctrl.connect()

    print("[INFO] Arduino bridge started")
    print("[INFO] Listening only for NEW gateway audit events...")

 # Start a subprocess that continuously watches the audit log
    proc = subprocess.Popen(
        AUDIT_CMD,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            allowed, reason = extract_decision(obj)
            if allowed is None:
                continue

            cmd = map_reason_to_command(allowed, reason)
            if not cmd:
                continue

            print(f"[AUDIT] allowed={allowed}, reason={reason} -> {cmd}")
            ctrl.send(cmd)

    except KeyboardInterrupt:
        print("\n[INFO] Stopping bridge...")

    finally:
        ctrl.close()
        proc.terminate()


if __name__ == "__main__":
    main()

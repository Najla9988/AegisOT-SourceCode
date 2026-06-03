import argparse
import requests
import time
import statistics

import sys
sys.path.append("adapters/dnp3")

from serial_Controller import SerialController, command_from_gateway_response

def parse_args():
    p = argparse.ArgumentParser(description="AegisOT mixed legitimate + attack validation suite")
    p.add_argument("--gateway", default="http://localhost:8000", help="Gateway base URL")
    p.add_argument("--lightsim", default="http://localhost:8001", help="LightSim base URL")
    p.add_argument("--sleep", type=float, default=0.05, help="Delay between requests in seconds")
    return p.parse_args()


class MixedSuite:
    def __init__(self, gateway, lightsim, delay=0.05):
        self.gateway = gateway.rstrip("/")
        self.lightsim = lightsim.rstrip("/")
        self.delay = delay
        self.results = []
        self.seqs = {}
        self.seq_base = int(time.time() * 1000) % 9000000 + 1000000

        self.arduino = SerialController(enabled=True)
        self.arduino.connect()

    def next_seq(self, key):
        self.seqs[key] = self.seqs.get(key, self.seq_base) + 1
        return self.seqs[key]

    def lset(self, point, value):
        try:
            requests.post(f"{self.lightsim}/set", json={"point": point, "value": value}, timeout=5)
        except Exception:
            pass

    def validate(self, source, protocol, point, operation, sequence=None, payload="", timestamp=None):
        seq = sequence if sequence is not None else self.next_seq(f"{source}:{point}:{operation}")
        ts = timestamp if timestamp is not None else int(time.time() * 1000)

        t0 = time.perf_counter()
        r = requests.post(
            f"{self.gateway}/validate",
            json={
                "source": source,
                "protocol": protocol,
                "point": point,
                "operation": operation,
                "sequence": seq,
                "payload": str(payload),
                "timestamp": ts,
            },
            timeout=5,
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        body = r.json()
        body["latency_ms"] = body.get("latency_ms", round(latency_ms, 3))
        return body, latency_ms

    def record(self, section, label, resp, latency_ms, expected_allowed=None, expected_reason_contains=None):
        allowed = resp.get("allowed")
        reason = resp.get("reason", "")
        ok = True

        if expected_allowed is not None:
            ok = allowed == expected_allowed
        if expected_reason_contains:
            ok = ok and expected_reason_contains.lower() in reason.lower()

        mark = "✓" if ok else "✗"
        status = "PASS" if ok else "FAIL"

        print(f"  {mark} {status:4s} [{label}] allowed={allowed} reason={reason} latency={latency_ms:.3f}ms")

        arduino_cmd = command_from_gateway_response(resp)
        self.arduino.send(arduino_cmd)

        self.results.append({
            "section": section,
            "label": label,
            "allowed": allowed,
            "reason": reason,
            "latency_ms": latency_ms,
            "ok": ok,
            "expected_allowed": expected_allowed,
        })

        time.sleep(self.delay)

    def section(self, title):
        print(f"\n{title}\n" + "-" * 60)

    def run_legitimate(self):
        self.section("Legitimate traffic")

        cases = [
            ("monitoring_agent", "opcua", "analog_input_1", "read", ""),
            ("monitoring_agent", "opcua", "breaker_status_1", "read", ""),
            ("scada_hmi", "opcua", "valve_position_1", "write", 35.0),
            ("scada_master", "dnp3", "breaker_status_5", "operate", True),
            ("scada_master", "dnp3", "analog_output_1", "write", 68.0),
            ("dnp3_master", "dnp3", "analog_input_1", "read", ""),
        ]

        for src, proto, point, op, payload in cases:
            if op in ("write", "operate") and payload != "":
                self.lset(point, payload)

            resp, lat = self.validate(src, proto, point, op, payload=payload)
            self.record("legitimate", f"{src} {op} {point}", resp, lat, True)

    def run_acl(self):
        self.section("False/attack traffic - ACL")

        cases = [
            ("attacker_vm", "opcua", "breaker_status_1", "write", True),
            ("monitoring_agent", "opcua", "analog_input_1", "write", 1.0),
        ]

        for src, proto, point, op, payload in cases:
            resp, lat = self.validate(src, proto, point, op, payload=payload)
            self.record("attack", f"{src} {op} {point}", resp, lat, False, "acl")

    def run_sequence(self):
        self.section("False/attack traffic - Sequence rollback")

        high = self.seq_base + 5000
        low = self.seq_base + 50

        self.validate("scada_hmi", "opcua", "analog_input_2", "read", sequence=high)
        resp, lat = self.validate("scada_hmi", "opcua", "analog_input_2", "read", sequence=low)

        self.record("attack", "sequence rollback", resp, lat, False, "sequence")

    def run_replay(self):
        self.section("False/attack traffic - Replay")

        ts = int(time.time() * 1000)
        seq = self.next_seq("replay:test")

        resp1, lat1 = self.validate("scada_hmi", "opcua", "breaker_status_1", "read", sequence=seq, timestamp=ts)
        self.record("legitimate", "fresh request before replay", resp1, lat1, True)

        resp2, lat2 = self.validate("scada_hmi", "opcua", "breaker_status_1", "read", sequence=seq, timestamp=ts)
        self.record("attack", "replayed identical request", resp2, lat2, False, "replay")

    def summary(self):
        all_lat = [r["latency_ms"] for r in self.results]
        checks = [r for r in self.results if r["expected_allowed"] is not None]
        passed = sum(1 for r in checks if r["ok"])

        print("\n" + "=" * 70)
        print("Mixed Validation Suite Summary")
        print("=" * 70)
        print(f"Checked scenarios : {len(checks)}")
        print(f"Passed checks     : {passed}/{len(checks)}")

        if all_lat:
            print(f"Overall avg       : {statistics.mean(all_lat):.2f}ms")
            print(f"Min / Max         : {min(all_lat):.2f}ms / {max(all_lat):.2f}ms")

        print("=" * 70)


def main():
    args = parse_args()
    suite = MixedSuite(args.gateway, args.lightsim, args.sleep)

    print("\n" + "=" * 70)
    print("AegisOT Mostly Legitimate + Few False Attacks")
    print(f"Gateway : {suite.gateway}")
    print(f"LightSim: {suite.lightsim}")
    print(f"Seq base: {suite.seq_base}")
    print("=" * 70)

    suite.run_legitimate()
    suite.run_acl()
    suite.run_legitimate()
    suite.run_sequence()
    suite.run_legitimate()
    suite.run_replay()

    suite.summary()


if __name__ == "__main__":
    main()

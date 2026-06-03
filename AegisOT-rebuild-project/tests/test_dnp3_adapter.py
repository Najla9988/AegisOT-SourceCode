#!/usr/bin/env python3
"""
Quick test to verify DNP3 adapter integration with the gateway
Run this after: docker-compose up -d
"""

import requests
import time

GATEWAY = "[localhost](http://localhost:8000)"
LIGHTSIM = "[localhost](http://localhost:8001)"

def test_gateway_health():
    print("\n[TEST 1] Gateway Health Check")
    try:
        r = requests.get(f"{GATEWAY}/health", timeout=5)
        print(f"  Status: {r.json()}")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

def test_lightsim_state():
    print("\n[TEST 2] LightSim State")
    try:
        r = requests.get(f"{LIGHTSIM}/state", timeout=5)
        print(f"  State: {r.json()}")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

def test_valid_command():
    print("\n[TEST 3] Valid DNP3 Command")
    cmd = {
        "source": "scada_master_1",
        "protocol": "dnp3",
        "point": "pump_1_startstop",
        "operation": "operate",
        "sequence": int(time.time()),
        "payload": "",
        "timestamp": int(time.time())
    }
    try:
        r = requests.post(f"{GATEWAY}/validate", json=cmd, timeout=5)
        result = r.json()
        print(f"  Result: {result}")
        return result.get("allowed", False)
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

def main():
    print("="*50)
    print("DNP3 Adapter Integration Test")
    print("="*50)
    
    results = []
    results.append(("Gateway Health", test_gateway_health()))
    results.append(("LightSim State", test_lightsim_state()))
    results.append(("Valid Command", test_valid_command()))
    
    print("\n" + "="*50)
    print("RESULTS")
    print("="*50)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")

if __name__ == "__main__":
    main()

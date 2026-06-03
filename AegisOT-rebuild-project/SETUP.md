# AegisOT — Setup & Run Guide
# Ubuntu 22.04 Lab VM

## 1. Prerequisites

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git curl
sudo usermod -aG docker $USER   # log out and back in after this
```

## 2. Project Layout

```
aegisot/
├── gateway/
│   ├── gateway.py               # FastAPI core validation engine
│   ├── merkle_logger.py         # Merkle-chained audit logger
│   ├── lightsim.py              # Simulated device state
│   ├── Dockerfile.gateway
│   └── requirements.gateway.txt
├── adapters/
│   ├── opcua_adapter.py         # OPC UA northbound adapter
│   ├── dnp3_adapter.py          # DNP3 southbound adapter
│   ├── Dockerfile.adapters
│   └── requirements.adapters.txt
├── config/
│   ├── config.yaml              # Gateway & service config
│   └── acl.yaml                 # Per-point ACL rules
├── monitoring/
│   └── prometheus.yml
├── tests/
│   ├── test_attacks.py          # Full test suite (HTTP)
│   └── scapy_attacks.py         # Raw packet attacks (Kali VM)
└── docker-compose.yml
```

## 3. Build and Start

```bash
cd aegisot/
docker compose build        # first time only (~3 min)
docker compose up -d        # start all services
docker compose ps           # verify all containers are Up
```

## 4. Verify Services Are Running

```bash
# Gateway health check
curl http://localhost:8000/health

# Expected output:
# {"status":"ok","redis":"connected","merkle_root":"<64-char-hex>"}

# Prometheus metrics
curl http://localhost:8000/metrics | grep gateway_

# Grafana dashboard
# Open browser: http://localhost:3000  (user: admin / pass: aegisot2025)
```

## 5. Run the Test Suite (from Lab VM)

```bash
cd tests/
pip install requests
python test_attacks.py --gateway http://localhost:8000
```

Expected output:
```
TEST 1 — Legitimate Baseline (all should ALLOW)
  ✅ PASS  [HMI read breaker_status_1]
  ✅ PASS  [HMI read analog_input_1]
  ...

TEST 2 — Replay Attack
  ✅ PASS  [First send (fresh)]
  ✅ PASS  [Replay of identical payload]
  ...

RESULTS: 15/15 passed  |  0 failed
```

## 6. Run Scapy Raw Packet Attacks (from Kali Attacker VM)

On the Kali VM, join the same Docker subnet (or host-only adapter):

```bash
sudo apt install -y python3-scapy
sudo python3 scapy_attacks.py --target 192.168.50.40 --opcua 192.168.50.30
```

Then check gateway logs on the Lab VM:
```bash
docker logs aegisot_gateway --follow
```

## 7. Watch Attacks in Real Time (Grafana)

- Open: http://localhost:3000
- Dashboard → AegisOT Security Overview
- Run test_attacks.py or scapy_attacks.py — watch spikes in:
  - `gateway_commands_blocked_total{reason="replay"}`
  - `gateway_commands_blocked_total{reason="acl"}`
  - `gateway_commands_blocked_total{reason="rate_limit"}`
  - `gateway_validation_latency_seconds` (should stay < 5ms)

## 8. View Audit Logs (Merkle Chain)

```bash
docker exec aegisot_gateway cat /app/logs/audit.jsonl | python3 -m json.tool | head -80
```

Each line is a chained record:
```json
{
  "index": 0,
  "prev_hash": "0000...0000",
  "hash": "a3f7...e912",
  "entry": { "source": "scada_hmi", "decision": {"allowed": true}, ... }
}
```

## 9. Latency Measurement

```bash
# Collect 50 validation responses and print latency stats
python3 - <<'EOF'
import requests, statistics, time
times = []
for i in range(50):
    r = requests.post("http://localhost:8000/validate", json={
        "source": "scada_hmi", "protocol": "opcua",
        "point": "analog_input_1", "operation": "read",
        "sequence": i+300, "payload": "", "timestamp": time.time()
    })
    times.append(r.json().get("latency_ms", 0))
print(f"avg={statistics.mean(times):.2f}ms  max={max(times):.2f}ms  min={min(times):.2f}ms")
EOF
```

## 10. Teardown

```bash
docker compose down          # stop containers, keep volumes
docker compose down -v       # stop and delete all volumes (clean slate)
```

## Troubleshooting

| Problem | Solution |
|---|---|
| `gateway` stuck in "starting" | Wait 15s for Redis healthcheck to pass |
| `pydnp3` build fails | Needs `libboost-all-dev` in the adapter Dockerfile — already included |
| Port already in use | `sudo lsof -i :8000` then kill the process |
| Redis connection refused | `docker compose restart redis` |
| OPC UA port 4840 blocked | Check firewall: `sudo ufw allow 4840` |

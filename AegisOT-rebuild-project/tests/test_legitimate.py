import requests, time, statistics

GATEWAY  = "http://localhost:8000"
LIGHTSIM = "http://localhost:8001"
results  = []

def log(label, resp, latency):
    allowed = resp.get("allowed", False)
    reason  = resp.get("reason", "?")
    status  = "PASS" if allowed else "FAIL"
    print(f"  [{status}] {label:<48} allowed={allowed}  reason={reason}  latency={latency:.1f}ms")
    results.append({"allowed": allowed, "reason": reason, "latency": latency})

def gw(source, protocol, point, operation, seq, payload=""):
    t0 = time.time()
    r  = requests.post(f"{GATEWAY}/validate", json={
        "source": source, "protocol": protocol, "point": point,
        "operation": operation, "sequence": seq,
        "payload": str(payload), "timestamp": int(time.time() * 1000)
    }, timeout=5)
    return r.json(), (time.time() - t0) * 1000

def lset(point, value):
    requests.post(f"{LIGHTSIM}/set", json={"point": point, "value": value}, timeout=5)

print("\n" + "="*68)
print("  AegisOT — Legitimate End-to-End Traffic Test")
print("="*68)

# 1 — OPC UA reads via monitoring_agent
print("\n[1] OPC UA reads — monitoring agent (read-only observer)")
for i, pt in enumerate(["analog_input_1","analog_input_2","breaker_status_1",
                         "breaker_status_2","valve_position_1"]):
    resp, lat = gw("monitoring_agent","opcua", pt, "read", 200+i)
    log(f"OPC UA read  {pt}", resp, lat)
    time.sleep(0.1)

# 2 — OPC UA reads + write via scada_hmi
print("\n[2] OPC UA — SCADA HMI operator")
hmi_cmds = [
    ("breaker_status_1","read",""),
    ("analog_input_1",  "read",""),
    ("analog_input_2",  "read",""),
    ("temperature_sensor_1","read",""),
    ("valve_position_1","read",""),
    ("valve_position_1","write",35.0),
]
for i,(pt,op,val) in enumerate(hmi_cmds):
    if op == "write": lset(pt, val)
    resp, lat = gw("scada_hmi","opcua", pt, op, 300+i, val)
    log(f"OPC UA {op:<6} {pt}", resp, lat)
    time.sleep(0.1)

# 3 — DNP3 reads via scada_master
print("\n[3] DNP3 reads — SCADA master southbound")
for i, pt in enumerate(["breaker_status_5","analog_output_1",
                         "analog_output_2","digital_output_1"]):
    resp, lat = gw("scada_master","dnp3", pt, "read", 400+i)
    log(f"DNP3  read   {pt}", resp, lat)
    time.sleep(0.1)

# 4 — DNP3 operates + writes via scada_master
print("\n[4] DNP3 control — SCADA master field operations")
dnp3_ops = [
    ("breaker_status_5","operate",True),
    ("analog_output_1", "write",  68.0),
    ("analog_output_2", "write",  91.5),
    ("digital_output_1","operate",False),
]
for i,(pt,op,val) in enumerate(dnp3_ops):
    lset(pt, val)
    resp, lat = gw("scada_master","dnp3", pt, op, 500+i, val)
    log(f"DNP3  {op:<8} {pt} = {val}", resp, lat)
    time.sleep(0.15)

# 5 — DNP3 reads+operates via dnp3_master
print("\n[5] DNP3 field polling — dnp3_master (wildcard access)")
for i, pt in enumerate(["breaker_status_1","breaker_status_2","breaker_status_3",
                         "analog_input_1","analog_input_2"]):
    resp, lat = gw("dnp3_master","dnp3", pt, "read", 600+i)
    log(f"DNP3  read   {pt}", resp, lat)
    time.sleep(0.1)
for i, pt in enumerate(["breaker_status_1","breaker_status_2","breaker_status_3"]):
    lset(pt, i % 2 == 0)
    resp, lat = gw("dnp3_master","dnp3", pt, "operate", 700+i, i%2==0)
    log(f"DNP3  operate {pt}", resp, lat)
    time.sleep(0.15)

# 6 — Mixed realistic polling cycle
print("\n[6] Realistic mixed SCADA polling cycle")
cycle = [
    ("monitoring_agent","opcua","analog_input_1",     "read",   900, ""),
    ("monitoring_agent","opcua","analog_input_2",     "read",   901, ""),
    ("monitoring_agent","opcua","breaker_status_1",   "read",   902, ""),
    ("monitoring_agent","opcua","breaker_status_2",   "read",   903, ""),
    ("monitoring_agent","opcua","temperature_sensor_1","read",  904, ""),
    ("scada_hmi",       "opcua","analog_input_1",     "read",   910, ""),
    ("scada_hmi",       "opcua","breaker_status_1",   "read",   911, ""),
    ("scada_hmi",       "opcua","valve_position_1",   "write",  912, 55.0),
    ("scada_master",    "dnp3", "breaker_status_5",   "operate",920, True),
    ("scada_master",    "dnp3", "analog_output_1",    "write",  921, 77.0),
    ("dnp3_master",     "dnp3", "breaker_status_1",   "read",   930, ""),
    ("dnp3_master",     "dnp3", "analog_input_1",     "read",   931, ""),
    ("dnp3_master",     "dnp3", "breaker_status_2",   "operate",932, True),
]
for src,proto,pt,op,seq,val in cycle:
    if op in ("write","operate") and val != "": lset(pt, val)
    resp, lat = gw(src, proto, pt, op, seq, val)
    log(f"{proto.upper():<5} {op:<8} {pt}", resp, lat)
    time.sleep(0.05)

# Summary
print("\n" + "="*68)
total     = len(results)
passed    = sum(1 for r in results if r["allowed"])
latencies = [r["latency"] for r in results]
print(f"  Total commands : {total}")
print(f"  Allowed (PASS) : {passed}  ({100*passed//total}%)")
print(f"  Blocked (FAIL) : {total-passed}")
print(f"  Avg latency    : {statistics.mean(latencies):.2f}ms")
print(f"  Min latency    : {min(latencies):.2f}ms")
print(f"  Max latency    : {max(latencies):.2f}ms")
print(f"  Stdev          : {statistics.stdev(latencies):.2f}ms")
print("\n  Final LightSim device state:")
for k,v in requests.get(f"{LIGHTSIM}/state",timeout=5).json().items():
    print(f"    {k:<30} = {v}")
print("="*68 + "\n")

"""
AegisOT - DNP3 Adapter (Pure Python simulation — no pydnp3 required)
Simulates a DNP3 outstation over raw TCP.
All inbound control commands are validated via the gateway /validate endpoint.
Only approved commands update the simulated device state.
"""

import asyncio
import struct
import logging
import time
import requests
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aegisot.dnp3_adapter")

with open("/app/config/config.yaml") as f:
    CONFIG = yaml.safe_load(f)

GATEWAY_URL = f"http://{CONFIG['gateway']['host']}:{CONFIG['gateway']['port']}/validate"
DNP3_PORT   = CONFIG["dnp3"]["port"]
SOURCE_ID   = CONFIG["dnp3"]["source_id"]

# Simulated device state
DEVICE_STATE = {
    "breaker_status_5":  False,
    "analog_output_1":   0.0,
    "analog_output_2":   0.0,
    "digital_output_1":  False,
}

FC_NAMES = {
    0x01: "READ", 0x02: "WRITE", 0x03: "SELECT",
    0x04: "OPERATE", 0x05: "DIRECT_OPERATE", 0x81: "RESPONSE",
}

POINT_MAP = {
    0: "breaker_status_5",
    1: "analog_output_1",
    2: "analog_output_2",
    3: "digital_output_1",
}

_seq = {}

def _next_seq(point):
    _seq[point] = _seq.get(point, 0) + 1
    return _seq[point]

def _call_gateway(point, operation, value, source):
    seq = _next_seq(point)
    payload = {
        "source": source, "protocol": "dnp3",
        "point": point, "operation": operation,
        "sequence": seq, "payload": str(value),
        "timestamp": time.time(),
    }
    try:
        resp = requests.post(GATEWAY_URL, json=payload, timeout=2)
        result = resp.json()
        allowed = result.get("allowed", False)
        logger.info("Gateway: %s | src=%s point=%s op=%s latency=%sms",
                    "ALLOW" if allowed else "BLOCK",
                    source, point, operation, result.get("latency_ms", "?"))
        return allowed
    except Exception as e:
        logger.error("Gateway unreachable: %s — FAIL CLOSED", e)
        return False

def _parse_dnp3_frame(data):
    if len(data) < 10:
        return None
    try:
        if data[0] != 0x05 or data[1] != 0x64:
            return None
        app_start = 10
        if len(data) <= app_start + 1:
            return None
        app_ctrl  = data[app_start]
        seq_num   = app_ctrl & 0x0F
        func_code = data[app_start + 1] if len(data) > app_start + 1 else 0x01
        point_index = data[app_start + 4] if len(data) > app_start + 4 else 0
        value       = data[app_start + 6] if len(data) > app_start + 6 else 0
        return {
            "sequence": seq_num, "func_code": func_code,
            "func_name": FC_NAMES.get(func_code, f"FC_{func_code:#04x}"),
            "point_index": point_index, "value": value,
        }
    except Exception:
        return None

def _build_dnp3_response(allowed, sequence):
    app_ctrl  = 0xC0 | (sequence & 0x0F)
    iin2 = 0x00 if allowed else 0x04
    dl_header = b"\x05\x64" + struct.pack("<H", 7) + b"\x44\x05" + b"\x00\x00" + b"\x00\x00"
    return dl_header + bytes([0xC0]) + bytes([app_ctrl, 0x81, 0x00, iin2])

async def handle_client(reader, writer):
    peer = writer.get_extra_info("peername")
    source_ip = peer[0] if peer else "unknown"
    logger.info("DNP3 connection from %s", source_ip)
    try:
        while True:
            data = await asyncio.wait_for(reader.read(256), timeout=30)
            if not data:
                break
            frame = _parse_dnp3_frame(data)
            if frame is None:
                logger.warning("Malformed frame from %s — dropping", source_ip)
                continue
            fc        = frame["func_code"]
            point_name = POINT_MAP.get(frame["point_index"], f"point_{frame['point_index']}")
            val       = frame["value"]
            seq       = frame["sequence"]
            operation = "operate" if fc in (0x03,0x04,0x05) else ("write" if fc==0x02 else "read")
            logger.info("DNP3 %s from %s — point=%s val=%s seq=%d",
                        frame["func_name"], source_ip, point_name, val, seq)
            allowed = _call_gateway(point_name, operation, val, source_ip)
            if allowed and operation in ("operate", "write"):
                old = DEVICE_STATE.get(point_name)
                DEVICE_STATE[point_name] = bool(val) if isinstance(old, bool) else float(val)
                logger.info("State updated: %s = %s", point_name, DEVICE_STATE[point_name])
            writer.write(_build_dnp3_response(allowed, seq))
            await writer.drain()
    except asyncio.TimeoutError:
        logger.info("Client %s timed out", source_ip)
    except Exception as e:
        logger.error("Handler error: %s", e)
    finally:
        writer.close()

async def main():
    server = await asyncio.start_server(handle_client, "0.0.0.0", DNP3_PORT)
    logger.info("DNP3 adapter (pure Python) on port %d", DNP3_PORT)
    logger.info("Points: %s", list(POINT_MAP.values()))
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())

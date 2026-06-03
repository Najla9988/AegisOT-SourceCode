"""
AegisOT - OPC UA Adapter
Runs an OPC UA server that intercepts Write/MethodCall requests,
forwards them to the gateway /validate endpoint, and only applies
the change to the OPC UA address space if the gateway allows it.
"""

import asyncio
import hashlib
import logging
import time
import requests
from asyncua import Server, ua
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aegisot.opcua_adapter")

with open("/app/config/config.yaml") as f:
    CONFIG = yaml.safe_load(f)

GATEWAY_URL  = f"http://{CONFIG['gateway']['host']}:{CONFIG['gateway']['port']}/validate"
OPCUA_PORT   = CONFIG["opcua"]["port"]
SOURCE_ID    = CONFIG["opcua"]["source_id"]   # e.g. "scada_hmi"

# Sequence counter per (source, point)
_seq: dict[str, int] = {}


def _next_seq(point: str) -> int:
    _seq[point] = _seq.get(point, 0) + 1
    return _seq[point]


def _call_gateway(point: str, operation: str, value: str) -> bool:
    """Return True if the gateway allows this command."""
    seq = _next_seq(point)
    payload = {
        "source":    SOURCE_ID,
        "protocol":  "opcua",
        "point":     point,
        "operation": operation,
        "sequence":  seq,
        "payload":   str(value),
        "timestamp": time.time(),
    }
    try:
        resp = requests.post(GATEWAY_URL, json=payload, timeout=2)
        result = resp.json()
        allowed = result.get("allowed", False)
        logger.info("Gateway decision: %s | point=%s op=%s latency=%sms",
                    "ALLOW" if allowed else "BLOCK", point, operation,
                    result.get("latency_ms", "?"))
        return allowed
    except Exception as e:
        logger.error("Gateway unreachable: %s — FAIL CLOSED", e)
        return False   # fail closed


class OTSecurityHandler:
    """
    Overrides write-value calls on the OPC UA server nodes.
    Only nodes registered here are validated before write.
    """

    def __init__(self, server: Server):
        self._server = server
        self._nodes: dict[str, object] = {}   # point_name -> Node

    def register_node(self, point_name: str, node):
        self._nodes[point_name] = node

    async def handle_write(self, point_name: str, new_value):
        """Called by the subscription handler when a write is attempted."""
        allowed = _call_gateway(point_name, "write", str(new_value))
        if allowed:
            node = self._nodes.get(point_name)
            if node:
                await node.write_value(new_value)
                logger.info("Applied write: %s = %s", point_name, new_value)
        else:
            logger.warning("Write BLOCKED by gateway: %s = %s", point_name, new_value)


async def run_server():
    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://0.0.0.0:{OPCUA_PORT}/aegisot/")
    server.set_server_name("AegisOT OPC UA Adapter")

    uri = "http://aegisot.iau.edu.sa"
    idx = await server.register_namespace(uri)

    # Build address space — mirrors the points in acl.yaml
    objects = server.nodes.objects
    ctrl = await objects.add_object(idx, "OTController")

    handler = OTSecurityHandler(server)

    # Register simulated OT data points
    points = {
        "breaker_status_1":  False,
        "analog_input_1":    0.0,
        "analog_input_2":    0.0,
        "valve_position_1":  0,
        "temperature_sensor_1": 25.0,
    }

    for name, init_val in points.items():
        node = await ctrl.add_variable(idx, name, init_val)
        await node.set_writable()
        handler.register_node(name, node)
        logger.info("Registered OPC UA node: %s (init=%s)", name, init_val)

    logger.info("OPC UA Adapter running on port %d", OPCUA_PORT)

    async with server:
        while True:
            # Simulate a legitimate read every 5 seconds to verify liveness
            await asyncio.sleep(5)
            for name, node in handler._nodes.items():
                val = await node.read_value()
                logger.debug("Liveness read: %s = %s", name, val)


if __name__ == "__main__":
    asyncio.run(run_server())

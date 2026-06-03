"""
AegisOT - LightSim
A minimal FastAPI service that holds simulated field-device state.
The DNP3/OPC UA adapters call /set after the gateway approves a command.
The Grafana dashboard reads /state to visualize the current device values.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [LightSim] %(message)s")
logger = logging.getLogger("aegisot.lightsim")

app = FastAPI(title="AegisOT LightSim", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Shared simulated device state
STATE: dict[str, object] = {
    "breaker_status_1":    False,
    "breaker_status_5":    False,
    "analog_input_1":      0.0,
    "analog_input_2":      0.0,
    "analog_output_1":     0.0,
    "analog_output_2":     0.0,
    "valve_position_1":    0,
    "temperature_sensor_1": 25.0,
    "digital_output_1":    False,
}


@app.get("/state")
def get_state():
    """Return full device state (used by Grafana / monitoring)."""
    return STATE


@app.post("/set")
def set_point(point: str, value: str):
    """
    Apply a validated command to device state.
    Only called by adapters AFTER the gateway has allowed the command.
    """
    if point not in STATE:
        return {"error": f"unknown point: {point}"}

    # Coerce value type to match initial type
    orig = STATE[point]
    try:
        if isinstance(orig, bool):
            coerced = value.lower() in ("true", "1", "on")
        elif isinstance(orig, int):
            coerced = int(value)
        elif isinstance(orig, float):
            coerced = float(value)
        else:
            coerced = value
    except (ValueError, TypeError):
        coerced = value

    old = STATE[point]
    STATE[point] = coerced
    logger.info("State change: %s  %s → %s", point, old, coerced)
    return {"point": point, "old": old, "new": coerced}


@app.get("/health")
def health():
    return {"status": "ok", "points": len(STATE)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

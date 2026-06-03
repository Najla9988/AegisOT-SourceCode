# adapters/lightsim/app.py

from fastapi import FastAPI
from datetime import datetime

app = FastAPI(title="LightSim Field Device Simulator")

# Simulated field device states
device_state = {
    "pump_1_startstop": "OFF",
    "breaker_status_1": "OFF", 
    "tank_level_1": 50.0,
    "voltage_reading_1": 120.0,
}

history = []


@app.get("/state")
def get_state():
    """GET /state - Returns current state of all simulated devices"""
    return {
        "devices": device_state,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/state/{point}")
def get_point_state(point: str):
    """GET /state/{point} - Returns state of a specific point"""
    if point not in device_state:
        return {"error": f"Unknown point: {point}"}, 404
    return {
        "point": point,
        "value": device_state[point],
        "timestamp": datetime.now().isoformat()
    }


@app.post("/set")
def set_state(data: dict):
    """POST /set - Sets device state (called by adapters after gateway approval)"""
    point = data.get("point", "pump_1_startstop")
    value = data.get("value", "OFF")
    
    old_value = device_state.get(point, "UNKNOWN")
    device_state[point] = value
    
    event = {
        "point": point,
        "old_value": old_value,
        "new_value": value,
        "timestamp": datetime.now().isoformat()
    }
    history.append(event)
    
    print(f"[LIGHTSIM] {point}: {old_value} → {value}")
    
    return {
        "status": "ok",
        "point": point,
        "old_value": old_value,
        "new_value": value
    }


@app.get("/history")
def get_history():
    """GET /history - Returns recent state changes"""
    return {"history": history[-20:]}  # Last 20 events


@app.post("/reset")
def reset_state():
    """POST /reset - Resets all devices to default state"""
    device_state.update({
        "pump_1_startstop": "OFF",
        "breaker_status_1": "OFF",
        "tank_level_1": 50.0,
        "voltage_reading_1": 120.0,
    })
    history.clear()
    print("[LIGHTSIM] All devices reset to default")
    return {"status": "reset_complete"}

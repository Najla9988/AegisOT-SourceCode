"""
AegisOT - Unified OT Security Gateway Core
FastAPI-based validation engine with ACL, replay, sequence, rate-limit,
Prometheus metrics, audit logging, and Merkle chain status.
"""

import hashlib
import json
import time
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import redis
import yaml
from prometheus_client import Counter, Histogram, generate_latest

from merkle_logger import MerkleAuditLogger


# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aegisot.gateway")


# ---------------- Load config ----------------
with open("/app/config/config.yaml") as f:
    CONFIG = yaml.safe_load(f)

with open("/app/config/acl.yaml") as f:
    ACL_RULES = yaml.safe_load(f)["acl"]


# ---------------- Redis connection ----------------
redis_client = redis.Redis(
    host=CONFIG["redis"]["host"],
    port=CONFIG["redis"]["port"],
    db=0,
    decode_responses=True,
)


# ---------------- Prometheus metrics ----------------
COMMANDS_ALLOWED = Counter(
    "gateway_commands_allowed_total",
    "Commands allowed"
)

COMMANDS_BLOCKED = Counter(
    "gateway_commands_blocked_total",
    "Commands blocked",
    ["reason"]
)

VALIDATION_LATENCY = Histogram(
    "gateway_validation_latency_seconds",
    "Validation latency"
)


# ---------------- Merkle audit logger ----------------
audit = MerkleAuditLogger()


# ---------------- FastAPI app ----------------
app = FastAPI(title="AegisOT Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- Request model ----------------
class CommandRequest(BaseModel):
    source: str
    protocol: str
    point: str
    operation: str
    sequence: int
    payload: Optional[str] = ""
    timestamp: Optional[float] = None


# ---------------- Helpers ----------------
def _hash_payload(source: str, point: str, operation: str, payload: str) -> str:
    raw = f"{source}:{point}:{operation}:{payload}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _check_acl(source: str, protocol: str, point: str, operation: str) -> bool:
    for rule in ACL_RULES:
        if (
            rule.get("source") in (source, "*")
            and rule.get("protocol") in (protocol, "*")
            and (rule.get("point", rule.get("points", "")) in (point, "*"))
            and operation in rule.get("operations", [])
        ):
            return True
    return False


def _check_replay(source: str, payload_hash: str, point: str, sequence: int) -> bool:
    """
    Return True if blocked because this command was replayed.
    """
    key = f"replay:{source}:{point}:{sequence}"
    ttl = CONFIG["security"]["replay_ttl_seconds"]

    if redis_client.exists(key):
        return True

    redis_client.setex(key, ttl, payload_hash)
    return False


def _check_sequence(source: str, point: str, sequence: int) -> bool:
    """
    Return True if blocked because sequence is not strictly increasing.
    """
    key = f"seq:{source}:{point}"
    last = redis_client.get(key)

    if last is not None and int(last) >= sequence:
        return True

    redis_client.set(key, sequence)
    return False


def _check_rate_limit(source: str) -> bool:
    """
    Return True if blocked because source exceeded allowed requests per minute.
    """
    key = f"rate:{source}"
    limit = CONFIG["security"]["rate_limit_per_minute"]

    count = redis_client.incr(key)

    if count == 1:
        redis_client.expire(key, 60)

    return count > limit


def verify_merkle_chain() -> bool:
    """
    Checks whether the audit chain is intact.
    It reads audit.jsonl and verifies that every prev_hash matches the previous entry hash.
    """
    try:
        with open("/app/logs/audit.jsonl", "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        prev = "0" * 64

        for line in lines:
            record = json.loads(line)

            if record.get("prev_hash") != prev:
                return False

            prev = record.get("hash", "")

        return True

    except FileNotFoundError:
        return True
    except Exception:
        return False


# ---------------- Validate endpoint ----------------
@app.post("/validate")
def validate(cmd: CommandRequest):
    start = time.perf_counter()

    cmd.timestamp = cmd.timestamp or time.time()
    payload_hash = _hash_payload(cmd.source, cmd.point, cmd.operation, cmd.payload)

    decision = {"allowed": False, "reason": "unknown"}

    # 1. ACL check
    if not _check_acl(cmd.source, cmd.protocol, cmd.point, cmd.operation):
        decision["reason"] = "acl_denied"
        COMMANDS_BLOCKED.labels(reason="acl").inc()
        logger.warning("BLOCK [ACL] src=%s point=%s op=%s", cmd.source, cmd.point, cmd.operation)

    # 2. Replay check
    elif _check_replay(cmd.source, payload_hash, cmd.point, cmd.sequence):
        decision["reason"] = "replay_detected"
        COMMANDS_BLOCKED.labels(reason="replay").inc()
        logger.warning("BLOCK [REPLAY] src=%s hash=%s", cmd.source, payload_hash[:16])

    # 3. Sequence check
    elif _check_sequence(cmd.source, cmd.point, cmd.sequence):
        decision["reason"] = "sequence_violation"
        COMMANDS_BLOCKED.labels(reason="sequence").inc()
        logger.warning("BLOCK [SEQ] src=%s point=%s seq=%d", cmd.source, cmd.point, cmd.sequence)

    # 4. Rate-limit check
    elif _check_rate_limit(cmd.source):
        decision["reason"] = "rate_limit_exceeded"
        COMMANDS_BLOCKED.labels(reason="rate_limit").inc()
        logger.warning("BLOCK [RATE] src=%s", cmd.source)

    # 5. Allow
    else:
        decision = {"allowed": True, "reason": "all_checks_passed"}
        COMMANDS_ALLOWED.inc()
        logger.info(
            "ALLOW src=%s proto=%s point=%s op=%s seq=%d",
            cmd.source,
            cmd.protocol,
            cmd.point,
            cmd.operation,
            cmd.sequence,
        )

    # Audit every decision
    audit.log({
        "ts": cmd.timestamp,
        "source": cmd.source,
        "protocol": cmd.protocol,
        "point": cmd.point,
        "operation": cmd.operation,
        "sequence": cmd.sequence,
        "hash": payload_hash,
        "decision": decision,
    })

    elapsed = time.perf_counter() - start
    VALIDATION_LATENCY.observe(elapsed)

    return {**decision, "latency_ms": round(elapsed * 1000, 3)}


# ---------------- Metrics endpoint ----------------
@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return generate_latest()


# ---------------- Health endpoint ----------------
@app.get("/health")
def health():
    try:
        redis_client.ping()

        merkle_ok = audit.verify()

        return {
            "status": "ok",
            "redis": "connected",
            "merkle_root": audit.root(),
            "merkle_status": "INTACT" if merkle_ok else "BROKEN"
        }

    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ---------------- Audit endpoint ----------------
@app.get("/audit")
def get_audit():
    try:
        with open("/app/logs/audit.jsonl", "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        entries = [json.loads(line) for line in lines]

        # Last 10 decisions only
        return entries[-10:]

    except FileNotFoundError:
        return []
    except Exception:
        return []


# ---------------- Optional tamper simulation endpoint ----------------
@app.post("/tamper")
def tamper_audit_log():
    """
    Demo endpoint: modifies the last audit entry to simulate tampering.
    This should make merkle_status become BROKEN.
    """
    try:
        with open("/app/logs/audit.jsonl", "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        if not lines:
            return {"status": "no audit records to tamper"}

        last = json.loads(lines[-1])
        last["entry"]["decision"]["reason"] = "tampered_log"

        lines[-1] = json.dumps(last)

        with open("/app/logs/audit.jsonl", "w") as f:
            for line in lines:
                f.write(line + "\n")

        return {"status": "tampered", "message": "Audit log was modified. Merkle chain should now be BROKEN."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

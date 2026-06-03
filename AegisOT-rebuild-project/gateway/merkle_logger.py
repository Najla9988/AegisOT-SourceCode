"""
AegisOT - Merkle-Chained Audit Logger
Every gateway decision is hashed and chained so any tampering is detectable.
"""

import hashlib
import json
import os
import threading


class MerkleAuditLogger:
    def __init__(self, log_file: str = "/app/logs/audit.jsonl"):
        self._chain: list[dict] = []
        self._prev_hash = "0" * 64
        self._lock = threading.Lock()
        self._log_file = log_file
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        self._load_existing_chain()

    def _load_existing_chain(self):
        if not os.path.exists(self._log_file):
            return

        try:
            with open(self._log_file, "r") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]

            for line in lines:
                record = json.loads(line)
                self._chain.append(record)

            if self._chain:
                self._prev_hash = self._chain[-1].get("hash", "0" * 64)

        except Exception:
            self._chain = []
            self._prev_hash = "0" * 64

    def log(self, entry: dict) -> str:
        with self._lock:
            entry_json = json.dumps(entry, separators=(",", ":"), sort_keys=True)
            leaf_hash = self._compute_hash(self._prev_hash, entry_json)

            record = {
                "prev_hash": self._prev_hash,
                "hash": leaf_hash,
                "entry": entry,
            }

            self._chain.append(record)

            with open(self._log_file, "a") as f:
                f.write(json.dumps(record) + "\n")

            self._prev_hash = leaf_hash
            return leaf_hash

    def root(self) -> str:
        return self._prev_hash

    def verify(self) -> bool:
        return self.verify_file()

    def verify_file(self) -> bool:
        prev = "0" * 64

        if not os.path.exists(self._log_file):
            return True

        try:
            with open(self._log_file, "r") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]

            for line in lines:
                record = json.loads(line)
                entry_json = json.dumps(
                    record["entry"],
                    separators=(",", ":"),
                    sort_keys=True
                )

                expected_hash = self._compute_hash(prev, entry_json)

                if record.get("prev_hash") != prev:
                    return False

                if record.get("hash") != expected_hash:
                    return False

                prev = record["hash"]

            return True

        except Exception:
            return False

    def entries(self) -> list[dict]:
        with self._lock:
            return list(self._chain)

    @staticmethod
    def _compute_hash(prev_hash: str, data: str) -> str:
        raw = f"{prev_hash}{data}".encode()
        return hashlib.sha256(raw).hexdigest()

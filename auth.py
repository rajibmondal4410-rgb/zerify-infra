import uuid
import hashlib
from datetime import datetime
from typing import Optional
from fastapi import Header, HTTPException

# Permanent hardcoded demo key — never changes on restart
DEMO_KEY = "zfy_sk_zerify_demo_permanent_2026"

API_KEYS: dict = {
    DEMO_KEY: {
        "name": "demo",
        "created": "2026-01-01",
        "calls": 0,
        "verifications": []
    }
}

def generate_api_key(name: str = "default") -> str:
    raw = f"{uuid.uuid4()}{name}"
    key = "zfy_sk_" + hashlib.sha256(raw.encode()).hexdigest()[:24]
    API_KEYS[key] = {
        "name": name,
        "created": datetime.utcnow().isoformat(),
        "calls": 0,
        "verifications": []
    }
    return key

def validate_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    # No key provided — allow demo key automatically
    if x_api_key is None:
        API_KEYS[DEMO_KEY]["calls"] += 1
        return DEMO_KEY
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    API_KEYS[x_api_key]["calls"] += 1
    return x_api_key

def get_key_stats(key: str) -> dict:
    return API_KEYS.get(key, {"name": "unknown", "calls": 0, "verifications": []})

def record_verification(key: str, record: dict):
    if key in API_KEYS:
        API_KEYS[key]["verifications"].append(record)
        if len(API_KEYS[key]["verifications"]) > 100:
            API_KEYS[key]["verifications"] = API_KEYS[key]["verifications"][-100:]

def get_all_verifications() -> list:
    all_v = []
    for key, data in API_KEYS.items():
        all_v.extend(data.get("verifications", []))
    return sorted(all_v, key=lambda x: x.get("timestamp", ""), reverse=True)[:200]
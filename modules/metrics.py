import json
import os

METRICS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "metrics.json")

_data = {
    "rate_limit_hits": 0,
    "gemini_calls": 0,
    "fallbacks_used": 0,
}

def _ensure_dir():
    d = os.path.dirname(METRICS_FILE)
    os.makedirs(d, exist_ok=True)

def inc_rate_limit():
    _data["rate_limit_hits"] += 1
    _persist()

def inc_call():
    _data["gemini_calls"] += 1
    _persist()

def inc_fallback():
    _data["fallbacks_used"] += 1
    _persist()

def _persist():
    _ensure_dir()
    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(_data, f, indent=2)

def export_metrics(path: str | None = None):
    if path is None:
        path = METRICS_FILE
    _persist()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

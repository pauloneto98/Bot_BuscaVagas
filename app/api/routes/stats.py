"""
Stats & Dashboard Routes — /api/stats, /api/jobs
Provides aggregated metrics and application history.
"""

import json
import os
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends

from app.config import settings
from app.api.dependencies import verify_token
from app.db.repositories import ApplicationRepository

router = APIRouter()


@router.get("/api/stats", dependencies=[Depends(verify_token)])
def get_stats():
    candidaturas = ApplicationRepository.get_all()

    total = len(candidaturas)
    enviados = sum(1 for c in candidaturas if c.get("email_enviado"))
    hoje = datetime.now().strftime("%Y-%m-%d")
    hoje_count = sum(1 for c in candidaturas if str(c.get("data", "")).startswith(hoje))

    # Per-day counts for chart (last 30 days)
    day_counts = Counter()
    for c in candidaturas:
        d = c.get("data", "")[:10]
        if d:
            day_counts[d] += 1
    sorted_days = sorted(day_counts.items())[-30:]

    # Top companies
    emp_counts: dict[str, int] = {}
    for c in candidaturas:
        emp = c.get("empresa", "Desconhecida")
        emp_counts[emp] = emp_counts.get(emp, 0) + 1
    top_empresas = sorted(emp_counts.items(), key=lambda x: -x[1])[:10]

    # Source breakdown
    source_counts: dict[str, int] = {}
    for c in candidaturas:
        note = c.get("notas", "")
        if "JSON" in note or "manual" in note.lower():
            src = "Manual"
        elif "teste" in note.lower():
            src = "Teste"
        else:
            src = "Automatico"
        source_counts[src] = source_counts.get(src, 0) + 1

    # Metrics
    metrics = {"rate_limit_hits": 0, "gemini_calls": 0, "fallbacks_used": 0}
    if os.path.exists(settings.METRICS_FILE):
        try:
            with open(settings.METRICS_FILE, "r", encoding="utf-8") as f:
                metrics = json.load(f)
        except Exception:
            pass

    return {
        "total": total,
        "emails_enviados": enviados,
        "sem_email": total - enviados,
        "hoje": hoje_count,
        "chart_days": {
            "labels": [d[0] for d in sorted_days],
            "values": [d[1] for d in sorted_days],
        },
        "top_empresas": {
            "labels": [e[0] for e in top_empresas],
            "values": [e[1] for e in top_empresas],
        },
        "sources": source_counts,
        "metrics": metrics,
    }


@router.get("/api/jobs", dependencies=[Depends(verify_token)])
def get_recent_jobs():
    """Return recent application history from DB."""
    history = ApplicationRepository.get_all()
    recent = list(reversed(history))[:50]
    return {"jobs": recent}

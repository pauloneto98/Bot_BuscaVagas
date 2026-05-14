"""
Autonomous 24/7 Mode Routes — /api/auto/*
Manages the continuous operation scheduler subprocess.
"""

import os
import subprocess
import sys
import threading
from queue import Queue, Empty

from fastapi import APIRouter, Depends

from app.config import settings
from app.api.dependencies import verify_token

router = APIRouter()

_auto_process: subprocess.Popen | None = None
_auto_stdout: str = ""


def _enqueue_output(out, queue):
    for line in iter(out.readline, ''):
        queue.put(line)
    out.close()


@router.get("/api/auto/status")
def get_auto_status():
    global _auto_process
    running = _auto_process is not None and _auto_process.poll() is None
    return {"running": running}


@router.post("/api/auto/start", dependencies=[Depends(verify_token)])
def start_auto():
    global _auto_process, _auto_stdout
    if _auto_process is not None and _auto_process.poll() is None:
        return {"status": "already running"}

    _auto_stdout = ""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    _auto_process = subprocess.Popen(
        [sys.executable, "-m", "app.services.scheduler"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=settings.BASE_DIR,
        env=env,
        text=True,
        bufsize=1,
        encoding="utf-8"
    )

    q = Queue()
    t = threading.Thread(target=_enqueue_output, args=(_auto_process.stdout, q))
    t.daemon = True
    t.start()

    def collect_output():
        global _auto_stdout
        while _auto_process.poll() is None:
            try:
                line = q.get(timeout=0.1)
                _auto_stdout += line
                if len(_auto_stdout) > 50000:
                    _auto_stdout = _auto_stdout[-50000:]
            except Empty:
                continue
        while not q.empty():
            _auto_stdout += q.get()

    threading.Thread(target=collect_output, daemon=True).start()
    return {"status": "started"}


@router.post("/api/auto/stop", dependencies=[Depends(verify_token)])
def stop_auto():
    global _auto_process, _auto_stdout
    if _auto_process is not None and _auto_process.poll() is None:
        _auto_process.terminate()
        _auto_process.wait(timeout=5)
        _auto_stdout += "\n[!] PROCESSO AUTONOMO INTERROMPIDO PELO USUARIO.\n"
        return {"status": "stopped"}
    return {"status": "not running"}


@router.get("/api/auto/logs", dependencies=[Depends(verify_token)])
def get_auto_logs():
    return {"log": _auto_stdout}

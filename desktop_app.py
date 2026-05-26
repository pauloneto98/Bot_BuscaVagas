"""
Desktop App — Bot Busca Vagas
Launches the FastAPI dashboard inside a native-looking browser window (Edge/Chrome App Mode).
Double-click this (or the compiled .exe) to open the app.
No extra dependencies required — uses the browser already installed on Windows.
"""

import os
import sys
import time
import socket
import threading
import subprocess
import shutil

# ---------------------------------------------------------------------------
# Resolve base directory (works both from source and from PyInstaller bundle)
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    # Running as compiled .exe — PyInstaller sets this
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure the project root is on sys.path so imports like `app.*` work
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.chdir(BASE_DIR)

# ---------------------------------------------------------------------------
# Server configuration
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

# ---------------------------------------------------------------------------
# Utility: check if the server is ready
# ---------------------------------------------------------------------------

def _port_is_open(host: str, port: int, timeout: float = 0.3) -> bool:
    """Return True if something is listening on host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False


def _wait_for_server(host: str, port: int, max_wait: float = 15.0) -> bool:
    """Block until the server is reachable or *max_wait* seconds elapse."""
    start = time.time()
    while time.time() - start < max_wait:
        if _port_is_open(host, port):
            return True
        time.sleep(0.25)
    return False


# ---------------------------------------------------------------------------
# Start Uvicorn in a background thread
# ---------------------------------------------------------------------------

def _run_server():
    """Run the FastAPI app with Uvicorn (blocking call)."""
    import uvicorn
    from app.api.server import app  # noqa: F401

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="warning",
    )


def _start_server_thread() -> threading.Thread:
    t = threading.Thread(target=_run_server, daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------------------
# Find and launch browser in App Mode (no address bar, no tabs)
# ---------------------------------------------------------------------------

def _find_browser() -> tuple[str, str] | None:
    """
    Find Edge or Chrome on the system.
    Returns (path, name) or None.
    """
    candidates = [
        # Microsoft Edge (always present on Windows 10/11)
        (
            os.path.join(
                os.environ.get("ProgramFiles(x86)", ""),
                "Microsoft", "Edge", "Application", "msedge.exe",
            ),
            "Edge",
        ),
        (
            os.path.join(
                os.environ.get("ProgramFiles", ""),
                "Microsoft", "Edge", "Application", "msedge.exe",
            ),
            "Edge",
        ),
        # Google Chrome
        (
            os.path.join(
                os.environ.get("ProgramFiles", ""),
                "Google", "Chrome", "Application", "chrome.exe",
            ),
            "Chrome",
        ),
        (
            os.path.join(
                os.environ.get("ProgramFiles(x86)", ""),
                "Google", "Chrome", "Application", "chrome.exe",
            ),
            "Chrome",
        ),
        (
            os.path.join(
                os.environ.get("LOCALAPPDATA", ""),
                "Google", "Chrome", "Application", "chrome.exe",
            ),
            "Chrome",
        ),
    ]

    # Also check if msedge or chrome is on PATH
    for cmd, name in [("msedge", "Edge"), ("chrome", "Chrome"), ("google-chrome", "Chrome")]:
        path = shutil.which(cmd)
        if path:
            return (path, name)

    for path, name in candidates:
        if path and os.path.isfile(path):
            return (path, name)

    return None


def _launch_app_window(url: str) -> subprocess.Popen | None:
    """
    Launch browser in App Mode — opens a clean window that looks
    like a native desktop application (no tabs, no address bar).
    """
    browser = _find_browser()

    if browser:
        browser_path, browser_name = browser
        print(f"[Bot Busca Vagas] Abrindo janela do app via {browser_name}...")

        # --app flag opens the URL in a standalone app window
        # --window-size sets the initial window dimensions
        proc = subprocess.Popen(
            [
                browser_path,
                f"--app={url}",
                "--window-size=1280,820",
                "--disable-extensions",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc

    # Fallback: open default browser normally
    print("[Bot Busca Vagas] Navegador nao encontrado. Abrindo no navegador padrao...")
    import webbrowser
    webbrowser.open(url)
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 50)
    print("  Bot Busca Vagas — Dashboard Desktop")
    print("=" * 50)
    print()

    # Check if server is already running
    if _port_is_open(HOST, PORT):
        print(f"[INFO] Servidor ja esta rodando em {URL}")
        _launch_app_window(URL)
        print("[OK] Janela aberta. Voce pode fechar este terminal.")
        return

    print("[...] Iniciando servidor...")
    _start_server_thread()

    if not _wait_for_server(HOST, PORT):
        print("[ERRO] O servidor nao iniciou a tempo. Verifique os logs.")
        input("Pressione ENTER para sair...")
        sys.exit(1)

    print(f"[OK] Servidor pronto em {URL}")

    browser_proc = _launch_app_window(URL)

    if browser_proc:
        print("[OK] Janela do aplicativo aberta!")
        print()
        print(">>> MANTENHA ESTA JANELA ABERTA para o servidor continuar rodando.")
        print(">>> Feche esta janela (ou pressione Ctrl+C) para encerrar o servidor.")
        print()

        try:
            # Keep the server running until user closes the terminal
            # or presses Ctrl+C
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Bot Busca Vagas] Encerrando...")
    else:
        print("[OK] Servidor rodando. Feche esta janela para encerrar.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[Bot Busca Vagas] Encerrando...")


if __name__ == "__main__":
    main()

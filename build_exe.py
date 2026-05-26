"""
Build EXE — Bot Busca Vagas
Compiles the desktop application into a standalone Windows .exe using PyInstaller.
Run: python build_exe.py
"""

import os
import subprocess
import sys
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Paths
ENTRY_POINT = os.path.join(BASE_DIR, "desktop_app.py")
ICON_FILE = os.path.join(BASE_DIR, "bot_icon.ico")
WEB_DIR = os.path.join(BASE_DIR, "web")
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_ENV = os.path.join(BASE_DIR, "config.env")
RESUME_PDF = os.path.join(BASE_DIR, "Curriculo-PauloNeto.pdf")
APP_DIR = os.path.join(BASE_DIR, "app")

EXE_NAME = "BotBuscaVagas"


def main():
    print("=" * 60)
    print("  Build EXE — Bot Busca Vagas")
    print("=" * 60)

    # Verify icon exists
    icon_arg = []
    if os.path.exists(ICON_FILE):
        icon_arg = [f"--icon={ICON_FILE}"]
        print(f"[OK] Icone encontrado: {ICON_FILE}")
    else:
        print("[AVISO] Icone nao encontrado. Usando icone padrao.")
        print("        Rode 'python convert_icon.py' primeiro para gerar o icone.")

    # Build the PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",            # onedir is faster to build and start than onefile
        "--noconsole",         # hide the terminal window
        f"--name={EXE_NAME}",
        *icon_arg,
        # --- Bundle data files ---
        f"--add-data={WEB_DIR};web",
        f"--add-data={CONFIG_ENV};.",
        # --- Bundle the app package ---
        f"--add-data={APP_DIR};app",
        # --- Hidden imports that PyInstaller may miss ---
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespan",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=uvicorn.lifespan.off",
        "--hidden-import=fastapi",
        "--hidden-import=starlette",
        "--hidden-import=dotenv",
        "--hidden-import=app",
        "--hidden-import=app.api",
        "--hidden-import=app.api.server",
        "--hidden-import=app.api.auth",
        "--hidden-import=app.api.routes.bot",
        "--hidden-import=app.api.routes.hunter",
        "--hidden-import=app.api.routes.auto",
        "--hidden-import=app.api.routes.stats",
        "--hidden-import=app.api.routes.config",
        "--hidden-import=app.config",
        "--hidden-import=app.core",
        "--hidden-import=app.db",
        "--hidden-import=app.services",
        # Entry point
        ENTRY_POINT,
    ]

    print("\n[...] Compilando. Isso pode levar alguns minutos...\n")
    result = subprocess.run(cmd, cwd=BASE_DIR)

    if result.returncode != 0:
        print("\n[ERRO] Build falhou! Verifique os erros acima.")
        sys.exit(1)

    # The output directory
    dist_dir = os.path.join(BASE_DIR, "dist", EXE_NAME)
    exe_path = os.path.join(dist_dir, f"{EXE_NAME}.exe")

    # Copy data files that should live alongside the exe (mutable at runtime)
    data_dist = os.path.join(dist_dir, "data")
    if os.path.exists(DATA_DIR):
        if os.path.exists(data_dist):
            shutil.rmtree(data_dist)
        shutil.copytree(DATA_DIR, data_dist)
        print(f"[OK] Pasta 'data/' copiada para: {data_dist}")

    if os.path.exists(RESUME_PDF):
        shutil.copy2(RESUME_PDF, dist_dir)
        print(f"[OK] Curriculo copiado para: {dist_dir}")

    # Copy config.env to dist as well (mutable config)
    if os.path.exists(CONFIG_ENV):
        shutil.copy2(CONFIG_ENV, dist_dir)

    # Copy the icon file to dist
    if os.path.exists(ICON_FILE):
        shutil.copy2(ICON_FILE, dist_dir)

    print("\n" + "=" * 60)
    print(f"  BUILD COMPLETO!")
    print(f"  Executavel: {exe_path}")
    print("=" * 60)

    # --- Create Desktop Shortcut ---
    _create_shortcut(exe_path)


def _create_shortcut(exe_path: str):
    """Create a desktop shortcut (.lnk) for the exe."""
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop):
            # Try Portuguese Windows path
            desktop = os.path.join(os.path.expanduser("~"), "Área de Trabalho")
        if not os.path.exists(desktop):
            desktop = os.path.join(os.path.expanduser("~"), "Area de Trabalho")
        if not os.path.exists(desktop):
            print("[AVISO] Nao foi possivel encontrar a Area de Trabalho.")
            return

        shortcut_path = os.path.join(desktop, "Bot Busca Vagas.lnk")

        # Use PowerShell to create the shortcut
        icon_path = os.path.join(os.path.dirname(exe_path), "bot_icon.ico")
        ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{exe_path}"
$Shortcut.WorkingDirectory = "{os.path.dirname(exe_path)}"
$Shortcut.Description = "Bot Busca Vagas - Dashboard"
if (Test-Path "{icon_path}") {{ $Shortcut.IconLocation = "{icon_path}" }}
$Shortcut.Save()
'''
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
        )
        print(f"\n[OK] Atalho criado na Area de Trabalho: {shortcut_path}")

    except Exception as e:
        print(f"[AVISO] Nao foi possivel criar atalho: {e}")
        print(f"        Voce pode criar manualmente um atalho para: {exe_path}")


if __name__ == "__main__":
    main()

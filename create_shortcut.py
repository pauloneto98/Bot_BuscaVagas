"""
Create Desktop Shortcut — Bot Busca Vagas
Creates a clickable shortcut on the Windows Desktop that launches the app.
Run once: python create_shortcut.py
"""

import os
import subprocess
import sys
import ctypes

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_FILE = os.path.join(BASE_DIR, "bot_icon.ico")
BAT_FILE = os.path.join(BASE_DIR, "BotBuscaVagas.bat")


def _get_desktop_path() -> str:
    """Get the Desktop path using the Windows Shell API."""
    try:
        shell32 = ctypes.windll.shell32
        buf = ctypes.create_unicode_buffer(260)
        # CSIDL_DESKTOPDIRECTORY = 0x0010
        result = shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)
        if result == 0:
            return buf.value
    except Exception:
        pass

    # Fallback
    candidates = [
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
        os.path.join(os.path.expanduser("~"), "OneDrive", "Área de Trabalho"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


def main():
    desktop = _get_desktop_path()

    if not desktop or not os.path.exists(desktop):
        print(f"[ERRO] Nao foi possivel encontrar a Area de Trabalho.")
        sys.exit(1)

    print(f"[OK] Area de Trabalho: {desktop}")

    shortcut_path = os.path.join(desktop, "Bot Busca Vagas.lnk")

    icon_arg = ""
    if os.path.exists(ICON_FILE):
        icon_arg = f'$Shortcut.IconLocation = "{ICON_FILE}"'

    ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{BAT_FILE}"
$Shortcut.WorkingDirectory = "{BASE_DIR}"
$Shortcut.Description = "Bot Busca Vagas - Dashboard Desktop"
{icon_arg}
$Shortcut.Save()
'''

    result = subprocess.run(
        ["powershell", "-Command", ps_script],
        capture_output=True, text=True,
    )

    if result.returncode == 0:
        print(f"[OK] Atalho criado: {shortcut_path}")
        print()
        print(">>> Clique em 'Bot Busca Vagas' na Area de Trabalho para abrir!")
    else:
        print(f"[ERRO] {result.stderr}")


if __name__ == "__main__":
    main()

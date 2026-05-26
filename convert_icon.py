"""
Convert Icon — Bot Busca Vagas
Converts the generated PNG icon to a proper Windows .ico file.
Run: python convert_icon.py
"""

import os
import sys
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PNG_SOURCE = os.path.join(
    os.path.expanduser("~"),
    ".gemini", "antigravity", "brain",
    "4e317e45-d73f-427c-811a-c3a7d591b1c9",
    "bot_icon_1778889665991.png",
)
PNG_DEST = os.path.join(BASE_DIR, "bot_icon.png")
ICO_DEST = os.path.join(BASE_DIR, "bot_icon.ico")


def main():
    # Step 1: Copy the PNG into the project directory
    if os.path.exists(PNG_SOURCE):
        shutil.copy2(PNG_SOURCE, PNG_DEST)
        print(f"[OK] Copiado: {PNG_DEST}")
    elif not os.path.exists(PNG_DEST):
        print(f"[ERRO] Imagem nao encontrada: {PNG_SOURCE}")
        print("       Coloque manualmente um arquivo 'bot_icon.png' na raiz do projeto.")
        sys.exit(1)

    # Step 2: Convert PNG to ICO with multiple sizes
    try:
        from PIL import Image

        img = Image.open(PNG_DEST)
        # Windows .ico supports multiple sizes; we include the most common ones
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(ICO_DEST, format="ICO", sizes=sizes)
        print(f"[OK] Icone criado: {ICO_DEST}")
    except ImportError:
        print("[ERRO] Pillow nao instalado. Rode: pip install Pillow")
        sys.exit(1)
    except Exception as e:
        print(f"[ERRO] Falha ao converter icone: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Módulo para envio de notificações via WhatsApp Web usando Playwright.
Executa em um subprocesso separado para evitar conflito com outro contexto Playwright ativo.
Mantém a sessão salva para não precisar escanear o QR Code toda vez.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
WA_PROFILE_DIR = os.path.join(DATA_DIR, "whatsapp_profile")
WA_SENDER_SCRIPT = os.path.join(os.path.dirname(__file__), "_wa_sender.py")


def send_whatsapp_alert(phone_number: str, text: str, pdf_path: str = "") -> bool:
    """
    Dispara um subprocesso Python separado para abrir o WhatsApp Web via Playwright.
    Isso evita o conflito de dois contextos Playwright rodando no mesmo processo.
    """
    import subprocess
    
    args = [sys.executable, WA_SENDER_SCRIPT,
            "--phone", phone_number,
            "--text", text]
    if pdf_path and os.path.exists(pdf_path):
        args += ["--pdf", pdf_path]

    print(f"  📲 [WhatsApp] Disparando notificação para {phone_number}...")
    try:
        result = subprocess.run(args, timeout=300)  # 5 min de timeout total
        if result.returncode == 0:
            print("  ✅ [WhatsApp] Mensagem enviada com sucesso!")
            return True
        else:
            print("  ⚠ [WhatsApp] Subprocesso terminou com erro.")
            return False
    except subprocess.TimeoutExpired:
        print("  ⚠ [WhatsApp] Timeout de 5 minutos. Processo encerrado.")
        return False
    except Exception as e:
        print(f"  ❌ [WhatsApp] Erro ao disparar subprocesso: {e}")
        return False

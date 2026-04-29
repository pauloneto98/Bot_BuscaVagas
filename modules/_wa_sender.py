"""
Script auxiliar executado em subprocesso separado para enviar mensagem via WhatsApp Web.
Nunca deve ser importado diretamente — é chamado via subprocess pelo whatsapp_notifier.py.
"""
import argparse
import os
import time
import urllib.parse
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
WA_PROFILE_DIR = os.path.join(DATA_DIR, "whatsapp_profile")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phone", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--pdf", default="")
    args = parser.parse_args()

    os.makedirs(WA_PROFILE_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=WA_PROFILE_DIR,
            headless=False,
            viewport={"width": 1024, "height": 768}
        )

        page = browser.pages[0] if browser.pages else browser.new_page()

        encoded_msg = urllib.parse.quote(args.text)
        url = f"https://web.whatsapp.com/send?phone={args.phone}&text={encoded_msg}"

        print(f"  [WhatsApp] Abrindo conversa com {args.phone}...")
        page.goto(url)

        # Aguarda até 3 minutos (QR Code ou já logado)
        print("  [WhatsApp] Aguardando carregamento (ate 3 min - escaneie o QR Code se pedido)...")
        try:
            page.wait_for_selector('span[data-icon="attach-menu-plus"]', timeout=180000)
        except Exception:
            print("  [WhatsApp] Timeout de 3 minutos.")
            browser.close()
            exit(1)

        time.sleep(2)

        # Envia a mensagem de texto
        print("  [WhatsApp] Enviando mensagem...")
        page.keyboard.press("Enter")
        time.sleep(3)

        # Envia o PDF como anexo
        pdf_path = args.pdf
        if pdf_path and os.path.exists(pdf_path):
            print(f"  [WhatsApp] Anexando curriculo: {os.path.basename(pdf_path)}")
            try:
                # Clica no botão de Anexar
                page.locator('span[data-icon="attach-menu-plus"]').click()
                time.sleep(1)

                # Tenta o input de documento
                inputs = page.locator('input[type="file"]')
                count = inputs.count()
                doc_sent = False
                for i in range(count):
                    try:
                        accept_val = inputs.nth(i).get_attribute("accept") or ""
                        if "*" in accept_val or "application" in accept_val or accept_val == "":
                            inputs.nth(i).set_input_files(pdf_path)
                            doc_sent = True
                            break
                    except Exception:
                        continue

                if not doc_sent and count > 0:
                    inputs.last.set_input_files(pdf_path)

                time.sleep(3)
                # Clica em enviar na tela de preview
                send_btn = page.locator('span[data-icon="send"]').last
                if send_btn.count() > 0:
                    send_btn.click()
                    time.sleep(2)

            except Exception as e:
                print(f"  [WhatsApp] Falha ao enviar PDF: {e}")

        print("  [WhatsApp] Operacao concluida!")
        time.sleep(2)
        browser.close()
        exit(0)


if __name__ == "__main__":
    main()

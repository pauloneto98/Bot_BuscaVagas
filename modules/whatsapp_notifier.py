"""
Módulo para envio de notificações via WhatsApp Web usando Playwright.
Mantém a sessão salva para não precisar escanear o QR Code toda vez.
"""
import os
import time
import urllib.parse
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
WA_PROFILE_DIR = os.path.join(DATA_DIR, "whatsapp_profile")


def send_whatsapp_alert(phone_number: str, text: str, pdf_path: str = "") -> bool:
    """
    Abre o WhatsApp Web via Playwright, envia o texto e, se fornecido, faz upload do PDF.
    """
    os.makedirs(WA_PROFILE_DIR, exist_ok=True)
    
    try:
        with sync_playwright() as p:
            # Contexto persistente = salva os cookies e login do WhatsApp
            browser = p.chromium.launch_persistent_context(
                user_data_dir=WA_PROFILE_DIR,
                headless=False,  # Sempre visível para acompanhamento e QR Code (se precisar)
                viewport={"width": 1024, "height": 768}
            )
            
            page = browser.pages[0] if browser.pages else browser.new_page()
            
            # 1. Carregar chat específico já com a mensagem digitada no box
            encoded_msg = urllib.parse.quote(text)
            url = f"https://web.whatsapp.com/send?phone={phone_number}&text={encoded_msg}"
            
            print(f"  📱 [WhatsApp] Abrindo conversa com {phone_number}...")
            page.goto(url)
            
            # Aguarda a tela principal carregar
            try:
                # O botão de 'anexar' (clip) aparece quando o chat está pronto
                page.wait_for_selector('span[data-icon="attach-menu-plus"]', timeout=60000)
            except Exception:
                print("  ⚠ [WhatsApp] Timeout. Pode ser necessário escanear o QR Code.")
                print("  ⏳ Feche a janela após escanear e tente novamente na próxima.")
                browser.close()
                return False
                
            time.sleep(2)
            
            # 2. Enviar a mensagem de texto
            print("  📱 [WhatsApp] Enviando texto...")
            page.keyboard.press("Enter")
            time.sleep(2)
            
            # 3. Enviar o PDF (se existir)
            if pdf_path and os.path.exists(pdf_path):
                print(f"  📎 [WhatsApp] Anexando currículo: {os.path.basename(pdf_path)}")
                
                # Clica no botão de Anexar (+)
                page.locator('span[data-icon="attach-menu-plus"]').click()
                time.sleep(1)
                
                # O input type="file" que aceita documentos (*/*)
                # O WhatsApp tem múltiplos inputs ocultos, o de documento geralmente é o último ou o que tem accept="*"
                try:
                    # Tenta setar o arquivo diretamente no input oculto de documentos
                    inputs = page.locator('input[type="file"]')
                    count = inputs.count()
                    
                    # Vamos iterar pelos inputs de arquivo e tentar achar o de documento
                    doc_input_found = False
                    for i in range(count):
                        accept_val = inputs.nth(i).get_attribute("accept")
                        if accept_val == "*" or accept_val == "*/*":
                            inputs.nth(i).set_input_files(pdf_path)
                            doc_input_found = True
                            break
                    
                    if not doc_input_found:
                        # Se não achou pelo accept, tenta o primeiro (geralmente fotos/vídeos, mas vale tentar)
                        inputs.first.set_input_files(pdf_path)
                        
                    # Aguarda a tela de preview do envio
                    time.sleep(3)
                    
                    # Clica no botão verde de enviar da tela de preview
                    page.locator('span[data-icon="send"]').click()
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"  ⚠ [WhatsApp] Falha ao enviar anexo: {e}")
                    
            print("  ✅ [WhatsApp] Operação concluída.")
            # Pequeno delay para garantir o disparo pela rede antes de fechar
            time.sleep(2)
            browser.close()
            return True
            
    except Exception as e:
        print(f"  ❌ [WhatsApp] Erro na automação: {e}")
        return False

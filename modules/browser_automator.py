"""
Módulo para automação de candidaturas via navegador usando Playwright.
Tenta preencher formulários básicos. Se for barrado (ex: Gupy, Workday ou erro no script),
aciona o módulo do WhatsApp para notificar o usuário.
"""
import os
import time
from playwright.sync_api import sync_playwright
from .whatsapp_notifier import send_whatsapp_alert

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
BROWSER_PROFILE_DIR = os.path.join(DATA_DIR, "browser_profile")

WHATSAPP_NUMBER = "5581982198599" # Número do Paulo Neto fornecido

def apply_via_browser(job_url: str, curriculo_path: str, job_info: dict) -> bool:
    """
    Tenta aplicar via navegador. Se for um site muito complexo ou falhar,
    chama o send_whatsapp_alert e retorna False.
    Retorna True apenas se o script confirmar que aplicou com sucesso.
    """
    os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)
    
    print(f"  🌐 [Navegador] Tentando acessar a vaga via portal web...")
    
    # 1. Checagem rápida de sites notoriamente difíceis (que exigem login/captcha sempre)
    # Mesmo assim vamos abrir para o usuário ver, mas já sabemos que a chance de falha é alta
    complex_domains = ["gupy.io", "workday.com", "taleo.net", "icims.com", "myworkdayjobs"]
    is_complex = any(d in job_url.lower() for d in complex_domains)

    success = False
    is_linkedin = "linkedin.com" in job_url.lower()
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=BROWSER_PROFILE_DIR,
                headless=False, # Visível para o usuário conforme pedido
                viewport={"width": 1280, "height": 800}
            )
            
            page = browser.pages[0] if browser.pages else browser.new_page()
            
            # Navegar para a vaga
            try:
                page.goto(job_url, timeout=30000)
                time.sleep(5) # Aguarda renderização completa
            except Exception as e:
                print(f"  ⚠ [Navegador] Falha ao carregar a página: {e}")
                browser.close()
                _trigger_whatsapp(job_url, curriculo_path, job_info)
                return False

            # Para LinkedIn: aguarda login antes de continuar
            if is_linkedin:
                print("  🔑 [LinkedIn] Aguardando sessão autenticada (faça login se solicitado)...")
                try:
                    # Se houver botão "Sign In" (class contendo nav__button-secondary ou sign-in), significa deslogado.
                    # Mas a forma mais segura é: logado = elemento de perfil OU botão "Easy Apply" presente.
                    page.wait_for_selector(
                        '.global-nav__me-photo, [data-control-name="identity_profile_photo"], button.jobs-apply-button, button:has-text("Easy Apply")',
                        timeout=120000  # 2 min para o usuário fazer login
                    )
                    print("  ✅ [LinkedIn] Sessão autenticada ou botão de candidatar visível!")
                    time.sleep(2)
                except Exception:
                    print("  ⚠ [LinkedIn] Timeout de 2 minutos aguardando login. Acionando WhatsApp.")
                    browser.close()
                    _trigger_whatsapp(job_url, curriculo_path, job_info)
                    return False
                    
                # Tenta o Easy Apply do LinkedIn
                try:
                    # Aguarda o botão de Easy Apply ficar disponível
                    easy_apply_btn = page.locator(
                        'button.jobs-apply-button, button:has-text("Easy Apply"), button:has-text("Candidatura Simplificada")'
                    ).first
                    if easy_apply_btn.count() > 0:
                        print("  🖥️ [LinkedIn] Clicando em Easy Apply...")
                        easy_apply_btn.click()
                        time.sleep(3)
                        
                        # Tenta submeter as telas do easy apply
                        for step in range(5):  # Máximo 5 telas
                            # Botão de próximo/enviar
                            next_btn = page.locator(
                                'button:has-text("Submit application"), button:has-text("Enviar candidatura"), '
                                'button:has-text("Review"), button:has-text("Revisar"), '
                                'button:has-text("Next"), button:has-text("Próximo")'
                            ).first
                            if next_btn.count() > 0:
                                next_btn.click()
                                time.sleep(2)
                                # Verifica se a candidatura foi enviada
                                if page.locator('h2:has-text("Your application was sent"), h2:has-text("Candidatura enviada")').count() > 0:
                                    print("  ✅ [LinkedIn] Candidatura Easy Apply enviada com sucesso!")
                                    success = True
                                    break
                            else:
                                break  # Não achou botão de avançar, para
                                
                        if not success:
                            print("  ⚠ [LinkedIn] Não conseguiu completar o Easy Apply. Acionando WhatsApp.")
                    else:
                        print("  ⚠ [LinkedIn] Botão Easy Apply não encontrado. Acionando WhatsApp.")
                        
                except Exception as e:
                    print(f"  ⚠ [LinkedIn] Erro no Easy Apply: {e}")
                    
                browser.close()
                if not success:
                    _trigger_whatsapp(job_url, curriculo_path, job_info)
                return success
                    
        
            # Isso é um "best-effort". Se não achar os campos, vai cair no except.
            try:
                # Procura botões de 'Apply', 'Candidatar', 'Aplicar'
                apply_btn = page.locator('button:has-text("Apply"), button:has-text("Candidatar"), a:has-text("Apply"), a:has-text("Candidatar")').first
                if apply_btn.count() > 0:
                    print("  🖱️ [Navegador] Clicando no botão de Candidatar...")
                    apply_btn.click()
                    time.sleep(3)
                    
                # Procura input de arquivo
                file_input = page.locator('input[type="file"]').first
                if file_input.count() > 0:
                    print(f"  📎 [Navegador] Fazendo upload do currículo: {os.path.basename(curriculo_path)}")
                    file_input.set_input_files(curriculo_path)
                    time.sleep(2)
                else:
                    raise ValueError("Nenhum campo de upload de currículo encontrado.")
                    
                # Procura Submit
                submit_btn = page.locator('button:has-text("Submit Application"), button:has-text("Enviar"), input[type="submit"]').first
                if submit_btn.count() > 0:
                    print("  🖱️ [Navegador] Enviando formulário...")
                    submit_btn.click()
                    time.sleep(5)
                    success = True
                    print("  ✅ [Navegador] Candidatura enviada aparentemente com sucesso!")
                else:
                    raise ValueError("Botão de Submit não encontrado.")
                    
            except Exception as e:
                print(f"  ⚠ [Navegador] Fui barrado ou não encontrei os campos corretos: {e}")
                success = False

            browser.close()
            
    except Exception as e:
        print(f"  ❌ [Navegador] Erro fatal no Playwright: {e}")
        success = False

    if not success:
        _trigger_whatsapp(job_url, curriculo_path, job_info)
        
    return success

def _trigger_whatsapp(job_url: str, curriculo_path: str, job_info: dict):
    """Envia notificação via WhatsApp."""
    empresa = job_info.get("empresa", "Empresa Desconhecida")
    titulo = job_info.get("titulo", "Vaga")
    
    msg = (
        f"🤖 *Bot Busca Vagas*\n"
        f"Fui barrado ao tentar enviar o currículo pelo site!\n\n"
        f"🏢 *Empresa:* {empresa}\n"
        f"🎯 *Vaga:* {titulo}\n"
        f"🔗 *Link da vaga:* {job_url}\n\n"
        f"📎 Estou enviando o seu currículo em PDF personalizado em anexo para você mesmo aplicar manualmente."
    )
    
    print("  📲 [Fallback] Acionando notificação via WhatsApp...")
    send_whatsapp_alert(WHATSAPP_NUMBER, msg, curriculo_path)

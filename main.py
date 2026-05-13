#!/usr/bin/env python3
"""
Bot de Candidatura Automática — v2
Busca vagas, adapta currículo com IA e envia candidaturas por email.

Uso:
  python3 main.py              # Executa uma vez (fluxo completo)
  python3 main.py --teste      # Modo teste (1 vaga mock, sem enviar email)
  python3 main.py --agendar    # Agenda execução diária às 09:00 BRT
  python3 main.py --validar    # Valida configurações e conexões
  python3 main.py --status     # Exibe histórico e estatísticas
"""

import argparse
import glob
import io
import json
import os
import re
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "config.env"))

from modules.browser_automator import apply_via_browser
from modules.company_researcher import find_company_email
from modules.config_validator import run_validation
from modules.email_sender import send_application_email
from modules.job_scraper import search_all_jobs
from modules.logger import (
    build_applied_set, export_csv, get_recent, get_stats,
    load_history, log_application, save_history
)
from modules.metrics import export_metrics, inc_fallback
from modules.database import get_pending_leads, update_lead_status_by_email
from modules.resume_adapter import (
    adapt_resume_and_analyze, extract_resume_text,
    generate_resume_docx, generate_resume_pdf, is_international_job
)

_RESUME_CACHE_FILE = os.path.join(BASE_DIR, "data", "resume_cache.json")

def load_resume_cache():
    if os.path.exists(_RESUME_CACHE_FILE):
        try:
            with open(_RESUME_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_resume_cache(cache):
    try:
        with open(_RESUME_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except:
        pass

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)
    except AttributeError:
        pass

console = Console()


def get_resume_path() -> str:
    pdf_name = os.getenv("RESUME_PDF", "Curriculo-PauloNeto.pdf")
    path = os.path.join(BASE_DIR, pdf_name)
    if not os.path.exists(path):
        console.print(f"[bold red]✗ Currículo não encontrado:[/bold red] {path}")
        sys.exit(1)
    return path


def print_banner():
    candidate_name = os.getenv("CANDIDATE_NAME", "Paulo Antonio do Nascimento Neto")
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    console.print()
    console.print(Panel(
        f"[bold cyan]🤖  BOT DE CANDIDATURA AUTOMÁTICA[/bold cyan]\n"
        f"[dim]👤 Candidato: {candidate_name}   📅 {now}[/dim]",
        border_style="cyan",
        expand=False,
    ))


def show_status():
    """Exibe histórico e estatísticas detalhadas."""
    print_banner()
    history = load_history()
    stats = get_stats(history)

    # ── Painel de estatísticas ────────────────────────────────────
    console.print()
    console.print(Panel(
        f"[bold green]✅ Emails enviados:[/bold green]       {stats['emails_enviados']}\n"
        f"[yellow]📋 Total processadas:[/yellow]     {stats['total_vagas_encontradas']}\n"
        f"[dim]📭 Sem email encontrado:    {stats['sem_email']}[/dim]\n"
        f"[cyan]📅 Candidaturas hoje:      {stats['candidaturas_hoje']}[/cyan]",
        title="📊 Estatísticas",
        border_style="blue",
        expand=False,
    ))

    # ── Top empresas ─────────────────────────────────────────────
    if stats["top_empresas"]:
        t = Table(title="🏢 Empresas com mais candidaturas", box=box.ROUNDED)
        t.add_column("Empresa", style="white")
        t.add_column("Candidaturas", justify="center", style="cyan")
        for emp, count in stats["top_empresas"]:
            t.add_row(emp, str(count))
        console.print(t)

    # ── Histórico recente ─────────────────────────────────────────
    recent = get_recent(history, n=15)
    if recent:
        console.print()
        t2 = Table(title="📜 Candidaturas Recentes", box=box.ROUNDED, show_lines=True)
        t2.add_column("Data", style="dim", width=14)
        t2.add_column("Empresa", style="bold white")
        t2.add_column("Vaga", style="white")
        t2.add_column("Email", justify="center", width=6)
        for c in recent:
            email_icon = "[green]✅[/green]" if c.get("email_enviado") else "[red]❌[/red]"
            t2.add_row(
                c.get("data", "")[:16],
                c.get("empresa", ""),
                c.get("vaga", ""),
                email_icon,
            )
        console.print(t2)

    # ── CSV ───────────────────────────────────────────────────────
    csv_path = export_csv()
    if csv_path:
        console.print(f"\n[dim]📁 CSV exportado em: {csv_path}[/dim]")


def load_pending_leads_from_db() -> list[dict]:
    """Carrega leads do banco SQLite com status 'pending'."""
    pending = get_pending_leads()
    jobs = []
    
    for lead in pending:
        # Pular se e-mail não for válido ou empresa vazia
        email = lead.get("email")
        empresa = lead.get("empresa")
        if not email or not empresa:
            continue
            
        titulo = lead.get("cargo_da_vaga", "Desenvolvedor de Software")
        if not titulo:
            titulo = "Desenvolvedor de Software"
            
        jobs.append({
            "titulo": titulo,
            "empresa": empresa,
            "local": "Brasil/Remoto",
            "url": lead.get("site", ""),
            "descricao": f"Candidatura direta. Fonte: {lead.get('fonte', 'Banco de Dados')}",
            "fonte": "SQLite",
            "email_direto": email,
            "id_lead": lead.get("id") # Guardar para referenciar depois se necessário
        })
        
    return jobs


def run_bot(test_mode: bool = False, manual_only: bool = False):
    """Executa o fluxo principal do bot."""
    start_time = datetime.now()
    candidate_name = os.getenv("CANDIDATE_NAME", "Paulo Antonio do Nascimento Neto")

    print_banner()

    # 1. Validar config antes de rodar
    console.print("\n[dim]Verificando configurações...[/dim]")
    if not run_validation(full=False):
        console.print("[bold red]✗ Corrija as configurações antes de continuar.[/bold red]")
        return

    # 2. Carregar currículo base
    resume_path = get_resume_path()
    console.print(f"\n[bold]📄 Extraindo texto do currículo:[/bold] {os.path.basename(resume_path)}")
    resume_text = extract_resume_text(resume_path)
    if not resume_text:
        console.print("[bold red]✗ Não foi possível extrair texto do currículo![/bold red]")
        return
    console.print(f"  [green]✅[/green] {len(resume_text)} caracteres extraídos")

    # 3. Carregar histórico
    history = load_history()
    stats_before = get_stats(history)
    console.print(f"[dim]📊 Candidaturas anteriores: {stats_before['total_vagas_encontradas']}[/dim]")

    # 4. Buscar vagas
    if test_mode:
        console.print("\n[bold yellow]⚠ MODO TESTE:[/bold yellow] Usando vaga mock (sem envio de email)")
        jobs = [{
            "titulo": "Desenvolvedor Junior Python",
            "empresa": "Empresa Teste",
            "local": "Remoto - Brasil",
            "url": "https://exemplo.com/vaga/123",
            "descricao": (
                "Buscamos desenvolvedor júnior com experiência em Python, "
                "HTML, CSS e vontade de aprender. Trabalho 100% remoto. "
                "Requisitos: Python básico, Git, comunicação."
            ),
            "fonte": "Teste",
        }]
    elif manual_only:
        console.print("\n[bold cyan]📋 MODO MANUAL:[/bold cyan] Processando apenas leads pendentes do banco de dados")
        jobs = load_pending_leads_from_db()
        if not jobs:
            console.print("[yellow]⚠ Nenhum lead pendente no banco de dados.[/yellow]")
            return
        console.print(f"  [green]✅[/green] {len(jobs)} lead(s) carregado(s)")
    else:
        # Carregar leads pendentes + buscados automaticamente
        manual_jobs = load_pending_leads_from_db()
        if manual_jobs:
            console.print(f"\n[bold cyan]📋 {len(manual_jobs)} lead(s) pendente(s) do banco de dados carregado(s)[/bold cyan]")
        auto_jobs = search_all_jobs()
        jobs = manual_jobs + auto_jobs

    if not jobs:
        console.print("\n[yellow]⚠ Nenhuma vaga encontrada. Tente novamente mais tarde.[/yellow]")
        return

    # 5. Processar vagas
    applied_count = skipped_count = error_count = 0
    applied_set = build_applied_set(history)
    resume_cache = load_resume_cache()

    console.print(f"\n[bold cyan]🚀 Processando {len(jobs)} vagas...[/bold cyan]")

    for i, job in enumerate(jobs):
        console.rule(f"[dim]Vaga {i+1}/{len(jobs)}[/dim]")
        console.print(f"  [bold]📋 {job['titulo']}[/bold]")
        console.print(f"  [cyan]🏢 {job['empresa']}[/cyan]  📍 {job['local']}")

        # Verificar duplicata usando busca O(1)
        emp_key = job["empresa"].strip().lower()
        vaga_key = job["titulo"].strip().lower()

        if (emp_key, vaga_key) in applied_set:
            console.print("  [dim]⏭  Já se candidatou. Pulando...[/dim]")
            skipped_count += 1
            continue

        try:
            vaga_slug = re.sub(r"[^\w]", "_", job.get('titulo', 'vaga'))[:30].lower()
            
            # 5. Pesquisar email da empresa primeiro (para decidir se usa IA)
            company_email = ""
            if job.get("email_direto"):
                company_email = job["email_direto"]
                console.print(f"  📧 Email direto fornecido: {company_email}")
            else:
                company_info = find_company_email(job["empresa"])
                company_email = company_info.get("email", "")

            # Verificar configuração de Otimização de Tokens
            personalize_only_emails = os.getenv("PERSONALIZE_ONLY_EMAILS", "true").lower() == "true"
            is_email_job = bool(company_email)
            skip_ai = False
            
            if personalize_only_emails and not is_email_job:
                skip_ai = True
                
            pdf_path = ""
            analysis = {}
            adapted = {}
            
            if skip_ai:
                console.print("  [blue]⚡ Otimização de Tokens:[/blue] Vaga sem e-mail detectada. Usando currículo base para site/portal.")
                pdf_path = get_resume_path()
            else:
                # 5b. Analisar e Adaptar (Verificando Cache primeiro)
                if vaga_slug in resume_cache:
                    console.print(f"  [green]🗂️  Cache: Reutilizando análise e adaptação para '{job['titulo']}'[/green]")
                    adapted = resume_cache[vaga_slug]["adapted"]
                    analysis = resume_cache[vaga_slug]["analysis"]
                else:
                    adapted, analysis = adapt_resume_and_analyze(resume_text, job)
                    if adapted and not adapted.get("_rate_limit_fallback"):
                        resume_cache[vaga_slug] = {"adapted": adapted, "analysis": analysis}
                        save_resume_cache(resume_cache)
                
                if adapted and adapted.get("_rate_limit_fallback"):
                    console.print("  [yellow]⚠ Rate Limit: Usando currículo estático original como fallback...[/yellow]")
                    inc_fallback()
                    base_pdf = get_resume_path()
                    if os.path.exists(base_pdf):
                        pdf_path = base_pdf
                        console.print(f"  [green]✅ Currículo original encontrado.[/green]")
                    else:
                        console.print(f"  [red]✗ Currículo original não encontrado: {base_pdf}[/red]")
                elif not adapted:
                    console.print("  [yellow]⚠ Não foi possível adaptar o currículo.[/yellow]")
                    error_count += 1
                    log_application(history, job["empresa"], job["titulo"],
                                    job.get("url", ""), False, notas="Erro na adaptação")
                    applied_set.add((emp_key, vaga_key))
                    continue
                else:
                    time.sleep(2)
                    # Set language for PDF/DOCX section headers
                    idioma = analysis.get("idioma_vaga", "pt-BR")
                    adapted["_lang"] = "en" if idioma.startswith("en") or is_international_job(job) else "pt"
                    # 5c. Gerar PDF e DOCX
                    pdf_path = generate_resume_pdf(adapted, job, candidate_name)
                    generate_resume_docx(adapted, job, candidate_name)

            if not pdf_path:
                console.print("  [yellow]⚠ Erro ao gerar/encontrar PDF.[/yellow]")
                error_count += 1
                continue

            if test_mode:
                console.print("  [bold yellow]🧪 MODO TESTE:[/bold yellow] Email NÃO enviado")
                log_application(history, job["empresa"], job["titulo"],
                                job.get("url", ""), False, curriculo_path=pdf_path,
                                notas="Modo teste")
                applied_set.add((emp_key, vaga_key))
                applied_count += 1
                continue

            # 5e. Enviar email
            if company_email:
                success = send_application_email(
                    to_email=company_email,
                    job=job,
                    analysis=analysis,
                    adapted_data=adapted,
                    resume_path=pdf_path,
                )
                log_application(
                    history, job["empresa"], job["titulo"],
                    job.get("url", ""), success,
                    email_destino=company_email,
                    curriculo_path=pdf_path,
                )
                applied_set.add((emp_key, vaga_key))
                if success:
                    applied_count += 1
                    update_lead_status_by_email(company_email, 'applied')
                else:
                    error_count += 1
                    update_lead_status_by_email(company_email, 'failed')
            else:
                # Linkedin precisa login, então pulamos vagas do LinkedIn quando não tem email
                if job.get("url") and "linkedin.com" in job.get("url", "").lower():
                    console.print("  ⚠ Vaga do LinkedIn sem email (precisa login). Pulando.")
                    log_application(
                        history, job["empresa"], job["titulo"],
                        job.get("url", ""), False,
                        notas="LinkedIn sem email - pulado",
                    )
                    error_count += 1
                else:
                    console.print("  [yellow]⚠ Sem email de contato. Pulando para próxima vaga.[/yellow]")
                    log_application(
                        history, job["empresa"], job["titulo"],
                        job.get("url", ""), False,
                        notas="Sem email - pulado",
                    )
                    error_count += 1
                    
                applied_set.add((emp_key, vaga_key))

            time.sleep(3)

        except Exception as e:
            console.print(f"  [red]✗ Erro inesperado: {e}[/red]")
            error_count += 1
            log_application(history, job["empresa"], job["titulo"],
                            job.get("url", ""), False, notas=f"Erro: {str(e)[:100]}")

    # 6. Resumo final com tabela rica
    elapsed = (datetime.now() - start_time).total_seconds()
    final_stats = get_stats(load_history())

    console.print()
    summary_table = Table(box=box.ROUNDED, show_header=False, expand=False)
    summary_table.add_column("Métrica", style="bold")
    summary_table.add_column("Valor", justify="right", style="cyan")
    summary_table.add_row("⏱  Tempo total",            f"{elapsed/60:.1f} minutos")
    summary_table.add_row("🔍 Vagas encontradas",       str(len(jobs)))
    summary_table.add_row("✅ Processadas com sucesso", str(applied_count))
    summary_table.add_row("⏭  Já aplicadas (puladas)", str(skipped_count))
    summary_table.add_row("✗  Erros",                  str(error_count))
    summary_table.add_row("📧 Total emails (acumulado)", str(final_stats["emails_enviados"]))

    console.print(Panel(summary_table, title="📊 Resumo da Execução", border_style="green"))
    try:
        export_metrics()
    except Exception:
        pass




def retry_failed_applications():
    """Tenta aplicar via navegador para vagas anteriores que falharam por falta de email."""
    print_banner()
    history = load_history()
    candidaturas = history.get("candidaturas", [])
    
    # Filtrar vagas não enviadas que tenham URL
    to_retry = [c for c in candidaturas if not c.get("email_enviado") and c.get("url")]
    
    if not to_retry:
        console.print("[yellow]⚠ Nenhuma vaga elegível para retry encontrada no histórico.[/yellow]")
        return
        
    console.print(f"\n[bold cyan]🔄 Iniciando Retry em {len(to_retry)} vagas passadas...[/bold cyan]")
    
    success_count = 0
    for i, job in enumerate(to_retry):
        console.rule(f"[dim]Retry {i+1}/{len(to_retry)}[/dim]")
        console.print(f"  [bold]📋 {job['vaga']}[/bold]")
        console.print(f"  [cyan]🏢 {job['empresa']}[/cyan]")
        
        pdf_path = job.get("curriculo_gerado", "")
        if not pdf_path or not os.path.exists(pdf_path):
            console.print("  [red]✗ PDF original não encontrado para esta vaga. Pulando...[/red]")
            continue
            
        success = apply_via_browser(job["url"], pdf_path, {"empresa": job["empresa"], "titulo": job["vaga"]})
        if success:
            job["email_enviado"] = True # Marcamos como enviado (aplicado com sucesso)
            job["notas"] = "Aplicado via Navegador (Retry)"
            success_count += 1
            
    # Salvar histórico modificado
    if success_count > 0:
        save_history(history)
        
    console.print(f"\n[bold green]✅ Retry concluído! {success_count} candidaturas enviadas via navegador.[/bold green]")


def main():
    parser = argparse.ArgumentParser(description="Bot de Candidatura Automática")
    parser.add_argument("--teste",   action="store_true",
                        help="Modo teste (1 vaga mock, sem enviar email)")
    parser.add_argument("--validar", action="store_true",
                        help="Valida configurações e testa conexões")
    parser.add_argument("--status",  action="store_true",
                        help="Exibe histórico de candidaturas e estatísticas")
    parser.add_argument("--manual",  action="store_true",
                        help="Processa APENAS leads pendentes do banco de dados")
    parser.add_argument("--retry-browser", action="store_true",
                        help="Tenta aplicar via navegador para vagas passadas sem email")
    args = parser.parse_args()

    if args.validar:
        run_validation(full=True)
    elif args.retry_browser:
        try:
            retry_failed_applications()
        except KeyboardInterrupt:
            console.print("\n\n[yellow]⏹ Retry interrompido pelo usuário.[/yellow]")
    elif args.status:
        show_status()
    elif args.teste:
        run_bot(test_mode=True)
    elif args.manual:
        run_bot(manual_only=True)
    else:
        run_bot()


if __name__ == "__main__":
    main()

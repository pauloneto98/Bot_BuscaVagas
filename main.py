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
import os
import sys
import time
import glob
import shutil
import re
import io
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)
    except AttributeError:
        pass


import schedule
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import box
from rich.text import Text

import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "config.env"))
MANUAL_EMAILS_FILE = os.path.join(BASE_DIR, "data", "emails_manuais.txt")

from modules.job_scraper import search_all_jobs, _search_linkedin
from modules.job_analyzer import analyze_job
from modules.resume_adapter import extract_resume_text, adapt_resume, generate_resume_pdf, generate_resume_docx
from modules.company_researcher import find_company_email
from modules.email_sender import send_application_email
from modules.logger import load_history, is_already_applied, log_application, get_stats, get_recent, export_csv
from modules.config_validator import run_validation

console = Console()


def get_resume_path() -> str:
    pdf_name = os.getenv("RESUME_PDF", "Curriculo_Paulo_Net0.pdf")
    path = os.path.join(BASE_DIR, pdf_name)
    if not os.path.exists(path):
        console.print(f"[bold red]✗ Currículo não encontrado:[/bold red] {path}")
        sys.exit(1)
    return path


def print_banner():
    candidate_name = os.getenv("CANDIDATE_NAME", "Paulo Neto")
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


def load_manual_emails() -> list[dict]:
    """Carrega emails manuais do arquivo data/emails_manuais.txt."""
    if not os.path.exists(MANUAL_EMAILS_FILE):
        return []
    jobs = []
    with open(MANUAL_EMAILS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 2:
                continue
            empresa = parts[0]
            email = parts[1]
            titulo = parts[2] if len(parts) >= 3 else "Desenvolvedor de Software Junior"
            # Validar email básico
            if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email):
                console.print(f"  [yellow]⚠ Email inválido ignorado:[/yellow] {email}")
                continue
            jobs.append({
                "titulo": titulo,
                "empresa": empresa,
                "local": "Brasil",
                "url": "",
                "descricao": f"Candidatura direta para {titulo} na empresa {empresa}.",
                "fonte": "Manual",
                "email_direto": email,
            })
    return jobs


def run_bot(test_mode: bool = False, manual_only: bool = False):
    """Executa o fluxo principal do bot."""
    start_time = datetime.now()
    candidate_name = os.getenv("CANDIDATE_NAME", "Paulo Neto")

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
        console.print("\n[bold cyan]📋 MODO MANUAL:[/bold cyan] Processando emails de data/emails_manuais.txt")
        jobs = load_manual_emails()
        if not jobs:
            console.print("[yellow]⚠ Nenhum email manual encontrado.[/yellow]")
            console.print(f"[dim]  Edite o arquivo: {MANUAL_EMAILS_FILE}[/dim]")
            return
        console.print(f"  [green]✅[/green] {len(jobs)} candidatura(s) manual(is) carregada(s)")
    else:
        # Carregar manuais + buscados automaticamente
        manual_jobs = load_manual_emails()
        if manual_jobs:
            console.print(f"\n[bold cyan]📋 {len(manual_jobs)} email(s) manual(is) carregado(s)[/bold cyan]")
        auto_jobs = search_all_jobs()
        jobs = manual_jobs + auto_jobs

    if not jobs:
        console.print("\n[yellow]⚠ Nenhuma vaga encontrada. Tente novamente mais tarde.[/yellow]")
        return

    # 5. Processar vagas
    applied_count = skipped_count = error_count = 0

    console.print(f"\n[bold cyan]🚀 Processando {len(jobs)} vagas...[/bold cyan]")

    for i, job in enumerate(jobs):
        console.rule(f"[dim]Vaga {i+1}/{len(jobs)}[/dim]")
        console.print(f"  [bold]📋 {job['titulo']}[/bold]")
        console.print(f"  [cyan]🏢 {job['empresa']}[/cyan]  📍 {job['local']}")

        # Verificar duplicata
        if is_already_applied(history, job["empresa"], job["titulo"]):
            console.print("  [dim]⏭  Já se candidatou. Pulando...[/dim]")
            skipped_count += 1
            continue

        try:
            # 5a. Analisar vaga
            analysis = analyze_job(job)
            time.sleep(2)

            # 5b. Adaptar currículo
            adapted = adapt_resume(resume_text, job, analysis)
            
            pdf_path = ""
            if adapted and adapted.get("_rate_limit_fallback"):
                console.print("  [yellow]⚠ Rate Limit: Procurando currículo fallback (genérico da vaga)...[/yellow]")
                vaga_slug = re.sub(r"[^\w]", "_", job.get('titulo', 'vaga'))[:30]
                curriculos_dir = os.path.join(BASE_DIR, "data", "curriculos")
                os.makedirs(curriculos_dir, exist_ok=True)
                
                # Procura se já gerou um currículo para esta vaga
                existing_pdfs = glob.glob(os.path.join(curriculos_dir, f"*_{vaga_slug}_*.pdf"))
                if existing_pdfs:
                    pdf_path = existing_pdfs[0]
                    console.print(f"  [green]✅ Reutilizando currículo: {os.path.basename(pdf_path)}[/green]")
                else:
                    pdf_path = os.path.join(curriculos_dir, f"Curriculo_{candidate_name.replace(' ', '_')}_{vaga_slug}_01.pdf")
                    base_pdf = os.getenv("RESUME_PDF_PATH", "Curriculo_Paulo_Net0.pdf")
                    if os.path.exists(base_pdf):
                        shutil.copy(base_pdf, pdf_path)
                        console.print(f"  [green]✅ Currículo base categorizado como: {os.path.basename(pdf_path)}[/green]")
                    else:
                        pdf_path = ""
            elif not adapted:
                console.print("  [yellow]⚠ Não foi possível adaptar o currículo.[/yellow]")
                error_count += 1
                log_application(history, job["empresa"], job["titulo"],
                                job.get("url", ""), False, notas="Erro na adaptação")
                continue
            else:
                time.sleep(2)
                # 5c. Gerar PDF e DOCX
                pdf_path = generate_resume_pdf(adapted, job, candidate_name)
                generate_resume_docx(adapted, job, candidate_name)

            if not pdf_path:
                console.print("  [yellow]⚠ Erro ao gerar/encontrar PDF.[/yellow]")
                error_count += 1
                continue

            # 5d. Pesquisar email da empresa (ou usar email manual)
            if job.get("email_direto"):
                company_email = job["email_direto"]
                console.print(f"  📧 Email manual: {company_email}")
            else:
                company_info = find_company_email(job["empresa"])
                company_email = company_info.get("email", "")

            if test_mode:
                console.print("  [bold yellow]🧪 MODO TESTE:[/bold yellow] Email NÃO enviado")
                log_application(history, job["empresa"], job["titulo"],
                                job.get("url", ""), False, curriculo_path=pdf_path,
                                notas="Modo teste")
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
                if success:
                    applied_count += 1
                else:
                    error_count += 1
            else:
                console.print("  [yellow]⚠ Sem email de contato. Currículo gerado mas não enviado.[/yellow]")
                log_application(
                    history, job["empresa"], job["titulo"],
                    job.get("url", ""), False,
                    curriculo_path=pdf_path,
                    notas="Email não encontrado",
                )
                applied_count += 1

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


def run_scheduled():
    """Agenda a execução diária às 09:00 BRT."""
    console.print(Panel(
        "[bold]⏰ Bot agendado para executar diariamente às 09:00[/bold]\n"
        "[dim]Pressione Ctrl+C para parar[/dim]",
        border_style="yellow",
    ))
    schedule.every().day.at("09:00").do(run_bot)
    console.print("[cyan]🚀 Executando a primeira vez agora...[/cyan]\n")
    run_bot()
    while True:
        schedule.run_pending()
        time.sleep(60)


def main():
    parser = argparse.ArgumentParser(description="Bot de Candidatura Automática")
    parser.add_argument("--agendar", action="store_true",
                        help="Agenda execução diária às 09:00")
    parser.add_argument("--teste",   action="store_true",
                        help="Modo teste (1 vaga mock, sem enviar email)")
    parser.add_argument("--validar", action="store_true",
                        help="Valida configurações e testa conexões")
    parser.add_argument("--status",  action="store_true",
                        help="Exibe histórico de candidaturas e estatísticas")
    parser.add_argument("--manual",  action="store_true",
                        help="Processa APENAS emails manuais (data/emails_manuais.txt)")
    args = parser.parse_args()

    if args.validar:
        run_validation(full=True)
    elif args.status:
        show_status()
    elif args.agendar:
        try:
            run_scheduled()
        except KeyboardInterrupt:
            console.print("\n\n[yellow]⏹ Bot encerrado pelo usuário.[/yellow]")
    elif args.teste:
        run_bot(test_mode=True)
    elif args.manual:
        run_bot(manual_only=True)
    else:
        run_bot()


if __name__ == "__main__":
    main()

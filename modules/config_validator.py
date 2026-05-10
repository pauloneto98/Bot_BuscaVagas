"""
Módulo de Validação de Configurações
Verifica se todas as variáveis obrigatórias estão corretas antes de rodar o bot.
"""

import os
import smtplib
import socket

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, "config.env"))

console = Console()


def _check_gemini_api() -> tuple[bool, str]:
    """Testa se a API Gemini está acessível e autenticada."""
    try:
        import google.generativeai as genai
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return False, "GEMINI_API_KEY não definida"
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = model.generate_content("Responda apenas: OK")
        if resp.text:
            return True, f"Conectado ✓ (modelo: gemini-1.5-flash)"
        return False, "API respondeu sem texto"
    except Exception as e:
        err = str(e)
        if "API_KEY_INVALID" in err or "invalid" in err.lower():
            return False, "Chave de API inválida"
        if "quota" in err.lower() or "429" in err.lower():
            return True, "API ok (rate limit ativo - aguarde)"
        return False, f"Erro: {err[:80]}"


def _check_smtp() -> tuple[bool, str]:
    """Testa autenticação Gmail SMTP."""
    email = os.getenv("EMAIL_ADDRESS", "")
    password = os.getenv("EMAIL_APP_PASSWORD", "")
    if not email or not password:
        return False, "EMAIL_ADDRESS ou EMAIL_APP_PASSWORD não definidos"

    # Detectar senha normal (sem espaços e sem formato de app password)
    clean = password.replace(" ", "")
    if len(clean) < 16:
        return False, (
            f"Senha parece ser a senha NORMAL do Gmail (muito curta). "
            f"Gere uma Senha de App em: https://myaccount.google.com/apppasswords"
        )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
            smtp.login(email, password)
        return True, f"Autenticado como {email} ✓"
    except smtplib.SMTPAuthenticationError:
        return False, (
            "Autenticação falhou! Use uma Senha de App (16 chars), não sua senha normal.\n"
            "         Gere em: https://myaccount.google.com/apppasswords"
        )
    except (socket.timeout, OSError) as e:
        return False, f"Sem conexão com smtp.gmail.com: {e}"
    except Exception as e:
        return False, f"Erro SMTP: {str(e)[:80]}"


def _check_resume() -> tuple[bool, str]:
    """Verifica se o currículo PDF existe."""
    pdf_name = os.getenv("RESUME_PDF", "Curriculo-PauloNeto.pdf")
    path = os.path.join(BASE_DIR, pdf_name)
    if os.path.exists(path):
        size_kb = os.path.getsize(path) // 1024
        return True, f"{pdf_name} encontrado ({size_kb} KB) ✓"
    return False, f"Arquivo não encontrado: {path}"


def _check_env_vars() -> list[tuple[str, bool, str]]:
    """Verifica variáveis de ambiente obrigatórias."""
    vars_required = [
        ("GEMINI_API_KEY", "Chave da API Gemini"),
        ("EMAIL_ADDRESS", "Email Gmail"),
        ("EMAIL_APP_PASSWORD", "Senha de App Gmail"),
        ("CANDIDATE_NAME", "Nome do candidato"),
        ("RESUME_PDF", "Nome do arquivo PDF"),
    ]
    results = []
    for var, desc in vars_required:
        val = os.getenv(var, "")
        if val:
            # Mascarar valor sensível
            if "PASSWORD" in var or "KEY" in var:
                display = val[:4] + "***" + val[-2:] if len(val) > 6 else "***"
            else:
                display = val
            results.append((desc, True, display))
        else:
            results.append((desc, False, "NÃO DEFINIDO"))
    return results


def run_validation(full: bool = True) -> bool:
    """
    Executa todas as validações e exibe resultado.
    full=True: testa conexões reais (mais lento)
    full=False: apenas verifica variáveis
    Retorna True se tudo ok, False se há problemas críticos.
    """
    console.print()
    console.print(Panel(
        "[bold cyan]🔍 Validando configurações do Bot de Candidatura...[/bold cyan]",
        border_style="cyan"
    ))

    all_ok = True

    # ── Tabela de variáveis de ambiente ──────────────────────────
    table = Table(title="Variáveis de Ambiente", box=box.ROUNDED, show_header=True)
    table.add_column("Variável", style="bold white", width=30)
    table.add_column("Status", width=8)
    table.add_column("Valor", style="dim")

    env_checks = _check_env_vars()
    for desc, ok, val in env_checks:
        icon = "[green]✅[/green]" if ok else "[red]❌[/red]"
        table.add_row(desc, icon, val)
        if not ok:
            all_ok = False

    console.print(table)

    # ── Arquivo de currículo ──────────────────────────────────────
    console.print()
    resume_ok, resume_msg = _check_resume()
    if resume_ok:
        console.print(f"  [green]✅ Currículo:[/green] {resume_msg}")
    else:
        console.print(f"  [red]❌ Currículo:[/red] {resume_msg}")
        all_ok = False

    # ── Testes de conexão (somente se full=True) ──────────────────
    if full:
        console.print()
        console.print("[bold]Testando conexões...[/bold]")

        # Gemini
        console.print("  [dim]→ Testando Gemini API...[/dim]", end="")
        gemini_ok, gemini_msg = _check_gemini_api()
        if gemini_ok:
            console.print(f"\r  [green]✅ Gemini API:[/green] {gemini_msg}          ")
        else:
            console.print(f"\r  [red]❌ Gemini API:[/red] {gemini_msg}          ")
            all_ok = False

        # SMTP
        console.print("  [dim]→ Testando Gmail SMTP...[/dim]", end="")
        smtp_ok, smtp_msg = _check_smtp()
        if smtp_ok:
            console.print(f"\r  [green]✅ Gmail SMTP:[/green] {smtp_msg}          ")
        else:
            console.print(f"\r  [yellow]⚠️  Gmail SMTP:[/yellow] {smtp_msg}          ")
            # SMTP falhou mas não é crítico para testar scraping/Gemini
            all_ok = False

    # ── Resultado final ───────────────────────────────────────────
    console.print()
    if all_ok:
        console.print(Panel(
            "[bold green]✅ Todas as configurações estão corretas![/bold green]\n"
            "  Execute [cyan]python3 main.py --teste[/cyan] para uma execução de teste.",
            border_style="green"
        ))
    else:
        console.print(Panel(
            "[bold red]⚠️  Há problemas nas configurações![/bold red]\n"
            "  Corrija os erros acima antes de rodar o bot.",
            border_style="red"
        ))

    return all_ok


if __name__ == "__main__":
    run_validation(full=True)

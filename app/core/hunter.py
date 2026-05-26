"""
Bot Caçador de Leads (TI) - Versão Aprimorada
Realiza varreduras web atrás de empresas de TI (pequenas e médias/startups)
que estejam com vagas abertas. Usa Gemini para extrair e formatar JSON.

Melhorias:
- Mais fontes de busca (GitHub Jobs, Stack Overflow Jobs, etc.)
- Busca direta por emails em páginas de carreiras
- Suporte a múltiplas localizações (Brasil, Portugal, Remoto)
- Extração de emails de domínios específicos de tech
"""

import io
import json
import os
import random
import re
import sys
import time
import urllib.parse
from datetime import datetime
from typing import Optional

# Fix encoding no Windows para suportar emojis/UTF-8
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

from app.config import settings
from app.core.researcher import _fallback_hunter_io, _fallback_apollo_io
from app.db.repositories import LeadRepository

DATA_DIR = settings.DATA_DIR

# ── Configuracao Gemini ──────────────────────────────────────────
GEMINI_API_KEY = settings.GEMINI_API_KEY
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    
generation_config = {
    "temperature": 0.1,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 1024,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

try:
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config=generation_config,
        safety_settings=safety_settings
    )
except Exception:
    model = None


# ── Termos de Busca (Dorks) ──────────────────────────────────────
ROLES = [
    "python", "fastapi", "react", "node.js", "full stack", 
    "desenvolvedor python", "desenvolvedor full stack",
    "software engineer", "backend developer", "frontend developer",
    "devops", "data engineer", "mobile developer", "java developer"
]

LOCATIONS_PRESENCIAL = [
    "recife", "pernambuco", "pe",
    "sao paulo", "sp",
    "rio de janeiro", "rj",
    "lisboa", "porto", "portugal"
]

LOCATIONS_REMOTE = [
    '"remoto" OR "home office" OR "remote"',
    '"trabalho remoto" OR "vaga remota"'
]

# Novos prefixes expandidos para mais fontes
PREFIXES = [
    'site:linkedin.com/jobs "tecnologia"',
    'site:gupy.io "tecnologia"',
    'site:vagas.com.br "tecnologia"',
    'site:indeed.com "tecnologia"',
    'site:portodigital.org/empresas',
    '"trabalhe conosco" "tecnologia"',
    '"careers" "tecnologia"',
    'site:github.com/jobs "developer"',
    'site:stackoverflow.com/jobs "developer"',
    'site:glassdoor.com.br "tecnologia"',
    'site:programathor.com.br',
    'site:geekhunter.com.br',
    'site:99jobs.com "tecnologia"',
    'site:trampos.co "tecnologia"',
    'site:hipsters.jobs "tecnologia"',
    'site:remotar.com.br',
    'site:trabalharemoto.net',
]

# Tech company domains conhecidos no Brasil
TECH_COMPANY_DOMAINS = [
    "ifood.com.br", "totvs.com.br", "accenture.com", "mv.com.br",
    "serasa.com.br", "brq.com", "gft.com", "nava.com.br",
    "certisign.com.br", "fortestecnologia.com.br", "usabit.com.br",
    "argosolutions.com.br", "swile.co", "stone.com.br", "nubank.com.br",
    "mercadolivre.com.br", "magazineluiza.com.br", "via.com.br"
]

# Email patterns para busca direta
HR_EMAIL_PATTERNS = [
    "rh@", "vagas@", "recrutamento@", "talentos@", "careers@",
    "jobs@", "hr@", "contato@", "selecao@", "people@",
    "curriculo@", "trabalhe@", "oportunidades@"
]


def generate_queries(num_queries: int = 20) -> list:
    """Gera queries dinâmicas para busca diversificada."""
    queries = []
    
    # Queries com foco em emails diretos
    for _ in range(num_queries // 4):
        role = random.choice(ROLES)
        loc = random.choice(LOCATIONS_REMOTE + LOCATIONS_PRESENCIAL[:3])
        prefix = random.choice(PREFIXES[:7])
        query = f'{prefix} "{role}" {loc} "@" "email"'
        queries.append(query)
    
    # Queries em sites específicos de tech
    for _ in range(num_queries // 4):
        role = random.choice(ROLES)
        site = random.choice(PREFIXES[7:])
        query = f'{site} "{role}"'
        queries.append(query)
    
    # Queries focadas em páginas de carreiras
    for _ in range(num_queries // 4):
        role = random.choice(ROLES)
        loc = random.choice(LOCATIONS_PRESENCIAL)
        query = f'site:linkedin.com/jobs "{role}" "{loc}" "vagas" "@"'
        queries.append(query)
    
    # Queries genéricas com foco em RH
    for _ in range(num_queries // 4):
        role = random.choice(ROLES)
        query = f'"{role}" "rh@" OR "vagas@" OR "recrutamento@" OR "careers@"'
        queries.append(query)
    
    return queries[:num_queries]


# Gera queries dinâmicas
QUERIES = generate_queries(20)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
]

# Email regex pattern
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# Blocked domains for email extraction
BLOCKED_EMAIL_DOMAINS = {
    'example.com', 'sentry.io', 'github.com', 'noreply',
    'no-reply', 'wixpress.com', 'cloudflare.com', 'amazonaws.com',
    'google.com', 'microsoft.com', 'outlook.com', 'gmail.com',
    'hotmail.com', 'yahoo.com', 'yandex.com',
    # Plataformas de emprego (NÃO são empresas contratando)
    'indeed.com', 'linkedin.com', 'glassdoor.com', 'vagas.com.br',
    'gupy.io', 'jooble.org', 'catho.com.br', 'infojobs.com.br',
    'remote.co', 'upwork.com', 'freelancer.com', 'fiverr.com',
    'stackoverflow.com', 'dice.com', 'ziprecruiter.com',
    'roberthalf.com', 'sapo.pt', 'emprego.sapo.pt',
    'remotefrontendjobs.com', 'weworkremotely.com',
    'remoteok.com', 'wellfound.com', 'angel.co',
}

# HR-related email prefixes (prioritized)
HR_EMAIL_PREFIXES = [
    'rh@', 'vagas@', 'recrutamento@', 'talentos@', 'careers@',
    'jobs@', 'hr@', 'contato@', 'selecao@', 'people@',
    'curriculo@', 'trabalhe@', 'oportunidades@', 'rh.ti@',
    'rh.ti@', 'tech.rh@', 'dev.rh@', 'talent@',
]


def _get_headers() -> dict:
    """Returns headers for web requests."""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'DNT': '1',
        'Upgrade-Insecure-Requests': '1',
    }


def extract_emails_from_text(text: str) -> list:
    """Extract and filter emails from text content."""
    if not text:
        return []
    
    found = EMAIL_PATTERN.findall(text)
    filtered = []
    
    for email in found:
        email_lower = email.lower()
        # Skip blocked domains
        if any(domain in email_lower for domain in BLOCKED_EMAIL_DOMAINS):
            continue
        # Skip image/file extensions
        if email_lower.endswith(('.png', '.jpg', '.svg', '.gif', '.css', '.js')):
            continue
        filtered.append(email_lower)
    
    return list(set(filtered))


def score_email(email: str) -> int:
    """Score an email - lower is better (more likely to be HR-related)."""
    email_lower = email.lower()
    for i, prefix in enumerate(HR_EMAIL_PREFIXES):
        if email_lower.startswith(prefix) or prefix.rstrip('@') in email_lower:
            return i
    return 100


def prioritize_emails(emails: list) -> list:
    """Sort emails by priority (HR emails first)."""
    return sorted(emails, key=score_email)


def scrape_page_emails(url: str, timeout: int = 10) -> list:
    """Visit a URL and extract all emails from the page."""
    if not url or not url.startswith('http'):
        return []
    
    try:
        response = requests.get(url, headers=_get_headers(), timeout=timeout)
        if response.status_code == 200:
            return extract_emails_from_text(response.text)
    except (requests.RequestException, requests.Timeout):
        pass
    
    return []


def find_career_pages(base_url: str) -> list:
    """Try to discover career/contact pages of a website."""
    slugs = [
        '/contato', '/contact', '/fale-conosco',
        '/carreiras', '/careers', '/trabalhe-conosco',
        '/vagas', '/jobs', '/rh', '/people',
        '/about-us', '/sobre', '/team',
    ]
    found = []
    
    for slug in slugs:
        url = base_url.rstrip('/') + slug
        try:
            response = requests.get(url, headers=_get_headers(), timeout=8)
            if response.status_code == 200:
                found.append(url)
                if len(found) >= 3:
                    break
        except (requests.RequestException, requests.Timeout):
            continue
    
    return found


def extract_domain_from_url(url: str) -> str:
    """Extract domain from URL."""
    if not url:
        return ''
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split('/')[0]
    except Exception:
        return ''


def search_company_email(company_name: str, domain: str = None) -> Optional[str]:
    """Search for a specific company's HR email."""
    if not company_name:
        return None
    
    queries = [
        f'"{company_name}" email rh vagas',
        f'"{company_name}" recrutamento email',
        f'"{company_name}" careers email',
        f'"{company_name}" trabalhe conosco email',
        f'site:{domain} "rh@" OR "vagas@" OR "recrutamento@"' if domain else '',
        f'site:{domain} careers contact' if domain else '',
    ]
    
    for query in queries:
        if not query:
            continue
        
        try:
            results_text = search_duckduckgo(query)
            if results_text:
                emails = extract_emails_from_text(results_text)
                if emails:
                    prioritized = prioritize_emails(emails)
                    return prioritized[0]
        except Exception:
            continue
        
        time.sleep(random.uniform(2, 4))
    
    # ── Etapa 4: APIs Oficiais (Fallback) ──
    if domain:
        print(f"  [Fallback] Acionando APIs para {domain}...")
        api_emails = _fallback_hunter_io(domain)
        if not api_emails:
            api_emails = _fallback_apollo_io(domain)
        if api_emails:
            return api_emails[0]

    return None


def load_existing_leads() -> list:
    return LeadRepository.get_all()

def save_leads(leads: list):
    # No-op since we insert into DB immediately, but kept for compatibility 
    pass


from duckduckgo_search import DDGS

def search_duckduckgo(query: str) -> str:
    """Busca no DuckDuckGo via biblioteca oficial e retorna o texto para a IA ler."""
    try:
        results_text = []
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=10))
            for r in results:
                title = r.get('title', '')
                body = r.get('body', '')
                href = r.get('href', '')
                results_text.append(f"Título: {title}\nLink: {href}\nTrecho: {body}")
        
        return "\n\n".join(results_text)
    except Exception as e:
        print(f"  [Erro na busca DDGS]: {e}")
        return ""


def _build_extraction_prompt(text_data: str) -> str:
    """Constrói o prompt de extração de leads."""
    return f"""
Você é um agente especializado em prospecção B2B para mercado de tecnologia.

## OBJETIVO
Encontrar e compilar e-mails de contato (RH, recrutamento ou geral) de empresas de TI que estão ativamente contratando.

## PROCESSO DE EXTRAÇÃO
Para cada empresa encontrada:
1. Identifique o nome da empresa e domínio do site
2. Busque e-mails nos padrões: rh@, recrutamento@, careers@, jobs@, talentos@, selecao@
3. Se não encontrar e-mail direto, registre o LinkedIn da empresa

## FILTROS
- Apenas empresas de TI/tecnologia
- Preferencialmente vagas remotas ou em Recife/PE
- Stack de interesse: Python, FastAPI, React, Node.js, Full Stack

## FORMATO DE SAÍDA
Retorne APENAS um JSON array válido (sem markdown, sem crases de formatação) com as chaves:
"empresa", "site", "email", "cargo_da_vaga", "fonte", "data".

Se não encontrar nenhuma empresa válida, retorne um array vazio [].

TEXTO DA BUSCA PARA ANALISAR:
{text_data[:3500]}
"""


def _extract_with_groq(prompt: str) -> list:
    """Fallback: usa a API da Groq (Llama 3) para extrair leads."""
    groq_key = settings.GROQ_API_KEY
    if not groq_key:
        return []
    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
        print("  [Groq/Llama 3] Acionando fallback para extração de leads...")
        chat = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2048,
        )
        content = chat.choices[0].message.content.strip()
        content = re.sub(r"^```json\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return parsed
        return []
    except Exception as e:
        print(f"  [Erro Groq]: {e}")
        return []


def extract_leads_with_gemini(text_data: str) -> list:
    """Usa a IA para ler os resultados e extrair empresas/emails/vagas válidas."""
    if not text_data.strip():
        return []

    prompt = _build_extraction_prompt(text_data)

    # Tentativa 1: Gemini
    if model and GEMINI_API_KEY:
        try:
            response = model.generate_content(prompt)
            content = response.text.strip()
            content = re.sub(r"^```json\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return parsed
            return []
        except Exception as e:
            err_str = str(e)
            print(f"  [Gemini]: {err_str[:120]}")
            if "429" in err_str or "quota" in err_str.lower():
                # Fallback para Groq
                return _extract_with_groq(prompt)
            return []
    
    # Se Gemini não está configurado, tenta direto a Groq
    return _extract_with_groq(prompt)


def export_leads_csv(leads: list, output_path: str = None):
    """Export leads to CSV format."""
    if not output_path:
        output_path = os.path.join(DATA_DIR, "leads_ti.csv")
    
    import csv
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'empresa', 'site', 'email', 'cargo_da_vaga', 'fonte', 'data'
        ])
        writer.writeheader()
        for lead in leads:
            writer.writerow({
                'empresa': lead.get('empresa', ''),
                'site': lead.get('site', ''),
                'email': lead.get('email', ''),
                'cargo_da_vaga': lead.get('cargo_da_vaga', ''),
                'fonte': lead.get('fonte', ''),
                'data': lead.get('data', ''),
            })
    
    print(f"  📄 CSV exportado: {output_path}")
    return output_path


def export_leads_for_email_sender(leads: list, output_path: str = None):
    """Export leads in format compatible with emails_tech_compilado.json."""
    if not output_path:
        output_path = os.path.join(DATA_DIR, "leads_compilado_hunter.json")
    
    data = {
        "metadata": {
            "titulo": "Leads Coletados - Email Hunter",
            "descricao": "Empresas de TI com vagas ativas",
            "gerado_em": datetime.now().strftime("%Y-%m-%d"),
            "total_leads": len(leads),
        },
        "agencias_rh": [
            {
                "nome": lead.get('empresa', ''),
                "email": lead.get('email', ''),
                "regiao": "Brasil",
                "especialidade": lead.get('cargo_da_vaga', 'Tecnologia'),
            }
            for lead in leads if lead.get('email')
        ]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"  📄 JSON exportado: {output_path}")
    return output_path


def hunt_specific_companies(companies: list, max_results: int = 50) -> list:
    """
    Hunt emails for a specific list of companies.
    
    Args:
        companies: List of dicts with 'nome' and optionally 'site'/'domain'
        max_results: Maximum number of leads to return
    
    Returns:
        List of leads found
    """
    print("\n>>> Iniciando busca direcionada de empresas...")
    print(f"Empresas na lista: {len(companies)}\n")
    
    existing_leads = load_existing_leads()
    existing_emails = {lead.get("email", "").lower() for lead in existing_leads if lead.get("email")}
    
    new_leads = []
    
    for i, company in enumerate(companies, 1):
        company_name = company.get('nome', '')
        company_site = company.get('site', '') or company.get('link', '')
        domain = extract_domain_from_url(company_site) if company_site else None
        
        if not company_name:
            continue
        
        print(f"\n[{i}/{len(companies)}] 🔎 {company_name}")
        
        # Check if we already have this company
        existing_company = next(
            (l for l in existing_leads if l.get('empresa', '').lower() == company_name.lower()),
            None
        )
        
        if existing_company and existing_company.get('email'):
            print(f"  ⏭ Já temos email: {existing_company['email']}")
            continue
        
        # Search for email
        email = search_company_email(company_name, domain)
        
        if email and email not in existing_emails:
            lead = {
                'empresa': company_name,
                'site': company_site or f"www.{company_name.lower().replace(' ', '')}.com.br",
                'email': email,
                'cargo_da_vaga': company.get('vagas_destaque', 'Desenvolvedor'),
                'fonte': 'Company Research',
                'data': datetime.now().strftime('%Y-%m-%d'),
                'status': 'pending'
            }
            existing_leads.append(lead)
            existing_emails.add(email)
            new_leads.append(lead)
            LeadRepository.insert(lead)
            print(f"  ✅ Email encontrado: {email}")
        else:
            print(f"  ❌ Email não encontrado")
        
        # Rate limiting
        delay = random.uniform(3, 6)
        time.sleep(delay)
        
        if len(new_leads) >= max_results:
            break
    
    save_leads(existing_leads)
    
    print(f"\n[ OK ] Busca direcionada concluída!")
    print(f"Novos leads: {len(new_leads)}")
    print(f"Total no banco: {len(existing_leads)}")
    
    return new_leads


def run_hunter(max_queries: int = None):
    """
    Main hunter function - runs the email collection process.
    
    Args:
        max_queries: Maximum number of queries to run (default: all)
    """
    print("\n>>> Iniciando Bot Caçador de Leads (TI)...")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    
    existing_leads = load_existing_leads()
    existing_emails = {lead.get("email", "").lower() for lead in existing_leads if lead.get("email")}
    
    print(f"[ INFO ] Leads já existentes no banco: {len(existing_leads)}")
    
    new_leads_found = 0
    
    # Shuffle queries for variety
    queries = QUERIES.copy()
    random.shuffle(queries)
    
    if max_queries:
        queries = queries[:max_queries]
    
    for i, query in enumerate(queries, 1):
        print(f"\n[ BUSCA {i}/{len(queries)} ]: {query}")
        
        raw_text = search_duckduckgo(query)
        if not raw_text:
            print("  ! Nenhum resultado retornado pelo buscador.")
            time.sleep(3)
            continue
            
        print("  * Analisando resultados com IA...")
        extracted_data = extract_leads_with_gemini(raw_text)
        
        valid_found_this_turn = 0
        for lead in extracted_data:
            email = lead.get("email", "").strip().lower()
            empresa = lead.get("empresa", "").strip()
            
            # Basic security filters
            if not email or "@" not in email:
                continue
            # Bloquear domínios de plataformas de emprego
            email_domain = email.split('@')[1] if '@' in email else ''
            if any(blocked in email_domain for blocked in BLOCKED_EMAIL_DOMAINS):
                continue
            if email in existing_emails:
                print(f"  > Já existe: {empresa} ({email})")
                continue
                
            # Add to database
            lead['status'] = 'pending'
            lead['data'] = datetime.now().strftime('%Y-%m-%d')
            inserted = LeadRepository.insert(lead)
            
            if inserted:
                existing_leads.append(lead)
                existing_emails.add(email)
                new_leads_found += 1
                valid_found_this_turn += 1
                print(f"  + [NOVO LEAD]: {empresa} | {email} | {lead.get('cargo_da_vaga', '')} | {lead.get('fonte', '')}")
            else:
                print(f"  > Ignorado (Erro ao inserir ou já existe no BD): {empresa} ({email})")
            
        if valid_found_this_turn == 0:
            print("  - Nenhum lead novo útil encontrado nesta busca.")
        
        # Anti-blocking interval (15 RPM limit)
        delay = random.uniform(12, 16)
        print(f"  ~ Pausa de {delay:.1f}s para evitar rate limit...")
        time.sleep(delay)
        
    print("\n[ OK ] CAÇADA CONCLUÍDA!")
    print(f"Novos leads encontrados hoje: {new_leads_found}")
    print(f"Total no banco (SQLite): {len(existing_leads)}")
    
    # Export to CSV (optional via CLI)
    # export_leads_csv(existing_leads)
    # export_leads_for_email_sender(existing_leads)


def print_help():
    """Print help information."""
    print("""
Bot Caçador de Leads (TI) - Comandos

Uso:
    python tools/email_hunter.py              # Executa busca automática
    python tools/email_hunter.py --hunt-companies  # Busca empresas do JSON
    python tools/email_hunter.py --export-csv       # Exporta leads para CSV
    python tools/email_hunter.py --stats            # Mostra estatísticas
    python tools/email_hunter.py --help             # Esta mensagem

Opções:
    --hunt-companies    Processa lista de empresas do emails_tech_compilado.json
    --export-csv        Exporta leads atuais para CSV
    --stats             Mostra estatísticas do banco de leads
    --max-queries N     Limita número de queries (padrão: todas)
    --help              Mostra esta ajuda
""")


def show_stats():
    """Show statistics about the leads database."""
    leads = load_existing_leads()
    
    if not leads:
        print("  Nenhum lead no banco de dados.")
        return
    
    print(f"\n📊 Estatísticas do Banco de Leads")
    print(f"   Total de leads: {len(leads)}")
    
    # Count by source
    sources = {}
    for lead in leads:
        source = lead.get('fonte', 'Desconhecida')
        sources[source] = sources.get(source, 0) + 1
    
    print(f"\n   Leads por fonte:")
    for source, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"      {source}: {count}")
    
    # Count emails with HR patterns
    hr_emails = sum(1 for l in leads if any(
        p in l.get('email', '').lower() for p in HR_EMAIL_PREFIXES
    ))
    print(f"\n   Emails HR/Recrutamento: {hr_emails}/{len(leads)}")
    
    # Export paths
    csv_path = os.path.join(DATA_DIR, "leads_ti.csv")
    json_path = os.path.join(DATA_DIR, "leads_compilado_hunter.json")
    print(f"\n   Arquivos de exportação:")
    print(f"      CSV: {csv_path}")
    print(f"      JSON: {json_path}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == '--help' or arg == '-h':
            print_help()
        elif arg == '--stats':
            show_stats()
        elif arg == '--export-csv':
            leads = load_existing_leads()
            export_leads_csv(leads)
            export_leads_for_email_sender(leads)
        elif arg == '--hunt-companies':
            # Load companies from compiled JSON
            json_file = os.path.join(DATA_DIR, "emails_tech_compilado.json")
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Combine RH agencies and tech companies
                companies = []
                for item in data.get('agencias_rh', []):
                    companies.append({
                        'nome': item.get('nome', ''),
                        'site': '',
                        'vagas_destaque': item.get('especialidade', ''),
                    })
                for item in data.get('empresas_tecnologia', []):
                    companies.append({
                        'nome': item.get('nome', ''),
                        'site': item.get('link', ''),
                        'vagas_destaque': item.get('vagas_destaque', ''),
                    })
                
                hunt_specific_companies(companies)
            else:
                print(f"  Arquivo não encontrado: {json_file}")
        elif arg == '--max-queries':
            if len(sys.argv) > 2:
                try:
                    max_q = int(sys.argv[2])
                    run_hunter(max_queries=max_q)
                except ValueError:
                    print("  Erro: valor inválido para max-queries")
            else:
                print("  Erro: especifique o número máximo de queries")
        else:
            print(f"  Opção desconhecida: {arg}")
            print_help()
    else:
        run_hunter()

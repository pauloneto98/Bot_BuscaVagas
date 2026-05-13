"""
Módulo de Pesquisa de Empresas — v2
Pesquisa email de contato/RH da empresa na web.
Melhorias: DuckDuckGo como fallback do Google, scraping de /contato e /carreiras.
Integração adicional: Fallback para as APIs Hunter.io e Apollo.io.
"""

import os
import re
import requests
from urllib.parse import quote_plus, urljoin, urlparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from .job_scraper import _get_headers, _random_delay, _safe_get

# Carregar chaves de API
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, "config.env"))
HUNTER_IO_API_KEY = os.getenv("HUNTER_IO_API_KEY", "")
APOLLO_IO_API_KEY = os.getenv("APOLLO_IO_API_KEY", "")

_EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)
_BLOCKED_DOMAINS = {
    "example.com", "sentry.io", "github.com", "noreply",
    "no-reply", "wixpress.com", "cloudflare.com", "amazonaws.com",
}
_HR_PREFIXES = [
    "rh@", "vagas@", "recrutamento@", "talentos@", "careers@",
    "jobs@", "hr@", "contato@", "contact@", "curriculo@",
    "selecao@", "people@", "talent@",
]


def _extract_emails(text: str) -> list[str]:
    """Extrai e filtra emails de um texto."""
    found = _EMAIL_PATTERN.findall(text)
    return list({
        e.lower() for e in found
        if not any(b in e.lower() for b in _BLOCKED_DOMAINS)
        and not e.endswith((".png", ".jpg", ".svg", ".gif"))
    })


def _score_email(email: str) -> int:
    """Pontua um email — menor = melhor (mais provável de ser RH)."""
    for i, prefix in enumerate(_HR_PREFIXES):
        if email.startswith(prefix) or prefix.rstrip("@") in email:
            return i
    return 100


def _prioritize_emails(emails: list[str]) -> list[str]:
    return sorted(emails, key=_score_email)


def _scrape_page_emails(url: str) -> list[str]:
    """Visita uma URL e extrai todos os emails."""
    if not url or not url.startswith("http"):
        return []
    resp = _safe_get(url, timeout=10)
    if not resp:
        return []
    return _extract_emails(resp.text)


def _find_contact_pages(base_url: str) -> list[str]:
    """Tenta descobrir páginas de contato/carreiras de um site."""
    slugs = [
        "/contato", "/contact", "/fale-conosco",
        "/carreiras", "/careers", "/trabalhe-conosco",
        "/vagas", "/jobs", "/rh",
    ]
    found = []
    for slug in slugs:
        url = urljoin(base_url, slug)
        resp = _safe_get(url, timeout=8)
        if resp and resp.status_code == 200:
            found.append(url)
            if len(found) >= 3:
                break
    return found


def _search_google(query: str) -> list[dict]:
    """Busca no Google e retorna resultados."""
    try:
        url = "https://www.google.com/search"
        params = {"q": query, "num": 10, "hl": "pt-BR"}
        response = requests.get(url, params=params, headers=_get_headers(), timeout=15)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "lxml")
        results = []
        for g in soup.find_all("div", class_="g"):
            title_tag = g.find("h3")
            link_tag = g.find("a")
            snippet_tag = g.find("div", class_="VwiC3b")
            if title_tag and link_tag:
                href = link_tag.get("href", "")
                if href.startswith("/url?q="):
                    href = href.split("/url?q=")[1].split("&")[0]
                if href.startswith("http"):
                    results.append({
                        "title": title_tag.get_text(),
                        "url": href,
                        "snippet": snippet_tag.get_text() if snippet_tag else "",
                    })
        return results
    except requests.RequestException:
        return []


def _search_duckduckgo(query: str) -> list[dict]:
    """Fallback: busca no DuckDuckGo HTML."""
    try:
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}
        response = requests.post(url, data=params, headers=_get_headers(), timeout=15)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "lxml")
        results = []
        for result in soup.find_all("div", class_="result"):
            title_tag = result.find("a", class_="result__a")
            snippet_tag = result.find("a", class_="result__snippet")
            if title_tag:
                href = title_tag.get("href", "")
                results.append({
                    "title": title_tag.get_text(),
                    "url": href,
                    "snippet": snippet_tag.get_text() if snippet_tag else "",
                })
        return results[:10]
    except requests.RequestException:
        return []


def _fallback_hunter_io(domain: str) -> list[str]:
    """Busca e-mails do domínio via API do Hunter.io."""
    if not HUNTER_IO_API_KEY or not domain:
        return []
    print(f"  [Hunter.io] Buscando contatos para o domínio: {domain}...")
    try:
        url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={HUNTER_IO_API_KEY}&type=personal"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            emails = []
            for em in data.get('data', {}).get('emails', []):
                # Filtra por departamentos úteis se possível, ou pega todos
                dept = em.get('department')
                if dept in ['hr', 'executive', 'management'] or not dept:
                    emails.append(em.get('value', ''))
            return [e for e in emails if e]
    except Exception as e:
        print(f"  [Hunter.io] Erro: {e}")
    return []


def _fallback_apollo_io(domain: str) -> list[str]:
    """Busca e-mails do domínio via API do Apollo.io."""
    if not APOLLO_IO_API_KEY or not domain:
        return []
    print(f"  [Apollo.io] Buscando contatos de RH para: {domain}...")
    try:
        url = "https://api.apollo.io/v1/mixed_people/search"
        headers = {
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
        }
        payload = {
            "api_key": APOLLO_IO_API_KEY,
            "q_organization_domains": domain,
            "person_titles": ["recruiter", "hr", "talent", "human resources", "recrutamento", "tech recruiter"],
            "page": 1
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            emails = []
            for person in data.get('people', []):
                email = person.get('email')
                if email:
                    emails.append(email)
            return emails
    except Exception as e:
        print(f"  [Apollo.io] Erro: {e}")
    return []


def find_company_email(company_name: str) -> dict:
    """Pesquisa email de contato/RH de uma empresa."""
    print(f"  🔎 Pesquisando contato: {company_name}...")
    result = {"email": "", "website": "", "metodo": ""}
    all_emails: list[str] = []
    website_url: str = ""

    # Queries prioritárias: foco em RH, vagas e recrutamento
    hr_queries = [
        f'"{company_name}" email rh vagas site:br',
        f'"{company_name}" curriculo vagas contato',
        f'"{company_name}" vagas.com.br contato',
        f'"{company_name}" indeed.com contato',
        f'"{company_name}" linkedin vagas email',
        f'"{company_name}" trabalhos contato email',
    ]

    # ── Etapa 1: Busca focada em RH/vagas ─────────────────────────
    for query in hr_queries:
        _random_delay(0.3, 0.7)
        search_results = _search_google(query) or _search_duckduckgo(query)

        for r in search_results[:6]:
            snippet_emails = _extract_emails(r.get("snippet", ""))
            all_emails.extend(snippet_emails)

            url = r.get("url", "")
            company_slug = company_name.lower().replace(" ", "")
            is_company_site = any(
                x in url.lower()
                for x in [company_slug[:8], "contato", "contact", "trabalhe", "careers", "vagas"]
            )

            if is_company_site and not website_url:
                parsed = urlparse(url)
                website_url = f"{parsed.scheme}://{parsed.netloc}"
                result["website"] = website_url
                # Scraping da página encontrada
                page_emails = _scrape_page_emails(url)
                all_emails.extend(page_emails)

        if all_emails:
            break

    # ── Etapa 2: Tentar páginas /contato /carreiras do site ────────
    if website_url and not all_emails:
        _random_delay(0.3, 0.7)
        contact_pages = _find_contact_pages(website_url)
        for page_url in contact_pages:
            page_emails = _scrape_page_emails(page_url)
            all_emails.extend(page_emails)
            if all_emails:
                break

    # ── Etapa 3: Fallback — busca qualquer email da empresa ────────
    if not all_emails:
        print(f"  🔄 Buscando por vagas.com.br e indeed...")
        fallback_queries = [
            f'"{company_name}" vagas.com.br contato',
            f'"{company_name}" indeed.com.br contato',
            f'"{company_name}" wellfound.com contato',
            f'"{company_name}" careers contact email',
        ]
        for query in fallback_queries:
            _random_delay(0.3, 0.7)
            search_results = _search_google(query) or _search_duckduckgo(query)

            for r in search_results[:8]:
                # Verifica snippet e title por emails
                combined_text = r.get("snippet", "") + " " + r.get("title", "")
                snippet_emails = _extract_emails(combined_text)
                all_emails.extend(snippet_emails)

                # Visita a página se parecer do site da empresa
                url = r.get("url", "")
                company_slug = company_name.lower().replace(" ", "")[:8]
                if company_slug in url.lower() and not website_url:
                    website_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                    result["website"] = website_url
                    page_emails = _scrape_page_emails(url)
                    all_emails.extend(page_emails)

                    # Tenta também a homepage
                    home_emails = _scrape_page_emails(website_url)
                    all_emails.extend(home_emails)

            if all_emails:
                break

    # ── Etapa 4: APIs Oficiais (Fallback) ─────────────────────────
    if not all_emails and website_url:
        parsed = urlparse(website_url)
        domain = parsed.netloc.replace("www.", "")
        
        # Tenta Hunter.io
        api_emails = _fallback_hunter_io(domain)
        if not api_emails:
            # Tenta Apollo.io se Hunter falhar
            api_emails = _fallback_apollo_io(domain)
        
        if api_emails:
            all_emails.extend(api_emails)
            result["metodo"] = "api_fallback"

    # ── Resultado ─────────────────────────────────────────────────
    if all_emails:
        best = _prioritize_emails(list(set(all_emails)))[0]
        result["email"] = best
        if not result.get("metodo"):
            result["metodo"] = "pesquisa_web"
        print(f"  📧 Email encontrado: {best} (Fonte: {result['metodo']})")
    else:
        print(f"  ⚠ Nenhum email encontrado para {company_name}")

    return result

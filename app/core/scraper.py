"""
Módulo de Busca de Vagas — v5 (BR + Internacional)
Busca vagas em fontes nativas BR + internacionais com filtro rígido de localidade.

Fontes BR: Gupy RSS, Vagas.com.br, Remotive API, Programathor, GeekHunter, Remotar, Trampos.co
Fontes internacionais: RemoteOK, WeWorkRemotely, Wellfound, Google, DuckDuckGo
Filtro: presencial apenas Recife/Jaboatão/Olinda; remoto para qualquer localidade.
"""

import os
import sys
import random
import re
import time
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

from app.config import settings


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

# ── Categorias de vagas ───────────────────────────────────────────
JOB_CATEGORIES_PT = [
    "desenvolvedor de software",
    "analista de dados",
    "suporte de TI",
    "help desk",
    "desenvolvedor python",
    "desenvolvedor web",
    "analista de sistemas",
]

JOB_CATEGORIES_EN = [
    "software developer",
    "data analyst",
    "IT support",
    "QA engineer",
    "python developer",
]

# ── Localidade ────────────────────────────────────────────────────
PRESENCIAL_ALLOWED = [c.lower() for c in settings.PRESENCIAL_CITIES]

DELAY_MIN = float(settings.REQUEST_DELAY_MIN) if settings.REQUEST_DELAY_MIN else 0.5
DELAY_MAX = float(settings.REQUEST_DELAY_MAX) if settings.REQUEST_DELAY_MAX else 1.5

BLOCK_SIGNALS = [
    "captcha", "robot", "automated", "please verify",
    "access denied", "cloudflare", "just a moment",
    "challenge-platform", "security check",
]

_stats = {
    "google": {"ok": 0, "blocked": 0, "error": 0},
    "duckduckgo": {"ok": 0, "blocked": 0, "error": 0},
    "remoteok": {"ok": 0, "blocked": 0, "error": 0},
    "weworkremotely": {"ok": 0, "blocked": 0, "error": 0},
    "wellfound": {"ok": 0, "blocked": 0, "error": 0},
    "gupy": {"ok": 0, "blocked": 0, "error": 0},
    "vagascom": {"ok": 0, "blocked": 0, "error": 0},
    "remotive": {"ok": 0, "blocked": 0, "error": 0},
    "programathor": {"ok": 0, "blocked": 0, "error": 0},
    "geekhunter": {"ok": 0, "blocked": 0, "error": 0},
    "remotar": {"ok": 0, "blocked": 0, "error": 0},
    "trampos": {"ok": 0, "blocked": 0, "error": 0},
    "adzuna": {"ok": 0, "blocked": 0, "error": 0},
    "jsearch": {"ok": 0, "blocked": 0, "error": 0},
}


def get_stats() -> dict:
    return _stats


def _get_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }


def _random_delay(min_s=None, max_s=None):
    lo = min_s if min_s is not None else DELAY_MIN
    hi = max_s if max_s is not None else DELAY_MAX
    time.sleep(random.uniform(lo, hi))


def _clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _is_blocked(response):
    if response.status_code in (403, 429, 503):
        return True
    text_lower = response.text[:2000].lower()
    return any(sig in text_lower for sig in BLOCK_SIGNALS)


def _safe_get(url, params=None, timeout=10, source="", json=False):
    try:
        headers = _get_headers()
        if json:
            headers["Accept"] = "application/json"
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        if _is_blocked(response):
            if source and source in _stats:
                _stats[source]["blocked"] += 1
            return None
        if source and source in _stats:
            _stats[source]["ok"] += 1
        return response
    except (requests.Timeout, requests.RequestException):
        if source and source in _stats:
            _stats[source]["error"] += 1
        return None


def _log(msg):
    print(msg)
    sys.stdout.flush()


def _extract_email_from_text(text: str) -> str:
    """Extrai o primeiro email encontrado no texto da vaga."""
    if not text:
        return ""
    emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    # Filtrar emails genéricos de plataformas
    blocked_domains = ["gupy.io", "indeed.com", "linkedin.com", "glassdoor.com", "catho.com.br", "noreply", "no-reply", "vagas.com"]
    for email in emails:
        email_lower = email.lower()
        if not any(blocked in email_lower for blocked in blocked_domains):
            return email_lower
    return ""


# ═══════════════════════════════════════════════════════════════════════
#  FILTRO DE LOCALIDADE
# ═══════════════════════════════════════════════════════════════════════

REMOTE_KEYWORDS = ["remoto", "remote", "home office", "homeoffice", "home-office", "híbrido", "hibrido", "hybrid"]
UNDEFINED_LOCATIONS = ["brasil", "brazil", "", "não informado", "nao informado", "nacional", "qualquer lugar"]


def _is_location_allowed(job: dict) -> bool:
    """
    Retorna True se a vaga pode ser candidatada:
    - Vagas remotas/híbridas: SEMPRE aceitas
    - Vagas presenciais: apenas Recife, Jaboatão dos Guararapes e Olinda
    - Vagas sem localidade definida: aceitas (serão avaliadas depois)
    """
    local = job.get("local", "").lower().strip()
    modalidade = job.get("modalidade", "").lower().strip()
    titulo = job.get("titulo", "").lower()
    descricao = job.get("descricao", "").lower()

    # Checar se é remoto/híbrido em qualquer campo
    all_text = f"{local} {modalidade} {titulo} {descricao[:200]}"
    if any(k in all_text for k in REMOTE_KEYWORDS):
        return True

    # Localidade indefinida — aceitar (sem informação)
    if local in UNDEFINED_LOCATIONS or not local:
        return settings.ACCEPT_UNDEFINED_LOCATION

    # Presencial — verificar cidade
    for city in PRESENCIAL_ALLOWED:
        if city in local:
            return True

    # Bloquear outras cidades presenciais
    return False


# ═══════════════════════════════════════════════════════════════════════
#  SCRAPERS BR NATIVOS
# ═══════════════════════════════════════════════════════════════════════

def _search_gupy_rss(query: str) -> list:
    """
    Busca vagas no Gupy via RSS/sitemap.
    Usa busca DuckDuckGo focada em gupy.io como fallback.
    """
    jobs = []
    try:
        # Tentativa direta via DuckDuckGo site:gupy.io
        ddg_url = "https://html.duckduckgo.com/html/"
        search_terms = [
            f"site:gupy.io {query}",
            f"site:gupy.io/jobs {query} remoto",
        ]
        for term in search_terms:
            params = {"q": term}
            response = requests.post(ddg_url, data=params, headers=_get_headers(), timeout=10)
            if not response or response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, "lxml")
            for result in soup.find_all("div", class_="result"):
                title_tag = result.find("a", class_="result__a")
                snippet_tag = result.find("a", class_="result__snippet")
                if not title_tag:
                    continue

                href = title_tag.get("href", "")
                if "gupy.io" not in href:
                    continue

                title_text = _clean_text(title_tag.get_text())
                snippet_text = _clean_text(snippet_tag.get_text()) if snippet_tag else ""

                # Extrair empresa da URL (formato: empresa.gupy.io)
                empresa = ""
                m = re.search(r"https?://([^.]+)\.gupy\.io", href)
                if m:
                    empresa = m.group(1).replace("-", " ").title()

                if not empresa:
                    empresa = _extract_company_from_result(title_text, snippet_text, href)

                titulo = _clean_title_gupy(title_text)
                local = _extract_location(snippet_text + " " + title_text)

                if titulo:
                    jobs.append({
                        "titulo": titulo,
                        "empresa": empresa or "Empresa no Gupy",
                        "local": local,
                        "modalidade": _detect_modalidade(title_text + " " + snippet_text),
                        "url": href,
                        "descricao": snippet_text,
                        "fonte": "Gupy",
                    })
                if len(jobs) >= 10:
                    break

            _random_delay(0.5, 1)
            if len(jobs) >= 8:
                break

        _stats["gupy"]["ok"] += 1 if jobs else 0
    except Exception as e:
        _stats["gupy"]["error"] += 1
    return jobs


def _clean_title_gupy(title: str) -> str:
    """Remove sufixos de sites do título."""
    title = re.sub(r"\s*[-–|]\s*Gupy.*$", "", title, flags=re.I)
    title = re.sub(r"\s*[-–|]\s*vagas?.*$", "", title, flags=re.I)
    return title.strip()


def _detect_modalidade(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["híbrido", "hibrido", "hybrid"]):
        return "híbrido"
    if any(k in t for k in ["remoto", "remote", "home office"]):
        return "remoto"
    if "presencial" in t:
        return "presencial"
    return ""


def _search_vagascom(query: str) -> list:
    """Busca vagas no Vagas.com.br via scraping HTML."""
    jobs = []
    try:
        # Vagas.com.br usa URL pattern: /empregos/cargo-empresa-cidade
        query_slug = query.lower().replace(" ", "-")
        urls_to_try = [
            f"https://www.vagas.com.br/empregos/{query_slug}",
            f"https://www.vagas.com.br/vagas-de-{query_slug}",
        ]

        for url in urls_to_try:
            response = _safe_get(url, timeout=10, source="vagascom")
            if not response:
                continue

            soup = BeautifulSoup(response.text, "lxml")

            # Vagas.com.br lista vagas em elementos com class "job"
            job_items = (
                soup.find_all("li", class_=lambda c: c and "job" in c.lower()) or
                soup.find_all("article", class_=lambda c: c and "job" in c.lower()) or
                soup.find_all("div", class_=lambda c: c and ("vaga" in c.lower() or "job" in c.lower()))
            )

            for item in job_items:
                title_tag = item.find(["h2", "h3", "a"], class_=lambda c: c and ("title" in (c or "").lower() or "vaga" in (c or "").lower()))
                if not title_tag:
                    title_tag = item.find(["h2", "h3"])
                if not title_tag:
                    continue

                titulo = _clean_text(title_tag.get_text())
                if not titulo:
                    continue

                link_tag = item.find("a", href=True)
                href = ""
                if link_tag:
                    href = link_tag.get("href", "")
                    if href.startswith("/"):
                        href = "https://www.vagas.com.br" + href

                empresa_tag = item.find(class_=lambda c: c and ("company" in (c or "").lower() or "empresa" in (c or "").lower()))
                empresa = _clean_text(empresa_tag.get_text()) if empresa_tag else ""

                local_tag = item.find(class_=lambda c: c and ("location" in (c or "").lower() or "local" in (c or "").lower() or "cidade" in (c or "").lower()))
                local = _clean_text(local_tag.get_text()) if local_tag else "Brasil"

                jobs.append({
                    "titulo": titulo,
                    "empresa": empresa or "Empresa no Vagas.com.br",
                    "local": local,
                    "modalidade": _detect_modalidade(titulo + " " + local),
                    "url": href,
                    "descricao": f"Vaga de {titulo} em {local} via Vagas.com.br",
                    "fonte": "Vagas.com.br",
                })

                if len(jobs) >= 10:
                    break

            if len(jobs) >= 5:
                break

    except Exception:
        _stats["vagascom"]["error"] += 1
    return jobs


def _search_remotive(query: str) -> list:
    """
    Busca vagas remotas no Remotive via API JSON pública.
    API gratuita sem autenticação: https://remotive.com/api/remote-jobs
    """
    jobs = []
    try:
        url = "https://remotive.com/api/remote-jobs"
        params = {"search": query, "limit": 20}
        response = _safe_get(url, params=params, timeout=12, source="remotive", json=True)
        if not response:
            return jobs

        data = response.json()
        job_list = data.get("jobs", [])

        for item in job_list:
            titulo = item.get("title", "")
            empresa = item.get("company_name", "Unknown")
            local = item.get("candidate_required_location", "Remote")
            url_vaga = item.get("url", "")
            descricao_html = item.get("description", "")
            descricao = _clean_text(BeautifulSoup(descricao_html, "lxml").get_text())[:500]

            jobs.append({
                "titulo": titulo,
                "empresa": empresa,
                "local": local or "Remote",
                "modalidade": "remoto",
                "url": url_vaga,
                "descricao": descricao,
                "fonte": "Remotive",
            })

            if len(jobs) >= 10:
                break

        _stats["remotive"]["ok"] += 1
    except Exception:
        _stats["remotive"]["error"] += 1
    return jobs


def _search_programathor(query: str) -> list:
    """Busca vagas de desenvolvimento no Programathor via scraping."""
    jobs = []
    try:
        query_slug = query.lower().replace(" ", "+")
        url = f"https://programathor.com.br/jobs?search={query_slug}"
        response = _safe_get(url, timeout=10, source="programathor")
        if not response:
            return jobs

        soup = BeautifulSoup(response.text, "lxml")

        # Programathor lista vagas em cards
        cards = (
            soup.find_all("div", class_=lambda c: c and "job" in (c or "").lower()) or
            soup.find_all("article") or
            soup.find_all("div", class_=lambda c: c and "card" in (c or "").lower())
        )

        for card in cards:
            title_tag = card.find(["h2", "h3", "h4", "a"])
            if not title_tag:
                continue

            titulo = _clean_text(title_tag.get_text())
            if len(titulo) < 5:
                continue

            link_tag = card.find("a", href=True)
            href = ""
            if link_tag:
                href = link_tag.get("href", "")
                if href.startswith("/"):
                    href = "https://programathor.com.br" + href

            # Empresa
            empresa_candidates = card.find_all(["span", "p", "div"])
            empresa = ""
            for ec in empresa_candidates:
                text = _clean_text(ec.get_text())
                if text and len(text) > 2 and len(text) < 60 and text != titulo:
                    empresa = text
                    break

            local_text = _clean_text(card.get_text())
            local = _extract_location(local_text)

            jobs.append({
                "titulo": titulo,
                "empresa": empresa or "Empresa no Programathor",
                "local": local,
                "modalidade": _detect_modalidade(local_text),
                "url": href,
                "descricao": f"Vaga de {titulo} via Programathor",
                "fonte": "Programathor",
            })

            if len(jobs) >= 8:
                break

    except Exception:
        _stats["programathor"]["error"] += 1
    return jobs


def _search_geekhunter(query: str) -> list:
    """Busca vagas de dev no GeekHunter via scraping HTML."""
    jobs = []
    try:
        query_slug = query.lower().replace(" ", "-")
        urls_to_try = [
            f"https://www.geekhunter.com.br/vagas?search={query.replace(' ', '+')}",
            "https://www.geekhunter.com.br/vagas",
        ]

        for url in urls_to_try:
            response = _safe_get(url, timeout=10, source="geekhunter")
            if not response:
                continue

            soup = BeautifulSoup(response.text, "lxml")

            job_items = (
                soup.find_all("div", class_=lambda c: c and "job" in (c or "").lower()) or
                soup.find_all("li", class_=lambda c: c and "job" in (c or "").lower()) or
                soup.find_all("article")
            )

            for item in job_items:
                title_tag = item.find(["h2", "h3", "h4"])
                if not title_tag:
                    continue

                titulo = _clean_text(title_tag.get_text())
                if not titulo or len(titulo) < 5:
                    continue

                link_tag = item.find("a", href=True)
                href = ""
                if link_tag:
                    href = link_tag.get("href", "")
                    if href.startswith("/"):
                        href = "https://www.geekhunter.com.br" + href

                local_text = _clean_text(item.get_text())
                local = _extract_location(local_text)

                jobs.append({
                    "titulo": titulo,
                    "empresa": "Empresa no GeekHunter",
                    "local": local,
                    "modalidade": _detect_modalidade(local_text),
                    "url": href,
                    "descricao": f"Vaga de {titulo} via GeekHunter",
                    "fonte": "GeekHunter",
                })

                if len(jobs) >= 8:
                    break

            if jobs:
                break

    except Exception:
        _stats["geekhunter"]["error"] += 1
    return jobs


def _search_remotar(query: str) -> list:
    """Busca vagas 100% remotas no Remotar.com.br."""
    jobs = []
    try:
        url = "https://remotar.com.br/jobs"
        response = _safe_get(url, timeout=10, source="remotar")
        if not response:
            return jobs

        soup = BeautifulSoup(response.text, "lxml")
        query_words = query.lower().split()

        job_items = (
            soup.find_all("div", class_=lambda c: c and "job" in (c or "").lower()) or
            soup.find_all("article") or
            soup.find_all("li")
        )

        for item in job_items:
            item_text = item.get_text().lower()
            if not any(w in item_text for w in query_words[:2]):
                continue

            title_tag = item.find(["h2", "h3", "h4", "a"])
            if not title_tag:
                continue

            titulo = _clean_text(title_tag.get_text())
            if not titulo or len(titulo) < 5:
                continue

            link_tag = item.find("a", href=True)
            href = ""
            if link_tag:
                href = link_tag.get("href", "")
                if href.startswith("/"):
                    href = "https://remotar.com.br" + href

            jobs.append({
                "titulo": titulo,
                "empresa": "Empresa no Remotar",
                "local": "Remoto",
                "modalidade": "remoto",
                "url": href,
                "descricao": f"Vaga remota de {titulo} via Remotar.com.br",
                "fonte": "Remotar",
            })

            if len(jobs) >= 8:
                break

    except Exception:
        _stats["remotar"]["error"] += 1
    return jobs


def _search_trampos(query: str) -> list:
    """Busca vagas criativas/dev no Trampos.co."""
    jobs = []
    try:
        url = f"https://trampos.co/vagas?s={query.replace(' ', '+')}"
        response = _safe_get(url, timeout=10, source="trampos")
        if not response:
            return jobs

        soup = BeautifulSoup(response.text, "lxml")

        job_items = (
            soup.find_all("li", class_=lambda c: c and "job" in (c or "").lower()) or
            soup.find_all("div", class_=lambda c: c and "job" in (c or "").lower()) or
            soup.find_all("article")
        )

        for item in job_items:
            title_tag = item.find(["h2", "h3", "a"])
            if not title_tag:
                continue

            titulo = _clean_text(title_tag.get_text())
            if not titulo or len(titulo) < 5:
                continue

            link_tag = item.find("a", href=True)
            href = ""
            if link_tag:
                href = link_tag.get("href", "")
                if href.startswith("/"):
                    href = "https://trampos.co" + href

            local_text = _clean_text(item.get_text())
            local = _extract_location(local_text)

            jobs.append({
                "titulo": titulo,
                "empresa": "Empresa no Trampos.co",
                "local": local,
                "modalidade": _detect_modalidade(local_text),
                "url": href,
                "descricao": f"Vaga de {titulo} via Trampos.co",
                "fonte": "Trampos.co",
            })

            if len(jobs) >= 8:
                break

    except Exception:
        _stats["trampos"]["error"] += 1
    return jobs


def _search_adzuna(query: str) -> list:
    """
    Busca vagas na API Adzuna (vagas BR e internacionais remotas).
    Docs: https://developer.adzuna.com/
    """
    jobs = []
    app_id = settings.ADZUNA_APP_ID
    app_key = settings.ADZUNA_APP_KEY
    if not app_id or not app_key:
        return jobs

    # Buscar vagas no Brasil + remotas internacionais
    searches = [
        {"country": "br", "what": query, "where": "", "label": "BR"},
        {"country": "br", "what": f"{query} remoto", "where": "", "label": "BR Remoto"},
        {"country": "gb", "what": f"{query} remote", "where": "", "label": "UK Remote"},
        {"country": "us", "what": f"{query} remote", "where": "", "label": "US Remote"},
    ]

    for search in searches:
        try:
            country = search["country"]
            url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
            params = {
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": 10,
                "what": search["what"],
                "content-type": "application/json",
            }
            if search["where"]:
                params["where"] = search["where"]

            response = requests.get(url, params=params, timeout=12)
            if response.status_code != 200:
                _stats["adzuna"]["error"] += 1
                continue

            data = response.json()
            results = data.get("results", [])
            _stats["adzuna"]["ok"] += 1

            for item in results:
                titulo = item.get("title", "")
                empresa = item.get("company", {}).get("display_name", "Empresa")
                local = item.get("location", {}).get("display_name", "")
                descricao = _clean_text(item.get("description", ""))[:500]
                url_vaga = item.get("redirect_url", "")

                # Extrair email da descrição
                email_direto = _extract_email_from_text(descricao)

                job_data = {
                    "titulo": _clean_text(titulo),
                    "empresa": empresa,
                    "local": local or ("Remote" if "remote" in search["what"].lower() else "Brasil"),
                    "modalidade": _detect_modalidade(f"{titulo} {descricao} {local}"),
                    "url": url_vaga,
                    "descricao": descricao,
                    "fonte": f"Adzuna ({search['label']})",
                }
                if email_direto:
                    job_data["email_direto"] = email_direto

                jobs.append(job_data)

                if len(jobs) >= 20:
                    break

            _random_delay(0.3, 0.6)

        except Exception as e:
            _stats["adzuna"]["error"] += 1
            _log(f"  ❌ Adzuna ({search['label']}): {e}")

    return jobs


def _search_jsearch(query: str) -> list:
    """
    Busca vagas via JSearch (RapidAPI) — vagas locais e remotas.
    Docs: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
    """
    jobs = []
    api_key = settings.RAPIDAPI_KEY
    if not api_key:
        return jobs

    # Busca híbrida: presenciais em Recife + remotas BR + remotas exterior
    searches = [
        {"query": f"{query} in Recife, Brazil", "label": "Recife"},
        {"query": f"{query} remote in Brazil", "label": "BR Remoto"},
        {"query": f"{query} remote", "label": "Global Remoto"},
    ]

    for search in searches:
        try:
            url = "https://jsearch.p.rapidapi.com/search"
            params = {
                "query": search["query"],
                "num_pages": "1",
                "date_posted": "week",
            }
            headers = {
                "x-rapidapi-host": "jsearch.p.rapidapi.com",
                "x-rapidapi-key": api_key,
                "Content-Type": "application/json",
            }

            response = requests.get(url, params=params, headers=headers, timeout=15)
            if response.status_code != 200:
                _stats["jsearch"]["error"] += 1
                continue

            data = response.json()
            results = data.get("data", [])
            _stats["jsearch"]["ok"] += 1

            for item in results:
                titulo = item.get("job_title", "")
                empresa = item.get("employer_name", "Empresa")
                cidade = item.get("job_city", "")
                estado = item.get("job_state", "")
                pais = item.get("job_country", "")
                is_remote = item.get("job_is_remote", False)
                descricao = _clean_text(item.get("job_description", ""))[:500]
                url_vaga = item.get("job_apply_link", "") or item.get("job_google_link", "")

                local = ""
                if is_remote:
                    local = "Remote"
                elif cidade:
                    local = f"{cidade}, {estado}" if estado else cidade
                    if pais and pais != "BR":
                        local += f" - {pais}"
                else:
                    local = pais or "Brasil"

                # Extrair email da descrição
                email_direto = _extract_email_from_text(descricao)

                job_data = {
                    "titulo": _clean_text(titulo),
                    "empresa": empresa,
                    "local": local,
                    "modalidade": "remoto" if is_remote else _detect_modalidade(f"{titulo} {local} {descricao}"),
                    "url": url_vaga,
                    "descricao": descricao,
                    "fonte": f"JSearch ({search['label']})",
                }
                if email_direto:
                    job_data["email_direto"] = email_direto

                jobs.append(job_data)

                if len(jobs) >= 20:
                    break

            _random_delay(0.5, 1.0)

        except Exception as e:
            _stats["jsearch"]["error"] += 1
            _log(f"  ❌ JSearch ({search['label']}): {e}")

    return jobs


# ═══════════════════════════════════════════════════════════════════════
#  FONTES INTERNACIONAIS (mantidas do v4)
# ═══════════════════════════════════════════════════════════════════════

def _search_google_jobs(query):
    jobs = []
    try:
        url = "https://www.google.com/search"
        params = {"q": f"vaga {query}", "num": 15, "hl": "pt-BR"}
        response = _safe_get(url, params=params, timeout=8, source="google")
        if not response:
            return jobs
        soup = BeautifulSoup(response.text, "lxml")
        for g in soup.find_all("div", class_="g"):
            title_tag = g.find("h3")
            link_tag = g.find("a")
            snippet_tag = g.find("div", class_="VwiC3b") or g.find("span", class_="st")
            if not title_tag:
                continue
            title_text = _clean_text(title_tag.get_text())
            snippet_text = _clean_text(snippet_tag.get_text()) if snippet_tag else ""
            href = ""
            if link_tag:
                href = link_tag.get("href", "")
                if href.startswith("/url?q="):
                    href = href.split("/url?q=")[1].split("&")[0]
            empresa = _extract_company_from_result(title_text, snippet_text, href)
            titulo = _extract_job_title(title_text, query)
            if empresa and titulo:
                jobs.append({
                    "titulo": titulo, "empresa": empresa,
                    "local": _extract_location(snippet_text),
                    "modalidade": _detect_modalidade(snippet_text + " " + titulo),
                    "url": href if href.startswith("http") else "",
                    "descricao": snippet_text, "fonte": "Google",
                })
            if len(jobs) >= 8:
                break
    except Exception:
        pass
    return jobs


def _search_duckduckgo_jobs(query):
    jobs = []
    try:
        url = "https://html.duckduckgo.com/html/"
        params = {"q": f"vaga {query} email contato"}
        response = requests.post(url, data=params, headers=_get_headers(), timeout=8)
        if not response or response.status_code != 200:
            _stats["duckduckgo"]["error"] += 1
            return jobs
        _stats["duckduckgo"]["ok"] += 1
        soup = BeautifulSoup(response.text, "lxml")
        for result in soup.find_all("div", class_="result"):
            title_tag = result.find("a", class_="result__a")
            snippet_tag = result.find("a", class_="result__snippet")
            if not title_tag:
                continue
            title_text = _clean_text(title_tag.get_text())
            snippet_text = _clean_text(snippet_tag.get_text()) if snippet_tag else ""
            href = title_tag.get("href", "")
            empresa = _extract_company_from_result(title_text, snippet_text, href)
            titulo = _extract_job_title(title_text, query)
            if empresa and titulo:
                email_direto = _extract_email_from_text(snippet_text)
                job_data = {
                    "titulo": titulo, "empresa": empresa,
                    "local": _extract_location(snippet_text),
                    "modalidade": _detect_modalidade(snippet_text + " " + titulo),
                    "url": href if href.startswith("http") else "",
                    "descricao": snippet_text, "fonte": "DuckDuckGo",
                }
                if email_direto:
                    job_data["email_direto"] = email_direto
                jobs.append(job_data)
            if len(jobs) >= 8:
                break
    except Exception:
        _stats["duckduckgo"]["error"] += 1
    return jobs


def _search_remoteok(query):
    """Busca vagas no Remote OK via API JSON pública."""
    jobs = []
    try:
        url = "https://remoteok.com/api"
        headers = _get_headers()
        headers["Accept"] = "application/json"
        response = requests.get(url, headers=headers, timeout=10)
        if not response or response.status_code != 200:
            _stats["remoteok"]["error"] += 1
            return jobs

        _stats["remoteok"]["ok"] += 1
        data = response.json()

        query_words = query.lower().split()
        for item in data:
            if not isinstance(item, dict) or not item.get("position"):
                continue
            combined = f"{item.get('position', '')} {item.get('company', '')} {item.get('description', '')[:200]}".lower()
            if not any(w in combined for w in query_words):
                continue
            jobs.append({
                "titulo": item.get("position", ""),
                "empresa": item.get("company", "Unknown"),
                "local": item.get("location", "Remote"),
                "modalidade": "remoto",
                "url": item.get("url", f"https://remoteok.com/remote-jobs/{item.get('slug', '')}"),
                "descricao": _clean_text(BeautifulSoup(item.get("description", ""), "lxml").get_text())[:500],
                "fonte": "RemoteOK",
            })
            if len(jobs) >= 8:
                break
    except Exception:
        _stats["remoteok"]["error"] += 1
    return jobs


def _search_weworkremotely(query):
    """Busca vagas no We Work Remotely via RSS feed."""
    jobs = []
    feeds = [
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
        "https://weworkremotely.com/remote-jobs.rss",
    ]
    query_words = query.lower().split()

    for feed_url in feeds:
        try:
            response = requests.get(feed_url, headers=_get_headers(), timeout=10)
            if not response or response.status_code != 200:
                continue
            _stats["weworkremotely"]["ok"] += 1
            root = ET.fromstring(response.content)

            for item in root.findall(".//item"):
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                desc = item.findtext("description", "")

                combined = f"{title} {desc[:200]}".lower()
                if not any(w in combined for w in query_words):
                    continue

                parts = title.split(":", 1)
                if len(parts) == 2:
                    empresa = parts[0].strip()
                    titulo = parts[1].strip()
                else:
                    empresa = "Unknown"
                    titulo = title

                desc_text = _clean_text(BeautifulSoup(desc, "lxml").get_text())[:500] if desc else ""

                jobs.append({
                    "titulo": titulo, "empresa": empresa,
                    "local": "Remote", "modalidade": "remoto",
                    "url": link,
                    "descricao": desc_text,
                    "fonte": "WeWorkRemotely",
                })
                if len(jobs) >= 8:
                    break
        except Exception:
            _stats["weworkremotely"]["error"] += 1

        if len(jobs) >= 8:
            break
    return jobs


def _search_wellfound(query):
    """Busca vagas no Wellfound via Google site: search (JS-heavy site)."""
    jobs = []
    try:
        ddg_url = "https://html.duckduckgo.com/html/"
        ddg_params = {"q": f"site:wellfound.com {query} remote job"}
        response = requests.post(ddg_url, data=ddg_params, headers=_get_headers(), timeout=8)
        if not response or response.status_code != 200:
            return jobs

        soup = BeautifulSoup(response.text, "lxml")

        for result in soup.find_all("div", class_="result"):
            title_tag = result.find("a", class_="result__a")
            snippet_tag = result.find("a", class_="result__snippet")
            if not title_tag:
                continue
            title_text = _clean_text(title_tag.get_text())
            href = title_tag.get("href", "")
            if "wellfound.com" not in href:
                continue
            snippet_text = _clean_text(snippet_tag.get_text()) if snippet_tag else ""
            title_clean = re.sub(r"\s*[-–|]\s*Wellfound.*$", "", title_text, flags=re.I)
            parts = re.split(r"\s+at\s+", title_clean, maxsplit=1)
            titulo = parts[0].strip() if parts else title_clean
            empresa = parts[1].strip() if len(parts) == 2 else "Startup"
            if titulo:
                jobs.append({
                    "titulo": titulo, "empresa": empresa,
                    "local": "Remote", "modalidade": "remoto", "url": href,
                    "descricao": snippet_text, "fonte": "Wellfound",
                })
            if len(jobs) >= 8:
                break

        _stats["wellfound"]["ok"] += 1
    except Exception:
        _stats["wellfound"]["error"] += 1
    return jobs


# ═══════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════

_SKIP_DOMAINS = [
    "youtube.com", "wikipedia.org", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "reddit.com", "tiktok.com",
]

_JOB_SITE_PATTERNS = [
    "linkedin.com", "indeed.com", "glassdoor.com", "vagas.com",
    "gupy.io", "catho.com", "infojobs.com", "trabalhabrasil.com",
    "netvagas.com", "empregos.com", "trampos.co", "programathor.com",
    "geekhunter.com", "remotar.com", "wellfound.com", "remoteok.com",
    "weworkremotely.com", "remotive.com", "careers", "vagas", "jobs",
]


def _extract_company_from_result(title, snippet, url):
    patterns = [
        r"(?:na|em|at)\s+([A-Z][A-Za-zÀ-ú\s&.]+?)(?:\s*[-–|]|\s+contrat|\s+busca|\s+procura|$)",
        r"([A-Z][A-Za-zÀ-ú\s&.]{2,30})\s+(?:contrat|busca|procura|está com|oferece|abre)",
        r"[-–|]\s*([A-Z][A-Za-zÀ-ú\s&.]{2,30})\s*(?:[-–|]|$)",
        r"([A-Z][A-Za-zÀ-ú\s&.]{2,25})\s*[-–|]",
    ]
    for text in [title, snippet]:
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                company = m.group(1).strip().rstrip(".-– ")
                if company.lower() not in [
                    "vaga", "vagas", "emprego", "empregos", "oportunidade",
                    "remoto", "junior", "pleno", "senior", "estágio",
                    "glassdoor", "catho",
                ]:
                    return company
    if url:
        for site in _JOB_SITE_PATTERNS:
            if site in url.lower():
                parts = re.split(r'\s*[-–|]\s*', title)
                for part in parts:
                    part = part.strip()
                    if (len(part) > 2 and
                        part.lower() not in ["linkedin", "indeed", "glassdoor", "catho",
                                              "vagas.com", "gupy", "infojobs", "wellfound"] and
                        not any(kw in part.lower() for kw in ["vaga", "emprego", "junior", "estágio"])):
                        return part
                break
    return ""


def _extract_job_title(title, query):
    parts = re.split(r'\s*[-–|]\s*', title)
    if len(parts) >= 2:
        candidate = parts[0].strip()
        if any(kw in candidate.lower() for kw in [
            "desenvolv", "analista", "suporte", "help desk", "qa", "test",
            "estagi", "junior", "cientista", "dados", "python", "java",
            "programad", "técnico", "engineer", "developer", "software",
        ]):
            return candidate
    query_words = query.lower().split()
    if any(w in title.lower() for w in query_words[:2]):
        clean = re.sub(r'\s*[-–|]\s*(?:LinkedIn|Indeed|Glassdoor|Catho|Gupy|Wellfound).*$', '', title, flags=re.I)
        return clean.strip()
    return ""


def _extract_location(text):
    loc_patterns = [
        r"(Remoto|Remote|Home\s*Office|Híbrido|Hybrid)",
        r"(Recife|Olinda|Jaboatão dos Guararapes|Cabo de Santo Agostinho|São Paulo|Rio de Janeiro|Belo Horizonte|Porto Alegre|Curitiba|Brasília|Salvador|Fortaleza|Campinas)",
        r"(Lisboa|Porto|Braga|Coimbra|Portugal)",
        r"([A-Z][a-zà-ú]+(?:\s+(?:do|de|dos|das)\s+[A-Z][a-zà-ú]+)*\s*[-,]\s*[A-Z]{2})",
    ]
    for pattern in loc_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return "Brasil"


def _is_junior_job(title):
    t = title.lower()
    hard_block = [
        "ceo", "cto", "cio", "coo", "cfo",
        "vice president", "vp of", "vp,",
        "head of engineering", "head of product", "head of data",
        "chief ",
    ]
    for word in hard_block:
        if word in t:
            return False
    return True


def _deduplicate_and_filter_jobs(jobs):
    """Remove duplicados, filtra por senioridade e por localidade."""
    seen = set()
    filtered = []
    for job in jobs:
        if not _is_junior_job(job["titulo"]):
            continue
        # Filtro de localidade
        if not _is_location_allowed(job):
            _log(f"  ⚠️  Localidade bloqueada: {job['titulo']} — {job.get('local', '?')}")
            continue
        key = (job["titulo"].lower().strip(), job["empresa"].lower().strip())
        if key not in seen:
            seen.add(key)
            filtered.append(job)
    return filtered


# ═══════════════════════════════════════════════════════════════════════
#  ORQUESTRAÇÃO
# ═══════════════════════════════════════════════════════════════════════

def search_all_jobs(max_per_category=None):
    # Carregar categorias e localizações dinamicamente do config
    global JOB_CATEGORIES_PT, JOB_CATEGORIES_EN, PRESENCIAL_ALLOWED
    if hasattr(settings, "JOB_CATEGORIES") and settings.JOB_CATEGORIES:
        cats = [c.strip() for c in settings.JOB_CATEGORIES.split(",") if c.strip()]
        if cats:
            JOB_CATEGORIES_PT = cats
            JOB_CATEGORIES_EN = [c for c in cats if any(x in c.lower() for x in ["developer", "analyst", "support", "engineer", "python"])]
            if not JOB_CATEGORIES_EN:
                JOB_CATEGORIES_EN = ["software developer", "python developer", "data analyst"]

    if hasattr(settings, "PRESENCIAL_CITIES") and settings.PRESENCIAL_CITIES:
        PRESENCIAL_ALLOWED = [c.lower() for c in settings.PRESENCIAL_CITIES]

    if max_per_category is None:
        max_per_category = settings.MAX_JOBS_PER_CATEGORY

    all_jobs = []

    _log("\n🔍 Iniciando busca de vagas — Bot v5")
    _log("=" * 60)

    # ── Fontes BR Nativas ────────────────────────────────────────────
    _log("\n🇧🇷 Buscando em fontes brasileiras nativas...")

    br_sources = [
        ("Remotive API", _search_remotive),
        ("Gupy", _search_gupy_rss),
        ("Vagas.com.br", _search_vagascom),
        ("Programathor", _search_programathor),
        ("GeekHunter", _search_geekhunter),
        ("Remotar", _search_remotar),
        ("Trampos.co", _search_trampos),
    ]

    for category in JOB_CATEGORIES_PT[:4]:  # Limita para não ser muito lento
        _log(f"\n🔎 Categoria: '{category}'")
        for source_name, search_fn in br_sources:
            try:
                found = search_fn(category)
                if found:
                    _log(f"  ✅ {source_name}: {len(found)} vagas")
                    all_jobs.extend(found[:max_per_category])
                else:
                    _log(f"  — {source_name}: 0 vagas")
            except Exception as e:
                _log(f"  ❌ {source_name}: erro — {e}")
            _random_delay(0.3, 0.8)

    # ── APIs de Vagas (Adzuna + JSearch) ──────────────────────────
    _log(f"\n{'=' * 60}")
    _log("🌐 Buscando via APIs de vagas (Adzuna + JSearch)...")

    api_categories = JOB_CATEGORIES_PT[:3] + JOB_CATEGORIES_EN[:2]
    for category in api_categories:
        _log(f"  🔎 API: '{category}'")

        adzuna_jobs = _search_adzuna(category)
        if adzuna_jobs:
            _log(f"    ✅ Adzuna: {len(adzuna_jobs)} vagas")
            all_jobs.extend(adzuna_jobs[:max_per_category])
        _random_delay(0.3, 0.6)

        jsearch_jobs = _search_jsearch(category)
        if jsearch_jobs:
            _log(f"    ✅ JSearch: {len(jsearch_jobs)} vagas")
            all_jobs.extend(jsearch_jobs[:max_per_category])
        _random_delay(0.5, 1)

    # ── Buscas via Google/DuckDuckGo (PT) ───────────────────────────
    _log(f"\n{'=' * 60}")
    _log("🔎 Buscando via motores de busca (PT)...")

    for category in JOB_CATEGORIES_PT:
        for location in ["remoto Brasil", "Recife PE", "Olinda PE", "Jaboatão dos Guararapes PE"]:
            query = f"{category} {location}"
            google_jobs = _search_google_jobs(query)
            if google_jobs:
                all_jobs.extend(google_jobs[:max_per_category])
            elif len(all_jobs) < 10:
                ddg_jobs = _search_duckduckgo_jobs(query)
                all_jobs.extend(ddg_jobs[:max_per_category])
            _random_delay(0.5, 1)

    # ── Buscas internacionais (EN) ───────────────────────────────────
    _log(f"\n{'=' * 60}")
    _log("🌍 Buscando vagas internacionais (Wellfound, RemoteOK, WeWorkRemotely)...")

    for category in JOB_CATEGORIES_EN:
        _log(f"\n🔎 International: '{category}'")

        rok_jobs = _search_remoteok(category)
        if rok_jobs:
            _log(f"  RemoteOK: {len(rok_jobs)} vagas")
            all_jobs.extend(rok_jobs[:max_per_category])
        _random_delay(0.5, 1)

        wwr_jobs = _search_weworkremotely(category)
        if wwr_jobs:
            _log(f"  WeWorkRemotely: {len(wwr_jobs)} vagas")
            all_jobs.extend(wwr_jobs[:max_per_category])
        _random_delay(0.5, 1)

        wf_jobs = _search_wellfound(category)
        if wf_jobs:
            _log(f"  Wellfound: {len(wf_jobs)} vagas")
            all_jobs.extend(wf_jobs[:max_per_category])
        _random_delay(0.5, 1)

    # Filtrar, deduplicar e aplicar filtro de localidade
    unique_jobs = _deduplicate_and_filter_jobs(all_jobs)

    s = get_stats()
    _log(f"\n{'=' * 60}")
    _log(f"✅ Total bruto: {len(all_jobs)} | Após filtros: {len(unique_jobs)} vagas")
    _log(f"   🏙️  Filtro: presencial apenas Recife/Jaboatão/Olinda | remoto: qualquer lugar")

    for source in _stats:
        src = _stats[source]
        if src["ok"] + src["blocked"] + src["error"] > 0:
            _log(f"   {source.capitalize():20} → ok:{src['ok']} bloqueado:{src['blocked']} erro:{src['error']}")

    for job in unique_jobs:
        if not job.get("descricao"):
            job["descricao"] = f"Vaga de {job['titulo']} na empresa {job['empresa']} em {job.get('local', 'Brasil')}."

    return unique_jobs

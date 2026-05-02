"""
Módulo de Busca de Vagas — v3 (Google/DuckDuckGo first)
Busca vagas via motores de busca (Google, DuckDuckGo) como fonte primária.
LinkedIn/Indeed como fallback opcional. Nunca trava — timeouts curtos.
"""

import os
import sys
import random
import re
import time
import json
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, "config.env"))

# ── User-Agents para rotação ──────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:127.0) Gecko/20100101 Firefox/127.0",
]

# ── Categorias de vagas (reduzido para otmizar) ───────────────────
JOB_CATEGORIES = [
    # Português — mais relevantes
    "desenvolvedor de software",
    "analista de dados",
    "suporte de TI",
    "help desk",
]

# ── Localizações ──────────────────────────────────────────────────────
LOCATIONS_REMOTE = ["remoto Brasil"]
LOCATIONS_PRESENCIAL = [
    "Recife PE",
    "Jaboatao dos Guararapes PE",
]
LOCATIONS_PORTUGAL = ["Portugal"]

# ── Config de delays (otimizado) ─────────────────────────────────
DELAY_MIN = float(os.getenv("REQUEST_DELAY_MIN", "0.3"))
DELAY_MAX = float(os.getenv("REQUEST_DELAY_MAX", "0.8"))

# ── Frases que indicam CAPTCHA/bloqueio ──────────────────────────────
BLOCK_SIGNALS = [
    "captcha", "robot", "automated", "please verify",
    "access denied", "cloudflare", "just a moment",
    "challenge-platform", "security check",
]

# ── Estatísticas da sessão ────────────────────────────────────────────
_stats = {
    "google": {"ok": 0, "blocked": 0, "error": 0},
    "duckduckgo": {"ok": 0, "blocked": 0, "error": 0},
    "linkedin": {"ok": 0, "blocked": 0, "error": 0},
    "indeed": {"ok": 0, "blocked": 0, "error": 0},
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


def _random_delay(min_s: float = None, max_s: float = None):
    lo = min_s if min_s is not None else DELAY_MIN
    hi = max_s if max_s is not None else DELAY_MAX
    time.sleep(random.uniform(lo, hi))


def _clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _is_blocked(response: requests.Response) -> bool:
    if response.status_code in (403, 429, 503):
        return True
    text_lower = response.text[:2000].lower()
    return any(sig in text_lower for sig in BLOCK_SIGNALS)


def _safe_get(url: str, params: dict = None, timeout: int = 8, source: str = "") -> requests.Response | None:
    """Faz GET seguro com timeout curto e detecção de bloqueio."""
    try:
        response = requests.get(url, params=params, headers=_get_headers(), timeout=timeout)
        if _is_blocked(response):
            if source and source in _stats:
                _stats[source]["blocked"] += 1
            return None
        if source and source in _stats:
            _stats[source]["ok"] += 1
        return response
    except requests.Timeout:
        if source and source in _stats:
            _stats[source]["error"] += 1
        return None
    except requests.RequestException:
        if source and source in _stats:
            _stats[source]["error"] += 1
        return None


def _log(msg: str):
    """Print com flush imediato."""
    print(msg)
    sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════════
#  GOOGLE SEARCH (fonte primária)
# ═══════════════════════════════════════════════════════════════════════

def _search_google_jobs(query: str) -> list[dict]:
    """
    Busca vagas via Google Search.
    Extrai título, empresa e snippet dos resultados.
    """
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

            # Extrair empresa do título ou snippet
            empresa = _extract_company_from_result(title_text, snippet_text, href)
            titulo = _extract_job_title(title_text, query)

            if empresa and titulo:
                jobs.append({
                    "titulo": titulo,
                    "empresa": empresa,
                    "local": _extract_location(snippet_text),
                    "url": href if href.startswith("http") else "",
                    "descricao": snippet_text,
                    "fonte": "Google",
                })

            if len(jobs) >= 8:
                break

    except Exception:
        pass

    return jobs


# ═══════════════════════════════════════════════════════════════════════
#  DUCKDUCKGO SEARCH (fallback confiável)
# ═══════════════════════════════════════════════════════════════════════

def _search_duckduckgo_jobs(query: str) -> list[dict]:
    """
    Busca vagas via DuckDuckGo HTML (mais tolerante que Google).
    """
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
                jobs.append({
                    "titulo": titulo,
                    "empresa": empresa,
                    "local": _extract_location(snippet_text),
                    "url": href if href.startswith("http") else "",
                    "descricao": snippet_text,
                    "fonte": "DuckDuckGo",
                })

            if len(jobs) >= 8:
                break

    except Exception:
        _stats["duckduckgo"]["error"] += 1

    return jobs


# ═══════════════════════════════════════════════════════════════════════
#  LINKEDIN (fonte secundária — tentativa rápida)
# ═══════════════════════════════════════════════════════════════════════

def _search_linkedin(query: str, location: str, remote: bool = False) -> list[dict]:
    """Busca vagas no LinkedIn via endpoint público (guest). Timeout curto."""
    jobs = []
    params = {
        "keywords": query,
        "location": location,
        "trk": "guest_homepage-basic_guest_nav_menu_jobs",
        "position": "1",
        "pageNum": "0",
    }
    if remote:
        params["f_WT"] = "2"

    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    response = _safe_get(url, params=params, timeout=6, source="linkedin")
    if not response:
        return jobs

    soup = BeautifulSoup(response.text, "lxml")
    cards = soup.find_all("div", class_="base-card")

    for card in cards[:8]:
        try:
            title_tag = card.find("h3", class_="base-search-card__title")
            company_tag = card.find("h4", class_="base-search-card__subtitle")
            location_tag = card.find("span", class_="job-search-card__location")
            link_tag = card.find("a", class_="base-card__full-link")

            if not title_tag or not company_tag:
                continue

            job = {
                "titulo": _clean_text(title_tag.get_text()),
                "empresa": _clean_text(company_tag.get_text()),
                "local": _clean_text(location_tag.get_text()) if location_tag else location,
                "url": link_tag["href"].split("?")[0] if link_tag else "",
                "descricao": "",
                "fonte": "LinkedIn",
            }
            jobs.append(job)
        except Exception:
            continue

    return jobs


# ═══════════════════════════════════════════════════════════════════════
#  HELPERS — Extração de dados dos resultados de busca
# ═══════════════════════════════════════════════════════════════════════

# Sites que não são vagas reais
_SKIP_DOMAINS = [
    "youtube.com", "wikipedia.org", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "reddit.com", "tiktok.com",
]

# Padrões comuns de sites de vagas
_JOB_SITE_PATTERNS = [
    "linkedin.com", "indeed.com", "glassdoor.com", "vagas.com",
    "gupy.io", "catho.com", "infojobs.com", "trabalhabrasil.com",
    "netvagas.com", "empregos.com", "trampos.co", "programathor.com",
    "geekhunter.com", "remotar.com", "careers", "vagas", "jobs",
]


def _extract_company_from_result(title: str, snippet: str, url: str) -> str:
    """Tenta extrair o nome da empresa a partir do resultado de busca."""
    # Padrão: "Vaga em EMPRESA" ou "EMPRESA contrata" ou "EMPRESA - Vaga"
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
                # Filtrar palavras genéricas
                if company.lower() not in [
                    "vaga", "vagas", "emprego", "empregos", "oportunidade",
                    "remoto", "junior", "pleno", "senior", "estágio",
                    "linkedin", "indeed", "glassdoor", "catho",
                ]:
                    return company

    # Tentar extrair do domínio da URL
    if url:
        for site in _JOB_SITE_PATTERNS:
            if site in url.lower():
                # Se é um site de vagas, tentar pegar empresa do título
                parts = re.split(r'\s*[-–|]\s*', title)
                for part in parts:
                    part = part.strip()
                    if (len(part) > 2 and
                        part.lower() not in ["linkedin", "indeed", "glassdoor", "catho",
                                              "vagas.com", "gupy", "infojobs"] and
                        not any(kw in part.lower() for kw in ["vaga", "emprego", "junior", "estágio"])):
                        return part
                break

    return ""


def _extract_job_title(title: str, query: str) -> str:
    """Extrai o título da vaga a partir do título do resultado de busca."""
    # Remover o nome do site (após último - ou |)
    parts = re.split(r'\s*[-–|]\s*', title)
    if len(parts) >= 2:
        # O título da vaga geralmente é a primeira parte
        candidate = parts[0].strip()
        if any(kw in candidate.lower() for kw in [
            "desenvolv", "analista", "suporte", "help desk", "qa", "test",
            "estagi", "junior", "cientista", "dados", "python", "java",
            "programad", "técnico", "engineer", "developer",
        ]):
            return candidate

    # Se não encaixou, usar o query como base
    query_words = query.lower().split()
    if any(w in title.lower() for w in query_words[:2]):
        # Limpar o título
        clean = re.sub(r'\s*[-–|]\s*(?:LinkedIn|Indeed|Glassdoor|Catho|Gupy).*$', '', title, flags=re.I)
        return clean.strip()

    return ""


def _extract_location(text: str) -> str:
    """Tenta extrair localização do texto."""
    loc_patterns = [
        r"(Remoto|Remote|Home\s*Office|Híbrido|Hybrid)",
        r"(Recife|São Paulo|Rio de Janeiro|Belo Horizonte|Porto Alegre|Curitiba|Brasília|Salvador|Fortaleza)",
        r"(Lisboa|Porto|Braga|Coimbra|Portugal)",
        r"([A-Z][a-zà-ú]+(?:\s+(?:do|de|dos|das)\s+[A-Z][a-zà-ú]+)*\s*[-,]\s*[A-Z]{2})",
    ]
    for pattern in loc_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return "Brasil"


def _try_get_page_description(url: str) -> str:
    """Tenta obter a descrição da vaga visitando a página. Timeout muito curto."""
    if not url or not url.startswith("http"):
        return ""
    # Não tentar em sites que sabemos que vão bloquear
    if any(d in url.lower() for d in _SKIP_DOMAINS):
        return ""
    resp = _safe_get(url, timeout=6)
    if not resp:
        return ""
    soup = BeautifulSoup(resp.text, "lxml")

    # Tentar pegar de JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and "description" in data:
                return _clean_text(BeautifulSoup(data["description"], "lxml").get_text())[:2000]
        except Exception:
            continue

    # Tentar meta description
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return _clean_text(meta["content"])

    # Tentar pegar texto do body (limitado)
    body = soup.find("body")
    if body:
        text = _clean_text(body.get_text())
        return text[:2000] if len(text) > 100 else ""

    return ""


# ═══════════════════════════════════════════════════════════════════════
#  ORQUESTRAÇÃO DA BUSCA
# ═══════════════════════════════════════════════════════════════════════

def _is_junior_job(title: str) -> bool:
    """Filtro mínimo: bloqueia apenas cargos C-level e VP.
    Vagas junior, pleno, senior, specialist, etc. todas passam.
    A IA (Gemini) decide a compatibilidade com o currículo.
    """
    t = title.lower()

    # Bloquear apenas C-level e cargos de alta gestão estratégica
    hard_block = [
        "ceo", "cto", "cio", "coo", "cfo",
        "vice president", "vp of", "vp,",
        "head of engineering", "head of product", "head of data",
        "chief ",
    ]

    for word in hard_block:
        if word in t:
            return False

    # Tudo passa — a IA decide se o perfil bate
    return True

def _deduplicate_and_filter_jobs(jobs: list[dict]) -> list[dict]:
    """Remove vagas duplicadas e filtra para manter apenas nível iniciante/júnior."""
    seen = set()
    filtered = []
    for job in jobs:
        if not _is_junior_job(job["titulo"]):
            continue
            
        key = (job["titulo"].lower().strip(), job["empresa"].lower().strip())
        if key not in seen:
            seen.add(key)
            filtered.append(job)
    return filtered


def search_all_jobs(max_per_category: int = None) -> list[dict]:
    """
    Busca vagas em todas as categorias via Google/DuckDuckGo (primário)
    e LinkedIn (secundário). Retorna lista de vagas.
    """
    if max_per_category is None:
        max_per_category = int(os.getenv("MAX_JOBS_PER_CATEGORY", "3"))

    all_jobs = []

    # Montar lista de buscas otimizada (apenas Brasil.remote + Recife + Portugal)
    searches = []
    for category in JOB_CATEGORIES:
        searches.append((category, "remoto Brasil"))
        searches.append((category, "Recife PE"))
    
    # Apenas as primeiras 5 categorias para Portugal
    for category in JOB_CATEGORIES[:5]:
        searches.append((category, "Portugal"))

    _log(f"\n🔍 Iniciando busca de vagas ({len(searches)} buscas planejadas)...")

    total = len(searches)
    _log(f"\n🔍 Iniciando busca de vagas ({total} buscas planejadas)...")
    _log("=" * 60)

    for i, (category, location) in enumerate(searches):
        _log(f"\n[{i+1}/{total}] 🔎 '{category}' - {location}")

        found_this_round = []

        # ── 1. Google (fonte primária) ──────────────────────────────
        query = f"{category} {location}"
        google_jobs = _search_google_jobs(query)
        if google_jobs:
            _log(f"  Google: {len(google_jobs)} vagas")
            found_this_round.extend(google_jobs)
        else:
            _log(f"  Google: 0 vagas (bloqueado ou sem resultados)")

        _random_delay(0.5, 1)

        # ── 2. DuckDuckGo (fallback) ────────────────────────────────
        if len(found_this_round) < 3:
            ddg_jobs = _search_duckduckgo_jobs(query)
            if ddg_jobs:
                _log(f"  DuckDuckGo: {len(ddg_jobs)} vagas")
                found_this_round.extend(ddg_jobs)
            else:
                _log(f"  DuckDuckGo: 0 vagas")
            _random_delay(0.5, 1)

        # ── 3. LinkedIn (tentativa rápida) ──────────────────────────
        remote = "remoto" in location.lower()
        lk_jobs = _search_linkedin(category, location.replace(" ", ", "), remote=remote)
        if lk_jobs:
            _log(f"  LinkedIn: {len(lk_jobs)} vagas")
            found_this_round.extend(lk_jobs)
        else:
            _log(f"  LinkedIn: 0 vagas (bloqueado ou sem resultados)")

        # Limitar por categoria
        all_jobs.extend(found_this_round[:max_per_category])
        _random_delay(0.5, 1.5)

    # Filtrar juniores e remover duplicatas
    unique_jobs = _deduplicate_and_filter_jobs(all_jobs)

    # Estatísticas
    s = get_stats()
    _log(f"\n{'=' * 60}")
    _log(f"✅ Total: {len(all_jobs)} vagas encontradas, {len(unique_jobs)} únicas")
    for source in ["google", "duckduckgo", "linkedin"]:
        _log(f"   {source.capitalize():12} → ok:{s[source]['ok']} bloqueado:{s[source]['blocked']} erro:{s[source]['error']}")

    # Garantir que tem pelo menos uma descrição básica (sem enriquecimento para otimizar)
    if unique_jobs:
        for job in unique_jobs:
            if not job.get("descricao"):
                job["descricao"] = (
                    f"Vaga de {job['titulo']} na empresa {job['empresa']} "
                    f"em {job['local']}."
                )

    return unique_jobs

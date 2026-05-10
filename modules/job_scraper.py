"""
Módulo de Busca de Vagas — v4 (International Job Boards)
Busca vagas via Google/DuckDuckGo + Wellfound, Remote OK, We Work Remotely.
"""

import os
import sys
import random
import re
import time
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, "config.env"))

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
]

JOB_CATEGORIES_EN = [
    "software developer",
    "data analyst",
    "IT support",
    "QA engineer",
]

LOCATIONS_REMOTE = ["remoto Brasil"]
LOCATIONS_PRESENCIAL = ["Recife PE", "Olinda PE", "Jaboatão dos Guararapes PE", "Cabo de Santo Agostinho PE"]
LOCATIONS_PORTUGAL = ["Portugal"]

DELAY_MIN = float(os.getenv("REQUEST_DELAY_MIN", "0.3"))
DELAY_MAX = float(os.getenv("REQUEST_DELAY_MAX", "0.8"))

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


def _safe_get(url, params=None, timeout=8, source=""):
    try:
        response = requests.get(url, params=params, headers=_get_headers(), timeout=timeout)
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


# ═══════════════════════════════════════════════════════════════════════
#  GOOGLE SEARCH
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
                    "url": href if href.startswith("http") else "",
                    "descricao": snippet_text, "fonte": "Google",
                })
            if len(jobs) >= 8:
                break
    except Exception:
        pass
    return jobs


# ═══════════════════════════════════════════════════════════════════════
#  DUCKDUCKGO SEARCH
# ═══════════════════════════════════════════════════════════════════════

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
                jobs.append({
                    "titulo": titulo, "empresa": empresa,
                    "local": _extract_location(snippet_text),
                    "url": href if href.startswith("http") else "",
                    "descricao": snippet_text, "fonte": "DuckDuckGo",
                })
            if len(jobs) >= 8:
                break
    except Exception:
        _stats["duckduckgo"]["error"] += 1
    return jobs


# ═══════════════════════════════════════════════════════════════════════
#  REMOTE OK (JSON API)
# ═══════════════════════════════════════════════════════════════════════

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
                "url": item.get("url", f"https://remoteok.com/remote-jobs/{item.get('slug', '')}"),
                "descricao": _clean_text(BeautifulSoup(item.get("description", ""), "lxml").get_text())[:500],
                "fonte": "RemoteOK",
            })
            if len(jobs) >= 8:
                break
    except Exception:
        _stats["remoteok"]["error"] += 1
    return jobs


# ═══════════════════════════════════════════════════════════════════════
#  WE WORK REMOTELY (RSS)
# ═══════════════════════════════════════════════════════════════════════

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

                # Extrair empresa do título (formato: "Company: Job Title")
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
                    "local": "Remote",
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


# ═══════════════════════════════════════════════════════════════════════
#  WELLFOUND (via Google site: search)
# ═══════════════════════════════════════════════════════════════════════

def _search_wellfound(query):
    """Busca vagas no Wellfound via Google site: search (JS-heavy site)."""
    jobs = []
    try:
        url = "https://www.google.com/search"
        params = {"q": f"site:wellfound.com/jobs {query} remote", "num": 10}
        response = _safe_get(url, params=params, timeout=8, source="wellfound")
        if not response:
            # Fallback to DuckDuckGo
            ddg_url = "https://html.duckduckgo.com/html/"
            ddg_params = {"q": f"site:wellfound.com {query} remote job"}
            response = requests.post(ddg_url, data=ddg_params, headers=_get_headers(), timeout=8)
            if not response or response.status_code != 200:
                return jobs

        soup = BeautifulSoup(response.text, "lxml")

        for g in soup.find_all("div", class_="g"):
            title_tag = g.find("h3")
            link_tag = g.find("a")
            snippet_tag = g.find("div", class_="VwiC3b") or g.find("span", class_="st")
            if not title_tag:
                continue
            title_text = _clean_text(title_tag.get_text())
            href = ""
            if link_tag:
                href = link_tag.get("href", "")
                if href.startswith("/url?q="):
                    href = href.split("/url?q=")[1].split("&")[0]

            if "wellfound.com" not in href:
                continue

            snippet_text = _clean_text(snippet_tag.get_text()) if snippet_tag else ""

            # Parse title: usually "Job Title at Company - Wellfound"
            title_clean = re.sub(r"\s*[-–|]\s*Wellfound.*$", "", title_text, flags=re.I)
            parts = re.split(r"\s+at\s+", title_clean, maxsplit=1)
            if len(parts) == 2:
                titulo = parts[0].strip()
                empresa = parts[1].strip()
            else:
                titulo = title_clean
                empresa = _extract_company_from_result(title_text, snippet_text, href)

            if titulo:
                jobs.append({
                    "titulo": titulo,
                    "empresa": empresa or "Startup",
                    "local": "Remote",
                    "url": href if href.startswith("http") else "",
                    "descricao": snippet_text,
                    "fonte": "Wellfound",
                })
            if len(jobs) >= 8:
                break

        # Also try DuckDuckGo results format
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
                    "local": "Remote", "url": href,
                    "descricao": snippet_text, "fonte": "Wellfound",
                })
            if len(jobs) >= 8:
                break

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
    "weworkremotely.com", "careers", "vagas", "jobs",
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
        r"(Recife|Olinda|Jaboatão dos Guararapes|Cabo de Santo Agostinho|São Paulo|Rio de Janeiro|Belo Horizonte|Porto Alegre|Curitiba|Brasília|Salvador|Fortaleza)",
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


# ═══════════════════════════════════════════════════════════════════════
#  ORQUESTRAÇÃO
# ═══════════════════════════════════════════════════════════════════════

def search_all_jobs(max_per_category=None):
    if max_per_category is None:
        max_per_category = int(os.getenv("MAX_JOBS_PER_CATEGORY", "3"))

    all_jobs = []

    searches_pt = []
    
    search_presencial = os.getenv("SEARCH_PRESENCIAL", "true").lower() == "true"
    search_portugal = os.getenv("SEARCH_PORTUGAL", "true").lower() == "true"

    for category in JOB_CATEGORIES_PT:
        searches_pt.append((category, "remoto Brasil"))
        if search_presencial:
            for loc in LOCATIONS_PRESENCIAL:
                searches_pt.append((category, loc))
                
    if search_portugal:
        for category in JOB_CATEGORIES_PT[:5]:
            searches_pt.append((category, "Portugal"))

    _log("\n🔍 Iniciando busca de vagas...")
    _log(f"   📋 {len(searches_pt)} buscas nacionais (PT) + 3 fontes internacionais (EN)")
    _log("=" * 60)

    total = len(searches_pt)
    for i, (category, location) in enumerate(searches_pt):
        _log(f"\n[{i+1}/{total}] 🔎 '{category}' - {location}")
        found = []

        google_jobs = _search_google_jobs(f"{category} {location}")
        if google_jobs:
            _log(f"  Google: {len(google_jobs)} vagas")
            found.extend(google_jobs)
        else:
            _log("  Google: 0 vagas")

        _random_delay(0.5, 1)

        if len(found) < 3:
            ddg_jobs = _search_duckduckgo_jobs(f"{category} {location}")
            if ddg_jobs:
                _log(f"  DuckDuckGo: {len(ddg_jobs)} vagas")
                found.extend(ddg_jobs)
            _random_delay(0.5, 1)

        all_jobs.extend(found[:max_per_category])
        _random_delay(0.5, 1.5)

    # ── Buscas internacionais (EN) ───────────────────────────────────
    _log(f"\n{'=' * 60}")
    _log("🌍 Buscando vagas internacionais (Wellfound, RemoteOK, WeWorkRemotely)...")

    for category in JOB_CATEGORIES_EN:
        _log(f"\n🔎 International: '{category}'")

        # Remote OK
        rok_jobs = _search_remoteok(category)
        if rok_jobs:
            _log(f"  RemoteOK: {len(rok_jobs)} vagas")
            all_jobs.extend(rok_jobs[:max_per_category])
        else:
            _log("  RemoteOK: 0 vagas")
        _random_delay(0.5, 1)

        # We Work Remotely
        wwr_jobs = _search_weworkremotely(category)
        if wwr_jobs:
            _log(f"  WeWorkRemotely: {len(wwr_jobs)} vagas")
            all_jobs.extend(wwr_jobs[:max_per_category])
        else:
            _log("  WeWorkRemotely: 0 vagas")
        _random_delay(0.5, 1)

        # Wellfound
        wf_jobs = _search_wellfound(category)
        if wf_jobs:
            _log(f"  Wellfound: {len(wf_jobs)} vagas")
            all_jobs.extend(wf_jobs[:max_per_category])
        else:
            _log("  Wellfound: 0 vagas")
        _random_delay(0.5, 1)

    # Filtrar e deduplicar
    unique_jobs = _deduplicate_and_filter_jobs(all_jobs)

    s = get_stats()
    _log(f"\n{'=' * 60}")
    _log(f"✅ Total: {len(all_jobs)} vagas encontradas, {len(unique_jobs)} únicas")
    for source in ["google", "duckduckgo", "remoteok", "weworkremotely", "wellfound"]:
        _log(f"   {source.capitalize():18} → ok:{s[source]['ok']} bloqueado:{s[source]['blocked']} erro:{s[source]['error']}")

    for job in unique_jobs:
        if not job.get("descricao"):
            job["descricao"] = f"Vaga de {job['titulo']} na empresa {job['empresa']} em {job['local']}."

    return unique_jobs

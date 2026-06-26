"""
Módulo de Adaptação de Currículo — v4
Preserva o currículo base integralmente; a IA altera apenas objetivo e habilidades técnicas.
"""

import hashlib
import json
import os
import re

import fitz  # PyMuPDF
from fpdf import FPDF
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.core.analyzer import _call_gemini, _extract_json, _call_groq

from app.config import settings

OUTPUT_DIR = os.path.join(settings.DATA_DIR, "curriculos")
_BASE_RESUME_CACHE = os.path.join(settings.DATA_DIR, "base_resume_parsed.json")

_SECTION_PATTERNS = [
    ("objetivo", [
        r"objetivo\s+profissional", r"^objetivo\s*$", r"professional\s+objective",
        r"^objective\s*$", r"resumo\s+profissional",
    ]),
    ("experiencia", [
        r"experi[eê]ncia\s+profissional", r"^experi[eê]ncia\s*$",
        r"professional\s+experience", r"^experience\s*$", r"hist[oó]rico\s+profissional",
    ]),
    ("formacao", [
        r"forma[cç][aã]o\s+acad[eê]mica", r"^forma[cç][aã]o\s*$", r"^educa[cç][aã]o\s*$",
        r"^education\s*$", r"escolaridade",
    ]),
    ("habilidades_tecnicas", [
        r"habilidades\s+t[eé]cnicas", r"conhecimentos\s+t[eé]cnicos",
        r"technical\s+skills", r"^skills\s*$", r"stack\s+t[eé]cn",
        r"tecnologias",
    ]),
    ("habilidades_comportamentais", [
        r"habilidades\s+comportamentais", r"soft\s+skills", r"compet[eê]ncias\s+comportamentais",
    ]),
    ("projetos", [r"^projetos\s*$", r"^projects\s*$", r"portf[oó]lio"]),
    ("certificacoes", [r"certifica[cç][oõ]es", r"certifications", r"cursos\s+e\s+certifica"]),
    ("idiomas", [r"^idiomas\s*$", r"^languages\s*$"]),
]

COLOR_PRIMARY = (41, 65, 122)
COLOR_ACCENT = (0, 119, 181)
COLOR_SECONDARY = (80, 80, 80)
COLOR_LIGHT = (140, 140, 140)

# Section headers by language
SECTION_HEADERS = {
    "en": {
        "objective": "Professional Objective",
        "experience": "Professional Experience",
        "education": "Education",
        "tech_skills": "Technical Skills",
        "soft_skills": "Soft Skills",
        "projects": "Projects",
        "certifications": "Certifications",
        "languages": "Languages",
    },
    "pt": {
        "objective": "Objetivo Profissional",
        "experience": "Experiência Profissional",
        "education": "Formação Acadêmica",
        "tech_skills": "Habilidades Técnicas",
        "soft_skills": "Habilidades Comportamentais",
        "projects": "Projetos",
        "certifications": "Certificações",
        "languages": "Idiomas",
    },
}


def _safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def _ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _get_headers(lang_code):
    """Returns section headers dict based on language."""
    if lang_code and lang_code.startswith("en"):
        return SECTION_HEADERS["en"]
    return SECTION_HEADERS["pt"]


def is_international_job(job):
    """Detects if a job is international (needs English resume)."""
    source = job.get("fonte", "").lower()
    location = job.get("local", "").lower()

    international_sources = ["wellfound", "remoteok", "weworkremotely"]
    if any(s in source for s in international_sources):
        return True

    brazil_pt_keywords = [
        "brasil", "brazil", "recife", "são paulo", "rio de janeiro",
        "belo horizonte", "curitiba", "porto alegre", "salvador",
        "fortaleza", "brasília", "jaboatao",
        "portugal", "lisboa", "porto", "braga", "coimbra",
    ]
    if not any(kw in location for kw in brazil_pt_keywords):
        # Check if location seems international
        if location and location not in ["", "remote", "remoto"]:
            return True

    return False


def extract_resume_text(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text.strip()
    except Exception as e:
        print(f"  ✗ Erro ao extrair texto do PDF: {e}")
        return ""


def _resume_cache_key(pdf_path: str) -> str:
    try:
        st = os.stat(pdf_path)
        raw = f"{os.path.abspath(pdf_path)}::{st.st_mtime}::{st.st_size}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    except OSError:
        return hashlib.sha256(pdf_path.encode()).hexdigest()[:16]


def _load_cached_base_resume(cache_key: str, cache_file: str | None = None) -> dict | None:
    path = cache_file if cache_file else _BASE_RESUME_CACHE
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            store = json.load(f)
        entry = store.get(cache_key)
        if entry and isinstance(entry, dict):
            return entry
    except Exception:
        pass
    return None


def _save_cached_base_resume(cache_key: str, data: dict, cache_file: str | None = None):
    path = cache_file if cache_file else _BASE_RESUME_CACHE
    store = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                store = json.load(f)
        except Exception:
            store = {}
    store[cache_key] = data
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _match_section_header(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return None
    for key, patterns in _SECTION_PATTERNS:
        for pat in patterns:
            if re.search(pat, stripped, re.IGNORECASE):
                return key
    return None


def _split_resume_sections(resume_text: str) -> dict[str, str]:
    lines = resume_text.split("\n")
    sections: dict[str, str] = {}
    header_lines: list[str] = []
    current_key = "_header"
    current_lines: list[str] = []

    for line in lines:
        key = _match_section_header(line)
        if key:
            sections[current_key] = "\n".join(current_lines).strip()
            current_key = key
            current_lines = []
            continue
        current_lines.append(line)

    sections[current_key] = "\n".join(current_lines).strip()
    if "_header" in sections:
        header_lines = sections.pop("_header", "").split("\n")
        sections["_header"] = "\n".join(header_lines).strip()
    return sections


def _parse_contact_from_header(header_text: str, candidate_name: str) -> dict:
    data = {
        "nome": candidate_name,
        "email": "",
        "telefone": "",
        "linkedin": "",
        "localizacao": "",
    }
    if not header_text:
        return data

    email_m = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", header_text)
    if email_m:
        data["email"] = email_m.group(0)

    phone_m = re.search(
        r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2}\)?[\s.-]?)?\d{4,5}[\s.-]?\d{4}",
        header_text,
    )
    if phone_m:
        data["telefone"] = phone_m.group(0).strip()

    linkedin_m = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/\S+", header_text, re.I)
    if linkedin_m:
        data["linkedin"] = linkedin_m.group(0).strip()

    lines = [ln.strip() for ln in header_text.split("\n") if ln.strip()]
    if lines:
        first = lines[0]
        if "@" not in first and "linkedin" not in first.lower() and len(first) > 4:
            if not re.match(r"^[\d\s().+-]+$", first):
                data["nome"] = first

    loc_keywords = ("recife", "pernambuco", "brasil", "brazil", "pe", "portugal", "remoto")
    for ln in lines[1:6]:
        low = ln.lower()
        if any(k in low for k in loc_keywords) and "@" not in ln:
            data["localizacao"] = ln
            break

    return data


def _parse_skills_list(section_text: str) -> list[str]:
    if not section_text:
        return []
    text = section_text.replace("•", "\n").replace("·", "\n").replace("|", "\n")
    parts = re.split(r"[\n,;]+", text)
    skills = []
    seen = set()
    for part in parts:
        skill = part.strip(" -–—\t")
        if not skill or len(skill) < 2:
            continue
        key = skill.lower()
        if key in seen:
            continue
        seen.add(key)
        skills.append(skill)
    return skills


def _parse_experience_section(section_text: str) -> list[dict]:
    if not section_text:
        return []
    blocks = re.split(r"\n\s*\n", section_text.strip())
    experiences = []
    date_re = re.compile(
        r"\d{4}|jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|present|atual|current",
        re.IGNORECASE,
    )

    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        cargo = lines[0]
        empresa = ""
        periodo = ""
        descricao = []

        for ln in lines[1:]:
            if date_re.search(ln) and not periodo:
                periodo = ln
            elif not empresa and len(ln) < 80 and not ln.startswith(("-", "•")):
                empresa = ln
            else:
                descricao.append(ln.lstrip("-• ").strip())

        experiences.append({
            "cargo": cargo,
            "empresa": empresa,
            "periodo": periodo,
            "descricao": descricao,
        })

    return experiences


def parse_base_resume(resume_text: str, pdf_path: str | None = None, cache_file: str | None = None) -> dict:
    """Estrutura o currículo base a partir do PDF — sem alterar conteúdo via IA."""
    cache_key = _resume_cache_key(pdf_path) if pdf_path else None
    if cache_key:
        cached = _load_cached_base_resume(cache_key, cache_file=cache_file)
        if cached:
            return cached

    sections = _split_resume_sections(resume_text)
    candidate_name = settings.CANDIDATE_NAME
    contact = _parse_contact_from_header(sections.get("_header", ""), candidate_name)

    objetivo = sections.get("objetivo", "").strip()
    experiencia = _parse_experience_section(sections.get("experiencia", ""))
    formacao = _extract_education_from_text(resume_text)
    if not formacao and sections.get("formacao"):
        formacao = _parse_experience_section(sections["formacao"])
        formacao = [
            {"curso": e.get("cargo", ""), "instituicao": e.get("empresa", ""), "periodo": e.get("periodo", "")}
            for e in formacao
        ]

    habilidades_tecnicas = _parse_skills_list(sections.get("habilidades_tecnicas", ""))
    habilidades_comportamentais = _parse_skills_list(sections.get("habilidades_comportamentais", ""))
    idiomas = _parse_skills_list(sections.get("idiomas", ""))
    certificacoes = _parse_skills_list(sections.get("certificacoes", ""))

    projetos = []
    if sections.get("projetos"):
        for block in re.split(r"\n\s*\n", sections["projetos"].strip()):
            lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
            if lines:
                projetos.append({
                    "nome": lines[0],
                    "descricao": " ".join(lines[1:]) if len(lines) > 1 else "",
                })

    base = {
        **contact,
        "objetivo": objetivo,
        "experiencia": experiencia,
        "formacao": formacao,
        "habilidades_tecnicas": habilidades_tecnicas,
        "habilidades_comportamentais": habilidades_comportamentais,
        "projetos": projetos,
        "certificacoes": certificacoes,
        "idiomas": idiomas,
        "_preserve_base": True,
        "_base_skills_pool": list(habilidades_tecnicas),
    }

    # Fallback: experiência/formação em texto bruto se o parse estruturado falhar
    if not base["experiencia"] and sections.get("experiencia"):
        base["_experiencia_raw"] = sections["experiencia"]
    if not base["formacao"] and sections.get("formacao"):
        base["_formacao_raw"] = sections["formacao"]

    if cache_key:
        _save_cached_base_resume(cache_key, base, cache_file=cache_file)

    return base


def _validate_adapted_data(data, candidate_name, original_education=None, is_international=False):
    if not data.get("nome"):
        data["nome"] = candidate_name
    for field in ["email", "telefone", "linkedin", "localizacao", "objetivo"]:
        if not isinstance(data.get(field), str):
            data[field] = ""
    for field in ["experiencia", "formacao", "habilidades_tecnicas",
                  "habilidades_comportamentais", "idiomas", "projetos", "certificacoes"]:
        if not isinstance(data.get(field), list):
            data[field] = []

    if original_education and not data.get("formacao"):
        data["formacao"] = original_education

    return data


def _extract_education_from_text(resume_text: str) -> list:
    """
    Extrai a formação acadêmica diretamente do texto bruto do currículo PDF.
    Usa heurísticas de padrão para garantir que a formação original seja preservada.
    """
    education = []
    if not resume_text:
        return education

    # Common section headers for education in PT and EN
    section_patterns = [
        r'forma[cç][aã]o\s+acad[eê]mica',
        r'educa[cç][aã]o',
        r'education',
        r'gradua[cç][aã]o',
        r'escolaridade',
    ]
    next_section_patterns = [
        r'experi[eê]ncia',
        r'habilidades',
        r'skills',
        r'projetos',
        r'certifica[cç][oõ]es',
        r'idiomas',
        r'languages',
        r'sobre mim',
        r'objetivo',
    ]

    section_re = re.compile(
        r'(' + '|'.join(section_patterns) + r')',
        re.IGNORECASE
    )
    next_re = re.compile(
        r'(' + '|'.join(next_section_patterns) + r')',
        re.IGNORECASE
    )

    lines = resume_text.split('\n')
    in_section = False
    section_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_section:
                section_lines.append('')
            continue
        if section_re.search(stripped):
            in_section = True
            continue
        if in_section:
            # Stop when hitting another major section
            if next_re.search(stripped) and len(stripped) < 60:
                break
            section_lines.append(stripped)

    # Parse extracted lines into structured entries
    # Look for course name followed by institution and date patterns
    date_re = re.compile(r'\d{4}|jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|present|atual|cursando', re.IGNORECASE)
    
    i = 0
    while i < len(section_lines):
        line = section_lines[i].strip()
        if not line:
            i += 1
            continue

        curso = line
        instituicao = ''
        periodo = ''

        # Look ahead for institution / period
        for j in range(i + 1, min(i + 4, len(section_lines))):
            nxt = section_lines[j].strip()
            if not nxt:
                continue
            if date_re.search(nxt):
                if not periodo:
                    periodo = nxt
            elif not instituicao and nxt != curso:
                instituicao = nxt

        if curso:
            edu_entry = {"curso": curso}
            if instituicao:
                edu_entry["instituicao"] = instituicao
            if periodo:
                edu_entry["periodo"] = periodo
            education.append(edu_entry)

        # Advance past this block
        i += max(1, len([s for s in section_lines[i:i+4] if s.strip()]))

    return education[:3]  # Keep at most 3 entries from original


def _filter_skills_to_base_pool(tailored: list, base_pool: list) -> list:
    """Mantém apenas habilidades que existem no currículo base (match flexível)."""
    if not tailored:
        return base_pool
    pool_lower = {s.lower(): s for s in base_pool}
    pool_tokens = set()
    for s in base_pool:
        for tok in re.split(r"[\s/+,]+", s.lower()):
            if len(tok) > 2:
                pool_tokens.add(tok)

    result = []
    seen = set()
    for skill in tailored:
        if not isinstance(skill, str):
            continue
        sk = skill.strip()
        if not sk:
            continue
        low = sk.lower()
        if low in seen:
            continue
        if low in pool_lower:
            result.append(pool_lower[low])
            seen.add(low)
            continue
        if any(tok in low or low in tok for tok in pool_tokens if len(tok) > 3):
            result.append(sk)
            seen.add(low)

    return result if result else base_pool


def adapt_resume_and_analyze(resume_text, job, pdf_path: str | None = None, cache_file: str | None = None):
    """
    Preserva o currículo base; a IA personaliza apenas objetivo e habilidades técnicas.
    """
    descricao = job.get("descricao", "")
    if not descricao or len(descricao) < 20:
        descricao = f"Vaga de {job['titulo']} na empresa {job['empresa']} em {job['local']}."

    international = is_international_job(job)
    base = parse_base_resume(resume_text, pdf_path=pdf_path, cache_file=cache_file)
    base_pool = base.get("_base_skills_pool") or base.get("habilidades_tecnicas", [])
    objetivo_base = base.get("objetivo", "")

    lang_instruction = (
        "Write 'objetivo' in ENGLISH (max 3 lines)."
        if international else
        "Escreva 'objetivo' no MESMO idioma da vaga (máximo 3 linhas)."
    )

    pool_preview = ", ".join(base_pool[:40]) if base_pool else "(extraia do texto do currículo)"

    prompt = f"""Você é especialista em RH. Analise a vaga e personalize APENAS o objetivo profissional e a lista de habilidades técnicas.

REGRAS OBRIGATÓRIAS:
1. {lang_instruction}
2. NÃO altere experiências, formação, projetos, certificações ou contatos — eles já estão no currículo base.
3. "habilidades_tecnicas" deve conter SOMENTE tecnologias/competências que o candidato JÁ possui no currículo base.
4. Use a lista de habilidades do candidato como fonte; reordene priorizando o que a vaga pede.
5. Pode incluir sinônimos (ex: "JS" se o base tem "JavaScript") mas NUNCA invente stack nova.
6. Máximo 12 habilidades técnicas, as mais alinhadas à vaga primeiro.
7. Objetivo: direto, com cargo-alvo e palavras-chave da vaga (sem mentir experiência).

HABILIDADES DO CANDIDATO (fonte única permitida):
{pool_preview}

OBJETIVO ATUAL DO CANDIDATO:
{objetivo_base[:500] or "(não informado)"}

TRECHO DO CURRÍCULO (referência):
{resume_text[:2000]}

VAGA:
Título: {job.get('titulo', '')}
Empresa: {job.get('empresa', '')}
Local: {job.get('local', '')}
Descrição: {descricao[:1500]}

Retorne APENAS JSON válido:
{{
    "analise": {{
        "idioma_vaga": "{'en' if international else 'pt-BR'}",
        "nivel": "junior|estagio|pleno",
        "requisitos_obrigatorios": ["req1"],
        "palavras_chave": ["kw1"]
    }},
    "objetivo": "texto do objetivo profissional adaptado",
    "habilidades_tecnicas": ["skill1", "skill2"]
}}"""

    _safe_print(f"  Personalizando objetivo e skills para: {job.get('titulo', '')} ({job.get('empresa', '')})...")
    if international:
        _safe_print("  [i] Vaga internacional — objetivo em ingles")

    response_text = _call_gemini(prompt)
    if response_text == "__RATE_LIMIT__":
        _safe_print("  [!] Rate limit do Gemini. Acionando Groq/Llama 3...")
        response_text = _call_groq(prompt)
        if not response_text or response_text == "__RATE_LIMIT__":
            return {"_rate_limit_fallback": True}, {}

    if not response_text:
        _safe_print("  [!] IA nao respondeu. Usando curriculo base sem alteracoes.")
        return dict(base), {}

    result = _extract_json(response_text)
    if not result:
        _safe_print("  [!] Nao foi possivel parsear resposta da IA.")
        return dict(base), {}

    analise = result.get("analise", {})
    if international:
        analise["idioma_vaga"] = "en"

    tailored_objetivo = (result.get("objetivo") or "").strip()
    tailored_skills = result.get("habilidades_tecnicas", [])
    if not isinstance(tailored_skills, list):
        tailored_skills = []

    merged = dict(base)
    if tailored_objetivo:
        merged["objetivo"] = tailored_objetivo
    merged["habilidades_tecnicas"] = _filter_skills_to_base_pool(tailored_skills, base_pool)
    merged["_preserve_base"] = True

    candidate_name = settings.CANDIDATE_NAME
    original_education = base.get("formacao") or _extract_education_from_text(resume_text)
    validated = _validate_adapted_data(
        merged, candidate_name, original_education=original_education, is_international=international
    )
    validated["_preserve_base"] = True

    return validated, analise


# ═══════════════════════════════════════════════════════════════════════
#  GERADOR DE PDF (1 página, compacto)
# ═══════════════════════════════════════════════════════════════════════

_UNICODE_REPLACEMENTS = {
    "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u00b7": "-",
    "\u2022": "-", "\u2010": "-", "\u2011": "-", "\u00a0": " ",
    "\u200b": "", "\u00ad": "",
}


def _sanitize_text(text):
    if not text:
        return ""
    for unicode_char, replacement in _UNICODE_REPLACEMENTS.items():
        text = text.replace(unicode_char, replacement)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class ResumePDF(FPDF):
    """PDF de currículo compacto — otimizado para 1 página."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=False, margin=10)
        self.COLOR_PRIMARY = COLOR_PRIMARY
        self.COLOR_SECONDARY = COLOR_SECONDARY
        self.COLOR_ACCENT = COLOR_ACCENT
        self.COLOR_LIGHT = COLOR_LIGHT

    def _add_section_title(self, title):
        self.ln(2)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*self.COLOR_PRIMARY)
        self.cell(0, 5, _sanitize_text(title.upper()), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*self.COLOR_ACCENT)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.5)

    def _add_text(self, text, bold=False, size=8, color=None):
        style = "B" if bold else ""
        self.set_font("Helvetica", style, size)
        self.set_text_color(*(color or self.COLOR_SECONDARY))
        self.multi_cell(0, 4, _sanitize_text(text))

    def _add_bullet(self, text):
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*self.COLOR_SECONDARY)
        bullet_x = self.l_margin + 3
        self.set_x(bullet_x)
        self.cell(3, 4, "-")
        self.set_x(bullet_x + 4)
        self.multi_cell(self.w - self.r_margin - bullet_x - 4, 4, _sanitize_text(text))

    def _fits_page(self):
        return self.get_y() < (self.h - 15)


def generate_resume_pdf(adapted_data, job, candidate_name, output_dir=None):
    """Gera PDF de currículo de 1 página."""
    if output_dir is None:
        output_dir = OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    empresa_slug = re.sub(r"[^\w]", "_", job.get("empresa", "empresa"))[:30]
    vaga_slug = re.sub(r"[^\w]", "_", job.get("titulo", "vaga"))[:30]
    filename = f"CV_{candidate_name.replace(' ', '_')}_{empresa_slug}_{vaga_slug}.pdf"
    filepath = os.path.join(output_dir, filename)

    if os.path.exists(filepath):
        _safe_print(f"  ⚠ Currículo com o mesmo nome já existe: {filename}. Não guardando duplicata.")
        return filepath

    # Determine language for section headers
    preserve = adapted_data.get("_preserve_base", False)
    lang = adapted_data.get("_lang", "pt")
    headers = _get_headers(lang)

    pdf = ResumePDF()
    if preserve:
        pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_left_margin(12)
    pdf.set_right_margin(12)
    pdf.set_x(12)

    # ── HEADER ────────────────────────────────────────────────────
    nome = adapted_data.get("nome", candidate_name)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*pdf.COLOR_PRIMARY)
    pdf.cell(0, 8, _sanitize_text(nome), new_x="LMARGIN", new_y="NEXT", align="C")

    contato_parts = [p for p in [
        adapted_data.get("email", ""),
        adapted_data.get("telefone", ""),
        adapted_data.get("localizacao", ""),
    ] if p]
    if contato_parts:
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*pdf.COLOR_LIGHT)
        pdf.cell(0, 4, _sanitize_text("  |  ".join(contato_parts)), new_x="LMARGIN", new_y="NEXT", align="C")

    if adapted_data.get("linkedin"):
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*pdf.COLOR_ACCENT)
        pdf.cell(0, 4, _sanitize_text(adapted_data["linkedin"]), new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.ln(1)
    pdf.set_draw_color(*pdf.COLOR_PRIMARY)
    pdf.set_line_width(0.6)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(1)

    # ── OBJECTIVE ─────────────────────────────────────────────────
    if adapted_data.get("objetivo") and pdf._fits_page():
        pdf._add_section_title(headers["objective"])
        pdf._add_text(adapted_data["objetivo"])

    # ── EXPERIENCE ────────────────────────────────────────────────
    exps = adapted_data.get("experiencia", [])
    if not preserve:
        exps = exps[:3]
    if exps and pdf._fits_page():
        pdf._add_section_title(headers["experience"])
        for exp in exps:
            if not pdf._fits_page():
                break
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(*pdf.COLOR_SECONDARY)
            pdf.cell(0, 5, _sanitize_text(exp.get("cargo", "")), new_x="LMARGIN", new_y="NEXT")
            info = [p for p in [exp.get("empresa"), exp.get("periodo")] if p]
            if info:
                pdf.set_font("Helvetica", "I", 7.5)
                pdf.set_text_color(*pdf.COLOR_LIGHT)
                pdf.cell(0, 4, _sanitize_text(" | ".join(info)), new_x="LMARGIN", new_y="NEXT")
            desc_limit = len(exp.get("descricao", [])) if preserve else 2
            for item in exp.get("descricao", [])[:desc_limit]:
                pdf._add_bullet(item)
            pdf.ln(1)

    elif adapted_data.get("_experiencia_raw") and pdf._fits_page():
        pdf._add_section_title(headers["experience"])
        pdf._add_text(adapted_data["_experiencia_raw"], size=7.5)

    # ── EDUCATION ─────────────────────────────────────────────────
    edus = adapted_data.get("formacao", [])
    if not preserve:
        edus = edus[:2]
    if edus and pdf._fits_page():
        pdf._add_section_title(headers["education"])
        for edu in edus:
            if not pdf._fits_page():
                break
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(*pdf.COLOR_SECONDARY)
            pdf.cell(0, 5, _sanitize_text(edu.get("curso", "")), new_x="LMARGIN", new_y="NEXT")
            info = [p for p in [edu.get("instituicao"), edu.get("periodo")] if p]
            if info:
                pdf.set_font("Helvetica", "I", 7.5)
                pdf.set_text_color(*pdf.COLOR_LIGHT)
                pdf.cell(0, 4, _sanitize_text(" | ".join(info)), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

    elif adapted_data.get("_formacao_raw") and pdf._fits_page():
        pdf._add_section_title(headers["education"])
        pdf._add_text(adapted_data["_formacao_raw"], size=7.5)

    # ── TECH SKILLS ───────────────────────────────────────────────
    skills = adapted_data.get("habilidades_tecnicas", [])
    if not preserve:
        skills = skills[:8]
    if skills and pdf._fits_page():
        pdf._add_section_title(headers["tech_skills"])
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*pdf.COLOR_SECONDARY)
        pdf.multi_cell(0, 4, _sanitize_text("  •  ".join(skills)))

    # ── SOFT SKILLS ───────────────────────────────────────────────
    soft = adapted_data.get("habilidades_comportamentais", [])
    if not preserve:
        soft = soft[:4]
    if soft and pdf._fits_page():
        pdf._add_section_title(headers["soft_skills"])
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*pdf.COLOR_SECONDARY)
        pdf.multi_cell(0, 4, _sanitize_text("  •  ".join(soft)))

    # ── PROJECTS (only if space) ──────────────────────────────────
    projs = adapted_data.get("projetos", [])
    if not preserve:
        projs = projs[:2]
    if projs and pdf._fits_page():
        pdf._add_section_title(headers["projects"])
        for proj in projs:
            if not pdf._fits_page():
                break
            pdf.set_font("Helvetica", "B", 7.5)
            pdf.set_text_color(*pdf.COLOR_SECONDARY)
            pdf.cell(0, 4, _sanitize_text(proj.get("nome", "")), new_x="LMARGIN", new_y="NEXT")
            if proj.get("descricao"):
                pdf._add_text(proj["descricao"], size=7, color=pdf.COLOR_LIGHT)

    # ── CERTIFICATIONS (only if space) ────────────────────────────
    certs = adapted_data.get("certificacoes", [])
    if not preserve:
        certs = certs[:3]
    if certs and pdf._fits_page():
        pdf._add_section_title(headers["certifications"])
        for cert in certs:
            if not pdf._fits_page():
                break
            pdf._add_bullet(cert)

    # ── LANGUAGES ─────────────────────────────────────────────────
    langs = adapted_data.get("idiomas", [])
    if langs and pdf._fits_page():
        pdf._add_section_title(headers["languages"])
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*pdf.COLOR_SECONDARY)
        pdf.multi_cell(0, 4, _sanitize_text("  •  ".join(langs)))

    try:
        temp_filepath = filepath + ".tmp"
        pdf.output(temp_filepath)
        
        # Verificar duplicata por tamanho de arquivo
        temp_size = os.path.getsize(temp_filepath)
        duplicate_path = None
        for existing_file in os.listdir(output_dir):
            existing_path = os.path.join(output_dir, existing_file)
            if os.path.isfile(existing_path) and not existing_file.endswith(".tmp") and existing_file.endswith(".pdf"):
                if os.path.getsize(existing_path) == temp_size:
                    duplicate_path = existing_path
                    break
        
        if duplicate_path:
            os.remove(temp_filepath)
            _safe_print(f"  ⚠ Currículo com o mesmo tamanho ({temp_size} bytes) já existe: {os.path.basename(duplicate_path)}. Não guardando duplicata.")
            return duplicate_path
        
        if os.path.exists(filepath):
            os.remove(filepath)
        os.rename(temp_filepath, filepath)
        _safe_print(f"  ✅ PDF gerado (1 página): {filename}")
        return filepath
    except Exception as e:
        _safe_print(f"  ✗ Erro ao salvar PDF: {e}")
        if 'temp_filepath' in locals() and os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except:
                pass
        return ""


# ═══════════════════════════════════════════════════════════════════════
#  GERADOR DE DOCX (1 página, compacto)
# ═══════════════════════════════════════════════════════════════════════

def generate_resume_docx(adapted_data, job, candidate_name, output_dir=None):
    if output_dir is None:
        output_dir = OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    empresa_slug = re.sub(r"[^\w]", "_", job.get("empresa", "empresa"))[:30]
    vaga_slug = re.sub(r"[^\w]", "_", job.get("titulo", "vaga"))[:30]
    filename = f"CV_{candidate_name.replace(' ', '_')}_{empresa_slug}_{vaga_slug}.docx"
    filepath = os.path.join(output_dir, filename)

    if os.path.exists(filepath):
        print(f"  ⚠ Currículo com o mesmo nome já existe: {filename}. Não guardando duplicata.")
        return filepath

    lang = adapted_data.get("_lang", "pt")
    headers = _get_headers(lang)

    doc = Document()

    for section in doc.sections:
        section.top_margin = Cm(1.0)
        section.bottom_margin = Cm(1.0)
        section.left_margin = Cm(1.5)
        section.right_margin = Cm(1.5)

    def _add_heading(text, level=1):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(14 if level == 1 else 9)
        r, g, b = COLOR_PRIMARY if level <= 2 else COLOR_SECONDARY
        run.font.color.rgb = RGBColor(r, g, b)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.space_before = Pt(0)
        return p

    def _add_section(title):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(1)
        run = p.add_run(title.upper())
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(*COLOR_PRIMARY)

    def _add_body(text, italic=False, size=8):
        p = doc.add_paragraph(text)
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.space_before = Pt(0)
        for run in p.runs:
            run.italic = italic
            run.font.size = Pt(size)
            run.font.color.rgb = RGBColor(*COLOR_SECONDARY)
        return p

    _add_heading(adapted_data.get("nome", candidate_name))

    contato = [c for c in [adapted_data.get("email", ""), adapted_data.get("telefone", ""),
               adapted_data.get("localizacao", "")] if c]
    if contato:
        p = doc.add_paragraph("  |  ".join(contato))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(1)
        for run in p.runs:
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(*COLOR_LIGHT)

    if adapted_data.get("linkedin"):
        p = doc.add_paragraph(adapted_data["linkedin"])
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        for run in p.runs:
            run.font.size = Pt(7)
            run.font.color.rgb = RGBColor(*COLOR_ACCENT)

    preserve = adapted_data.get("_preserve_base", False)

    if adapted_data.get("objetivo"):
        _add_section(headers["objective"])
        _add_body(adapted_data["objetivo"])

    exps = adapted_data.get("experiencia", [])
    if not preserve:
        exps = exps[:3]
    if exps:
        _add_section(headers["experience"])
        for exp in exps:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(exp.get("cargo", ""))
            run.bold = True
            run.font.size = Pt(9)
            info = " | ".join(filter(None, [exp.get("empresa"), exp.get("periodo")]))
            if info:
                _add_body(info, italic=True, size=7)
            desc_limit = len(exp.get("descricao", [])) if preserve else 2
            for item in exp.get("descricao", [])[:desc_limit]:
                bp = doc.add_paragraph(f"• {item}")
                bp.paragraph_format.space_after = Pt(0)
                bp.paragraph_format.left_indent = Cm(0.5)
                for run in bp.runs:
                    run.font.size = Pt(7.5)

    elif adapted_data.get("_experiencia_raw"):
        _add_section(headers["experience"])
        _add_body(adapted_data["_experiencia_raw"], size=7.5)

    edus = adapted_data.get("formacao", [])
    if not preserve:
        edus = edus[:2]
    if edus:
        _add_section(headers["education"])
        for edu in edus:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(edu.get("curso", ""))
            run.bold = True
            run.font.size = Pt(9)
            info = " | ".join(filter(None, [edu.get("instituicao"), edu.get("periodo")]))
            if info:
                _add_body(info, italic=True, size=7)

    elif adapted_data.get("_formacao_raw"):
        _add_section(headers["education"])
        _add_body(adapted_data["_formacao_raw"], size=7.5)

    skills = adapted_data.get("habilidades_tecnicas", [])
    if not preserve:
        skills = skills[:8]
    if skills:
        _add_section(headers["tech_skills"])
        _add_body("  •  ".join(skills), size=7.5)

    projs = adapted_data.get("projetos", [])
    if not preserve:
        projs = projs[:2]
    if projs:
        _add_section(headers["projects"])
        for proj in projs:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(proj.get("nome", ""))
            run.bold = True
            run.font.size = Pt(8)
            if proj.get("descricao"):
                _add_body(proj["descricao"], size=7)

    certs = adapted_data.get("certificacoes", [])
    if not preserve:
        certs = certs[:3]
    if certs:
        _add_section(headers["certifications"])
        for cert in certs:
            bp = doc.add_paragraph(f"• {cert}")
            bp.paragraph_format.space_after = Pt(0)
            for run in bp.runs:
                run.font.size = Pt(7.5)

    langs = adapted_data.get("idiomas", [])
    if langs:
        _add_section(headers["languages"])
        _add_body("  •  ".join(langs), size=7.5)

    try:
        temp_filepath = filepath + ".tmp"
        doc.save(temp_filepath)
        
        # Verificar duplicata por tamanho de arquivo
        temp_size = os.path.getsize(temp_filepath)
        duplicate_path = None
        for existing_file in os.listdir(output_dir):
            existing_path = os.path.join(output_dir, existing_file)
            if os.path.isfile(existing_path) and not existing_file.endswith(".tmp") and existing_file.endswith(".docx"):
                if os.path.getsize(existing_path) == temp_size:
                    duplicate_path = existing_path
                    break
        
        if duplicate_path:
            os.remove(temp_filepath)
            print(f"  ⚠ Currículo com o mesmo tamanho ({temp_size} bytes) já existe: {os.path.basename(duplicate_path)}. Não guardando duplicata.")
            return duplicate_path
        
        if os.path.exists(filepath):
            os.remove(filepath)
        os.rename(temp_filepath, filepath)
        print(f"  ✅ DOCX gerado (1 página): {filename}")
        return filepath
    except Exception as e:
        print(f"  ✗ Erro ao salvar DOCX: {e}")
        if 'temp_filepath' in locals() and os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except:
                pass
        return ""

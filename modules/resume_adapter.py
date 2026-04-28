"""
Módulo de Adaptação de Currículo — v2
Extrai texto do PDF original, adapta com Gemini e gera PDF + DOCX.
Melhorias: validação do JSON, geração DOCX, prompt aprimorado, fallback com currículo original.
"""

import json
import os
import re

import fitz  # PyMuPDF
from fpdf import FPDF
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

from .job_analyzer import _call_gemini, _extract_json

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# Cores do tema
COLOR_PRIMARY = (41, 65, 122)
COLOR_ACCENT = (0, 119, 181)
COLOR_SECONDARY = (80, 80, 80)
COLOR_LIGHT = (140, 140, 140)


def _ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def extract_resume_text(pdf_path: str) -> str:
    """Extrai todo o texto do currículo PDF."""
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


def _validate_adapted_data(data: dict, candidate_name: str) -> dict:
    """Valida e preenche campos obrigatórios ausentes no JSON adaptado."""
    if not data.get("nome"):
        data["nome"] = candidate_name
    for field in ["email", "telefone", "linkedin", "localizacao", "objetivo"]:
        if not isinstance(data.get(field), str):
            data[field] = ""
    for field in ["experiencia", "formacao", "habilidades_tecnicas",
                  "habilidades_comportamentais", "idiomas", "projetos", "certificacoes"]:
        if not isinstance(data.get(field), list):
            data[field] = []
    return data


def adapt_resume(resume_text: str, job: dict, analysis: dict) -> dict:
    """
    Usa Gemini para adaptar o currículo à vaga.
    Retorna dict com seções do currículo adaptado.
    """
    idioma = analysis.get("idioma_vaga", "pt-BR")
    if idioma.startswith("en"):
        lang_instruction = "O currículo DEVE ser totalmente em INGLÊS."
        obj_label = "Professional Summary"
    elif idioma == "pt-PT":
        lang_instruction = "O currículo deve ser em português de Portugal (evite brasileirismos)."
        obj_label = "Objetivo Profissional"
    elif idioma.startswith("es"):
        lang_instruction = "O currículo DEVE ser totalmente em ESPANHOL."
        obj_label = "Objetivo Profesional"
    else:
        lang_instruction = "O currículo deve ser em português brasileiro."
        obj_label = "Objetivo Profissional"

    requisitos = ", ".join(analysis.get("requisitos_obrigatorios", [])[:10])
    palavras_chave = ", ".join(analysis.get("palavras_chave", [])[:10])

    prompt = f"""Você é um especialista sênior em recrutamento com 20 anos de experiência.
Adapte o currículo para maximizar as chances de aprovação nesta vaga específica.

REGRAS CRÍTICAS:
1. NÃO invente habilidades, projetos ou experiências inexistentes
2. Reorganize e destaque as skills mais relevantes para a vaga
3. Adapte o objetivo para esta vaga específica usando palavras-chave da descrição
4. Mantenha TODOS os dados de contato originais intactos
5. {lang_instruction}
6. Máximo 2 páginas de conteúdo

CURRÍCULO ORIGINAL:
{resume_text[:4000]}

VAGA:
Título: {job.get('titulo', '')}
Empresa: {job.get('empresa', '')}
Local: {job.get('local', '')}
Nível: {analysis.get('nivel', 'junior')}
Área: {analysis.get('area', '')}
Requisitos obrigatórios: {requisitos}
Palavras-chave da vaga: {palavras_chave}
Descrição: {job.get('descricao', '')[:1500]}

Retorne APENAS JSON válido sem markdown:
{{
    "nome": "nome completo",
    "email": "email",
    "telefone": "telefone",
    "linkedin": "url linkedin",
    "localizacao": "cidade, estado/país",
    "objetivo": "objetivo profissional adaptado (3-4 linhas, incluindo palavras-chave da vaga)",
    "experiencia": [
        {{
            "cargo": "cargo",
            "empresa": "empresa",
            "periodo": "período",
            "descricao": ["conquista/responsabilidade 1", "conquista 2"]
        }}
    ],
    "formacao": [
        {{
            "curso": "curso",
            "instituicao": "instituição",
            "periodo": "período"
        }}
    ],
    "habilidades_tecnicas": ["skill1", "skill2"],
    "habilidades_comportamentais": ["soft skill 1"],
    "idiomas": ["Português - Nativo", "Inglês - Intermediário"],
    "projetos": [
        {{
            "nome": "nome do projeto",
            "descricao": "breve descrição com tecnologias"
        }}
    ],
    "certificacoes": ["certificação 1"]
}}"""

    print(f"  📝 Adaptando currículo para: {job.get('titulo', '')} ({job.get('empresa', '')})...")
    response_text = _call_gemini(prompt)

    if not response_text:
        print("  ⚠ Gemini não respondeu. Usando currículo base.")
        return {}

    adapted = _extract_json(response_text)
    if not adapted:
        print("  ⚠ Não foi possível parsear resposta do Gemini.")
        return {}

    candidate_name = os.getenv("CANDIDATE_NAME", "Paulo Neto")
    return _validate_adapted_data(adapted, candidate_name)


# ═══════════════════════════════════════════════════════════════════════
#  GERADOR DE PDF
# ═══════════════════════════════════════════════════════════════════════

# Mapa de caracteres Unicode → equivalentes ASCII seguros para Helvetica
_UNICODE_REPLACEMENTS = {
    "\u2013": "-",   # en-dash
    "\u2014": "-",   # em-dash
    "\u2018": "'",   # left single quote
    "\u2019": "'",   # right single quote
    "\u201c": '"',   # left double quote
    "\u201d": '"',   # right double quote
    "\u2026": "...", # ellipsis
    "\u00b7": "-",   # middle dot
    "\u2022": "-",   # bullet
    "\u2010": "-",   # hyphen
    "\u2011": "-",   # non-breaking hyphen
    "\u00a0": " ",   # non-breaking space
    "\u200b": "",    # zero-width space
    "\u00ad": "",    # soft hyphen
}


def _sanitize_text(text: str) -> str:
    """Substitui caracteres Unicode não suportados pela fonte Helvetica."""
    if not text:
        return ""
    for unicode_char, replacement in _UNICODE_REPLACEMENTS.items():
        text = text.replace(unicode_char, replacement)
    # Remove quaisquer caracteres fora do Latin-1 que restarem
    return text.encode("latin-1", errors="replace").decode("latin-1")


class ResumePDF(FPDF):
    """Gera PDFs de currículo com formatação profissional."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)
        self.COLOR_PRIMARY = COLOR_PRIMARY
        self.COLOR_SECONDARY = COLOR_SECONDARY
        self.COLOR_ACCENT = COLOR_ACCENT
        self.COLOR_LIGHT = COLOR_LIGHT
        self.COLOR_LINE = (200, 200, 200)

    def _add_section_title(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*self.COLOR_PRIMARY)
        self.cell(0, 7, _sanitize_text(title.upper()), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*self.COLOR_ACCENT)
        self.set_line_width(0.5)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def _add_text(self, text: str, bold: bool = False, size: int = 9, color: tuple = None):
        style = "B" if bold else ""
        self.set_font("Helvetica", style, size)
        self.set_text_color(*(color or self.COLOR_SECONDARY))
        self.multi_cell(0, 5, _sanitize_text(text))

    def _add_bullet(self, text: str):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.COLOR_SECONDARY)
        bullet_x = self.l_margin + 4
        self.set_x(bullet_x)
        self.cell(4, 5, "-")
        self.set_x(bullet_x + 5)
        self.multi_cell(self.w - self.r_margin - bullet_x - 5, 5, _sanitize_text(text))


def generate_resume_pdf(adapted_data: dict, job: dict, candidate_name: str) -> str:
    """Gera um PDF de currículo profissional. Retorna caminho do arquivo."""
    _ensure_output_dir()

    empresa_slug = re.sub(r"[^\w]", "_", job.get("empresa", "empresa"))[:30]
    vaga_slug = re.sub(r"[^\w]", "_", job.get("titulo", "vaga"))[:30]
    filename = f"CV_{candidate_name.replace(' ', '_')}_{empresa_slug}_{vaga_slug}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)

    pdf = ResumePDF()
    pdf.add_page()

    # ── CABEÇALHO ─────────────────────────────────────────────────
    nome = adapted_data.get("nome", candidate_name)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*pdf.COLOR_PRIMARY)
    pdf.cell(0, 10, _sanitize_text(nome), new_x="LMARGIN", new_y="NEXT", align="C")

    contato_parts = [
        adapted_data.get("email", ""),
        adapted_data.get("telefone", ""),
        adapted_data.get("localizacao", ""),
    ]
    contato_parts = [p for p in contato_parts if p]
    if contato_parts:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*pdf.COLOR_LIGHT)
        pdf.cell(0, 5, _sanitize_text("  |  ".join(contato_parts)), new_x="LMARGIN", new_y="NEXT", align="C")

    if adapted_data.get("linkedin"):
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*pdf.COLOR_ACCENT)
        pdf.cell(0, 5, _sanitize_text(adapted_data["linkedin"]), new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.ln(2)
    pdf.set_draw_color(*pdf.COLOR_PRIMARY)
    pdf.set_line_width(0.8)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)

    # ── OBJETIVO ──────────────────────────────────────────────────
    if adapted_data.get("objetivo"):
        pdf._add_section_title("Objetivo Profissional")
        pdf._add_text(adapted_data["objetivo"])

    # ── EXPERIÊNCIA ───────────────────────────────────────────────
    for exp in adapted_data.get("experiencia", []):
        if not adapted_data.get("_exp_header_added"):
            pdf._add_section_title("Experiência Profissional")
            adapted_data["_exp_header_added"] = True
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*pdf.COLOR_SECONDARY)
        pdf.cell(0, 6, _sanitize_text(exp.get("cargo", "")), new_x="LMARGIN", new_y="NEXT")
        info_parts = [p for p in [exp.get("empresa"), exp.get("periodo")] if p]
        if info_parts:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*pdf.COLOR_LIGHT)
            pdf.cell(0, 5, _sanitize_text(" | ".join(info_parts)), new_x="LMARGIN", new_y="NEXT")
        for item in exp.get("descricao", []):
            pdf._add_bullet(item)
        pdf.ln(2)

    # ── FORMAÇÃO ──────────────────────────────────────────────────
    for edu in adapted_data.get("formacao", []):
        if not adapted_data.get("_edu_header_added"):
            pdf._add_section_title("Formação Acadêmica")
            adapted_data["_edu_header_added"] = True
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*pdf.COLOR_SECONDARY)
        pdf.cell(0, 6, _sanitize_text(edu.get("curso", "")), new_x="LMARGIN", new_y="NEXT")
        info_parts = [p for p in [edu.get("instituicao"), edu.get("periodo")] if p]
        if info_parts:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*pdf.COLOR_LIGHT)
            pdf.cell(0, 5, _sanitize_text(" | ".join(info_parts)), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    # ── HABILIDADES TÉCNICAS ──────────────────────────────────────
    if adapted_data.get("habilidades_tecnicas"):
        pdf._add_section_title("Habilidades Técnicas")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*pdf.COLOR_SECONDARY)
        pdf.multi_cell(0, 5, _sanitize_text("  -  ".join(adapted_data["habilidades_tecnicas"])))

    # ── HABILIDADES COMPORTAMENTAIS ───────────────────────────────
    if adapted_data.get("habilidades_comportamentais"):
        pdf._add_section_title("Habilidades Comportamentais")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*pdf.COLOR_SECONDARY)
        pdf.multi_cell(0, 5, _sanitize_text("  -  ".join(adapted_data["habilidades_comportamentais"])))

    # ── PROJETOS ──────────────────────────────────────────────────
    for proj in adapted_data.get("projetos", []):
        if not adapted_data.get("_proj_header_added"):
            pdf._add_section_title("Projetos")
            adapted_data["_proj_header_added"] = True
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*pdf.COLOR_SECONDARY)
        pdf.cell(0, 5, _sanitize_text(proj.get("nome", "")), new_x="LMARGIN", new_y="NEXT")
        if proj.get("descricao"):
            pdf._add_text(proj["descricao"], size=8, color=pdf.COLOR_LIGHT)
        pdf.ln(1)

    # ── CERTIFICAÇÕES ─────────────────────────────────────────────
    if adapted_data.get("certificacoes"):
        pdf._add_section_title("Certificações")
        for cert in adapted_data["certificacoes"]:
            pdf._add_bullet(cert)

    # ── IDIOMAS ───────────────────────────────────────────────────
    if adapted_data.get("idiomas"):
        pdf._add_section_title("Idiomas")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*pdf.COLOR_SECONDARY)
        pdf.multi_cell(0, 5, _sanitize_text("  -  ".join(adapted_data["idiomas"])))


    try:
        pdf.output(filepath)
        print(f"  ✅ PDF gerado: {filename}")
        return filepath
    except Exception as e:
        print(f"  ✗ Erro ao salvar PDF: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════════════
#  GERADOR DE DOCX
# ═══════════════════════════════════════════════════════════════════════

def generate_resume_docx(adapted_data: dict, job: dict, candidate_name: str) -> str:
    """Gera um DOCX de currículo profissional. Retorna caminho do arquivo."""
    _ensure_output_dir()

    empresa_slug = re.sub(r"[^\w]", "_", job.get("empresa", "empresa"))[:30]
    vaga_slug = re.sub(r"[^\w]", "_", job.get("titulo", "vaga"))[:30]
    filename = f"CV_{candidate_name.replace(' ', '_')}_{empresa_slug}_{vaga_slug}.docx"
    filepath = os.path.join(OUTPUT_DIR, filename)

    doc = Document()

    # Margens
    for section in doc.sections:
        section.top_margin = Cm(1.5)
        section.bottom_margin = Cm(1.5)
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)

    def _add_heading(text: str, level: int = 1):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(18 if level == 1 else 11)
        r, g, b = COLOR_PRIMARY if level <= 2 else COLOR_SECONDARY
        run.font.color.rgb = RGBColor(r, g, b)
        return p

    def _add_section(title: str):
        p = doc.add_paragraph()
        run = p.add_run(title.upper())
        run.bold = True
        run.font.size = Pt(10)
        r, g, b = COLOR_PRIMARY
        run.font.color.rgb = RGBColor(r, g, b)
        doc.add_paragraph("─" * 60).runs[0].font.color.rgb = RGBColor(*COLOR_ACCENT)

    def _add_body(text: str, italic: bool = False, size: int = 9):
        p = doc.add_paragraph(text)
        for run in p.runs:
            run.italic = italic
            run.font.size = Pt(size)
            run.font.color.rgb = RGBColor(*COLOR_SECONDARY)
        return p

    # Nome
    _add_heading(adapted_data.get("nome", candidate_name))

    # Contato
    contato = [adapted_data.get("email", ""), adapted_data.get("telefone", ""),
               adapted_data.get("localizacao", "")]
    contato = [c for c in contato if c]
    if contato:
        p = doc.add_paragraph("  |  ".join(contato))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(*COLOR_LIGHT)

    if adapted_data.get("linkedin"):
        p = doc.add_paragraph(adapted_data["linkedin"])
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(*COLOR_ACCENT)

    # Objetivo
    if adapted_data.get("objetivo"):
        _add_section("Objetivo Profissional")
        _add_body(adapted_data["objetivo"])

    # Experiência
    if adapted_data.get("experiencia"):
        _add_section("Experiência Profissional")
        for exp in adapted_data["experiencia"]:
            p = doc.add_paragraph()
            run = p.add_run(exp.get("cargo", ""))
            run.bold = True
            run.font.size = Pt(10)
            info = " | ".join(filter(None, [exp.get("empresa"), exp.get("periodo")]))
            if info:
                _add_body(info, italic=True)
            for item in exp.get("descricao", []):
                doc.add_paragraph(f"• {item}", style="List Bullet")

    # Formação
    if adapted_data.get("formacao"):
        _add_section("Formação Acadêmica")
        for edu in adapted_data["formacao"]:
            p = doc.add_paragraph()
            run = p.add_run(edu.get("curso", ""))
            run.bold = True
            run.font.size = Pt(10)
            info = " | ".join(filter(None, [edu.get("instituicao"), edu.get("periodo")]))
            if info:
                _add_body(info, italic=True)

    # Habilidades técnicas
    if adapted_data.get("habilidades_tecnicas"):
        _add_section("Habilidades Técnicas")
        _add_body("  •  ".join(adapted_data["habilidades_tecnicas"]))

    # Projetos
    if adapted_data.get("projetos"):
        _add_section("Projetos")
        for proj in adapted_data["projetos"]:
            p = doc.add_paragraph()
            run = p.add_run(proj.get("nome", ""))
            run.bold = True
            run.font.size = Pt(9)
            if proj.get("descricao"):
                _add_body(proj["descricao"], size=8)

    # Certificações
    if adapted_data.get("certificacoes"):
        _add_section("Certificações")
        for cert in adapted_data["certificacoes"]:
            doc.add_paragraph(f"• {cert}")

    # Idiomas
    if adapted_data.get("idiomas"):
        _add_section("Idiomas")
        _add_body("  •  ".join(adapted_data["idiomas"]))

    try:
        doc.save(filepath)
        print(f"  ✅ DOCX gerado: {filename}")
        return filepath
    except Exception as e:
        print(f"  ✗ Erro ao salvar DOCX: {e}")
        return ""

"""
Módulo de Análise de Vagas — v2
Usa Google Gemini para analisar descrições de vagas.
Melhorias: cache por URL, fallback robusto, parsing JSON mais resistente.
"""

import json
import os
import re
import time

import google.generativeai as genai
from dotenv import load_dotenv
from .metrics import inc_rate_limit, inc_call

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, "config.env"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

MODEL_NAME = "gemini-1.5-flash"

# Cache simples em memória para evitar re-analisar mesma vaga na sessão
_analysis_cache: dict[str, dict] = {}


def _cache_key(job: dict) -> str:
    return f"{job.get('empresa', '').lower()}::{job.get('titulo', '').lower()}"


def _call_gemini(prompt: str, retries: int = 3) -> str:
    """Chama a API Gemini. Em caso de Rate Limit, pausa por 5 min e tenta novamente."""
    model = genai.GenerativeModel(MODEL_NAME)
    attempt = 0
    while True:
        try:
            response = model.generate_content(prompt)
            inc_call()
            return response.text
        except Exception as e:
            error_msg = str(e).lower()
            if "quota" in error_msg or "rate" in error_msg or "429" in error_msg:
                print("  ⏳ Rate limit/Cota da API atingida. Ativando fallback de currículo...")
                inc_rate_limit()
                return "__RATE_LIMIT__"
            elif "api_key_invalid" in error_msg or "invalid" in error_msg:
                print("  ✗ Chave de API Gemini inválida!")
                return ""
            else:
                attempt += 1
                print(f"  ✗ Erro Gemini: {e}")
                if attempt >= retries:
                    return ""
                time.sleep(5)
    return ""


def _extract_json(text: str) -> dict:
    """Extrai JSON de resposta com múltiplas estratégias de fallback."""
    if not text:
        return {}
    # 1. Bloco ```json
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if m:
        text = m.group(1)
    # 2. Parse direto
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # 3. Primeiro { ... } externo
    m2 = re.search(r"(\{.*\})", text, re.DOTALL)
    if m2:
        try:
            return json.loads(m2.group(1))
        except json.JSONDecodeError:
            pass
    # 4. Remover trailing commas
    try:
        cleaned = re.sub(r",\s*([}\]])", r"\1", text)
        return json.loads(cleaned)
    except Exception:
        pass
    return {}


def _default_analysis(job: dict) -> dict:
    return {
        "titulo_normalizado": job.get("titulo", ""),
        "empresa": job.get("empresa", ""),
        "nivel": "junior",
        "area": "outro",
        "requisitos_obrigatorios": [],
        "requisitos_desejaveis": [],
        "palavras_chave": [],
        "idioma_vaga": "pt-BR",
        "pais": "Brasil",
        "tipo": "remoto",
        "resumo": job.get("descricao", "")[:200],
    }


def analyze_job(job: dict) -> dict:
    """
    Analisa uma vaga usando Gemini.
    Usa cache para evitar re-analisar mesma vaga na sessão.
    """
    key = _cache_key(job)
    if key in _analysis_cache:
        print(f"  🗂️  Análise em cache: {job.get('titulo', '')}")
        return _analysis_cache[key]

    descricao = job.get("descricao", "")
    if not descricao or len(descricao) < 20:
        descricao = f"Vaga de {job['titulo']} na empresa {job['empresa']} em {job['local']}."

    prompt = f"""Analise esta descrição de vaga e retorne APENAS JSON válido (sem markdown):
{{
    "titulo_normalizado": "título limpo",
    "empresa": "{job['empresa']}",
    "nivel": "junior|estagio|pleno",
    "area": "desenvolvimento|dados|suporte|qa|outro",
    "requisitos_obrigatorios": ["skill1"],
    "requisitos_desejaveis": ["skill1"],
    "palavras_chave": ["kw1", "kw2"],
    "idioma_vaga": "pt-BR|pt-PT|en|es",
    "pais": "Brasil|Portugal|outro",
    "tipo": "remoto|presencial|hibrido",
    "resumo": "1-2 frases sobre a vaga"
}}

VAGA:
Título: {job['titulo']}
Empresa: {job['empresa']}
Local: {job['local']}
Descrição: {descricao[:2000]}"""

    print(f"  🤖 Analisando vaga: {job['titulo']}...")
    response_text = _call_gemini(prompt)

    result = _extract_json(response_text) if response_text else {}
    if not result:
        result = _default_analysis(job)

    for field in ["requisitos_obrigatorios", "requisitos_desejaveis", "palavras_chave"]:
        if not isinstance(result.get(field), list):
            result[field] = []

    _analysis_cache[key] = result
    return result

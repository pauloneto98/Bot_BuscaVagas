"""
Job Analyzer — Bot Busca Vagas
Uses Google Gemini to analyze job descriptions.
Features: in-memory cache, Groq/Llama fallback, resilient JSON parsing.
"""

import json
import os
import re
import time

import google.generativeai as genai
from groq import Groq

from app.config import settings
from app.services.logger import inc_rate_limit, inc_call

genai.configure(api_key=settings.GEMINI_API_KEY)

MODEL_NAME = settings.GEMINI_MODEL
GROQ_API_KEY = settings.GROQ_API_KEY

# In-memory cache to avoid re-analyzing the same job in a session
_analysis_cache: dict[str, dict] = {}


def _cache_key(job: dict) -> str:
    return f"{job.get('empresa', '').lower()}::{job.get('titulo', '').lower()}"


def _call_gemini(prompt: str, retries: int = 3) -> str:
    """Call the Gemini API. On rate limit, returns sentinel string."""
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
                print("  Rate limit/Cota da API atingida. Ativando fallback...")
                inc_rate_limit()
                return "__RATE_LIMIT__"
            elif "api_key_invalid" in error_msg or "invalid" in error_msg:
                print("  Chave de API Gemini invalida!")
                return ""
            else:
                attempt += 1
                print(f"  Erro Gemini: {e}")
                if attempt >= retries:
                    return ""
                time.sleep(5)
    return ""


def _call_groq(prompt: str) -> str:
    if not GROQ_API_KEY:
        return ""
    try:
        client = Groq(api_key=GROQ_API_KEY)
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=1024,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"  Erro Groq: {e}")
        return ""


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response with multiple fallback strategies."""
    if not text:
        return {}
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if m:
        text = m.group(1)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    m2 = re.search(r"(\{.*\})", text, re.DOTALL)
    if m2:
        try:
            return json.loads(m2.group(1))
        except json.JSONDecodeError:
            pass
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
        "nivel": "junior", "area": "outro",
        "requisitos_obrigatorios": [], "requisitos_desejaveis": [],
        "palavras_chave": [], "idioma_vaga": "pt-BR",
        "pais": "Brasil", "tipo": "remoto",
        "resumo": job.get("descricao", "")[:200],
    }


def analyze_job(job: dict) -> dict:
    """Analyze a job posting using Gemini. Uses cache to avoid re-analysis."""
    key = _cache_key(job)
    if key in _analysis_cache:
        print(f"  Analise em cache: {job.get('titulo', '')}")
        return _analysis_cache[key]

    descricao = job.get("descricao", "")
    if not descricao or len(descricao) < 20:
        descricao = f"Vaga de {job['titulo']} na empresa {job['empresa']} em {job['local']}."

    prompt = f"""Analise esta descricao de vaga e retorne APENAS JSON valido (sem markdown):
{{
    "titulo_normalizado": "titulo limpo",
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
Titulo: {job['titulo']}
Empresa: {job['empresa']}
Local: {job['local']}
Descricao: {descricao[:2000]}"""

    print(f"  Analisando vaga: {job['titulo']}...")
    response_text = _call_gemini(prompt)

    if response_text == "__RATE_LIMIT__":
        print("  Rate limit do Gemini. Acionando Groq/Llama 3...")
        response_text = _call_groq(prompt)
        if not response_text:
            response_text = ""

    result = _extract_json(response_text) if response_text else {}
    if not result:
        result = _default_analysis(job)

    for field in ["requisitos_obrigatorios", "requisitos_desejaveis", "palavras_chave"]:
        if not isinstance(result.get(field), list):
            result[field] = []

    _analysis_cache[key] = result
    return result

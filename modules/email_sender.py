"""
Módulo de Envio de Email — v2
Envia emails HTML profissionais com currículo PDF em anexo.
Melhorias: HTML email, CC para candidato, validação de endereço, SMTP mais robusto.
"""

import json
import os
import re
import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from dotenv import load_dotenv
from .job_analyzer import _call_gemini

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, "config.env"))

EMAIL_ADDRESS     = os.getenv("EMAIL_ADDRESS", "")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")
EMAIL_CC          = os.getenv("EMAIL_CC", "")
CANDIDATE_NAME    = os.getenv("CANDIDATE_NAME", "Paulo Neto")

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _is_valid_email(email: str) -> bool:
    return bool(_EMAIL_REGEX.match(email.strip()))


def generate_email_body(job: dict, analysis: dict, adapted_data: dict) -> dict:
    """
    Usa Gemini para gerar o corpo do email em texto puro e HTML.
    Retorna dict com: assunto, corpo_texto, corpo_html
    """
    idioma = analysis.get("idioma_vaga", "pt-BR")
    if idioma.startswith("en"):
        lang = "inglês"
    elif idioma == "pt-PT":
        lang = "português de Portugal"
    elif idioma.startswith("es"):
        lang = "espanhol"
    else:
        lang = "português brasileiro"

    skills_str = ", ".join(adapted_data.get("habilidades_tecnicas", [])[:5])
    objetivo_snippet = adapted_data.get("objetivo", "")[:200]

    prompt = f"""Crie um email profissional de candidatura para uma vaga de emprego.

DADOS:
- Candidato: {CANDIDATE_NAME}
- Vaga: {job.get('titulo', '')}
- Empresa: {job.get('empresa', '')}
- Habilidades principais: {skills_str}
- Resumo do candidato: {objetivo_snippet}

REGRAS:
1. Idioma: {lang}
2. Profissional, conciso e entusiasmado — máximo 120 palavras no corpo
3. Mencione a vaga e empresa pelo nome
4. Destaque 2-3 habilidades relevantes
5. Mencione que o currículo está em anexo
6. Não use colchetes ou placeholders

Retorne APENAS JSON válido sem markdown:
{{
    "assunto": "linha de assunto clara e profissional",
    "corpo": "corpo completo com saudação e despedida em texto puro"
}}"""

    response = _call_gemini(prompt)

    if response:
        m = re.search(r"\{.*\}", response, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group())
                assunto = data.get("assunto", "")
                corpo = data.get("corpo", "")
                if assunto and corpo:
                    return {
                        "assunto": assunto,
                        "corpo_texto": corpo,
                        "corpo_html": _text_to_html(corpo, job, CANDIDATE_NAME),
                    }
            except json.JSONDecodeError:
                pass

    # Fallback manual
    assunto = f"Candidatura – {job.get('titulo', 'Vaga')} – {CANDIDATE_NAME}"
    corpo = (
        f"Prezados,\n\n"
        f"Meu nome é {CANDIDATE_NAME} e gostaria de me candidatar à vaga de "
        f"{job.get('titulo', '')} na {job.get('empresa', 'sua empresa')}.\n\n"
        f"Tenho experiência com {skills_str} e estou em busca de novas oportunidades "
        f"para contribuir com a equipe de vocês.\n\n"
        f"Segue meu currículo em anexo para apreciação.\n\n"
        f"Agradeço a atenção e fico à disposição para uma conversa.\n\n"
        f"Atenciosamente,\n{CANDIDATE_NAME}"
    )
    return {
        "assunto": assunto,
        "corpo_texto": corpo,
        "corpo_html": _text_to_html(corpo, job, CANDIDATE_NAME),
    }


def _text_to_html(text: str, job: dict, candidate_name: str) -> str:
    """Converte texto puro em HTML profissional para o email."""
    paragraphs = text.split("\n\n")
    html_paras = "".join(
        f"<p style='margin:0 0 12px 0;'>{p.replace(chr(10), '<br>')}</p>"
        for p in paragraphs if p.strip()
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#f4f6f9;padding:30px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:8px;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08);overflow:hidden;">

        <!-- Cabeçalho -->
        <tr>
          <td style="background:linear-gradient(135deg,#29417a,#0077b5);
                     padding:28px 36px;text-align:center;">
            <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;">
              {candidate_name}
            </h1>
            <p style="margin:6px 0 0;color:#b0c8e8;font-size:13px;">
              Candidatura para {job.get('titulo', 'Vaga')}
            </p>
          </td>
        </tr>

        <!-- Corpo -->
        <tr>
          <td style="padding:32px 36px;color:#3d3d3d;font-size:14px;line-height:1.7;">
            {html_paras}
          </td>
        </tr>

        <!-- Rodapé -->
        <tr>
          <td style="background:#f8f9fb;padding:16px 36px;
                     border-top:1px solid #e8eaed;text-align:center;">
            <p style="margin:0;color:#888;font-size:11px;">
              📎 Currículo em anexo &nbsp;|&nbsp;
              Vaga: <strong>{job.get('titulo', '')}</strong> — {job.get('empresa', '')}
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_application_email(
    to_email: str,
    job: dict,
    analysis: dict,
    adapted_data: dict,
    resume_path: str,
) -> bool:
    """
    Envia email HTML de candidatura com currículo PDF em anexo.
    Retorna True se enviado com sucesso.
    """
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        print("  ✗ Credenciais de email não configuradas!")
        return False

    if not to_email or not _is_valid_email(to_email):
        print(f"  ✗ Email de destino inválido: '{to_email}'")
        return False

    email_content = generate_email_body(job, analysis, adapted_data)

    # Montar mensagem multipart (HTML + texto puro)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = email_content["assunto"]
    msg["From"]    = f"{CANDIDATE_NAME} <{EMAIL_ADDRESS}>"
    msg["To"]      = to_email
    if EMAIL_CC and _is_valid_email(EMAIL_CC) and EMAIL_CC != to_email:
        msg["Cc"] = EMAIL_CC

    msg.attach(MIMEText(email_content["corpo_texto"], "plain", "utf-8"))
    msg.attach(MIMEText(email_content["corpo_html"],  "html",  "utf-8"))

    # Converter para MIMEMultipart mixed para suportar anexo
    outer = MIMEMultipart("mixed")
    outer["Subject"] = msg["Subject"]
    outer["From"]    = msg["From"]
    outer["To"]      = msg["To"]
    if msg.get("Cc"):
        outer["Cc"] = msg["Cc"]
    outer.attach(msg)

    # Anexar currículo PDF
    if resume_path and os.path.exists(resume_path):
        with open(resume_path, "rb") as f:
            part = MIMEBase("application", "pdf")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=os.path.basename(resume_path),
        )
        outer.attach(part)

    # Enviar via Gmail SMTP SSL
    recipients = [to_email]
    if EMAIL_CC and _is_valid_email(EMAIL_CC) and EMAIL_CC != to_email:
        recipients.append(EMAIL_CC)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
            smtp.sendmail(EMAIL_ADDRESS, recipients, outer.as_string())
        print(f"  📧 Email enviado → {to_email}")
        if EMAIL_CC in recipients:
            print(f"     (CC enviado para {EMAIL_CC})")
        print(f"     Assunto: {email_content['assunto']}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("  ✗ Autenticação falhou! Use uma Senha de App do Gmail (16 chars).")
        print("    Gere em: https://myaccount.google.com/apppasswords")
        return False
    except smtplib.SMTPRecipientsRefused:
        print(f"  ✗ Destinatário recusado: {to_email}")
        return False
    except Exception as e:
        print(f"  ✗ Erro ao enviar email: {e}")
        return False

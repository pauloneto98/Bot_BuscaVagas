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
    Gera o corpo do e-mail usando template fixo no idioma da vaga.
    Suporta: pt-BR, pt-PT, en, es
    Retorna dict com: assunto, corpo_texto, corpo_html
    """
    idioma = analysis.get("idioma_vaga", "pt-BR")
    skills_str = ", ".join(adapted_data.get("habilidades_tecnicas", [])[:5])
    titulo = job.get('titulo', 'Position')
    empresa = job.get('empresa', 'your company')

    if idioma.startswith("en"):
        assunto = f"Application \u2013 {titulo} \u2013 {CANDIDATE_NAME}"
        corpo = (
            f"Dear Hiring Manager,\n\n"
            f"My name is {CANDIDATE_NAME} and I am writing to apply for the "
            f"{titulo} position at {empresa}.\n\n"
            f"I have experience with {skills_str or 'software development and IT support'} "
            f"and I am eager to contribute to your team.\n\n"
            f"Please find my resum\u00e9 attached for your review.\n\n"
            f"Thank you for your time and consideration. "
            f"I look forward to the opportunity to discuss my qualifications further.\n\n"
            f"Best regards,\n{CANDIDATE_NAME}"
        )

    elif idioma.startswith("es"):
        assunto = f"Solicitud de Empleo \u2013 {titulo} \u2013 {CANDIDATE_NAME}"
        corpo = (
            f"Estimado/a equipo de Selecci\u00f3n,\n\n"
            f"Mi nombre es {CANDIDATE_NAME} y me dirijo a ustedes para postularme "
            f"al puesto de {titulo} en {empresa}.\n\n"
            f"Cuento con experiencia en {skills_str or 'desarrollo de software y soporte t\u00e9cnico'} "
            f"y tengo gran inter\u00e9s en formar parte de su equipo.\n\n"
            f"Adjunto mi curr\u00edculum v\u00edtae para su consideraci\u00f3n.\n\n"
            f"Agradezco su atenci\u00f3n y quedo a su disposici\u00f3n para cualquier consulta.\n\n"
            f"Un cordial saludo,\n{CANDIDATE_NAME}"
        )

    elif idioma == "pt-PT":
        assunto = f"Candidatura \u2013 {titulo} \u2013 {CANDIDATE_NAME}"
        corpo = (
            f"Exmos. Senhores,\n\n"
            f"O meu nome \u00e9 {CANDIDATE_NAME} e venho por este meio candidatar-me "
            f"\u00e0 vaga de {titulo} na {empresa}.\n\n"
            f"Tenho experi\u00eancia em {skills_str or 'desenvolvimento de software e suporte de TI'} "
            f"e estou motivado/a para contribuir com a vossa equipa.\n\n"
            f"Junto em anexo o meu curr\u00edculo para aprecia\u00e7\u00e3o.\n\n"
            f"Agrade\u00e7o a aten\u00e7\u00e3o dispensada e fico ao dispor para esclarecimentos.\n\n"
            f"Com os melhores cumprimentos,\n{CANDIDATE_NAME}"
        )

    else:  # pt-BR (padr\u00e3o)
        assunto = f"Candidatura \u2013 {titulo} \u2013 {CANDIDATE_NAME}"
        corpo = (
            f"Prezados,\n\n"
            f"Meu nome \u00e9 {CANDIDATE_NAME} e gostaria de me candidatar \u00e0 vaga de "
            f"{titulo} na {empresa}.\n\n"
            f"Tenho experi\u00eancia com {skills_str or 'desenvolvimento de software e suporte de TI'} "
            f"e estou em busca de novas oportunidades para contribuir com a equipe de voc\u00eas.\n\n"
            f"Segue meu curr\u00edculo em anexo para aprecia\u00e7\u00e3o.\n\n"
            f"Agrade\u00e7o a aten\u00e7\u00e3o e fico \u00e0 disposi\u00e7\u00e3o para uma conversa.\n\n"
            f"Atenciosamente,\n{CANDIDATE_NAME}"
        )

    return {
        "assunto": assunto,
        "corpo_texto": corpo,
        "corpo_html": _text_to_html(corpo, job, CANDIDATE_NAME, idioma),
    }


def _text_to_html(text: str, job: dict, candidate_name: str, idioma: str = "pt-BR") -> str:
    """Converte texto puro em HTML profissional para o email."""
    lang_map = {"en": "en", "es": "es", "pt-PT": "pt-PT", "pt-BR": "pt-BR"}
    lang = lang_map.get(idioma, "pt-BR")
    paragraphs = text.split("\n\n")
    html_paras = "".join(
        f"<p style='margin:0 0 12px 0;'>{p.replace(chr(10), '<br>')}</p>"
        for p in paragraphs if p.strip()
    )

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#f4f6f9;padding:30px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:8px;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08);overflow:hidden;">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#29417a,#0077b5);
                     padding:28px 36px;text-align:center;">
            <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;">
              {candidate_name}
            </h1>
            <p style="margin:6px 0 0;color:#b0c8e8;font-size:13px;">
              {job.get('titulo', '')}
            </p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px 36px;color:#3d3d3d;font-size:14px;line-height:1.7;">
            {html_paras}
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f8f9fb;padding:16px 36px;
                     border-top:1px solid #e8eaed;text-align:center;">
            <p style="margin:0;color:#888;font-size:11px;">
              &#128206; Resume attached &nbsp;|&nbsp;
              Position: <strong>{job.get('titulo', '')}</strong> &mdash; {job.get('empresa', '')}
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

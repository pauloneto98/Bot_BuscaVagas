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

from app.core.analyzer import _call_gemini

from app.config import settings


EMAIL_ADDRESS     = settings.EMAIL_ADDRESS
EMAIL_APP_PASSWORD = settings.EMAIL_APP_PASSWORD
EMAIL_CC          = settings.EMAIL_CC
CANDIDATE_NAME    = settings.CANDIDATE_NAME

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _is_valid_email(email: str) -> bool:
    return bool(_EMAIL_REGEX.match(email.strip()))


def should_send_email_for_job(job: dict) -> bool:
    """
    Decide se devemos enviar e-mail para a vaga com base nas configurações
    e na inteligência do filtro de e-mails.
    """
    if not settings.ENABLE_EMAIL_SENDING:
        return False
        
    if settings.EMAIL_ONLY_SMALL_COMPANIES:
        # Se a vaga vem de uma grande plataforma de ATS e não tem email direto,
        # ou se a fonte for bloqueada, evitamos o envio automático.
        fonte = job.get("fonte", "").lower()
        if any(src.lower() in fonte for src in settings.EMAIL_BLOCKED_SOURCES):
            if not job.get("email_direto"):
                return False
                
    return True


def generate_email_body(job: dict, analysis: dict, adapted_data: dict, candidate_name: str = CANDIDATE_NAME) -> dict:
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
        assunto = f"Application \u2013 {titulo} \u2013 {candidate_name}"
        corpo = (
            f"Dear Hiring Manager,\n\n"
            f"My name is {candidate_name} and I am writing to apply for the "
            f"{titulo} position at {empresa}.\n\n"
            f"I have experience with {skills_str or 'software development and IT support'} "
            f"and I am eager to contribute to your team.\n\n"
            f"Please find my resum\u00e9 attached for your review.\n\n"
            f"Thank you for your time and consideration. "
            f"I look forward to the opportunity to discuss my qualifications further.\n\n"
            f"Best regards,\n{candidate_name}"
        )

    elif idioma.startswith("es"):
        assunto = f"Solicitud de Empleo \u2013 {titulo} \u2013 {candidate_name}"
        corpo = (
            f"Estimado/a equipo de Selecci\u00f3n,\n\n"
            f"Mi nombre es {candidate_name} y me dirijo a ustedes para postularme "
            f"al puesto de {titulo} en {empresa}.\n\n"
            f"Cuento con experiencia en {skills_str or 'desarrollo de software y soporte t\u00e9cnico'} "
            f"y tenho gran inter\u00e9s en formar parte de su equipo.\n\n"
            f"Adjunto mi curr\u00edculum v\u00edtae para su consideraci\u00f3n.\n\n"
            f"Agradezco su atenci\u00f3n y quedo a su disposici\u00f3n para cualquier consulta.\n\n"
            f"Un cordial saludo,\n{candidate_name}"
        )

    elif idioma == "pt-PT":
        assunto = f"Candidatura \u2013 {titulo} \u2013 {candidate_name}"
        corpo = (
            f"Exmos. Senhores,\n\n"
            f"O meu nome \u00e9 {candidate_name} e venho por este meio candidatar-me "
            f"\u00e0 vaga de {titulo} na {empresa}.\n\n"
            f"Tenho experi\u00eancia em {skills_str or 'desenvolvimento de software e suporte de TI'} "
            f"e estou motivado/a para contribuir com a vossa equipa.\n\n"
            f"Junto em anexo o meu curr\u00edculo para aprecia\u00e7\u00e3o.\n\n"
            f"Agrade\u00e7o a aten\u00e7\u00e3o dispensada e fico ao dispor para esclarecimentos.\n\n"
            f"Com os melhores cumprimentos,\n{candidate_name}"
        )

    else:  # pt-BR (padrão)
        assunto = f"Candidatura \u2013 {titulo} \u2013 {candidate_name}"
        corpo = (
            f"Prezados,\n\n"
            f"Meu nome \u00e9 {candidate_name} e gostaria de me candidatar \u00e0 vaga de "
            f"{titulo} na {empresa}.\n\n"
            f"Tenho experi\u00eancia com {skills_str or 'desenvolvimento de software e suporte de TI'} "
            f"e estou em busca de novas oportunidades para contribuir com a equipe de voc\u00eas.\n\n"
            f"Segue meu curr\u00edculo em anexo para aprecia\u00e7\u00e3o.\n\n"
            f"Agrade\u00e7o a aten\u00e7\u00e3o e fico \u00e0 disposição para uma conversa.\n\n"
            f"Atenciosamente,\n{candidate_name}"
        )

    return {
        "assunto": assunto,
        "corpo_texto": corpo,
        "corpo_html": _text_to_html(corpo, job, candidate_name, idioma),
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
    user_settings=None,
) -> bool:
    """
    Envia email HTML de candidatura com currículo PDF em anexo.
    Retorna True se enviado com sucesso.
    """
    email_address = user_settings.email_address if user_settings else EMAIL_ADDRESS
    email_app_password = user_settings.email_app_password if user_settings else EMAIL_APP_PASSWORD
    email_cc = user_settings.email_cc if user_settings else EMAIL_CC
    candidate_name = user_settings.candidate_name if user_settings else CANDIDATE_NAME

    if not email_address or not email_app_password:
        print("  ✗ Credenciais de email não configuradas!")
        return False

    if not to_email or not _is_valid_email(to_email):
        print(f"  ✗ Email de destino inválido: '{to_email}'")
        return False

    email_content = generate_email_body(job, analysis, adapted_data, candidate_name=candidate_name)

    # Montar mensagem multipart (HTML + texto puro)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = email_content["assunto"]
    msg["From"]    = f"{candidate_name} <{email_address}>"
    msg["To"]      = to_email
    if email_cc and _is_valid_email(email_cc) and email_cc != to_email:
        msg["Cc"] = email_cc

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
    if email_cc and _is_valid_email(email_cc) and email_cc != to_email:
        recipients.append(email_cc)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(email_address, email_app_password)
            smtp.sendmail(email_address, recipients, outer.as_string())
        print(f"  📧 Email enviado → {to_email}")
        if email_cc in recipients:
            print(f"     (CC enviado para {email_cc})")
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
        return Falseemail: {e}")
        return False

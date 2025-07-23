from flask import render_template_string
from .tasks import send_email_task
from .models import SendLog, Contact, db
from flask_mail import Message
from app import mail
import smtplib
from email.mime.text import MIMEText

def enqueue_emails(template, contacts, rate_limit=None, robot_id=None):
    """
    Enqueue emails for sending with optional rate limit.
    """
    for contact in contacts:
        # Construir contexto de dados a partir dos atributos do model
        data = {col.name: getattr(contact, col.name) for col in contact.__table__.columns}
        # Render dynamic subject and body
        subject = render_template_string(template.subject, **data)
        body = render_template_string(template.body, **data)
        # Queue task (destinatário, assunto, corpo)
        # Enfileirar task com robot_id para que a task saiba onde buscar credenciais
        send_email_task.apply_async(
            args=[robot_id, data.get('email'), subject, body],
            rate_limit=rate_limit or ''
        )
        # Log as pending
        log = SendLog(contact_id=contact.id, template_id=template.id, status='pending')
        db.session.add(log)
    db.session.commit()
    
def send_email(subject, recipients, body, html=None):
    msg = Message(subject, recipients=recipients, body=body, html=html)
    mail.send(msg)

def send_email_via_smtp(to_address, smtp_config):
    """
    Envia um email usando configurações SMTP dinâmicas.
    """
    try:
        msg = MIMEText("Este é um email enviado dinamicamente.")
        msg['Subject'] = "Assunto do Email"
        msg['From'] = smtp_config['username']
        msg['To'] = to_address

        with smtplib.SMTP(smtp_config['server'], smtp_config['port']) as server:
            server.starttls()
            server.login(smtp_config['username'], smtp_config['password'])
            server.sendmail(smtp_config['username'], [to_address], msg.as_string())
    except Exception as e:
        raise Exception(f"Erro ao enviar email: {str(e)}")
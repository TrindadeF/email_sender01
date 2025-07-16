from flask import render_template_string
from .tasks import send_email_task
from .models import SendLog, Contact, db
from flask_mail import Message
from app import mail

def enqueue_emails(template, contacts, rate_limit=None):
    """
    Enqueue emails for sending with optional rate limit.
    """
    for contact in contacts:
        # Render dynamic subject and body
        subject = render_template_string(template.subject, **contact.data)
        body = render_template_string(template.body, **contact.data)
        # Queue task
        send_email_task.apply_async(
            args=[contact.data.get('email'), subject, body],
            rate_limit=rate_limit or ''
        )
        # Log as pending
        log = SendLog(contact_id=contact.id, template_id=template.id, status='pending')
        db.session.add(log)
    db.session.commit()
    
def send_email(subject, recipients, body, html=None):
    msg = Message(subject, recipients=recipients, body=body, html=html)
    mail.send(msg)
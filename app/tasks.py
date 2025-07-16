from . import celery

@celery.task(name='app.tasks.send_email_task')
def send_email_task(to_address, subject, body):
    """
    Dummy email sending task; replace with real SMTP logic.
    """
    print(f"Sending email to {to_address} with subject: {subject}")
    # TODO: integrate with SMTP server
    return True

from flask_mail import Message
from app import mail, celery
from app.models import Robot
from email.mime.text import MIMEText
import smtplib

@celery.task(name='app.tasks.send_email_task')
def send_email_task(robot_id, to_address, subject, body):
    robot = Robot.query.get(robot_id)
    if not robot:
        return {'status': 'error', 'error': 'Robô não encontrado'}

    try:
        # Configurar o servidor SMTP usando o email interno
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = robot.internal_email
        msg['To'] = to_address

        with smtplib.SMTP(robot.smtp_server, robot.smtp_port) as server:
            server.starttls()
            server.login(robot.smtp_username, robot.smtp_password)
            server.sendmail(robot.internal_email, [to_address], msg.as_string())

        return {'status': 'success', 'to': to_address}
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
        return {'status': 'error', 'error': str(e)}
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

        # Log de envio bem-sucedido
        from app.models import RobotLog, db
        db.session.add(RobotLog(robot_id=robot.id, action='send', details=f'Email enviado para {to_address}'))
        db.session.commit()
        return {'status': 'success', 'to': to_address}
    except Exception as e:
        # Log de erro
        from app.models import RobotLog, db
        db.session.add(RobotLog(robot_id=robot.id, action='error', details=str(e)))
        db.session.commit()
        return {'status': 'error', 'error': str(e)}
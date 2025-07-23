from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from flask_jwt_extended import jwt_required, get_jwt_identity
import csv, io, json
import pandas as pd
from datetime import datetime
from .models import ContactList, Contact, EmailTemplate, InternalEmail, db, User
from .models import SendLog, Robot, RobotLog
from .filters import apply_filters
from .email_service import enqueue_emails, send_email_via_smtp
import unicodedata

main = Blueprint('main', __name__)

@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@main.route('/dashboard')
@login_required
def dashboard():
    user = current_user 
    stats = {
        'total_robots': Robot.query.count(),
        'total_sent': SendLog.query.filter_by(status='sent').count(),
        'total_pending': SendLog.query.filter_by(status='pending').count(),
        'delivery_rate': calculate_delivery_rate()
    }
    robots = Robot.query.all()
    return render_template('dashboard.html', stats=stats, robots=robots, user=user)

@main.route('/templates', methods=['GET', 'POST'])
@login_required
def templates():
    if request.method == 'POST':
        template = EmailTemplate(
            name=request.form['name'],
            subject=request.form['subject'],
            body=request.form['body'],
            user_id=current_user.id
        )
        db.session.add(template)
        db.session.commit()
        flash('Template criado com sucesso!', 'success')
        return redirect(url_for('main.templates'))
    
    templates = EmailTemplate.query.filter_by(user_id=current_user.id).all()
    return render_template('templates.html', templates=templates)

@main.route('/templates/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(id):
    template = EmailTemplate.query.get_or_404(id)
    # Verificar se o template pertence ao usuário atual
    if template.user_id != current_user.id:
        flash('Você não tem permissão para editar este template.', 'danger')
        return redirect(url_for('main.templates'))
    
    if request.method == 'POST':
        template.name = request.form['name']
        template.subject = request.form['subject']
        template.body = request.form['body']
        db.session.commit()
        flash('Template atualizado com sucesso!', 'success')
        return redirect(url_for('main.templates'))
    return render_template('edit_template.html', template=template)

@main.route('/templates/<int:id>/delete', methods=['POST'])
@login_required
def delete_template(id):
    template = EmailTemplate.query.get_or_404(id)
    db.session.delete(template)
    db.session.commit()
    flash('Template excluído com sucesso!', 'success')
    return redirect(url_for('main.templates'))


@main.route('/api/contacts/<titulo>', methods=['GET'])
@login_required
def get_contacts_by_title(titulo):
    contacts = Contact.query.filter_by(titulo=titulo).all()
    return jsonify([{'id': contact.id, 'email': contact.email, 'nome_congresso': contact.nome_congresso, 'ano_congresso': contact.ano_congresso} for contact in contacts])


@main.route('/robots', methods=['GET', 'POST'])
@login_required
def robots():
    if request.method == 'POST':
        internal_email = request.form.get('internal_email')
        # Processar regras de filtro opcionais (JSON)
        raw_rules = request.form.get('filter_rules', '')
        try:
            filter_rules = json.loads(raw_rules) if raw_rules else {}
        except Exception:
            filter_rules = {}
        robot = Robot(
            name=request.form.get('name'),
            email=request.form.get('email'),
            template_id=request.form.get('template_id'),
            user_id=current_user.id,
            emails_per_hour=request.form.get('emails_per_hour'),
            start_time=datetime.strptime(request.form.get('start_time'), '%H:%M').time(),
            end_time=datetime.strptime(request.form.get('end_time'), '%H:%M').time(),
            working_days=request.form.getlist('days[]'),
            filter_rules=filter_rules,
            internal_email=internal_email,
            contact_title=request.form.get('contact_title')
        )
        db.session.add(robot)
        db.session.commit()
        # Enfileirar envio inicial de e-mails para o título selecionado
        contacts = Contact.query.filter_by(titulo=robot.contact_title).all()
        # Enfileirar e-mails com ID do robô para que a task receba robot_id corretamente
        enqueue_emails(robot.template, contacts,
                       rate_limit=str(robot.emails_per_hour),
                       robot_id=robot.id)
        flash('Robô criado e e-mails enfileirados com sucesso!', 'success')
        return redirect(url_for('main.dashboard'))
    
    # Buscar templates, titulos e emails 
    internal_emails = InternalEmail.query.filter_by(user_id=current_user.id).all()
    templates = EmailTemplate.query.filter_by(user_id=current_user.id).all()
    titles = db.session.query(Contact.titulo).distinct().all()

    return render_template('robots.html', templates=templates, titles=titles, internal_emails=internal_emails)

@main.route('/internal-emails', methods=['GET', 'POST'])
@login_required
def internal_emails():
    if request.method == 'POST':
        email = request.form.get('email')
        description = request.form.get('description')
        smtp_server = request.form.get('smtp_server')
        smtp_port = request.form.get('smtp_port')
        smtp_username = request.form.get('smtp_username')
        smtp_password = request.form.get('smtp_password')

        # Verificar se todos os campos obrigatórios estão preenchidos
        if not email or not smtp_server or not smtp_port or not smtp_username or not smtp_password:
            flash('Todos os campos são obrigatórios.', 'error')
            return redirect(url_for('main.internal_emails'))

        # Associar email ao usuário logado
        internal_email = InternalEmail(
            email=email,
            description=description,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            user_id=current_user.id
        )
        db.session.add(internal_email)
        db.session.commit()
        flash('Email interno cadastrado com sucesso!', 'success')
        return redirect(url_for('main.internal_emails'))

    # Listar emails internos do usuário logado
    emails = InternalEmail.query.filter_by(user_id=current_user.id).all()
    return render_template('internal_emails.html', emails=emails)

@main.route('/internal-emails/delete/<int:email_id>', methods=['POST'])
@login_required
def delete_internal_email(email_id):
    email = InternalEmail.query.get_or_404(email_id)
    db.session.delete(email)
    db.session.commit()
    flash('Email interno excluído com sucesso!', 'success')
    return redirect(url_for('main.internal_emails'))

@main.route('/api/robots/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_robot(id):
    robot = Robot.query.get_or_404(id)
    # Verificar se o robô pertence ao usuário atual
    if robot.user_id != current_user.id:
        return jsonify({'error': 'Você não tem permissão para modificar este robô'}), 403
    robot.active = not robot.active
    db.session.add(RobotLog(
        robot=robot,
        action='stop' if robot.active else 'start'
    ))
    db.session.commit()
    return jsonify({'status': 'success'})
 
@main.route('/api/robots/<int:id>/logs', methods=['GET'])
@login_required
def robot_logs(id):
    from .models import RobotLog
    robot = Robot.query.get_or_404(id)
    # Verificar permissão
    if robot.user_id != current_user.id:
        return jsonify({'error': 'Você não tem permissão'}), 403
    # Buscar últimos 50 logs
    logs = RobotLog.query.filter_by(robot_id=id).order_by(RobotLog.timestamp.desc()).limit(50).all()
    return jsonify([
        {'timestamp': log.timestamp.isoformat(), 'action': log.action, 'details': log.details}
        for log in logs
    ])

@main.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        try:
            # Verificar se o arquivo foi enviado
            if 'file' not in request.files:
                flash('Nenhum arquivo selecionado', 'error')
                return redirect(request.url)
            
            file = request.files['file']
            if file.filename == '':
                flash('Nenhum arquivo selecionado', 'error')
                return redirect(request.url)

            # Ler o arquivo Excel
            df = pd.read_excel(file)
            print("DataFrame lido:", df.head())  # Debug
            
            def normalize_col(col):
                # Remove acentos, coloca em minúsculo e troca espaços por underline
                col = unicodedata.normalize('NFKD', col).encode('ASCII', 'ignore').decode('ASCII')
                return col.strip().lower().replace(' ', '_')

            # Padronizar nomes das colunas
            df.columns = [normalize_col(col) for col in df.columns]
            print("Colunas após padronização:", df.columns)  # Debug
            
            # Validar colunas necessárias
            # A coluna 'numero' representa o identificador importado, substituindo 'num'
            required_cols = ['numero', 'titulo', 'emails', 'nome_do_congresso', 'ano_do_congresso']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                flash(f'Colunas obrigatórias ausentes: {", ".join(missing_cols)}', 'error')
                return redirect(request.url)
            
            # Criar nova lista de contatos
            name = request.form.get('name', 'Lista Importada ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            contact_list = ContactList(name=name, user_id=current_user.id)
            db.session.add(contact_list)
            db.session.flush()

            # Processar cada linha do Excel
            for _, row in df.iterrows():
                emails = [e.strip() for e in str(row['emails']).split(',') if e.strip()]
                for email in emails:
                    contact = Contact(
                        list_id=contact_list.id,
                        titulo=str(row['titulo']),
                        email=email,
                        nome_congresso=str(row['nome_do_congresso']),
                        ano_congresso=str(row['ano_do_congresso'])
                    )
                    db.session.add(contact)
            
            db.session.commit()
            flash(f'Lista importada com sucesso! {len(df)} contatos adicionados.', 'success')
        except Exception as e:
            db.session.rollback()
            print("Erro ao processar arquivo:", str(e))  # Debug
            flash(f'Erro ao processar arquivo: {str(e)}', 'error')
            return redirect(request.url)

    # Buscar todas as listas de contatos do usuário atual
    contact_lists = ContactList.query.filter_by(user_id=current_user.id).all()
    for contact_list in contact_lists:
        contact_list.contacts = Contact.query.filter_by(list_id=contact_list.id).all()

    return render_template('upload.html', contact_lists=contact_lists)

@main.route('/robots/monitor')
@login_required
def robots_monitor():
    robots = Robot.query.filter_by(user_id=current_user.id).all()
    return render_template('robots_monitor.html', robots=robots)

@main.route('/compose', methods=['GET', 'POST'])
@login_required
def compose():
    templates = EmailTemplate.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        tpl_id = request.form.get('template')
        filters_json = request.form.get('filters', '{}')
        rate = request.form.get('rate') or ''
        try:
            filters = json.loads(filters_json)
        except ValueError:
            filters = {}
        template = EmailTemplate.query.get_or_404(tpl_id)
        query = Contact.query
        query = apply_filters(query, Contact, filters)
        contacts = query.all()
        enqueue_emails(template, contacts, rate)
        flash(f'Enfileirados {len(contacts)} e-mails', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('compose.html', templates=templates)

@main.route('/send-email/<int:robot_id>', methods=['POST'])
@login_required
def send_email(robot_id):
    robot = Robot.query.get_or_404(robot_id)
    if robot.user_id != current_user.id:
        flash('Você não tem permissão para enviar emails com este robô.', 'danger')
        return redirect(url_for('main.dashboard'))

    internal_email = InternalEmail.query.filter_by(email=robot.internal_email).first()
    if not internal_email:
        flash('O email interno associado ao robô não foi encontrado.', 'danger')
        return redirect(url_for('main.dashboard'))

    # Configurar credenciais SMTP dinamicamente
    smtp_config = {
        'server': internal_email.smtp_server,
        'port': internal_email.smtp_port,
        'username': internal_email.smtp_username,
        'password': internal_email.smtp_password
    }

    # Enviar email usando smtp_config
    try:
        send_email_via_smtp(robot.email, smtp_config)
        flash('Email enviado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao enviar email: {str(e)}', 'danger')

    return redirect(url_for('main.dashboard'))

def calculate_delivery_rate():
    total = SendLog.query.count()
    if total == 0:
        return 0
    sent = SendLog.query.filter_by(status='sent').count()
    return round((sent / total) * 100, 2)

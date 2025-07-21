from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from flask_jwt_extended import jwt_required, get_jwt_identity
import csv, io, json
import pandas as pd
from datetime import datetime
from .models import ContactList, Contact, EmailTemplate, InternalEmail, db, User
from .models import SendLog, Robot, RobotLog
from .filters import apply_filters
from .email_service import enqueue_emails
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



@main.route('/robots', methods=['GET', 'POST'])
@login_required
def robots():
    if request.method == 'POST':
        internal_email = request.form.get('internal_email')
        robot = Robot(
            name=request.form['name'],
            email=request.form['email'],
            template_id=request.form['template_id'],
            user_id=current_user.id,
            emails_per_hour=request.form['emails_per_hour'],
            start_time=datetime.strptime(request.form['start_time'], '%H:%M').time(),
            end_time=datetime.strptime(request.form['end_time'], '%H:%M').time(),
            working_days=request.form.getlist('days[]'),
            filter_rules=request.form['filter_rules'],
            internal_email=internal_email
        )
        db.session.add(robot)
        db.session.commit()
        flash('Robô criado com sucesso!', 'success')
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
        if not email:
            flash('O email é obrigatório.', 'error')
            return redirect(url_for('main.internal_emails'))

        # Associar email ao usuário logado
        internal_email = InternalEmail(email=email, description=description, user_id=current_user.id)
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
            required_cols = ['num', 'titulo', 'emails', 'nome_do_congresso', 'ano_do_congresso']
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

def calculate_delivery_rate():
    total = SendLog.query.count()
    if total == 0:
        return 0
    sent = SendLog.query.filter_by(status='sent').count()
    return round((sent / total) * 100, 2)

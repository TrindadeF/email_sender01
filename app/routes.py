from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from flask_jwt_extended import jwt_required, get_jwt_identity
import csv, io, json
import pandas as pd
from datetime import datetime
from .models import ContactList, Contact, EmailTemplate, db, User
from .models import SendLog, Robot, RobotLog
from .filters import apply_filters
from .email_service import enqueue_emails

main = Blueprint('main', __name__)

@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@main.route('/dashboard')
@login_required
def dashboard():
    stats = {
        'total_robots': Robot.query.count(),
        'total_sent': SendLog.query.filter_by(status='sent').count(),
        'total_pending': SendLog.query.filter_by(status='pending').count(),
        'delivery_rate': calculate_delivery_rate()
    }
    robots = Robot.query.all()
    return render_template('dashboard.html', stats=stats, robots=robots, user=user)

@main.route('/templates', methods=['GET', 'POST'])
@jwt_required()
def templates():
    current_user_id = get_jwt_identity()
    
    if request.method == 'POST':
        template = EmailTemplate(
            name=request.form['name'],
            subject=request.form['subject'],
            body=request.form['body'],
            user_id=current_user_id
        )
        db.session.add(template)
        db.session.commit()
        flash('Template criado com sucesso!', 'success')
        return redirect(url_for('main.templates'))
    
    templates = EmailTemplate.query.filter_by(user_id=current_user_id).all()
    return render_template('templates.html', templates=templates)

@main.route('/templates/<int:id>/edit', methods=['GET', 'POST'])
def edit_template(id):
    template = EmailTemplate.query.get_or_404(id)
    if request.method == 'POST':
        template.name = request.form['name']
        template.subject = request.form['subject']
        template.body = request.form['body']
        db.session.commit()
        flash('Template atualizado com sucesso!', 'success')
        return redirect(url_for('main.templates'))
    return render_template('edit_template.html', template=template)

@main.route('/templates/<int:id>/delete', methods=['POST'])
def delete_template(id):
    template = EmailTemplate.query.get_or_404(id)
    db.session.delete(template)
    db.session.commit()
    flash('Template excluído com sucesso!', 'success')
    return redirect(url_for('main.templates'))

@main.route('/robots', methods=['GET', 'POST'])
@jwt_required()
def robots():
    current_user_id = get_jwt_identity()
    
    if request.method == 'POST':
        robot = Robot(
            name=request.form['name'],
            email=request.form['email'],
            template_id=request.form['template_id'],
            user_id=current_user_id,
            emails_per_hour=request.form['emails_per_hour'],
            start_time=datetime.strptime(request.form['start_time'], '%H:%M').time(),
            end_time=datetime.strptime(request.form['end_time'], '%H:%M').time(),
            working_days=request.form.getlist('days[]'),
            filter_rules=request.form['filter_rules']
        )
        db.session.add(robot)
        db.session.commit()
        flash('Robô criado com sucesso!', 'success')
        return redirect(url_for('main.dashboard'))
    
    templates = EmailTemplate.query.all()
    return render_template('robots.html', templates=templates)

@main.route('/api/robots/<int:id>/toggle', methods=['POST'])
def toggle_robot(id):
    robot = Robot.query.get_or_404(id)
    robot.active = not robot.active
    db.session.add(RobotLog(
        robot=robot,
        action='stop' if robot.active else 'start'
    ))
    db.session.commit()
    return jsonify({'status': 'success'})

@main.route('/upload', methods=['GET', 'POST'])
@jwt_required()
def upload():
    current_user_id = get_jwt_identity()
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(request.url)

        try:
            # Ler o arquivo Excel
            df = pd.read_excel(file)
            print("DataFrame lido:", df.head())  # Debug
            
            # Padronizar nomes das colunas
            df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
            print("Colunas após padronização:", df.columns.tolist())  # Debug
            
            # Validar colunas necessárias
            required_cols = ['numero', 'titulo', 'emails', 'nome_do_congresso', 'ano_do_congresso']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                flash(f'Colunas obrigatórias ausentes: {", ".join(missing_cols)}', 'error')
                return redirect(request.url)
            
            # Criar nova lista de contatos
            name = request.form.get('name', 'Lista Importada ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            contact_list = ContactList(name=name, user_id=1)  # TODO: usar current_user.id
            db.session.add(contact_list)
            db.session.flush()

            # Processar cada linha do Excel
            for _, row in df.iterrows():
                contact_data = {
                    'numero': str(row['numero']),
                    'titulo': str(row['titulo']),
                    'emails': str(row['emails']),
                    'nome_congresso': str(row['nome_do_congresso']),
                    'ano_congresso': str(row['ano_do_congresso'])
                }
                
                contact = Contact(list_id=contact_list.id, data=contact_data)
                db.session.add(contact)
            
            db.session.commit()
            flash(f'Lista importada com sucesso! {len(df)} contatos adicionados.', 'success')
            return redirect(url_for('main.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            print("Erro ao processar arquivo:", str(e))  # Debug
            flash(f'Erro ao processar arquivo: {str(e)}', 'error')
            return redirect(request.url)

    return render_template('upload.html')

@main.route('/robots/monitor')
def robots_monitor():
    return render_template('robots.html')

@main.route('/compose', methods=['GET', 'POST'])
@jwt_required()
def compose():
    current_user_id = get_jwt_identity()
    templates = EmailTemplate.query.filter_by(user_id=current_user_id).all()
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

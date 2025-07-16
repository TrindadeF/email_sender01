from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User, db
from datetime import timedelta

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'GET':
        return render_template('auth/register.html')

    try:
        if request.content_type == 'application/json':
            data = request.get_json()
            
            # Validar dados
            if not all(k in data for k in ['username', 'email', 'password']):
                return jsonify({'error': 'Dados incompletos'}), 400
            
            username = data['username']
            email = data['email']
            password = data['password']
        else:
            # Dados do formulário
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            if not all([username, email, password, confirm_password]):
                flash('Por favor, preencha todos os campos.', 'danger')
                return render_template('auth/register.html'), 400
            
            if password != confirm_password:
                flash('As senhas não coincidem.', 'danger')
                return render_template('auth/register.html'), 400
        
        # Verificar se usuário já existe
        if User.query.filter_by(email=email).first():
            message = 'Email já cadastrado.'
            return (jsonify({'error': message}), 400) if request.content_type == 'application/json' else (render_template('auth/register.html', error=message), 400)
        
        if User.query.filter_by(username=username).first():
            message = 'Este nome já está em uso.'
            return (jsonify({'error': message}), 400) if request.content_type == 'application/json' else (render_template('auth/register.html', error=message), 400)
        
        # Criar novo usuário
        user = User(
            username=username,
            email=email,
            password=password  # Usa o setter password que irá gerar o hash automaticamente
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Gerar token JWT
        access_token = create_access_token(
            identity=user.id,
            expires_delta=timedelta(days=1)
        )
        
        if request.content_type == 'application/json':
            return jsonify({
                'message': 'Usuário registrado com sucesso',
                'access_token': access_token
            }), 201
        else:
            login_user(user)
            flash('Registro realizado com sucesso! Bem-vindo ao Email Sender.', 'success')
            return redirect(url_for('main.index'))
            
    except Exception as e:
        db.session.rollback()
        error_message = f"Erro ao criar conta: {str(e)}"
        print(f"Erro detalhado no registro: {type(e).__name__} - {str(e)}")  # Log do erro
        if request.content_type == 'application/json':
            return jsonify({'error': error_message}), 500
        flash(error_message, 'danger')
        return render_template('auth/register.html'), 500

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'GET':
        return render_template('auth/login.html')

    try:
        if request.content_type == 'application/json':
            data = request.get_json()
            
            if not all(k in data for k in ['email', 'password']):
                return jsonify({'error': 'Dados incompletos'}), 400
                
            email = data['email']
            password = data['password']
        else:
            # Dados do formulário
            email = request.form.get('email')
            password = request.form.get('password')
            
            if not all([email, password]):
                flash('Por favor, preencha todos os campos.', 'danger')
                return render_template('auth/login.html'), 400
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            message = 'Email ou senha incorretos.'
            if request.content_type == 'application/json':
                return jsonify({'error': message}), 401
            flash(message, 'danger')
            return render_template('auth/login.html'), 401
        
        # Login bem sucedido
        login_user(user)
        
        # Gerar token JWT
        access_token = create_access_token(
            identity=user.id,
            expires_delta=timedelta(days=1)
        )
        
        if request.content_type == 'application/json':
            return jsonify({
                'access_token': access_token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            }), 200
        else:
            flash(f'Bem-vindo de volta, {user.username}!', 'success')
            return redirect(url_for('main.index'))
            
    except Exception as e:
        return (jsonify({'error': str(e)}), 500) if request.content_type == 'application/json' else (render_template('auth/login.html', error=str(e)), 500)

@auth.route('/me', methods=['GET'])
@jwt_required()
def me():
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'Usuário não encontrado'}), 404
            
        return jsonify({
            'id': user.id,
            'username': user.username,
            'email': user.email
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth.route('/logout')
@login_required
def logout():
    try:
        logout_user()
        return redirect(url_for('auth.login'))
    except Exception as e:
        flash('Erro ao fazer logout.')
        return redirect(url_for('main.index'))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_jwt_extended import JWTManager
from celery import Celery


db = SQLAlchemy()
login_manager = LoginManager()
jwt = JWTManager()
celery = Celery(__name__)


def create_app(config_class='config.DevelopmentConfig'):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    jwt.init_app(app)

    # Configurações do JWT
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_SECRET_KEY"] = app.config['SECRET_KEY']  # Usa a mesma chave secreta da aplicação
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 3600  # 1 hora

    celery.conf.update(
        broker_url=app.config['CELERY_BROKER_URL'],
        result_backend=app.config['CELERY_RESULT_BACKEND']
    )

    from app.routes import main as main_blueprint
    from app.auth import auth as auth_blueprint
    
    app.register_blueprint(main_blueprint)
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    return app

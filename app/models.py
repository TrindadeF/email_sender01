from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    contacts_lists = db.relationship('ContactList', backref='owner', lazy=True)
    templates = db.relationship('EmailTemplate', backref='owner', lazy=True)
    schedules = db.relationship('Schedule', backref='owner', lazy=True)
    limits = db.relationship('Limits', uselist=False, backref='user')

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_auth_token(self, expires_in=3600):
        return create_access_token(identity=self.id, expires_delta=timedelta(seconds=expires_in))

    @staticmethod
    def verify_auth_token(token):
        try:
            data = verify_jwt_token(token)
            return User.query.get(data['identity'])
        except:
            return None

class ContactList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contacts = db.relationship('Contact', backref='list', lazy=True)

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('contact_list.id'), nullable=False)
    data = db.Column(db.JSON, nullable=False)

class EmailTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class SendLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('email_template.id'), nullable=False)
    status = db.Column(db.String(32), default='pending')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    cron = db.Column(db.String(64), nullable=False)  # e.g., cron expression
    active = db.Column(db.Boolean, default=True)

class Limits(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    daily = db.Column(db.Integer, default=1000)
    monthly = db.Column(db.Integer, default=30000)
    blocked_dates = db.Column(db.JSON, default=list)  # list of dates

class Robot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('email_template.id'), nullable=False)
    active = db.Column(db.Boolean, default=True)
    emails_per_hour = db.Column(db.Integer, default=100)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    working_days = db.Column(db.JSON, default=list)  # [0,1,2,3,4] for Mon-Fri
    filter_rules = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    template = db.relationship('EmailTemplate', backref='robots')
    logs = db.relationship('RobotLog', backref='robot', lazy=True)

class RobotLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    robot_id = db.Column(db.Integer, db.ForeignKey('robot.id'), nullable=False)
    action = db.Column(db.String(32), nullable=False)  # start, stop, send, error
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

from flask import Flask, render_template, request
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

from config import Config

# Initialize Flask extensions
db = SQLAlchemy()
mail = Mail()
csrf = CSRFProtect()

# Initialize LoginManager
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# User loader for Flask-Login
@login_manager.user_loader
def load_user(id):
    from app.models import User
    return User.query.get(int(id))

def create_app(config_class=Config):
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    app.config.from_object(config_class)
      # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    migrate = Migrate(app, db)

    # Configure CSRF for AJAX
    @app.before_request
    def csrf_protect():
        if request.method != 'GET':
            token = request.headers.get('X-CSRF-Token')
            if token:
                return token
    
    # Register blueprints
    from app.auth import auth_bp
    from app.routes import main_bp, teacher_bp, student_bp, admin_dashboard
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
        
    @app.errorhandler(429)
    def too_many_requests(error):
        return render_template('errors/429.html', 
                              minutes=5,
                              seconds=0), 429
    
    # Context processors
    @app.context_processor
    def inject_user():
        return dict(current_user=current_user)
    
    # Register template filters
    from app.filters import timesince, format_datetime
    app.jinja_env.filters['timesince'] = timesince
    app.jinja_env.filters['format_datetime'] = format_datetime
    
    return app

# Import for render_template and current_user
from flask import render_template
from flask_login import current_user
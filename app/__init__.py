from flask import Flask
import os

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    from app.models.database import init_db, migrate_database
    init_db()  # This creates the tables
    migrate_database()

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.quiz import quiz_bp
    from app.routes.progress import progress_bp
    from app.routes.settings import settings_bp
    from app.routes.admin import admin_bp 
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(progress_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(admin_bp) 
    
    return app
import os
from flask import Flask, send_from_directory
from app.config import Config
from app.db import close_db, init_db

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    # Ensure upload directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'users'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'products'), exist_ok=True)

    # Teardown database connection on request completion
    app.teardown_appcontext(close_db)

    # Register template filters for day/month/year date formatting
    from app.utils import format_dmy, format_date_dmy
    app.jinja_env.filters['dmy'] = format_dmy
    app.jinja_env.filters['date_dmy'] = format_date_dmy

    # Register Blueprints
    from app.views.kiosk import kiosk_bp
    from app.views.admin import admin_bp
    from app.views.stats import stats_bp

    app.register_blueprint(kiosk_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(stats_bp)

    # Route for serving uploaded images
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    # Initialize database tables and default categories/settings if missing
    with app.app_context():
        init_db(app)
        from app.models.category import Category
        from app.models.setting import Setting
        Category.ensure_defaults()
        Setting.ensure_defaults()

    return app
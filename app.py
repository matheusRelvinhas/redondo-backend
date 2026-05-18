import logging
from flask import Flask, request
from flask_cors import CORS
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models import db
from routes.register_blueprints import register_blueprints
from config import get_config
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_talisman import Talisman
from loguru import logger
from cache_scheduler import init_cache_cleanup_scheduler

logging.getLogger('werkzeug').setLevel(logging.ERROR)

def create_app():
    app = Flask(__name__)
    config = get_config()
    app.config.from_object(config)
    
    app.wsgi_app = ProxyFix(
        app.wsgi_app, 
        x_for=1,
        x_proto=1,
        x_host=1
    )

    
    Talisman(app, content_security_policy=None, force_https=False)
    
    cache = Cache(app)
    app.cache = cache
    
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[],
        storage_uri="memory://",
        strategy="moving-window"
    )
    app.limiter = limiter
    
    CORS(
        app,
        origins=app.config['CORS_ORIGINS'],
        supports_credentials=app.config['CORS_SUPPORTS_CREDENTIALS']
    )
    
    db.init_app(app)
    
    with app.app_context():
        try:
            db.create_all()
            logger.info("Create tables: Success")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
    
    # ========== OAUTH (Google) ==========
    oauth = OAuth(app)
    oauth.register(
        name='google',
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )
    app.oauth = oauth
    
    @app.before_request
    def log_suspicious_requests():
        if not request.headers.get("User-Agent"):
            ip = request.remote_addr
            app.logger.warning(f"Suspicious request from: {ip}")
    
    init_cache_cleanup_scheduler(app, interval_hours=6)
    
    register_blueprints(app)

    return app

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
from utils import get_rate_limit_key

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

    
    Talisman(app, content_security_policy=None, force_https=app.config.get('ENVIRONMENT', 'development').lower() == 'production')
    
    try:
        cache = Cache(app)
    except RuntimeError as exc:
        if 'redis' in str(exc).lower():
            logger.warning(f"Redis cache backend unavailable: {exc}. Falling back to filesystem cache")
            app.config['CACHE_TYPE'] = 'FileSystemCache'
            app.config['CACHE_DIR'] = 'cache'
            cache = Cache(app)
        else:
            raise
    app.cache = cache

    if app.config.get('ENVIRONMENT', 'development').lower() == 'production':
        logger.info("Using Redis cache backend in production")
    else:
        logger.info("Using filesystem cache backend in development")
    
    limiter = Limiter(
        app=app,
        key_func=get_rate_limit_key,
        default_limits=[],
        storage_uri="memory://",
        strategy="moving-window"
    )
    app.limiter = limiter
    
    cors_origins = app.config.get('CORS_ORIGINS', [])
    if isinstance(cors_origins, str):
        cors_origins = [origin.strip() for origin in cors_origins.split(',') if origin.strip()]

    CORS(
        app,
        origins=cors_origins,
        supports_credentials=app.config.get('CORS_SUPPORTS_CREDENTIALS', False)
    )
    
    db.init_app(app)
    
    with app.app_context():
        try:
            db.create_all()
            logger.info("Create tables: Success")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
    
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

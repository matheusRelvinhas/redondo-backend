import os
from flask import Flask, request
from flask_cors import CORS
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models import db
from routes.register_blueprints import register_blueprints
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_talisman import Talisman

load_dotenv()
app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY') 
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')
app.secret_key = os.getenv('GOOGLE_CLIENT_SECRET')
app.config["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

app.config['CACHE_TYPE'] = 'FileSystemCache'
app.config['CACHE_DIR'] = 'cache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 60 * 20
cache = Cache(app)
app.cache = cache

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
    strategy="moving-window"
)
app.limiter = limiter

Talisman(app, content_security_policy=None)

app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)
app.oauth = oauth

CORS(app, origins="*", supports_credentials=True)

db.init_app(app)

with app.app_context():
    try:
        db.create_all()
        print("Create tables OK.")
    except Exception as e:
        print(f"Error create tables: {e}")

register_blueprints(app)

@app.before_request
def log_suspicious_requests():
    if not request.headers.get("User-Agent"):
        ip = request.remote_addr
        app.logger.warning(f"Request suspeito de {ip}")

if __name__ == '__main__':
    app.run(
        debug=os.getenv('FLASK_DEBUG') == 'True',
        host="localhost",
        #host="0.0.0.0",
        port=int(os.getenv('FLASK_RUN_PORT')),
        threaded=True,
        use_reloader=False
    )

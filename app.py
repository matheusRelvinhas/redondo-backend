import os
from flask import Flask
from flask_cors import CORS
from flask_caching import Cache
from models import db
from routes.register_blueprints import register_blueprints
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth

load_dotenv()
app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY') 
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')
app.secret_key = os.getenv('GOOGLE_CLIENT_SECRET')

app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300        
cache = Cache(app)

oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)
app.oauth = oauth

db.init_app(app)
CORS(app, origins=[os.getenv('FRONTEND_URL')], supports_credentials=True)
register_blueprints(app)

with app.app_context():
    try:
        db.create_all()
        print("Create tables OK.")
    except Exception as e:
        print(f"Error create tables: {e}")

app.cache = cache

if __name__ == '__main__':
    app.run(
        debug=os.getenv('FLASK_DEBUG') == 'True',
        port=int(os.getenv('FLASK_RUN_PORT')),
        threaded=True,
        use_reloader=False
    )

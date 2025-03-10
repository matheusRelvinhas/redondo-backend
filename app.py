import os
from flask import Flask
from flask_cors import CORS
from models import db, User
from routes.register_blueprints import register_blueprints
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY') 

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

CORS(app, origins=[os.getenv('FRONTEND_URL')])

register_blueprints(app)

with app.app_context():
    try:
        db.create_all()
        print("Create tables OK.")
    except Exception as e:
        print(f"Error create tables: {e}")

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG') == 'True', port=int(os.getenv('FLASK_RUN_PORT', 3000)))

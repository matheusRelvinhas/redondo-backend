import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import inspect, text

from app import create_app
from models import db

TABLE = 'ai_analytics'
COLUMN = 'data'

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        columns = {c['name'] for c in inspect(db.engine).get_columns(TABLE)}
        if COLUMN in columns:
            print(f'{TABLE}.{COLUMN} ja existe, nada a fazer')
            sys.exit(0)

        db.session.execute(text(f'ALTER TABLE `{TABLE}` ADD COLUMN `{COLUMN}` JSON NULL'))
        db.session.commit()
        print(f'{TABLE}.{COLUMN} criada')

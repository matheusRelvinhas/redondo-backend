import os
from dotenv import load_dotenv
from app import create_app

os.environ.setdefault('ENVIRONMENT', 'production')

load_dotenv()

app = create_app()

if __name__ == '__main__':
    app.run()

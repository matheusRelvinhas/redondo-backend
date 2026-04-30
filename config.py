import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 20,
    }
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    CACHE_TYPE = 'FileSystemCache'
    CACHE_DIR = 'cache'
    CACHE_DEFAULT_TIMEOUT = 60 * 20
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    SECRET_KEY = os.getenv('GOOGLE_CLIENT_SECRET')
    LOG_LEVEL = 'INFO'
    CORS_ORIGINS = "*"
    CORS_SUPPORTS_CREDENTIALS = True


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    FLASK_ENV = 'development'
    LOG_LEVEL = 'DEBUG'
    THREADED = True
    CACHE_DEFAULT_TIMEOUT = 60 * 5


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    FLASK_ENV = 'production'
    LOG_LEVEL = 'WARNING'
    USE_RELOADER = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 40,
    }
    CACHE_DEFAULT_TIMEOUT = 60 * 30


def get_config():
    environment = os.getenv('ENVIRONMENT', 'development').lower()
    if environment == 'production':
        return ProductionConfig
    return DevelopmentConfig

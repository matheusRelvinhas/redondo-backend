import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
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
    CACHE_REDIS_URL = REDIS_URL
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    SECRET_KEY = os.getenv('SECRET_KEY') or os.getenv('JWT_SECRET_KEY') or os.urandom(24).hex()
    LOG_LEVEL = 'INFO'
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000')
    CORS_SUPPORTS_CREDENTIALS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = ENVIRONMENT == 'production'
    SESSION_COOKIE_SAMESITE = 'Lax'


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    FLASK_ENV = 'development'
    LOG_LEVEL = 'DEBUG'
    THREADED = True
    CACHE_TYPE = 'FileSystemCache'
    CACHE_DEFAULT_TIMEOUT = 60 * 5


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    FLASK_ENV = 'production'
    LOG_LEVEL = 'WARNING'
    USE_RELOADER = False
    CACHE_TYPE = 'RedisCache'
    CACHE_REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
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

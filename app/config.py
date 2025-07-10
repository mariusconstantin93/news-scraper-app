"""
Configuration file for the News Scraper application
"""

import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

# Configure logging to show only important messages
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING) 
logging.getLogger('werkzeug').setLevel(logging.WARNING)  # Flask development server logs
logging.getLogger('urllib3').setLevel(logging.WARNING)  # HTTP request logs

class Config:
    """Base configuration class"""
    
    # PostgreSQL Database Configuration
    DATABASE_URL = os.environ.get('DATABASE_URL') or 'postgresql://postgres:postgres@localhost:5432/news_scraper_db'
    
    # Parse DATABASE_URL for SQLAlchemy
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'echo': False,  # Disable SQL logging for cleaner output
        'echo_pool': False  # Disable connection pool logging
    }
    
    # Application settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-this-in-production'
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Scraper settings
    SCRAPER_TESTING_MODE = os.environ.get('SCRAPER_TESTING_MODE', 'true').lower() == 'true'
    SCRAPER_INTERVAL_MINUTES = int(os.environ.get('SCRAPER_INTERVAL_MINUTES', '2' if SCRAPER_TESTING_MODE else '120'))
    
    # News sources configuration
    NEWS_SOURCES = {
        'biziday': {
            'name': 'Biziday',
            'url': 'https://www.biziday.ro',
            'enabled': True,
            'frequency_minutes': SCRAPER_INTERVAL_MINUTES
        },
        'adevarul': {
            'name': 'Adevarul',
            'url': 'https://adevarul.ro',
            'enabled': True,
            'frequency_minutes': SCRAPER_INTERVAL_MINUTES
        },
        'facebook': {
            'name': 'Facebook',
            'url': 'https://facebook.com',
            'enabled': True,
            'frequency_minutes': SCRAPER_INTERVAL_MINUTES * 2  # Less frequent for Facebook
        }
    }

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    # Keep SQLAlchemy logging disabled for cleaner console output
    SQLALCHEMY_ENGINE_OPTIONS = {
        **Config.SQLALCHEMY_ENGINE_OPTIONS,
        'echo': False  # Disable SQL logging even in development for cleaner output
    }

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SCRAPER_TESTING_MODE = False
    SCRAPER_INTERVAL_MINUTES = 120  # 2 hours in production

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:postgres@localhost:5432/news_scraper_test_db'

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])
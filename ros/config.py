"""
Flask configuration settings
"""
import os
from datetime import datetime

class Config:
    """Base configuration"""
    
    # Flask settings
    HOST = '0.0.0.0'
    PORT = 5000
    DEBUG = True
    SECRET_KEY = 'your-secret-key-change-in-production'
    
    # MongoDB settings
    MONGO_URI = 'mongodb://localhost:27017/'
    MONGO_DB = 'gait_analysis'
    MONGO_COLLECTION = 'gait_data'
    
    # CSV settings
    CSV_OUTPUT_DIR = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'readings'
    )
    CSV_FILENAME = f"gait_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    # Admin token (change in production)
    ADMIN_TOKEN = 'admin123'


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    MONGO_DB = 'gait_analysis_test'

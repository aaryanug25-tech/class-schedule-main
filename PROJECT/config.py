import os

class Config:
    # Base directory of the project
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Flask secret key
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_secret_key')
    
    # Database settings
    DB_NAME = 'scheduler.db'
    DB_PATH = os.path.join(BASE_DIR, DB_NAME)
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
    
    # Template and static folders (relative to webapp directory)
    TEMPLATE_FOLDER = 'templates'
    STATIC_FOLDER = 'static'
    
    # Debug mode
    DEBUG = False  # Set to False in production
    
    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    # Add production-specific settings here

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

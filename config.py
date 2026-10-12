import os

class Config:
    SECRET_KEY = 'renttrack-secret-key-ako-to'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:@localhost/renttrack_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
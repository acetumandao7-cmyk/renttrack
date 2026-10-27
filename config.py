import os

class Config:
    SECRET_KEY = 'renttrack-secret-key-ako-to'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///renttrack.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
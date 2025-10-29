from flask_sqlalchemy import SQLAlchemy

# Shared SQLAlchemy instance for the whole app
# Import as: from extensions import db

db = SQLAlchemy()

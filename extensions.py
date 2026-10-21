"""Centraliza as extensoes compartilhadas do Flask e do SQLAlchemy."""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "login"

# app/models/party.py
from .db import db
from datetime import datetime

class Party(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    users = db.relationship("User", backref="party", lazy=True)
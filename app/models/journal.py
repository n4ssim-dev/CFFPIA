from datetime import datetime

from app import db


class Ingestion(db.Model):
    """Journal de collecte : trace chaque exécution d'ingestion avec son résultat."""

    __tablename__ = "ingestions"

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(100), nullable=False, index=True)
    statut = db.Column(db.String(20), nullable=False)  # en_cours | success | erreur
    nb_inseres = db.Column(db.Integer, default=0)
    nb_ignores = db.Column(db.Integer, default=0)   # doublons ignorés (ON CONFLICT DO NOTHING)
    nb_total = db.Column(db.Integer, default=0)
    message = db.Column(db.Text)                    # message d'erreur si statut=erreur
    debut = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    fin = db.Column(db.DateTime)

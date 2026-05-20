from flask import Blueprint, jsonify, request

from app import db
from app.models.journal import Ingestion
from app.scrapers.ingestion import (
    ingest_balances_comptables,
    ingest_budgets_communes,
    ingest_depenses_culturelles,
    ingest_donnees_demographiques,
    ingest_indicateurs_revenus,
    ingest_marches_publics,
    ingest_subventions_associations,
)

bp_ingest = Blueprint("ingestion", __name__, url_prefix="/api/ingest")


# ---------------------------------------------------------------------------
# POST /api/ingest/depenses-culturelles
# ---------------------------------------------------------------------------

@bp_ingest.post("/depenses-culturelles")
def ingest_culture():
    """
    Ingère les dépenses culturelles depuis le CSV du Ministère de la Culture.
    Seules les lignes absentes de la DB sont insérées (UNIQUE code_insee + annee).
    """
    try:
        return jsonify(ingest_depenses_culturelles())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# POST /api/ingest/budgets?annee=2022&max_records=10000
# ---------------------------------------------------------------------------

@bp_ingest.post("/budgets")
def ingest_budgets():
    """
    Ingère les comptes individuels des communes (DGFiP via data.gouv.fr).
    Paramètres : annee (int, optionnel), max_records (défaut 10 000 ; 0 = tout).
    """
    annee = request.args.get("annee", type=int)
    max_records = request.args.get("max_records", 10_000, type=int)
    resolved = None if max_records == 0 else max_records
    try:
        return jsonify(ingest_budgets_communes(annee=annee, max_records=resolved))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# POST /api/ingest/subventions?annee=2023&max_records=10000
# ---------------------------------------------------------------------------

@bp_ingest.post("/subventions")
def ingest_subventions():
    """
    Ingère les subventions versées aux associations par les collectivités (data.gouv.fr).
    Paramètres : annee (int, optionnel), max_records (défaut 10 000 ; 0 = tout).
    """
    annee = request.args.get("annee", type=int)
    max_records = request.args.get("max_records", 10_000, type=int)
    resolved = None if max_records == 0 else max_records
    try:
        return jsonify(ingest_subventions_associations(annee=annee, max_records=resolved))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# POST /api/ingest/marches?annee=2023&max_records=5000
# ---------------------------------------------------------------------------

@bp_ingest.post("/marches")
def ingest_marches():
    """
    Ingère les marchés publics (DECP — données essentielles de la commande publique).
    Paramètres : annee (int, optionnel), max_records (défaut 5 000 ; 0 = tout).
    """
    annee = request.args.get("annee", type=int)
    max_records = request.args.get("max_records", 5_000, type=int)
    resolved = None if max_records == 0 else max_records
    try:
        return jsonify(ingest_marches_publics(annee=annee, max_records=resolved))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# POST /api/ingest/balances?annee=2023&max_records=50000
# ---------------------------------------------------------------------------

@bp_ingest.post("/balances")
def ingest_balances():
    """
    Ingère les balances comptables des communes (poste par poste) depuis data.economie.gouv.fr.
    Paramètres : annee (défaut 2023), max_records (défaut 50 000 ; 0 = tout ~6M lignes).
    """
    annee = request.args.get("annee", 2023, type=int)
    max_records = request.args.get("max_records", 50_000, type=int)
    resolved = None if max_records == 0 else max_records
    try:
        return jsonify(ingest_balances_comptables(annee=annee, max_records=resolved))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# POST /api/ingest/demographie?annee=2020
# ---------------------------------------------------------------------------

@bp_ingest.post("/demographie")
def ingest_demographie():
    """
    Ingère la structure démographique des communes (RP INSEE).
    Paramètre : annee (2018 / 2019 / 2020, défaut 2020).
    """
    annee = request.args.get("annee", 2020, type=int)
    try:
        return jsonify(ingest_donnees_demographiques(annee=annee))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# POST /api/ingest/revenus?annee=2020
# ---------------------------------------------------------------------------

@bp_ingest.post("/revenus")
def ingest_revenus():
    """
    Ingère les indicateurs de revenus et pauvreté (Filosofi INSEE).
    Paramètre : annee (2018 / 2019 / 2020, défaut 2020).
    """
    annee = request.args.get("annee", 2020, type=int)
    try:
        return jsonify(ingest_indicateurs_revenus(annee=annee))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /api/ingest/history?limit=20
# ---------------------------------------------------------------------------

@bp_ingest.get("/history")
def ingestion_history():
    """Historique des ingestions avec leur statut et décompte insérés/ignorés."""
    limit = request.args.get("limit", 20, type=int)
    entries = (
        db.session.query(Ingestion)
        .order_by(Ingestion.debut.desc())
        .limit(limit)
        .all()
    )
    return jsonify(
        [
            {
                "id": e.id,
                "source": e.source,
                "statut": e.statut,
                "nb_inseres": e.nb_inseres,
                "nb_ignores": e.nb_ignores,
                "nb_total": e.nb_total,
                "debut": e.debut.isoformat() if e.debut else None,
                "fin": e.fin.isoformat() if e.fin else None,
                "duree_s": round((e.fin - e.debut).total_seconds(), 2) if e.fin and e.debut else None,
                "message": e.message,
            }
            for e in entries
        ]
    )

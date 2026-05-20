from flask import Blueprint, jsonify, request

from app.scrapers.data_gouv import (
    fetch_balances_comptables,
    fetch_budgets_communes,
    fetch_depenses_culturelles,
    fetch_donnees_demographiques,
    fetch_indicateurs_revenus,
    fetch_marches_publics,
    fetch_subventions_associations,
    search_datasets,
)

bp_data = Blueprint("data_gouv", __name__, url_prefix="/api")


def _int_param(name: str, default: int, min_val: int = 0, max_val: int = 500) -> int:
    try:
        return max(min_val, min(int(request.args.get(name, default)), max_val))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# GET /api/datasets?q=<query>&page=1&page_size=10
# ---------------------------------------------------------------------------

@bp_data.get("/datasets")
def datasets():
    """Recherche de datasets sur data.gouv.fr relatifs aux finances locales."""
    q = request.args.get("q", "finances collectivites locales")
    page = _int_param("page", 1, min_val=1, max_val=999)
    page_size = _int_param("page_size", 10, min_val=1, max_val=50)
    try:
        return jsonify(search_datasets(q, page=page, page_size=page_size))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# ---------------------------------------------------------------------------
# GET /api/depenses-culturelles?commune=Lyon&departement=69&limit=50&offset=0
# ---------------------------------------------------------------------------

@bp_data.get("/depenses-culturelles")
def depenses_culturelles():
    """
    Dépenses culturelles des communes françaises.
    Source : Ministère de la Culture via data.gouv.fr.
    Paramètres : commune (str), departement (str, ex: 69), limit, offset.
    """
    commune = request.args.get("commune")
    departement = request.args.get("departement")
    limit = _int_param("limit", 50, min_val=1, max_val=500)
    offset = _int_param("offset", 0, min_val=0, max_val=99999)
    try:
        return jsonify(fetch_depenses_culturelles(commune, departement, limit, offset))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# ---------------------------------------------------------------------------
# GET /api/budgets?commune=Lyon&departement=69&annee=2022&limit=50&offset=0
# ---------------------------------------------------------------------------

@bp_data.get("/budgets")
def budgets_communes():
    """
    Budgets annuels des communes : recettes, dépenses, épargne brute, encours de la dette.
    Source : DGFiP — Comptes individuels des communes (data.gouv.fr).
    Paramètres : commune (str), departement (str), annee (int), limit, offset.
    """
    commune = request.args.get("commune")
    departement = request.args.get("departement")
    annee = request.args.get("annee", type=int)
    limit = _int_param("limit", 50, min_val=1, max_val=500)
    offset = _int_param("offset", 0, min_val=0, max_val=99999)
    try:
        return jsonify(fetch_budgets_communes(commune, departement, annee, limit, offset))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# ---------------------------------------------------------------------------
# GET /api/subventions?commune=Bordeaux&beneficiaire=sport&annee=2023&limit=50
# ---------------------------------------------------------------------------

@bp_data.get("/subventions")
def subventions_associations():
    """
    Subventions versées par les collectivités locales aux associations.
    Source : data.gouv.fr — subventions collectivités territoriales.
    Paramètres : commune (str), beneficiaire (str), annee (int), limit, offset.
    """
    commune = request.args.get("commune")
    beneficiaire = request.args.get("beneficiaire")
    annee = request.args.get("annee", type=int)
    limit = _int_param("limit", 50, min_val=1, max_val=500)
    offset = _int_param("offset", 0, min_val=0, max_val=99999)
    try:
        return jsonify(fetch_subventions_associations(commune, beneficiaire, annee, limit, offset))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# ---------------------------------------------------------------------------
# GET /api/marches?acheteur=Marseille&annee=2023&nature=Marché&limit=50
# ---------------------------------------------------------------------------

@bp_data.get("/marches")
def marches_publics():
    """
    Marchés publics attribués par les collectivités locales.
    Source : DECP — Données essentielles de la commande publique (data.gouv.fr).
    Paramètres : acheteur (str), annee (int), nature (str), limit, offset.
    """
    acheteur = request.args.get("acheteur")
    annee = request.args.get("annee", type=int)
    nature = request.args.get("nature")
    limit = _int_param("limit", 50, min_val=1, max_val=500)
    offset = _int_param("offset", 0, min_val=0, max_val=99999)
    try:
        return jsonify(fetch_marches_publics(acheteur, annee, nature, limit, offset))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# ---------------------------------------------------------------------------
# GET /api/balances?siren=213300063&compte_prefix=64&annee=2023&limit=50
# ---------------------------------------------------------------------------

@bp_data.get("/balances")
def balances_comptables():
    """
    Balances comptables des communes par poste de compte.
    Source : DGFiP — data.economie.gouv.fr.
    Paramètres :
      siren         : SIREN de la commune (9 chiffres)
      commune       : nom de la commune (recherche partielle)
      compte_prefix : préfixe du compte (ex: '64'=personnel, '66'=financier, '73'=impôts)
      annee         : année d'exercice (défaut 2023)
      limit, offset
    """
    siren = request.args.get("siren")
    commune = request.args.get("commune")
    compte_prefix = request.args.get("compte_prefix")
    annee = request.args.get("annee", 2023, type=int)
    limit = _int_param("limit", 50, min_val=1, max_val=100)
    offset = _int_param("offset", 0, min_val=0, max_val=99999)
    try:
        return jsonify(fetch_balances_comptables(siren, commune, compte_prefix, annee, limit, offset))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# ---------------------------------------------------------------------------
# GET /api/demographie?code_insee=69123&annee=2020&limit=50
# ---------------------------------------------------------------------------

@bp_data.get("/demographie")
def demographie():
    """
    Structure démographique des communes par tranche d'âge.
    Source : INSEE — Recensement de la Population.
    Paramètres : code_insee (str), annee (2018/2019/2020), limit, offset.
    """
    code_insee = request.args.get("code_insee")
    annee = request.args.get("annee", 2020, type=int)
    limit = _int_param("limit", 50, min_val=1, max_val=500)
    offset = _int_param("offset", 0, min_val=0, max_val=99999)
    try:
        return jsonify(fetch_donnees_demographiques(code_insee, annee, limit, offset))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# ---------------------------------------------------------------------------
# GET /api/revenus?code_insee=69123&annee=2020&limit=50
# ---------------------------------------------------------------------------

@bp_data.get("/revenus")
def revenus():
    """
    Revenus et pauvreté par commune (Filosofi).
    Source : INSEE — Filosofi, fichier Communes.
    Paramètres : code_insee (str), annee (2018/2019/2020), limit, offset.
    """
    code_insee = request.args.get("code_insee")
    annee = request.args.get("annee", 2020, type=int)
    limit = _int_param("limit", 50, min_val=1, max_val=500)
    offset = _int_param("offset", 0, min_val=0, max_val=99999)
    try:
        return jsonify(fetch_indicateurs_revenus(code_insee, annee, limit, offset))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

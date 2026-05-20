"""
Logique d'ingestion : fetch → parse → upsert PostgreSQL.

Stratégie anti-redondance :
- Référentiels (departements, communes) : ON CONFLICT DO UPDATE (mise à jour du libellé)
- Données financières                   : ON CONFLICT DO NOTHING  (snapshot immuable par annee)
"""

from datetime import datetime, date

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import db
from app.models.finance import (
    BalanceComptableCommune,
    BudgetCommune,
    DepenseCulturelle,
    DonneesDemographiquesCommune,
    IndicateurRevenuCommune,
    MarchePublic,
    SubventionAssociation,
)
from app.models.journal import Ingestion
from app.models.referentiel import Commune, Departement
from app.scrapers.data_gouv import (
    DS_BALANCES_PREFIX,
    DS_BUDGETS_SLUG,
    DS_MARCHES_SLUG,
    ECONOMIE_API,
    INSEE_FILOSOFI_URLS,
    INSEE_RP_URLS,
    _SESSION,
    _download_insee_zip,
    _get,
    _get_csv,
    _get_dataset_resources,
    _load_culture_csv,
    _read_csv_from_zip,
    list_subventions_datasets,
)

GEO_API_COMMUNES_URL = "https://geo.api.gouv.fr/communes"

CHUNK_SIZE = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_int(val) -> int | None:
    try:
        return int(str(val).strip()) if val not in (None, "", "N/A") else None
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    if not val or val in ("N/A", ""):
        return None
    try:
        return float(str(val).replace(",", ".").replace(" ", ""))
    except (ValueError, TypeError):
        return None


def _safe_pct(val) -> float | None:
    if not val:
        return None
    try:
        return float(str(val).replace(",", ".").replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def _safe_date(val) -> date | None:
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y"):
        try:
            return datetime.strptime(str(val)[:10], fmt).date()
        except ValueError:
            continue
    return None


def _dep_from_insee(code_insee: str) -> str:
    return code_insee[:3] if code_insee.startswith("97") else code_insee[:2]


def _upsert_dep(code: str, libelle: str) -> None:
    db.session.execute(
        pg_insert(Departement)
        .values(code=code, libelle=libelle)
        .on_conflict_do_update(index_elements=["code"], set_={"libelle": libelle})
    )


def _upsert_commune(code_insee: str, nom: str, siren: str | None, code_dep: str) -> None:
    """
    UPSERT commune. Préserve les vrais noms : si on passe un placeholder
    (nom == code_insee, fallback faute de mieux), on n'écrase pas le nom
    potentiellement vrai déjà en base. Si on passe un vrai nom, il prime.
    Le SIREN n'est mis à jour que s'il est fourni (jamais écrasé par None).
    """
    nom_is_real = bool(nom) and nom != code_insee
    stmt = pg_insert(Commune).values(
        code_insee=code_insee, nom=nom or code_insee, siren=siren, code_departement=code_dep
    )
    if nom_is_real:
        set_clause: dict = {"nom": stmt.excluded.nom}
        if siren:
            set_clause["siren"] = stmt.excluded.siren
        stmt = stmt.on_conflict_do_update(index_elements=["code_insee"], set_=set_clause)
    elif siren:
        stmt = stmt.on_conflict_do_update(
            index_elements=["code_insee"], set_={"siren": stmt.excluded.siren}
        )
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=["code_insee"])
    db.session.execute(stmt)


# ---------------------------------------------------------------------------
# Dépenses culturelles (CSV Ministère de la Culture)
# ---------------------------------------------------------------------------

def ingest_depenses_culturelles() -> dict:
    journal = Ingestion(source="depenses-culturelles-des-communes", statut="en_cours")
    db.session.add(journal)
    db.session.commit()

    try:
        rows = _load_culture_csv()
        nb_inseres = 0
        communes_seen: set[str] = set()
        batch: list[dict] = []

        for row in rows:
            code_insee = (row.get("code_insee") or "").strip()
            if len(code_insee) != 5:
                continue

            annee = _safe_int(row.get("annee")) or 2023
            code_dep = _dep_from_insee(code_insee)

            if code_insee not in communes_seen:
                _upsert_dep(code_dep, code_dep)
                _upsert_commune(
                    code_insee,
                    (row.get("nom_commune") or "").strip(),
                    (row.get("siren") or "").strip() or None,
                    code_dep,
                )
                communes_seen.add(code_insee)

            batch.append(
                {
                    "code_insee": code_insee,
                    "annee": annee,
                    "depenses_totales_k_eur": _safe_int(row.get("depenses_culturelles_totales_k_eur")),
                    "depenses_fonctionnement_k_eur": _safe_int(row.get("depenses_culturelles_fonctionnement_k_eur")),
                    "depenses_investissement_k_eur": _safe_int(row.get("depenses_culturelles_investissement_k_eur")),
                    "depenses_totales_eur_par_hab": _safe_int(row.get("depenses_culturelles_totales_eur_par_habitant")),
                    "depenses_fonctionnement_eur_par_hab": _safe_int(row.get("depenses_culturelles_fonctionnement_eur_par_habitant")),
                    "depenses_investissement_eur_par_hab": _safe_int(row.get("depenses_culturelles_investissement_eur_par_habitant")),
                    "part_totale_pct": _safe_pct(row.get("part_depenses_culturelles_totales_pct")),
                    "part_fonctionnement_pct": _safe_pct(row.get("part_depenses_culturelles_fonctionnement_pct")),
                    "part_investissement_pct": _safe_pct(row.get("part_depenses_culturelles_investissement_pct")),
                    "population": _safe_int(row.get("population_annee")),
                }
            )

            if len(batch) >= CHUNK_SIZE:
                result = db.session.execute(
                    pg_insert(DepenseCulturelle)
                    .values(batch)
                    .on_conflict_do_nothing(index_elements=["code_insee", "annee"])
                )
                nb_inseres += result.rowcount
                batch.clear()
                db.session.flush()

        if batch:
            result = db.session.execute(
                pg_insert(DepenseCulturelle)
                .values(batch)
                .on_conflict_do_nothing(index_elements=["code_insee", "annee"])
            )
            nb_inseres += result.rowcount

        nb_total = len(rows)
        db.session.commit()
        _close_journal(journal, nb_inseres, nb_total - nb_inseres, nb_total)
        return _result(journal)

    except Exception as exc:
        db.session.rollback()
        _fail_journal(journal, exc)
        raise


# ---------------------------------------------------------------------------
# Budgets communaux (DGFiP via data.gouv.fr)
# ---------------------------------------------------------------------------

def ingest_budgets_communes(annee: int | None = None, max_records: int = 10_000) -> dict:
    """
    Ingère les comptes individuels des communes (recettes, dépenses, dette, épargne).
    Sélectionne automatiquement le CSV le plus récent du dataset DGFiP.
    """
    source_label = f"dgfip-comptes-communes-{annee or 'latest'}"
    journal = Ingestion(source=source_label, statut="en_cours")
    db.session.add(journal)
    db.session.commit()

    try:
        resources = _get_dataset_resources(DS_BUDGETS_SLUG)
        csv_resources = [r for r in resources if r.get("format", "").upper() == "CSV"]
        if annee:
            filtered = [r for r in csv_resources if str(annee) in (r.get("title") or "")]
            if filtered:
                csv_resources = filtered
        csv_resources.sort(key=lambda r: r.get("last_modified") or "", reverse=True)

        if not csv_resources:
            raise ValueError("Aucune ressource CSV trouvée dans le dataset DGFiP.")

        url = csv_resources[0]["url"]
        rows = _get_csv(url)
        if max_records:
            rows = rows[:max_records]

        nb_inseres, nb_ignores = 0, 0
        batch: list[dict] = []
        communes_seen: set[str] = set()

        for row in rows:
            code_insee = (row.get("depcom") or "").strip()
            if len(code_insee) != 5:
                continue

            annee_row = _safe_int(row.get("annee")) or annee
            if not annee_row:
                continue

            code_dep = (row.get("dep") or _dep_from_insee(code_insee)).strip()
            if code_insee not in communes_seen:
                _upsert_dep(code_dep, code_dep)
                _upsert_commune(
                    code_insee,
                    (row.get("commune") or code_insee).strip(),
                    None,
                    code_dep,
                )
                communes_seen.add(code_insee)

            batch.append(
                {
                    "code_insee": code_insee,
                    "annee": annee_row,
                    "recettes_fonctionnement_k_eur": _safe_int(row.get("produits_total")),
                    "depenses_fonctionnement_k_eur": _safe_int(row.get("charges_total")),
                    "recettes_investissement_k_eur": _safe_int(row.get("invest_ressources_total")),
                    "depenses_investissement_k_eur": _safe_int(row.get("invest_emplois_total")),
                    "epargne_brute_k_eur": _safe_int(row.get("cap_autofinancement")),
                    "encours_dette_k_eur": _safe_int(row.get("dette_encours_total")),
                    "depenses_totales_eur_par_hab": None,
                    "recettes_totales_eur_par_hab": None,
                    "population": _safe_int(row.get("population")),
                }
            )

            if len(batch) >= CHUNK_SIZE:
                result = db.session.execute(
                    pg_insert(BudgetCommune)
                    .values(batch)
                    .on_conflict_do_nothing(index_elements=["code_insee", "annee"])
                )
                nb_inseres += result.rowcount
                nb_ignores += len(batch) - result.rowcount
                batch.clear()
                db.session.flush()

        if batch:
            result = db.session.execute(
                pg_insert(BudgetCommune)
                .values(batch)
                .on_conflict_do_nothing(index_elements=["code_insee", "annee"])
            )
            nb_inseres += result.rowcount
            nb_ignores += len(batch) - result.rowcount

        db.session.commit()
        _close_journal(journal, nb_inseres, nb_ignores, nb_inseres + nb_ignores)
        return _result(journal)

    except Exception as exc:
        db.session.rollback()
        _fail_journal(journal, exc)
        raise


# ---------------------------------------------------------------------------
# Subventions aux associations (data.gouv.fr)
# ---------------------------------------------------------------------------

def ingest_subventions_associations(annee: int | None = None, max_records: int = 10_000) -> dict:
    """
    Agrège les datasets 'subventions associations' publiés par les collectivités sur data.gouv.fr.
    Chaque collectivité publie son propre fichier CSV au format réglementaire standard.
    Le SIREN (9 premiers chiffres du SIRET attribuant) sert à retrouver le code INSEE.
    """
    source_label = f"subventions-associations-{annee or 'latest'}"
    journal = Ingestion(source=source_label, statut="en_cours")
    db.session.add(journal)
    db.session.commit()

    try:
        # Index SIREN → code_insee à partir des communes déjà en base
        siren_map: dict[str, str] = {}
        for commune in db.session.query(Commune).filter(Commune.siren.isnot(None)).all():
            if commune.siren:
                siren_map[commune.siren.strip()] = commune.code_insee

        csv_resources = list_subventions_datasets(max_pages=5)
        nb_inseres, nb_ignores, total_rows = 0, 0, 0

        for res in csv_resources:
            try:
                rows = _get_csv(res["url"])
            except Exception:
                continue

            if max_records and total_rows >= max_records:
                break

            batch: list[dict] = []
            communes_seen: set[str] = set()

            for row in rows:
                if max_records and total_rows >= max_records:
                    break

                nom_beneficiaire = (row.get("nomBeneficiaire") or "").strip()
                if not nom_beneficiaire:
                    continue

                # Nettoyage du SIRET (parfois en notation scientifique via Excel)
                raw_siret = str(row.get("idAttribuant") or "").strip().replace(" ", "").replace(",", "")
                # Reconvertir depuis notation scientifique si nécessaire
                try:
                    if "E+" in raw_siret.upper() or "e+" in raw_siret:
                        raw_siret = str(int(float(raw_siret)))
                except (ValueError, OverflowError):
                    pass
                siren = raw_siret[:9].zfill(9) if len(raw_siret) >= 9 else ""

                code_insee = siren_map.get(siren)
                if not code_insee:
                    continue  # FK non nullable, on ne peut pas insérer sans commune connue

                date_str = row.get("dateConvention") or row.get("dateDecision") or ""
                annee_row = _safe_int(str(date_str).replace("/", "-")[:4]) or annee
                if not annee_row:
                    continue

                if code_insee not in communes_seen:
                    communes_seen.add(code_insee)

                batch.append(
                    {
                        "code_insee": code_insee,
                        "annee": annee_row,
                        "nom_beneficiaire": nom_beneficiaire[:300],
                        "objet": (row.get("objet") or None),
                        "montant_eur": _safe_float(row.get("montant") or row.get("montantVote")),
                    }
                )
                total_rows += 1

                if len(batch) >= CHUNK_SIZE:
                    result = db.session.execute(
                        pg_insert(SubventionAssociation)
                        .values(batch)
                        .on_conflict_do_nothing(
                            index_elements=["code_insee", "nom_beneficiaire", "annee"]
                        )
                    )
                    nb_inseres += result.rowcount
                    nb_ignores += len(batch) - result.rowcount
                    batch.clear()
                    db.session.flush()

            if batch:
                result = db.session.execute(
                    pg_insert(SubventionAssociation)
                    .values(batch)
                    .on_conflict_do_nothing(
                        index_elements=["code_insee", "nom_beneficiaire", "annee"]
                    )
                )
                nb_inseres += result.rowcount
                nb_ignores += len(batch) - result.rowcount
                db.session.flush()

        db.session.commit()
        _close_journal(journal, nb_inseres, nb_ignores, nb_inseres + nb_ignores)
        return _result(journal)

    except Exception as exc:
        db.session.rollback()
        _fail_journal(journal, exc)
        raise


# ---------------------------------------------------------------------------
# Marchés publics — DECP (data.gouv.fr)
# ---------------------------------------------------------------------------

def ingest_marches_publics(annee: int | None = None, max_records: int = 5_000) -> dict:
    source_label = f"marches-publics-{annee or 'latest'}"
    journal = Ingestion(source=source_label, statut="en_cours")
    db.session.add(journal)
    db.session.commit()

    try:
        resources = _get_dataset_resources(DS_MARCHES_SLUG)
        json_resources = [r for r in resources if r.get("format", "").upper() == "JSON"]
        if not json_resources:
            json_resources = [r for r in resources if r.get("format", "").upper() == "CSV"]
        if annee:
            filtered = [r for r in json_resources if str(annee) in (r.get("title") or "")]
            if filtered:
                json_resources = filtered
        json_resources.sort(key=lambda r: r.get("last_modified") or "", reverse=True)

        if not json_resources:
            raise ValueError("Aucune ressource trouvée dans le dataset DECP.")

        url = json_resources[0]["url"]
        data = _get(url)
        # Structure DECP : {"marches": {"marche": [...]}}
        if isinstance(data, list):
            marches = data
        elif isinstance(data.get("marches"), dict):
            marches = data["marches"].get("marche", [])
        else:
            marches = data.get("marches", [])
        if max_records:
            marches = marches[:max_records]

        # Précharger les vrais codes INSEE pour ne PAS créer de fausses communes.
        # Les acheteurs de marchés publics ne sont pas tous des communes : ce
        # sont aussi des EPCI, syndicats mixtes, régies, dont les 5 premiers
        # chiffres du SIRET ne correspondent à AUCUN code INSEE commune.
        known_codes: set[str] = {
            row[0] for row in db.session.query(Commune.code_insee).all()
        }

        nb_inseres, nb_ignores = 0, 0
        batch: list[dict] = []

        for m in marches:
            uid = str(m.get("id") or m.get("uid") or "").strip()
            if not uid:
                continue

            acheteur = m.get("acheteur") or {}
            acheteur_siret = str(acheteur.get("id") or m.get("acheteur_siret") or "")[:14] or None
            acheteur_nom = (acheteur.get("nom") or m.get("acheteur_nom") or "")[:300] or None

            # On ne tente la dérivation INSEE → commune QUE si les 5 premiers
            # chiffres du SIRET matchent une commune connue. Sinon code_insee=NULL
            # (la colonne est nullable) et le marché reste rattaché à son acheteur
            # via le SIRET + nom, sans polluer le référentiel commune.
            code_insee = None
            if acheteur_siret and len(acheteur_siret) >= 5:
                candidate = acheteur_siret[:5]
                if candidate.isdigit() and candidate in known_codes:
                    code_insee = candidate

            date_attr = _safe_date(m.get("dateAttributionMarche") or m.get("date_attribution"))
            annee_row = (date_attr.year if date_attr else None) or annee

            batch.append(
                {
                    "uid": uid[:100],
                    "acheteur_siret": acheteur_siret,
                    "acheteur_nom": acheteur_nom,
                    "code_insee": code_insee,
                    "intitule": (m.get("objet") or m.get("intitule") or None),
                    "nature": (m.get("nature") or None),
                    "procedure": (m.get("procedure") or None),
                    "montant_eur": _safe_float(m.get("montant")),
                    "date_attribution": date_attr,
                    "annee": annee_row,
                }
            )

            if len(batch) >= CHUNK_SIZE:
                result = db.session.execute(
                    pg_insert(MarchePublic)
                    .values(batch)
                    .on_conflict_do_nothing(index_elements=["uid"])
                )
                nb_inseres += result.rowcount
                nb_ignores += len(batch) - result.rowcount
                batch.clear()
                db.session.flush()

        if batch:
            result = db.session.execute(
                pg_insert(MarchePublic)
                .values(batch)
                .on_conflict_do_nothing(index_elements=["uid"])
            )
            nb_inseres += result.rowcount
            nb_ignores += len(batch) - result.rowcount

        db.session.commit()
        _close_journal(journal, nb_inseres, nb_ignores, nb_inseres + nb_ignores)
        return _result(journal)

    except Exception as exc:
        db.session.rollback()
        _fail_journal(journal, exc)
        raise


# ---------------------------------------------------------------------------
# Balances comptables des communes (DGFiP via data.economie.gouv.fr)
# ---------------------------------------------------------------------------

def _insee_from_record(rec: dict) -> str | None:
    """Reconstruit le code INSEE 5 chars depuis ndept + insee du record API."""
    ndept = str(rec.get("ndept") or "").strip()
    insee = str(rec.get("insee") or "").strip()
    if not ndept or not insee:
        return None
    try:
        ndept_int = int(ndept)
        if ndept_int >= 970:
            # Outre-mer : ndept significatif sur 3 chiffres (971-976)
            code = str(ndept_int) + str(int(insee)).zfill(2)
        else:
            code = str(ndept_int).zfill(2) + str(int(insee)).zfill(3)
        # Valider strictement 5 chars — sinon on skip le FK (code_insee nullable)
        return code if len(code) == 5 else None
    except (ValueError, AttributeError):
        return None


_BALANCES_SIREN_BATCH = 30


def _secret_to_none(val) -> float | None:
    """Renvoie None si la valeur est le secret statistique INSEE ('s')."""
    if val in (None, "", "s", "S", "nd", "ns"):
        return None
    return _safe_float(val)


def ingest_balances_comptables(annee: int = 2023, max_records: int = 50_000) -> dict:
    """
    Ingère les balances comptables des communes (poste par poste).
    Stratégie : itère par lots de SIRENs (communes en base) pour contourner
    la limite offset=10 000 de l'API Opendatasoft.

    max_records : nombre max de lignes (0 = tout).
    """
    source_label = f"balances-comptables-{annee}"
    journal = Ingestion(source=source_label, statut="en_cours")
    db.session.add(journal)
    db.session.commit()

    try:
        # Charger tous les SIRENs des communes en base
        communes_db = db.session.query(Commune).filter(Commune.siren.isnot(None)).all()
        siren_map: dict[str, str] = {c.siren.strip(): c.code_insee for c in communes_db if c.siren}
        sirens_all = list(siren_map.keys())

        dataset = f"{DS_BALANCES_PREFIX}{annee}"
        nb_inseres, nb_ignores, total_rows = 0, 0, 0
        batch: list[dict] = []

        for i in range(0, len(sirens_all), _BALANCES_SIREN_BATCH):
            if max_records and total_rows >= max_records:
                break

            siren_batch = sirens_all[i : i + _BALANCES_SIREN_BATCH]
            # Construire le filtre ODSQL : siren="s1" OR siren="s2" ...
            siren_filter = " OR ".join(f'siren="{s}"' for s in siren_batch)
            where = f'cbudg="1" AND ({siren_filter})'

            offset = 0
            while True:
                remaining = (max_records - total_rows) if max_records else 100
                limit = min(100, remaining)
                data = _get(
                    f"{ECONOMIE_API}/{dataset}/records",
                    params={"limit": limit, "offset": offset, "where": where},
                    timeout=30,
                )
                records = data.get("results", [])
                if not records:
                    break

                for rec in records:
                    siren = str(rec.get("siren") or "").strip()
                    compte = str(rec.get("compte") or "").strip()
                    if not siren or not compte:
                        continue

                    code_insee = siren_map.get(siren) or _insee_from_record(rec)

                    batch.append({
                        "siren": siren,
                        "code_insee": code_insee,
                        "annee": annee,
                        "compte": compte[:15],
                        "nom_commune": (rec.get("lbudg") or "")[:200] or None,
                        "obnetdeb": _safe_float(rec.get("obnetdeb")),
                        "obnetcre": _safe_float(rec.get("obnetcre")),
                        "sd": _safe_float(rec.get("sd")),
                        "sc": _safe_float(rec.get("sc")),
                    })
                    total_rows += 1

                if len(batch) >= CHUNK_SIZE:
                    result = db.session.execute(
                        pg_insert(BalanceComptableCommune)
                        .values(batch)
                        .on_conflict_do_nothing(index_elements=["siren", "annee", "compte"])
                    )
                    nb_inseres += result.rowcount
                    nb_ignores += len(batch) - result.rowcount
                    batch.clear()
                    db.session.commit()

                offset += len(records)
                if len(records) < limit or (max_records and total_rows >= max_records):
                    break

        if batch:
            result = db.session.execute(
                pg_insert(BalanceComptableCommune)
                .values(batch)
                .on_conflict_do_nothing(index_elements=["siren", "annee", "compte"])
            )
            nb_inseres += result.rowcount
            nb_ignores += len(batch) - result.rowcount
            db.session.commit()

        _close_journal(journal, nb_inseres, nb_ignores, nb_inseres + nb_ignores)
        return _result(journal)

    except Exception as exc:
        db.session.rollback()
        _fail_journal(journal, exc)
        raise


# ---------------------------------------------------------------------------
# RP — Structure démographique des communes
# ---------------------------------------------------------------------------

def ingest_donnees_demographiques(annee: int = 2020) -> dict:
    """
    Ingère la structure démographique par commune (tranches d'âge) depuis le RP INSEE.
    Années disponibles : 2018, 2019, 2020.
    """
    if annee not in INSEE_RP_URLS:
        raise ValueError(f"Année {annee} non disponible. Années : {sorted(INSEE_RP_URLS)}")

    journal = Ingestion(source=f"insee-rp-demographie-{annee}", statut="en_cours")
    db.session.add(journal)
    db.session.commit()

    try:
        zf = _download_insee_zip(INSEE_RP_URLS[annee])
        # Fichier principal : base-cc-evol-struct-pop-{annee}.CSV (pas de "COM" dans le nom)
        rows = _read_csv_from_zip(zf, "evol-struct-pop")
        yy = str(annee)[2:]

        nb_inseres, nb_ignores = 0, 0
        batch: list[dict] = []
        communes_seen: set[str] = set()

        for row in rows:
            code_insee = (row.get("CODGEO") or "").strip()
            if len(code_insee) != 5:
                continue

            pop = _safe_float(row.get(f"P{yy}_POP")) or 0
            pop0014 = round(_safe_float(row.get(f"P{yy}_POP0014")) or 0)
            pop1529 = round(_safe_float(row.get(f"P{yy}_POP1529")) or 0)
            pop3044 = round(_safe_float(row.get(f"P{yy}_POP3044")) or 0)
            pop4559 = round(_safe_float(row.get(f"P{yy}_POP4559")) or 0)
            pop6074 = round(_safe_float(row.get(f"P{yy}_POP6074")) or 0)
            pop7589 = round(_safe_float(row.get(f"P{yy}_POP7589")) or 0)
            pop90p  = round(_safe_float(row.get(f"P{yy}_POP90P"))  or 0)
            pop65p  = pop6074 + pop7589 + pop90p
            pop_tot = round(pop)

            if code_insee not in communes_seen:
                code_dep = _dep_from_insee(code_insee)
                _upsert_dep(code_dep, code_dep)
                # LIBGEO = libellé commune (convention INSEE des fichiers CODGEO).
                # On le passe pour patcher les noms manquants ou erronés en base.
                nom_commune = (row.get("LIBGEO") or "").strip() or code_insee
                _upsert_commune(code_insee, nom_commune, None, code_dep)
                communes_seen.add(code_insee)

            batch.append({
                "code_insee": code_insee,
                "annee": annee,
                "population_totale": pop_tot,
                "pop_0_14_ans": pop0014,
                "pop_15_29_ans": pop1529,
                "pop_30_44_ans": pop3044,
                "pop_45_59_ans": pop4559,
                "pop_60_74_ans": pop6074,
                "pop_75_89_ans": pop7589,
                "pop_90_ans_plus": pop90p,
                "part_moins_15_pct": round(pop0014 / pop * 100, 2) if pop else None,
                "part_65_ans_plus_pct": round(pop65p / pop * 100, 2) if pop else None,
                "part_15_64_ans_pct": round((pop1529 + pop3044 + pop4559) / pop * 100, 2) if pop else None,
            })

            if len(batch) >= CHUNK_SIZE:
                db.session.flush()
                result = db.session.execute(
                    pg_insert(DonneesDemographiquesCommune)
                    .values(batch)
                    .on_conflict_do_nothing(index_elements=["code_insee", "annee"])
                )
                nb_inseres += result.rowcount
                nb_ignores += len(batch) - result.rowcount
                batch.clear()
                db.session.commit()

        if batch:
            db.session.flush()
            result = db.session.execute(
                pg_insert(DonneesDemographiquesCommune)
                .values(batch)
                .on_conflict_do_nothing(index_elements=["code_insee", "annee"])
            )
            nb_inseres += result.rowcount
            nb_ignores += len(batch) - result.rowcount
            db.session.commit()

        _close_journal(journal, nb_inseres, nb_ignores, nb_inseres + nb_ignores)
        return _result(journal)

    except Exception as exc:
        db.session.rollback()
        _fail_journal(journal, exc)
        raise


# ---------------------------------------------------------------------------
# Filosofi — Revenus et pauvreté des communes
# ---------------------------------------------------------------------------

def ingest_indicateurs_revenus(annee: int = 2020) -> dict:
    """
    Ingère les indicateurs de revenus et pauvreté (Filosofi) par commune.
    Années disponibles : 2018, 2019, 2020.
    's' (secret statistique INSEE) → NULL.
    """
    if annee not in INSEE_FILOSOFI_URLS:
        raise ValueError(f"Année {annee} non disponible. Années : {sorted(INSEE_FILOSOFI_URLS)}")

    journal = Ingestion(source=f"insee-filosofi-{annee}", statut="en_cours")
    db.session.add(journal)
    db.session.commit()

    try:
        zf = _download_insee_zip(INSEE_FILOSOFI_URLS[annee])
        rows = _read_csv_from_zip(zf, "COM")
        yy = str(annee)[2:]

        nb_inseres, nb_ignores = 0, 0
        batch: list[dict] = []
        communes_seen: set[str] = set()

        for row in rows:
            code_insee = (row.get("CODGEO") or "").strip()
            if len(code_insee) != 5:
                continue

            if code_insee not in communes_seen:
                code_dep = _dep_from_insee(code_insee)
                _upsert_dep(code_dep, code_dep)
                nom_commune = (row.get("LIBGEO") or "").strip() or code_insee
                _upsert_commune(code_insee, nom_commune, None, code_dep)
                communes_seen.add(code_insee)

            rd_raw = row.get(f"RD{yy}") or row.get(f'RD"')  # champ parfois avec guillemet
            batch.append({
                "code_insee": code_insee,
                "annee": annee,
                "nb_menages_fiscaux": _safe_int(row.get(f"NBMENFISC{yy}")),
                "revenu_median_uc": _safe_int(_secret_to_none(row.get(f"MED{yy}"))),
                "taux_pauvrete_pct": _secret_to_none(row.get(f"TP60{yy}")),
                "part_menages_imposes_pct": _secret_to_none(row.get(f"PIMP{yy}")),
                "d1_revenu": _safe_int(_secret_to_none(row.get(f"D1{yy}"))),
                "d9_revenu": _safe_int(_secret_to_none(row.get(f"D9{yy}"))),
                "rapport_interdecile": _secret_to_none(rd_raw),
            })

            if len(batch) >= CHUNK_SIZE:
                db.session.flush()
                result = db.session.execute(
                    pg_insert(IndicateurRevenuCommune)
                    .values(batch)
                    .on_conflict_do_nothing(index_elements=["code_insee", "annee"])
                )
                nb_inseres += result.rowcount
                nb_ignores += len(batch) - result.rowcount
                batch.clear()
                db.session.commit()

        if batch:
            db.session.flush()
            result = db.session.execute(
                pg_insert(IndicateurRevenuCommune)
                .values(batch)
                .on_conflict_do_nothing(index_elements=["code_insee", "annee"])
            )
            nb_inseres += result.rowcount
            nb_ignores += len(batch) - result.rowcount
            db.session.commit()

        _close_journal(journal, nb_inseres, nb_ignores, nb_inseres + nb_ignores)
        return _result(journal)

    except Exception as exc:
        db.session.rollback()
        _fail_journal(journal, exc)
        raise


# ---------------------------------------------------------------------------
# Réparation du référentiel commune (geo.api.gouv.fr)
# ---------------------------------------------------------------------------

def repair_commune_referentiel() -> dict:
    """
    Patche les noms et SIRENs des communes en base à partir de l'API officielle
    geo.api.gouv.fr (référentiel COG INSEE). À utiliser quand le champ
    `Commune.nom` contient des placeholders (par ex. le code INSEE répété)
    suite à une ingestion défectueuse.

    L'API retourne ~35 000 entrées en un appel, sans clé. On fait un UPDATE
    en masse par PK (code_insee). Les communes du référentiel qui n'existent
    pas en base sont ignorées — on ne crée jamais ici. Les communes en base
    absentes du référentiel (artefacts) restent telles quelles.
    """
    journal = Ingestion(source="geo-api-gouv-referentiel", statut="en_cours")
    db.session.add(journal)
    db.session.commit()

    try:
        resp = _SESSION.get(
            GEO_API_COMMUNES_URL,
            params={"fields": "nom,code,codeDepartement,siren", "format": "json"},
            timeout=60,
        )
        resp.raise_for_status()
        rows = resp.json()

        # bulk_update_mappings exige que tous les PKs existent en base.
        # On filtre donc sur les code_insee réellement présents.
        existing_codes = {c.code_insee for c in db.session.query(Commune.code_insee).all()}
        mappings = [
            {
                "code_insee": row["code"],
                "nom": row["nom"],
                "siren": row.get("siren"),
            }
            for row in rows
            if row.get("code") and row.get("nom") and row["code"] in existing_codes
        ]
        db.session.bulk_update_mappings(Commune, mappings)
        db.session.commit()

        # Met aussi à jour le libellé des départements (souvent juste le code
        # avant ce passage). On déduit la liste des codes département depuis
        # les communes et on s'appuie sur l'endpoint /departements.
        dep_resp = _SESSION.get(
            "https://geo.api.gouv.fr/departements",
            params={"fields": "nom,code", "format": "json"},
            timeout=30,
        )
        dep_resp.raise_for_status()
        for dep in dep_resp.json():
            db.session.execute(
                Departement.__table__.update()
                .where(Departement.code == dep["code"])
                .values(libelle=dep["nom"])
            )
        db.session.commit()

        nb_total = len(mappings)
        _close_journal(journal, nb_total, 0, nb_total)
        return _result(journal)

    except Exception as exc:
        db.session.rollback()
        _fail_journal(journal, exc)
        raise


# ---------------------------------------------------------------------------
# Helpers journal
# ---------------------------------------------------------------------------

def _close_journal(journal: Ingestion, nb_inseres: int, nb_ignores: int, nb_total: int) -> None:
    journal.statut = "success"
    journal.nb_inseres = nb_inseres
    journal.nb_ignores = nb_ignores
    journal.nb_total = nb_total
    journal.fin = datetime.utcnow()
    db.session.commit()


def _fail_journal(journal: Ingestion, exc: Exception) -> None:
    journal.statut = "erreur"
    journal.message = str(exc)
    journal.fin = datetime.utcnow()
    db.session.commit()


def _result(journal: Ingestion) -> dict:
    return {
        "statut": journal.statut,
        "nb_inseres": journal.nb_inseres,
        "nb_ignores": journal.nb_ignores,
        "nb_total": journal.nb_total,
        "duree_s": round((journal.fin - journal.debut).total_seconds(), 2) if journal.fin else None,
    }

import csv
import io
import zipfile
import requests

DATA_GOUV_API = "https://www.data.gouv.fr/api/1"
ECONOMIE_API = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets"

CULTURE_DEPENSES_URL = (
    "https://object.data.gouv.fr/ministere-culture/DEPENSES_CULTURELLES"
    "/depenses_culturelles_des_communes.csv"
)

# Slug du dataset DGFiP "Comptes individuels des communes" sur data.gouv.fr
DS_BUDGETS_SLUG = "comptes-individuels-des-communes"

# Terme de recherche pour les datasets subventions (pas de dataset national unique)
DS_SUBVENTIONS_QUERY = "subventions associations"

# Slug du dataset DECP marchés publics consolidés
DS_MARCHES_SLUG = "donnees-essentielles-de-la-commande-publique-fichiers-consolides"

# Préfixe des datasets balances comptables des communes (suffixe = année)
DS_BALANCES_PREFIX = "balances-comptables-des-communes-en-"

# URLs directes INSEE par année (ZIP contenant CSV communes)
INSEE_RP_URLS = {
    2020: "https://www.insee.fr/fr/statistiques/fichier/7632446/base-cc-evol-struct-pop-2020_csv.zip",
    2019: "https://www.insee.fr/fr/statistiques/fichier/6456153/base-ccc-evol-struct-pop-2019.zip",
    2018: "https://www.insee.fr/fr/statistiques/fichier/5395875/base-ccc-evol-struct-pop-2018.zip",
}
INSEE_FILOSOFI_URLS = {
    2020: "https://www.insee.fr/fr/statistiques/fichier/6692392/base-cc-filosofi-2020_CSV.zip",
    2019: "https://www.insee.fr/fr/statistiques/fichier/6036902/base-cc-filosofi-2019_CSV.zip",
    2018: "https://www.insee.fr/fr/statistiques/fichier/5009236/base-cc-filosofi-2018_CSV_geo2021.zip",
}

_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json"})

# Simple module-level cache: {url: str}
_csv_cache: dict[str, str] = {}


def _get(url: str, params: dict | None = None, timeout: int = 15) -> dict:
    resp = _SESSION.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _get_csv(url: str, timeout: int = 60) -> list[dict]:
    """Télécharge et parse un CSV (mis en cache en mémoire). Détecte le délimiteur automatiquement."""
    if url not in _csv_cache:
        resp = _SESSION.get(url, timeout=timeout)
        resp.raise_for_status()
        _csv_cache[url] = resp.text
    raw = _csv_cache[url]
    # Détection du délimiteur sur la première ligne
    first_line = raw.split("\n")[0]
    delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter)
    return list(reader)


# ---------------------------------------------------------------------------
# data.gouv.fr — recherche de datasets
# ---------------------------------------------------------------------------

def search_datasets(q: str, page: int = 1, page_size: int = 10) -> dict:
    """Recherche de datasets sur data.gouv.fr."""
    data = _get(
        f"{DATA_GOUV_API}/datasets/",
        params={"q": q, "page": page, "page_size": page_size},
    )
    results = [
        {
            "id": d["id"],
            "slug": d["slug"],
            "title": d["title"],
            "description": (d.get("description") or "")[:200],
            "organization": (d.get("organization") or {}).get("name"),
            "url": d.get("page"),
            "resources_count": len(d.get("resources", [])),
        }
        for d in data.get("data", [])
    ]
    return {
        "total": data.get("total", 0),
        "page": page,
        "page_size": page_size,
        "results": results,
    }


def _get_dataset_resources(slug: str) -> list[dict]:
    """Retourne la liste des ressources d'un dataset data.gouv.fr."""
    data = _get(f"{DATA_GOUV_API}/datasets/{slug}/")
    return data.get("resources", [])


# ---------------------------------------------------------------------------
# Dépenses culturelles des communes (ministère de la Culture)
# ---------------------------------------------------------------------------

def _load_culture_csv() -> list[dict]:
    return _get_csv(CULTURE_DEPENSES_URL)


def fetch_depenses_culturelles(
    commune: str | None = None,
    departement: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Dépenses culturelles des communes (source : ministère de la Culture)."""
    rows = _load_culture_csv()

    if commune:
        terme = commune.upper()
        rows = [r for r in rows if terme in (r.get("nom_commune") or "").upper()]
    if departement:
        rows = [r for r in rows if (r.get("code_insee") or "").startswith(departement.lstrip("0").zfill(2))]

    total = len(rows)
    page_rows = rows[offset : offset + limit]

    return {
        "source": "Ministère de la Culture — data.gouv.fr",
        "dataset": "depenses-culturelles-des-communes",
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": page_rows,
    }


# ---------------------------------------------------------------------------
# Budgets communaux — DGFiP (data.gouv.fr)
# ---------------------------------------------------------------------------

def fetch_budgets_communes(
    commune: str | None = None,
    departement: str | None = None,
    annee: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """
    Budgets annuels des communes : recettes, dépenses, épargne brute, encours de la dette.
    Source : DGFiP — Comptes individuels des communes (data.gouv.fr).
    """
    resources = _get_dataset_resources(DS_BUDGETS_SLUG)
    # On cible le fichier CSV de l'année demandée, ou le plus récent disponible
    csv_resources = [
        r for r in resources
        if r.get("format", "").upper() == "CSV"
        and (annee is None or str(annee) in (r.get("title") or ""))
    ]
    if not csv_resources:
        csv_resources = [r for r in resources if r.get("format", "").upper() == "CSV"]

    if not csv_resources:
        return {"error": "Aucune ressource CSV trouvée pour ce dataset", "results": []}

    # Ressource la plus récente
    csv_resources.sort(key=lambda r: r.get("last_modified") or "", reverse=True)
    url = csv_resources[0]["url"]
    rows = _get_csv(url)

    if commune:
        terme = commune.upper()
        rows = [r for r in rows if terme in (r.get("lbudg") or r.get("nom_commune") or "").upper()]
    if departement:
        rows = [r for r in rows if (r.get("dep") or r.get("code_departement") or "").lstrip("0") == departement.lstrip("0")]
    if annee:
        rows = [r for r in rows if str(r.get("exer") or r.get("annee") or "") == str(annee)]

    total = len(rows)
    return {
        "source": "DGFiP — Comptes individuels des communes (data.gouv.fr)",
        "dataset": DS_BUDGETS_SLUG,
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": rows[offset : offset + limit],
    }


# ---------------------------------------------------------------------------
# Subventions aux associations (data.gouv.fr — agrégation multi-datasets)
# ---------------------------------------------------------------------------

def list_subventions_datasets(max_pages: int = 5) -> list[dict]:
    """Retourne les ressources CSV de tous les datasets 'subventions associations' trouvés."""
    csv_resources = []
    for page in range(1, max_pages + 1):
        data = _get(
            f"{DATA_GOUV_API}/datasets/",
            params={"q": DS_SUBVENTIONS_QUERY, "page": page, "page_size": 20},
        )
        for dataset in data.get("data", []):
            for res in dataset.get("resources", []):
                if res.get("format", "").upper() == "CSV":
                    csv_resources.append({"url": res["url"], "dataset_slug": dataset["slug"]})
        if page >= data.get("total", 0) // 20 + 1:
            break
    return csv_resources


def fetch_subventions_associations(
    commune: str | None = None,
    beneficiaire: str | None = None,
    annee: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """
    Subventions versées par les collectivités locales aux associations.
    Source : data.gouv.fr — agrégation de datasets publiés par les collectivités (format standard).
    """
    all_rows: list[dict] = []
    for res in list_subventions_datasets(max_pages=3):
        try:
            rows = _get_csv(res["url"])
            all_rows.extend(rows)
        except Exception:
            continue

    if commune:
        terme = commune.upper()
        all_rows = [r for r in all_rows if terme in (r.get("nomAttribuant") or "").upper()]
    if beneficiaire:
        terme = beneficiaire.upper()
        all_rows = [r for r in all_rows if terme in (r.get("nomBeneficiaire") or "").upper()]
    if annee:
        all_rows = [r for r in all_rows if str(r.get("dateConvention") or "").startswith(str(annee))]

    total = len(all_rows)
    return {
        "source": "data.gouv.fr — Subventions collectivités (format réglementaire)",
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": all_rows[offset : offset + limit],
    }


# ---------------------------------------------------------------------------
# Marchés publics — DECP (data.gouv.fr)
# ---------------------------------------------------------------------------

def fetch_marches_publics(
    acheteur: str | None = None,
    annee: int | None = None,
    nature: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """
    Marchés publics attribués par les collectivités locales.
    Source : DECP — Données essentielles de la commande publique (data.gouv.fr).
    """
    resources = _get_dataset_resources(DS_MARCHES_SLUG)
    json_resources = [r for r in resources if r.get("format", "").upper() == "JSON"]
    if not json_resources:
        json_resources = [r for r in resources if r.get("format", "").upper() == "CSV"]

    if not json_resources:
        return {"error": "Aucune ressource trouvée pour ce dataset", "results": []}

    json_resources.sort(key=lambda r: r.get("last_modified") or "", reverse=True)
    if annee:
        filtered = [r for r in json_resources if str(annee) in (r.get("title") or "")]
        if filtered:
            json_resources = filtered

    url = json_resources[0]["url"]
    data = _get(url)
    if isinstance(data, list):
        marches = data
    elif isinstance(data.get("marches"), dict):
        marches = data["marches"].get("marche", [])
    else:
        marches = data.get("marches", [])

    if acheteur:
        terme = acheteur.upper()
        marches = [m for m in marches if terme in (m.get("acheteur", {}).get("nom") or m.get("acheteur_nom") or "").upper()]
    if nature:
        terme = nature.upper()
        marches = [m for m in marches if terme in (m.get("nature") or "").upper()]

    total = len(marches)
    return {
        "source": "DECP — Données essentielles de la commande publique (data.gouv.fr)",
        "dataset": DS_MARCHES_SLUG,
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": marches[offset : offset + limit],
    }


# ---------------------------------------------------------------------------
# Balances comptables des communes (DGFiP via data.economie.gouv.fr)
# ---------------------------------------------------------------------------

# Libellés des classes de comptes pour lecture humaine
LABELS_COMPTES = {
    "6": "Charges (fonctionnement)",
    "60": "Achats et variation de stocks",
    "61": "Services extérieurs",
    "62": "Autres services extérieurs",
    "63": "Impôts, taxes et versements assimilés",
    "64": "Charges de personnel",
    "65": "Autres charges de gestion courante",
    "66": "Charges financières",
    "67": "Charges exceptionnelles",
    "68": "Dotations aux amortissements",
    "7": "Produits (fonctionnement)",
    "70": "Ventes et prestations de services",
    "73": "Impôts et taxes",
    "74": "Dotations, subventions et participations",
    "75": "Autres produits de gestion courante",
    "76": "Produits financiers",
    "77": "Produits exceptionnels",
    "2": "Investissement — immobilisations",
    "20": "Immobilisations incorporelles",
    "21": "Immobilisations corporelles",
    "23": "Immobilisations en cours",
    "1": "Financement à long terme",
    "16": "Emprunts et dettes assimilées",
}


def _label_compte(compte: str) -> str:
    for prefix in (compte[:3], compte[:2], compte[:1]):
        if prefix in LABELS_COMPTES:
            return LABELS_COMPTES[prefix]
    return "Autre"


def fetch_balances_comptables(
    siren: str | None = None,
    commune: str | None = None,
    compte_prefix: str | None = None,
    annee: int = 2023,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """
    Balances comptables des communes par poste de compte.
    Source : DGFiP — data.economie.gouv.fr.
    Paramètres :
      siren          : SIREN de la commune (9 chiffres)
      commune        : nom de la commune (recherche partielle)
      compte_prefix  : préfixe de compte (ex: '64' = charges de personnel)
      annee          : année d'exercice (défaut 2023)
    """
    dataset = f"{DS_BALANCES_PREFIX}{annee}"
    where_parts = ['categ="Commune"', 'cbudg="1"']
    if siren:
        where_parts.append(f'siren="{siren}"')
    if commune:
        where_parts.append(f'lbudg like "%{commune.upper()}%"')
    if compte_prefix:
        where_parts.append(f'compte like "{compte_prefix}%"')

    params = {
        "limit": min(limit, 100),
        "offset": offset,
        "where": " AND ".join(where_parts),
    }
    data = _get(f"{ECONOMIE_API}/{dataset}/records", params=params, timeout=30)
    results = data.get("results", [])

    enriched = []
    for r in results:
        r["libelle_compte"] = _label_compte(r.get("compte") or "")
        enriched.append(r)

    return {
        "source": f"DGFiP — Balances comptables des communes {annee} (data.economie.gouv.fr)",
        "annee": annee,
        "total_count": data.get("total_count", 0),
        "limit": limit,
        "offset": offset,
        "results": enriched,
    }


# ---------------------------------------------------------------------------
# Helpers ZIP INSEE
# ---------------------------------------------------------------------------

def _download_insee_zip(url: str, timeout: int = 120) -> zipfile.ZipFile:
    """Télécharge un ZIP depuis l'INSEE et le retourne comme objet ZipFile."""
    resp = _SESSION.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return zipfile.ZipFile(io.BytesIO(resp.content))


def _read_csv_from_zip(zf: zipfile.ZipFile, keyword: str, encoding: str = "utf-8") -> list[dict]:
    """Extrait et parse le premier CSV dont le nom contient `keyword`."""
    target = next(
        (n for n in zf.namelist() if keyword.upper() in n.upper() and n.endswith((".csv", ".CSV"))),
        None,
    )
    if not target:
        raise FileNotFoundError(f"Aucun fichier CSV contenant '{keyword}' dans le ZIP")
    with zf.open(target) as f:
        raw = f.read().decode(encoding, errors="replace")
    first_line = raw.split("\n")[0]
    delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
    return list(csv.DictReader(io.StringIO(raw), delimiter=delimiter))


# ---------------------------------------------------------------------------
# RP — Structure démographique des communes (INSEE)
# ---------------------------------------------------------------------------

def fetch_donnees_demographiques(
    code_insee: str | None = None,
    annee: int = 2020,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """
    Structure démographique par commune (tranches d'âge).
    Source : INSEE — Recensement de la Population, fichier Communes.
    """
    url = INSEE_RP_URLS.get(annee)
    if not url:
        return {"error": f"Année {annee} non disponible. Années: {sorted(INSEE_RP_URLS)}", "results": []}

    zf = _download_insee_zip(url)
    rows = _read_csv_from_zip(zf, "COM")
    yy = str(annee)[2:]

    if code_insee:
        rows = [r for r in rows if r.get("CODGEO") == code_insee]

    total = len(rows)
    page = rows[offset : offset + limit]

    def _fmt(r: dict) -> dict:
        pop = float(r.get(f"P{yy}_POP") or 0) or 1
        pop0014 = round(float(r.get(f"P{yy}_POP0014") or 0))
        pop6074 = round(float(r.get(f"P{yy}_POP6074") or 0))
        pop7589 = round(float(r.get(f"P{yy}_POP7589") or 0))
        pop90p  = round(float(r.get(f"P{yy}_POP90P")  or 0))
        pop65p  = pop6074 + pop7589 + pop90p
        return {
            "code_insee": r.get("CODGEO"),
            "population_totale": round(pop),
            "pop_0_14_ans": pop0014,
            "pop_15_29_ans": round(float(r.get(f"P{yy}_POP1529") or 0)),
            "pop_30_44_ans": round(float(r.get(f"P{yy}_POP3044") or 0)),
            "pop_45_59_ans": round(float(r.get(f"P{yy}_POP4559") or 0)),
            "pop_60_74_ans": pop6074,
            "pop_75_89_ans": pop7589,
            "pop_90_ans_plus": pop90p,
            "part_moins_15_pct": round(pop0014 / pop * 100, 2),
            "part_65_ans_plus_pct": round(pop65p / pop * 100, 2),
        }

    return {
        "source": f"INSEE — Recensement de la Population {annee}",
        "annee": annee,
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": [_fmt(r) for r in page],
    }


# ---------------------------------------------------------------------------
# Filosofi — Revenus et pauvreté des communes (INSEE)
# ---------------------------------------------------------------------------

def fetch_indicateurs_revenus(
    code_insee: str | None = None,
    annee: int = 2020,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """
    Revenus et pauvreté par commune (Filosofi).
    Source : INSEE — Filosofi, fichier Communes.
    's' = secret statistique (commune < 2000 ménages fiscaux) → retourné tel quel.
    """
    url = INSEE_FILOSOFI_URLS.get(annee)
    if not url:
        return {"error": f"Année {annee} non disponible. Années: {sorted(INSEE_FILOSOFI_URLS)}", "results": []}

    zf = _download_insee_zip(url)
    rows = _read_csv_from_zip(zf, "COM")
    yy = str(annee)[2:]

    if code_insee:
        rows = [r for r in rows if r.get("CODGEO") == code_insee]

    total = len(rows)
    return {
        "source": f"INSEE — Filosofi {annee}, fichier Communes",
        "annee": annee,
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": rows[offset : offset + limit],
    }

"""
Définition des intents (intentions).

Un "intent" est la catégorie d'action que l'utilisateur veut déclencher.
Ici, chaque intent correspond à un jeu de données (= un endpoint API).
La détection d'intent est faite par mots-clés normalisés : c'est rustique mais
prévisible, et ça suffit tant que les 7 catégories sont bien distinctes.

Pour chaque intent on stocke aussi `build_kwargs` : une fonction qui prend les
entités extraites et retourne le dict d'arguments à passer au scraper. C'est
ce qui fait le pont entre « ce que l'utilisateur a dit » et « comment appeler
la bonne fonction Python ».
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.scrapers.data_gouv import (
    fetch_balances_comptables,
    fetch_budgets_communes,
    fetch_depenses_culturelles,
    fetch_donnees_demographiques,
    fetch_indicateurs_revenus,
    fetch_marches_publics,
    fetch_subventions_associations,
)

from app.nlp.entities import Entities, _strip_accents


@dataclass(frozen=True)
class Intent:
    name: str
    keywords: tuple[str, ...]            # un seul mot-clé matché suffit à activer l'intent
    fetch: Callable[..., Any]            # scraper à invoquer
    build_kwargs: Callable[[Entities], dict[str, Any]]
    description: str


# --- builders : Entities → kwargs du fetch correspondant -------------------
# Chaque builder reflète la signature du scraper. C'est ici qu'on choisit quel
# attribut de Commune passer : `nom` (recherche textuelle), `code_insee`
# (clé INSEE pour INSEE), ou `siren` (clé pour DGFiP).

def _kw_depenses_culturelles(e: Entities) -> dict[str, Any]:
    return {
        "commune": e.commune.nom if e.commune else None,
        "departement": e.departement,
        "limit": 50,
        "offset": 0,
    }


def _kw_budgets(e: Entities) -> dict[str, Any]:
    return {
        "commune": e.commune.nom if e.commune else None,
        "departement": e.departement,
        "annee": e.annee,
        "limit": 50,
        "offset": 0,
    }


def _kw_balances(e: Entities) -> dict[str, Any]:
    return {
        # On préfère le SIREN s'il est connu — c'est l'identifiant le plus fiable
        # côté DGFiP. Sinon on retombe sur le nom.
        "siren": e.commune.siren if e.commune and e.commune.siren else None,
        "commune": e.commune.nom if e.commune else None,
        "compte_prefix": e.compte_prefix,
        "annee": e.annee or 2023,
        "limit": 50,
        "offset": 0,
    }


def _kw_subventions(e: Entities) -> dict[str, Any]:
    return {
        "commune": e.commune.nom if e.commune else None,
        "beneficiaire": e.beneficiaire,
        "annee": e.annee,
        "limit": 50,
        "offset": 0,
    }


def _kw_marches(e: Entities) -> dict[str, Any]:
    return {
        "acheteur": e.commune.nom if e.commune else None,
        "annee": e.annee,
        "nature": None,
        "limit": 50,
        "offset": 0,
    }


def _kw_demographie(e: Entities) -> dict[str, Any]:
    return {
        # INSEE indexe par code_insee, pas par nom.
        "code_insee": e.commune.code_insee if e.commune else None,
        "annee": e.annee or 2020,
        "limit": 50,
        "offset": 0,
    }


def _kw_revenus(e: Entities) -> dict[str, Any]:
    return {
        "code_insee": e.commune.code_insee if e.commune else None,
        "annee": e.annee or 2020,
        "limit": 50,
        "offset": 0,
    }


INTENTS: tuple[Intent, ...] = (
    Intent(
        name="depenses_culturelles",
        keywords=("culture", "culturel", "culturelle", "culturelles", "spectacle", "patrimoine"),
        fetch=fetch_depenses_culturelles,
        build_kwargs=_kw_depenses_culturelles,
        description="Dépenses culturelles des communes",
    ),
    Intent(
        name="budgets",
        keywords=("budget", "budgets", "recette", "recettes", "epargne", "endettement"),
        fetch=fetch_budgets_communes,
        build_kwargs=_kw_budgets,
        description="Budgets communaux (recettes, dépenses, épargne, dette)",
    ),
    Intent(
        name="balances",
        # Inclut aussi les concepts métier qui ne sont des balances qu'à travers
        # un poste comptable (personnel = 64, dette/intérêts = 66, impôts = 73…).
        # Le compte_prefix sera dérivé par entities._extract_compte_prefix.
        keywords=(
            "balance", "comptable", "comptabilite", "compte", "poste",
            "personnel", "salaire", "salaires", "remuneration", "remunerations",
            "charges", "interets", "fiscalite", "dotations",
            "impot", "impots", "taxe", "taxes",
        ),
        fetch=fetch_balances_comptables,
        build_kwargs=_kw_balances,
        description="Balances comptables par poste",
    ),
    Intent(
        name="subventions",
        keywords=("subvention", "subventions", "association", "associations", "aide"),
        fetch=fetch_subventions_associations,
        build_kwargs=_kw_subventions,
        description="Subventions versées aux associations",
    ),
    Intent(
        name="marches",
        keywords=("marche", "marches", "appel d'offres", "contrat", "attribution", "decp"),
        fetch=fetch_marches_publics,
        build_kwargs=_kw_marches,
        description="Marchés publics attribués",
    ),
    Intent(
        name="demographie",
        keywords=("demographie", "population", "habitant", "habitants", "age", "tranches"),
        fetch=fetch_donnees_demographiques,
        build_kwargs=_kw_demographie,
        description="Structure démographique (INSEE RP)",
    ),
    Intent(
        name="revenus",
        keywords=("revenu", "revenus", "salaire", "pauvrete", "menage", "menages", "filosofi", "decile"),
        fetch=fetch_indicateurs_revenus,
        build_kwargs=_kw_revenus,
        description="Revenus et pauvreté (INSEE Filosofi)",
    ),
)


def detect_intent(text: str) -> Intent | None:
    """
    Choisit l'intent dont les mots-clés apparaissent dans la phrase.
    Stratégie naïve mais transparente : on compte les mots-clés matchés par
    intent et on retient celui qui en a le plus. Égalité → premier déclaré.

    Pour passer à une approche apprenante plus tard, remplacer cette fonction
    par un classifieur (spaCy TextCategorizer ou scikit-learn).
    """
    normalized = _strip_accents(text)
    best: tuple[int, Intent | None] = (0, None)
    for intent in INTENTS:
        score = sum(1 for kw in intent.keywords if kw in normalized)
        if score > best[0]:
            best = (score, intent)
    return best[1]

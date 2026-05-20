"""
Extraction d'entités à partir d'une question en langage naturel.

Une "entité" en NLP, c'est un morceau de texte qui désigne une chose concrète
du domaine : un nom de commune, une année, un code département, un poste
comptable, etc. Le travail de ce module est de retrouver ces fragments dans
une phrase libre comme :

    "Quel est le budget de Lyon en 2022 ?"
                       ^^^^      ^^^^
                       commune   année

Trois techniques sont combinées ici :
  1. PhraseMatcher spaCy pour les noms de communes (liste fermée connue : on
     l'alimente depuis la table `communes`).
  2. Regex pour les patterns fixes (année à 4 chiffres, code département).
  3. Lookup mots-clés → valeurs canoniques (ex : "personnel" → compte '64').
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import spacy
from spacy.matcher import PhraseMatcher

from app.models.referentiel import Commune


# spaCy "blank" = pipeline français vide (juste le tokenizer, pas de NER ni POS).
# C'est suffisant pour un PhraseMatcher en mode exact-match et ça évite d'avoir
# à télécharger un modèle (fr_core_news_sm fait ~15 Mo).
_nlp = spacy.blank("fr")


# Années plausibles pour des données financières publiques : 19xx ou 20xx.
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

# Code département officiel INSEE :
#   - métropole hors Corse : '01'–'95'
#   - Corse : '2A', '2B'
#   - DOM : '971'–'976'
# Les \b évitent de matcher l'intérieur d'un autre nombre (ex : "2022" → "20").
_DEPT_RE = re.compile(
    r"\b(?:0[1-9]|[1-8]\d|9[0-5]|2[AB]|97[1-6])\b",
    re.IGNORECASE,
)

# Postes comptables M14 fréquemment cités en langage courant.
# Permet de transformer "dépenses de personnel" → compte_prefix='64'.
_COMPTE_KEYWORDS: dict[str, str] = {
    "personnel": "64",
    "salaires": "64",
    "salaire": "64",
    "remunerations": "64",
    "charges financieres": "66",
    "interets": "66",
    "dette": "66",
    "impots": "73",
    "taxes": "73",
    "fiscalite": "73",
    "subventions recues": "74",
    "dotations": "74",
}


@dataclass(frozen=True)
class Entities:
    """Résultat d'une extraction. Tous les champs sont optionnels."""
    commune: Optional[Commune] = None
    annee: Optional[int] = None
    departement: Optional[str] = None
    compte_prefix: Optional[str] = None
    beneficiaire: Optional[str] = None


def _strip_accents(text: str) -> str:
    """Minuscule + sans diacritiques. Utile pour comparer des mots-clés
    indépendamment de l'orthographe (« dépense » ↔ « depense »)."""
    text = text.lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


@lru_cache(maxsize=1)
def _commune_matcher() -> tuple[PhraseMatcher, dict[str, Commune]]:
    """
    Construit le PhraseMatcher une seule fois par process (lru_cache).
    On l'alimente avec tous les noms de communes en base — c'est le « gazetier »
    (gazetteer en anglais), terme NLP pour désigner une liste fermée de noms
    propres servant de référence.

    Retourne aussi un index { nom_minuscule → Commune } pour récupérer le
    code_insee/siren après détection.

    Doit être appelé dans un contexte applicatif Flask (la requête DB en a besoin).
    """
    matcher = PhraseMatcher(_nlp.vocab, attr="LOWER")
    index: dict[str, Commune] = {}
    # On exclut les communes dont le nom == code_insee : ce sont des entrées
    # historiques (communes fusionnées) ou des artefacts dont le « nom » n'est
    # pas exploitable pour du matching en langage naturel.
    rows = Commune.query.filter(Commune.nom != Commune.code_insee).all()
    for c in rows:
        # make_doc() = tokenisation sans pipeline. Le PhraseMatcher matche
        # sur des séquences de tokens, pas sur des substrings — ça évite que
        # "Marseille" matche "Marseillan".
        matcher.add(c.code_insee, [_nlp.make_doc(c.nom)])
        index[c.nom.lower()] = c
    return matcher, index


def _extract_commune(text: str) -> Optional[Commune]:
    matcher, index = _commune_matcher()
    doc = _nlp(text)
    matches = matcher(doc)
    if not matches:
        return None
    # En cas d'ambiguïté ("Saint-Pierre" existe dans plusieurs départements),
    # on prend le match le plus long — donc le plus spécifique.
    matches.sort(key=lambda m: m[2] - m[1], reverse=True)
    _, start, end = matches[0]
    return index.get(doc[start:end].text.lower())


def _extract_annee(text: str) -> Optional[int]:
    m = _YEAR_RE.search(text)
    return int(m.group()) if m else None


def _extract_departement(text: str) -> Optional[str]:
    m = _DEPT_RE.search(text)
    return m.group().upper() if m else None


def _extract_compte_prefix(text: str) -> Optional[str]:
    normalized = _strip_accents(text)
    for keyword, prefix in _COMPTE_KEYWORDS.items():
        if keyword in normalized:
            return prefix
    return None


def extract(text: str) -> Entities:
    """Point d'entrée du module : phrase libre → Entities."""
    return Entities(
        commune=_extract_commune(text),
        annee=_extract_annee(text),
        departement=_extract_departement(text),
        compte_prefix=_extract_compte_prefix(text),
        beneficiaire=None,  # extraction libre non triviale — laissé pour itération future
    )
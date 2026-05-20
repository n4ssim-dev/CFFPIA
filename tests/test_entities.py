"""
Tests des extracteurs d'entités (app/nlp/entities.py).

Couvre uniquement les fonctions PURES — celles qui ne dépendent ni de la base,
ni du réseau, ni du PhraseMatcher spaCy alimenté depuis Commune.query.
L'extraction de commune via le gazetier est testée à part (cf. test_pipeline.py).
"""

from __future__ import annotations

from app.nlp.entities import (
    _extract_annee,
    _extract_compte_prefix,
    _extract_departement,
    _strip_accents,
)


# ---------------------------------------------------------------------------
# _strip_accents — normalisation pour la comparaison de mots-clés
# ---------------------------------------------------------------------------

def test_strip_accents_basic():
    assert _strip_accents("Dépenses") == "depenses"


def test_strip_accents_multiple():
    assert _strip_accents("Marché à Paris") == "marche a paris"


def test_strip_accents_no_change():
    assert _strip_accents("budget") == "budget"


def test_strip_accents_empty():
    assert _strip_accents("") == ""


# ---------------------------------------------------------------------------
# _extract_annee — année 4 chiffres dans la plage 19xx / 20xx
# ---------------------------------------------------------------------------

def test_extract_annee_present():
    assert _extract_annee("Budget de Lyon en 2022 ?") == 2022


def test_extract_annee_absent():
    assert _extract_annee("Budget de Lyon") is None


def test_extract_annee_first_wins():
    # Quand plusieurs années sont présentes, la première trouvée est retenue.
    assert _extract_annee("entre 2019 et 2022") == 2019


def test_extract_annee_rejects_three_digits():
    # "100" ne doit pas matcher (regex demande 4 chiffres préfixés 19/20).
    assert _extract_annee("100 budget") is None


def test_extract_annee_rejects_out_of_range():
    # 1800 n'est pas dans le range plausible.
    assert _extract_annee("1800 quelque chose") is None


def test_extract_annee_handles_19xx():
    assert _extract_annee("recensement 1999") == 1999


# ---------------------------------------------------------------------------
# _extract_departement — 01-95, 2A/2B, 971-976
# ---------------------------------------------------------------------------

def test_extract_departement_two_digits():
    assert _extract_departement("dans le département 69") == "69"


def test_extract_departement_corse_a():
    assert _extract_departement("Corse-du-Sud (2A)") == "2A"


def test_extract_departement_corse_b_lowercase():
    # La casse en entrée est normalisée en sortie (uppercase).
    assert _extract_departement("en 2b") == "2B"


def test_extract_departement_dom():
    assert _extract_departement("La Réunion 974") == "974"


def test_extract_departement_year_should_not_match():
    # "2022" ne doit PAS être interprété comme un département.
    # La regex \b...\b protège contre l'extraction partielle de "20" dans "2022".
    assert _extract_departement("en 2022") is None


def test_extract_departement_absent():
    assert _extract_departement("Bordeaux") is None


def test_extract_departement_rejects_96():
    # 96 n'existe pas (les départements vont jusqu'à 95 puis sautent à 2A/2B/97x).
    assert _extract_departement("dans le 96") is None


# ---------------------------------------------------------------------------
# _extract_compte_prefix — mots-clés métier → préfixe de compte M14
# ---------------------------------------------------------------------------

def test_extract_compte_personnel():
    # "personnel" / "salaire" / etc. → compte 64 (charges de personnel).
    assert _extract_compte_prefix("charges de personnel") == "64"


def test_extract_compte_salaire():
    assert _extract_compte_prefix("salaires versés") == "64"


def test_extract_compte_dette():
    # "dette" → compte 66 (charges financières).
    assert _extract_compte_prefix("encours de dette") == "66"


def test_extract_compte_impots():
    # "impôts" (accentué) → 73, via la normalisation _strip_accents en amont.
    assert _extract_compte_prefix("recettes d'impôts") == "73"


def test_extract_compte_none():
    assert _extract_compte_prefix("question sans rapport") is None


def test_extract_compte_case_insensitive():
    assert _extract_compte_prefix("PERSONNEL") == "64"

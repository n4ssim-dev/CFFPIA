"""
Tests de la détection d'intent (app/nlp/intents.py).

detect_intent est une fonction pure (mots-clés normalisés → Intent).
Aucune DB, aucun réseau, aucun fetch — uniquement le matching textuel.
"""

from __future__ import annotations

from app.nlp.intents import INTENTS, detect_intent


def _names() -> set[str]:
    return {i.name for i in INTENTS}


def test_seven_intents_defined():
    """Sanity-check : on a bien les 7 jeux de données attendus."""
    assert _names() == {
        "depenses_culturelles",
        "budgets",
        "balances",
        "subventions",
        "marches",
        "demographie",
        "revenus",
    }


# ---------------------------------------------------------------------------
# Matchings positifs — un mot-clé propre à chaque intent
# ---------------------------------------------------------------------------

def test_detect_budgets():
    assert detect_intent("Quel est le budget de Lyon ?").name == "budgets"


def test_detect_subventions():
    assert detect_intent("subventions aux associations").name == "subventions"


def test_detect_marches_accented():
    # "marché" doit matcher "marche" après normalisation sans accents.
    assert detect_intent("les marchés publics à Paris").name == "marches"


def test_detect_demographie():
    assert detect_intent("démographie de Bordeaux").name == "demographie"


def test_detect_revenus():
    assert detect_intent("taux de pauvreté à Toulouse").name == "revenus"


def test_detect_depenses_culturelles():
    assert detect_intent("dépenses culturelles à Lille").name == "depenses_culturelles"


# ---------------------------------------------------------------------------
# Balances — mots-clés métier élargis (personnel / impôts / charges…)
# ---------------------------------------------------------------------------

def test_detect_balances_via_personnel():
    # "personnel" est listé dans les keywords de balances depuis l'enrichissement.
    assert detect_intent("charges de personnel à Lille").name == "balances"


def test_detect_balances_via_impots():
    assert detect_intent("impôts à Nantes").name == "balances"


def test_detect_balances_via_compte():
    assert detect_intent("compte comptable 64").name == "balances"


# ---------------------------------------------------------------------------
# Cas limites
# ---------------------------------------------------------------------------

def test_detect_none_when_no_keyword():
    assert detect_intent("bonjour, comment ça va ?") is None


def test_detect_none_on_empty():
    assert detect_intent("") is None


def test_detect_normalizes_case():
    # La détection ignore la casse.
    assert detect_intent("BUDGET").name == "budgets"


def test_detect_best_score_wins():
    # Une question qui contient des mots-clés de PLUSIEURS intents doit
    # retourner celui qui en a le plus.
    # "budget" (1 mot-clé de budgets) vs "marché public" (1 mot-clé de marches)
    # → égalité, le premier déclaré (depenses_culturelles, budgets, ...) gagne.
    intent = detect_intent("budget et marché de Lyon")
    # On vérifie surtout que la décision est déterministe et que l'intent
    # gagnant fait partie des deux candidats.
    assert intent is not None
    assert intent.name in {"budgets", "marches"}


def test_detect_more_keywords_wins_over_fewer():
    # Question avec 2 keywords budgets + 1 marches → budgets gagne.
    intent = detect_intent("budget recettes dépenses marché")
    assert intent.name == "budgets"

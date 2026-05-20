"""
Tests du générateur de réponse (app/nlp/responder.py).

summarize est une fonction pure : (Intent, Entities, data) → str.
On crée des Entities et Intent à la volée pour exercer les branches.
"""

from __future__ import annotations

from app.nlp.entities import Entities
from app.nlp.intents import INTENTS
from app.nlp.responder import summarize, _context_phrase


# Récupère un Intent existant pour ne pas avoir à en fabriquer un faux.
BUDGETS = next(i for i in INTENTS if i.name == "budgets")
MARCHES = next(i for i in INTENTS if i.name == "marches")


# ---------------------------------------------------------------------------
# _context_phrase — "pour X en YYYY" / "dans le département XX"
# ---------------------------------------------------------------------------

def test_context_phrase_commune_only():
    # Sans commune réelle, on ne peut pas tester le chemin "pour <nom>"
    # complet ici (Commune est un modèle SQLAlchemy). On vérifie au moins
    # le fallback département.
    ents = Entities(departement="69")
    assert _context_phrase(ents) == "dans le département 69"


def test_context_phrase_annee_only():
    ents = Entities(annee=2022)
    assert _context_phrase(ents) == "en 2022"


def test_context_phrase_empty():
    assert _context_phrase(Entities()) == ""


def test_context_phrase_dept_and_annee():
    ents = Entities(departement="13", annee=2023)
    assert _context_phrase(ents) == "dans le département 13 en 2023"


# ---------------------------------------------------------------------------
# summarize — chemins par type de `data`
# ---------------------------------------------------------------------------

def test_summarize_list_with_results():
    msg = summarize(BUDGETS, Entities(annee=2022), [{"x": 1}, {"x": 2}, {"x": 3}])
    assert "3 résultats" in msg
    assert "2022" in msg


def test_summarize_singular_result():
    # 1 résultat → "résultat" sans 's'.
    msg = summarize(MARCHES, Entities(), [{"x": 1}])
    assert "1 résultat" in msg
    assert "résultats" not in msg


def test_summarize_empty_list():
    msg = summarize(BUDGETS, Entities(annee=2022), [])
    assert "Aucun résultat" in msg


def test_summarize_dict_with_total():
    # search_datasets renvoie un dict {total, data, ...}.
    msg = summarize(MARCHES, Entities(), {"total": 42, "data": []})
    assert "42" in msg


def test_summarize_none():
    msg = summarize(BUDGETS, Entities(), None)
    assert "Aucune donnée" in msg


def test_summarize_includes_intent_description():
    msg = summarize(BUDGETS, Entities(annee=2022), [{"x": 1}])
    # La description de l'intent ("Budgets communaux…") apparaît dans la phrase.
    assert "budgets" in msg.lower()

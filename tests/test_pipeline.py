"""
Tests d'intégration de la pipeline NLP (app/nlp/pipeline.py).

On mocke `extract` (pour éviter de monter une DB pour le PhraseMatcher) et
le `fetch` de l'intent ciblé (pour ne pas appeler les vrais scrapers).
On valide la forme du dict retourné et la propagation correcte des erreurs.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.nlp import pipeline as pipeline_mod
from app.nlp.entities import Entities
from app.nlp.intents import INTENTS


# ---------------------------------------------------------------------------
# Helpers : monkey-patcher extract et detect_intent pour s'affranchir de la DB
# et des appels aux scrapers data.gouv.
# ---------------------------------------------------------------------------

def _patch_extract(monkeypatch, entities: Entities) -> None:
    """Force pipeline.extract à renvoyer les Entities passées (au lieu d'aller en DB)."""
    monkeypatch.setattr(pipeline_mod, "extract", lambda _text: entities)


def _patch_intent_fetch(monkeypatch, intent_name: str, fetch_fn) -> None:
    """
    Intent est un dataclass `frozen=True` : on ne peut pas réassigner `fetch`
    directement. À la place, on fabrique un clone via dataclasses.replace
    (autorisé même sur les frozen dataclasses) et on patche detect_intent
    pour qu'il renvoie ce clone.
    """
    original = next(i for i in INTENTS if i.name == intent_name)
    fake = replace(original, fetch=fetch_fn)
    monkeypatch.setattr(pipeline_mod, "detect_intent", lambda _text: fake)


# ---------------------------------------------------------------------------
# Cas 1 : aucune intention détectée
# ---------------------------------------------------------------------------

def test_answer_no_intent(monkeypatch):
    _patch_extract(monkeypatch, Entities())
    result = pipeline_mod.answer_question("bonjour")

    assert result["intent"] is None
    assert result["data"] is None
    assert result["params"] is None
    assert result["error"] is None
    # Le message d'aide guide vers les mots-clés.
    assert "budget" in result["answer"].lower()


# ---------------------------------------------------------------------------
# Cas 2 : chemin nominal — intent + fetch OK
# ---------------------------------------------------------------------------

def test_answer_happy_path(monkeypatch):
    _patch_extract(monkeypatch, Entities(annee=2022))

    fake_data = [{"id": 1}, {"id": 2}]
    # On capture les kwargs réellement passés au fetch pour vérifier le mapping.
    captured: dict = {}

    def fake_fetch(**kwargs):
        captured.update(kwargs)
        return fake_data

    _patch_intent_fetch(monkeypatch, "budgets", fake_fetch)
    result = pipeline_mod.answer_question("budget en 2022")

    assert result["intent"] == "budgets"
    assert result["data"] == fake_data
    assert result["error"] is None
    assert "2 résultats" in result["answer"]
    # Les kwargs construits par _kw_budgets contiennent bien l'année extraite.
    assert captured.get("annee") == 2022


# ---------------------------------------------------------------------------
# Cas 3 : remontée propre d'une erreur du scraper
# ---------------------------------------------------------------------------

def test_answer_fetch_error(monkeypatch):
    _patch_extract(monkeypatch, Entities())

    def boom(**_kwargs):
        raise RuntimeError("source HS")

    _patch_intent_fetch(monkeypatch, "marches", boom)
    result = pipeline_mod.answer_question("marchés publics")

    assert result["intent"] == "marches"
    assert result["error"] == "source HS"
    assert result["data"] is None
    # La phrase de réponse mentionne l'échec sans cacher la cause.
    assert "échoué" in result["answer"]


# ---------------------------------------------------------------------------
# Cas 4 : forme du dict — clés stables
# ---------------------------------------------------------------------------

def test_answer_dict_shape(monkeypatch):
    _patch_extract(monkeypatch, Entities())
    _patch_intent_fetch(monkeypatch, "budgets", lambda **_: [])

    result = pipeline_mod.answer_question("budget")
    # Le contrat de l'API : ces clés sont toujours présentes.
    assert set(result) == {"question", "intent", "entities", "params", "answer", "data", "error"}
    assert set(result["entities"]) >= {"commune", "code_insee", "annee", "departement", "compte_prefix"}


# ---------------------------------------------------------------------------
# Cas 5 : question vide / espaces uniquement
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question", ["", "   ", "\t\n"])
def test_answer_empty_question_routes_to_help(monkeypatch, question):
    # Aucun mot-clé → pas d'intent → message d'aide.
    _patch_extract(monkeypatch, Entities())
    result = pipeline_mod.answer_question(question)
    assert result["intent"] is None
    assert result["data"] is None

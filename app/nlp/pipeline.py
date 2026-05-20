"""
Orchestrateur de la pipeline NLP.

Une "pipeline" en NLP, c'est l'enchaînement d'étapes qui transforme un texte
brut en une action exécutable. Ici, l'enchaînement est :

    question (str)
        │
        ├──► detect_intent()         ──► quel jeu de données ?
        │
        ├──► extract()               ──► quelle commune, année, etc. ?
        │
        ├──► build_kwargs()          ──► quels paramètres pour le scraper ?
        │
        ├──► fetch()                 ──► appel data.gouv.fr / DGFiP
        │
        └──► summarize()             ──► phrase de réponse

C'est un point d'entrée volontairement simple : tout le code spécifique au
domaine (mots-clés, mapping params) vit dans intents.py et entities.py.
"""

from __future__ import annotations

from typing import Any

from app.nlp.entities import extract
from app.nlp.intents import detect_intent
from app.nlp.responder import summarize


def answer_question(question: str) -> dict[str, Any]:
    """
    Traite une question en français et retourne un dict structuré :
        {
            "question":   str,         # question d'origine
            "intent":     str | None,  # intent détecté (ou None si rien trouvé)
            "entities":   dict,        # entités extraites (commune, année, ...)
            "params":     dict,        # kwargs effectivement passés au scraper
            "answer":     str,         # phrase de réponse en langage naturel
            "data":       list | None, # résultat brut du scraper
            "error":      str | None,  # message d'erreur éventuel
        }
    """
    intent = detect_intent(question)
    entities = extract(question)

    base = {
        "question": question,
        "intent": intent.name if intent else None,
        "entities": {
            "commune": entities.commune.nom if entities.commune else None,
            "code_insee": entities.commune.code_insee if entities.commune else None,
            "annee": entities.annee,
            "departement": entities.departement,
            "compte_prefix": entities.compte_prefix,
        },
        "params": None,
        "answer": None,
        "data": None,
        "error": None,
    }

    if intent is None:
        base["answer"] = (
            "Je n'ai pas compris de quel jeu de données il s'agit. "
            "Essayez avec un mot-clé comme « budget », « subvention », "
            "« marché », « culture », « démographie » ou « revenus »."
        )
        return base

    params = intent.build_kwargs(entities)
    base["params"] = params

    try:
        data = intent.fetch(**params)
    except Exception as exc:  # remontée propre à l'appelant — l'API loggera
        base["error"] = str(exc)
        base["answer"] = f"L'appel à la source de données a échoué : {exc}"
        return base

    base["data"] = data
    base["answer"] = summarize(intent, entities, data)
    return base

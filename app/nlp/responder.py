"""
Formatage de la réponse en langage naturel.

Étape finale d'une pipeline NLP : "Natural Language Generation" (NLG). Ici
on reste sur du template-based — des phrases à trous — parce que les
réponses sont des résumés courts et déterministes. Un LLM serait surdimensionné.
"""

from __future__ import annotations

from typing import Any

from app.nlp.entities import Entities
from app.nlp.intents import Intent


def _context_phrase(entities: Entities) -> str:
    """Construit la portion « pour Lyon en 2022 » à partir des entités."""
    parts: list[str] = []
    if entities.commune:
        parts.append(f"pour {entities.commune.nom}")
    elif entities.departement:
        parts.append(f"dans le département {entities.departement}")
    if entities.annee:
        parts.append(f"en {entities.annee}")
    return " ".join(parts).strip()


def summarize(intent: Intent, entities: Entities, data: Any) -> str:
    """
    Produit une phrase courte décrivant le résultat. `data` peut être :
      - une liste de records (cas général des scrapers data.gouv) ;
      - un dict (cas search_datasets, etc.) ;
      - None.
    """
    context = _context_phrase(entities)
    where = f" {context}" if context else ""

    if data is None:
        return f"Aucune donnée renvoyée pour {intent.description.lower()}{where}."

    if isinstance(data, list):
        n = len(data)
        if n == 0:
            return f"Aucun résultat trouvé pour {intent.description.lower()}{where}."
        return (
            f"J'ai trouvé {n} résultat{'s' if n > 1 else ''} "
            f"sur {intent.description.lower()}{where}."
        )

    if isinstance(data, dict):
        total = data.get("total") or data.get("count") or len(data)
        return (
            f"Réponse reçue pour {intent.description.lower()}{where} "
            f"({total} élément(s))."
        )

    return f"Réponse reçue pour {intent.description.lower()}{where}."

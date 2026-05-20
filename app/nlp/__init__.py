"""Pipeline NLP : question en français → appel des scrapers data.gouv.fr."""

from app.nlp.pipeline import answer_question

__all__ = ["answer_question"]

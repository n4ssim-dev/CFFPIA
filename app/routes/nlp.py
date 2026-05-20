"""Endpoint NLP : POST /api/ask  { "question": "..." }."""

from flask import Blueprint, jsonify, request

from app.nlp import answer_question

bp_nlp = Blueprint("nlp", __name__, url_prefix="/api")


@bp_nlp.post("/ask")
def ask():
    """
    Reçoit une question en français et retourne l'intent détecté, les entités
    extraites, le résultat brut du scraper et une phrase de réponse.

    Exemple :
        curl -X POST http://localhost:5000/api/ask \\
             -H "Content-Type: application/json" \\
             -d '{"question": "Quel est le budget de Lyon en 2022 ?"}'
    """
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Le champ 'question' est requis."}), 400

    result = answer_question(question)
    status = 502 if result.get("error") else 200
    return jsonify(result), status

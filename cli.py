"""
Terminal interactif pour interroger la pipeline NLP de FranceFPIA.

Style inspiré de Claude Code : bordures arrondies, palette ambrée, prompt « ❯ ».
Pas de dépendance supplémentaire (juste ANSI + `requests` déjà présent).

Usage
-----
1. Lancer l'API Flask dans un autre terminal :
       flask run
2. Lancer le CLI ici :
       python cli.py
3. Poser une question en français. Exemples :
       Quel est le budget de Lyon en 2022 ?
       Charges de personnel à Lille en 2023
       Marchés publics à Paris
   Tapez /quit, /exit ou :q pour sortir.
"""

from __future__ import annotations

import re
import sys
import textwrap

import requests

# Regex pour retirer les séquences ANSI (\033[...m) afin de mesurer la
# largeur réellement affichée à l'écran (les codes couleur sont invisibles).
_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

# ---------------------------------------------------------------------------
# Codes ANSI (palette 256 couleurs)
# ---------------------------------------------------------------------------
# Le terminal interprète \033[38;5;<N>m comme « foreground couleur N ».
# \033[0m réinitialise tout (couleur + bold). Pas de lib externe nécessaire.

R = "\033[0m"               # reset
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"

# Palette : amber / gris / vert doux, dans le ton de Claude Code.
AMBER = "\033[38;5;208m"
AMBER_DIM = "\033[38;5;172m"
GRAY = "\033[38;5;244m"
LIGHT = "\033[38;5;252m"
GREEN = "\033[38;5;114m"
RED = "\033[38;5;203m"

API_URL = "http://127.0.0.1:5000/api/ask"
BOX_WIDTH = 60  # largeur intérieure du cadre, en caractères visibles


# ---------------------------------------------------------------------------
# Rendu
# ---------------------------------------------------------------------------

def _visible_len(text: str) -> int:
    """Longueur affichée à l'écran : on enlève les séquences ANSI invisibles."""
    return len(_ANSI_RE.sub("", text))


def _box_line(text: str) -> str:
    """Ligne du cadre : ljust à BOX_WIDTH en ignorant les codes ANSI."""
    pad = " " * max(0, BOX_WIDTH - _visible_len(text))
    return f"{AMBER}│{R} {text}{pad} {AMBER}│{R}"


def banner() -> None:
    rule = "─" * (BOX_WIDTH + 2)
    print()
    print(f"{AMBER}╭{rule}╮{R}")
    print(_box_line(f"{BOLD}FranceFPIA{R}  {DIM}— interrogation NLP des finances locales{R}"))
    print(_box_line(""))
    print(_box_line(f"{DIM}Tapez une question en français. Exemples :{R}"))
    print(_box_line(f"{GRAY}  · Budget de Lyon en 2022 ?{R}"))
    print(_box_line(f"{GRAY}  · Charges de personnel à Lille en 2023{R}"))
    print(_box_line(f"{GRAY}  · Marchés publics à Paris{R}"))
    print(_box_line(""))
    print(_box_line(f"{DIM}/quit · /exit · :q pour sortir{R}"))
    print(f"{AMBER}╰{rule}╯{R}")
    print()


def _chip(label: str, value: str) -> str:
    return f"{GRAY}{label}{R}{LIGHT}{value}{R}"


def render(result: dict) -> None:
    """Met en forme la réponse de /api/ask : chips d'entités puis phrase."""
    intent = result.get("intent")
    ents = result.get("entities", {})

    chips: list[str] = [_chip("intent=", intent or "—")]
    if ents.get("commune"):
        chips.append(_chip("commune=", ents["commune"]))
    if ents.get("annee"):
        chips.append(_chip("année=", str(ents["annee"])))
    if ents.get("departement"):
        chips.append(_chip("dépt=", ents["departement"]))
    if ents.get("compte_prefix"):
        chips.append(_chip("compte=", ents["compte_prefix"]))
    print(f"  {GRAY}·{R} " + f"  {GRAY}·{R} ".join(chips))

    answer = result.get("answer") or "(réponse vide)"
    for line in textwrap.wrap(answer, width=72) or [""]:
        print(f"  {GREEN}▌{R} {LIGHT}{line}{R}")

    if result.get("error"):
        print(f"  {RED}× erreur : {result['error']}{R}")

    data = result.get("data")
    if isinstance(data, list):
        print(f"  {DIM}{len(data)} enregistrement(s) bruts disponibles dans `data`.{R}")
    elif isinstance(data, dict):
        total = data.get("total") or data.get("count")
        if total is not None:
            print(f"  {DIM}{total} élément(s) renvoyés par la source.{R}")
    print()


# ---------------------------------------------------------------------------
# Boucle principale
# ---------------------------------------------------------------------------

def ask(question: str) -> dict | None:
    """POST /api/ask. Retourne le dict de réponse, ou None si l'API est down."""
    try:
        resp = requests.post(API_URL, json={"question": question}, timeout=30)
    except requests.ConnectionError:
        print(
            f"  {RED}× API injoignable à {API_URL}.{R}\n"
            f"  {DIM}Lancez `flask run` dans un autre terminal puis réessayez.{R}\n"
        )
        return None
    except requests.Timeout:
        print(f"  {RED}× Timeout en attendant la réponse de l'API.{R}\n")
        return None

    try:
        payload = resp.json()
    except ValueError:
        print(f"  {RED}× Réponse non-JSON ({resp.status_code}) : {resp.text[:200]}{R}\n")
        return None

    if resp.status_code >= 400 and not payload.get("answer"):
        print(f"  {RED}× HTTP {resp.status_code} : {payload.get('error', resp.text)}{R}\n")
        return None

    return payload


def main() -> int:
    banner()
    try:
        while True:
            try:
                question = input(f"{AMBER}❯{R} ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not question:
                continue
            if question.lower() in ("/quit", "/exit", ":q", "quit", "exit"):
                break

            result = ask(question)
            if result is not None:
                render(result)
    finally:
        print(f"{AMBER_DIM}au revoir.{R}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Tests des helpers de présentation du CLI (cli.py).

cli.py n'est pas un package — il est importé via le chemin racine ajouté
par conftest.py. On teste les fonctions pures de mise en forme : mesure
de largeur visible (en ignorant les codes ANSI) et alignement du cadre.
"""

from __future__ import annotations

import cli


# ---------------------------------------------------------------------------
# _visible_len — longueur affichée à l'écran (codes ANSI exclus)
# ---------------------------------------------------------------------------

def test_visible_len_plain():
    assert cli._visible_len("hello") == 5


def test_visible_len_strips_color_code():
    # "\033[38;5;208mhello\033[0m" → seules "hello" comptent à l'écran.
    colored = f"{cli.AMBER}hello{cli.R}"
    assert cli._visible_len(colored) == 5


def test_visible_len_strips_bold_and_dim():
    assert cli._visible_len(f"{cli.BOLD}{cli.DIM}txt{cli.R}") == 3


def test_visible_len_empty():
    assert cli._visible_len("") == 0


def test_visible_len_only_ansi():
    # Que des codes invisibles → longueur affichée = 0.
    assert cli._visible_len(f"{cli.AMBER}{cli.R}") == 0


# ---------------------------------------------------------------------------
# _box_line — padding correct quel que soit le contenu coloré
# ---------------------------------------------------------------------------

def test_box_line_pads_to_box_width():
    # La ligne produite doit contenir BOX_WIDTH caractères VISIBLES entre les bordures.
    line = cli._box_line("abc")
    # On retire les bordures et les espaces autour, puis on compte la zone interne.
    visible = cli._ANSI_RE.sub("", line)
    # Format attendu : "│ <contenu padé> │"
    assert visible.startswith("│ ")
    assert visible.endswith(" │")
    inner = visible[2:-2]  # entre "│ " et " │"
    assert len(inner) == cli.BOX_WIDTH


def test_box_line_with_ansi_keeps_alignment():
    # Le contenu coloré ne doit PAS décaler la bordure droite.
    plain = cli._box_line("hello")
    colored = cli._box_line(f"{cli.AMBER}hello{cli.R}")
    # Une fois les codes ANSI retirés, les deux lignes doivent avoir la même longueur.
    assert cli._visible_len(plain) == cli._visible_len(colored)


def test_box_line_truncates_negative_pad():
    # Si le texte est plus long que BOX_WIDTH, pas de pad négatif (max 0).
    long_text = "x" * (cli.BOX_WIDTH + 10)
    line = cli._box_line(long_text)
    # On ne crashe pas, et la ligne contient toujours les bordures.
    visible = cli._ANSI_RE.sub("", line)
    assert visible.startswith("│ ")
    assert visible.endswith(" │")

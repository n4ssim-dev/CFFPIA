"""
Configuration pytest commune à tous les tests.

pytest exécute ce fichier avant la collecte des tests. On l'utilise pour
ajouter la racine du projet au PYTHONPATH (utile pour importer `cli.py`
qui est à la racine, pas dans un package).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

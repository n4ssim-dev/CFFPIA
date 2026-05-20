from app import db  # noqa: F401

# Import de tous les modèles pour que Flask-Migrate les détecte via l'inspection de metadata
from app.models.referentiel import Commune, Departement  # noqa: F401
from app.models.finance import (  # noqa: F401
    BalanceComptableCommune,
    BudgetCommune,
    DepenseCulturelle,
    DonneesDemographiquesCommune,
    IndicateurRevenuCommune,
    MarchePublic,
    SubventionAssociation,
)
from app.models.journal import Ingestion  # noqa: F401

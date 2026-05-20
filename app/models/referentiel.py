from app import db


class Departement(db.Model):
    __tablename__ = "departements"

    # Code officiel INSEE : '01'–'95', '2A', '2B', '971'–'976'
    code = db.Column(db.String(3), primary_key=True)
    libelle = db.Column(db.String(100), nullable=False)

    communes = db.relationship("Commune", back_populates="departement", lazy="dynamic")


class Commune(db.Model):
    __tablename__ = "communes"

    # Code INSEE 5 caractères (ex: '33063', '2A001')
    code_insee = db.Column(db.String(5), primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    siren = db.Column(db.String(9))
    code_departement = db.Column(
        db.String(3), db.ForeignKey("departements.code"), nullable=False, index=True
    )

    departement = db.relationship("Departement", back_populates="communes")
    depenses_culturelles = db.relationship(
        "DepenseCulturelle", back_populates="commune", lazy="dynamic"
    )
    budgets = db.relationship("BudgetCommune", back_populates="commune", lazy="dynamic")
    subventions = db.relationship(
        "SubventionAssociation", back_populates="commune", lazy="dynamic"
    )
    marches = db.relationship("MarchePublic", back_populates="commune", lazy="dynamic")
    balances_comptables = db.relationship(
        "BalanceComptableCommune", back_populates="commune", lazy="dynamic"
    )
    donnees_demographiques = db.relationship(
        "DonneesDemographiquesCommune", back_populates="commune", lazy="dynamic"
    )
    indicateurs_revenus = db.relationship(
        "IndicateurRevenuCommune", back_populates="commune", lazy="dynamic"
    )

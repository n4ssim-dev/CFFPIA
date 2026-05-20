from datetime import datetime

from app import db


class DepenseCulturelle(db.Model):
    """
    Dépenses culturelles annuelles par commune.
    Source : Ministère de la Culture — data.gouv.fr.
    Déduplication : UNIQUE(code_insee, annee).
    """

    __tablename__ = "depenses_culturelles"
    __table_args__ = (
        db.UniqueConstraint("code_insee", "annee", name="uq_dep_cult_commune_annee"),
    )

    id = db.Column(db.Integer, primary_key=True)
    code_insee = db.Column(
        db.String(5), db.ForeignKey("communes.code_insee"), nullable=False, index=True
    )
    annee = db.Column(db.SmallInteger, nullable=False)

    # Montants en milliers d'euros
    depenses_totales_k_eur = db.Column(db.Integer)
    depenses_fonctionnement_k_eur = db.Column(db.Integer)
    depenses_investissement_k_eur = db.Column(db.Integer)

    # Ratios par habitant (euros)
    depenses_totales_eur_par_hab = db.Column(db.Integer)
    depenses_fonctionnement_eur_par_hab = db.Column(db.Integer)
    depenses_investissement_eur_par_hab = db.Column(db.Integer)

    # Part des dépenses culturelles dans le budget total (%)
    part_totale_pct = db.Column(db.Numeric(5, 2))
    part_fonctionnement_pct = db.Column(db.Numeric(5, 2))
    part_investissement_pct = db.Column(db.Numeric(5, 2))

    population = db.Column(db.Integer)
    source = db.Column(db.String(100), nullable=False, default="ministere-culture")
    ingere_le = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    commune = db.relationship("Commune", back_populates="depenses_culturelles")


class BudgetCommune(db.Model):
    """
    Budget annuel d'une commune : recettes, dépenses, épargne brute, dette.
    Source : DGFiP — Comptes individuels des communes (data.gouv.fr).
    Déduplication : UNIQUE(code_insee, annee).
    """

    __tablename__ = "budgets_communes"
    __table_args__ = (
        db.UniqueConstraint("code_insee", "annee", name="uq_budget_commune_annee"),
    )

    id = db.Column(db.Integer, primary_key=True)
    code_insee = db.Column(
        db.String(5), db.ForeignKey("communes.code_insee"), nullable=False, index=True
    )
    annee = db.Column(db.SmallInteger, nullable=False)

    # Fonctionnement (en milliers d'euros)
    recettes_fonctionnement_k_eur = db.Column(db.Integer)
    depenses_fonctionnement_k_eur = db.Column(db.Integer)

    # Investissement (en milliers d'euros)
    recettes_investissement_k_eur = db.Column(db.Integer)
    depenses_investissement_k_eur = db.Column(db.Integer)

    # Indicateurs synthétiques
    epargne_brute_k_eur = db.Column(db.Integer)   # recettes fonct. - dépenses fonct.
    encours_dette_k_eur = db.Column(db.Integer)    # dette au 31/12

    # Ratios par habitant (euros)
    depenses_totales_eur_par_hab = db.Column(db.Integer)
    recettes_totales_eur_par_hab = db.Column(db.Integer)

    population = db.Column(db.Integer)
    source = db.Column(db.String(100), nullable=False, default="dgfip-comptes-communes")
    ingere_le = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    commune = db.relationship("Commune", back_populates="budgets")


class SubventionAssociation(db.Model):
    """
    Subventions versées par les collectivités locales aux associations.
    Source : data.gouv.fr — subventions-versees-par-les-collectivites-territoriales.
    Déduplication : UNIQUE(code_insee, nom_beneficiaire, annee).
    """

    __tablename__ = "subventions_associations"
    __table_args__ = (
        db.UniqueConstraint(
            "code_insee", "nom_beneficiaire", "annee",
            name="uq_subv_assoc_commune_nom_annee",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    code_insee = db.Column(
        db.String(5), db.ForeignKey("communes.code_insee"), nullable=False, index=True
    )
    annee = db.Column(db.SmallInteger, nullable=False)

    nom_beneficiaire = db.Column(db.String(300), nullable=False)
    objet = db.Column(db.Text)
    montant_eur = db.Column(db.Numeric(14, 2))

    source = db.Column(db.String(100), nullable=False, default="data.gouv.fr-subventions")
    ingere_le = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    commune = db.relationship("Commune", back_populates="subventions")


class DonneesDemographiquesCommune(db.Model):
    """
    Structure démographique par commune et par tranche d'âge.
    Source : INSEE — Recensement de la Population (RP), fichier Communes.
    Déduplication : UNIQUE(code_insee, annee).
    """

    __tablename__ = "donnees_demographiques_communes"
    __table_args__ = (
        db.UniqueConstraint("code_insee", "annee", name="uq_demog_commune_annee"),
    )

    id = db.Column(db.Integer, primary_key=True)
    code_insee = db.Column(
        db.String(5), db.ForeignKey("communes.code_insee"), nullable=False, index=True
    )
    annee = db.Column(db.SmallInteger, nullable=False)

    population_totale = db.Column(db.Integer)

    # Tranches d'âge (valeurs arrondies issues du RP)
    pop_0_14_ans = db.Column(db.Integer)
    pop_15_29_ans = db.Column(db.Integer)
    pop_30_44_ans = db.Column(db.Integer)
    pop_45_59_ans = db.Column(db.Integer)
    pop_60_74_ans = db.Column(db.Integer)
    pop_75_89_ans = db.Column(db.Integer)
    pop_90_ans_plus = db.Column(db.Integer)

    # Parts calculées (%)
    part_moins_15_pct = db.Column(db.Numeric(5, 2))
    part_65_ans_plus_pct = db.Column(db.Numeric(5, 2))
    part_15_64_ans_pct = db.Column(db.Numeric(5, 2))

    source = db.Column(db.String(100), nullable=False, default="insee-rp")
    ingere_le = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    commune = db.relationship("Commune", back_populates="donnees_demographiques")


class IndicateurRevenuCommune(db.Model):
    """
    Revenus et pauvreté par commune (Filosofi — Fichier localisé social et fiscal).
    Source : INSEE — Filosofi, fichier Communes.
    Déduplication : UNIQUE(code_insee, annee).
    's' (secret statistique) → NULL (communes < 2000 ménages fiscaux).
    """

    __tablename__ = "indicateurs_revenus_communes"
    __table_args__ = (
        db.UniqueConstraint("code_insee", "annee", name="uq_revenus_commune_annee"),
    )

    id = db.Column(db.Integer, primary_key=True)
    code_insee = db.Column(
        db.String(5), db.ForeignKey("communes.code_insee"), nullable=False, index=True
    )
    annee = db.Column(db.SmallInteger, nullable=False)

    nb_menages_fiscaux = db.Column(db.Integer)
    revenu_median_uc = db.Column(db.Integer)        # €/an par unité de consommation
    taux_pauvrete_pct = db.Column(db.Numeric(5, 2)) # % population sous 60% médiane nationale
    part_menages_imposes_pct = db.Column(db.Numeric(5, 2))
    d1_revenu = db.Column(db.Integer)               # 1er décile (€)
    d9_revenu = db.Column(db.Integer)               # 9ème décile (€)
    rapport_interdecile = db.Column(db.Numeric(6, 2))  # D9/D1

    source = db.Column(db.String(100), nullable=False, default="insee-filosofi")
    ingere_le = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    commune = db.relationship("Commune", back_populates="indicateurs_revenus")


class BalanceComptableCommune(db.Model):
    """
    Balance comptable annuelle d'une commune par compte (poste de dépense/recette).
    Source : DGFiP via data.economie.gouv.fr — Balances comptables des communes.
    Filtre appliqué : budget principal (cbudg=1), categ=Commune.
    Déduplication : UNIQUE(siren, annee, compte).
    """

    __tablename__ = "balances_comptables_communes"
    __table_args__ = (
        db.UniqueConstraint("siren", "annee", "compte", name="uq_balance_siren_annee_compte"),
    )

    id = db.Column(db.Integer, primary_key=True)
    code_insee = db.Column(
        db.String(5), db.ForeignKey("communes.code_insee"), nullable=True, index=True
    )
    siren = db.Column(db.String(9), nullable=False, index=True)
    annee = db.Column(db.SmallInteger, nullable=False, index=True)

    compte = db.Column(db.String(15), nullable=False, index=True)  # ex: '6411', '73111'
    nom_commune = db.Column(db.String(200))

    # Mouvements nets réels (en euros)
    obnetdeb = db.Column(db.Numeric(16, 2))  # dépenses réalisées
    obnetcre = db.Column(db.Numeric(16, 2))  # recettes réalisées

    # Soldes finaux
    sd = db.Column(db.Numeric(16, 2))  # solde débiteur
    sc = db.Column(db.Numeric(16, 2))  # solde créditeur

    source = db.Column(db.String(100), nullable=False, default="dgfip-balances-comptables")
    ingere_le = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    commune = db.relationship("Commune", back_populates="balances_comptables")


class MarchePublic(db.Model):
    """
    Marchés publics attribués par les collectivités locales.
    Source : DECP — Données essentielles de la commande publique (data.gouv.fr).
    Déduplication : UNIQUE(uid).
    """

    __tablename__ = "marches_publics"
    __table_args__ = (
        db.UniqueConstraint("uid", name="uq_marche_uid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(100), nullable=False, index=True)

    # Acheteur (collectivité qui passe le marché)
    acheteur_siret = db.Column(db.String(14))
    acheteur_nom = db.Column(db.String(300))
    code_insee = db.Column(
        db.String(5), db.ForeignKey("communes.code_insee"), nullable=True, index=True
    )

    # Marché
    intitule = db.Column(db.Text)
    nature = db.Column(db.String(50))       # Marché / Contrat de concession
    procedure = db.Column(db.String(100))   # Appel d'offres ouvert, MAPA, etc.
    montant_eur = db.Column(db.Numeric(16, 2))
    date_attribution = db.Column(db.Date)
    annee = db.Column(db.SmallInteger, index=True)

    source = db.Column(db.String(100), nullable=False, default="decp-data.gouv.fr")
    ingere_le = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    commune = db.relationship("Commune", back_populates="marches")

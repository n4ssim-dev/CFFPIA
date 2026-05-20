"""replace epci et fiscalite par budgets, subventions et marches

Revision ID: a1f3c82e9b04
Revises: 8cd5b420d279
Create Date: 2026-05-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1f3c82e9b04'
down_revision = '8cd5b420d279'
branch_labels = None
depends_on = None


def upgrade():
    # Suppression des tables fiscalité / EPCI
    op.drop_table('deliberations_fiscalite_epci')
    op.drop_table('deliberations_fiscalite_commune')
    op.drop_table('epci')

    # Suppression de la colonne FK deliberations sur communes
    with op.batch_alter_table('communes', schema=None) as batch_op:
        pass  # la relation était uniquement côté ORM, pas de colonne FK à supprimer

    # -----------------------------------------------------------------------
    # Budgets annuels des communes (DGFiP)
    # -----------------------------------------------------------------------
    op.create_table(
        'budgets_communes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code_insee', sa.String(length=5), nullable=False),
        sa.Column('annee', sa.SmallInteger(), nullable=False),
        sa.Column('recettes_fonctionnement_k_eur', sa.Integer(), nullable=True),
        sa.Column('depenses_fonctionnement_k_eur', sa.Integer(), nullable=True),
        sa.Column('recettes_investissement_k_eur', sa.Integer(), nullable=True),
        sa.Column('depenses_investissement_k_eur', sa.Integer(), nullable=True),
        sa.Column('epargne_brute_k_eur', sa.Integer(), nullable=True),
        sa.Column('encours_dette_k_eur', sa.Integer(), nullable=True),
        sa.Column('depenses_totales_eur_par_hab', sa.Integer(), nullable=True),
        sa.Column('recettes_totales_eur_par_hab', sa.Integer(), nullable=True),
        sa.Column('population', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('ingere_le', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['code_insee'], ['communes.code_insee']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code_insee', 'annee', name='uq_budget_commune_annee'),
    )
    with op.batch_alter_table('budgets_communes', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_budgets_communes_code_insee'), ['code_insee'], unique=False
        )

    # -----------------------------------------------------------------------
    # Subventions aux associations
    # -----------------------------------------------------------------------
    op.create_table(
        'subventions_associations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code_insee', sa.String(length=5), nullable=False),
        sa.Column('annee', sa.SmallInteger(), nullable=False),
        sa.Column('nom_beneficiaire', sa.String(length=300), nullable=False),
        sa.Column('objet', sa.Text(), nullable=True),
        sa.Column('montant_eur', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('ingere_le', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['code_insee'], ['communes.code_insee']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'code_insee', 'nom_beneficiaire', 'annee',
            name='uq_subv_assoc_commune_nom_annee',
        ),
    )
    with op.batch_alter_table('subventions_associations', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_subventions_associations_code_insee'), ['code_insee'], unique=False
        )

    # -----------------------------------------------------------------------
    # Marchés publics (DECP)
    # -----------------------------------------------------------------------
    op.create_table(
        'marches_publics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.String(length=100), nullable=False),
        sa.Column('acheteur_siret', sa.String(length=14), nullable=True),
        sa.Column('acheteur_nom', sa.String(length=300), nullable=True),
        sa.Column('code_insee', sa.String(length=5), nullable=True),
        sa.Column('intitule', sa.Text(), nullable=True),
        sa.Column('nature', sa.String(length=50), nullable=True),
        sa.Column('procedure', sa.String(length=100), nullable=True),
        sa.Column('montant_eur', sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column('date_attribution', sa.Date(), nullable=True),
        sa.Column('annee', sa.SmallInteger(), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('ingere_le', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['code_insee'], ['communes.code_insee']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uid', name='uq_marche_uid'),
    )
    with op.batch_alter_table('marches_publics', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_marches_publics_uid'), ['uid'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_marches_publics_code_insee'), ['code_insee'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_marches_publics_annee'), ['annee'], unique=False
        )


def downgrade():
    op.drop_table('marches_publics')
    op.drop_table('subventions_associations')
    op.drop_table('budgets_communes')

    # Recréation table EPCI
    op.create_table(
        'epci',
        sa.Column('siren', sa.String(length=9), nullable=False),
        sa.Column('libelle', sa.String(length=300), nullable=False),
        sa.Column('type_fiscalite', sa.String(length=10), nullable=True),
        sa.Column('code_departement', sa.String(length=3), nullable=False),
        sa.ForeignKeyConstraint(['code_departement'], ['departements.code']),
        sa.PrimaryKeyConstraint('siren'),
    )
    with op.batch_alter_table('epci', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_epci_code_departement'), ['code_departement'], unique=False
        )

    # Recréation tables fiscalité
    from sqlalchemy.dialects import postgresql
    op.create_table(
        'deliberations_fiscalite_commune',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code_depcom', sa.String(length=5), nullable=False),
        sa.Column('annee', sa.SmallInteger(), nullable=False),
        sa.Column('code_departement', sa.String(length=3), nullable=True),
        sa.Column('ind_tlv', sa.Boolean(), nullable=True),
        sa.Column('taux_zrc', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('taux_zrv', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('donnees', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('ingere_le', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['code_departement'], ['departements.code']),
        sa.ForeignKeyConstraint(['code_depcom'], ['communes.code_insee']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code_depcom', 'annee', name='uq_delib_fisc_com_annee'),
    )

    op.create_table(
        'deliberations_fiscalite_epci',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('siren_epci', sa.String(length=9), nullable=False),
        sa.Column('annee', sa.SmallInteger(), nullable=False),
        sa.Column('code_departement', sa.String(length=3), nullable=True),
        sa.Column('type_fiscalite', sa.String(length=10), nullable=True),
        sa.Column('taux_zrc', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('taux_zrv', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('donnees', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('ingere_le', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['code_departement'], ['departements.code']),
        sa.ForeignKeyConstraint(['siren_epci'], ['epci.siren']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('siren_epci', 'annee', name='uq_delib_fisc_epci_annee'),
    )

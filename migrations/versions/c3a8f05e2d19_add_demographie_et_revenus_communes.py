"""add donnees demographiques et indicateurs revenus communes

Revision ID: c3a8f05e2d19
Revises: b2e7d94f1c08
Create Date: 2026-05-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c3a8f05e2d19'
down_revision = 'b2e7d94f1c08'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'donnees_demographiques_communes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code_insee', sa.String(length=5), nullable=False),
        sa.Column('annee', sa.SmallInteger(), nullable=False),
        sa.Column('population_totale', sa.Integer(), nullable=True),
        sa.Column('pop_0_14_ans', sa.Integer(), nullable=True),
        sa.Column('pop_15_29_ans', sa.Integer(), nullable=True),
        sa.Column('pop_30_44_ans', sa.Integer(), nullable=True),
        sa.Column('pop_45_59_ans', sa.Integer(), nullable=True),
        sa.Column('pop_60_74_ans', sa.Integer(), nullable=True),
        sa.Column('pop_75_89_ans', sa.Integer(), nullable=True),
        sa.Column('pop_90_ans_plus', sa.Integer(), nullable=True),
        sa.Column('part_moins_15_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('part_65_ans_plus_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('part_15_64_ans_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('ingere_le', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['code_insee'], ['communes.code_insee']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code_insee', 'annee', name='uq_demog_commune_annee'),
    )
    with op.batch_alter_table('donnees_demographiques_communes', schema=None) as batch_op:
        batch_op.create_index('ix_donnees_demographiques_communes_code_insee', ['code_insee'], unique=False)

    op.create_table(
        'indicateurs_revenus_communes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code_insee', sa.String(length=5), nullable=False),
        sa.Column('annee', sa.SmallInteger(), nullable=False),
        sa.Column('nb_menages_fiscaux', sa.Integer(), nullable=True),
        sa.Column('revenu_median_uc', sa.Integer(), nullable=True),
        sa.Column('taux_pauvrete_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('part_menages_imposes_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('d1_revenu', sa.Integer(), nullable=True),
        sa.Column('d9_revenu', sa.Integer(), nullable=True),
        sa.Column('rapport_interdecile', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('ingere_le', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['code_insee'], ['communes.code_insee']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code_insee', 'annee', name='uq_revenus_commune_annee'),
    )
    with op.batch_alter_table('indicateurs_revenus_communes', schema=None) as batch_op:
        batch_op.create_index('ix_indicateurs_revenus_communes_code_insee', ['code_insee'], unique=False)


def downgrade():
    op.drop_table('indicateurs_revenus_communes')
    op.drop_table('donnees_demographiques_communes')

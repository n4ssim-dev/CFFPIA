"""add balances comptables communes

Revision ID: b2e7d94f1c08
Revises: a1f3c82e9b04
Create Date: 2026-05-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b2e7d94f1c08'
down_revision = 'a1f3c82e9b04'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'balances_comptables_communes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code_insee', sa.String(length=5), nullable=True),
        sa.Column('siren', sa.String(length=9), nullable=False),
        sa.Column('annee', sa.SmallInteger(), nullable=False),
        sa.Column('compte', sa.String(length=15), nullable=False),
        sa.Column('nom_commune', sa.String(length=200), nullable=True),
        sa.Column('obnetdeb', sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column('obnetcre', sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column('sd', sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column('sc', sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('ingere_le', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['code_insee'], ['communes.code_insee']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('siren', 'annee', 'compte', name='uq_balance_siren_annee_compte'),
    )
    with op.batch_alter_table('balances_comptables_communes', schema=None) as batch_op:
        batch_op.create_index('ix_balances_comptables_communes_code_insee', ['code_insee'], unique=False)
        batch_op.create_index('ix_balances_comptables_communes_siren', ['siren'], unique=False)
        batch_op.create_index('ix_balances_comptables_communes_annee', ['annee'], unique=False)
        batch_op.create_index('ix_balances_comptables_communes_compte', ['compte'], unique=False)


def downgrade():
    op.drop_table('balances_comptables_communes')

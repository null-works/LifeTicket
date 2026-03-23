"""Add resolution_notes and resolved_at to Ticket

Revision ID: 5ae7fef4f4ef
Revises: 
Create Date: 2026-03-23 11:44:17.250610

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5ae7fef4f4ef'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ticket', schema=None) as batch_op:
        batch_op.add_column(sa.Column('resolution_notes', sa.Text(), server_default='', nullable=True))
        batch_op.add_column(sa.Column('resolved_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('ticket', schema=None) as batch_op:
        batch_op.drop_column('resolved_at')
        batch_op.drop_column('resolution_notes')

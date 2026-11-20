"""Create the AgriFM database schema.

Revision ID: 0001_initial_schema
Revises:
"""
from alembic import op

from apps.api.models import metadata


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    metadata.drop_all(bind=op.get_bind(), checkfirst=True)

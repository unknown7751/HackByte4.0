"""rename trello_card_id to source_id and drop unique constraint

Revision ID: a2b3c4d5e6f7
Revises: 31a717b2606a
Create Date: 2026-04-04 00:30:00.000000
"""
from typing import Sequence, Union
from alembic import op

# revision identifiers
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "31a717b2606a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename column
    op.alter_column("accidents", "trello_card_id", new_column_name="source_id")
    # Drop the old unique constraint (name depends on auto-generated convention)
    # The unique index was auto-created; drop it and recreate as non-unique
    op.drop_index("ix_accidents_trello_card_id", table_name="accidents", if_exists=True)
    op.create_index("ix_accidents_source_id", "accidents", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_accidents_source_id", table_name="accidents", if_exists=True)
    op.alter_column("accidents", "source_id", new_column_name="trello_card_id")
    op.create_index("ix_accidents_trello_card_id", "accidents", ["trello_card_id"], unique=True)

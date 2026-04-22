"""create_loan_products_table

Revision ID: a1b2c3d4e5f6
Revises: b416ea9fae12
Create Date: 2026-04-22 04:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "3297b0b4ec8e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "loan_products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lender_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lenders.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False, default="standard"),
        sa.Column("min_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("max_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("min_installments", sa.Integer(), nullable=False),
        sa.Column("max_installments", sa.Integer(), nullable=False),
        sa.Column("annual_interest_rate", sa.Numeric(5, 4), nullable=False),
        sa.Column("example_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("example_monthly_payment", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_featured", sa.Boolean(), nullable=False, default=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, default=0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_loan_products_lender_id"), "loan_products", ["lender_id"])
    op.create_index(op.f("ix_loan_products_tier"), "loan_products", ["tier"])
    op.create_index(op.f("ix_loan_products_is_active"), "loan_products", ["is_active"])


def downgrade() -> None:
    op.drop_table("loan_products")

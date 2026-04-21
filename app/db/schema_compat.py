"""Centralized backward-compatible schema fixes for existing databases.

This module keeps startup schema reconciliation in one place to avoid
scattered ad-hoc ALTER TABLE statements across the codebase.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


# Keep these fixes idempotent (`IF NOT EXISTS`) and append-only.
SCHEMA_COMPAT_SQL: Sequence[str] = (
    """
    ALTER TABLE IF EXISTS users
    ADD COLUMN IF NOT EXISTS photo_url VARCHAR(500)
    """,
    """
    ALTER TABLE IF EXISTS lenders
    ADD COLUMN IF NOT EXISTS address_line VARCHAR(255)
    """,
    """
    ALTER TABLE IF EXISTS lenders
    ADD COLUMN IF NOT EXISTS photo_url VARCHAR(500)
    """,
    """
    ALTER TABLE IF EXISTS client_bank_accounts
    ADD COLUMN IF NOT EXISTS balance NUMERIC(15, 2) NOT NULL DEFAULT 0.00
    """,
    """
    ALTER TABLE IF EXISTS customer_documents
    ADD COLUMN IF NOT EXISTS bank_account_id UUID
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'fk_customer_documents_bank_account_id'
        ) THEN
            ALTER TABLE customer_documents
            ADD CONSTRAINT fk_customer_documents_bank_account_id
            FOREIGN KEY (bank_account_id)
            REFERENCES client_bank_accounts(id)
            ON DELETE SET NULL;
        END IF;
    END $$;
    """,
)


async def apply_schema_compat_fixes(conn: AsyncConnection) -> None:
    """Apply idempotent schema compatibility fixes for drifted environments."""
    for statement in SCHEMA_COMPAT_SQL:
        await conn.execute(text(statement))


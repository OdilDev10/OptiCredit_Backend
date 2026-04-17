#!/usr/bin/env python3
"""Alembic migration runner."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db.base import Base
from app.db.session import engine


async def init_db():
    """Initialize database with all models."""
    print("Initializing database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully!")


async def main():
    """Run migrations."""
    try:
        await init_db()
        print("\nSchema ready for models.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

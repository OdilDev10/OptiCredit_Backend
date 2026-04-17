"""Idempotent startup seed for essential development accounts."""

from __future__ import annotations

import logging

from sqlalchemy import select

# Ensure all ORM models are registered before querying.
from app.db import base as _base  # noqa: F401
from app.db.session import AsyncSessionFactory
from app.core.enums import AccountType, UserRole, UserStatus
from app.core.security import hash_password
from app.models.user import User

logger = logging.getLogger("app.seed")
logger.setLevel(logging.INFO)

TEST_USER_EMAIL = "odil.martinez@opticredit.app"
TEST_USER_PASSWORD = "Test@1234"


async def run_startup_seed() -> None:
    """Create/update required dev user without duplicating records."""
    async with AsyncSessionFactory() as session:
        stmt = select(User).where(User.email == TEST_USER_EMAIL)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                first_name="Odil",
                last_name="Martinez",
                email=TEST_USER_EMAIL,
                password_hash=hash_password(TEST_USER_PASSWORD),
                account_type=AccountType.INTERNAL,
                role=UserRole.PLATFORM_ADMIN,
                status=UserStatus.ACTIVE,
            )
            session.add(user)
            action = "created"
        else:
            user.password_hash = hash_password(TEST_USER_PASSWORD)
            user.status = UserStatus.ACTIVE
            user.account_type = AccountType.INTERNAL
            user.role = UserRole.PLATFORM_ADMIN
            action = "updated"

        await session.commit()
        logger.info("Startup seed %s user: %s", action, TEST_USER_EMAIL)

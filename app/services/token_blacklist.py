"""Token blacklist service for refresh token management."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Set, Dict
from uuid import UUID
from jose import jwt

from app.config import settings

ALGORITHM = "HS256"


class TokenBlacklist:
    """In-memory token blacklist for logout and rotation."""

    def __init__(self):
        self._blacklisted_tokens: Set[str] = set()
        self._user_tokens: Dict[str, Set[str]] = {}  # user_id -> set of token_ids
        self._token_metadata: Dict[str, dict] = {}  # token_id -> metadata
        self._cleanup_task = None

    def _start_cleanup(self):
        """Start background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        """Periodically clean up expired tokens."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def _cleanup_expired(self):
        """Remove expired tokens from memory."""
        now = datetime.now(timezone.utc)
        expired_ids = [
            token_id
            for token_id, meta in self._token_metadata.items()
            if meta.get("exp", now) < now
        ]
        for token_id in expired_ids:
            self._blacklisted_tokens.discard(token_id)
            self._token_metadata.pop(token_id, None)
            for user_tokens in self._user_tokens.values():
                user_tokens.discard(token_id)

    def get_token_id(self, token: str) -> str | None:
        """Extract token ID from JWT without verification."""
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[ALGORITHM],
                options={"verify_exp": False},
            )
            return payload.get("jti") or payload.get("token_id")
        except Exception:
            return None

    def blacklist_token(self, token: str) -> bool:
        """Add a token to the blacklist."""
        token_id = self.get_token_id(token)
        if token_id:
            self._blacklisted_tokens.add(token_id)
            return True
        return False

    def is_blacklisted(self, token: str) -> bool:
        """Check if a token is blacklisted."""
        token_id = self.get_token_id(token)
        return token_id in self._blacklisted_tokens

    def register_token(self, user_id: str, token: str, exp: datetime) -> str:
        """Register a new refresh token for a user. Returns token ID."""
        token_id = self.get_token_id(token)
        if not token_id:
            import uuid

            token_id = str(uuid.uuid4())

        if user_id not in self._user_tokens:
            self._user_tokens[user_id] = set()
        self._user_tokens[user_id].add(token_id)

        self._token_metadata[token_id] = {
            "user_id": user_id,
            "exp": exp,
        }

        self._start_cleanup()
        return token_id

    def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all tokens for a user. Returns count of revoked tokens."""
        if user_id not in self._user_tokens:
            return 0

        count = 0
        for token_id in self._user_tokens[user_id]:
            self._blacklisted_tokens.add(token_id)
            count += 1

        self._user_tokens[user_id].clear()
        return count

    def revoke_token_family(self, user_id: str, token: str) -> bool:
        """Revoke a token and all its family members (rotation tracking)."""
        token_id = self.get_token_id(token)
        if not token_id:
            return False

        if user_id in self._user_tokens:
            for tid in list(self._user_tokens[user_id]):
                self._blacklisted_tokens.add(tid)
            self._user_tokens[user_id].clear()

        self._blacklisted_tokens.add(token_id)
        return True

    @property
    def stats(self) -> dict:
        """Get blacklist stats."""
        return {
            "blacklisted_tokens": len(self._blacklisted_tokens),
            "registered_users": len(self._user_tokens),
            "metadata_entries": len(self._token_metadata),
        }


token_blacklist = TokenBlacklist()

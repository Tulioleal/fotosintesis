from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from uuid import UUID, uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AuthSession, AuthUser, RecoveryToken
from app.auth.passwords import hash_password, hash_token, verify_password
from app.auth.tables import recovery_tokens, sessions, users
from app.db.repository import RepositoryBase


class DuplicateEmailError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _user_from_row(row) -> AuthUser:
    return AuthUser(
        id=row.id,
        name=row.name,
        email=row.email,
        password_hash=row.password_hash,
        email_verified=row.email_verified,
        timezone=row.timezone,
        created_at=_utc(row.created_at),
        updated_at=_utc(row.updated_at),
    )


def _session_from_row(row) -> AuthSession:
    return AuthSession(
        id=row.id,
        user_id=row.user_id,
        token=row.session_token,
        expires_at=_utc(row.expires),
        absolute_expires_at=_utc(row.absolute_expires_at),
        created_at=_utc(row.created_at),
        updated_at=_utc(row.updated_at),
        invalidated_at=_utc(row.invalidated_at) if row.invalidated_at else None,
    )


class DatabaseAuthRepository(RepositoryBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_user(self, name: str, email: str, password: str) -> AuthUser:
        normalized_email = email.strip().lower()
        now = datetime.now(timezone.utc)
        user = AuthUser(
            id=uuid4(),
            name=name.strip(),
            email=normalized_email,
            password_hash=hash_password(password),
            email_verified=False,
            created_at=now,
            updated_at=now,
        )
        try:
            await self.session.execute(
                insert(users).values(
                    id=user.id,
                    name=user.name,
                    email=user.email,
                    email_verified=user.email_verified,
                    password_hash=user.password_hash,
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                )
            )
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise DuplicateEmailError("email already registered") from error
        return user

    async def verify_credentials(self, email: str, password: str) -> AuthUser:
        row = (
            await self.session.execute(
                select(users).where(users.c.email == email.strip().lower())
            )
        ).first()
        user = _user_from_row(row) if row else None
        if (
            user is None
            or not user.password_hash
            or not verify_password(password, user.password_hash)
        ):
            raise InvalidCredentialsError("invalid credentials")
        return user

    async def create_session(
        self, user_id: UUID, idle_ttl: timedelta, absolute_ttl: timedelta
    ) -> AuthSession:
        now = datetime.now(timezone.utc)
        session = AuthSession(
            id=uuid4(),
            user_id=user_id,
            token=token_urlsafe(32),
            expires_at=now + idle_ttl,
            absolute_expires_at=now + absolute_ttl,
            created_at=now,
            updated_at=now,
        )
        await self.session.execute(
            insert(sessions).values(
                id=session.id,
                user_id=session.user_id,
                session_token=session.token,
                expires=session.expires_at,
                absolute_expires_at=session.absolute_expires_at,
                created_at=session.created_at,
                updated_at=session.updated_at,
                invalidated_at=session.invalidated_at,
            )
        )
        await self.session.commit()
        return session

    async def get_valid_session(
        self, token: str, idle_ttl: timedelta
    ) -> tuple[AuthSession, AuthUser] | None:
        row = (
            await self.session.execute(select(sessions).where(sessions.c.session_token == token))
        ).first()
        session = _session_from_row(row) if row else None
        now = datetime.now(timezone.utc)
        if (
            session is None
            or session.invalidated_at is not None
            or session.expires_at <= now
            or session.absolute_expires_at <= now
        ):
            return None

        session.expires_at = min(now + idle_ttl, session.absolute_expires_at)
        session.updated_at = now
        user_row = (
            await self.session.execute(select(users).where(users.c.id == session.user_id))
        ).first()
        user = _user_from_row(user_row) if user_row else None
        if user is None:
            return None
        await self.session.execute(
            update(sessions)
            .where(sessions.c.id == session.id)
            .values(expires=session.expires_at, updated_at=session.updated_at)
        )
        await self.session.commit()
        return session, user

    async def invalidate_session(self, token: str) -> None:
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(sessions)
            .where(sessions.c.session_token == token)
            .values(invalidated_at=now, updated_at=now)
        )
        await self.session.commit()

    async def update_timezone(self, user_id: UUID, tz: str | None) -> AuthUser | None:
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(users).where(users.c.id == user_id).values(timezone=tz, updated_at=now)
        )
        await self.session.commit()
        row = (await self.session.execute(select(users).where(users.c.id == user_id))).first()
        return _user_from_row(row) if row else None

    async def create_recovery_token(self, email: str, ttl: timedelta) -> RecoveryToken:
        user_row = (
            await self.session.execute(
                select(users).where(users.c.email == email.strip().lower())
            )
        ).first()
        user = _user_from_row(user_row) if user_row else None
        now = datetime.now(timezone.utc)
        raw_token = token_urlsafe(32)
        recovery = RecoveryToken(
            id=uuid4(),
            user_id=user.id if user else None,
            token_hash=hash_token(raw_token),
            expires_at=now + ttl,
            created_at=now,
        )
        if user is not None:
            # Invalidate any prior active tokens for the same account so only
            # the most recent link can be used.
            await self.session.execute(
                update(recovery_tokens)
                .where(
                    recovery_tokens.c.user_id == user.id,
                    recovery_tokens.c.used_at.is_(None),
                    recovery_tokens.c.invalidated_at.is_(None),
                )
                .values(invalidated_at=now)
            )
        await self.session.execute(
            insert(recovery_tokens).values(
                id=recovery.id,
                user_id=recovery.user_id,
                token_hash=recovery.token_hash,
                expires_at=recovery.expires_at,
                created_at=recovery.created_at,
            )
        )
        await self.session.commit()
        # Attach the raw token transiently so the delivery boundary can build
        # the link; it is never persisted.
        recovery.token = raw_token
        return recovery

    async def consume_recovery_token(self, raw_token: str, new_password: str) -> bool:
        """Atomically consume a valid token and update the password.

        Returns True only if a single eligible token was consumed and the
        password updated in the same transaction. The conditional
        ``UPDATE ... WHERE used_at IS NULL`` ensures concurrent attempts with
        the same token yield at most one success. A neutral False is returned
        for unknown, expired, used, or invalidated tokens.
        """
        token_hash = hash_token(raw_token)
        now = datetime.now(timezone.utc)
        row = (
            await self.session.execute(
                select(recovery_tokens).where(recovery_tokens.c.token_hash == token_hash)
            )
        ).first()
        if row is None:
            await self.session.rollback()
            return False

        user_id = row.user_id
        expires_at = _utc(row.expires_at)
        if user_id is None or expires_at is None or expires_at <= now:
            await self.session.rollback()
            return False

        result = await self.session.execute(
            update(recovery_tokens)
            .where(
                recovery_tokens.c.token_hash == token_hash,
                recovery_tokens.c.used_at.is_(None),
                recovery_tokens.c.invalidated_at.is_(None),
                recovery_tokens.c.expires_at > now,
            )
            .values(used_at=now)
        )
        if result.rowcount == 0:
            await self.session.rollback()
            return False

        await self.session.execute(
            update(users)
            .where(users.c.id == user_id)
            .values(password_hash=hash_password(new_password), updated_at=now)
        )
        await self._revoke_all_sessions(user_id, now)
        await self.session.commit()
        return True

    async def _revoke_all_sessions(self, user_id: UUID, now: datetime) -> None:
        await self.session.execute(
            update(sessions)
            .where(
                sessions.c.user_id == user_id,
                sessions.c.invalidated_at.is_(None),
            )
            .values(invalidated_at=now, updated_at=now)
        )

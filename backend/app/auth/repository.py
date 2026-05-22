from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from uuid import UUID, uuid4

from app.auth.models import AuthSession, AuthUser, RecoveryToken
from app.auth.passwords import hash_password, verify_password


class DuplicateEmailError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


class InMemoryAuthRepository:
    def __init__(self) -> None:
        self.users_by_email: dict[str, AuthUser] = {}
        self.users_by_id: dict[UUID, AuthUser] = {}
        self.sessions_by_token: dict[str, AuthSession] = {}
        self.recovery_tokens: dict[str, RecoveryToken] = {}

    def create_user(self, name: str, email: str, password: str) -> AuthUser:
        normalized_email = email.strip().lower()
        if normalized_email in self.users_by_email:
            raise DuplicateEmailError("email already registered")

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
        self.users_by_email[normalized_email] = user
        self.users_by_id[user.id] = user
        return user

    def verify_credentials(self, email: str, password: str) -> AuthUser:
        user = self.users_by_email.get(email.strip().lower())
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("invalid credentials")
        return user

    def create_session(self, user_id: UUID, idle_ttl: timedelta, absolute_ttl: timedelta) -> AuthSession:
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
        self.sessions_by_token[session.token] = session
        return session

    def get_valid_session(self, token: str, idle_ttl: timedelta) -> tuple[AuthSession, AuthUser] | None:
        session = self.sessions_by_token.get(token)
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
        user = self.users_by_id.get(session.user_id)
        if user is None:
            return None
        return session, user

    def invalidate_session(self, token: str) -> None:
        session = self.sessions_by_token.get(token)
        if session is not None:
            session.invalidated_at = datetime.now(timezone.utc)

    def create_recovery_token(self, email: str, ttl: timedelta) -> RecoveryToken:
        user = self.users_by_email.get(email.strip().lower())
        now = datetime.now(timezone.utc)
        recovery = RecoveryToken(
            id=uuid4(),
            user_id=user.id if user else None,
            token=token_urlsafe(32),
            expires_at=now + ttl,
            created_at=now,
        )
        self.recovery_tokens[recovery.token] = recovery
        return recovery


auth_repository = InMemoryAuthRepository()

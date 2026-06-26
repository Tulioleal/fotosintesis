"""Shared SQLAlchemy repository base class.

Centralizes the common ``AsyncSession`` wiring and the explicit
``commit``/``rollback`` helpers used by every feature repository in the
backend.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class RepositoryBase:
    """Base class for repositories that wrap a single ``AsyncSession``.

    Subclasses can call :meth:`commit` and :meth:`rollback` instead of
    reaching into ``self.session`` directly. Method signatures and
    exception behavior of subclasses are intentionally preserved.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


__all__ = ["RepositoryBase"]

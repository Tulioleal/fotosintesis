from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tables import garden_plants, plant_profiles, reminders, users
from app.db.repository import RepositoryBase
from app.schemas.reminders import ReminderCreate, ReminderDto, ReminderRecurrence, ReminderStatus, ReminderUpdate
from app.scheduling.timezone import local_datetime_to_utc, resolve_timezone


class MissingTimezoneError(ValueError):
    """Raised when neither the reminder override nor the user preference supplies a timezone."""


class ReminderRepository(RepositoryBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_reminders(self, *, user_id: UUID, garden_plant_id: UUID | None = None) -> list[ReminderDto]:
        conditions = [reminders.c.user_id == user_id]
        if garden_plant_id is not None:
            conditions.append(reminders.c.garden_plant_id == garden_plant_id)

        rows = (
            await self.session.execute(
                select(reminders, garden_plants, plant_profiles)
                .join(garden_plants, garden_plants.c.id == reminders.c.garden_plant_id)
                .join(plant_profiles, plant_profiles.c.id == garden_plants.c.profile_id)
                .where(and_(*conditions))
                .order_by(reminders.c.status.asc(), reminders.c.due_at.asc())
            )
        ).all()
        return [_reminder_from_row(row._mapping) for row in rows]

    async def create_reminder(self, *, user_id: UUID, payload: ReminderCreate) -> ReminderDto | None:
        if not await self._plant_exists(user_id=user_id, garden_plant_id=payload.garden_plant_id):
            return None
        zone = await self._resolve_effective_timezone(user_id, payload.timezone)
        reminder_id = uuid4()
        due_at = _to_utc(payload.date, payload.time, zone)
        await self.session.execute(
            insert(reminders).values(
                id=reminder_id,
                user_id=user_id,
                garden_plant_id=payload.garden_plant_id,
                action=payload.action,
                due_at=due_at,
                recurrence=_stored_recurrence(payload.recurrence),
                suggestion_justification=payload.suggestion_justification,
                timezone=zone.key,
            )
        )
        await self._increment_active(payload.garden_plant_id, 1)
        await self.session.commit()
        return await self.get_reminder(user_id=user_id, reminder_id=reminder_id)

    async def get_reminder(self, *, user_id: UUID, reminder_id: UUID) -> ReminderDto | None:
        row = (
            await self.session.execute(
                select(reminders, garden_plants, plant_profiles)
                .join(garden_plants, garden_plants.c.id == reminders.c.garden_plant_id)
                .join(plant_profiles, plant_profiles.c.id == garden_plants.c.profile_id)
                .where(reminders.c.id == reminder_id, reminders.c.user_id == user_id)
            )
        ).first()
        return _reminder_from_row(row._mapping) if row else None

    async def update_reminder(
        self, *, user_id: UUID, reminder_id: UUID, payload: ReminderUpdate
    ) -> ReminderDto | None:
        existing = await self._reminder_row(user_id=user_id, reminder_id=reminder_id)
        if existing is None:
            return None

        values: dict[str, object | None] = {}
        moved_plant_id: UUID | None = None
        if payload.garden_plant_id is not None:
            if not await self._plant_exists(user_id=user_id, garden_plant_id=payload.garden_plant_id):
                return None
            values["garden_plant_id"] = payload.garden_plant_id
            if payload.garden_plant_id != existing.garden_plant_id:
                moved_plant_id = payload.garden_plant_id
        if payload.action is not None:
            values["action"] = payload.action
        if payload.date is not None or payload.time is not None:
            values["due_at"] = await _updated_due_at(existing, payload, user_id, self)
        if payload.recurrence is not None:
            values["recurrence"] = _stored_recurrence(payload.recurrence)
        if payload.suggestion_justification is not None:
            values["suggestion_justification"] = payload.suggestion_justification.strip() or None
        if payload.timezone is not None:
            values["timezone"] = payload.timezone

        if values:
            await self.session.execute(update(reminders).where(reminders.c.id == reminder_id).values(**values))
            if (
                moved_plant_id is not None
                and existing.status == ReminderStatus.pending.value
            ):
                await self._increment_active(existing.garden_plant_id, -1)
                await self._increment_active(moved_plant_id, 1)
            await self.session.commit()
        return await self.get_reminder(user_id=user_id, reminder_id=reminder_id)

    async def delete_reminder(self, *, user_id: UUID, reminder_id: UUID) -> bool:
        existing = await self._reminder_row(user_id=user_id, reminder_id=reminder_id)
        if existing is None:
            return False
        await self.session.execute(delete(reminders).where(reminders.c.id == reminder_id))
        if existing.status == ReminderStatus.pending.value:
            await self._increment_active(existing.garden_plant_id, -1)
        await self.session.commit()
        return True

    async def complete_reminder(self, *, user_id: UUID, reminder_id: UUID) -> ReminderDto | None:
        existing = await self._reminder_row(user_id=user_id, reminder_id=reminder_id)
        if existing is None:
            return None
        if existing.status != ReminderStatus.pending.value:
            return await self.get_reminder(user_id=user_id, reminder_id=reminder_id)

        await self.session.execute(
            update(reminders)
            .where(reminders.c.id == reminder_id)
            .values(status=ReminderStatus.completed.value)
        )
        next_due_at = _next_occurrence(
            existing.due_at, existing.recurrence, existing.timezone
        )
        if next_due_at is not None:
            await self.session.execute(
                insert(reminders).values(
                    id=uuid4(),
                    user_id=user_id,
                    garden_plant_id=existing.garden_plant_id,
                    action=existing.action,
                    due_at=next_due_at,
                    recurrence=existing.recurrence,
                    suggestion_justification=existing.suggestion_justification,
                    timezone=existing.timezone,
                )
            )
        else:
            await self._increment_active(existing.garden_plant_id, -1)
        await self.session.commit()

        completed = await self.get_reminder(user_id=user_id, reminder_id=reminder_id)
        if completed and next_due_at is not None:
            completed.next_occurrence_at = next_due_at
        return completed

    async def _plant_exists(self, *, user_id: UUID, garden_plant_id: UUID) -> bool:
        row = (
            await self.session.execute(
                select(garden_plants.c.id).where(
                    garden_plants.c.id == garden_plant_id,
                    garden_plants.c.user_id == user_id,
                )
            )
        ).first()
        return row is not None

    async def reconcile_active_reminders(self) -> int:
        """Recompute each garden plant's active reminder count from pending rows.

        Idempotent: running it again has no additional effect. Returns the
        number of garden plants whose stored counter was changed.
        """
        counts = (
            await self.session.execute(
                select(reminders.c.garden_plant_id, func.count())
                .where(reminders.c.status == ReminderStatus.pending.value)
                .group_by(reminders.c.garden_plant_id)
            )
        ).all()
        expected = {plant_id: count for plant_id, count in counts}

        all_plant_ids = (
            await self.session.execute(select(garden_plants.c.id))
        ).scalars().all()
        changed = 0
        for plant_id in all_plant_ids:
            target = expected.get(plant_id, 0)
            await self.session.execute(
                update(garden_plants)
                .where(garden_plants.c.id == plant_id)
                .values(active_reminders=target)
            )
            changed += 1
        await self.session.commit()
        return changed

    async def _reminder_row(self, *, user_id: UUID, reminder_id: UUID):
        return (
            await self.session.execute(
                select(reminders).where(reminders.c.id == reminder_id, reminders.c.user_id == user_id)
            )
        ).first()

    async def _increment_active(self, garden_plant_id: UUID, amount: int) -> None:
        await self.session.execute(
            update(garden_plants)
            .where(garden_plants.c.id == garden_plant_id)
            .values(active_reminders=garden_plants.c.active_reminders + amount)
        )

    async def _resolve_effective_timezone(self, user_id: UUID, override: str | None):
        raw = override
        if not raw:
            raw = await self._user_timezone(user_id)
        if not raw:
            raise MissingTimezoneError(
                "Provide a timezone on your account or on this reminder to schedule it."
            )
        zone = resolve_timezone(raw)
        if zone is None:
            raise MissingTimezoneError("Provide a valid IANA timezone.")
        return zone

    async def _user_timezone(self, user_id: UUID) -> str | None:
        value = await self.session.scalar(select(users.c.timezone).where(users.c.id == user_id))
        return value


async def _updated_due_at(existing, payload: ReminderUpdate, user_id: UUID, repository: ReminderRepository):
    zone_key = payload.timezone or existing.timezone
    zone = await repository._resolve_effective_timezone(user_id, zone_key)
    due_date = payload.date or existing.due_at.date()
    due_time = (payload.time or existing.due_at.timetz().replace(tzinfo=None))
    return _to_utc(due_date, due_time, zone)


def _to_utc(due_date: date, due_time: time, zone) -> datetime:
    return local_datetime_to_utc(due_date, due_time, zone)


def _next_occurrence(due_at: datetime, recurrence: str | None, tz_key: str | None):
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    zone = resolve_timezone(tz_key)
    match recurrence:
        case ReminderRecurrence.daily.value:
            return _add_local_days(due_at, 1, zone)
        case ReminderRecurrence.weekly.value:
            return _add_local_days(due_at, 7, zone)
        case ReminderRecurrence.monthly.value:
            return _add_local_months(due_at, zone)
    return None


def _add_local_days(due_at: datetime, days: int, zone) -> datetime | None:
    if zone is None:
        return due_at + timedelta(days=days)
    local = due_at.astimezone(zone).replace(tzinfo=None)
    shifted = local + timedelta(days=days)
    return _to_utc(shifted.date(), shifted.time(), zone)


def _add_local_months(due_at: datetime, zone) -> datetime | None:
    if zone is None:
        local = due_at.replace(tzinfo=None)
    else:
        local = due_at.astimezone(zone).replace(tzinfo=None)
    month = local.month + 1
    year = local.year
    if month > 12:
        month = 1
        year += 1
    day = min(local.day, _days_in_month(year, month))
    shifted = local.replace(year=year, month=month, day=day)
    if zone is None:
        return shifted.replace(tzinfo=timezone.utc)
    return _to_utc(shifted.date(), shifted.time(), zone)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        following = date(year + 1, 1, 1)
    else:
        following = date(year, month + 1, 1)
    return (following - timedelta(days=1)).day


def _stored_recurrence(recurrence: ReminderRecurrence) -> str | None:
    return None if recurrence == ReminderRecurrence.none else recurrence.value


def _response_recurrence(recurrence: str | None) -> ReminderRecurrence:
    if recurrence in {item.value for item in ReminderRecurrence}:
        return ReminderRecurrence(recurrence)
    return ReminderRecurrence.none


def _reminder_from_row(row) -> ReminderDto:
    nickname = row[garden_plants.c.nickname]
    plant_name = nickname or row[plant_profiles.c.common_name] or row[plant_profiles.c.scientific_name]
    return ReminderDto(
        id=row[reminders.c.id],
        garden_plant_id=row[reminders.c.garden_plant_id],
        plant_name=plant_name,
        action=row[reminders.c.action],
        due_at=row[reminders.c.due_at],
        recurrence=_response_recurrence(row[reminders.c.recurrence]),
        status=ReminderStatus(row[reminders.c.status]),
        suggestion_justification=row[reminders.c.suggestion_justification],
        timezone=row[reminders.c.timezone],
    )

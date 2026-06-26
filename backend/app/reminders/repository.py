from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tables import garden_plants, plant_profiles, reminders
from app.db.repository import RepositoryBase
from app.schemas.reminders import ReminderCreate, ReminderDto, ReminderRecurrence, ReminderStatus, ReminderUpdate


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
        reminder_id = uuid4()
        due_at = _combine_due_at(payload.date, payload.time)
        await self.session.execute(
            insert(reminders).values(
                id=reminder_id,
                user_id=user_id,
                garden_plant_id=payload.garden_plant_id,
                action=payload.action,
                due_at=due_at,
                recurrence=_stored_recurrence(payload.recurrence),
                suggestion_justification=payload.suggestion_justification,
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
        if payload.garden_plant_id is not None:
            if not await self._plant_exists(user_id=user_id, garden_plant_id=payload.garden_plant_id):
                return None
            values["garden_plant_id"] = payload.garden_plant_id
        if payload.action is not None:
            values["action"] = payload.action
        if payload.date is not None or payload.time is not None:
            current_due_at = existing.due_at
            values["due_at"] = _combine_due_at(
                payload.date or current_due_at.date(),
                payload.time or current_due_at.timetz().replace(tzinfo=None),
            )
        if payload.recurrence is not None:
            values["recurrence"] = _stored_recurrence(payload.recurrence)
        if payload.suggestion_justification is not None:
            values["suggestion_justification"] = payload.suggestion_justification.strip() or None

        if values:
            await self.session.execute(update(reminders).where(reminders.c.id == reminder_id).values(**values))
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
        next_due_at = calculate_next_occurrence(existing.due_at, existing.recurrence)
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


def calculate_next_occurrence(due_at: datetime, recurrence: str | None) -> datetime | None:
    match recurrence:
        case ReminderRecurrence.daily.value:
            return due_at + timedelta(days=1)
        case ReminderRecurrence.weekly.value:
            return due_at + timedelta(weeks=1)
        case ReminderRecurrence.monthly.value:
            month = due_at.month + 1
            year = due_at.year
            if month > 12:
                month = 1
                year += 1
            day = min(due_at.day, _days_in_month(year, month))
            return due_at.replace(year=year, month=month, day=day)
    return None


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        following = date(year + 1, 1, 1)
    else:
        following = date(year, month + 1, 1)
    return (following - timedelta(days=1)).day


def _combine_due_at(due_date: date, due_time: time) -> datetime:
    return datetime.combine(due_date, due_time, tzinfo=timezone.utc)


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
    )

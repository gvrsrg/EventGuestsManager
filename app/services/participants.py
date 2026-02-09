from uuid import UUID
from fastapi import HTTPException
from sqlmodel import Session
from sqlalchemy import select, func, update

from ..models import Event, EventParticipant, RideMatch
from ..enums import (
    EventJoinPolicy, EventStatus,
    ParticipationStatus, RideMode,
    RideMatchStatus,
)

def _normalize_ride(ride_mode: RideMode, seats_offered: int | None):
    seats_offered = 0 if seats_offered is None else seats_offered
    if ride_mode == RideMode.OFFER:
        if seats_offered < 1:
            raise HTTPException(400, "seats_offered must be >= 1 when ride_mode=OFFER")
        return ride_mode, seats_offered
    if seats_offered != 0:
        raise HTTPException(400, "seats_offered must be 0 unless ride_mode=OFFER")
    return ride_mode, 0

def _count_approved(session: Session, event_id: UUID) -> int:
    stmt = select(func.count()).select_from(EventParticipant).where(
        EventParticipant.event_id == event_id,
        EventParticipant.status == ParticipationStatus.APPROVED,
    )
    return int(session.exec(stmt).one())

def _resolve_join_status(event: Event, approved_count: int) -> ParticipationStatus:
    if event.status != EventStatus.PUBLISHED:
        raise HTTPException(400, "Event is not published")
    if event.status == EventStatus.CANCELED:
        raise HTTPException(400, "Event is canceled")

    is_full = event.capacity is not None and approved_count >= event.capacity

    if event.join_policy == EventJoinPolicy.OPEN:
        if is_full:
            raise HTTPException(400, "Event is full")
        return ParticipationStatus.APPROVED

    if event.join_policy == EventJoinPolicy.APPROVAL:
        return ParticipationStatus.PENDING

    if event.join_policy == EventJoinPolicy.OPEN_UNTIL_CAPACITY_THEN_APPROVAL:
        return ParticipationStatus.PENDING if is_full else ParticipationStatus.APPROVED

    return ParticipationStatus.PENDING

def join_event(session: Session, event_id: UUID, user_id: UUID, ride_mode: RideMode, seats_offered: int | None, pickup_area: str | None, notes: str | None) -> EventParticipant:
    # lock event
    event = session.exec(
        select(Event).where(Event.id == event_id).with_for_update()
    ).one_or_none()
    if not event:
        raise HTTPException(404, "Event not found")
    if event.status == EventStatus.CANCELED:
        raise HTTPException(400, "Event is canceled")

    approved = _count_approved(session, event_id)
    status = _resolve_join_status(event, approved)

    ride_mode, seats_offered = _normalize_ride(ride_mode, seats_offered)

    p = session.exec(
        select(EventParticipant)
        .where(EventParticipant.event_id == event_id, EventParticipant.user_id == user_id)
        .with_for_update()
    ).one_or_none()

    if not p:
        p = EventParticipant(
            event_id=event_id,
            user_id=user_id,
            status=status,
            ride_mode=ride_mode,
            seats_offered=seats_offered,
            pickup_area=pickup_area,
            notes=notes,
        )
        session.add(p)
    else:
        p.status = status
        p.ride_mode = ride_mode
        p.seats_offered = seats_offered
        if pickup_area is not None:
            p.pickup_area = pickup_area
        if notes is not None:
            p.notes = notes

    session.flush()
    return p

def leave_event(session: Session, event_id: UUID, user_id: UUID) -> EventParticipant:
    p = session.exec(
        select(EventParticipant)
        .where(EventParticipant.event_id == event_id, EventParticipant.user_id == user_id)
        .with_for_update()
    ).one_or_none()
    if not p:
        raise HTTPException(404, "Not joined")

    p.status = ParticipationStatus.CANCELED
    p.ride_mode = RideMode.NONE
    p.seats_offered = 0

    # cancel active matches
    session.exec(
        update(RideMatch)
        .where(
            RideMatch.event_id == event_id,
            RideMatch.status.in_([RideMatchStatus.PROPOSED, RideMatchStatus.ACCEPTED]),
            (RideMatch.driver_participant_id == p.id) | (RideMatch.rider_participant_id == p.id),
        )
        .values(status=RideMatchStatus.CANCELED)
    )

    # optional auto-promote pending for OPEN_UNTIL_CAPACITY_THEN_APPROVAL
    event = session.exec(select(Event).where(Event.id == event_id).with_for_update()).one()
    if event.join_policy == EventJoinPolicy.OPEN_UNTIL_CAPACITY_THEN_APPROVAL and event.capacity:
        approved = _count_approved(session, event_id)
        if approved < event.capacity:
            oldest_pending = session.exec(
                select(EventParticipant)
                .where(EventParticipant.event_id == event_id, EventParticipant.status == ParticipationStatus.PENDING)
                .order_by(EventParticipant.created_at.asc())
                .with_for_update()
            ).one_or_none()
            if oldest_pending:
                oldest_pending.status = ParticipationStatus.APPROVED

    session.flush()
    return p

def update_my_participation(session: Session, event_id: UUID, user_id: UUID, ride_mode: RideMode | None, seats_offered: int | None, pickup_area: str | None, notes: str | None) -> EventParticipant:
    p = session.exec(
        select(EventParticipant)
        .where(EventParticipant.event_id == event_id, EventParticipant.user_id == user_id)
        .with_for_update()
    ).one_or_none()
    if not p:
        raise HTTPException(404, "Not joined")

    if p.status not in (ParticipationStatus.APPROVED, ParticipationStatus.PENDING):
        raise HTTPException(400, "Cannot update in this status")

    prev_mode = p.ride_mode

    new_mode = ride_mode if ride_mode is not None else p.ride_mode
    new_seats = seats_offered if seats_offered is not None else p.seats_offered
    new_mode, new_seats = _normalize_ride(new_mode, new_seats)

    p.ride_mode = new_mode
    p.seats_offered = new_seats
    if pickup_area is not None:
        p.pickup_area = pickup_area
    if notes is not None:
        p.notes = notes

    if prev_mode != p.ride_mode:
        session.exec(
            update(RideMatch)
            .where(
                RideMatch.event_id == event_id,
                RideMatch.status.in_([RideMatchStatus.PROPOSED, RideMatchStatus.ACCEPTED]),
                (RideMatch.driver_participant_id == p.id) | (RideMatch.rider_participant_id == p.id),
            )
            .values(status=RideMatchStatus.CANCELED)
        )

    session.flush()
    return p

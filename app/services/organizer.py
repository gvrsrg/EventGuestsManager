from uuid import UUID
from fastapi import HTTPException
from sqlmodel import Session
from sqlalchemy import select, func, update

from ..models import Event, EventParticipant, RideMatch
from ..enums import (
    ParticipationStatus, RideMode, RideMatchStatus,
    EventJoinPolicy
)

def _ensure_organizer(session: Session, event_id: UUID, user_id: UUID) -> Event:
    event = session.exec(select(Event).where(Event.id == event_id)).one_or_none()
    if not event:
        raise HTTPException(404, "Event not found")
    if event.created_by != user_id:
        raise HTTPException(403, "Forbidden")
    return event

def list_participants(session: Session, event_id: UUID, organizer_id: UUID):
    _ensure_organizer(session, event_id, organizer_id)
    return session.exec(
        select(EventParticipant)
        .where(EventParticipant.event_id == event_id)
        .order_by(EventParticipant.created_at.asc())
    ).all()

def set_participant_status(session: Session, event_id: UUID, organizer_id: UUID, participant_id: UUID, next_status: ParticipationStatus):
    if next_status not in (ParticipationStatus.APPROVED, ParticipationStatus.REJECTED):
        raise HTTPException(400, "Invalid status change")

    # lock event + participant to enforce capacity safely
    event = session.exec(
        select(Event).where(Event.id == event_id).with_for_update()
    ).one_or_none()
    if not event:
        raise HTTPException(404, "Event not found")
    if event.created_by != organizer_id:
        raise HTTPException(403, "Forbidden")

    p = session.exec(
        select(EventParticipant)
        .where(EventParticipant.id == participant_id, EventParticipant.event_id == event_id)
        .with_for_update()
    ).one_or_none()
    if not p:
        raise HTTPException(404, "Participant not found")

    if next_status == ParticipationStatus.APPROVED:
        if event.capacity is not None:
            approved = session.exec(
                select(func.count())
                .select_from(EventParticipant)
                .where(
                    EventParticipant.event_id == event_id,
                    EventParticipant.status == ParticipationStatus.APPROVED,
                )
            ).one()
            approved_count = int(approved)
            if approved_count >= event.capacity:
                raise HTTPException(400, "Cannot approve: event is full")

    p.status = next_status
    session.add(p)
    session.flush()
    return p

def event_stats(session: Session, event_id: UUID):
    # participation status counts
    def _count_status(status: ParticipationStatus) -> int:
        return int(session.exec(
            select(func.count())
            .select_from(EventParticipant)
            .where(EventParticipant.event_id == event_id, EventParticipant.status == status)
        ).one())

    approved_count = _count_status(ParticipationStatus.APPROVED)
    pending_count = _count_status(ParticipationStatus.PENDING)
    rejected_count = _count_status(ParticipationStatus.REJECTED)
    canceled_count = _count_status(ParticipationStatus.CANCELED)

    need_ride_count = int(session.exec(
        select(func.count())
        .select_from(EventParticipant)
        .where(
            EventParticipant.event_id == event_id,
            EventParticipant.status == ParticipationStatus.APPROVED,
            EventParticipant.ride_mode == RideMode.NEED
        )
    ).one())

    offer_ride_count = int(session.exec(
        select(func.count())
        .select_from(EventParticipant)
        .where(
            EventParticipant.event_id == event_id,
            EventParticipant.status == ParticipationStatus.APPROVED,
            EventParticipant.ride_mode == RideMode.OFFER
        )
    ).one())

    seats_offered_total = int(session.exec(
        select(func.coalesce(func.sum(EventParticipant.seats_offered), 0))
        .where(
            EventParticipant.event_id == event_id,
            EventParticipant.status == ParticipationStatus.APPROVED,
            EventParticipant.ride_mode == RideMode.OFFER
        )
    ).one())

    seats_accepted_total = int(session.exec(
        select(func.count())
        .select_from(RideMatch)
        .where(
            RideMatch.event_id == event_id,
            RideMatch.status == RideMatchStatus.ACCEPTED
        )
    ).one())

    seats_remaining_total = max(0, seats_offered_total - seats_accepted_total)

    # Riders who still need ride AND have no accepted match
    # unmatched = NEED riders minus distinct riders in accepted matches
    need_riders_ids = session.exec(
        select(EventParticipant.id)
        .where(
            EventParticipant.event_id == event_id,
            EventParticipant.status == ParticipationStatus.APPROVED,
            EventParticipant.ride_mode == RideMode.NEED
        )
    ).all()
    need_riders_set = set(need_riders_ids)

    accepted_riders_ids = session.exec(
        select(RideMatch.rider_participant_id)
        .where(
            RideMatch.event_id == event_id,
            RideMatch.status == RideMatchStatus.ACCEPTED
        )
    ).all()
    accepted_riders_set = set(accepted_riders_ids)

    unmatched_riders_count = len(need_riders_set - accepted_riders_set)

    return {
        "event_id": event_id,
        "approved_count": approved_count,
        "pending_count": pending_count,
        "rejected_count": rejected_count,
        "canceled_count": canceled_count,
        "need_ride_count": need_ride_count,
        "offer_ride_count": offer_ride_count,
        "seats_offered_total": seats_offered_total,
        "seats_accepted_total": seats_accepted_total,
        "seats_remaining_total": seats_remaining_total,
        "unmatched_riders_count": unmatched_riders_count,
    }

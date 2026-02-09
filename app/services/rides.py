from uuid import UUID
from fastapi import HTTPException
from sqlmodel import Session
from sqlalchemy import select, func

from ..models import EventParticipant, RideMatch
from ..enums import ParticipationStatus, RideMode, RideMatchStatus

def _accepted_count(session: Session, event_id: UUID, driver_pid: UUID) -> int:
    stmt = select(func.count()).select_from(RideMatch).where(
        RideMatch.event_id == event_id,
        RideMatch.driver_participant_id == driver_pid,
        RideMatch.status == RideMatchStatus.ACCEPTED,
    )
    return int(session.exec(stmt).one())

def _ensure_compatible_and_seat(session: Session, event_id: UUID, driver_pid: UUID, rider_pid: UUID):
    driver = session.exec(
        select(EventParticipant).where(EventParticipant.id == driver_pid, EventParticipant.event_id == event_id).with_for_update()
    ).one_or_none()
    rider = session.exec(
        select(EventParticipant).where(EventParticipant.id == rider_pid, EventParticipant.event_id == event_id).with_for_update()
    ).one_or_none()

    if not driver or not rider:
        raise HTTPException(404, "Driver or rider not found")
    if driver.id == rider.id:
        raise HTTPException(400, "Driver and rider must be different")
    if driver.status != ParticipationStatus.APPROVED or rider.status != ParticipationStatus.APPROVED:
        raise HTTPException(400, "Both participants must be approved")
    if driver.ride_mode != RideMode.OFFER:
        raise HTTPException(400, "Driver is not offering")
    if rider.ride_mode != RideMode.NEED:
        raise HTTPException(400, "Rider does not need a ride")

    accepted = _accepted_count(session, event_id, driver.id)
    if accepted >= driver.seats_offered:
        raise HTTPException(400, "No seats remaining for this driver")

def create_match(session: Session, event_id: UUID, created_by: UUID, driver_pid: UUID, rider_pid: UUID) -> RideMatch:
    _ensure_compatible_and_seat(session, event_id, driver_pid, rider_pid)
    m = RideMatch(
        event_id=event_id,
        driver_participant_id=driver_pid,
        rider_participant_id=rider_pid,
        status=RideMatchStatus.PROPOSED,
        created_by=created_by,
    )
    session.add(m)
    session.flush()
    return m

def update_match_status(session: Session, match_id: UUID, user_id: UUID, next_status: RideMatchStatus) -> RideMatch:
    if next_status not in (RideMatchStatus.ACCEPTED, RideMatchStatus.REJECTED, RideMatchStatus.CANCELED):
        raise HTTPException(400, "Invalid next status")

    m = session.exec(select(RideMatch).where(RideMatch.id == match_id).with_for_update()).one_or_none()
    if not m:
        raise HTTPException(404, "Match not found")

    driver = session.exec(select(EventParticipant).where(EventParticipant.id == m.driver_participant_id)).one_or_none()
    rider = session.exec(select(EventParticipant).where(EventParticipant.id == m.rider_participant_id)).one_or_none()

    allowed = user_id in {m.created_by, (driver.user_id if driver else None), (rider.user_id if rider else None)}
    if not allowed:
        raise HTTPException(403, "Forbidden")

    if next_status == RideMatchStatus.ACCEPTED:
        _ensure_compatible_and_seat(session, m.event_id, m.driver_participant_id, m.rider_participant_id)

    m.status = next_status
    session.flush()
    return m

def list_matches(session: Session, event_id: UUID):
    return session.exec(
        select(RideMatch).where(RideMatch.event_id == event_id).order_by(RideMatch.created_at.desc())
    ).all()

def suggestions(session: Session, event_id: UUID):
    drivers = session.exec(
        select(EventParticipant)
        .where(
            EventParticipant.event_id == event_id,
            EventParticipant.status == ParticipationStatus.APPROVED,
            EventParticipant.ride_mode == RideMode.OFFER,
        )
        .order_by(EventParticipant.created_at.asc())
    ).all()

    riders = session.exec(
        select(EventParticipant)
        .where(
            EventParticipant.event_id == event_id,
            EventParticipant.status == ParticipationStatus.APPROVED,
            EventParticipant.ride_mode == RideMode.NEED,
        )
        .order_by(EventParticipant.created_at.asc())
    ).all()

    out = []
    rider_idx = 0
    for d in drivers:
        accepted = _accepted_count(session, event_id, d.id)
        remaining = d.seats_offered - accepted
        while remaining > 0 and rider_idx < len(riders):
            out.append({
                "driver_participant_id": str(d.id),
                "rider_participant_id": str(riders[rider_idx].id),
            })
            remaining -= 1
            rider_idx += 1
        if rider_idx >= len(riders):
            break
    return out


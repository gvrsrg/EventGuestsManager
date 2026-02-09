from uuid import UUID
from fastapi import FastAPI, Depends, HTTPException
from sqlmodel import Session, select

from .db import get_session, init_db
from .deps import get_current_user_id
from .models import Event
from .enums import EventStatus, ParticipationStatus
from .schemas import (
    EventCreate, JoinEvent, UpdateMyParticipation,
    RideMatchCreate, RideMatchUpdate, OrganizerParticipantOut, EventStatsOut
)
from .services.participants import join_event, leave_event, update_my_participation
from .services.rides import create_match, update_match_status, list_matches, suggestions
from .services.organizer import list_participants, set_participant_status, event_stats

app = FastAPI(title="Event + Rides (SQLModel)")

@app.on_event("startup")
def on_startup():
    # In production use Alembic migrations instead of create_all.
    init_db()

@app.post("/events")
def create_event(payload: EventCreate, session: Session = Depends(get_session), user_id: UUID = Depends(get_current_user_id)):
    e = Event(
        created_by=user_id,
        title=payload.title,
        description=payload.description,
        start_at=payload.start_at,
        end_at=payload.end_at,
        location_name=payload.location_name,
        location_lat=payload.location_lat,
        location_lng=payload.location_lng,
        capacity=payload.capacity,
        join_policy=payload.join_policy,
        status=EventStatus.DRAFT,
    )
    session.add(e)
    session.commit()
    session.refresh(e)
    return e

@app.post("/events/{event_id}/publish")
def publish_event(event_id: UUID, session: Session = Depends(get_session), user_id: UUID = Depends(get_current_user_id)):
    e = session.exec(select(Event).where(Event.id == event_id)).one_or_none()
    if not e:
        raise HTTPException(404, "Event not found")
    if e.created_by != user_id:
        raise HTTPException(403, "Forbidden")
    e.status = EventStatus.PUBLISHED
    session.add(e)
    session.commit()
    session.refresh(e)
    return e

@app.get("/events")
def list_events(session: Session = Depends(get_session)):
    return session.exec(select(Event).order_by(Event.start_at.asc())).all()

@app.get("/events/{event_id}")
def get_event(event_id: UUID, session: Session = Depends(get_session)):
    e = session.exec(select(Event).where(Event.id == event_id)).one_or_none()
    if not e:
        raise HTTPException(404, "Event not found")
    return e

# ----- Participation -----
@app.post("/events/{event_id}/join")
def api_join(event_id: UUID, payload: JoinEvent, session: Session = Depends(get_session), user_id: UUID = Depends(get_current_user_id)):
    with session.begin():
        p = join_event(session, event_id, user_id, payload.ride_mode, payload.seats_offered, payload.pickup_area, payload.notes)
    session.refresh(p)
    return p

@app.post("/events/{event_id}/leave")
def api_leave(event_id: UUID, session: Session = Depends(get_session), user_id: UUID = Depends(get_current_user_id)):
    with session.begin():
        p = leave_event(session, event_id, user_id)
    session.refresh(p)
    return p

@app.patch("/events/{event_id}/participants/me")
def api_update_me(event_id: UUID, payload: UpdateMyParticipation, session: Session = Depends(get_session), user_id: UUID = Depends(get_current_user_id)):
    with session.begin():
        p = update_my_participation(session, event_id, user_id, payload.ride_mode, payload.seats_offered, payload.pickup_area, payload.notes)
    session.refresh(p)
    return p

# ----- Rides -----
@app.get("/events/{event_id}/rides/matches")
def api_list_matches(event_id: UUID, session: Session = Depends(get_session)):
    return list_matches(session, event_id)

@app.post("/events/{event_id}/rides/suggestions")
def api_suggestions(event_id: UUID, session: Session = Depends(get_session)):
    return suggestions(session, event_id)

@app.post("/events/{event_id}/rides/matches")
def api_create_match(event_id: UUID, payload: RideMatchCreate, session: Session = Depends(get_session), user_id: UUID = Depends(get_current_user_id)):
    with session.begin():
        m = create_match(session, event_id, user_id, payload.driver_participant_id, payload.rider_participant_id)
    session.refresh(m)
    return m

@app.patch("/rides/matches/{match_id}")
def api_update_match(match_id: UUID, payload: RideMatchUpdate, session: Session = Depends(get_session), user_id: UUID = Depends(get_current_user_id)):
    with session.begin():
        m = update_match_status(session, match_id, user_id, payload.status)
    session.refresh(m)
    return m

# ----- Organizer: participants list -----
@app.get("/events/{event_id}/participants", response_model=list[OrganizerParticipantOut])
def api_list_participants(
    event_id: UUID,
    session: Session = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
):
    return list_participants(session, event_id, user_id)

# ----- Organizer: approve -----
@app.patch("/events/{event_id}/participants/{participant_id}/approve", response_model=OrganizerParticipantOut)
def api_approve_participant(
    event_id: UUID,
    participant_id: UUID,
    session: Session = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
):
    with session.begin():
        p = set_participant_status(session, event_id, user_id, participant_id, ParticipationStatus.APPROVED)
    session.refresh(p)
    return p

# ----- Organizer: reject -----
@app.patch("/events/{event_id}/participants/{participant_id}/reject", response_model=OrganizerParticipantOut)
def api_reject_participant(
    event_id: UUID,
    participant_id: UUID,
    session: Session = Depends(get_session),
    user_id: UUID = Depends(get_current_user_id),
):
    with session.begin():
        p = set_participant_status(session, event_id, user_id, participant_id, ParticipationStatus.REJECTED)
    session.refresh(p)
    return p

# ----- Stats -----
@app.get("/events/{event_id}/stats", response_model=EventStatsOut)
def api_event_stats(event_id: UUID, session: Session = Depends(get_session)):
    # readable without auth; if you want organizer-only, add Depends(get_current_user_id) + check
    return event_stats(session, event_id)

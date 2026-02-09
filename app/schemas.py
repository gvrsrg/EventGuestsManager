from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field

from enums import EventJoinPolicy, RideMode, RideMatchStatus, ParticipationStatus

class EventCreate(SQLModel):
    title: str
    description: Optional[str] = None
    start_at: datetime
    end_at: Optional[datetime] = None
    location_name: str
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    capacity: Optional[int] = Field(default=None, ge=1)
    join_policy: EventJoinPolicy

class JoinEvent(SQLModel):
    ride_mode: RideMode
    seats_offered: Optional[int] = 0
    pickup_area: Optional[str] = None
    notes: Optional[str] = None

class UpdateMyParticipation(SQLModel):
    ride_mode: Optional[RideMode] = None
    seats_offered: Optional[int] = None
    pickup_area: Optional[str] = None
    notes: Optional[str] = None

class RideMatchCreate(SQLModel):
    driver_participant_id: UUID
    rider_participant_id: UUID

class RideMatchUpdate(SQLModel):
    status: RideMatchStatus  # ACCEPTED/REJECTED/CANCELED

class OrganizerParticipantOut(SQLModel):
    id: UUID
    event_id: UUID
    user_id: UUID
    status: ParticipationStatus
    ride_mode: RideMode
    seats_offered: int
    pickup_area: Optional[str] = None
    notes: Optional[str] = None

class EventStatsOut(SQLModel):
    event_id: UUID

    approved_count: int
    pending_count: int
    rejected_count: int
    canceled_count: int

    need_ride_count: int
    offer_ride_count: int

    seats_offered_total: int
    seats_accepted_total: int
    seats_remaining_total: int

    unmatched_riders_count: int
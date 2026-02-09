from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, Index
from sqlalchemy import Column, Text, DateTime, Integer, CheckConstraint, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ENUM

from enums import (
    EventJoinPolicy, EventStatus,
    ParticipationStatus, RideMode,
    RideMatchStatus,
)

class User(SQLModel, table=True):
    __tablename__ = "users"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    full_name: str = Field(sa_column=Column(Text, nullable=False))
    email: str = Field(sa_column=Column(Text, unique=True, nullable=False))
    phone: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

class Event(SQLModel, table=True):
    __tablename__ = "events"
    __table_args__ = (Index("idx_events_start_at", "start_at"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_by: UUID = Field(nullable=False, index=True)

    title: str = Field(sa_column=Column(Text, nullable=False))
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    start_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    end_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    location_name: str = Field(sa_column=Column(Text, nullable=False))
    location_lat: Optional[float] = Field(default=None)
    location_lng: Optional[float] = Field(default=None)

    capacity: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    join_policy: EventJoinPolicy = Field(
        sa_column=Column(ENUM(EventJoinPolicy, name="event_join_policy_enum"), nullable=False)
    )
    status: EventStatus = Field(
        default=EventStatus.DRAFT,
        sa_column=Column(ENUM(EventStatus, name="event_status_enum"), nullable=False, server_default=EventStatus.DRAFT.value),
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

class EventParticipant(SQLModel, table=True):
    __tablename__ = "event_participants"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_user"),
        CheckConstraint(
            "((ride_mode = 'OFFER' AND seats_offered >= 1) OR (ride_mode <> 'OFFER' AND seats_offered = 0))",
            name="chk_offer_seats",
        ),
        Index("idx_participants_event_status", "event_id", "status"),
        Index("idx_participants_event_ride", "event_id", "ride_mode"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    event_id: UUID = Field(foreign_key="events.id", index=True)
    user_id: UUID = Field(index=True)

    status: ParticipationStatus = Field(
        sa_column=Column(ENUM(ParticipationStatus, name="participation_status_enum"), nullable=False)
    )

    ride_mode: RideMode = Field(
        default=RideMode.NONE,
        sa_column=Column(ENUM(RideMode, name="ride_mode_enum"), nullable=False, server_default=RideMode.NONE.value),
    )
    seats_offered: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )

    pickup_area: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

class RideMatch(SQLModel, table=True):
    __tablename__ = "ride_matches"
    __table_args__ = (
        CheckConstraint("driver_participant_id <> rider_participant_id", name="chk_driver_not_rider"),
        Index("idx_matches_event_status", "event_id", "status"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    event_id: UUID = Field(foreign_key="events.id", index=True)

    driver_participant_id: UUID = Field(foreign_key="event_participants.id", index=True)
    rider_participant_id: UUID = Field(foreign_key="event_participants.id", index=True)

    status: RideMatchStatus = Field(
        default=RideMatchStatus.PROPOSED,
        sa_column=Column(ENUM(RideMatchStatus, name="ride_match_status_enum"), nullable=False, server_default=RideMatchStatus.PROPOSED.value),
    )

    created_by: UUID = Field(index=True)

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    )

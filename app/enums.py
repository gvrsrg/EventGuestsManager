from enum import Enum

class EventJoinPolicy(str, Enum):
    OPEN = "OPEN"
    APPROVAL = "APPROVAL"
    OPEN_UNTIL_CAPACITY_THEN_APPROVAL = "OPEN_UNTIL_CAPACITY_THEN_APPROVAL"

class EventStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CANCELED = "CANCELED"

class ParticipationStatus(str, Enum):
    APPROVED = "APPROVED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"

class RideMode(str, Enum):
    NONE = "NONE"
    NEED = "NEED"
    OFFER = "OFFER"

class RideMatchStatus(str, Enum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"

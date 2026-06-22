"""Import all models so Alembic/metadata can discover them."""
from app.models.user import User
from app.models.friendship import Friendship
from app.models.trip import Trip, TripPhoto
from app.models.visited import VisitedCountry, VisitedCity
from app.models.badge import Badge, UserBadge
from app.models.challenge import Challenge, ChallengeParticipant
from app.models.activity import ActivityFeed

__all__ = [
    "User",
    "Friendship",
    "Trip",
    "TripPhoto",
    "VisitedCountry",
    "VisitedCity",
    "Badge",
    "UserBadge",
    "Challenge",
    "ChallengeParticipant",
    "ActivityFeed",
]

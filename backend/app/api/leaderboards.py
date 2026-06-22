from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.middleware.auth import get_current_user
from app.schemas.social import LeaderboardResponse
from app.services import leaderboard

router = APIRouter(prefix="/leaderboards", tags=["leaderboards"])


def _validate_metric(metric: str) -> str:
    if metric not in leaderboard.VALID_METRICS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"metric must be one of {sorted(leaderboard.VALID_METRICS)}")
    return metric


@router.get("/friends", response_model=LeaderboardResponse)
def friends_leaderboard(
    metric: str = Query(default="countries"),
    period: str = Query(default="all_time"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validate_metric(metric)
    return LeaderboardResponse(**leaderboard.get_rankings(db, user, metric, period))


@router.get("/global", response_model=LeaderboardResponse)
def global_leaderboard(
    metric: str = Query(default="countries"),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
):
    _validate_metric(metric)
    return LeaderboardResponse(**leaderboard.get_global(db, metric, limit))

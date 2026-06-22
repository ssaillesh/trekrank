from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.middleware.auth import get_current_user
from app.schemas.social import ShareCardRequest, ShareCardResponse
from app.api.dispatch import run_share_card

router = APIRouter(prefix="/share", tags=["share"])


@router.post("/card", response_model=ShareCardResponse)
def create_share_card(body: ShareCardRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    url = run_share_card(str(user.id), body.card_type, body.year)
    if not url:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Could not generate share card")
    return ShareCardResponse(
        image_url=url,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )

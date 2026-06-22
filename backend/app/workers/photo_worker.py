"""Worker 3: Photo Processor. Strips EXIF, builds thumbnail + medium, updates the row."""
import io
import uuid

from PIL import Image

from app.database import SessionLocal
from app.models import TripPhoto
from app.services.storage import save_bytes, read_bytes_from_url
from app.workers.celery_app import celery


def _strip_exif(img: Image.Image) -> Image.Image:
    data = list(img.getdata())
    clean = Image.new(img.mode, img.size)
    clean.putdata(data)
    return clean


def process_photo_sync(photo_id: str) -> None:
    db = SessionLocal()
    try:
        photo = db.get(TripPhoto, uuid.UUID(str(photo_id)))
        if not photo:
            return
        raw = read_bytes_from_url(photo.photo_url)
        if not raw:
            return
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        img = _strip_exif(img)

        # medium 1200x1200
        medium = img.copy()
        medium.thumbnail((1200, 1200))
        mbuf = io.BytesIO()
        medium.save(mbuf, format="JPEG", quality=85)
        photo.photo_url = save_bytes(mbuf.getvalue(), ext="jpg", subdir="photos")

        # thumbnail 400x400
        thumb = img.copy()
        thumb.thumbnail((400, 400))
        tbuf = io.BytesIO()
        thumb.save(tbuf, format="JPEG", quality=80)
        photo.thumbnail_url = save_bytes(tbuf.getvalue(), ext="jpg", subdir="thumbs")

        db.add(photo)
        db.commit()
    finally:
        db.close()


@celery.task(name="trekrank.process_photo")
def process_photo(photo_id: str) -> None:
    process_photo_sync(photo_id)

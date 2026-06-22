"""Generate a branded 1080x1920 (Instagram Story) share card with Pillow."""
import io

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, VisitedCountry
from app.services.storage import save_bytes

W, H = 1080, 1920
BG_TOP = (24, 33, 56)
BG_BOTTOM = (52, 84, 138)
ACCENT = (94, 234, 212)
WHITE = (255, 255, 255)
MUTED = (180, 195, 220)


def _font(size: int, bold: bool = False):
    candidates = [
        "/System/Library/Fonts/SFNSRounded.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _gradient(draw: ImageDraw.ImageDraw) -> None:
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def _centered(draw, text, font, y, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text(((W - w) / 2, y), text, font=font, fill=fill)


def generate_share_card(db: Session, user: User, card_type: str, year: int | None) -> str:
    """Render the card, store it, and return the public URL."""
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    _gradient(draw)

    # Branding
    _centered(draw, "TREKRANK", _font(64, bold=True), 120, ACCENT)

    title = f"{year} in Travel" if (card_type == "year_recap" and year) else "My Travel Map"
    _centered(draw, title, _font(54), 230, WHITE)
    _centered(draw, f"@{user.username}", _font(40), 320, MUTED)

    # Big stats grid
    stats = [
        (str(user.total_countries), "COUNTRIES"),
        (str(user.total_cities), "CITIES"),
        (f"{int(float(user.total_km)):,}", "KM TRAVELED"),
        (str(user.total_trips), "TRIPS"),
    ]
    grid_top = 520
    cell_h = 280
    for i, (value, label) in enumerate(stats):
        row, col = divmod(i, 2)
        cx = W * (0.27 if col == 0 else 0.73)
        cy = grid_top + row * cell_h
        vf = _font(120, bold=True)
        bbox = draw.textbbox((0, 0), value, font=vf)
        draw.text((cx - (bbox[2] - bbox[0]) / 2, cy), value, font=vf, fill=WHITE)
        lf = _font(34)
        lb = draw.textbbox((0, 0), label, font=lf)
        draw.text((cx - (lb[2] - lb[0]) / 2, cy + 150), label, font=lf, fill=ACCENT)

    # Top destinations
    top = db.execute(
        select(VisitedCountry)
        .where(VisitedCountry.user_id == user.id)
        .order_by(VisitedCountry.visit_count.desc())
        .limit(5)
    ).scalars().all()
    _centered(draw, "TOP DESTINATIONS", _font(38, bold=True), 1180, ACCENT)
    y = 1260
    for vc in top:
        _centered(draw, f"{vc.country_name}  ·  {vc.visit_count}x", _font(44), y, WHITE)
        y += 80

    _centered(draw, "trekrank.app", _font(36), H - 120, MUTED)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return save_bytes(buf.getvalue(), ext="png", subdir="share")

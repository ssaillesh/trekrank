"""Chat-driven itinerary concierge. Public (no auth) — the product's front door.

With an LLM key it runs as a sharp concierge that reads the whole conversation,
extracts what it needs, asks one focused follow-up when required, then builds a
real plan optimised for close-together, best-value, hidden-gem stops. Without a
key it degrades to a keyword heuristic so the app still works.
"""
import random
import re

from fastapi import APIRouter

from app.config import settings
from app.schemas.plan import ChatRequest, ChatResponse, Plan
from app.services import llm, yelp
from app.services.geocoding import geocode
from app.services.planner import build_plan, build_trip, VIBE_PLANS

router = APIRouter(prefix="/plan", tags=["planner"])


@router.get("/debug")
def debug():
    """Config health for the planner brain. Never returns the API keys."""
    ok, detail = llm.ping()
    return {
        "llm_configured": llm.available(),
        "llm_base_url": settings.llm_base_url,
        "llm_model": settings.llm_model,
        "llm_test_ok": ok,
        "llm_test_detail": detail,
        "yelp_configured": yelp.available(),
    }

VIBE_LABELS = {
    "chill": "Chill", "romantic": "Romantic", "adventurous": "Adventurous",
    "extravagant": "Extravagant", "night_out": "Night out",
}
_VIBE_KEYWORDS = {
    "chill": ["chill", "relax", "casual", "low key", "lowkey", "cozy"],
    "romantic": ["romantic", "date", "romance", "anniversary", "cute"],
    "adventurous": ["adventure", "adventurous", "active", "outdoors", "explore"],
    "extravagant": ["extravagant", "fancy", "luxury", "luxurious", "upscale", "splurge", "baller"],
    "night_out": ["night out", "party", "bars", "clubbing", "nightlife"],
}

# The concierge's brain. Tuned to this app: sharp, efficient, gathers the four
# signals that matter, and only asks when it truly needs to.
SYSTEM = """You are the planning brain for a local outing concierge app.
Persona: a sharp, polished concierge — efficient and tasteful, minimal fluff, no rambling.
Your job: read the whole conversation and output ONLY JSON (no prose) with these keys:
  budget: number in USD or null
  vibe: one of chill|romantic|adventurous|extravagant|night_out, or null
  party_size: integer (default 2)
  days: integer (1 unless they mention a weekend/multi-day trip)
  time_of_day: morning|afternoon|evening|night or null
  transport: walk|transit|car or null
  group_type: date|friends|family|solo or null
  dietary: short string of food prefs/restrictions, or ""
  location: a city/neighbourhood the user names to plan in (e.g. "Toronto", "Kensington Market"), or null
  interests: short string of specific things they want (e.g. "aquarium, hookah, rec room"), or ""
  ready: true ONLY if budget AND vibe are known
  question: if not ready, ONE concise concierge-style question to get the missing essentials
  quick_replies: array of 2-5 short tappable answers for that question
Planning is optimised for stops close together, best value, and a hidden gem — so a
walkable, budget-fitting plan. Prefer to gather time_of_day, transport, group_type and
dietary when natural, but NEVER block a plan on them: if budget and vibe are known,
set ready=true and leave the rest null. Ask at most what's essential, in one question."""


def _joined_user_text(req):
    return " ".join(m.content for m in req.messages if m.role == "user").lower()


def _orig_user_text(req):
    return " ".join(m.content for m in req.messages if m.role == "user")


def _extract_location(orig_text):
    """Catch 'in/around/near <Capitalized Place>' when the LLM isn't available."""
    m = re.search(r"\b(?:in|around|near|at)\s+([A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,2})", orig_text)
    return m.group(1).strip() if m else None


def _extract_days(text):
    if "weekend" in text:
        return 2
    m = re.search(r"(\d+)\s*[- ]?day", text)
    if m:
        return max(1, min(int(m.group(1)), 5))
    for w, n in {"two": 2, "three": 3, "four": 4, "five": 5}.items():
        if re.search(rf"\b{w}[- ]day", text):
            return n
    return 1


def _heuristic_extract(text):
    out = {"days": _extract_days(text)}
    m = re.search(r"\$?\s*(\d{2,4})\b", text)
    if m:
        out["budget"] = float(m.group(1))
    for vibe, kws in _VIBE_KEYWORDS.items():
        if any(k in text for k in kws):
            out["vibe"] = vibe
            break
    if any(w in text for w in ["morning", "breakfast", "brunch"]):
        out["time_of_day"] = "morning"
    elif any(w in text for w in ["afternoon", "midday", "lunch"]):
        out["time_of_day"] = "afternoon"
    elif any(w in text for w in ["late night", "night out", "clubbing"]):
        out["time_of_day"] = "night"
    if any(w in text for w in ["walk", "walking", "on foot"]):
        out["transport"] = "walk"
    elif any(w in text for w in ["transit", "subway", "metro", "bus", "train"]):
        out["transport"] = "transit"
    elif any(w in text for w in ["car", "driving", "drive"]):
        out["transport"] = "car"
    if any(w in text for w in ["solo", "myself", "just me", "alone"]):
        out["group_type"], out["party_size"] = "solo", 1
    elif "family" in text or "kids" in text:
        out["group_type"] = "family"
    elif "friends" in text:
        out["group_type"] = "friends"
    elif any(w in text for w in ["date", "couple", "for two", "partner"]):
        out["group_type"], out["party_size"] = "date", out.get("party_size", 2)
    for diet in ["vegan", "vegetarian", "halal", "kosher", "gluten-free", "gluten free", "pescatarian"]:
        if diet in text:
            out["dietary"] = diet
            break
    if any(w in text for w in ["no alcohol", "sober", "non-alcoholic", "no drinks"]):
        out["group_type"] = out.get("group_type") or "family"  # suppresses bars
    return out


def _llm_extract(req):
    convo = "\n".join(f"{m.role}: {m.content}" for m in req.messages)
    return llm.chat_json([{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": convo}])


def _clean(prefs):
    """Drop null/empty so build_plan uses its own defaults."""
    keep = {}
    for k in ("budget", "vibe", "party_size", "days", "time_of_day",
              "transport", "group_type", "dietary", "interests"):
        v = prefs.get(k)
        if v not in (None, "", "null"):
            keep[k] = v
    return keep


def _needs(prefs):
    if not prefs.get("budget"):
        return ChatResponse(type="question",
            message="Certainly. What's the budget for the outing?",
            quick_replies=["$50", "$100", "$200", "No limit"])
    if not prefs.get("vibe"):
        return ChatResponse(type="question",
            message="And the mood you're after?",
            quick_replies=[VIBE_LABELS[v] for v in ["chill", "romantic", "adventurous", "extravagant", "night_out"]])
    return None


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    text = _joined_user_text(req)
    prefs = (_llm_extract(req) if llm.available() else None) or _heuristic_extract(text)

    # Where to plan: a city the user named wins over the device pin. This also
    # lets people plan for a place they're not currently standing in.
    lat, lng = req.lat, req.lng
    loc_name = prefs.get("location") or _extract_location(_orig_user_text(req))
    if loc_name:
        coords = geocode(loc_name, None)
        if coords:
            lat, lng = coords
    if lat is None or lng is None:
        return ChatResponse(type="message",
            message="Tell me where — enable location, or just name a city (e.g. \"in Toronto\") — plus your budget and vibe.")

    if not prefs.get("budget") and any(w in text for w in ["no limit", "no object", "unlimited"]):
        prefs["budget"] = 500
    if any(w in text for w in ["surprise", "random", "you pick", "you choose", "whatever"]):
        prefs.setdefault("budget", 100)
        prefs["vibe"] = prefs.get("vibe") or random.choice(list(VIBE_PLANS))
    if not prefs.get("days"):
        prefs["days"] = _extract_days(text)

    missing = _needs(prefs)
    if missing:
        if prefs.get("question"):
            return ChatResponse(type="question", message=prefs["question"],
                                quick_replies=prefs.get("quick_replies") or missing.quick_replies)
        return missing

    opts = _clean(prefs)
    days = int(opts.pop("days", 1) or 1)
    opts.pop("budget", None)
    budget = float(prefs["budget"])

    if days > 1:
        trip = [Plan(**d) for d in build_trip(days=days, lat=lat, lng=lng, budget=budget, **opts) if d["stops"]]
        if not trip:
            return ChatResponse(type="message", message="I couldn't source enough for that trip nearby. A larger budget or different vibe?")
        title = f"Your {len(trip)}-day {opts.get('vibe','').replace('_',' ')} trip".strip()
        return ChatResponse(type="itinerary", message=f"{title} — arranged day by day.", days=trip, title=title)

    plan_dict = build_plan(lat=lat, lng=lng, budget=budget, **opts)
    if not plan_dict["stops"]:
        return ChatResponse(type="message", message="I couldn't source enough open spots nearby for that. A larger budget or different vibe?")
    plan = Plan(**plan_dict)
    return ChatResponse(type="itinerary", message=plan.intro or "Your plan:", plan=plan)

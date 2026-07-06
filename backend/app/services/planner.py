"""Itinerary planner — turns budget + vibe + context into an ordered plan of real
nearby places. Optimises for: stops CLOSE together (no crossing town), best value
(great rating for the price), and a hidden-gem or two. Uses Yelp (ratings/prices)
when keyed, falls back to OpenStreetMap. An optional LLM writes the narration.
"""
import math
import random

from app.services import yelp
from app.services.hotspots import fetch_hotspots
from app.services import llm
from app.services import weather as weather_svc
from app.services import events as events_svc

# Indoor-only activity set for wet/cold days.
INDOOR_ACTIVITIES = "arcades,escapegames,bowling,poolhalls,lasertag,karaoke,trampoline,museums,aquariums"

PRICE_COST = {"$": 15, "$$": 30, "$$$": 65, "$$$$": 110}
PRICE_LEVEL = {"$": 1, "$$": 2, "$$$": 3, "$$$$": 4}

# "activity" = real things to do (aquarium, arcade, escape room, museum, bowling…).
# "leisure"  = evening vibes (lounge, hookah, cocktail/live-music, karaoke…).
# Every plan is built as activity + food + leisure so it's never all restaurants.
SLOT_SPECS = {
    "cafe":    {"label": "Coffee & warm-up", "icon": "☕", "yelp": {"categories": "coffee,cafes"}, "osm": "food", "base": 8},
    "scenic":  {"label": "Scenic spot",      "icon": "🌇", "yelp": {"categories": "parks,landmarks", "term": "scenic view"}, "osm": "nature", "base": 0},
    "activity":{"label": "Activity",         "icon": "🎡", "yelp": {"categories": "aquariums,zoos,museums,galleries,arcades,escapegames,amusementparks,bowling,active,arts", "term": "things to do"}, "osm": "activities", "base": 28},
    "lunch":   {"label": "Lunch",            "icon": "🥗", "yelp": {"categories": "restaurants", "term": "lunch"}, "osm": "food", "base": 18},
    "dinner":  {"label": "Dinner",           "icon": "🍽️", "yelp": {"categories": "restaurants", "term": "dinner"}, "osm": "food", "base": 30},
    "leisure": {"label": "Vibes & drinks",   "icon": "🎶", "yelp": {"categories": "lounges,hookah_bars,cocktailbars,karaoke,comedyclubs,musicvenues,bars"}, "osm": "party", "base": 18},
    "drinks":  {"label": "Drinks",           "icon": "🍸", "yelp": {"categories": "bars,cocktailbars"}, "osm": "party", "base": 15},
    "dessert": {"label": "Sweet finish",     "icon": "🍰", "yelp": {"categories": "desserts,icecream"}, "osm": "food", "base": 10},
}

# Each vibe = activity + a meal + a leisure/finish. Price band scales with vibe.
VIBE_PLANS = {
    "chill":       {"price": "1,2",   "slots": ["activity", "dinner", "dessert"]},
    "romantic":    {"price": "2,3",   "slots": ["activity", "dinner", "leisure"]},
    "adventurous": {"price": "1,2,3", "slots": ["activity", "dinner", "leisure"]},
    "extravagant": {"price": "3,4",   "slots": ["activity", "dinner", "leisure"]},
    "night_out":   {"price": "2,3",   "slots": ["activity", "dinner", "leisure"]},
}
DEFAULT_VIBE = "romantic"

# Time of day overrides the slot template (evening falls through to the vibe).
TIME_PLANS = {
    "morning":   ["cafe", "activity", "lunch"],
    "afternoon": ["activity", "lunch", "leisure"],
    "night":     ["activity", "dinner", "leisure"],
}

# Transport shapes how far stops can be and how hard we penalise distance so the
# plan stays walkable/tight unless you've got a car.
TRANSPORT = {
    "walk":    {"radius": 1500, "penalty": 1.6, "cluster": 900},
    "transit": {"radius": 4500, "penalty": 0.6, "cluster": 2500},
    "car":     {"radius": 9000, "penalty": 0.25, "cluster": 6000},
    "any":     {"radius": 4000, "penalty": 0.8, "cluster": 2200},
}


def _haversine_km(a_lat, a_lng, b_lat, b_lng):
    R = 6371
    dlat = math.radians(b_lat - a_lat)
    dlng = math.radians(b_lng - a_lng)
    x = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * math.sin(dlng / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(x))


def _est_cost(cand, slot):
    return PRICE_COST.get(cand.get("price"), slot["base"])


# Fun, real activity categories keyed to who's going — so a boys' day gets
# arcades/karting/paintball/escape rooms, not an art gallery.
def activity_categories(group_type, vibe, interests):
    it = (interests or "").lower()
    competitive = "arcades,escapegames,gokarts,lasertag,paintball,axethrowing,minigolf,bowling,trampoline,karaoke"
    if any(w in it for w in ["paintball", "arcade", "escape", "kart", "laser", "axe", "bowling",
                              "competitive", "mini golf", "minigolf", "trampoline", "climb", "karaoke"]):
        return competitive
    if group_type == "friends" or any(w in it for w in ["boys", "guys", "bros", "bachelor", "squad", "buddies"]):
        return competitive
    # "fun & exciting" energy → active/competitive, NOT a quiet gallery.
    if vibe in ("adventurous", "night_out"):
        return competitive
    if group_type == "date" or vibe == "romantic":
        return "aquariums,galleries,observatories,wineries,museums,minigolf,arcades"
    if group_type == "family":
        return "aquariums,zoos,amusementparks,minigolf,bowling,arcades,trampoline,museums"
    # sensible default: fun, hands-on — deliberately no galleries/museums so they
    # don't win on rating for someone who just wants a good time.
    return "arcades,escapegames,gokarts,bowling,minigolf,aquariums,trampoline"


_CUISINES = ["korean bbq", "kbbq", "bbq", "sushi", "ramen", "korean", "japanese", "italian",
             "steakhouse", "steak", "burgers", "burger", "pizza", "thai", "indian", "chinese",
             "dim sum", "mexican", "tacos", "seafood", "vietnamese", "pho", "mediterranean",
             "greek", "hotpot", "hot pot", "noodles"]


def cuisine_term(interests, dietary):
    s = f"{interests or ''} {dietary or ''}".lower()
    for w in _CUISINES:
        if w in s:
            return w
    return None


def _gather(anchor, slot_key, price_pref, radius, dietary, term_override=None, cat_override=None):
    slot = SLOT_SPECS[slot_key]
    term = slot["yelp"].get("term")
    if dietary and slot_key in ("lunch", "dinner"):
        term = f"{dietary} {term or ''}".strip()
    if term_override:                       # e.g. "escape room" / "korean bbq"
        term = term_override
    categories = cat_override or slot["yelp"].get("categories")
    cands = yelp.search(anchor[0], anchor[1], term=term,
                        categories=categories,
                        price=price_pref, radius=radius, limit=15, sort_by="rating")
    if len(cands) < 5:
        for h in fetch_hotspots(slot["osm"], lat=anchor[0], lng=anchor[1], radius=radius):
            cands.append({"source": "osm", "name": h["name"], "lat": h["lat"], "lng": h["lng"],
                          "rating": None, "review_count": None, "price": None,
                          "categories": [h.get("subtype") or slot["osm"]],
                          "address": h.get("address"), "image": None, "url": h.get("website")})
    return cands


def _score(c, anchor, penalty, want_gem):
    """Higher is better. Balances rating, closeness to the running anchor, value
    (cheaper wins ties), and a bonus for hidden gems (well-rated, few reviews)."""
    rating = c.get("rating") or 3.6                      # neutral for unrated OSM
    dist = _haversine_km(anchor[0], anchor[1], c["lat"], c["lng"])
    level = PRICE_LEVEL.get(c.get("price"), 2)
    score = rating * 2.0 - dist * penalty - (level - 1) * 0.3   # value: cheaper edges ahead
    rc = c.get("review_count")
    if want_gem and rc is not None and rating >= 4.0 and rc < 350:
        score += 0.8                                     # reward the under-the-radar spot
    return score


def _pick(cands, used, anchor, penalty, want_gem, vary=False):
    ranked = sorted(
        (c for c in cands if c.get("name") and c["name"].lower() not in used),
        key=lambda c: _score(c, anchor, penalty, want_gem), reverse=True)
    if not ranked:
        return None
    # On a "try another", pick from the strong top few for genuine variety.
    if vary and len(ranked) > 1:
        return random.choice(ranked[:min(4, len(ranked))])
    return ranked[0]


def _slots_for(vibe, time_of_day, group_type):
    slots = list(TIME_PLANS.get(time_of_day) or VIBE_PLANS[vibe]["slots"])
    # No bars for family / kids or if they've asked to stay sober.
    if group_type in ("family", "kids"):
        slots = ["dessert" if s == "drinks" else s for s in slots]
    return slots


def build_plan(*, lat, lng, budget, vibe=DEFAULT_VIBE, party_size=2, transport="any",
               time_of_day=None, group_type=None, dietary="", interests="",
               radius=None, exclude=None, vary=False):
    vibe = vibe if vibe in VIBE_PLANS else DEFAULT_VIBE
    price_pref = VIBE_PLANS[vibe]["price"]
    tconf = TRANSPORT.get(transport, TRANSPORT["any"])
    radius = radius or tconf["radius"]
    used = set(exclude or ())
    slots = _slots_for(vibe, time_of_day, group_type)

    # Weather-aware: on a wet/cold day, keep it indoors — swap the outdoor scenic
    # stop for a cosy cafe and force indoor activities.
    wx = weather_svc.get_weather(lat, lng)
    bad_weather = bool(wx and (wx["rainy"] or wx["cold"]))
    if bad_weather:
        slots = ["cafe" if s == "scenic" else s for s in slots]

    # Surface the hidden gem on the activity if there is one, else the last stop.
    gem_index = slots.index("activity") if "activity" in slots else len(slots) - 1

    anchor = (lat, lng)      # each pick pulls the next search toward the last stop
    stops = []
    for i, slot_key in enumerate(slots):
        slot = SLOT_SPECS[slot_key]
        # route the search: group-aware fun for activities, cuisine for meals.
        term_override = cat_override = None
        cz = cuisine_term(interests, dietary)
        if slot_key == "activity":
            cat_override = INDOOR_ACTIVITIES if bad_weather else activity_categories(group_type, vibe, interests)
            if interests and not cz:
                term_override = interests          # e.g. "escape room"
        elif slot_key in ("dinner", "lunch") and cz:
            term_override = cz                     # e.g. "korean bbq"
        # tighter search radius around the running anchor keeps stops together;
        # if nothing decent is that close, widen to the full radius before skipping.
        r = tconf["cluster"] if i > 0 else radius
        cands = _gather(anchor, slot_key, price_pref, r, dietary, term_override, cat_override)
        pick = _pick(cands, used, anchor, tconf["penalty"], (i == gem_index), vary)
        if not pick and r < radius:
            cands = _gather(anchor, slot_key, price_pref, radius, dietary, term_override, cat_override)
            pick = _pick(cands, used, anchor, tconf["penalty"], (i == gem_index), vary)
        if not pick:
            continue
        used.add(pick["name"].lower())
        anchor = (pick["lat"], pick["lng"])
        stops.append({
            "slot": slot_key, "label": slot["label"], "icon": slot["icon"],
            "name": pick["name"], "lat": pick["lat"], "lng": pick["lng"],
            "rating": pick.get("rating"), "price": pick.get("price"),
            "address": pick.get("address"), "image": pick.get("image"),
            "url": pick.get("url"), "source": pick.get("source"),
            "est_cost": _est_cost(pick, slot), "categories": pick.get("categories") or [],
        })

    def total():
        return sum(s["est_cost"] for s in stops) * max(1, party_size)

    # Only trim on a real overage (estimates are rough), and drop the least
    # essential first — a dessert/drink before ever cutting the activity, so the
    # plan keeps its activity + food + leisure shape.
    DROP_ORDER = {"dessert": 0, "cafe": 1, "drinks": 1, "leisure": 1, "scenic": 2, "activity": 3}
    while stops and total() > budget * 1.15 and len(stops) > 2:
        droppable = [s for s in stops if s["slot"] not in ("dinner", "lunch")]
        if not droppable:
            break
        stops.remove(min(droppable, key=lambda s: DROP_ORDER.get(s["slot"], 5)))

    # how spread out the plan ended up (for the UI / narration)
    spread = 0.0
    for a, b in zip(stops, stops[1:]):
        spread += _haversine_km(a["lat"], a["lng"], b["lat"], b["lng"])

    # Live events happening near here (concerts, games, comedy) — surfaced as
    # options the guest can build around, not forced into the fixed stops.
    events = []
    if events_svc.available():
        cls = events_svc.classification_for(vibe, interests)
        events = events_svc.search_events(lat, lng, radius_km=25, size=8, classification=cls)[:3]

    plan = {
        "vibe": vibe, "budget": budget, "party_size": party_size, "currency": "USD",
        "estimated_cost": total(), "center": {"lat": lat, "lng": lng},
        "walk_km": round(spread, 1), "stops": stops,
        "weather": (wx["summary"] if wx else None),
        "events": events,
    }
    _narrate(plan, interests, group_type, time_of_day, dietary, wx, events)
    return plan


def build_trip(*, days, lat, lng, budget, **opts):
    days = max(1, min(days, 5))
    per_day = budget / days
    used, trip = set(), []
    for d in range(days):
        plan = build_plan(lat=lat, lng=lng, budget=per_day, exclude=used, **opts)
        plan["day"] = d + 1
        for s in plan["stops"]:
            used.add(s["name"].lower())
        trip.append(plan)
    return trip


_START_HINT = {"morning": "10:00 AM", "afternoon": "1:00 PM", "night": "8:00 PM"}


def _narrate(plan, interests, group_type, time_of_day, dietary, wx=None, events=None):
    stops = plan["stops"]
    if llm.available() and stops:
        listing = "\n".join(
            f"{i+1}. {s['label']} — {s['name']}"
            + (f" ({s['price']}, {s['rating']}★)" if s.get('rating') else "")
            + (f" [{', '.join(s['categories'][:2])}]" if s.get('categories') else "")
            + f"  ~${s['est_cost']}/pp"
            for i, s in enumerate(stops))
        ctx = ", ".join(filter(None, [
            f"group: {group_type}" if group_type else "",
            f"time: {time_of_day}" if time_of_day else "",
            f"dietary: {dietary}" if dietary else "",
            f"they specifically want: {interests}" if interests else "",
            f"weather today: {wx['summary']} (kept it indoors)" if wx and (wx.get("rainy") or wx.get("cold")) else "",
        ]))
        ev_line = ""
        if events:
            ev_line = "Live events near here tonight: " + "; ".join(
                f"{e['name']} at {e['venue']}" + (f" {e['time'][:5]}" if e.get('time') else "")
                for e in events if e.get("name"))
        start = _START_HINT.get(time_of_day, "6:00 PM")
        msg = [
            {"role": "system", "content":
             "You are a sharp, in-the-know local concierge. You are given a FIXED, ordered "
             "list of real venues (already chosen and close together). Do NOT invent or swap "
             "venues — narrate THESE. Make it feel like a friend who knows the city planning a "
             "day people will remember. Return JSON: "
             '{"intro": str, "stops": [{"time": str, "desc": str}, ...], "tip": str}. '
             "intro = 2-3 sentences reasoning about the group and why this plan works. "
             "stops = one per venue IN ORDER: a clock time (schedule them realistically from the "
             "start time, allowing travel + dwell) and 1-2 vivid, specific sentences on what to do "
             "there and why it fits. tip = one punchy closing line ('if it were my crew…'). "
             "If a real live event is provided and fits the vibe, casually mention it as an "
             "option in the intro or tip (with its time) — do NOT put it in stops. "
             "Confident, warm, concrete. No markdown."},
            {"role": "user", "content":
             f"Vibe: {plan['vibe']}. Budget: ${plan['budget']} for {plan['party_size']}. "
             f"Start around {start}. Context — {ctx or 'none given'}. "
             f"All stops are within ~{plan['walk_km']}km of each other.\nVENUES:\n{listing}"
             + (f"\n{ev_line}" if ev_line else "")},
        ]
        data = llm.chat_json(msg)
        if data and isinstance(data.get("stops"), list) and data["stops"]:
            plan["intro"] = data.get("intro") or _template_intro(plan)
            plan["tip"] = data.get("tip")
            for s, extra in zip(stops, data["stops"]):
                if isinstance(extra, dict):
                    s["time"] = extra.get("time")
                    s["why"] = extra.get("desc") or s.get("why")
            return
    # deterministic fallback
    plan["intro"] = _template_intro(plan)
    for s in stops:
        bits = []
        if s.get("rating"):
            bits.append(f"{s['rating']}★" + (f" · {s['price']}" if s.get("price") else ""))
        if s.get("categories"):
            bits.append(s["categories"][0])
        s["why"] = " · ".join(bits) or f"A solid {s['label'].lower()} nearby."


def _template_intro(plan):
    n = len(plan["stops"])
    close = f" all within ~{plan['walk_km']}km" if plan.get("walk_km") else ""
    return (f"A {plan['vibe']} plan — {n} stop{'s' if n != 1 else ''}{close}, "
            f"about ${plan['estimated_cost']} for {plan['party_size']}.")

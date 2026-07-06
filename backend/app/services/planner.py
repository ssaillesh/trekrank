"""Itinerary planner — turns budget + vibe + context into an ordered plan of real
nearby places. Optimises for: stops CLOSE together (no crossing town), best value
(great rating for the price), and a hidden-gem or two. Uses Yelp (ratings/prices)
when keyed, falls back to OpenStreetMap. An optional LLM writes the narration.
"""
import math

from app.services import yelp
from app.services.hotspots import fetch_hotspots
from app.services import llm

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


def _gather(anchor, slot_key, price_pref, radius, dietary, term_override=None):
    slot = SLOT_SPECS[slot_key]
    term = slot["yelp"].get("term")
    if dietary and slot_key in ("lunch", "dinner"):
        term = f"{dietary} {term or ''}".strip()
    if term_override:                       # e.g. "aquarium" for the activity slot
        term = term_override
    cands = yelp.search(anchor[0], anchor[1], term=term,
                        categories=slot["yelp"].get("categories"),
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


def _pick(cands, used, anchor, penalty, want_gem):
    ranked = sorted(
        (c for c in cands if c.get("name") and c["name"].lower() not in used),
        key=lambda c: _score(c, anchor, penalty, want_gem), reverse=True)
    return ranked[0] if ranked else None


def _slots_for(vibe, time_of_day, group_type):
    slots = list(TIME_PLANS.get(time_of_day) or VIBE_PLANS[vibe]["slots"])
    # No bars for family / kids or if they've asked to stay sober.
    if group_type in ("family", "kids"):
        slots = ["dessert" if s == "drinks" else s for s in slots]
    return slots


def build_plan(*, lat, lng, budget, vibe=DEFAULT_VIBE, party_size=2, transport="any",
               time_of_day=None, group_type=None, dietary="", interests="",
               radius=None, exclude=None):
    vibe = vibe if vibe in VIBE_PLANS else DEFAULT_VIBE
    price_pref = VIBE_PLANS[vibe]["price"]
    tconf = TRANSPORT.get(transport, TRANSPORT["any"])
    radius = radius or tconf["radius"]
    used = set(exclude or ())
    slots = _slots_for(vibe, time_of_day, group_type)

    # Surface the hidden gem on the activity if there is one, else the last stop.
    gem_index = slots.index("activity") if "activity" in slots else len(slots) - 1

    anchor = (lat, lng)      # each pick pulls the next search toward the last stop
    stops = []
    for i, slot_key in enumerate(slots):
        slot = SLOT_SPECS[slot_key]
        # bias the activity search toward whatever the guest specifically asked for
        term_override = interests if (slot_key == "activity" and interests) else None
        # tighter search radius around the running anchor keeps stops together;
        # if nothing decent is that close, widen to the full radius before skipping.
        r = tconf["cluster"] if i > 0 else radius
        cands = _gather(anchor, slot_key, price_pref, r, dietary, term_override)
        pick = _pick(cands, used, anchor, tconf["penalty"], want_gem=(i == gem_index))
        if not pick and r < radius:
            cands = _gather(anchor, slot_key, price_pref, radius, dietary, term_override)
            pick = _pick(cands, used, anchor, tconf["penalty"], want_gem=(i == gem_index))
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

    plan = {
        "vibe": vibe, "budget": budget, "party_size": party_size, "currency": "USD",
        "estimated_cost": total(), "center": {"lat": lat, "lng": lng},
        "walk_km": round(spread, 1), "stops": stops,
    }
    _narrate(plan, interests, group_type, time_of_day, dietary)
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


def _narrate(plan, interests, group_type, time_of_day, dietary):
    stops = plan["stops"]
    if llm.available() and stops:
        listing = "\n".join(
            f"- {s['label']}: {s['name']}"
            + (f" ({s['price']}, {s['rating']}★)" if s.get('rating') else "")
            + (f" [{', '.join(s['categories'][:2])}]" if s.get('categories') else "")
            for s in stops)
        ctx = ", ".join(filter(None, [
            f"for {group_type}" if group_type else "",
            f"{time_of_day}" if time_of_day else "",
            f"{dietary} food" if dietary else "",
            f"interests: {interests}" if interests else "",
        ]))
        msg = [
            {"role": "system", "content":
             "You are a sharp, polished concierge — efficient, tasteful, minimal fluff. "
             "Given a fixed itinerary of real nearby places, write a one-line intro and a "
             "crisp reason (max 14 words) for each stop, noting why it fits the guest. "
             'Return JSON {"intro": str, "why": [str,...]} with one why per stop in order.'},
            {"role": "user", "content":
             f"Vibe {plan['vibe']}, ${plan['budget']} for {plan['party_size']} ({ctx or 'no extra context'}). "
             f"Stops are within ~{plan['walk_km']}km total.\n{listing}"},
        ]
        data = llm.chat_json(msg)
        if data and isinstance(data.get("why"), list):
            plan["intro"] = data.get("intro") or _template_intro(plan)
            for s, why in zip(stops, data["why"]):
                s["why"] = why
            return
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

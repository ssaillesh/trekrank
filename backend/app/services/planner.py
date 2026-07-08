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
from app.services import experience

# Indoor-only activity set for wet/cold days.
INDOOR_ACTIVITIES = "arcades,escapegames,bowling,poolhalls,lasertag,karaoke,trampoline,museums,aquariums"

PRICE_COST = {"$": 15, "$$": 30, "$$$": 65, "$$$$": 110}
PRICE_LEVEL = {"$": 1, "$$": 2, "$$$": 3, "$$$$": 4}

# How much the fun/hype signal counts (activity & leisure slots only). Tuned so a
# ~1.5-star gap can flip on excitement (paintball 3.5★ vs gallery 5★) but a
# genuinely bad place can't ride "fun" past a much better one. rating contributes
# rating*2.0 (≈2 pts/star); fun contributes up to fun_factor*1.3 (≈6.5 max).
FUN_WEIGHT = 1.3

# How much popularity/buzz counts. Higher = favour the busy, well-known, trendy
# spots a younger crowd wants (Cactus Club-type places with thousands of reviews)
# over tiny high-rated gems. log10(reviews) so 2000 reviews ≈ 3.3, 80 ≈ 1.9.
BUZZ_WEIGHT = 0.7

# "activity" = real things to do (aquarium, arcade, escape room, museum, bowling…).
# "leisure"  = evening vibes (lounge, hookah, cocktail/live-music, karaoke…).
# Every plan is built as activity + food + leisure so it's never all restaurants.
SLOT_SPECS = {
    "cafe":    {"label": "Coffee & warm-up", "icon": "☕", "yelp": {"categories": "coffee,cafes"}, "osm": "food", "base": 8},
    "scenic":  {"label": "Scenic & free",    "icon": "🌇", "yelp": {"categories": "parks,beaches,gardens,landmarks", "term": "scenic view"}, "osm": "nature", "base": 0},
    "activity":{"label": "Activity",         "icon": "🎡", "yelp": {"categories": "aquariums,zoos,museums,galleries,arcades,escapegames,amusementparks,bowling,active,arts", "term": "things to do"}, "osm": "activities", "base": 28},
    "lunch":   {"label": "Lunch",            "icon": "🥗", "yelp": {"categories": "restaurants", "term": "lunch"}, "osm": "food", "base": 18},
    "dinner":  {"label": "Dinner",           "icon": "🍽️", "yelp": {"categories": "restaurants", "term": "dinner"}, "osm": "food", "base": 30},
    "leisure": {"label": "Vibes & drinks",   "icon": "🎶", "yelp": {"categories": "danceclubs,nightlife,lounges,cocktailbars,hookah_bars,karaoke,comedyclubs,musicvenues,bars"}, "osm": "party", "base": 18},
    "drinks":  {"label": "Drinks",           "icon": "🍸", "yelp": {"categories": "bars,cocktailbars"}, "osm": "party", "base": 15},
    "dessert": {"label": "Sweet finish",     "icon": "🍰", "yelp": {"categories": "desserts,icecream"}, "osm": "food", "base": 10},
    "event":   {"label": "Live event",       "icon": "🎟️", "yelp": {}, "osm": "activities", "base": 40},
}

# Day order used to sequence a user-assembled (picker) itinerary.
SLOT_ORDER = {"cafe": 0, "scenic": 1, "activity": 2, "event": 3, "lunch": 4,
              "dinner": 6, "leisure": 7, "drinks": 7, "dessert": 8}

# Each vibe = activity + a meal + a leisure/finish. Price band scales with vibe.
VIBE_PLANS = {
    "chill":       {"price": "1,2",   "slots": ["activity", "dinner", "dessert"]},
    "romantic":    {"price": "2,3",   "slots": ["activity", "dinner", "leisure"]},
    "adventurous": {"price": "1,2,3", "slots": ["activity", "dinner", "leisure"]},
    "extravagant": {"price": "3,4",   "slots": ["activity", "dinner", "leisure"]},
    "night_out":   {"price": "2,3",   "slots": ["activity", "dinner", "leisure"]},
}
DEFAULT_VIBE = "romantic"

# A "day arc" ordered morning→night. We take the first N depending on how much of
# the day the guest wants filled — so a full day is many stops, an evening is few.
# Repeated slot types (e.g. two activities) resolve to different venues.
ARCS = {
    "morning":   ["cafe", "scenic", "activity", "lunch", "activity", "dinner", "leisure", "dessert"],
    "afternoon": ["scenic", "activity", "lunch", "activity", "dinner", "leisure", "dessert"],
    "evening":   ["scenic", "activity", "dinner", "leisure", "dessert"],
    "night":     ["dinner", "activity", "leisure", "dessert"],
}

# Transport shapes the search. Only "walk" chains stops tightly together (a
# walkable route); everything else searches the whole central-city radius from the
# centre, so you get the best spots across town — but bounded so it stays inside
# the city (~7km of downtown = central Toronto, not Scarborough/Mississauga).
TRANSPORT = {
    "walk":    {"radius": 1600, "penalty": 1.5, "cluster": 1000, "chain": True},
    "transit": {"radius": 7000, "penalty": 0.35, "chain": False},
    "car":     {"radius": 9000, "penalty": 0.2,  "chain": False},
    "any":     {"radius": 7000, "penalty": 0.35, "chain": False},
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
WATER_ACTIVITIES = ("rafting,paddleboarding,surfing,sailing,boatcharters,boattours,jetskis,"
                    "waterparks,snorkeling,divingcenters,beaches,lakes")
_WATER_WORDS = ["kayak", "canoe", "paddle", "waterbike", "water bike", "water biking",
                "jet ski", "jetski", "boat", "sail", "surf", "snorkel", "scuba", "raft",
                "swim", "beach", "on the water", "water activities", "water sports", "lake"]


def wants_water(interests, text=""):
    s = f"{interests or ''} {text or ''}".lower()
    return any(w in s for w in _WATER_WORDS)


def activity_categories(group_type, vibe, interests):
    it = (interests or "").lower()
    competitive = "arcades,escapegames,gokarts,lasertag,paintball,axethrowing,minigolf,bowling,trampoline,karaoke"
    # Water first: kayaking, waterbiking, paddleboarding etc. beat every other
    # routing rule — if they asked to be on the water, put them on the water.
    if wants_water(it):
        return WATER_ACTIVITIES
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
    # No hard price filter — a full candidate pool means "fancier" plans never
    # starve; the price tier is applied as a soft preference in scoring instead.
    # best_match (Yelp's relevance/popularity blend) surfaces the trendy, busy
    # spots better than pure rating; our own scoring then re-ranks with buzz + fun.
    cands = yelp.search(anchor[0], anchor[1], term=term,
                        categories=categories,
                        radius=radius, limit=20, sort_by="best_match")
    if len(cands) < 5:
        for h in fetch_hotspots(slot["osm"], lat=anchor[0], lng=anchor[1], radius=radius):
            cands.append({"source": "osm", "name": h["name"], "lat": h["lat"], "lng": h["lng"],
                          "rating": None, "review_count": None, "price": None,
                          "categories": [h.get("subtype") or slot["osm"]],
                          "address": h.get("address"), "image": None, "url": h.get("website")})
    return cands


def _score(c, anchor, penalty, want_gem, fancy=False, apply_fun=False):
    """Higher is better. Balances rating, closeness, price preference (cheaper for
    value vibes / pricier when they want fancy), a hidden-gem bonus, and — for
    activity/leisure slots — a fun/hype signal that's independent of star rating."""
    rating = c.get("rating") or 3.6                      # neutral for unrated OSM
    dist = _haversine_km(anchor[0], anchor[1], c["lat"], c["lng"])
    level = PRICE_LEVEL.get(c.get("price"), 2)
    score = rating * 2.0 - dist * penalty
    score += (level - 1) * 0.6 if fancy else -(level - 1) * 0.5   # tier preference
    score += math.log10((c.get("review_count") or 0) + 1) * BUZZ_WEIGHT   # buzz / popularity
    if apply_fun:
        # Excitement matters here, not just satisfaction — so a high-energy
        # experience can out-rank a better-reviewed but sleepy one.
        score += experience.fun_factor_for(c.get("categories")) * FUN_WEIGHT
    rc = c.get("review_count")
    if want_gem and not fancy and rc is not None and rating >= 4.0 and rc < 350:
        score += 0.8                                     # reward the under-the-radar spot
    return score


def tag_for(c) -> tuple[str | None, str | None]:
    """A single vibe tag for a candidate so the picker UI can show fun vs mediocre."""
    rating = c.get("rating") or 0
    rc = c.get("review_count") or 0
    fun = experience.fun_factor_for(c.get("categories"))
    if fun >= 4.0 and rc >= 150:
        return ("🔥", "Buzzing")
    if rating >= 4.7 and rc >= 30:
        return ("⭐", "Top-rated")
    if 0 < rc < 60 and rating >= 4.4:
        return ("💎", "Hidden gem")
    if fun <= 2.3:
        return ("😴", "Low-key")
    return (None, None)


def _pick(cands, used, anchor, penalty, want_gem, vary=False, fancy=False, apply_fun=False):
    ranked = sorted(
        (c for c in cands if c.get("name") and c["name"].lower() not in used),
        key=lambda c: _score(c, anchor, penalty, want_gem, fancy, apply_fun), reverse=True)
    if not ranked:
        return None
    # On a "try another", pick from the strong top few for genuine variety.
    if vary and len(ranked) > 1:
        return random.choice(ranked[:min(4, len(ranked))])
    return ranked[0]


def _slots_for(vibe, time_of_day, group_type, length):
    eff = time_of_day or ("night" if vibe == "night_out" else "evening")
    arc = ARCS.get(eff, ARCS["evening"])
    slots = arc[:max(2, min(length, len(arc)))]
    # No bars for family / kids — swap drinks/leisure for dessert.
    if group_type in ("family", "kids"):
        slots = ["dessert" if s in ("drinks", "leisure") else s for s in slots]
    return slots


def build_plan(*, lat, lng, budget, vibe=DEFAULT_VIBE, party_size=2, transport="any",
               time_of_day=None, group_type=None, dietary="", interests="",
               radius=None, exclude=None, vary=False, target_stops=4):
    vibe = vibe if vibe in VIBE_PLANS else DEFAULT_VIBE
    price_pref = VIBE_PLANS[vibe]["price"]
    tconf = TRANSPORT.get(transport, TRANSPORT["any"])
    radius = radius or tconf["radius"]
    used = set(exclude or ())
    slots = _slots_for(vibe, time_of_day, group_type, target_stops)

    # Weather-aware: on a wet/cold day, keep it indoors — swap the outdoor scenic
    # stop for a cosy cafe and force indoor activities.
    wx = weather_svc.get_weather(lat, lng)
    bad_weather = bool(wx and (wx["rainy"] or wx["cold"]))
    if bad_weather:
        slots = ["cafe" if s == "scenic" else s for s in slots]
        # the swap can create a second cafe (morning arc) — make it an activity
        seen_cafe = False
        for i, s in enumerate(slots):
            if s == "cafe":
                if seen_cafe:
                    slots[i] = "activity"
                seen_cafe = True

    # Surface the hidden gem on the activity if there is one, else the last stop.
    gem_index = slots.index("activity") if "activity" in slots else len(slots) - 1

    center = (lat, lng)
    chain = tconf.get("chain", False)   # only walking chains stops tightly together
    fancy = vibe == "extravagant"       # bias picks toward pricier/upscale venues
    anchor = center
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
        elif slot_key == "leisure" and interests and any(
                w in interests.lower() for w in ["club", "clubbing", "dance", "dj", "rave", "nightclub"]):
            term_override = "nightclub"            # they explicitly want to go clubbing
        # Walk mode: chain each stop near the last for a tight walkable route.
        # City mode: search the whole central-city radius from the centre, so you
        # get the best spots across town (still bounded to the city by `radius`).
        if chain:
            search_from = anchor
            r = tconf["cluster"] if i > 0 else radius
        else:
            search_from = center
            r = radius
        # Fun/hype only matters for what you DO — not for a restaurant or cafe.
        apply_fun = slot_key in ("activity", "leisure")
        cands = _gather(search_from, slot_key, price_pref, r, dietary, term_override, cat_override)
        pick = _pick(cands, used, search_from, tconf["penalty"], (i == gem_index), vary, fancy, apply_fun)
        if not pick and r < radius:
            cands = _gather(search_from, slot_key, price_pref, radius, dietary, term_override, cat_override)
            pick = _pick(cands, used, search_from, tconf["penalty"], (i == gem_index), vary, fancy, apply_fun)
        if not pick:
            continue
        used.add(pick["name"].lower())
        if chain:
            anchor = (pick["lat"], pick["lng"])
        stops.append({
            "slot": slot_key, "label": slot["label"], "icon": slot["icon"],
            "name": pick["name"], "lat": pick["lat"], "lng": pick["lng"],
            "rating": pick.get("rating"), "price": pick.get("price"),
            "address": pick.get("address"), "image": pick.get("image"),
            "url": pick.get("url"), "source": pick.get("source"),
            "est_cost": _est_cost(pick, slot), "categories": pick.get("categories") or [],
            # arousal (energy) drives the narration's emotional arc downstream.
            "arousal": experience.arousal_for(pick.get("categories")),
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


# ===================== PICKER: options + build-from-selection =================

def _to_option(c, slot_key):
    emoji, label = tag_for(c)
    return {
        "slot": slot_key, "name": c.get("name"),
        "lat": c.get("lat"), "lng": c.get("lng"),
        "rating": c.get("rating"), "review_count": c.get("review_count"),
        "price": c.get("price"), "categories": c.get("categories") or [],
        "address": c.get("address"), "image": c.get("image"),
        "url": c.get("url"), "source": c.get("source"),
        "est_cost": _est_cost(c, SLOT_SPECS[slot_key]),
        "arousal": experience.arousal_for(c.get("categories")),
        "tag": emoji, "tag_label": label,
    }


def gather_options(slot_key, *, lat, lng, vibe=DEFAULT_VIBE, group_type=None,
                   interests="", dietary="", transport="any", limit=6):
    """Ranked, tagged candidate venues for one category — the picker's menu."""
    tconf = TRANSPORT.get(transport, TRANSPORT["any"])
    price_pref = VIBE_PLANS.get(vibe, VIBE_PLANS[DEFAULT_VIBE])["price"]
    term_override = cat_override = None
    cz = cuisine_term(interests, dietary)
    if slot_key == "activity":
        cat_override = activity_categories(group_type, vibe, interests)
        if interests and not cz:
            term_override = interests
    elif slot_key in ("dinner", "lunch") and cz:
        term_override = cz
    cands = _gather((lat, lng), slot_key, price_pref, tconf["radius"], dietary, term_override, cat_override)
    apply_fun = slot_key in ("activity", "leisure")
    fancy = vibe == "extravagant"
    ranked = sorted((c for c in cands if c.get("name")),
                    key=lambda c: _score(c, (lat, lng), tconf["penalty"], False, fancy, apply_fun),
                    reverse=True)
    seen, out = set(), []
    for c in ranked:
        n = c["name"].lower()
        if n in seen:
            continue
        seen.add(n)
        out.append(_to_option(c, slot_key))
        if len(out) >= limit:
            break
    return out


def option_sections(time_of_day, vibe, group_type):
    """Which category sections the picker shows, given the intent."""
    secs = []
    day = time_of_day in ("morning", "afternoon")
    if day:
        secs.append(("cafe", "Coffee & warm-up", "☕", "optional"))
    secs.append(("scenic", "Scenic & free", "🌇", "optional — beaches, parks, lookouts"))
    secs.append(("activity", "Activity", "🎡", "pick 1–2"))
    if day:
        secs.append(("lunch", "Lunch", "🥗", "pick 1"))
    secs.append(("dinner", "Dinner", "🍽️", "pick 1"))
    if group_type not in ("family", "kids"):
        secs.append(("leisure", "Drinks & vibes", "🎶", "optional"))
    secs.append(("dessert", "Sweet finish", "🍰", "optional"))
    return secs


def build_from_selection(selections, *, lat, lng, party_size=2, budget=0,
                         vibe=DEFAULT_VIBE, interests="", group_type=None,
                         time_of_day=None, dietary=""):
    """Assemble + sequence + narrate an itinerary from the user's picked venues."""
    stops = []
    for sel in selections:
        slot_key = sel.get("slot", "activity")
        spec = SLOT_SPECS.get(slot_key, SLOT_SPECS["activity"])
        stops.append({
            "slot": slot_key, "label": spec["label"], "icon": spec["icon"],
            "name": sel.get("name"), "lat": sel.get("lat"), "lng": sel.get("lng"),
            "rating": sel.get("rating"), "price": sel.get("price"),
            "address": sel.get("address"), "image": sel.get("image"),
            "url": sel.get("url"), "source": sel.get("source"),
            "est_cost": sel.get("est_cost") if sel.get("est_cost") is not None else _est_cost(sel, spec),
            "categories": sel.get("categories") or [],
            "arousal": sel.get("arousal") if sel.get("arousal") is not None else experience.arousal_for(sel.get("categories")),
        })
    stops.sort(key=lambda s: SLOT_ORDER.get(s["slot"], 5))
    total = sum(s["est_cost"] for s in stops) * max(1, party_size)
    spread = 0.0
    for a, b in zip(stops, stops[1:]):
        spread += _haversine_km(a["lat"], a["lng"], b["lat"], b["lng"])
    plan = {
        "vibe": vibe, "budget": budget or total, "party_size": party_size, "currency": "USD",
        "estimated_cost": total, "center": {"lat": lat, "lng": lng},
        "walk_km": round(spread, 1), "stops": stops, "weather": None, "events": [],
    }
    _narrate(plan, interests, group_type, time_of_day, dietary, None, None)
    return plan


_START_HINT = {"morning": "10:00 AM", "afternoon": "1:00 PM", "night": "8:00 PM"}


def _narrate(plan, interests, group_type, time_of_day, dietary, wx=None, events=None):
    stops = plan["stops"]
    if llm.available() and stops:
        # The highest-arousal stop is the emotional peak — narrate the day as a
        # build → peak → wind-down arc around it.
        peak_idx = max(range(len(stops)), key=lambda i: stops[i].get("arousal", 2.5))
        listing = "\n".join(
            f"{i+1}. {s['label']} — {s['name']}"
            + (f" ({s['price']}, {s['rating']}★)" if s.get('rating') else "")
            + (f" [{', '.join(s['categories'][:2])}]" if s.get('categories') else "")
            + f"  ~${s['est_cost']}/pp"
            + (" [PEAK — emotional high point of the day; write it with the most "
               "energy and anticipation]" if i == peak_idx else "")
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
             "You are Layer 3 of a strict pipeline: a formatting + narration engine, NOT a "
             "recommender or search engine. You are given a FIXED, ordered list of REAL venues "
             "(already retrieved from verified sources) and possibly a list of REAL events.\n"
             "ABSOLUTE RULES (zero tolerance):\n"
             "- Narrate ONLY the exact venues in the VENUES list. Never invent, add, swap, rename, "
             "or substitute any place, restaurant, bar, activity, or neighbourhood-as-destination.\n"
             "- Do NOT name any venue, business, or event that is not in the provided lists. Not in "
             "the intro, not in a description, not in the tip. If you're unsure a name was given to "
             "you, do not use it.\n"
             "- Do NOT modify names, ratings, categories, or prices.\n"
             "- Only reference an event if it appears in the EVENTS line, using its exact name/time.\n"
             "- Use your own knowledge ONLY for tone, timing, transitions and readability — never for "
             "facts about specific places.\n"
             "Return JSON: {\"intro\": str, \"stops\": [{\"time\": str, \"desc\": str}, ...], \"tip\": str}.\n"
             "intro = 3-4 sentences about the day/group/vibe — set the scene and the arc of the "
             "night; mention NO venue names that aren't in the list (it's fine to name the listed "
             "ones or none).\n"
             "stops = one per venue IN ORDER: a realistic clock time (from the start time, allowing "
             "travel + dwell) and 2-3 vivid sentences about THAT venue only — what it is, why it "
             "fits this group and budget, and one concrete thing to do or order there (drawn only "
             "from its listed categories/price, never invented specifics like dish names you can't "
             "know). If a stop is free (a park, beach, lookout), say so — free is a feature.\n"
             "tip = one closing line; may reference the listed venues/events by their exact names only.\n"
             "VARY YOUR ENERGY per stop to follow the day's emotional arc: calm, unhurried language "
             "for the early/low-key stops, building excitement and anticipation toward the stop marked "
             "[PEAK], then an easy, satisfied wind-down after it. (This shapes TONE only — it does not "
             "let you add, invent, or reorder any venue.)\n"
             "Confident, warm, concrete. No markdown."},
            {"role": "user", "content":
             f"Vibe: {plan['vibe']}. Budget: ${plan['budget']} for {plan['party_size']}. "
             f"Start around {start}. Context — {ctx or 'none given'}. "
             f"Stops span ~{plan['walk_km']}km total, all within the city.\nVENUES:\n{listing}"
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
    return (f"A {plan['vibe']} plan — {n} stop{'s' if n != 1 else ''}, "
            f"about ${plan['estimated_cost']} for {plan['party_size']}.")

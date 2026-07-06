from pydantic import BaseModel, Field


class PlanStop(BaseModel):
    slot: str
    label: str
    icon: str
    name: str
    lat: float
    lng: float
    rating: float | None = None
    price: str | None = None
    address: str | None = None
    image: str | None = None
    url: str | None = None
    source: str | None = None
    est_cost: int
    categories: list[str] = []
    why: str | None = None
    time: str | None = None


class Center(BaseModel):
    lat: float
    lng: float


class Event(BaseModel):
    name: str
    venue: str | None = None
    lat: float | None = None
    lng: float | None = None
    date: str | None = None
    time: str | None = None
    category: str | None = None
    url: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    image: str | None = None


class Plan(BaseModel):
    vibe: str
    budget: float
    party_size: int
    currency: str = "USD"
    estimated_cost: int
    center: Center
    intro: str | None = None
    tip: str | None = None
    weather: str | None = None
    walk_km: float | None = None
    stops: list[PlanStop]
    events: list[Event] = Field(default_factory=list)
    day: int | None = None


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    lat: float | None = None
    lng: float | None = None


class ChatResponse(BaseModel):
    # "question" → need more info; "itinerary" → plan ready; "message" → info/error
    type: str
    message: str
    quick_replies: list[str] = Field(default_factory=list)
    plan: Plan | None = None          # single-day
    days: list[Plan] = Field(default_factory=list)  # multi-day trip
    title: str | None = None

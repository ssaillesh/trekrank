from pydantic import BaseModel


class Hotspot(BaseModel):
    name: str
    lat: float
    lng: float
    category: str           # food | activities | party | nature | history | shops
    subtype: str | None = None
    address: str | None = None
    website: str | None = None
    wikipedia: str | None = None   # e.g. "en:Casa Loma"
    wikidata: str | None = None
    image: str | None = None


class HotspotCity(BaseModel):
    key: str
    label: str
    lat: float
    lng: float


class HotspotCategory(BaseModel):
    key: str
    label: str
    icon: str


class HotspotMeta(BaseModel):
    cities: list[HotspotCity]
    categories: list[HotspotCategory]


class HotspotFeed(BaseModel):
    city: str
    category: str
    count: int
    hotspots: list[Hotspot]

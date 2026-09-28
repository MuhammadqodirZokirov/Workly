"""Matching: kim taklif oladi, ball va to'lqinlar (TZ 7-bo'lim). Sof funksiyalar — DB bilmaydi."""

import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from .pricing import Duration
from .worker import Experience

# Ball vaznlari: S = 0.30R + 0.20C + 0.15T + 0.15D + 0.10E + 0.10A
WEIGHTS = {"R": 0.30, "C": 0.20, "T": 0.15, "D": 0.15, "E": 0.10, "A": 0.10}
NEW_WORKER_R = 0.9
MIN_RATING = 3.5
MIN_RELIABILITY = 40
MAX_DISTANCE_KM = 10.0
# Uy nuqtasi yo'q, lekin tuman mos — masofa noma'lum; o'rtacha qiymat [D]
DISTRICT_ONLY_KM = 5.0
# Tarix yo'q bo'lsa neytral qiymatlar [D]
NO_HISTORY_C = 0.5
NO_HISTORY_T = 0.5

MAX_WAVES = 3
WAVE_MIN, WAVE_MAX, WAVE_PER_SLOT = 5, 15, 3
NEW_WORKER_EVERY = 5  # har 5 taklifdan 1 tasi "Yangi" ishchiga
OFFER_TTL = timedelta(minutes=10)
URGENT_OFFER_TTL = timedelta(minutes=5)
URGENT_WITHIN = timedelta(hours=2)
AVAILABLE_NOW_TTL = timedelta(hours=8)
MAX_MISSED_STREAK = 3  # ketma-ket 3 ta javobsiz taklif → "Band"

EXPERIENCE_SCORE = {Experience.NONE: 0.0, Experience.Y1_2: 0.33, Experience.Y3_5: 0.66, Experience.Y5_PLUS: 1.0}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def job_hours(duration: str | None) -> int:
    return 4 if duration == Duration.HALF_DAY else 8


def job_window(starts_at: datetime, duration: str | None, days: int) -> tuple[datetime, datetime]:
    """Ish vaqti oralig'i (kesishishni tekshirish uchun). Ko'p kunlikda — butun davr."""
    end = starts_at + timedelta(days=max(days, 1) - 1, hours=job_hours(duration))
    return starts_at, end


def overlaps(a: tuple[datetime, datetime], b: tuple[datetime, datetime]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def fits_schedule(slots: list[tuple[int, time, time]], weekday: int, start: time, hours: int) -> bool:
    """Haftalik jadvalga mosmi. Jadval kiritilmagan bo'lsa — istalgan vaqt [D]."""
    if not slots:
        return True
    end_minutes = start.hour * 60 + start.minute + hours * 60
    for day, s, e in slots:
        e_min = e.hour * 60 + e.minute
        if day == weekday and s <= start and end_minutes <= e_min:
            return True
    return False


@dataclass(frozen=True)
class WorkerSignals:
    worker_id: int
    rating: float | None  # Bayes reytingi; None — "Yangi"
    reviews_count: int
    completion_rate: float | None  # tugatilgan / qabul qilingan, 90 kun
    avg_response_min: float | None
    distance_km: float
    experience: Experience
    days_since_last_job: int | None

    @property
    def is_new(self) -> bool:
        return self.reviews_count < 3


def score(s: WorkerSignals) -> float:
    r = NEW_WORKER_R if s.rating is None else s.rating / 5
    c = NO_HISTORY_C if s.completion_rate is None else s.completion_rate
    t = NO_HISTORY_T if s.avg_response_min is None else 1 - min(s.avg_response_min / 10, 1)
    d = 1 - min(s.distance_km / MAX_DISTANCE_KM, 1)
    e = EXPERIENCE_SCORE[Experience(s.experience)]
    if s.days_since_last_job is None:
        a = 0.0
    else:
        a = 1.0 if s.days_since_last_job <= 7 else 0.5 if s.days_since_last_job <= 30 else 0.0
    w = WEIGHTS
    return round(w["R"] * r + w["C"] * c + w["T"] * t + w["D"] * d + w["E"] * e + w["A"] * a, 4)


def wave_size(free_slots: int) -> int:
    return max(WAVE_MIN, min(WAVE_PER_SLOT * free_slots, WAVE_MAX))


def compose_wave(ranked: list[WorkerSignals], size: int) -> list[WorkerSignals]:
    """Ball bo'yicha saralangan nomzodlardan to'lqin; har 5-o'rin "Yangi" ishchiga (sovuq start)."""
    pool = list(ranked)
    new_pool = [w for w in pool if w.is_new]
    wave: list[WorkerSignals] = []
    while pool and len(wave) < size:
        position = len(wave) + 1
        pick = None
        if position % NEW_WORKER_EVERY == 0:
            pick = next((w for w in new_pool if w in pool), None)
        pick = pick or pool[0]
        wave.append(pick)
        pool.remove(pick)
    return wave


def offer_ttl(starts_at: datetime, now: datetime) -> timedelta:
    return URGENT_OFFER_TTL if starts_at - now <= URGENT_WITHIN else OFFER_TTL

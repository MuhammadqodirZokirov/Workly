"""Reyting va statistika: rezyume, matching va profil uchun (TZ 13)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from workly.domain.workday import RatingInput, bayes_rating, counted_reviews
from workly.infrastructure.db.models import Assignment, Offer, ReliabilityEvent, Review, WorkerProfile


@dataclass
class ReviewView:
    rating: float
    tags: list[str]
    comment: str | None
    is_auto: bool
    created_at: datetime


@dataclass
class WorkerStats:
    rating: float | None
    reviews_count: int  # avtomatik baholarsiz
    reliability: int
    completed_jobs: int
    no_shows_90d: int
    avg_response_minutes: float | None
    recent_reviews: list[ReviewView]


async def visible_reviews(db: AsyncSession, user_id: int, role: str, limit: int = 20) -> list[Review]:
    rows = await db.scalars(
        select(Review)
        .where(
            Review.target_id == user_id,
            Review.target_role == role,
            Review.visible_at.is_not(None),
            Review.hidden_by_admin.is_(False),
        )
        .order_by(Review.created_at.desc())
        .limit(limit)
    )
    return list(rows)


async def rating_of(db: AsyncSession, user_id: int, role: str) -> tuple[float | None, int]:
    reviews = await visible_reviews(db, user_id, role)
    items = [RatingInput(r.rating, r.is_auto) for r in reviews]
    return bayes_rating(items), counted_reviews(items)


async def worker_stats(db: AsyncSession, user_id: int, now: datetime | None = None) -> WorkerStats:
    now = now or datetime.now(UTC)
    reviews = await visible_reviews(db, user_id, "worker")
    items = [RatingInput(r.rating, r.is_auto) for r in reviews]
    completed = await db.scalar(
        select(func.count(Assignment.id)).where(Assignment.worker_id == user_id, Assignment.status == "confirmed")
    )
    no_shows = await db.scalar(
        select(func.count(ReliabilityEvent.id)).where(
            ReliabilityEvent.user_id == user_id,
            ReliabilityEvent.reason == "no_show",
            ReliabilityEvent.created_at >= now - timedelta(days=90),
        )
    )
    responses = (
        await db.execute(
            select(Offer.sent_at, Offer.responded_at).where(
                Offer.worker_id == user_id,
                Offer.responded_at.is_not(None),
                Offer.wave > 0,
                Offer.sent_at >= now - timedelta(days=90),
            )
        )
    ).all()
    minutes = [(r - s).total_seconds() / 60 for s, r in responses]
    profile = await db.get(WorkerProfile, user_id)
    return WorkerStats(
        rating=bayes_rating(items),
        reviews_count=counted_reviews(items),
        reliability=profile.reliability if profile else 100,
        completed_jobs=completed or 0,
        no_shows_90d=no_shows or 0,
        avg_response_minutes=round(sum(minutes) / len(minutes), 1) if minutes else None,
        recent_reviews=[
            ReviewView(r.rating, r.tags or [], r.comment, r.is_auto, r.created_at) for r in reviews if not r.is_auto
        ][:5],
    )

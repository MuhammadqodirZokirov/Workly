"""Ish kuni: check-in, tasdiqlash, yakunlash, almashtirish, baholar va intizom (TZ 10, 11, 13).

Faza 1-lite: jarimalar pulsiz — faqat Ishonchlilik indeksi (TZ 22). Overtime va qo'shimcha vazifa — admin qo'lda.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from workly.domain.errors import Forbidden, InvalidState, NotFound, ValidationFailed
from workly.domain.matching import haversine_km
from workly.domain.orders import AssignmentStatus, OrderStatus, derive_status, derive_workday_status
from workly.domain.users import UserStatus
from workly.domain.workday import (
    AUTO_CONFIRM_AFTER,
    CONFIRM_REMINDER_AFTER,
    EMPLOYER_CONFIRM_WAIT,
    LATE_ESCALATE,
    LATE_PENALTY,
    LATE_REMIND,
    NO_SHOW_AFTER,
    PRIOR_MEAN,
    RELIABILITY_CLEAN_JOB,
    RELIABILITY_SUSPEND_BELOW,
    REMINDERS,
    REVIEW_WINDOW,
    EmployerTag,
    NoShowAction,
    RatingInput,
    WorkerTag,
    bayes_rating,
    check_gps,
    clamp_reliability,
    ensure_checkin_window,
    no_show_penalty,
)
from workly.infrastructure.db.models import (
    Assignment,
    CheckIn,
    EmployerProfile,
    Order,
    ReliabilityEvent,
    Review,
    User,
    WorkerProfile,
)
from workly.infrastructure.storage import FileStorage, sniff_image

from .audit import audit, record_transition

log = logging.getLogger(__name__)
SELFIE_RETENTION = timedelta(days=30)
SUSPEND_LOW_RELIABILITY = timedelta(days=7)
SUSPEND_NO_SHOW = timedelta(days=3)


def utc(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=UTC)


class WorkdayService:
    def __init__(self, db: AsyncSession, storage: FileStorage | None = None, now: datetime | None = None):
        self.db, self.storage = db, storage
        self.now = now or datetime.now(UTC)
        self.outbox: list[tuple[str, tuple]] = []  # bildirishnomalar — commit'dan keyin
        self.files_to_delete: list[str] = []

    # ================= yordamchilar =================
    async def _assignment(self, assignment_id: int) -> Assignment:
        a = await self.db.get(Assignment, assignment_id)
        if a is None:
            raise NotFound("Tayinlov topilmadi", code="ASSIGNMENT_NOT_FOUND")
        await self.db.refresh(a, attribute_names=["order"])
        return a

    async def for_worker(self, user: User, assignment_id: int) -> Assignment:
        a = await self._assignment(assignment_id)
        if a.worker_id != user.id:
            raise NotFound("Tayinlov topilmadi", code="ASSIGNMENT_NOT_FOUND")
        return a

    async def for_employer(self, user: User, assignment_id: int) -> Assignment:
        a = await self._assignment(assignment_id)
        if a.order.employer_id != user.id:
            raise NotFound("Tayinlov topilmadi", code="ASSIGNMENT_NOT_FOUND")
        return a

    def _set_status(self, a: Assignment, status: AssignmentStatus, actor: int | None, reason: str | None = None):
        record_transition(self.db, "assignment", a.id, a.status, status, actor, reason=reason)
        a.status = status

    async def _sync_order(self, order: Order, actor: int | None) -> None:
        await self.db.flush()
        await self.db.refresh(order, attribute_names=["assignments"])
        statuses = [x.status for x in order.assignments]
        new = derive_workday_status(statuses)
        if new is None:
            open_ = statuses.count(AssignmentStatus.OPEN)
            filled = sum(1 for s in statuses if s == AssignmentStatus.ASSIGNED)
            new = derive_status(open_, filled)
        if new != order.status:
            record_transition(self.db, "order", order.id, order.status, new, actor)
            order.status = new

    async def _reliability(self, user_id: int, role: str, delta: int, reason: str, a: Assignment | None) -> int:
        self.db.add(
            ReliabilityEvent(user_id=user_id, role=role, delta=delta, reason=reason, assignment_id=a.id if a else None)
        )
        model = WorkerProfile if role == "worker" else EmployerProfile
        profile = await self.db.get(model, user_id)
        if profile is None:
            return 100
        profile.reliability = clamp_reliability(profile.reliability + delta)
        if role == "worker" and profile.reliability < RELIABILITY_SUSPEND_BELOW:
            # Ishonchlilik < 40 — avtomatik to'xtatish, 7 kun + suhbat (TZ 11)
            profile.suspended_until = max(utc(profile.suspended_until) or self.now, self.now + SUSPEND_LOW_RELIABILITY)
        return profile.reliability

    # ================= check-in =================
    async def checkin(
        self, user: User, assignment_id: int, lat: float, lon: float, accuracy_m: float, selfie: bytes
    ) -> Assignment:
        a = await self.for_worker(user, assignment_id)
        if a.status != AssignmentStatus.ASSIGNED:
            raise InvalidState("Check-in faqat tayinlangan ish uchun", code="INVALID_STATE")
        starts_at = utc(a.order.starts_at)
        ensure_checkin_window(starts_at, self.now)
        distance_m = haversine_km(lat, lon, a.order.lat, a.order.lon) * 1000
        try:
            check_gps(distance_m, accuracy_m)
        except ValidationFailed as e:
            # Muvaffaqiyatsiz urinish ham nizo uchun dalil sifatida saqlanadi (selfie'siz)
            self.db.add(
                CheckIn(
                    assignment_id=a.id,
                    lat=lat,
                    lon=lon,
                    accuracy_m=accuracy_m,
                    distance_m=distance_m,
                    accepted=False,
                    reason=e.code,
                )
            )
            await self.db.commit()
            raise
        if sniff_image(selfie) not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValidationFailed("Selfie rasm bo'lishi kerak", code="UNSUPPORTED_FILE")
        key = await self.storage.save(selfie, prefix=f"checkins/{a.id}")
        self.db.add(
            CheckIn(
                assignment_id=a.id,
                lat=lat,
                lon=lon,
                accuracy_m=accuracy_m,
                distance_m=distance_m,
                selfie_key=key,
                accepted=True,
            )
        )
        a.arrived_at = self.now
        self._set_status(a, AssignmentStatus.ARRIVED, user.id)
        if self.now > starts_at + LATE_REMIND:
            await self._reliability(user.id, "worker", LATE_PENALTY, "late", a)
        await self._sync_order(a.order, user.id)
        self.outbox.append(("workday_event", (a.id, "worker_arrived")))
        return a

    async def confirm_arrival(self, employer: User, assignment_id: int, same_person: bool) -> Assignment:
        """ "Ishchi yetib keldi — shu odammi?" Ha / Yo'q. GPS ishlamasa employer qo'lda tasdiqlaydi (TZ 10)."""
        a = await self.for_employer(employer, assignment_id)
        if a.status == AssignmentStatus.ASSIGNED:
            ensure_checkin_window(utc(a.order.starts_at), self.now)
            if not same_person:
                raise InvalidState("Ishchi hali check-in qilmagan", code="NOT_ARRIVED")
            a.arrived_at = self.now
        elif a.status != AssignmentStatus.ARRIVED:
            raise InvalidState("Bu holatda tasdiqlab bo'lmaydi", code="INVALID_STATE")
        if not same_person:
            a.problem = "identity_mismatch"
            self._set_status(a, AssignmentStatus.DISPUTED, employer.id, reason="identity_mismatch")
            audit(self.db, employer.id, "workday.identity_mismatch", "assignment", a.id)
            self.outbox.append(("workday_event", (a.id, "problem")))
        else:
            a.arrival_confirmed_at = self.now
            self._set_status(a, AssignmentStatus.WORKING, employer.id)
        await self._sync_order(a.order, employer.id)
        return a

    # ================= yakunlash =================
    async def finish(self, user: User, assignment_id: int) -> Assignment:
        a = await self.for_worker(user, assignment_id)
        if a.status not in (AssignmentStatus.ARRIVED, AssignmentStatus.WORKING):
            raise InvalidState("Ish boshlanmagan", code="INVALID_STATE")
        a.finished_at = self.now
        self._set_status(a, AssignmentStatus.FINISHED, user.id)
        self.outbox.append(("workday_event", (a.id, "work_finished")))
        return a

    async def confirm_work(self, employer: User, assignment_id: int, ok: bool, reason: str | None) -> Assignment:
        """ "Ha, bajarildi" yoki "Muammo bor" (Faza 1-lite: nizoni admin qo'lda hal qiladi)."""
        a = await self.for_employer(employer, assignment_id)
        if a.status not in (AssignmentStatus.WORKING, AssignmentStatus.FINISHED):
            raise InvalidState("Bu holatda tasdiqlab bo'lmaydi", code="INVALID_STATE")
        if ok:
            await self._confirm(a, employer.id, auto=False)
        else:
            if not reason or len(reason.strip()) < 20:
                raise ValidationFailed("Muammoni kamida 20 belgida yozing", code="REASON_REQUIRED")
            a.problem = reason.strip()[:300]
            self._set_status(a, AssignmentStatus.DISPUTED, employer.id, reason="employer_problem")
            self.outbox.append(("workday_event", (a.id, "problem")))
        await self._sync_order(a.order, employer.id)
        return a

    async def _confirm(self, a: Assignment, actor: int | None, *, auto: bool) -> None:
        a.finished_at = a.finished_at or self.now
        a.confirmed_at = self.now
        a.auto_confirmed = auto
        self._set_status(a, AssignmentStatus.CONFIRMED, actor, reason="auto" if auto else None)
        # Har muammosiz ish +2 (TZ 11); kechikkan bo'lsa ham ish bajarilgan
        await self._reliability(a.worker_id, "worker", RELIABILITY_CLEAN_JOB, "clean_job", a)
        self.outbox.append(("workday_event", (a.id, "confirmed")))

    async def cash_received(self, user: User, assignment_id: int, amount: int) -> Assignment:
        """Naqd rejim: ishchi "Naqd oldim: X so'm"; kelishilgandan kam bo'lsa — muammo (TZ 9)."""
        a = await self.for_worker(user, assignment_id)
        if a.status not in (AssignmentStatus.FINISHED, AssignmentStatus.CONFIRMED):
            raise InvalidState("Ish hali yakunlanmagan", code="INVALID_STATE")
        if amount < 0:
            raise ValidationFailed("Summa noto'g'ri", code="INVALID_AMOUNT")
        a.cash_received = amount
        expected = a.order.price["worker_price"] * max(a.order.days, 1)
        if amount < expected:
            a.problem = f"cash_short: {amount} < {expected}"
            audit(
                self.db,
                user.id,
                "workday.cash_short",
                "assignment",
                a.id,
                after={"amount": amount, "expected": expected},
            )
            self.outbox.append(("workday_event", (a.id, "problem")))
        await self.db.flush()
        return a

    # ================= almashtirish / kelmaslik =================
    async def replace(self, employer: User, assignment_id: int) -> Assignment:
        """Employer T+30 dan keyin "Almashtiring" (TZ 10)."""
        a = await self.for_employer(employer, assignment_id)
        if a.status != AssignmentStatus.ASSIGNED or self.now < utc(a.order.starts_at) + LATE_ESCALATE:
            raise InvalidState("Almashtirish ishchi 30 daqiqa kechiksa mumkin", code="REPLACE_NOT_ALLOWED")
        await self._open_replacement(a, employer.id, "replaced_by_employer")
        self._set_status(a, AssignmentStatus.REPLACED, employer.id)
        await self._sync_order(a.order, employer.id)
        return a

    async def _open_replacement(self, a: Assignment, actor: int | None, reason: str) -> Assignment:
        order = a.order
        await self.db.refresh(order, attribute_names=["assignments"])
        slot = Assignment(
            order_id=order.id, slot_no=max(x.slot_no for x in order.assignments) + 1, status=AssignmentStatus.OPEN
        )
        self.db.add(slot)
        # Almashtirish ustuvor — yangi to'lqinlar ruxsat etiladi (TZ 7)
        order.waves_sent = 0
        order.matching_alerted_at = None
        audit(self.db, actor, f"workday.{reason}", "assignment", a.id)
        await self.db.flush()
        self.outbox.append(("replacement_wave", (order.id,)))
        return slot

    async def _no_show(self, a: Assignment) -> None:
        since = self.now - timedelta(days=90)
        previous = await self.db.scalar(
            select(func.count(ReliabilityEvent.id)).where(
                ReliabilityEvent.user_id == a.worker_id,
                ReliabilityEvent.reason == "no_show",
                ReliabilityEvent.created_at >= since,
            )
        )
        delta, action = no_show_penalty((previous or 0) + 1)
        a.no_show_at = self.now
        self._set_status(a, AssignmentStatus.NO_SHOW, None, reason=action)
        await self._reliability(a.worker_id, "worker", delta, "no_show", a)
        profile = await self.db.get(WorkerProfile, a.worker_id)
        if action == NoShowAction.SUSPEND_3D and profile:
            profile.suspended_until = max(utc(profile.suspended_until) or self.now, self.now + SUSPEND_NO_SHOW)
        elif action == NoShowAction.BLOCK:
            worker = await self.db.get(User, a.worker_id)
            worker.status = UserStatus.BLOCKED
            audit(self.db, None, "user.auto_block", "user", worker.id, after={"reason": "3_no_shows_90d"})
        await self._open_replacement(a, None, "no_show")
        self.outbox.append(("workday_event", (a.id, "no_show")))

    # ================= baholar =================
    async def review(self, user: User, assignment_id: int, rating: int, tags: list[str], comment: str | None) -> Review:
        a = await self._assignment(assignment_id)
        if a.worker_id == user.id:
            target_id, target_role, allowed = a.order.employer_id, "employer", set(EmployerTag)
        elif a.order.employer_id == user.id:
            target_id, target_role, allowed = a.worker_id, "worker", set(WorkerTag)
        else:
            raise NotFound("Tayinlov topilmadi", code="ASSIGNMENT_NOT_FOUND")
        if a.status != AssignmentStatus.CONFIRMED:
            raise InvalidState("Baho ish tasdiqlangandan keyin", code="INVALID_STATE")
        if self.now > utc(a.confirmed_at) + REVIEW_WINDOW:
            raise InvalidState("Baho muddati (48 soat) tugagan", code="REVIEW_CLOSED")
        if not 1 <= rating <= 5:
            raise ValidationFailed("Baho 1–5", code="INVALID_RATING")
        if bad := [t for t in tags if t not in allowed]:
            raise ValidationFailed("Noto'g'ri teg", code="INVALID_TAG", details=bad)
        exists = await self.db.scalar(
            select(Review.id).where(Review.assignment_id == a.id, Review.author_id == user.id)
        )
        if exists:
            raise InvalidState("Siz allaqachon baholagansiz", code="ALREADY_REVIEWED")
        review = Review(
            assignment_id=a.id,
            author_id=user.id,
            target_id=target_id,
            target_role=target_role,
            rating=rating,
            tags=sorted(set(tags)),
            comment=(comment or "").strip()[:300] or None,
        )
        self.db.add(review)
        await self.db.flush()
        await self._reveal_if_both(a)
        return review

    async def _reveal_if_both(self, a: Assignment) -> None:
        """Ikki tomonlama yashirin: ikkalasi baholagach ochiladi — qasos bahosining oldini oladi (TZ 13)."""
        reviews = list(await self.db.scalars(select(Review).where(Review.assignment_id == a.id)))
        if len(reviews) >= 2:
            for r in reviews:
                r.visible_at = r.visible_at or self.now

    async def current_rating(self, user_id: int, role: str) -> float | None:
        rows = await self.db.execute(
            select(Review.rating, Review.is_auto)
            .where(
                Review.target_id == user_id,
                Review.target_role == role,
                Review.visible_at.is_not(None),
                Review.hidden_by_admin.is_(False),
            )
            .order_by(Review.created_at.desc())
            .limit(20)
        )
        return bayes_rating([RatingInput(r, auto) for r, auto in rows])

    # ================= scheduler qadami =================
    async def tick(self) -> dict:
        stats = {
            "reminders": 0,
            "late": 0,
            "no_show": 0,
            "auto_arrival": 0,
            "auto_confirm": 0,
            "auto_review": 0,
            "selfies_purged": 0,
        }
        rows = list(
            await self.db.scalars(
                select(Assignment)
                .join(Order)
                .where(
                    Assignment.status.in_(
                        [AssignmentStatus.ASSIGNED, AssignmentStatus.ARRIVED, AssignmentStatus.FINISHED]
                    )
                )
            )
        )
        for a in rows:
            await self.db.refresh(a, attribute_names=["order"])
            t = utc(a.order.starts_at)
            tl = dict(a.timeline or {})
            if a.status == AssignmentStatus.ASSIGNED:
                for kind, before in REMINDERS.items():
                    if kind not in tl and t - before <= self.now < t:
                        tl[kind] = self.now.isoformat()
                        self.outbox.append(("workday_event", (a.id, kind)))
                        stats["reminders"] += 1
                if self.now >= t + NO_SHOW_AFTER:
                    await self._no_show(a)
                    stats["no_show"] += 1
                elif self.now >= t + LATE_ESCALATE and "late_30" not in tl:
                    tl["late_30"] = self.now.isoformat()  # moderatorga qo'ng'iroq vazifasi + employerga tanlov
                    self.outbox.append(("workday_event", (a.id, "late_30")))
                    stats["late"] += 1
                elif self.now >= t + LATE_REMIND and "late_15" not in tl:
                    tl["late_15"] = self.now.isoformat()
                    self.outbox.append(("workday_event", (a.id, "late_15")))
                    stats["late"] += 1
            elif a.status == AssignmentStatus.ARRIVED and self.now >= utc(a.arrived_at) + EMPLOYER_CONFIRM_WAIT:
                # Employer 15 daqiqada javob bermadi — GPS va selfie yetarli
                a.arrival_confirmed_at = self.now
                self._set_status(a, AssignmentStatus.WORKING, None, reason="auto")
                stats["auto_arrival"] += 1
            elif a.status == AssignmentStatus.FINISHED:
                finished = utc(a.finished_at)
                if self.now >= finished + AUTO_CONFIRM_AFTER:
                    await self._confirm(a, None, auto=True)
                    stats["auto_confirm"] += 1
                elif self.now >= finished + CONFIRM_REMINDER_AFTER and "confirm_reminder" not in tl:
                    tl["confirm_reminder"] = self.now.isoformat()
                    self.outbox.append(("workday_event", (a.id, "confirm_reminder")))
            a.timeline = tl
            await self._sync_order(a.order, None)

        stats["auto_review"] = await self._auto_reviews()
        stats["selfies_purged"] = await self._purge_selfies()
        await self.db.flush()
        return stats

    async def _auto_reviews(self) -> int:
        """48 soatda baho berilmasa — baholanuvchining joriy o'rtachasi, "avtomatik" belgisi bilan (TZ 13, OS-18)."""
        deadline = self.now - REVIEW_WINDOW
        done = list(
            await self.db.scalars(
                select(Assignment).where(
                    Assignment.status == AssignmentStatus.CONFIRMED,
                    Assignment.confirmed_at <= deadline,
                    Assignment.timeline.is_not(None),
                )
            )
        )
        created = 0
        for a in done:
            if (a.timeline or {}).get("reviews_closed"):
                continue
            await self.db.refresh(a, attribute_names=["order"])
            authors = set((await self.db.scalars(select(Review.author_id).where(Review.assignment_id == a.id))).all())
            pairs = [(a.order.employer_id, a.worker_id, "worker"), (a.worker_id, a.order.employer_id, "employer")]
            for author, target, role in pairs:
                if author not in authors:
                    avg = await self.current_rating(target, role)
                    self.db.add(
                        Review(
                            assignment_id=a.id,
                            author_id=author,
                            target_id=target,
                            target_role=role,
                            rating=avg or PRIOR_MEAN,
                            is_auto=True,
                            visible_at=self.now,
                        )
                    )
                    created += 1
            for r in await self.db.scalars(select(Review).where(Review.assignment_id == a.id)):
                r.visible_at = r.visible_at or self.now
            a.timeline = {**(a.timeline or {}), "reviews_closed": self.now.isoformat()}
        return created

    async def _purge_selfies(self) -> int:
        """Selfie 30 kun saqlanadi; nizodagi ishda — hal bo'lguncha (TZ 19)."""
        rows = await self.db.scalars(
            select(CheckIn)
            .join(Assignment, Assignment.id == CheckIn.assignment_id)
            .where(
                CheckIn.selfie_key.is_not(None),
                CheckIn.created_at <= self.now - SELFIE_RETENTION,
                Assignment.status != AssignmentStatus.DISPUTED,
            )
        )
        count = 0
        for c in rows:
            self.files_to_delete.append(c.selfie_key)
            c.selfie_key = None
            count += 1
        return count

    def ensure_not_self(self, user: User, a: Assignment) -> None:
        if a.worker_id == a.order.employer_id == user.id:
            raise Forbidden()


# Order holati uchun qisqa havola (routerlar uchun)
__all__ = ["WorkdayService", "OrderStatus"]

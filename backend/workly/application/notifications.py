from typing import Protocol


class Notifier(Protocol):
    """Foydalanuvchiga xabar (bot, zaxira — SMS). Xabarda shaxsiy ma'lumot bo'lmaydi (TZ 15-bo'lim)."""

    async def verification_result(self, user_id: int, approved: bool, reason: str | None) -> None: ...

    async def business_verification_result(self, user_id: int, approved: bool, reason: str | None) -> None: ...

    async def offer_new(self, offer_id: int) -> None: ...

    async def worker_assigned(self, offer_id: int) -> None: ...

    async def worker_set_busy(self, user_id: int) -> None: ...

    async def matching_exhausted(self, order_id: int) -> None: ...


class NullNotifier:
    async def verification_result(self, user_id: int, approved: bool, reason: str | None) -> None:
        return None

    async def business_verification_result(self, user_id: int, approved: bool, reason: str | None) -> None:
        return None

    async def offer_new(self, offer_id: int) -> None:
        return None

    async def worker_assigned(self, offer_id: int) -> None:
        return None

    async def worker_set_busy(self, user_id: int) -> None:
        return None

    async def matching_exhausted(self, order_id: int) -> None:
        return None

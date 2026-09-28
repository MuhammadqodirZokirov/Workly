from typing import Protocol


class Notifier(Protocol):
    """Foydalanuvchiga xabar (bot, zaxira — SMS). Xabarda shaxsiy ma'lumot bo'lmaydi (TZ 15-bo'lim)."""

    async def verification_result(self, user_id: int, approved: bool, reason: str | None) -> None: ...

    async def business_verification_result(self, user_id: int, approved: bool, reason: str | None) -> None: ...


class NullNotifier:
    async def verification_result(self, user_id: int, approved: bool, reason: str | None) -> None:
        return None

    async def business_verification_result(self, user_id: int, approved: bool, reason: str | None) -> None:
        return None

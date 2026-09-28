import logging

from aiogram import Router
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
    TelegramUnauthorizedError,
)
from aiogram.types import ErrorEvent

log = logging.getLogger(__name__)


async def errors_handler(event: ErrorEvent):
    """Barcha routerlardagi xatolarni ushlaydi. Logga PII yozilmaydi — faqat update_id."""
    exc, update_id = event.exception, event.update.update_id
    if isinstance(exc, TelegramUnauthorizedError):
        log.error("Bot token noto'g'ri: %s", exc)
    elif isinstance(exc, TelegramForbiddenError):
        log.warning("Forbidden (bot bloklangan?): %s (update_id=%s)", exc, update_id)
    elif isinstance(exc, TelegramRetryAfter):
        log.warning("RetryAfter %ss (update_id=%s)", exc.retry_after, update_id)
    elif isinstance(exc, TelegramBadRequest):
        log.warning("BadRequest: %s (update_id=%s)", exc, update_id)
    elif isinstance(exc, TelegramAPIError):
        log.error("TelegramAPIError: %s (update_id=%s)", exc, update_id)
    else:
        log.error("update_id=%s: %s", update_id, exc, exc_info=exc)
    return True


def create_router() -> Router:
    router = Router(name="errors")
    router.error.register(errors_handler)
    return router

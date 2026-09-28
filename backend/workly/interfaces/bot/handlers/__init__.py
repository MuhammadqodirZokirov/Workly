from aiogram import F, Router

from . import contact, errors, help, offers, start


def setup_routers() -> Router:
    router = Router(name="root")
    # Foydalanuvchi boti faqat shaxsiy chatda ishlaydi
    router.message.filter(F.chat.type == "private")
    router.include_routers(
        errors.create_router(),
        start.create_router(),
        help.create_router(),
        contact.create_router(),
        offers.create_router(),
    )
    return router

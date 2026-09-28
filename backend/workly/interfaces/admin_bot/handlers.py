"""Admin bot menyulari. Til — o'zbek (lotin), foydalanuvchilar: asoschi va xodimlar.

Har saqlashdan oldin ko'rinish va "Saqlaysizmi?" — Ha / Bekor (TZ 16).
"""

from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from workly.application.admin_catalog import AdminCatalogService
from workly.application.admin_ops import AdminOpsService
from workly.application.pricing import PriceService
from workly.domain.errors import DomainError
from workly.domain.pricing import MAX_FACTOR, MIN_FACTOR, bound
from workly.infrastructure.db.models import Specialization, User

UNITS = {"day": "kun", "hour": "soat", "m2": "m²", "guest": "kishi"}
ADMIN_ONLY = "Bu bo'lim faqat admin uchun"


def money(v: int) -> str:
    return f"{v:,}".replace(",", " ")


class Menu(CallbackData, prefix="m"):
    to: str


class Cat(CallbackData, prefix="c"):
    act: str  # open | toggle | spec | new_spec
    id: int


class Dist(CallbackData, prefix="d"):
    id: int


class Price(CallbackData, prefix="p"):
    act: str  # cat | item | edit
    cat: int
    spec: int = 0  # 0 — kategoriya darajasidagi narx


class Rev(CallbackData, prefix="r"):
    id: int


class Confirm(CallbackData, prefix="ok"):
    yes: bool


class NewItem(StatesGroup):
    latin = State()
    ru = State()
    confirm = State()


class PriceEdit(StatesGroup):
    base = State()
    confirm = State()


def kb(rows: list[list[tuple[str, CallbackData | str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=text, callback_data=cb if isinstance(cb, str) else cb.pack())
                for text, cb in row
            ]
            for row in rows
        ]
    )


CONFIRM_KB = kb([[("✅ Ha, saqlash", Confirm(yes=True)), ("✖️ Bekor", Confirm(yes=False))]])


def main_menu(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [[("📊 Bugungi statistika", Menu(to="stats"))]]
    if is_admin:
        rows = [
            [("🗂 Kategoriyalar", Menu(to="cats")), ("💰 Narxlar", Menu(to="prices"))],
            [("📍 Hududlar", Menu(to="dists")), ("⭐ Avtomatik baholar", Menu(to="auto"))],
            *rows,
        ]
    return kb(rows)


def mark(active: bool) -> str:
    return "🟢" if active else "⚪️"


def create_router() -> Router:
    router = Router(name="admin")

    # ---------------- menyu ----------------
    @router.message(CommandStart())
    @router.message(Command("cancel"))
    async def start(message: Message, state: FSMContext, staff: User, is_admin: bool) -> None:
        await state.clear()
        role = "admin" if is_admin else "moderator"
        await message.answer(
            f"Workly admin bot · {escape(staff.full_name or staff.phone or '')} ({role})\n"
            "Signallar shu yerga keladi: yangi verifikatsiya, T+30 qo'ng'iroq, nizolar.",
            reply_markup=main_menu(is_admin),
        )

    @router.callback_query(Menu.filter(F.to == "home"))
    async def home(call: CallbackQuery, state: FSMContext, is_admin: bool) -> None:
        await state.clear()
        await call.message.edit_text("Menyu", reply_markup=main_menu(is_admin))
        await call.answer()

    # ---------------- statistika ----------------
    async def stats_text(db: AsyncSession) -> str:
        b = await AdminOpsService(db).board()
        a = b.assignments
        return (
            f"📊 <b>{b.date}</b>\n"
            f"Buyurtmalar: {sum(b.orders.values())}\n"
            f"Joyida / ishlamoqda: {a.get('arrived', 0) + a.get('working', 0)}\n"
            f"Hali kelmagan: {a.get('assigned', 0)} · kelmadi: {a.get('no_show', 0)}\n"
            f"Tugadi: {a.get('finished', 0) + a.get('confirmed', 0)}\n"
            f"📞 Qo'ng'iroq navbati: {len(b.call_queue)}\n"
            f"⚠️ Nizolar: {b.pending.get('disputes', 0)}\n"
            f"🪪 Verifikatsiya kutmoqda: {b.pending.get('verifications', 0)}\n"
            f"🏢 Biznes tekshiruvi: {b.pending.get('business', 0)}\n"
            f"✋ Tasdiq kutayotgan buyurtma: {b.pending.get('orders_approval', 0)}"
        )

    @router.message(Command("stats"))
    async def stats_cmd(message: Message, db: AsyncSession) -> None:
        await message.answer(await stats_text(db))

    @router.callback_query(Menu.filter(F.to == "stats"))
    async def stats(call: CallbackQuery, db: AsyncSession) -> None:
        await call.message.edit_text(await stats_text(db), reply_markup=kb([[("⬅️ Menyu", Menu(to="home"))]]))
        await call.answer()

    # Qolgan bo'limlar — faqat admin (moderator: statistika va signallar)
    async def deny(call: CallbackQuery) -> None:
        await call.answer(ADMIN_ONLY, show_alert=True)

    # ---------------- kategoriyalar ----------------
    async def show_categories(call: CallbackQuery, db: AsyncSession) -> None:
        cats = await AdminCatalogService(db).categories()
        rows = [[(f"{mark(c.is_active)} {c.name_uz_latn}", Cat(act="open", id=c.id))] for c in cats]
        rows.append([("➕ Yangi kategoriya", Cat(act="new", id=0))])
        rows.append([("⬅️ Menyu", Menu(to="home"))])
        await call.message.edit_text("🗂 Kategoriyalar (🟢 yoqilgan, ⚪️ o'chirilgan)", reply_markup=kb(rows))

    @router.callback_query(Menu.filter(F.to == "cats"))
    async def categories(call: CallbackQuery, db: AsyncSession, is_admin: bool) -> None:
        if not is_admin:
            return await deny(call)
        await show_categories(call, db)
        await call.answer()

    async def show_category(call: CallbackQuery, db: AsyncSession, category_id: int) -> None:
        c = await AdminCatalogService(db).category(category_id)
        await db.refresh(c, attribute_names=["specializations"])
        rows = [
            [
                (
                    f"{mark(c.is_active)} Kategoriya: {'o‘chirish' if c.is_active else 'yoqish'}",
                    Cat(act="toggle", id=c.id),
                )
            ]
        ]
        rows += [[(f"{mark(s.is_active)} {s.name_uz_latn}", Cat(act="spec", id=s.id))] for s in c.specializations]
        rows.append([("➕ Ish turi qo'shish", Cat(act="new_spec", id=c.id))])
        rows.append([("⬅️ Kategoriyalar", Menu(to="cats"))])
        await call.message.edit_text(
            f"<b>{escape(c.name_uz_latn)}</b> / {escape(c.name_uz_cyrl)} / {escape(c.name_ru)}\n"
            "Ish turini bosing — yoqiladi yoki o'chiriladi.",
            reply_markup=kb(rows),
        )

    @router.callback_query(Cat.filter(F.act == "open"))
    async def category(call: CallbackQuery, callback_data: Cat, db: AsyncSession, is_admin: bool) -> None:
        if not is_admin:
            return await deny(call)
        await show_category(call, db, callback_data.id)
        await call.answer()

    @router.callback_query(Cat.filter(F.act.in_({"toggle", "spec"})))
    async def toggle(call: CallbackQuery, callback_data: Cat, db: AsyncSession, staff: User, is_admin: bool) -> None:
        if not is_admin:
            return await deny(call)
        svc = AdminCatalogService(db)
        if callback_data.act == "toggle":
            active = await svc.toggle(staff, "category", callback_data.id)
            category_id = callback_data.id
        else:
            active = await svc.toggle(staff, "specialization", callback_data.id)
            category_id = (await db.get(Specialization, callback_data.id)).category_id
        await show_category(call, db, category_id)
        await call.answer("Yoqildi" if active else "O'chirildi")

    @router.callback_query(Cat.filter(F.act.in_({"new", "new_spec"})))
    async def new_item(call: CallbackQuery, callback_data: Cat, state: FSMContext, is_admin: bool) -> None:
        if not is_admin:
            return await deny(call)
        await state.set_state(NewItem.latin)
        await state.update_data(category_id=callback_data.id if callback_data.act == "new_spec" else None)
        what = "ish turi" if callback_data.act == "new_spec" else "kategoriya"
        await call.message.answer(f"Yangi {what} nomi — o'zbekcha (lotin). Bekor qilish: /cancel")
        await call.answer()

    @router.message(NewItem.latin, F.text)
    async def new_latin(message: Message, state: FSMContext) -> None:
        await state.update_data(latin=message.text)
        await state.set_state(NewItem.ru)
        await message.answer("Endi ruscha nomi:")

    @router.message(NewItem.ru, F.text)
    async def new_ru(message: Message, state: FSMContext, db: AsyncSession) -> None:
        data = await state.get_data()
        try:
            names = AdminCatalogService(db).preview(data["latin"], message.text)
        except DomainError as e:
            await state.set_state(NewItem.latin)
            await message.answer(f"❌ {escape(e.message)}\nLotin nomini qayta yozing:")
            return
        await state.update_data(ru=message.text)
        await state.set_state(NewItem.confirm)
        await message.answer(
            f"Lotin: <b>{escape(names['uz_latn'])}</b>\n"
            f"Kirill (avtomatik): <b>{escape(names['uz_cyrl'])}</b>\n"
            f"Rus: <b>{escape(names['ru'])}</b>\n\nSaqlaysizmi?",
            reply_markup=CONFIRM_KB,
        )

    @router.callback_query(NewItem.confirm, Confirm.filter())
    async def new_confirm(
        call: CallbackQuery, callback_data: Confirm, state: FSMContext, db: AsyncSession, staff: User
    ) -> None:
        data = await state.get_data()
        await state.clear()
        if not callback_data.yes:
            await call.message.edit_text("Bekor qilindi.")
            return await call.answer()
        svc = AdminCatalogService(db)
        try:
            if data.get("category_id"):
                item = await svc.create_specialization(staff, data["category_id"], data["latin"], data["ru"])
            else:
                item = await svc.create_category(staff, data["latin"], data["ru"])
        except DomainError as e:
            await call.message.edit_text(f"❌ {escape(e.message)}")
            return await call.answer()
        await call.message.edit_text(
            f"✅ Saqlandi: <b>{escape(item.name_uz_latn)}</b>\nNarxini «💰 Narxlar» bo'limida belgilang.",
            reply_markup=kb([[("⬅️ Menyu", Menu(to="home"))]]),
        )
        await call.answer()

    # ---------------- hududlar ----------------
    async def show_districts(call: CallbackQuery, db: AsyncSession) -> None:
        rows, row = [], []
        for d in await AdminCatalogService(db).districts():
            row.append((f"{mark(d.is_active)} {d.name_uz_latn}", Dist(id=d.id)))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([("⬅️ Menyu", Menu(to="home"))])
        await call.message.edit_text("📍 Tumanlar — bosing: yoqish / o'chirish", reply_markup=kb(rows))

    @router.callback_query(Menu.filter(F.to == "dists"))
    async def districts(call: CallbackQuery, db: AsyncSession, is_admin: bool) -> None:
        if not is_admin:
            return await deny(call)
        await show_districts(call, db)
        await call.answer()

    @router.callback_query(Dist.filter())
    async def district_toggle(
        call: CallbackQuery, callback_data: Dist, db: AsyncSession, staff: User, is_admin: bool
    ) -> None:
        if not is_admin:
            return await deny(call)
        active = await AdminCatalogService(db).toggle(staff, "district", callback_data.id)
        await show_districts(call, db)
        await call.answer("Yoqildi" if active else "O'chirildi")

    # ---------------- narxlar ----------------
    @router.callback_query(Menu.filter(F.to == "prices"))
    async def prices(call: CallbackQuery, db: AsyncSession, is_admin: bool) -> None:
        if not is_admin:
            return await deny(call)
        cats = await AdminCatalogService(db).categories()
        rows = [[(c.name_uz_latn, Price(act="cat", cat=c.id))] for c in cats if c.is_active]
        rows.append([("⬅️ Menyu", Menu(to="home"))])
        await call.message.edit_text("💰 Kategoriyani tanlang", reply_markup=kb(rows))
        await call.answer()

    async def price_map(db: AsyncSession) -> dict[tuple[int, int | None], object]:
        return {(r.category_id, r.specialization_id): r for r in await PriceService(db).current()}

    @router.callback_query(Price.filter(F.act == "cat"))
    async def price_category(call: CallbackQuery, callback_data: Price, db: AsyncSession, is_admin: bool) -> None:
        if not is_admin:
            return await deny(call)
        c = await AdminCatalogService(db).category(callback_data.cat)
        await db.refresh(c, attribute_names=["specializations"])
        current = await price_map(db)

        def label(name: str, spec_id: int | None) -> str:
            row = current.get((c.id, spec_id))
            return f"{name}: {money(row.base)}" if row else f"{name}: kategoriya narxi"

        rows = [[(label("Kategoriya (umumiy)", None), Price(act="item", cat=c.id, spec=0))]]
        rows += [
            [(label(s.name_uz_latn, s.id), Price(act="item", cat=c.id, spec=s.id))]
            for s in c.specializations
            if s.is_active
        ]
        rows.append([("⬅️ Narxlar", Menu(to="prices"))])
        await call.message.edit_text(f"💰 <b>{escape(c.name_uz_latn)}</b>", reply_markup=kb(rows))
        await call.answer()

    @router.callback_query(Price.filter(F.act == "item"))
    async def price_item(
        call: CallbackQuery, callback_data: Price, state: FSMContext, db: AsyncSession, is_admin: bool
    ) -> None:
        if not is_admin:
            return await deny(call)
        current = await price_map(db)
        spec = callback_data.spec or None
        row = current.get((callback_data.cat, spec)) or current.get((callback_data.cat, None))
        unit = row.unit if row else "day"
        now = (
            f"Hozir: {money(row.base)} so'm / {UNITS.get(unit, unit)} ({money(row.min_price)}–{money(row.max_price)})"
            if row
            else "Narx belgilanmagan"
        )
        await state.set_state(PriceEdit.base)
        await state.update_data(
            cat=callback_data.cat, spec=spec, unit=unit, min_order=row.min_order_amount if row else 0
        )
        await call.message.answer(f"{now}\n\nYangi bazaviy narxni yozing (so'm, masalan 150000). Bekor: /cancel")
        await call.answer()

    @router.message(PriceEdit.base, F.text)
    async def price_base(message: Message, state: FSMContext) -> None:
        digits = "".join(ch for ch in message.text if ch.isdigit())
        base = int(digits) if digits else 0
        if not 1_000 <= base <= 100_000_000:
            await message.answer("Narx 1 000 dan 100 000 000 so'mgacha bo'lsin. Qayta yozing:")
            return
        await state.update_data(base=base)
        await state.set_state(PriceEdit.confirm)
        data = await state.get_data()
        await message.answer(
            f"Yangi narx: <b>{money(base)} so'm / {UNITS.get(data['unit'], data['unit'])}</b>\n"
            f"Min (×0.75): {money(bound(base, MIN_FACTOR))} · Max (×2): {money(bound(base, MAX_FACTOR))}\n"
            "Faqat yangi buyurtmalarga ta'sir qiladi.\n\nSaqlaysizmi?",
            reply_markup=CONFIRM_KB,
        )

    @router.callback_query(PriceEdit.confirm, Confirm.filter())
    async def price_confirm(
        call: CallbackQuery, callback_data: Confirm, state: FSMContext, db: AsyncSession, staff: User
    ) -> None:
        data = await state.get_data()
        await state.clear()
        if not callback_data.yes:
            await call.message.edit_text("Bekor qilindi.")
            return await call.answer()
        try:
            await PriceService(db).set_price(
                staff,
                category_id=data["cat"],
                specialization_id=data["spec"],
                unit=data["unit"],
                base=data["base"],
                min_price=None,
                max_price=None,
                min_order_amount=data["min_order"],
                ip=None,
            )
        except DomainError as e:
            await call.message.edit_text(f"❌ {escape(e.message)}")
            return await call.answer()
        await call.message.edit_text(
            f"✅ Narx saqlandi: {money(data['base'])} so'm", reply_markup=kb([[("⬅️ Menyu", Menu(to="home"))]])
        )
        await call.answer()

    # ---------------- avtomatik baholar ----------------
    async def show_auto(call: CallbackQuery, db: AsyncSession) -> None:
        reviews = await AdminCatalogService(db).auto_reviews()
        lines = [f"#{r.id} · tayinlov {r.assignment_id} · {r.target_role} · {r.rating:.1f}" for r in reviews]
        rows = [[(f"🙈 #{r.id} ni yashirish", Rev(id=r.id))] for r in reviews]
        rows.append([("⬅️ Menyu", Menu(to="home"))])
        text = "⭐ Avtomatik baholar (48 soatda qo'yilmagan — reytingga kirmaydi)\n\n" + (
            "\n".join(lines) if lines else "Hozircha yo'q"
        )
        await call.message.edit_text(text, reply_markup=kb(rows))

    @router.callback_query(Menu.filter(F.to == "auto"))
    async def auto(call: CallbackQuery, db: AsyncSession, is_admin: bool) -> None:
        if not is_admin:
            return await deny(call)
        await show_auto(call, db)
        await call.answer()

    @router.callback_query(Rev.filter())
    async def hide(call: CallbackQuery, callback_data: Rev, db: AsyncSession, staff: User, is_admin: bool) -> None:
        if not is_admin:
            return await deny(call)
        await AdminCatalogService(db).hide_review(staff, callback_data.id)
        await show_auto(call, db)
        await call.answer("Yashirildi")

    return router

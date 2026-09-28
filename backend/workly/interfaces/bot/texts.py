"""Bot matnlari. Kirill varianti lotindan avtomatik olinadi (TZ 18-bo'lim), keyin qo'lda tekshiriladi.
Buyruqlar va havolalar {0}, {1} kabi raqamli joy egalari orqali qo'yiladi — ular transliteratsiya qilinmaydi.
"""

from workly.domain.translit import latin_to_cyrillic
from workly.domain.users import Lang

_LATN = {
    "start": "Assalomu alaykum, {0}!\n\n<b>Workly</b> — ish top. Ishchi top. Ishonchli.",
    "share_phone_ask": "Davom etish uchun telefon raqamingizni yuboring 👇",
    "share_phone_btn": "📱 Raqamni yuborish",
    "open_app": "Ilovani ochish uchun tugmani bosing 👇",
    "open_app_btn": "🚀 Workly ilovasini ochish",
    "phone_ok": "✅ Raqamingiz tasdiqlandi.",
    "phone_not_own": "Iltimos, faqat o'zingizning raqamingizni tugma orqali yuboring.",
    "phone_taken": "Bu raqam boshqa Telegram akkauntga bog'langan. Qo'llab-quvvatlash xizmatiga yozing.",
    "help": "Buyruqlar:\n{0} — Botni ishga tushirish\n{1} — Yordam",
    "throttled": "Juda ko'p so'rov! Biroz kuting.",
    "cmd_start": "Botni ishga tushirish",
    "cmd_help": "Yordam",
    "verification_approved": "✅ Profilingiz tasdiqlandi! Endi ish takliflarini olasiz.",
    "verification_rejected": "❌ Profilingiz tasdiqlanmadi.\nSabab: {0}\n\nIlovada ma'lumotni tuzatib, qayta yuboring.",
    "reason_blurry": "rasm noaniq",
    "reason_mismatch": "ma'lumotlar hujjatga mos emas",
    "reason_underage": "yosh talabga javob bermaydi (18+)",
    "reason_doc_expired": "hujjat muddati o'tgan",
    "reason_duplicate": "bu hujjat bilan boshqa akkaunt mavjud",
    "reason_other": "moderator izohini ilovada ko'ring",
    "business_approved": '✅ Kompaniyangiz tasdiqlandi. Profilda "Tasdiqlangan ish beruvchi" belgisi paydo bo\'ldi.',
    "business_rejected": "❌ Kompaniya tasdiqlanmadi.\nSabab: {0}\n\nIlovada ma'lumotni tuzatib, qayta yuboring.",
    "business_reason_stir_invalid": "STIR topilmadi yoki faol emas",
    "business_reason_company_mismatch": "kompaniya nomi STIR ga mos emas",
    "business_reason_other": "moderator izohini ilovada ko'ring",
    "offer_new": "🔔 <b>Yangi taklif</b>\n{0} · {1}\n📍 {2}, ~{3} km\n🗓 {4} · {5}\n💰 Siz olasiz: <b>{6} so'm</b>{7}\n\n⏱ {8} daqiqa ichida javob bering",
    "offer_extras_night": "\n🌙 Tungi ish",
    "offer_extras_lunch": "\n🍲 Tushlik bor",
    "offer_extras_transport": "\n🚌 Yo'l haqi bor",
    "offer_extras_tools": "\n🧰 Asbobni o'zingiz olib kelasiz",
    "btn_accept": "✅ Qabul",
    "btn_decline": "✖️ Rad",
    "btn_details": "Batafsil",
    "dur_half_day": "yarim kun (4 soat)",
    "dur_day": "1 kun (8 soat)",
    "dur_multi_day": "{0} kun",
    "dur_volume": "ish hajmi bo'yicha",
    "offer_accepted": "✅ Qabul qildingiz! Aniq manzil va ish beruvchi kontakti ilovada.",
    "offer_declined": "Rad etildi. Keyingi takliflarni kutib turing.",
    "offer_gone": "Kechirasiz, bu taklif endi faol emas.",
    "offer_slots_filled": "Kechirasiz, o'rinlar to'lib bo'ldi.",
    "offer_time_conflict": "Shu vaqtda sizda boshqa ish bor.",
    "worker_assigned_employer": "👷 Buyurtma #{0}: ishchi tayinlandi ({1}/{2}). Ishchi kartasi va aloqa ilovada.",
    "worker_busy": 'Ketma-ket 3 ta taklifga javob bermadingiz — holatingiz "Band" qilindi. Ilovada qayta yoqishingiz mumkin.',
    "matching_exhausted_employer": "Buyurtma #{0}: hozircha barcha o'rinlar to'lmadi. Ilovada tanlang: kutish, vaqtni o'zgartirish yoki bekor qilish (to'liq qaytarish bilan).",
    "matching_exhausted_admin": "⚠️ Buyurtma #{0}: 3 to'lqindan keyin to'lmadi ({1}/{2}).",
}

_RU = {
    "start": "Здравствуйте, {0}!\n\n<b>Workly</b> — найди работу. Найди работника. Надёжно.",
    "share_phone_ask": "Чтобы продолжить, отправьте свой номер телефона 👇",
    "share_phone_btn": "📱 Отправить номер",
    "open_app": "Нажмите кнопку, чтобы открыть приложение 👇",
    "open_app_btn": "🚀 Открыть Workly",
    "phone_ok": "✅ Номер подтверждён.",
    "phone_not_own": "Пожалуйста, отправьте свой номер с помощью кнопки.",
    "phone_taken": "Этот номер привязан к другому Telegram-аккаунту. Напишите в поддержку.",
    "help": "Команды:\n{0} — Запустить бота\n{1} — Помощь",
    "throttled": "Слишком много запросов! Подождите немного.",
    "cmd_start": "Запустить бота",
    "cmd_help": "Помощь",
    "verification_approved": "✅ Ваш профиль подтверждён! Теперь вы будете получать предложения работы.",
    "verification_rejected": (
        "❌ Профиль не подтверждён.\nПричина: {0}\n\nИсправьте данные в приложении и отправьте снова."
    ),
    "reason_blurry": "нечёткое фото",
    "reason_mismatch": "данные не совпадают с документом",
    "reason_underage": "возраст не соответствует (18+)",
    "reason_doc_expired": "срок действия документа истёк",
    "reason_duplicate": "с этим документом уже есть другой аккаунт",
    "reason_other": "см. комментарий модератора в приложении",
    "business_approved": "✅ Компания подтверждена. В профиле появился значок «Проверенный работодатель».",
    "business_rejected": (
        "❌ Компания не подтверждена.\nПричина: {0}\n\nИсправьте данные в приложении и отправьте снова."
    ),
    "business_reason_stir_invalid": "ИНН не найден или неактивен",
    "business_reason_company_mismatch": "название компании не соответствует ИНН",
    "business_reason_other": "см. комментарий модератора в приложении",
    "offer_new": "🔔 <b>Новое предложение</b>\n{0} · {1}\n📍 {2}, ~{3} км\n🗓 {4} · {5}\n💰 Вы получите: <b>{6} сум</b>{7}\n\n⏱ Ответьте в течение {8} мин",
    "offer_extras_night": "\n🌙 Ночная работа",
    "offer_extras_lunch": "\n🍲 Обед есть",
    "offer_extras_transport": "\n🚌 Проезд оплачивается",
    "offer_extras_tools": "\n🧰 Нужны свои инструменты",
    "btn_accept": "✅ Принять",
    "btn_decline": "✖️ Отказаться",
    "btn_details": "Подробнее",
    "dur_half_day": "полдня (4 часа)",
    "dur_day": "1 день (8 часов)",
    "dur_multi_day": "{0} дн.",
    "dur_volume": "по объёму работ",
    "offer_accepted": "✅ Вы приняли! Точный адрес и контакт работодателя — в приложении.",
    "offer_declined": "Отказ принят. Ждите следующих предложений.",
    "offer_gone": "Извините, это предложение уже неактивно.",
    "offer_slots_filled": "Извините, все места уже заняты.",
    "offer_time_conflict": "На это время у вас уже есть работа.",
    "worker_assigned_employer": "👷 Заказ #{0}: назначен работник ({1}/{2}). Карточка и контакт — в приложении.",
    "worker_busy": "Вы не ответили на 3 предложения подряд — статус «Занят». Включить снова можно в приложении.",
    "matching_exhausted_employer": "Заказ #{0}: пока не все места заполнены. Выберите в приложении: ждать, изменить время или отменить (с полным возвратом).",
    "matching_exhausted_admin": "⚠️ Заказ #{0}: не заполнен после 3 волн ({1}/{2}).",
}

# Brend nomi va HTML teglar transliteratsiya qilinmaydi
_KEEP = ("<b>", "</b>", "Workly")


def _to_cyrl(text: str) -> str:
    for i, token in enumerate(_KEEP):
        text = text.replace(token, f"\x00{i}\x00")
    text = latin_to_cyrillic(text)
    for i, token in enumerate(_KEEP):
        text = text.replace(f"\x00{i}\x00", token)
    return text


_CYRL = {k: _to_cyrl(v) for k, v in _LATN.items()}

TEXTS = {Lang.UZ_LATN: _LATN, Lang.UZ_CYRL: _CYRL, Lang.RU: _RU}


def t(key: str, lang: str | None, *args) -> str:
    table = TEXTS.get(lang, _LATN)
    text = table.get(key) or _LATN[key]
    return text.format(*args) if args else text


def lang_of(language_code: str | None) -> Lang:
    return Lang.from_telegram(language_code)

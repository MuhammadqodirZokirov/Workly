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

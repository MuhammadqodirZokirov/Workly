"""Bot matnlari. Kirill varianti lotindan avtomatik olinadi (TZ 18-bo'lim), keyin qo'lda tekshiriladi.
Buyruqlar va havolalar {0}, {1} kabi raqamli joy egalari orqali qo'yiladi — ular transliteratsiya qilinmaydi.
"""

from rabotago.domain.translit import latin_to_cyrillic
from rabotago.domain.users import Lang

_LATN = {
    "start": "Assalomu alaykum, {0}!\n\nRabotaGo — kunlik ish va ishchini tez topish xizmati.",
    "share_phone_ask": "Davom etish uchun telefon raqamingizni yuboring 👇",
    "share_phone_btn": "📱 Raqamni yuborish",
    "open_app": "Ilovani ochish uchun tugmani bosing 👇",
    "open_app_btn": "🚀 RabotaGo'ni ochish",
    "phone_ok": "✅ Raqamingiz tasdiqlandi.",
    "phone_not_own": "Iltimos, faqat o'zingizning raqamingizni tugma orqali yuboring.",
    "phone_taken": "Bu raqam boshqa Telegram akkauntga bog'langan. Qo'llab-quvvatlash xizmatiga yozing.",
    "help": "Buyruqlar:\n{0} — Botni ishga tushirish\n{1} — Yordam",
    "throttled": "Juda ko'p so'rov! Biroz kuting.",
    "cmd_start": "Botni ishga tushirish",
    "cmd_help": "Yordam",
}

_RU = {
    "start": "Здравствуйте, {0}!\n\nRabotaGo — сервис быстрого поиска подработки и работников.",
    "share_phone_ask": "Чтобы продолжить, отправьте свой номер телефона 👇",
    "share_phone_btn": "📱 Отправить номер",
    "open_app": "Нажмите кнопку, чтобы открыть приложение 👇",
    "open_app_btn": "🚀 Открыть RabotaGo",
    "phone_ok": "✅ Номер подтверждён.",
    "phone_not_own": "Пожалуйста, отправьте свой номер с помощью кнопки.",
    "phone_taken": "Этот номер привязан к другому Telegram-аккаунту. Напишите в поддержку.",
    "help": "Команды:\n{0} — Запустить бота\n{1} — Помощь",
    "throttled": "Слишком много запросов! Подождите немного.",
    "cmd_start": "Запустить бота",
    "cmd_help": "Помощь",
}

# "RabotaGo" brend nomi transliteratsiya qilinmaydi
_CYRL = {k: latin_to_cyrillic(v.replace("RabotaGo", "\x00")).replace("\x00", "RabotaGo") for k, v in _LATN.items()}

TEXTS = {Lang.UZ_LATN: _LATN, Lang.UZ_CYRL: _CYRL, Lang.RU: _RU}


def t(key: str, lang: str | None, *args) -> str:
    table = TEXTS.get(lang, _LATN)
    text = table.get(key) or _LATN[key]
    return text.format(*args) if args else text


def lang_of(language_code: str | None) -> Lang:
    return Lang.from_telegram(language_code)

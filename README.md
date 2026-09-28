<p align="center"><img src="docs/brand/workly-logo.webp" alt="Workly" width="360"></p>

<p align="center"><b>Ish top. Ishchi top. Ishonchli.</b></p>

# Workly

Toshkentda kunlik ishchi va ish beruvchini tez bog'laydigan platforma.

- Texnik topshiriq: [docs/TZ_v2.0.md](docs/TZ_v2.0.md)
- Brend: [docs/brand/BRAND.md](docs/brand/BRAND.md)

## Tuzilma

```
backend/                     FastAPI + aiogram 3, bitta jarayon (Faza 1-lite)
  workly/
    domain/                  sof qoidalar: xatolar, rollar, telefon, initData, transliteratsiya
    application/             use case'lar: AuthService, UserService, CatalogService
    infrastructure/          config, DB (SQLAlchemy 2 async), JWT, SMS (Eskiz), seed
    interfaces/api/          FastAPI routerlar /api/v1
    interfaces/bot/          aiogram 3 bot (xabarlar, requestContact)
    workers/                 scheduler (keyingi blok)
  alembic/                   migratsiyalar
  tests/                     pytest (SQLite yoki PostgreSQL)
web/                         React PWA + Mini App (keyingi bloklar)
admin/                       React + Refine (keyingi bloklar)
deploy/                      docker-compose
```

TZ'dagi `bot/` papkasi o'rniga bot hozircha `backend/workly/interfaces/bot` da turadi: Faza 1-lite'da API, bot va scheduler bitta jarayonda ishlaydi (TZ 22-bo'lim). Bot domen va application qatlamini to'g'ridan-to'g'ri chaqiradi. Alohida servisga ajratish keyinroq.

## Lokal ishga tushirish

Talablar: Python 3.11+, PostgreSQL 16, Redis 7.

```bash
cp .env.example .env            # to'ldiring
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m workly.infrastructure.seed
uvicorn workly.interfaces.api.asgi:app --reload
```

- API hujjati: http://localhost:8000/api/docs
- `SMS_PROVIDER=console` bo'lsa, SMS kod logga yoziladi
- `BOT_MODE=polling` bo'lsa, bot API bilan birga ishga tushadi; `off` — botsiz

Docker bilan: `docker compose -f deploy/docker-compose.yml --env-file .env up -d --build`

## Testlar

```bash
cd backend
pytest                                   # SQLite xotirada
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/workly_test pytest
ruff check . && ruff format --check .
```

## Holat — Faza 1-lite

| Blok (TZ 22) | Holat |
|---|---|
| 1. Backend yadrosi: auth, profillar, katalog, hududlar | **Deyarli tayyor**: auth, `/me`, katalog; ishchi profili, jadval, hujjat/selfie yuklash (shifrlangan), verifikatsiya va moderator navbati, audit jurnali. Qolgan: employer profili, ommaviy rezyume |
| 2. Buyurtma, matching, lenta, bot | — |
| 3. Check-in, yakunlash, baho | — |
| 4. Web frontend, 3 til | — |
| 5. Admin: Refine + admin bot | — |
| 6. Test, deploy | CI tayyor; server deploy — keyin |

## API (hozirgi)

| Metod | Yo'l | Izoh |
|---|---|---|
| POST | `/api/v1/auth/telegram` | Mini App initData → tokenlar |
| POST | `/api/v1/auth/otp/send` | 6 xonali kod; 2 daqiqa; 60 s da 1 ta; kuniga 5 ta |
| POST | `/api/v1/auth/otp/verify` | 5 xato → 15 daqiqa blok |
| POST | `/api/v1/auth/refresh` | Rotatsiya; eski token qayta ishlatilsa barcha sessiyalar bekor |
| POST | `/api/v1/auth/logout` | |
| GET, PATCH, DELETE | `/api/v1/me` | Profil, til; soft delete |
| POST | `/api/v1/me/roles` | `worker` / `employer` |
| POST | `/api/v1/me/consents` | Hujjat versiyasi, IP, qurilma |
| GET | `/api/v1/catalog/categories`, `/regions`, `/districts` | Nomlar 3 tilda |
| GET, PUT | `/api/v1/worker/profile` | Ishchi profili: F.I.Sh, sana (18+), jins, tumanlar, uy nuqtasi, kategoriya + tajriba, favqulodda kontakt. Qisman yangilash |
| PUT | `/api/v1/worker/availability` | Haftalik jadval (kuniga ≤ 3 oraliq, kesishmasin) |
| POST | `/api/v1/worker/files` | multipart `kind` + `file`: ID karta, pasport, selfie, guvohnoma. JPEG/PNG/WEBP (guvohnomaga PDF), ≤ 5 MB |
| POST | `/api/v1/worker/verification` | Tekshiruvga yuborish: hujjat turi va raqami. To'liqlikni tekshiradi |
| GET | `/api/v1/admin/verifications` | Moderator navbati (eng eskisi birinchi), takroriy hujjat belgisi |
| GET | `/api/v1/admin/verifications/{user_id}` | Hujjat raqami va 5 daqiqalik imzoli fayl havolalari; audit jurnaliga yoziladi |
| POST | `/api/v1/admin/verifications/{user_id}/approve`, `/reject` | Belgilar (`qualified`, `background_checked`) yoki rad sababi shabloni; ishchiga bot/SMS xabar |

Xato formati: `{"code": "...", "message": "...", "details": ...}`.

## Verifikatsiya

`not_submitted → pending → verified | rejected`, `rejected → pending` (qayta yuborish), `verified → expired`. Har o'tish `state_transitions`ga, moderator harakatlari va hujjatni ko'rish `audit_logs`ga yoziladi.

- Hujjat raqami shifrlangan (Fernet) + takrorni topish uchun kalitli hash; bir xil hujjat bilan ikkinchi akkaunt moderatorga belgilanadi
- Fayllar diskda shifrlangan (Faza 1-lite; o'sishda MinIO), faqat imzoli havola orqali ochiladi
- Tekshiruvda yoki tasdiqlangandan keyin F.I.Sh, sana, jins va hujjat fayllari o'zgartirilmaydi

## Rollar

Birinchi super admin yoki moderator (foydalanuvchi avval ilovaga kirgan bo'lishi kerak):

```bash
python -m workly.cli grant-role --phone +998901234567 --role super_admin
python -m workly.cli revoke-role --phone +998901234567 --role moderator
```

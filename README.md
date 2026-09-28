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
    workers/                 scheduler (matching, ish kuni)
  alembic/                   migratsiyalar
  tests/                     pytest (SQLite yoki PostgreSQL)
web/                         React 19 + Vite + Tailwind: PWA + Telegram Mini App
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

Web ilova (backend `localhost:8000` da ishlab turgan bo'lsa):

```bash
cd web
npm install
npm run dev          # http://localhost:5173, /api → localhost:8000
npm test && npm run build
```

`VITE_BOT_URL=https://t.me/<bot>` — Telegram bot havolasi (ixtiyoriy).

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
| 1. Backend yadrosi: auth, profillar, katalog, hududlar | **Tayyor**: auth, `/me`, katalog; ishchi profili, jadval, hujjatlar (shifrlangan), verifikatsiya; employer profili (jismoniy/biznes) va STIR tekshiruvi; ommaviy rezyume; audit jurnali |
| 2. Buyurtma, matching, lenta, bot | **Tayyor**: narxlash, buyurtma yaratish; matching (ball, to'lqinlar, sovuq start, sevimlilar to'lqini, bloklar), atomik qabul, ochiq lenta, scheduler (30 s), botda Qabul/Rad; T−60 qisman to'lgan buyurtma tanlovi; employer va ishchi bekor qilishi (TZ 11 jadvali, pilotda faqat Ishonchlilik) |
| 3. Check-in, yakunlash, baho | **Tayyor**: check-in (GPS ≤ 200 m + jonli selfie, shifrlangan, 30 kunda o'chadi) va employer tasdig'i; kechikish T+15/T+30, T+60 kelmaslik → jarima va almashtirish to'lqini; yakunlash, employer tasdig'i yoki muammo, 24 soatda avtotasdiq; naqd pul qaydi; ikki tomonlama yashirin baho (48 soat), bayes reyting, ishonchlilik indeksi |
| 4. Web frontend, 3 til | **Boshlandi**: kirish (Telegram / SMS), rol tanlash, ishchi (takliflar, lenta, tayinlovlar, profil va hujjatlar), ish beruvchi (buyurtma + narx, buyurtmalar), 3 til, ish kuni (check-in, tasdiq, baho). Qolgan: xarita, chat, push |
| 5. Admin: Refine + admin bot | **Web panel tayyor** (`/admin`, TOTP 2FA): operatsiya taxtasi (bugungi holat, T+30 qo'ng'iroq navbati, nizolar, to'lmagan buyurtmalar), verifikatsiya, bizneslar, buyurtmalar (qidiruv, vaqt chizig'i, qo'lda tayinlash, jarimasiz bekor qilish), nizo qarori, foydalanuvchilarni bloklash, narxlar. Moderator — faqat taxta va verifikatsiya. Admin bot (`ADMIN_BOT_TOKEN`): kategoriya va ish turi (qo'shish, yoqish/o'chirish; kirill avtomatik), narxlar, tumanlar, avtomatik baholarni yashirish, bugungi statistika; signallar (yangi verifikatsiya va biznes, T+30, nizo, to'lmagan buyurtma) |
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
| GET | `/api/v1/workers/{id}` | Ommaviy rezyume (faqat employer/moderator, faqat tasdiqlangan ishchi): "Jasur T.", avatar, ko'nikmalar, tumanlar, belgilar, statistika. Telefon, hujjat, manzil yashirin |
| GET, PUT | `/api/v1/employer/profile` | Jismoniy shaxs yoki biznes (kompaniya, STIR, faoliyat, manzil, tuman) |
| POST | `/api/v1/employer/verification` | Biznesni STIR tekshiruviga yuborish |
| GET | `/api/v1/admin/employers` | Biznes tekshiruvi navbati (shu STIR bilan boshqa akkauntlar ko'rsatiladi) |
| POST | `/api/v1/admin/employers/{user_id}/approve`, `/reject` | "Tasdiqlangan ish beruvchi" belgisi yoki rad sababi |
| POST | `/api/v1/orders/quote` | Narx: ishchi narxi, jami, servis haqi, "Siz olasiz", tungi ish belgisi, bekor qilish qoidalari. 15 daqiqa amal qiladi |
| POST | `/api/v1/orders` | `quote_id` + `accept_rules`, `Idempotency-Key` sarlavhasi majburiy. Birinchi buyurtma ≤ 3 ishchi; yangi employerda 10+ — admin tasdig'i |
| GET | `/api/v1/orders`, `/orders/{id}` | O'z buyurtmalari |
| POST | `/api/v1/orders/{id}/cancel`, `/repeat` | Bekor qilish (hozircha tayinlovgacha); oldingi parametrlar bilan yangi narx |
| POST | `/api/v1/worker/status` | "Hozir bo'shman" (8 soat) — shoshilinch ishlar uchun |
| GET | `/api/v1/worker/offers` | Faol takliflar: tuman, masofa, vaqt, "Siz olasiz"; aniq manzil va telefonsiz |
| POST | `/api/v1/offers/{id}/accept`, `/decline` | Atomik qabul (qulf + FOR UPDATE); qabul qilgach manzil va employer telefoni ochiladi |
| GET | `/api/v1/jobs/open`, POST `/jobs/{order_id}/take` | Ochiq ishlar lentasi (1-to'lqindan keyin), birinchi olgan oladi |
| GET | `/api/v1/worker/assignments` | Tayinlangan ishlar: manzil, mo'ljal, xarita nuqtasi, employer telefoni |
| GET, POST | `/api/v1/admin/prices` | Narx versiyalari (kategoriya yoki mutaxassislik; min/max default ×0.75 / ×2) |
| POST | `/api/v1/admin/orders/{id}/approve` | Katta buyurtmani tasdiqlash |
| GET | `/api/v1/admin/verifications` | Moderator navbati (eng eskisi birinchi), takroriy hujjat belgisi |
| GET | `/api/v1/admin/verifications/{user_id}` | Hujjat raqami va 5 daqiqalik imzoli fayl havolalari; audit jurnaliga yoziladi |
| POST | `/api/v1/assignments/{id}/checkin` | multipart: `lat`, `lon`, `accuracy`, `selfie`; oyna T−30…T+60 daqiqa |
| POST | `/api/v1/assignments/{id}/confirm-arrival` | Employer: `same_person` (yo'q → muammo, adminga) |
| POST | `/api/v1/assignments/{id}/finish`, `/confirm`, `/cash-received` | Ishchi tugatdi → employer tasdiqlaydi yoki muammo (≥ 20 belgi); naqd pul qaydi |
| POST | `/api/v1/assignments/{id}/replace` | Employer: ishchi 30 daqiqadan ko'p kechiksa |
| GET, POST | `/api/v1/orders/{id}/cancel-preview`, `/cancel` | Employer: avval oqibati (summa, %, Ishonchlilik), keyin bekor; istalgan faol holatda |
| POST | `/api/v1/orders/{id}/partial` | T−60 tanlovi: `start` (qolgan o'rinlar yopiladi, narx kamayadi) yoki kutish |
| GET, POST | `/api/v1/assignments/{id}/cancel-preview`, `/cancel` | Ishchi: boshlanishdan oldin; o'rniga yangi ishchi izlanadi |
| GET | `/api/v1/employer/workers` | Men bilan ishlagan ishchilar |
| PUT, DELETE | `/api/v1/employer/favorites/{worker_id}`, `/blocks/{worker_id}` | Sevimli — alohida birinchi to'lqin; bloklangan — taklif olmaydi |
| POST, GET | `/api/v1/assignments/{id}/review`, `/reviews` | Baho 1–5 + teglar; ikkala tomon baholaguncha yashirin |
| GET | `/api/v1/admin/ops/board` | Moderator ham: bugungi raqamlar, T+30 qo'ng'iroq navbati, nizolar |
| POST | `/api/v1/admin/ops/calls/{assignment_id}` | Qo'ng'iroq qilindi + izoh |
| GET | `/api/v1/admin/orders`, `/orders/{id}` | Qidiruv (#raqam, telefon), holat, kun; vaqt chizig'i |
| POST | `/api/v1/admin/orders/{id}/cancel`, `/assign` | Jarimasiz bekor qilish (sabab ≥ 10 belgi); qo'lda tayinlash |
| POST | `/api/v1/admin/assignments/{id}/resolve` | Nizo qarori: ish hisoblanadimi, sabab, asossiz nizo ochgan tomonga −10 |
| GET, POST | `/api/v1/admin/users`, `/users/{id}/block`, `/unblock`, `/history` | Qidiruv, bloklash sababi bilan, audit tarixi |
| POST | `/api/v1/admin/verifications/{user_id}/approve`, `/reject` | Belgilar (`qualified`, `background_checked`) yoki rad sababi shabloni; ishchiga bot/SMS xabar |

Xato formati: `{"code": "...", "message": "...", "details": ...}`.

## Matching (TZ 7)

- Nomzod: tasdiqlangan, mutaxassislik mos, tuman yoki uydan ≤ 10 km, jadvalga mos (shoshilinchda — "Hozir bo'shman"), vaqti kesishmaydi, ishonchlilik ≥ 40
- Ball: `S = 0.30R + 0.20C + 0.15T + 0.15D + 0.10E + 0.10A`; to'lqin `min(3 × bo'sh o'rin, 15)`, kamida 5; har 5-o'rin "Yangi" ishchiga
- Taklif 10 daqiqa (2 soat ichida boshlansa — 5); ko'pi bilan 3 to'lqin, keyin adminga va employerga signal
- Scheduler API jarayonida har 30 s ishlaydi (Redis qulfi bilan bitta nusxa); muddatlar bazada — qayta ishga tushsa ham yo'qolmaydi
- Ketma-ket 3 ta javobsiz taklif — "Band"; rad etish jazolanmaydi

## Ish kuni (TZ 10, 13, 15)

- **Check-in**: T−30 dan T+60 gacha; GPS buyurtma nuqtasidan ≤ 200 m, aniqlik ≤ 100 m. Rad etilgan urinish ham dalil sifatida saqlanadi (selfie'siz). Employer 15 daqiqada javob bermasa — avtomatik "ishlamoqda"
- **Kechikish**: T+15 ishchi va employerga eslatma, T+30 employer "almashtirish" tugmasi + adminlarga qo'ng'iroq signali, T+60 — kelmadi
- **Kelmaslik** (90 kun ichida): 1-marta −20, 2-marta −30 va 3 kun to'xtatish, 3-marta blok. Slot qayta ochiladi, almashtirish to'lqini "hozir bo'shman" ishchilardan boshlanadi
- **Yakunlash**: employer 24 soatda tasdiqlamasa — avtotasdiq (20-soatda eslatma). Muammosiz ish +2 ishonchlilik, kechikish −3; indeks < 40 — takliflar to'xtaydi
- **Baho**: ikkala tomon baholaguncha yashirin; 48 soatda baholanmasa — joriy o'rtacha bilan avtomatik (reytingga kirmaydi). Reyting: bayes (m=4.5, C=3), so'nggi 20 ta, eskilari kamroq vazn

## Bekor qilish va T−60 (TZ 6, 11)

- **Employer**: ishchi yo'q yoki ≥ 24 soat — bepul; 6–24 soat — 20%, −5; < 6 soat — 50%, −10; ishchi yetib kelgandan keyin — birinchi kunning 100%, −10. Employer Ishonchlilik qiymatlari TZ da berilmagan — ishchi jadvaliga o'xshash olindi
- **Ishchi**: ≥ 24 soat — 0 (oyiga 3+ marta — ogohlantirish); 6–24 soat — −5; < 6 soat — 20%, −10. Ish vaqti boshlangach bekor qilib bo'lmaydi (kechikish/kelmaslik qoidalari ishlaydi)
- **Pilot**: summa ekranda va audit jurnalida ko'rsatiladi, lekin olinmaydi (`PENALTIES_CHARGED = False`)
- **T−60**: qisman to'lgan buyurtmada employerga tanlov; javob bo'lmasa yoki "kutish" — izlash davom etadi, ish vaqtida bo'sh o'rinlar yopiladi va narx topilganlar soniga tushadi
- **Sevimlilar**: alohida birinchi to'lqin (3 to'lqin limitiga kirmaydi); **blok**: ishchi shu employerdan taklif ham, lentada buyurtma ham ko'rmaydi. Faqat shu employer bilan ishlagan ishchi uchun

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

### Admin bot

`ADMIN_BOT_TOKEN` berilsa, API jarayonida alohida bot (polling) ishga tushadi. Kirish — bazada `moderator`/`admin`/`super_admin` roli bor va Telegram'ni bog'lagan foydalanuvchi (asosiy botda telefonini ulashgan). Moderator — statistika va signallar; admin — kategoriya, ish turi, narx, tuman, avtomatik baholar. Har saqlashdan oldin ko'rinish va "Saqlaysizmi?" (Ha / Bekor), har o'zgarish audit jurnalida. Hujjat va selfie botga yuborilmaydi — signalda faqat web panel havolasi.

### Admin panel (`/admin`) va 2FA

Admin panel — web ilovaning `/admin` bo'limi. Kirish: oddiy SMS/Telegram → **TOTP kodi** (Google Authenticator, Authy va h.k.) → 8 soatlik admin sessiyasi. Admin API'lari (`/api/v1/admin/*`) TOTP'siz 403 `MFA_REQUIRED` qaytaradi.

```bash
python -m workly.cli totp-setup --phone +998901234567   # otpauth:// URI — Authenticator'da QR/qo'lda kiritiladi
```

- Sir shifrlangan saqlanadi; bir kodni qayta ishlatib bo'lmaydi; 5 xato → 15 daqiqa blok; har kirish va xato audit jurnalida
- Hozircha bo'limlar: verifikatsiya navbati (hujjatlarni ko'rish, tasdiqlash/rad etish), biznes (STIR) tekshiruvi

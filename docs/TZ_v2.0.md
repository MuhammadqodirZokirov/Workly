# IshTop — Texnik Topshiriq (TZ) v2.0 · Web App

Sep 28, 2026 · @Muhammadqodir Zokirov

## Hujjat haqida

v2.0 IshTop'ni Telegram botdan to'liq web ilovaga o'tkazadi: bitta frontend brauzerda va Telegram ichida ishlaydi, bot faqat xabar va tezkor tugmalar uchun qoladi.

Belgilar: **\[D\]** — standart qaror, holati 24-bo'limda; **\[?\]** — sizdan ma'lumot kerak; **OS-N** — ochiq savol raqami. Summalar so'mda, vaqt — Toshkent (UTC+5).

### v1.0 da esdan chiqqan 6 ta muhim narsa

| № | Nima | Nega muhim | Qaror |
| --- | --- | --- | --- |
| 1 | Shaxsiy ma'lumotlar qonuni | Pasport, selfie va joylashuv O'zbekistondagi serverda saqlanishi shart | Prod — O'zbekistondagi data-markazda; Contabo — faqat test |
| 2 | Begona pulni ushlab turish | Foydalanuvchilar pulini hamyonda saqlash litsenziya talab qilishi mumkin | Faza 1 da faqat komissiya uchun xizmat balansi |
| 3 | Investor ulushi | YaTT ulush sota olmaydi | Seed investordan oldin MChJ |
| 4 | Soliq tuzilmasi | Agent shartnomasisiz butun oborot platforma daromadi sanalishi mumkin | Buxgalter bilan agent modeli |
| 5 | Fiskal chek | Payme/Click to'lovida MXIK kodi va fiskal chek talab qilinadi | Faza 2 integratsiyasida |
| 6 | O'zini o'zi band ro'yxati | Qurilish va yuk ishlari ruxsat etilgan faoliyatlar ro'yxatida bo'lmasligi mumkin | Tekshirish (OS-29) |

### v1.0 → v2.0 o'zgarishlar

| Mavzu | v1.0 | v2.0 |
| --- | --- | --- |
| Kanal | Telegram bot | Web ilova (PWA + Telegram Mini App); bot — xabarlar |
| Backend | aiogram handlerlari | FastAPI API + domen qatlami; bot alohida servis |
| To'lov | Payme/Click escrow | Faza 1: naqd + xizmat balansi; Faza 2: onlayn hold |
| Check-in | yo'q | GPS 200 m + jonli selfie + employer tasdig'i |
| Jazolar | reytingdan ayirish, ikki xil qoida | yagona jadval, alohida Ishonchlilik indeksi |
| Pul hisobi | bitta balans | double-entry ledger |
| Yangi modullar | — | overtime, qo'shimcha vazifa, SOS, chat, uy xizmatlari, agent rejimi |
| Hosting | Railway | O'zbekistondagi server |

Tuzatish: Telegram bot foydalanuvchini faqat kameradan rasm olishga majburlay olmaydi — v1.0 muhokamasidagi bu faraz noto'g'ri edi. Web ilovada jonli kamera (getUserMedia) bu muammoni hal qiladi.

## Loyiha haqida

IshTop Toshkentda kunlik ishchi va ish beruvchini 30 daqiqada bog'laydi, ishchi kelganini GPS bilan tasdiqlaydi va Faza 2 dan to'lovni kafolatlaydi.

**Muammo.** Ishchi qurilish joylarida yoki Telegram kanallarda ish kutadi, to'lov kafolati yo'q. Ish beruvchi ishchini soatlab qidiradi va kim ishonchli ekanini bilmaydi. Hech bir kanalda reyting, davomat nazorati va nizo hal qilish yo'q.

**Yechim.** Tekshirilgan profillar, avtomatik moslashtirish, joyida check-in, ikki tomonlama reyting va 48 soatlik nizo jarayoni. Faza 2 da onlayn to'lov pulni ish tasdiqlanguncha ushlab turadi.

| Segment | Kim | Asosiy ehtiyoj |
| --- | --- | --- |
| Ishchi — kunlik ish | 18+ yosh, asosan 18–45; qurilish, yuk, ombor | Tez ish va ishlagan pulning kafolati |
| Ishchi — uy xizmatlari | tozalash, bola qarash, oshpazlik; asosan ayollar | Xavfsiz, tekshirilgan mijoz |
| Employer — biznes | qurilish firmasi, kargo, ombor, do'kon | Ko'p ishchi, tez, hujjat bilan |
| Employer — jismoniy shaxs | ko'chish, ta'mir, uy tozalash | Bir martalik, oddiy, ishonchli |

Start hududi — Toshkent shahri, 12 tuman; boshqa viloyat va tumanlarni admin bot yoki panelda yoqadi \[OS-3\]. Tillar — o'zbek (lotin), o'zbek (kirill) va rus \[OS-2\]. IshTop — ishchi nom, yangi qisqa nom tanlanmoqda \[OS-32\]. Faza 1-lite tarkibi va muddati 22-bo'limda.

## Platforma shakli va arxitektura

Bitta React frontend uch joyda ochiladi — brauzer, telefonga o'rnatilgan PWA va Telegram Mini App; hammasi bitta FastAPI backendga ulanadi \[D, OS-1\].

&#91;embedded content: arxitektura · 3 kanal, backend, 4 tashqi xizmat\]

Faza 1 da hammasi bitta serverda Docker Compose bilan ishlaydi. Contabo VPS faqat test muhiti bo'ladi, unda haqiqiy shaxsiy ma'lumot saqlanmaydi.

### Texnologiyalar

| Qatlam | Tanlov | Nega |
| --- | --- | --- |
| Frontend | React 18 + TypeScript + Vite, PWA | React tajribangiz bor; bitta kod brauzer va Mini App uchun |
| UI | Tailwind CSS + shadcn/ui \[D, OS-26\] | Dizaynersiz toza interfeys |
| Telegram | @telegram-apps/sdk (Mini App), aiogram 3 (bot va admin bot) | initData bilan kirish, xabarlar |
| Backend | Python 3.12, FastAPI, Pydantic v2 | Asosiy tilingiz; OpenAPI hujjati avtomatik |
| Baza | PostgreSQL 16 + PostGIS; SQLAlchemy 2 (async), Alembic | Masofa va radius so'rovlari |
| Kesh, navbat | Redis 7 | OTP, lock, rate limit, pub/sub |
| Fon ishlari | Celery + Beat, muddatlar bazada | Server qayta ishga tushsa ham muddat yo'qolmaydi |
| Fayllar | MinIO (S3 bilan mos) | Pasport va selfie shifrlangan, imzoli havola bilan |
| Xarita | Yandex Maps JS + Geocoder \[D, OS-22\] | Mahalliy manzillar bilan yaxshi ishlaydi; narxi tekshiriladi |
| SMS | Eskiz.uz \[D, OS-23\] | Telegram orqali kirganlarga SMS kerak emas |
| Push | Web Push (VAPID) | Android'da ishlaydi; iOS'da faqat o'rnatilgan PWA'da |
| Admin | React + Refine | CRUD sahifalar tez yig'iladi |
| Monitoring | Sentry (PII tozalangan), Uptime Kuma | Xato va uzilish haqida darhol xabar |
| Deploy | Docker Compose, GitHub Actions, Nginx, Let's Encrypt | Bitta buyruq bilan yangilash |

### Kod tuzilmasi

```
ishtop/
├── backend/
│   ├── domain/          # entity, holat mashinasi, narx, matching
│   ├── application/     # use case: CreateOrder, AcceptOffer, CheckIn
│   ├── infrastructure/  # db, redis, payme, click, eskiz, minio, telegram
│   ├── interfaces/api/  # FastAPI routerlar, WebSocket, webhooklar
│   ├── workers/         # Celery tasklar, scheduler
│   └── tests/
├── bot/                 # aiogram: xabarlar, inline Qabul/Rad
├── web/                 # React: ishchi + employer (PWA + Mini App)
├── admin/               # React + Refine
└── deploy/              # docker-compose, nginx, CI
```

Qoida: domen qatlami FastAPI va bazani bilmaydi; holat faqat domen metodlari orqali o'zgaradi (6-bo'lim).

### Muhitlar

| Muhit | Qayerda | Ma'lumot |
| --- | --- | --- |
| dev | Kompyuteringiz, Docker | Soxta |
| staging | Contabo VPS | Soxta |
| prod | O'zbekistondagi VPS, sinov davrida \~10$/oy \[OS-21\] | Haqiqiy |

Deploy: GitHub Actions → Docker image → server; migratsiyalar Alembic bilan avtomatik bajariladi.

**10$ byudjet.** O'zbekistonda joylashgan VPS'lardan Serverspace narxlari: 1 GB RAM, 25 GB SSD — 430 rubl/oy; 2 GB RAM, 2 vCPU — 1,559 rubl/oy (2026-yil 1-sentyabr holati, [manba](https://hostinghub.ru/vps-search/os/linux-49/server_location/uzbekistan-613)). Demak 10$ ga 1 GB li server olinadi. Faza 1-lite uchun bitta FastAPI jarayoni (API, bot webhook, scheduler), PostgreSQL, Redis va Nginx unga swap va sozlash bilan sig'adi; mahalliy provayderlar ham solishtiriladi, 2–4 GB ga o'tish — 100 ishchi/kun bosqichida.

## Rollar, ruxsatlar va autentifikatsiya

Bitta telefon raqam — bitta akkaunt; unga ishchi va employer rollari birga ulanishi mumkin, admin rollarini faqat super admin beradi.

| Rol | Kim | Asosiy huquqlar |
| --- | --- | --- |
| Ishchi | Tasdiqlangan shaxs, 18+ | Takliflarni qabul qilish, check-in, balans, baholash, nizo |
| Employer — jismoniy shaxs | 18+ | Buyurtma, to'lov, baholash, nizo |
| Employer — biznes | STIR bilan kompaniya | Jismoniy shaxs huquqlari + menejerlar va hujjatlar (Faza 2) |
| Agent | Dala xodimi | Ishchini joyida ro'yxatdan o'tkazish (16-bo'lim) |
| Moderator | Operator | Verifikatsiya, qo'ng'iroq navbati, chat flaglari |
| Admin | Operatsiya rahbari | Moderator huquqlari + nizo qarori, blok, qaytarish |
| Super admin | Asoschi | Hammasi + moliya, narx va komissiya sozlamalari, rollar |

Har so'rovda ikki tekshiruv bor: rol ruxsati (RBAC) va egalik — ishchi faqat o'z tayinlovini ko'radi. Bir akkaunt o'z buyurtmasiga ishchi bo'la olmaydi. Ilovada rol "Rolni almashtirish" tugmasi bilan o'zgaradi.

### Kirish usullari

| Kanal | Kirish | Telefon tasdig'i |
| --- | --- | --- |
| Telegram Mini App | initData HMAC-SHA256 imzosi bot tokeni bilan tekshiriladi; auth\_date 24 soatdan eski bo'lmasin | requestContact — Telegram tasdiqlagan raqam, SMS kerak emas |
| Brauzer / PWA | Telefon + SMS kod | Eskiz orqali 6 xonali kod |
| Admin panel | Login + parol + TOTP 2FA | Akkauntni super admin yaratadi |

**SMS kod:** 6 xonali, 2 daqiqa amal qiladi; 5 marta xato — 15 daqiqa blok; bir raqamga 60 soniyada 1 ta, kuniga 5 tadan ko'p emas.

**Sessiya:** JWT access token 15 daqiqa, refresh token 30 kun. Refresh har ishlatilganda yangilanadi, bazada hash holida va qurilma bo'yicha saqlanadi; chiqishda bekor qilinadi.

**Rozilik:** foydalanish shartlari, maxfiylik siyosati va shartnoma versiyasi, vaqti, IP va qurilma yoziladi. Yangi versiya chiqsa, keyingi kirishda qayta rozilik so'raladi.

**Akkauntni o'chirish:** faol buyurtma, nizo yoki qarz bo'lmasa ruxsat beriladi. Profil darhol yashiriladi, ma'lumot 90 kundan keyin o'chiriladi, moliyaviy yozuvlar qonun muddatigacha saqlanadi.

## Ishchi moduli

Ishchi 5 daqiqada ro'yxatdan o'tadi, 24 soat ichida tasdiqlanadi va faqat shundan keyin taklif oladi.

### Ro'yxatdan o'tish

| № | Qadam | Qoida |
| --- | --- | --- |
| 1 | Til | O'zbek (lotin), o'zbek (kirill) yoki rus \[OS-2\] |
| 2 | Telefon | Mini App — requestContact; brauzer — SMS kod |
| 3 | F.I.Sh | Hujjatdagidek |
| 4 | Tug'ilgan sana | To'liq sana; 18+; hujjat bilan solishtiriladi; employerning yosh filtri uchun ishlatiladi |
| 5 | Jins | Profil ma'lumoti; kategoriyani cheklamaydi \[D, OS-6\] |
| 6 | Kategoriya, mutaxassislik | Bir nechtasini tanlash mumkin (jadval quyida) |
| 7 | Tajriba | Har kategoriya uchun: yo'q / 1–2 / 3–5 / 5+ yil |
| 8 | Hududlar | Bir nechta tuman + ixtiyoriy uy nuqtasi xaritada |
| 9 | Mavjudlik | Haftalik jadval: kunlar va soatlar |
| 10 | Hujjat | ID karta (ikki tomoni) yoki pasport asosiy sahifasi |
| 11 | Jonli selfie | Ilova ichida kameradan; galereyadan yuklab bo'lmaydi |
| 12 | Favqulodda kontakt | Ism va telefon, ixtiyoriy; SOS uchun |
| 13 | Rozilik | Foydalanish shartlari, maxfiylik, ishchi shartnomasi |

To'lov kartasi ro'yxatda so'ralmaydi — birinchi pul chiqarishda (Faza 2) kiritiladi. Bu ro'yxatni qisqartiradi.

### Kategoriyalar

| Kategoriya | Mutaxassisliklar | Holat |
| --- | --- | --- |
| Qurilish | Umumiy ishchi, g'isht teruvchi, suvoqchi, bo'yoqchi, santexnik, elektrik, usta | Faol |
| Yuk tashish | Yukchi, ombor ishchisi, haydovchi yordamchisi | Faol |
| Uy tozalash | Umumiy, deraza va kafel, ta'mirdan keyin | Faol |
| Boshqa | Erkin tavsif; admin tasdig'idan keyin chiqadi | Faol |
| Bola qarash | 0–1, 1–3, 3–7, 7+ yosh | Admin yoqadi |
| Oshpazlik | Uy oshpazi, tadbir yordamchisi | Admin yoqadi |
| Dehqonchilik | Dala, bog', hosil yig'ish | Admin yoqadi |

Kategoriya, mutaxassislik, narx birligi va narxlarni admin bot yoki web panelda qo'shadi va yoqadi — kod o'zgarmaydi \[OS-4\].

### Verifikatsiya

Holatlar: NOT\_SUBMITTED → PENDING → VERIFIED yoki REJECTED (sabab bilan); hujjat muddati tugasa — EXPIRED. Muddat — operatsion soatlarda 24 soat.

Moderator tekshiradi: selfie va hujjatdagi yuz bir odammi, yosh, hujjat muddati, ism mosligi. Tizim hujjat raqami hash'i bo'yicha takroriy akkauntni avtomatik aniqlaydi.

Rad sabablari shablon bilan beriladi: rasm noaniq, ma'lumot mos emas, yosh yetmaydi, hujjat muddati o'tgan, takroriy akkaunt. Ishchi sababni ko'radi va qayta yuklaydi. Elektrik yoki santexnik guvohnoma yuklasa — "Tasdiqlangan malaka" belgisi oladi.

Sudlanmaganlik ma'lumotnomasi (my.gov.uz) ixtiyoriy: uni yuklagan ishchi "Tekshirilgan" belgisini oladi, employer shu belgi bo'yicha filtrlaydi \[OS-30\].

### Ommaviy profil (rezyume)

Employer ko'radi: rasm, ism va familiya bosh harfi ("Jasur T."), kategoriyalar, tumanlar, Reyting va baholar soni, Ishonchlilik, bajarilgan ishlar, 90 kundagi kelmasliklar, o'rtacha javob vaqti, belgilar (Yangi, Top, Tasdiqlangan malaka), oxirgi 5 sharh.

Yashirin qoladi: telefon (tayinlovgacha), hujjat, aniq manzil.

### Mavjudlik

- "Hozir bo'shman" tugmasi shoshilinch buyurtmalar uchun; 8 soatdan keyin yoki ketma-ket 3 ta javobsiz taklifdan keyin avtomatik o'chadi.
- Haftalik jadval va sana bo'yicha istisno ("ertaga band") — ertangi buyurtmalar shu bo'yicha moslanadi.
- Vaqti kesishgan taklif yuborilmaydi: bir vaqtda ikki tayinlov bo'lmaydi.
- Joriy joylashuv faqat "Hozir bo'shman" yoqilganda va rozilik bilan olinadi; 24 soatdan keyin o'chiriladi.

### Taklif

Taklif kartasida: kategoriya, tuman va masofa, sana va vaqt, davomiylik, sof summa ("Siz olasiz: 145,500 so'm"), to'lov rejimi, asbob, tushlik va yo'l haqi, employer nomi, reytingi va belgisi.

Tugmalar: Qabul, Rad, Batafsil. Muddat — 10 daqiqa, shoshilinchda 5. Taklif botda inline tugmalar bilan va ilovada bir vaqtda keladi; qaysi birida bosilsa ham ishlaydi.

Qabul qilinganda slot atomik band qilinadi (6-bo'lim), aniq manzil va employer kontakti ochiladi (OS-12).

### Ochiq ishlar lentasi \[D, OS-5\]

Birinchi to'lqinda to'lmagan buyurtmalar mos ishchilarga lentada ko'rinadi; birinchi qabul qilgan oladi. Lentada faqat ishchining kategoriyasi va hududiga mos ishlar chiqadi.

Ishchi statistikasi: haftalik va oylik daromad, ishlar soni, reyting dinamikasi.

## Ish beruvchi moduli

Jismoniy shaxs 2 daqiqada ro'yxatdan o'tib, birinchi buyurtmani 5 daqiqada beradi; biznes STIR bilan tasdiqlanadi.

### Ro'yxatdan o'tish

| Qadam | Jismoniy shaxs | Biznes |
| --- | --- | --- |
| Telefon | Telegram yoki SMS | Telegram yoki SMS |
| Ism | Ism, familiya | Kompaniya nomi + mas'ul shaxs |
| Hujjat | Talab qilinmaydi; ixtiyoriy ID tasdig'i — "Tasdiqlangan employer" belgisi \[OS-30\] | STIR, faoliyat sohasi |
| Manzil | Ixtiyoriy | Asosiy manzil va tuman |
| Rozilik | Shartlar, maxfiylik, employer shartnomasi | + B2B shartnoma (Faza 2) |

### Buyurtma yaratish

| Maydon | Qiymatlar | Qoida |
| --- | --- | --- |
| Kategoriya, mutaxassislik | Ro'yxatdan | "Boshqa" — admin tasdig'i |
| Ishchi soni | 1–50 | Birinchi buyurtma ≤ 3; yangi employerda 10+ — admin tasdig'i |
| Sana | Bugun, ertaga, kalendar (30 kungacha) |  |
| Boshlanish vaqti | Kecha-kunduz (24/7) | 22:00–06:00 oralig'i taklifda "Tungi ish" belgisi bilan \[OS-31\] |
| Davomiylik | Yarim kun (4 s), kun (8 s), bir necha kun; uy xizmatlarida — ish hajmi | Birlik kategoriyaga bog'liq \[D, OS-7, OS-9\] |
| Manzil | Xaritada nuqta + matn + mo'ljal | Tuman nuqtadan avtomatik aniqlanadi |
| Tavsif | 500 belgigacha, 3 tagacha rasm | Taqiqlangan ishlar filtri (14-bo'lim) |
| Asbob | Employer beradi yoki ishchi o'zi olib keladi (+10%) | \[D, OS-11\] |
| Tushlik, yo'l haqi | Bor / yo'q | Taklifda ishchiga ko'rinadi |
| Afzallik | Faqat Top ishchilar (+10%); uy xizmatlarida — jins va yosh toifasi | \[D, OS-6\] |
| To'lov rejimi | Naqd yoki onlayn (Faza 2) | 9-bo'lim |

Narx ekrani: bitta ishchi narxi, jami summa, servis haqi va bekor qilish qoidalari. Narx 15 daqiqa bloklanadi; Faza 2 da arzonroq sana va vaqt muqobillari ko'rsatiladi.

### Kuzatish

Vaqt chizig'i: Izlanmoqda → Tayinlandi → Yetib keldi → Ishlamoqda → Tugadi. Ekranda tayinlangan ishchilar kartalari (rasm, Reyting, Ishonchlilik), chat, qo'ng'iroq, "Almashtirish" va "Bekor qilish" tugmalari bor. Bekor qilishdan oldin to'lanadigan summa ko'rsatiladi.

### Yakunlash va takroriy ish

- Ish tugagach ikki tugma: "Ha, bajarildi" va "Muammo bor" (nizo ochiladi). "Kelmadi" holatini check-in tizimi o'zi aniqlaydi (10-bo'lim).
- "Qayta buyurtma" — oldingi parametrlar bilan bir bosishda.
- Sevimli ishchilar: keyingi buyurtmada birinchi to'lqin ularga boradi.
- Ishchini bloklash: u shu employerga boshqa taklif qilinmaydi.

### B2B (Faza 2)

Kompaniyada bir nechta menejer, oylik obuna 1.5–2 mln so'm (employer komissiyasisiz, oylik limit \[?\]), 2 soatlik SLA. Har oy hisobot va bajarilgan xizmat dalolatnomasi beriladi (Didox yoki Faktura.uz).

## Buyurtma hayot sikli

Buyurtma ishchi soni bo'yicha tayinlovlarga bo'linadi: har tayinlov o'z holatlaridan o'tadi, buyurtma holati esa tayinlovlardan hisoblanadi.

&#91;embedded content: tayinlov hayot sikli · 7 asosiy holat, 5 chetga chiqish\]

Chap ustun — asosiy yo'l, o'ng ustun — chetga chiqishlar. Almashtirilgan ishchi uchun yangi tayinlov taklifdan qayta boshlanadi.

### Boshqa holat mashinalari

| Obyekt | Holatlar | Eslatma |
| --- | --- | --- |
| Buyurtma | DRAFT → MATCHING → PARTIALLY\_ASSIGNED → ASSIGNED → IN\_PROGRESS → COMPLETED; CANCELLED, EXPIRED | Tayinlovlardan hisoblanadi |
| To'lov (Faza 2) | PENDING → HELD → RELEASED; REFUNDED, PARTIALLY\_REFUNDED, FROZEN | HELD dan faqat domen metodi bilan chiqadi |
| Komissiya rezervi (naqd) | RESERVED → CAPTURED yoki RELEASED | Buyurtma bekor bo'lsa — RELEASED |
| Pul chiqarish (Faza 2) | REQUESTED → PROCESSING → PAID; FAILED | FAILED bo'lsa summa balansga qaytadi |
| Verifikatsiya | NOT\_SUBMITTED → PENDING → VERIFIED; REJECTED, EXPIRED | 4-bo'lim |
| Taklif | SENT → ACCEPTED; DECLINED, EXPIRED, WITHDRAWN | Slot to'lsa qolganlari WITHDRAWN |

### Qoidalar

- Holat faqat domen metodi orqali o'zgaradi; ruxsatsiz o'tish 409 INVALID\_STATE qaytaradi. Har o'tish `state_transitions` jurnaliga yoziladi: kim, qachon, sabab.
- Taklif qabulida `SELECT … FOR UPDATE` va Redis lock ishlaydi — bitta slotni ikki ishchi ololmaydi. Pul va holat so'rovlari Idempotency-Key bilan keladi.
- Qisman to'lgan buyurtma: T−60 daqiqada ham to'lmagan bo'lsa, employer tanlaydi — topilganlar bilan boshlash (qolgani qaytariladi) yoki kutish \[D, OS-10\].
- Ko'p kunlik buyurtma: har kun alohida tayinlov-kun — alohida check-in, yakun va to'lov; o'sha ishchi bilan davom etish afzal \[D, OS-9\].
- Muddatli hodisalar (taklif muddati, T+15/T+30/T+60, 24 soatlik avtotasdiq) `scheduled_jobs` jadvalida saqlanadi; scheduler ularni har 30 soniyada tekshiradi.

## Matching

Tizim mos ishchilarni ball bo'yicha saralab, to'lqin-to'lqin taklif yuboradi; kim birinchi qabul qilsa, slot o'shaniki. Maqsad — Oy 3 da median to'ldirish vaqti ≤ 30 daqiqa, fill rate ≥ 90% (21-bo'lim).

### Kim taklif oladi

Barcha shartlar bir vaqtda bajarilishi kerak:

- Profil tasdiqlangan; blok yoki to'xtatish yo'q.
- Kategoriya va mutaxassislik mos.
- Sana va vaqt jadvalga to'g'ri keladi; shoshilinch buyurtmada — "Hozir bo'shman" yoqilgan.
- Ish joyi tanlangan tumanlarda yoki uy nuqtasidan 10 km ichida \[D\].
- Vaqti kesishgan boshqa tayinlov yo'q.
- Reyting ≥ 3.5 yoki "Yangi"; Ishonchlilik ≥ 40.
- Naqd buyurtmada: qarz yo'q, xizmat balansi 3% komissiyaga yetadi yoki bepul kvota bor.
- Employer bu ishchini bloklamagan; uy xizmatlarida jins va yosh afzalligi bo'lsa — mos.

### Ball

```latex
S = 0.30R + 0.20C + 0.15T + 0.15D + 0.10E + 0.10A
```

| Belgi | Nima | Hisob (0–1) |
| --- | --- | --- |
| R | Reyting | Bayes reytingi / 5; "Yangi" ishchida 0.9 |
| C | Bajarish ulushi | Tugatilgan / qabul qilingan, 90 kun |
| T | Javob tezligi | 1 − min(o'rtacha javob daqiqasi / 10, 1) |
| D | Masofa | 1 − min(km / 10, 1) |
| E | Tajriba | Yo'q — 0; 1–2 yil — 0.33; 3–5 yil — 0.66; 5+ yil — 1 |
| A | Faollik | Oxirgi 7 kunda ishlagan — 1; 30 kunda — 0.5; aks holda 0 |

Vaznlar admin panelda sozlanadi va har o'zgarish versiya sifatida saqlanadi.

### To'lqinlar

| Qoida | Qiymat |
| --- | --- |
| To'lqin hajmi | min(3 × bo'sh slot, 15), kamida 5 ta ishchi |
| Taklif muddati | 10 daqiqa; ish 2 soat ichida boshlansa — 5 daqiqa |
| Yangi ishchilar | Har 5 taklifdan 1 tasi "Yangi" ishchiga — sovuq start muammosi uchun |
| Sevimlilar | Employerning sevimli ishchilari alohida birinchi to'lqin oladi |
| Lenta | 1-to'lqindan keyin to'lmagan buyurtma "Ochiq ishlar"ga chiqadi |
| Chegara | 3 to'lqindan keyin adminga signal; employerga tanlov: kutish, vaqtni o'zgartirish yoki to'liq qaytarish bilan bekor qilish |
| Ustuvorlik | Almashtirish > B2B SLA > balans bilan ta'minlangan buyurtma > qolganlar |

### Intizom

Rad etish jazolanmaydi. Ketma-ket 3 ta taklifga javob bermaslik holatni avtomatik "Band"ga o'tkazadi va ishchiga xabar boradi. Javobsiz qolgan takliflar T balliga ta'sir qiladi.

## Narxlash

Faza 1 da narx qat'iy: admin har kategoriya uchun bazaviy, minimal va maksimal narxni belgilaydi; dinamik koeffitsientlar Faza 2 da yoqiladi.

### Bazaviy narxlar

| Kategoriya | Birlik | Bazaviy, so'm | Min (×0.75) | Max (×2) |
| --- | --- | --- | --- | --- |
| Qurilish — umumiy | Kun, 8 soat | 150,000 | 112,500 | 300,000 |
| Qurilish — usta | Kun | 250,000 | 187,500 | 500,000 |
| Yuk tashish | Kun | 130,000 | 97,500 | 260,000 |
| Boshqa | Kun | 120,000 | 90,000 | 240,000 |
| Dehqonchilik | Kun | 100,000 | 75,000 | 200,000 |
| Uy tozalash | m² \[D\] | Admin kiritadi |  |  |
| Oshpazlik | Mehmon soni \[D\] | Admin kiritadi |  |  |
| Bola qarash | Soat × bola soni \[D\] | Admin kiritadi |  |  |

Uy xizmatlarida narx = birlik narxi × hajm, eng kam buyurtma summasi bilan; birlik, narx va eng kam summani admin bot yoki panel orqali kiritadi (16-bo'lim). Employer hajmni kiritadi; joyida hajm katta chiqsa, ishchi qo'shimcha vazifa kabi qayta hisob so'raydi \[OS-7, OS-8\].

Yarim kun (4 soat) = kunlik narx × 0.6 \[D\].

### Faza 2 formulasi

```latex
P = B \times K_{talab} \times K_{vaqt} \times K_{hajm} \times K_{mavsum}, \quad 0.75B \le P \le 2B
```

| Koeffitsient | Shart | Qiymat |
| --- | --- | --- |
| Talab (buyurtma / bo'sh ishchi, har 30 daqiqada) | < 0.5 | 0.90 |
|  | 0.5–1.0 | 1.00 |
|  | 1.0–1.5 | 1.20 |
|  | > 1.5 | 1.50 |
| Vaqt (boshlanishgacha) | 3+ kun | 0.90 |
|  | 1–2 kun | 1.00 |
|  | 6–24 soat | 1.20 |
|  | 2–6 soat | 1.35 \[D\] |
|  | < 2 soat | 1.50 |
| Hajm (ishchi soni) | 1–2 | 1.10 |
|  | 3–5 | 1.00 |
|  | 6–10 | 0.95 |
|  | 10+ | 0.85 |
| Mavsum | Iyun–avgust | 1.10 |
|  | Dekabr–yanvar | 0.90 |
|  | Ramazon | 1.15 |
|  | Boshqa oylar | 1.00 |

v1.0 da 2–6 soat oralig'i uchun koeffitsient yo'q edi — 1.35 qo'shildi.

### Qo'shimcha qoidalar

- Top ishchi tanlovi +10%, ishchi asbobi +10% — ikkalasi ham ishchiga to'liq o'tadi.
- Overtime: kunlik narx / 8 × 1.25 soatiga; har boshlangan 30 daqiqa hisoblanadi; kuniga 4 soatgacha.
- Yaxlitlash 1,000 so'mgacha. Narx 15 daqiqa bloklanadi; sozlama o'zgarsa, eski buyurtmalar narxi o'zgarmaydi — narx nusxasi buyurtmada saqlanadi.
- Ishchi taklifda har doim o'z sof summasini ko'radi.

Misol (Faza 1): 3 ta umumiy ishchi, ertaga, 1 kun — 3 × 150,000 = 450,000 + 10% servis = 495,000 so'm. Har ishchi 145,500 so'm oladi.

## To'lov, balans va komissiya

Faza 1 da platforma begona pulni ushlamaydi: ishchi pulni naqd oladi, komissiyalar ikki tomonning oldindan to'ldirilgan xizmat balansidan yechiladi \[D, OS-13\].

### To'lov rejimlari

| Rejim | Qachon | Pul yo'li | Kafolat |
| --- | --- | --- | --- |
| Naqd | Faza 1 | Employer ishchiga qo'lda to'laydi; komissiyalar balanslardan | Platforma kafolatlamaydi — ishchiga taklifda aniq yoziladi |
| Onlayn | Faza 2 | Employer kartasi → provayderda hold → ish tasdig'idan keyin ishchiga | To'liq kafolat |

### Komissiya

Employer narx + 10% to'laydi, ishchi narx − 3% oladi \[D, OS-14\]. Har ikki tomon uchun birinchi 3 ta yakunlangan ish bepul.

| 150,000 so'mlik ish | Summa, so'm |
| --- | --- |
| Employer to'laydi | 165,000 |
| Ishchi oladi | 145,500 |
| Platforma daromadi | 19,500 |

### Naqd rejim qoidalari

1. Buyurtma tasdiqlanganda employer komissiyasi xizmat balansidan rezerv qilinadi; yetmasa — balansni to'ldirish yoki Faza 2 da onlayn to'lov.
2. Naqd buyurtma taklifi faqat 3% komissiyaga balansi yetadigan yoki bepul kvotasi bor ishchiga boradi.
3. Ish tugagach ishchi "Naqd oldim: X so'm"ni tasdiqlaydi; shundan keyin ikkala komissiya yechiladi.
4. Ishchi "Pul olmadim" desa, nizo ochiladi; hal bo'lguncha employer yangi buyurtma bera olmaydi.
5. Balansi bor foydalanuvchilar matchingda ustunlik oladi.

### Xizmat balansi, daromad va qarz

- **Xizmat balansi** (ikkala rol): Payme/Click orqali to'ldiriladi (YaTT ochilgach). Faqat komissiya, jarima va obunaga sarflanadi; boshqa foydalanuvchiga o'tkazilmaydi. So'rov bilan 5 ish kunida qaytariladi \[D\].
- **Daromad** (Faza 2, faqat onlayn rejim): ishchi ilovada ko'radi, pul esa provayder yoki bank hisobida turadi. Kartaga chiqarish — kamida 10,000 so'm, 1–24 soatda.
- **Qarz**: jarima balansdan oshsa, farq qarz bo'lib yoziladi. Qarz bor ekan naqd takliflar kelmaydi; keyingi to'ldirish yoki daromaddan avtomatik yopiladi \[D, OS-16\].

### Ledger (pul hisobi)

Har pul harakati double-entry: bitta tranzaksiyadagi yozuvlar yig'indisi 0 ga teng. Hisoblar: xizmat balansi, qarz, komissiya rezervi, platforma daromadi, to'lanadigan kompensatsiya, provayder hisob-kitobi, hold (Faza 2).

Yozuvlar o'zgarmaydi — xato faqat teskari yozuv bilan tuzatiladi. Balans yozuvlar yig'indisidan hisoblanadi. Har kuni Payme/Click hisobotlari bilan solishtiriladi; farq chiqsa, adminga signal boradi.

### Onlayn to'lov (Faza 2)

- Payme Merchant API va Click Merchant API; webhook imzosi tekshiriladi, takroriy so'rov ikki marta bajarilmaydi.
- Provayderda hold yoki split imkoniyati bormi — aniqlash kerak \[?\]. Bo'lmasa, bank nominal hisobi yoki litsenziyali hamkor.
- Har to'lovda MXIK kodi va fiskal chek ma'lumotlari yuboriladi.
- Chargeback uchun dalillar: check-in GPS va selfie, employer tasdig'i, chat.

### Bonuslar (Faza 2)

Yangi employerga 50,000 so'm — bitta kartaga bir marta \[D, OS-19\]. Referral: ikkala tomonga bittadan bepul buyurtma. Haftalik top-10 ishchiga 50,000 so'm.

## Ish kuni

Ishchi ish joyidan 200 metr ichida GPS va jonli selfie bilan check-in qiladi, employer bir bosishda tasdiqlaydi; 60 daqiqa kechiksa, almashtirish boshlanadi.

### Check-in

| Qadam | Qoida |
| --- | --- |
| T−12 soat va T−1 soat | Ikkala tomonga eslatma |
| T−15 daqiqa | Ishchiga "Check-in qiling" eslatmasi |
| Check-in oynasi | T−30 daqiqadan T+60 daqiqagacha |
| GPS | Masofa ≤ 200 m, aniqlik ≤ 100 m; bo'lmasa qayta urinish yoki employer qo'lda tasdiqlaydi |
| Selfie | Ilova ichida jonli kamera (getUserMedia), galereya yo'q; 30 kun saqlanadi |
| Employer tasdig'i | "Ishchi yetib keldi — shu odammi?" Ha / Yo'q; 15 daqiqada javob bo'lmasa, GPS va selfie yetarli |
| Natija | Tayinlov "Yetib keldi" holatiga o'tadi, ish vaqti hisoblana boshlaydi |

Telegram Mini App ichida kamera va GPS WebView ruxsatiga bog'liq; ishlamasa, ilova sahifani brauzerda ochishni taklif qiladi. Veb-ilova soxta GPS dasturlarini aniqlay olmaydi, shuning uchun employer tasdig'i asosiy dalil hisoblanadi.

### Kechikish

| Vaqt | Hodisa |
| --- | --- |
| T+15 | Ishchiga eslatma; employerga "ishchi kechikmoqda" |
| T+30 | Moderatorga qo'ng'iroq vazifasi (tunda — ishchiga avtomatik SMS); employer tanlaydi: Kutaman / Almashtiring / Bekor (to'liq qaytarish) |
| T+60 | Check-in va asosli sabab yo'q — "Kelmadi"; tezkor almashtirish to'lqini (5 daqiqa); employerga kompensatsiya (11-bo'lim) |
| Asosli sabab | Kasallik, baxtsiz hodisa, yo'l halokati — 24 soatda dalil bilan; jarima bekor, Ishonchlilik o'zgarmaydi |

### Overtime

- Rejadagi tugash vaqtida ishchiga savol: "Davom etasizmi?" — +1, +2, +3 yoki +4 soat. Employer narxni ko'rib tasdiqlaydi; employer ham o'zi so'rashi mumkin.
- Narx 8-bo'limdagi formula bo'yicha, kuniga 4 soatgacha. Taymer ikkala tomonda ko'rinadi; istalgan tomon "Stop" bosadi.
- Naqd rejimda summa naqd qo'shiladi, komissiya balansdan yechiladi; Faza 2 da qo'shimcha hold qilinadi.

### Qo'shimcha vazifa

- Employer tavsif va narx yozadi yoki "Kelishamiz"ni tanlaydi; ishchi bir marta qarshi narx taklif qila oladi.
- Ishchi rad etsa — jarima yo'q. Qabul qilingan summa tayinlov jamiga qo'shiladi.

### Yakunlash

- Ishchi "Tugatdim" bosadi (joylashuv yoziladi); employer "Ha, bajarildi" yoki "Muammo bor" bosadi.
- Employer 24 soatda javob bermasa — avtomatik tasdiq; 20-soatda eslatma boradi.
- Naqd rejimda ishchi "Naqd oldim: X so'm"ni tasdiqlaydi; summa kelishilgandan kam bo'lsa — nizo.
- Shundan keyin ikkala tomondan baho so'raladi (13-bo'lim).

## Bekor qilish, jarima va bloklash

v1.0 dagi ikki xil "kelmadi" qoidasi bitta jadvalga keltirildi: jarima puli to'liq jabrlangan tomonga o'tadi, intizom esa Ishonchlilik indeksiga ta'sir qiladi \[D, OS-15, OS-17\].

### Employer bekor qilsa

| Qachon | To'lov | Kimga |
| --- | --- | --- |
| Ishchi hali tayinlanmagan | 0 | — |
| Ishdan ≥ 24 soat oldin | 0 | — |
| 6–24 soat oldin | Buyurtmaning 20% | Tayinlangan ishchilarga teng |
| < 6 soat oldin | 50% | Ishchilarga |
| Ishchi yetib kelgandan keyin | Birinchi kunning 100% | Ishchiga |

### Ishchi bekor qilsa yoki kelmasa

Jarima shu tayinlovdagi kunlik narxdan foizda hisoblanadi. Asosli sabab dalil bilan isbotlansa, hammasi bekor qilinadi.

| Holat | 90 kun ichida | Jarima | Ishonchlilik | Qo'shimcha |
| --- | --- | --- | --- | --- |
| Bekor, ≥ 24 soat oldin | Har safar | 0 | 0 | Oyiga 3+ marta — ogohlantirish |
| Bekor, 6–24 soat oldin | Har safar | 0 | −5 |  |
| Bekor, < 6 soat oldin | Har safar | 20% | −10 |  |
| Kelmadi | 1-marta | 20% | −20 | Ogohlantirish |
| Kelmadi | 2-marta | 30% | −30 | 3 kunga to'xtatish |
| Kelmadi | 3-marta | 30% | −40 | Blok + admin tekshiruvi |
| Kechikish 15–60 daqiqa | Har safar | 0 | −3 |  |

Jarima avval xizmat balansidan, yetmasa qarz sifatida olinadi (9-bo'lim) va to'liq employerga kompensatsiya bo'lib o'tadi.

### Ishonchlilik indeksi

Indeks 0–100 oralig'ida; yangi foydalanuvchi 100 dan boshlaydi. Har muammosiz ish +2 beradi (100 gacha), 40 dan past — avtomatik to'xtatish. Employer ham shunday indeksga ega: bekor qilishlar va asossiz nizolar uni kamaytiradi.

### Bloklash

| Sabab | Tur | Qaytish |
| --- | --- | --- |
| 3 ta "kelmadi" 90 kunda | Avtomatik blok | Admin suhbati, 7 kundan keyin |
| Reyting < 3.5 (ishchi, ≥ 5 baho) | Avtomatik to'xtatish | Admin suhbati, 7 kun |
| Reyting < 3.0 (employer) | Ogohlantirish, keyin blok | Admin qarori |
| Ishonchlilik < 40 | Avtomatik to'xtatish | 7 kun + suhbat |
| Qarz 30 kundan ortiq | Naqd rejim yopiladi | Qarzni yopish |
| Tashqarida to'lov (isbotlangan) | 1-marta 30 kun, 2-marta doimiy \[D, OS-12\] | Admin qarori |
| Soxta hujjat, firibgarlik | Doimiy | Yo'q |
| Zo'ravonlik yoki tahdid | Darhol doimiy | Yo'q |

Har blokning sababi, muddati va kim qo'ygani audit jurnaliga yoziladi; foydalanuvchi sababni ilovada ko'radi.

## Nizolar

Nizo ish tugaganidan keyin 24 soat ichida ochiladi va ko'pi bilan 48 soatda hal qilinadi; onlayn to'lovda pul shu vaqt davomida muzlatiladi.

| № | Qadam | Kim | Muddat |
| --- | --- | --- | --- |
| 1 | Sabab, izoh (kamida 20 belgi) va 5 tagacha rasm bilan nizo ochish | Ishchi yoki employer | Ish tugagach 24 soat; xavfli sharoit — ish vaqtida |
| 2 | Dalillar avtomatik qo'shiladi: check-in va check-out GPS, vaqt, selfie, chat, overtime va vazifalar logi | Tizim | Darhol |
| 3 | Qarshi tomon javobi | Qarshi tomon | 24 soat; javob bo'lmasa mavjud dalil bilan hal qilinadi |
| 4 | Qaror: ishchiga to'liq, employerga qaytarish, foizda bo'lish yoki ikkalasiga ogohlantirish; sabab majburiy | Admin | Javobdan keyin 24 soat |
| 5 | Apellyatsiya — bir marta | Istalgan tomon | Qarordan keyin 48 soat; super admin ko'radi |
| 6 | Pul, jarima va Ishonchlilik qarorga ko'ra o'zgaradi; asossiz nizo ochgan tomonga −10 | Tizim | Darhol |

| Employer sabablari | Ishchi sabablari |
| --- | --- |
| Sifatsiz ish | To'lov berilmadi yoki kam berildi |
| Ishchi ketib qoldi | Ish berilmadi |
| Kech keldi | Kelishilgandan boshqa ish buyurildi |
| Ish bajarilmadi | Xavfli sharoit |
| Boshqa | Boshqa |

Naqd rejimda platforma naqd pulni ko'chira olmaydi, shuning uchun qaror balanslar, kompensatsiya va bloklar orqali bajariladi. 48 soatdan oshgan nizo super adminga signal beradi. 90 kunda 3 ta asossiz nizo — admin tekshiruvi.

## Reyting, ishonchlilik va sharhlar

Profilda ikki raqam ko'rinadi: Reyting (boshqalarning bahosi, 1–5) va Ishonchlilik (intizom, 0–100); jazolar faqat ikkinchisiga ta'sir qiladi.

- Ikkala tomon 1–5 yulduz, tezkor teglar (Vaqtida keldi, Sifatli ish, Muomalasi yaxshi, To'lov o'z vaqtida) va 300 belgigacha izoh qoldiradi; muddat — 48 soat.
- Baho ikki tomonlama yashirin: ikkalasi baholagach yoki 48 soat o'tgach ochiladi. Bu qasos bahosining oldini oladi.
- Baho 48 soatda berilmasa, avtomatik baho qo'yiladi — baholanuvchining joriy o'rtacha reytingi (yangi foydalanuvchida 4.5) — va "avtomatik" deb belgilanadi. U o'rtachani deyarli o'zgartirmaydi va baholar soni chegaralariga (≥ 5 baho, "Yangi" belgisi) kirmaydi; admin kerak bo'lsa o'chiradi \[OS-18\].

### Hisoblash

```latex
R = \frac{C \cdot m + \sum_{i=1}^{n} w_i r_i}{C + \sum_{i=1}^{n} w_i}, \quad m = 4.5,\; C = 3,\; n \le 20
```

w — vazn: eng yangi baho 1.0, 20-chisi 0.5, oralig'i chiziqli. 3 ta bahogacha profilda "Yangi" belgisi turadi.

| Chegara | Ishchi | Employer |
| --- | --- | --- |
| Top / Ishonchli belgisi | R ≥ 4.5 va ≥ 10 ish | R ≥ 4.5 va ≥ 5 buyurtma |
| Past ustuvorlik | R 3.5–4.0 | R 3.5–4.0 |
| To'xtatish | R < 3.5 (≥ 5 baho) | R < 3.0 — ogohlantirish, keyin blok |

### Moderatsiya va manipulyatsiya

Izohlar so'kinish filtridan o'tadi (o'zbek lotin va kirill, rus), har izohda "Shikoyat" tugmasi bor; admin izohni yashirsa, sababi loglanadi.

Avtomatik flaglar: bir juftlikdan 7 kunda 3+ ta 5 yulduz; bitta qurilma yoki IP dan bir nechta akkaunt; ro'yxatdan o'tgan kuni kelgan baho. Qarorni admin qabul qiladi.

## Jismoniy xavfsizlik va taqiqlangan ishlar

Faol ish davomida SOS tugmasi doim ko'rinadi: u joylashuvni adminga va favqulodda kontaktga yuboradi, lekin 112, 102 va 103 o'rnini bosmaydi.

| Vosita | Nima bo'ladi |
| --- | --- |
| SOS | Admin navbatiga eng yuqori ustuvorlik bilan: GPS, buyurtma, ikki tomon ma'lumoti; favqulodda kontaktga SMS va Telegram; ekranda 112, 102, 103 tugmalari |
| Xavfli sharoit | Ish to'xtaydi, ishchiga jarima yo'q; admin tekshiradi; bajarilgan qism to'lanadi; tasdiqlansa employer ogohlantiriladi yoki bloklanadi |
| Zo'ravonlik yoki tahdid | Employer tekshiruvsiz darhol bloklanadi; ishchiga to'liq to'lov yoki kompensatsiya |
| Tungi ishlar | Ochiq (24/7). Taklifda "Tungi ish" belgisi, rad etish jazosiz; tunda admin o'rniga avtomatik qoidalar, SOS — 112 va favqulodda kontakt \[OS-31\] |
| Uy xizmatlari | Employer ID tasdig'i ixtiyoriy ("Tasdiqlangan employer" belgisi, ishchi filtrlaydi); employer ishchining jinsi va yosh toifasini tanlaydi; ishchi "ish holatini ulashish" havolasini yaqiniga yuboradi |
| Bola qarash | Majburiy qo'shimcha tekshiruv yo'q; sudlanmaganlik ma'lumotnomasi ixtiyoriy — "Tekshirilgan" belgisi, employer shu belgi bo'yicha filtrlaydi \[OS-30\] |

Operatsion soatlardan tashqarida admin javobi kafolatlanmaydi — bu SOS ekranida aniq yoziladi.

### Taqiqlangan ishlar

Employer buyurtma berishda bu ro'yxatga rozilik bildiradi; tavsif so'z filtri va moderatsiyadan o'tadi.

- Qonunga zid har qanday ish; 18 yoshdan kichiklarni jalb qilish.
- Himoya vositasisiz balandlikda ishlash, xavfli kimyoviy yoki portlovchi moddalar, yuqori kuchlanishli tarmoq.
- Qarz undirish, qo'riqchilik, intim xizmatlar.
- Ishchidan hujjat, karta yoki pul talab qilish.

## Bildirishnomalar va chat

Asosiy kanal — Telegram bot (bepul va tezkor), zaxira — Web Push; SMS faqat kod va eng muhim ogohlantirishlar uchun.

| Hodisa | Kimga | Kanal |
| --- | --- | --- |
| Yangi taklif (Qabul/Rad tugmalari bilan) | Ishchi | Bot + push |
| Taklif muddati 2 daqiqada tugaydi | Ishchi | Bot |
| Ishchi tayinlandi | Employer, ishchi | Bot + push |
| Ish oldidan eslatma (T−12 s, T−1 s) | Ikkalasi | Bot |
| Check-in eslatmasi (T−15) | Ishchi | Bot + push |
| Ishchi yetib keldi — tasdiqlang | Employer | Bot + push |
| Kechikish, almashtirish | Ikkalasi | Bot + push; T+30 da SMS |
| Ishni tasdiqlang, 20-soat eslatmasi | Employer | Bot + push |
| Baho so'rovi | Ikkalasi | Bot |
| Nizo holati | Ikkalasi | Bot + push |
| Profil tasdiqlandi yoki rad etildi | Ishchi | Bot + SMS |
| Balans kam yoki qarz | Foydalanuvchi | Bot |
| SOS | Admin | Admin panel + Telegram guruh + SMS |

Xabar shablonlari uch tilda: o'zbek (lotin, kirill) va rus. Tinch soatlar 22:00–07:00: faqat takliflar va shoshilinch xabarlar; ishchi tungi takliflarni o'chirib qo'yishi mumkin. Foydalanuvchi botni bloklasa, push va SMS ishlatiladi. Har xabar `notifications` jadvalida yetkazilish holati bilan saqlanadi.

Bot xabarlarida pasport, aniq manzil yoki telefon yuborilmaydi — faqat ilovaga havola (19-bo'lim).

### Chat

Har tayinlov uchun alohida chat bor: matn, rasm, joylashuv. U tayinlovdan ish tugashi + 24 soatgacha ochiq, keyin faqat o'qiladi va nizoda dalil bo'ladi.

Telefon raqam tayinlangandan keyin ochiladi \[D, OS-12\]. Chatda telefon yoki karta raqami, "tashqarida to'laymiz" kabi iboralar aniqlansa — ikkala tomonga ogohlantirish, adminga flag.

## Admin panel va agent rejimi

Faza 1 da barcha admin rollarini siz bajarasiz, shuning uchun eng muhim modul — kunlik operatsiya taxtasi va navbatlar.

| Modul | Nima qiladi | SLA |
| --- | --- | --- |
| Dashboard | Bugungi buyurtmalar, tayinlovlar, check-in, kechikish, nizolar, balanslar | Real vaqt |
| Operatsiya taxtasi | Bugungi tayinlovlar holati; T+30 qo'ng'iroq navbati | Qo'ng'iroq ≤ 10 daqiqa |
| Verifikatsiya | Hujjat va selfie yonma-yon, takroriy hujjat ogohlantirishi, tasdiq/rad shablonlari | ≤ 24 soat |
| Buyurtmalar | Qidiruv, vaqt chizig'i, qo'lda tayinlash, bekor qilish, qaytarish | — |
| Nizolar | Dalillar paneli, qaror formasi, apellyatsiya | ≤ 48 soat |
| Foydalanuvchilar | Profil, ledger, jarima, blok, ichki eslatmalar | — |
| Moliya | Ledger, to'ldirishlar, pul chiqarish, provayder bilan kunlik solishtirish, daromad hisoboti | Kunlik |
| Sozlamalar | Kategoriya, hudud (viloyat, tuman), narx va hajm birligi, koeffitsient, komissiya, bepul kvota, matching vaznlari, avtomatik baho | Har o'zgarish versiyalanadi |
| Kontent | Oferta va shartnoma versiyalari, xabar shablonlari | — |
| Broadcast | Rol, kategoriya va tuman bo'yicha xabar | — |
| Audit jurnali | Har admin harakati: kim, nima, qachon, oldin va keyin | O'zgarmas |

Har pul yoki reyting o'zgarishi sabab bilan yoziladi. Admin kirishida 2FA majburiy; moderator faqat verifikatsiya va qo'ng'iroq navbatini ko'radi.

Platforma 24/7 ishlaydi; qo'lda admin ishi 07:00–21:00 \[D, OS-33\]. Undan tashqarida avtomatik qoidalar ishlaydi, qo'lda amallar ertalabga qoladi.

### Admin bot

Kundalik sozlamalar Telegram admin botda ham qilinadi: kategoriya, ish turi, narx va hududlarni telefondan kiritish mumkin \[OS-34\].

| Menyu | Nima qiladi |
| --- | --- |
| Kategoriyalar | Qo'shish, tahrirlash, yoqish yoki o'chirish; nom 3 tilda — kirill lotindan avtomatik chiqadi va tasdiqlanadi |
| Ish turlari | Kategoriya ichida mutaxassislik qo'shish, tahrirlash, yoqish yoki o'chirish |
| Narxlar | Birlik (kun, soat, m², kishi), bazaviy narx, min/max (avtomatik ×0.75 va ×2, qo'lda o'zgartiriladi), eng kam buyurtma summasi |
| Hududlar | Viloyat va tumanlarni yoqish yoki o'chirish |
| Signallar | Yangi verifikatsiya, T+30 qo'ng'iroq vazifasi, SOS, bugungi statistika |
| Avtomatik baholar | Ko'rish va kerak bo'lsa o'chirish |

- Bot faqat interfeys: web panel bilan bir xil API va domen qoidalarini chaqiradi; har o'zgarish audit jurnaliga yoziladi.
- Kirish: bazada admin roli bor Telegram ID'lar; alohida admin bot tokeni \[D\].
- Har saqlashdan oldin ko'rinish va "Saqlaysizmi?" — Ha / Bekor. Narx o'zgarishi faqat yangi buyurtmalarga ta'sir qiladi (8-bo'lim).
- Komissiya, jarima foizlari va bepul kvota botda faqat TOTP kodi bilan o'zgaradi; qaytarish va doimiy blok — faqat web panelda \[D\].
- Pasport va selfie botga yuborilmaydi: signalda faqat web panelga havola bo'ladi (19-bo'lim).
- Ko'p narxni birdaniga Excel fayl bilan yuklash — Faza 1 to'liqda.

### Agent rejimi

Dala agenti ishchini joyida ro'yxatdan o'tkazadi: hujjat va selfie oladi, ishchi o'z telefoniga kelgan kod bilan tasdiqlaydi. Agent statistikasi yuritiladi; birinchi ishini bajargan har ishchi uchun agentga bonus \[?\]. Pilotdan keyin yoqiladi.

## Ma'lumotlar modeli

Taxminan 30 ta jadval; pul faqat ledger yozuvlarida, har holat o'zgarishi alohida jurnalda saqlanadi.

| Guruh | Jadvallar | Muhim maydonlar |
| --- | --- | --- |
| Foydalanuvchi | users, user\_roles, sessions, consents | phone (unique), telegram\_id, lang, status; rozilik versiyasi, vaqti, IP |
| Ishchi | worker\_profiles, worker\_skills, worker\_availability, worker\_documents | birth\_date, gender, tumanlar, home\_point; tajriba; doc\_type, doc\_number\_hash, fayl kaliti, verification\_status |
| Employer | employer\_profiles, business\_verifications, favorites, employer\_blocks | type, company, stir, verified\_at |
| Katalog | categories, specializations, regions, districts, price\_configs, config\_versions | is\_active; unit (kun, soat, m², kishi), base, min, max, koeffitsientlar, active\_from |
| Buyurtma | orders, assignments, assignment\_days, offers | Buyurtma: kategoriya, soni, vaqt, geo, hajm, jins va yosh afzalligi, payment\_mode, narx nusxasi, status. Tayinlov: ishchi, status. Taklif: to'lqin, sent\_at, ttl, status |
| Ish kuni | checkins, time\_entries, extra\_tasks | geo, accuracy, distance\_m, selfie\_key, employer\_confirmed; overtime start/stop; vazifa narxi va holati |
| Pul | accounts, ledger\_entries, payments, withdrawals, debts, commission\_reserves | Hisob turi va egasi; yozuv: txn\_id, account, amount (+/−), sabab, havola; provayder ID |
| Intizom | penalties, cancellations, reliability\_events, blocks | Tur, summa, asos, sabab, reversed\_at |
| Nizo | disputes, dispute\_evidence, dispute\_decisions, appeals | Sabab, muddatlar, qaror, bo'lish foizi, admin |
| Baho | reviews, review\_tags, review\_reports | rating, teglar, izoh, visible\_at |
| Aloqa | chat\_threads, chat\_messages, notifications, push\_subscriptions | Flaglar (raqam aniqlandi), yetkazilish holati |
| Xavfsizlik | sos\_events, emergency\_contacts | geo, handled\_by |
| Tizim | state\_transitions, scheduled\_jobs, audit\_logs, idempotency\_keys | Obyekt, from → to, kim; run\_at, status; admin harakati, oldin/keyin |

- Vaqtlar — `timestamptz`, UTC. Pul — BIGINT, so'mda; float ishlatilmaydi.
- Joylashuv — PostGIS `geography(Point)`; masofa va radius indeks bilan.
- Hujjat raqami shifrlangan saqlanadi; takrorni topish uchun alohida hash ustuni.
- Buyurtmada narx nusxasi saqlanadi — sozlama o'zgarsa, eski buyurtma o'zgarmaydi.
- Foydalanuvchi soft delete bilan o'chiriladi (3-bo'limdagi muddatlar).

## API va real-time

REST API `/api/v1` ostida, OpenAPI hujjati avtomatik chiqadi; holat o'zgarishlari WebSocket orqali real vaqtda keladi.

| Guruh | Asosiy endpointlar |
| --- | --- |
| Auth | POST /auth/telegram, /auth/otp/send, /auth/otp/verify, /auth/refresh, /auth/logout |
| Profil | GET, PATCH /me; POST /me/roles; POST /me/consents; DELETE /me |
| Ishchi | PUT /worker/profile; POST /worker/documents; PUT /worker/availability; POST /worker/status; GET /worker/offers; GET /jobs/open |
| Taklif | POST /offers/{id}/accept, /offers/{id}/decline |
| Buyurtma | POST /orders/quote; POST /orders; GET /orders, /orders/{id}; POST /orders/{id}/cancel, /orders/{id}/repeat |
| Tayinlov | POST /assignments/{id}/checkin, /confirm-arrival, /finish, /confirm, /cash-received, /replace, /sos |
| Overtime, vazifa | POST /assignments/{id}/overtime, /overtime/{oid}/approve, /overtime/{oid}/stop; POST /assignments/{id}/tasks, /tasks/{tid}/accept |
| Baho, nizo | POST /assignments/{id}/review; POST /disputes, /disputes/{id}/evidence, /disputes/{id}/appeal |
| Balans | GET /wallet, /wallet/ledger; POST /wallet/topup; POST /withdrawals (Faza 2) |
| Chat | GET, POST /chats/{id}/messages |
| Katalog | GET /catalog/categories, /catalog/regions, /catalog/districts |
| Admin | /admin/… — verifikatsiya, buyurtma, nizo, moliya, sozlama, broadcast, audit |
| Webhook | POST /webhooks/payme, /webhooks/click, /webhooks/telegram |

- **Ruxsat:** Bearer JWT; har endpoint rol va egalikni tekshiradi.
- **Idempotency-Key:** pul va holatni o'zgartiruvchi har POST'da majburiy; kalit 24 soat saqlanadi.
- **Xato formati:** `{code, message, details}`; noto'g'ri holat — 409 INVALID\_STATE, validatsiya — 422.
- **Rate limit:** auth — daqiqasiga 5, qolgani — foydalanuvchiga daqiqasiga 60.
- **WebSocket `/ws`:** token bilan ulanadi; hodisalar — offer.new, offer.withdrawn, assignment.updated, order.updated, chat.message, wallet.updated. Uzilishdan keyin REST orqali qayta sinxronlanadi.
- **Webhooklar:** Payme — Basic auth va IP tekshiruvi; Click — sign\_string tekshiruvi; ikkalasi idempotent.
- **Versiya:** buzuvchi o'zgarish faqat `/api/v2` da.

## IT xavfsizlik, maxfiylik va nofunksional talablar

Pasport, selfie va joylashuv — eng sezgir ma'lumot: ular shifrlanadi, O'zbekistondagi serverda saqlanadi va har ko'rish jurnalga yoziladi.

| Soha | Talab |
| --- | --- |
| Ma'lumot joyi | Prod baza va fayllar O'zbekistondagi serverda; baza shaxsga doir ma'lumotlar bazalari davlat reyestrida ro'yxatdan o'tkaziladi — qonunning 27-1-moddasi ([manba](https://www.mondaq.com/data-protection/1197754/the-law-on-personal-data-has-been-amended)). 2025 yilda bu talabni yumshatish muhokama qilingan ([manba](https://ad.kun.uz/en/news/2025/07/22/experts-urge-uzbekistan-to-revise-data-localization-rules-to-support-innovation)) — joriy holatni yurist bilan tekshirish |
| Shifrlash | HTTPS (TLS 1.2+); fayllar server tomonda shifrlangan; hujjat raqamlari ustun darajasida shifr + hash |
| Fayllarga kirish | Yopiq bucket, 5 daqiqalik imzoli havola, faqat moderator va undan yuqori; har ko'rish audit jurnalida |
| Autentifikatsiya | OTP limitlari, refresh rotatsiya, admin uchun TOTP 2FA |
| Ruxsat | Har so'rovda RBAC + egalik tekshiruvi |
| Himoya | Rate limit, OWASP ASVS 1-daraja, bog'liqliklarni skanerlash (Dependabot), maxfiy kalitlar koddan tashqarida |
| Loglar | PII yozilmaydi; Sentry'ga yuborishdan oldin tozalanadi |
| Zaxira | Lite: kunlik shifrlangan pg\_dump va fayllar ikkinchi joyga (arzon O'zbekiston storage yoki shifrlangan holda o'z kompyuteringiz), 14 kun saqlanadi; oyiga bir marta tiklash testi. O'sishda — WAL (PITR) |
| Saqlash muddati | Selfie — 30 kun (nizoda — hal bo'lgach 90 kun); hujjatlar — akkaunt o'chirilgach 90 kun; moliyaviy yozuvlar — buxgalter aytgan muddat \[?\]; loglar — 90 kun |
| Telegram | Telegram serverlari chet elda: bot xabarida faqat ilovaga havola, sezgir ma'lumot yo'q |

### Nofunksional talablar

| Ko'rsatkich | Maqsad |
| --- | --- |
| Qurilmalar | Android 8+ (Chrome, WebView), iOS 15+ Safari, Telegram'ning joriy versiyalari; ekran 360 px dan |
| Birinchi yuklanish | 3G da ≤ 3 soniya; boshlang'ich JS ≤ 250 KB (gzip) |
| API tezligi | p95 ≤ 300 ms; taklif yetkazish ≤ 5 soniya |
| Ishlash vaqti | Oyiga 99.5% |
| Cho'qqi yuk | 07:00–09:00; Faza 1 da 200 ta parallel foydalanuvchi \[D\] |
| Soddalik | Tugmalar ≥ 48 px, ikonka + qisqa matn, minimal yozish; asosiy amal ≤ 3 bosishda |
| Tillar | Barcha matnlar tarjima fayllarida: uz-Latn, uz-Cyrl, ru; kirill lotindan avtomatik transliteratsiya qilinib, qo'lda tekshiriladi |
| Vaqt | Bazada UTC, ekranda Asia/Tashkent |

## Yuridik va soliq talablari

Pullik ishga tushishdan oldin to'rt masala hal bo'lishi kerak — tadbirkorlik shakli, shaxsiy ma'lumotlar, to'lov modeli va soliq tuzilmasi; hammasini yurist va buxgalter tasdiqlaydi.

| Masala | Tavsiya | Qachon |
| --- | --- | --- |
| Tadbirkorlik shakli | YaTT pullik komissiyadan oldin ochiladi; pilot bepul, shuning uchun unga qadar daromad yo'q | Pilot oxiri \[D, OS-27\] |
| Investor ulushi | YaTT ulush sota olmaydi — investor uchun MChJ kerak | Seed'dan oldin \[OS-28\] |
| Hujjatlar | Ommaviy oferta, foydalanish shartlari, maxfiylik siyosati, ishchi va employer shartnomalari; jarimalar neustoyka bandi sifatida yoziladi | Pilotdan oldin |
| Shaxsiy ma'lumotlar | Rozilik, O'zbekistonda saqlash, davlat reyestri, uchinchi shaxslarga bermaslik (19-bo'lim) | Pilotdan oldin |
| To'lov modeli | Foydalanuvchilar pulini ushlab turish litsenziya talab qilishi mumkin. Faza 1 — faqat xizmat balansi (avans); Faza 2 — provayder hold/split yoki bank nominal hisobi | Faza 2 dan oldin |
| Fiskal chek | Payme/Click orqali har to'lovda MXIK kodi va fiskal chek | Payme ulanishida |
| Soliq tuzilmasi | Agent (vositachilik) shartnomasi — platforma daromadi faqat komissiya bo'lishi uchun | YaTT ochishda |
| Ishchilar soligi | Tanlangan model — o'zini o'zi band maqomi; stavka va qurilish, yuk, tozalash ruxsat etilgan faoliyatlar ro'yxatida borligi tekshiriladi | Faza 2 \[OS-29\] |
| Bandlik agentligi | Xususiy bandlik agentligi litsenziyasi kerakmi — yurist javob beradi | Faza 2 |
| B2B hujjatlar | Bajarilgan xizmat dalolatnomasi, elektron hisob-faktura (Didox yoki Faktura.uz) | Faza 2 |
| Sug'urta | Baxtsiz hodisa sug'urtasi — sug'urta kompaniyasi bilan | Faza 3 |
| Brend | Yangi qisqa nom tanlanadi, keyin tovar belgisi va .uz domen tekshiriladi | Hozir \[OS-32\] |

Soliq stavkalari va litsenziya talablari 2026 yil holatida mutaxassis tomonidan tasdiqlanishi kerak; bu jadval — tekshiruv ro'yxati, yuridik xulosa emas.

## Analitika, KPI va test

Asosiy o'lchov — buyurtma qanchalik tez va to'liq to'ldirilgani; hajm maqsadlari sizning rejangizdan: Oy 1 — kuniga 15 ishchi, Oy 3 — kuniga 100 ishchi va 20 employer.

| Ko'rsatkich | Oy 1 | Oy 3 |
| --- | --- | --- |
| Kuniga ishlagan ishchilar | 15 | 100 |
| Oylik ishchi-kunlar (25 ish kuni) | 375 | 2,500 |
| Faol employerlar | 10 | 20 |
| Tasdiqlangan ishchilar | 50 | 500 |
| Fill rate \[D\] | ≥ 80% | ≥ 90% |
| Median to'ldirish vaqti \[D\] | < 60 daqiqa | < 30 daqiqa |
| Kelmaslik ulushi \[D\] | < 8% | < 5% |
| Nizo ulushi \[D\] | < 10% | < 5% |
| 30 kunda qayta buyurtma bergan employer \[D\] | 50% | 60% |

Oy 1 — pilotdan keyingi birinchi oy. v1.0 dagi "Oy 3 — 300 bitim" maqsadi shu rejaga almashtirildi.

**Hodisalar:** signup\_started, signup\_completed, verification\_submitted, verification\_approved, order\_quoted, order\_created, offer\_sent, offer\_accepted, offer\_expired, checkin\_ok, checkin\_failed (sabab bilan), no\_show, job\_finished, job\_confirmed, cash\_confirmed, dispute\_opened, dispute\_resolved, review\_submitted, topup, penalty\_applied. Vosita — 10$ serverda PostHog sig'maydi, shuning uchun o'z `events` jadvali \[D\].

### Test

| Tur | Nima tekshiriladi | Vosita |
| --- | --- | --- |
| Unit | Holat o'tishlari, narx formulasi, matching balli, ledger (har tranzaksiya yig'indisi 0) | pytest |
| Integratsiya | Payme/Click sandbox, Eskiz, Telegram initData | pytest + testcontainers |
| E2E | Ro'yxat → buyurtma → taklif → check-in → yakun → baho | Playwright |
| Yuk | Ertalabki cho'qqi, 200 parallel foydalanuvchi | k6 yoki Locust |
| Pilot | 5 employer, 30 ishchi, 2 hafta, bepul | Real foydalanish |

Qabul mezoni: kritik oqimlar testdan o'tgan, ledger farqi 0, ochiq kritik xato yo'q.

## Bosqichlar va muddatlar

Birinchi Faza 1-lite chiqadi — bepul pilot uchun minimal mahsulot: taxminan 10.5 hafta to'liq kunlik ish, kechqurun va dam olish kunlari ishlaganda 21–28 hafta \[OS-20, OS-25\].

&#91;embedded content: yo’l xaritasi · 5 faza, 4 darvoza\]

Muddatlar haftasiga 15–20 soatga hisoblangan; darvozadan o'tmagan faza boshlanmaydi. Komissiya faqat Faza 1 to'liq tugab, YaTT ochilgach yoqiladi.

### Faza 1-lite tarkibi

| Modul | Faza 1-lite | Keyinroq |
| --- | --- | --- |
| Kirish | Telegram Mini App + SMS kod | MyID (Faza 3) |
| Tillar | O'zbek (lotin, kirill), rus | O'zgarishsiz |
| Kategoriya, hudud | Admin yoqadi; start — qurilish, yuk, uy tozalash; Toshkent | Yangi kategoriya va viloyatlar — istalgan vaqt, admin orqali |
| Narx | Qat'iy + min/max; uy xizmatlari — hajm bo'yicha | Dinamik narx (Faza 2) |
| Matching | To'lqinlar + Ochiq ishlar lentasi | O'zgarishsiz |
| Check-in | GPS + selfie + employer tasdig'i | Avtomatik yuz solishtirish (Faza 3) |
| Baho | Reyting + Ishonchlilik (pulsiz jazolar) | Moliyaviy jarimalar (Faza 1 to'liq) |
| Pul | Pilot bepul, komissiya yo'q | Balans, ledger, naqd komissiya (Faza 1 to'liq); onlayn to'lov (Faza 2) |
| Aloqa | Bot xabarlari; telefon tayinlovdan keyin | Chat, Web Push (Faza 1 to'liq) |
| Nizo | Admin qo'lda, bot orqali | Nizo ekrani (Faza 1 to'liq) |
| Overtime, vazifa | Tomonlar kelishadi, admin qayd qiladi | Ilovada (Faza 1 to'liq), avto-hisob (Faza 2) |
| Admin | Web: verifikatsiya, buyurtmalar, operatsiya taxtasi. Admin bot: kategoriya, ish turi, narx, hudud, signallar | Moliya, broadcast, Excel import (Faza 1 to'liq) |
| Server | Bitta VPS: FastAPI (API + bot webhook + scheduler), PostgreSQL, Redis, Nginx | Celery, MinIO, alohida bot servisi — o'sishda |

### Ish hajmi (Faza 1-lite)

| Blok | To'liq kun, hafta |
| --- | --- |
| Backend yadrosi: auth, profillar, katalog, hududlar | 2 |
| Buyurtma, matching, lenta, bot | 2.5 |
| Check-in, yakunlash, baho | 1.5 |
| Web frontend, 3 til | 2.5 |
| Admin: Refine (katalogsiz) + admin bot | 1.5 |
| Test, deploy | 0.5 |
| Jami | 10.5 hafta, taxminan 420 soat |

O'zbek kirill matnlari lotindan avtomatik transliteratsiya qilinib, qo'lda tekshiriladi — uchinchi til alohida tarjima talab qilmaydi.

## Xavflar

Eng katta xavf texnik emas: yolg'iz asoschining vaqti va birinchi employerlarni topish. Jadval muhimlik tartibida.

| Xavf | Nima qilamiz |
| --- | --- |
| Asoschi vaqti: faqat kechqurun va dam olish kunlari | Faza 1-lite, tayyor komponentlar (Refine, shadcn/ui), admin ishini avtomatlashtirish; pilotdan keyin yarim stavka moderator |
| Employer topilmaydi | Faza 0 da 10 ta employer bilan suhbat; bepul pilot; qurilish firmalari va kargo bilan to'g'ridan-to'g'ri ishlash |
| Uy xizmatlari va bola qarashda majburiy tekshiruv yo'q \[OS-30\] | Bitta jiddiy hodisa platforma obro'sini yo'qotadi. Ixtiyoriy "Tekshirilgan" belgilari va filtrlar, SOS, reyting; birinchi hodisadan keyin qoida qayta ko'riladi. Tavsiya: bola qarashda sudlanmaganlik ma'lumotnomasini majburiy qilish |
| Tungi ishlar 24/7, lekin tunda admin yo'q \[OS-31\] | Tunda avtomatik almashtirish va SMS; SOS — 112 va favqulodda kontakt; ishchi tungi takliflarni o'chira oladi |
| Yosh va jins filtri \[OS-6\] | Kamsitish haqidagi e'tirozlar xavfi; filtr faqat uy xizmatlarida, yurist bilan tekshiriladi |
| 10$ server \[OS-21\] | 10$ ga asosan 1 GB RAM li server chiqadi (2-bo'lim) — pilot uchun tor, lekin Lite arxitektura bilan ishlaydi; 100 ishchi/kun bosqichida 2–4 GB ga o'tish |
| Platformani chetlab o'tish | Almashtirish, reyting va kafolat qiymati; chatda ogohlantirish; isbotlangan holatda blok |
| Ishchilar texnikadan qiynaladi | Agent bilan ro'yxat, katta tugmalar, bot orqali Qabul, kirill yozuv |
| Avtomatik o'rtacha baholar reytingni sun'iy barqaror qiladi \[OS-18\] | Avtomatik baholar ulushi hisobotda ko'rinadi; 30% dan oshsa, baho eslatmalari kuchaytiriladi \[D\] |
| GPS aldash | Employer tasdig'i, selfie, nizo dalillari |
| Yuridik: to'lov litsenziyasi, soliq, lokalizatsiya | Faza 1 da begona pul yo'q; yurist va buxgalter bilan tekshirish (20-bo'lim) |
| Qishki mavsumda talab tushadi | Uy xizmatlari va ombor ishlari |
| Ma'lumot sizib chiqishi | Shifrlash, eng kam ruxsat, audit jurnali |

## Qarorlar va ochiq savollar

Javoblaringiz bilan 19 ta masala hal qilindi; 2 tasi ochiq — o'zini o'zi band ro'yxati va yangi nom, qolgan 13 tasida default ishlaydi. Holat ustunini o'zingiz o'zgartirishingiz mumkin.

| № | Mavzu | Qaror | Holat |
| --- | --- | --- | --- |
| OS-1 | Platforma | Bitta frontend: PWA + Telegram Mini App; bot — xabarlar | Tasdiqlandi |
| OS-2 | Tillar | O'zbek (lotin), o'zbek (kirill), rus | O'zgartirildi |
| OS-3 | Hudud | Toshkent shahri; viloyat va tumanlarni admin yoqadi | O'zgartirildi |
| OS-4 | Kategoriyalar | Start: qurilish, yuk, uy tozalash; yangi kategoriya va ish turlarini admin bot yoki panel orqali qo'shadi | O'zgartirildi |
| OS-5 | Ishchi tanlash | Avtomatik to'lqinlar + Ochiq ishlar lentasi, ishchi o'zi tanlaydi; uy xizmatlarida employer 3 nomzoddan | Tasdiqlandi |
| OS-6 | Jins va yosh | Kategoriyalar hammaga ochiq; uy xizmatlarida employer jins va yosh toifasini tanlaydi | O'zgartirildi |
| OS-7 | Narx birligi | Qurilish, yuk — kun yoki yarim kun; uy xizmatlari — ish hajmi | O'zgartirildi |
| OS-8 | Uy xizmatlari narxi | Admin bot yoki panel orqali kiritiladi; default birliklar: tozalash — m², oshpazlik — mehmon soni, bola qarash — soat × bola soni | O'zgartirildi |
| OS-9 | Ko'p kunlik buyurtma | Har kun alohida check-in, yakun va to'lov | Default |
| OS-10 | Qisman to'lgan buyurtma | Employer tanlaydi: boshlash yoki kutish | Default |
| OS-11 | Asbob, tushlik, yo'l haqi | Buyurtmada maydon; ishchi asbobi +10% | Default |
| OS-12 | Telefon, tashqi to'lov | Telefon tayinlovdan keyin; chatdagi gapga ogohlantirish | Tasdiqlandi |
| OS-13 | Naqd rejim | Ishchi naqd oladi, komissiyalar balanslardan, birinchi 3 ta bepul | Tasdiqlandi |
| OS-14 | Komissiya | Employer +10%, ishchi −3% | Tasdiqlandi |
| OS-15 | Jarima kimga | 100% jabrlangan tomonga | Tasdiqlandi |
| OS-16 | Qarz | Qarz bor ekan naqd ish yo'q | Tasdiqlandi |
| OS-17 | Kelmaslik jazosi | 11-bo'limdagi yagona jadval | Default |
| OS-18 | Bahosiz ish | 48 soatda baho bo'lmasa — avtomatik o'rtacha baho (13-bo'lim) | O'zgartirildi |
| OS-19 | Yangi employer bonusi | Faza 2, bitta kartaga bir marta | Default |
| OS-20 | Birinchi bosqich | Faza 1-lite | Tasdiqlandi |
| OS-21 | Server | O'zbekistondagi VPS, sinov davrida \~10$/oy | Tasdiqlandi |
| OS-22 | Xarita | Yandex Maps; narxi tekshiriladi | Default |
| OS-23 | SMS | Eskiz.uz | Default |
| OS-24 | Yuz solishtirish | Faza 1 — admin qo'lda; Faza 3 — avtomatik | Default |
| OS-25 | Vaqt | Haftasiga 15–20 soat deb hisoblandi | Default |
| OS-26 | Dizayn | Tayyor UI kit (shadcn/ui) | Default |
| OS-27 | YaTT | Pullik komissiyadan oldin | Default |
| OS-28 | MChJ | Seed investordan oldin | Default |
| OS-29 | O'zini o'zi band | Ruxsat etilgan faoliyatlar ro'yxatini tekshirish | Ochiq |
| OS-30 | Uy xizmatlari tekshiruvi | Majburiy emas; ixtiyoriy "Tekshirilgan" belgilari | O'zgartirildi |
| OS-31 | Tungi ishlar | 24/7 ochiq; tunda avtomatik qoidalar | O'zgartirildi |
| OS-32 | Nom | Yangi qisqa nom tanlanadi, keyin domen va tovar belgisi | Ochiq |
| OS-33 | Admin soatlari | Platforma 24/7; qo'lda admin ishi 07:00–21:00 | Default |
| OS-34 | Admin bot | Kategoriya, ish turi, narx, hudud va signallar Telegram admin botda; moliyaviy sozlamalar TOTP bilan (16-bo'lim) | Tasdiqlandi |

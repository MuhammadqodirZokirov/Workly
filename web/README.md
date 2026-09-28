# web — ishchi va ish beruvchi ilovasi

React 19 + TypeScript + Vite + Tailwind 4 + TanStack Query. Bitta kod brauzerda, PWA sifatida va Telegram Mini App ichida ishlaydi (TZ 2). Dizayn: [docs/design/DESIGN.md](../docs/design/DESIGN.md).

```bash
npm install
npm run dev      # http://localhost:5173 (/api → http://localhost:8000)
npm test         # vitest
npm run build    # dist/ — Nginx orqali beriladi
```

## Tuzilma

```
src/
  lib/        api (JWT + refresh rotatsiya), auth (Telegram initData / SMS), i18n (uz-Latn, uz-Cyrl, ru), format, catalog
  components/ ui (tugma, input, karta, chip…), shared (pastki menyu, ish kartasi)
  pages/      Welcome, Login, RoleSelect, Profile
    worker/   WorkerHome (takliflar, "Hozir bo'shman"), WorkerJobs (takliflar / lenta / ishlarim), WorkerProfilePage (hujjatlar)
    employer/ EmployerHome, NewOrder (narx hisobi), Orders, OrderDetail
```

## Muhim qarorlar

- **Kirish:** Telegram ichida initData bilan avtomatik; brauzerda telefon + SMS kod. Parol yo'q (TZ 3).
- **Token:** access 15 daqiqa; 401 bo'lsa refresh bir marta (parallel so'rovlar bitta refresh'ni kutadi — backend eski refresh qayta ishlatilsa barcha sessiyalarni yopadi).
- **Joylashuv:** brauzer geolokatsiyasi; ruxsat bo'lmasa — tuman markazi (taxminiy). Yandex Maps (OS-22) — keyingi bosqich.
- **Selfie:** `capture="user"` — telefonda to'g'ridan-to'g'ri old kamera. Backend galereyadan olinganini aniqlay olmaydi.

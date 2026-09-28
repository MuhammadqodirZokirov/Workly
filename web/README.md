# web — ishchi va employer ilovasi

React 18 + TypeScript + Vite, PWA + Telegram Mini App (TZ 2-bo'lim). Hali boshlanmagan — Faza 1-lite 4-bloki.

Backend bilan kirish:
- Mini App: `POST /api/v1/auth/telegram` (`{init_data: Telegram.WebApp.initData}`)
- Brauzer: `POST /api/v1/auth/otp/send` → `POST /api/v1/auth/otp/verify`

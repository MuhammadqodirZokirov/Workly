# Workly — brend qoidalari (qisqa)

To'liq versiya: [WORKLY_Brand_Book_v1.0.pdf](WORKLY_Brand_Book_v1.0.pdf)

**Brend satri:** Ish top. Ishchi top. Ishonchli.
**G'oya:** Tez · Ishonch · Yangilik · Regional (O'zbekiston, Markaziy Osiyo, MDH).

## Ranglar

| Token | HEX | Qo'llanish |
|---|---|---|
| `blue` (Workly Blue) | `#2563EB` | Asosiy rang, primary CTA |
| `orange` (Workly Orange) | `#F97316` | Accent, muhim signal |
| `midnight` | `#0F172A` | Matn, dark UI |
| `mist` | `#E2E8F0` | Divider, surface |
| `snow` | `#F8FAFC` | Fon |

UI nisbati: 55% blue · 25% neutral · 20% orange (taxminan).

## Shriftlar

- **Inter** — asosiy: UI, sarlavha, CTA, navigatsiya
- **Manrope** — marketing, katta promo sarlavhalar

## UI

- Primary CTA — ko'k to'la tugma; Secondary — oq fon + chegara
- Ikonlar — sodda, yumaloq geometriya
- Ovoz: qisqa va to'g'ri gaplar, oddiy ishchan til, ishchi va employer'ga teng murojaat

## Logo

- Oq/och fonda — asosiy logo; qorong'i fonda — oq variant
- Atrofida kamida belgi balandligining 0.5x bo'sh joy
- Cho'zmang, outline bermang, rangini va soyasini o'zgartirmang

## Fayllar

| Fayl | Nima |
|---|---|
| `workly-logo.webp` | Asosiy logo (belgi + so'z) |
| `workly-mark.webp` | Faqat W belgisi |
| `workly-icon-dark.webp` | Qorong'i dumaloq ikonka (Telegram bot avatari uchun mos) |
| `workly-brand-board.webp` | Brend doskasi |

> Hozircha logolar rastr (webp). Frontend va ilova ikonkalari (PWA, favicon) uchun **SVG** variant kerak bo'ladi.

## Frontend tokenlari (Tailwind uchun)

```js
colors: {
  brand: { blue: "#2563EB", orange: "#F97316", midnight: "#0F172A", mist: "#E2E8F0", snow: "#F8FAFC" },
},
fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], display: ["Manrope", "Inter", "sans-serif"] },
```

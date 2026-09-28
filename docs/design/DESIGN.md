# Workly — web ilova dizayni

Manba: dizaynerning ekranlari (`screens/`), boardlar (`boards/`), fonlar (`web/public/backgrounds/`) va [brend qoidalari](../brand/BRAND.md). Quyida — frontend uchun kelishilgan qoidalar va **TZ bo'yicha tuzatishlar**.

## Tokenlar

| Token | Qiymat | Qayerda |
|---|---|---|
| `blue` | `#2563EB` | Asosiy tugma, faol chip, narx, faol tab |
| `orange` | `#F97316` | "Bugun", "Tungi ish", signal, xarita pinlari (tanlangan) |
| `midnight` | `#0F172A` | Matn, qorong'i fon |
| `mist` | `#E2E8F0` | Chegara, divider, input fon |
| `snow` | `#F8FAFC` | Sahifa foni |
| Radius | karta 16px, input/tugma 12px, chip 999px | |
| Soya | `0 4px 16px rgb(15 23 42 / 0.06)` | Kartalar |
| Shrift | Inter (UI), Manrope (splash/promo sarlavha) | |
| Tugma | balandlik ≥ 48px (TZ 19), to'la kenglik; primary — ko'k, secondary — oq + chegara | |

## Komponentlar (ekranlardan)

- **Sarlavha:** chapda logo, o'ngda joylashuv tanlagich ("Toshkent ▾") va avatar
- **Qidiruv:** kulrang maydon + o'ngda filtr ikonkasi
- **Kategoriyalar:** rangli doira ichida ikonka + nom (Qurilish, Yuk tashish, Ombor, Uy xizmatlari)
- **"Yaqin ishlar" banneri:** ko'k gradient, xarita pini
- **Segment tab:** Ishlar / Ishchilar
- **Ish kartasi:** chapda rasm, sarlavha, tuman, narx (ko'k), o'ngda to'q sariq teg ("Bugun"), saqlash ikonkasi
- **Ishchi kartasi:** rasm, ism, mutaxassislik, ★ reyting (baholar soni), holat tegi (Bo'sh / Band)
- **Pastki menyu:** Bosh sahifa · Ishlar · (+) markaziy tugma · Xabarlar · Profil
- **Profil menyusi:** ikonkali ro'yxat (e'lonlarim, saqlanganlar, xabarlar, to'lovlar, sozlamalar, yordam, chiqish)
- **Xarita:** pinlar + pastda tanlangan ish kartasi va "Yo'nalish" tugmasi

## Fonlar

| Fayl | Qayerda |
|---|---|
| `03_blue_orange_waves`, `01_minimal_light` | Splash, kirish |
| `02_city_central_asia`, `11_blue_sky` | Rol tanlash, onboarding |
| `05_soft_geometric`, `07_pastel_waves`, `10_warm_cream` | Bo'sh holatlar (ish yo'q, xabar yo'q) |
| `04_dark_tech`, `09_cobalt_waves`, `12_dark_future` | Qorong'i rejim / Telegram qorong'i mavzusi |
| `06_sunset_city`, `08_misty_city` | Promo, tungi ish |

Har fon 2 o'lchamda: `_1080.webp` (katta ekran), `_720.webp` (telefon). Fon ustidagi matn uchun oq/qorong'i gradient qatlami — kontrast WCAG AA.

## TZ bo'yicha tuzatishlar (dizayndan farq qiladi)

| Ekran | Dizaynda | Qilinadi | Sabab |
|---|---|---|---|
| Ro'yxatdan o'tish | Parol, Google/Apple | Telegram (Mini App'da avtomatik) + telefon SMS kodi | TZ 3: parol yo'q |
| Asosiy ma'lumotlar | "Ismingiz", "Shahar" | Familiya, Ism, Otasining ismi; tumanlar (bir nechta) | Hujjatdagidek; matching tuman bo'yicha |
| Ishchi profili | Qo'ng'iroq tugmasi, "Xabar yozish" | Faqat tayinlovdan keyin | TZ 4, 15: telefon tayinlovgacha yashirin, chetlab o'tishning oldini olish |
| Ishchi profili / kartalar | "150 000 so'm/kun" | Ko'rsatilmaydi (narx — admin, kategoriya bo'yicha) | TZ 8: Faza 1 qat'iy narx |
| Ish kartasi (ishchiga) | "150 000 so'm/kun" | "Siz olasiz: …" — sof summa | TZ 4 |
| Yangi ish joyi | "Maosh" maydoni | Narx avtomatik hisoblanadi (quote), bekor qilish qoidalari ko'rsatiladi | TZ 5, 8 |
| Yangi ish joyi | Sana + "7 kun" | Sana, boshlanish vaqti, davomiylik (yarim kun / kun / bir necha kun), ishchi soni, asbob, tushlik, yo'l haqi | TZ 5 |
| Ishchilar ro'yxati | Barcha ishchilar katalogi | "Sevimli ishchilar"; tanlash faqat uy xizmatlarida (3 nomzod) | TZ 7: avtomatik to'lqinlar |
| Holat tegi | "Onlayn" | "Bo'sh" (Hozir bo'shman) / "Band" | TZ 4 |
| Chat | Ovozli xabar | Matn, rasm, joylashuv | TZ 15 |
| Kompaniya profili | — | STIR tekshiruvi holati va "Tasdiqlangan ish beruvchi" belgisi | TZ 5 |

## Tillar

Barcha matnlar `uz-Latn`, `uz-Cyrl`, `ru` tarjima fayllarida; kirill lotindan avtomatik (backend `translit`), qo'lda tekshiriladi.

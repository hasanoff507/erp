# Kod uchun spetsifikatsiya — yagona manba

Bu papka — ilovani yozish uchun **yagona va to'liq** spetsifikatsiya. Kod faqat shu hujjatlarga tayanadi. Tarix, tadqiqot va tekshiruv yozuvlari boshqa joyda (`spec/tarix/`, `research_notes/`) — kod yozishda ular kerak emas.

## Qoidalar

1. **Avval spec, keyin kod.** Spec'da yo'q yoki noaniq narsa kodda o'zboshimchalik bilan hal qilinmaydi: avval tegishli faylga yoziladi (yoki `26-ochiq-savollar-reestri.md` ga qo'shiladi), keyin kod yoziladi.
2. **Spec o'zgarsa** — shu commit'da bog'liq fayllar ham yangilanadi (masalan maydon qo'shilsa: `11` model → `12` DB → `17–20` API → `07` ekran) va `01-qarorlar.md` ga qator qo'shiladi.
3. **Ziddiyat bo'lsa** ustunlik tartibi: `01-qarorlar.md` → mavzu bo'yicha asosiy fayl (masalan DB uchun `12`, API uchun `17–20`) → boshqalar.
4. Belgilar: *taxmin* — tasdiqlanmagan raqam; *ochiq savol* — tashqi javob kutilmoqda (kod sozlama/adapter ortida yoziladi); *(sana: …)* — o'zgarish izi.
5. Tashqi buxgalteriya/ERP tizimlari bilan hech qanday bog'liqlik yo'q — mahsulot noldan quriladi.

## O'qish tartibi

| # | Fayl | Nima uchun | Qachon o'qiladi |
|---|---|---|---|
| 01 | `01-qarorlar.md` | Barcha qabul qilingan qarorlar (tarif, auth, chek, fiskal, nomlash…) | **Har doim birinchi** |
| | **Mahsulot — nima quriladi** | | |
| 02 | `02-rollar-va-ssenariylar.md` | 5 rol, kundalik ssenariylar, huquqlar matritsasi | Boshida |
| 03 | `03-modullar-talablari.md` | 18 modul, foydalanuvchi hikoyalari (US-Mxx-nn), qabul mezonlari | Har modul oldidan |
| 04 | `04-biznes-jarayonlar.md` | BP-01…13 — hujjat oqimlari | Har modul oldidan |
| 05 | `05-mvp-chegarasi.md` | Must/Should/Could, tarif (99 000), MVP'dan keyingilar | Boshida |
| 06 | `06-ekranlar-umumiy.md` | Ekranlar ro'yxati va oqimlar (POS/BO/ADM) | Frontend oldidan |
| 07 | `07-ekran-tafsilotlari.md` | 37 ekran: maydonlar, validatsiya, holatlar, API, ruxsatlar | Har ekranni yozishda |
| 08 | `08-dizayn-tizimi.md` | Tokenlar, komponentlar, formatlash, chek/yorliq shablonlari, matnlar | Frontend oldidan |
| 09 | `09-ai-funksiyalar.md` | AI-01/03/05/06 — mahsulot talablari | AI bosqichi oldidan |
| | **Arxitektura — qanday quriladi** | | |
| 10 | `10-umumiy-arxitektura.md` | Komponentlar, stack, oqimlar, muhitlar | Boshida |
| 11 | `11-malumotlar-modeli.md` | Jadvallar va registrlar (mantiqiy model) | Backend oldidan |
| 12 | `12-db-sxema.md` | To'liq PostgreSQL DDL, RLS, seed, migratsiya tartibi | Migratsiyalarni yozishda |
| 13 | `13-provodka-qoidalari.md` | Har hujjat uchun Dt/Kt, FIFO/AVECO, QQS, davr yopish | Posting xizmatida |
| 14 | `14-autentifikatsiya-oauth2.md` | O'z OAuth 2.0 AS, Google kirish, Telegram OTP, bloklash, admin panel | 1-bosqichda |
| 15 | `15-xavfsizlik-va-audit.md` | Ruxsatlar katalogi va matritsasi, RLS, audit, backup | 1-bosqichda |
| 16 | `16-offline-sync.md` | Outbox, `/sync/push|pull`, to'qnashuvlar, 48 soat, markirovka | Kassa bosqichida |
| 17 | `17-api-umumiy.md` | API qoidalari, nomlash, xato formati va kodlar katalogi | Har endpoint oldidan |
| 18 | `18-api-kassa.md` | Kassa, qaytarish, chegirma, qarz, kassa puli, to'lovlar, voqealar | Kassa bosqichida |
| 19 | `19-api-ombor.md` | Katalog, narx, yorliq, import, qoldiq, kirim, ko'chirish, inventarizatsiya | Ombor bosqichida |
| 20 | `20-api-moliya-admin.md` | QQS, buxgalteriya, hisobotlar, xodimlar, filiallar, xarajat, obuna, bildirishnoma, AI | Tegishli bosqichda |
| 21 | `21-integratsiyalar.md` | OFD, e-faktura, CRPT, E-IMZO, to'lovlar, Google, Telegram, SMS (zaxira), Claude | Integratsiya bosqichida |
| 22 | `22-ai-qatlami.md` | `AiProvider`, limitlar, eval, OCR quvuri | AI bosqichida |
| 23 | `23-backend-arxitekturasi.md` | FastAPI modullari, `tenant_transaction`, posting xizmati, SAQ, testlar | Backend boshida |
| 24 | `24-frontend-arxitekturasi.md` | FSD, Effector, shadcn, orval, PWA, platformalar va chop etish | Frontend boshida |
| 25 | `25-nofunksional-talablar.md` | Tezlik, sig'im, uskunalar, xarajat, qo'llab-quvvatlash | Rejalashtirishda |
| 26 | `26-ochiq-savollar-reestri.md` | Har ochiq savol + qaror yoki vaqtinchalik taxmin | Noaniqlik bo'lganda |
| 27 | `27-backlog.md` | Bosqichlar ketma-ketligi va "tayyor" ta'rifi (jamoa: asoschi + Claude) | Ish rejasi |
| 28 | `28-android-pos.md` | Kotlin POS — MVP'dan keyin | Keyinroq |

## Bosqich bo'yicha minimal o'qish to'plami

| Bosqich | O'qiladigan fayllar |
|---|---|
| Skelet + auth | 01, 10, 23, 24, 12 (§1–5), 14, 15, 17 |
| Katalog va ombor | 03 (M04–M07, M09), 04, 11, 12, 13, 19, 07 (BO-02…05, BO-18) |
| Kassa (veb) | 03 (M01–M03, M08, M16), 04, 13, 16, 18, 07 (POS-01…15), 08 |
| Moliya, hisobot, obuna | 03 (M10–M12, M15, M17, M18), 13, 20, 07 (BO-06…21) |
| Integratsiyalar | 21, 16, 18–20 tegishli bo'limlar |
| AI | 09, 22, 20 (AI bo'limi) |

## Kod tashqarisidagi hujjatlar

- `spec/tarix/` — tekshiruvlar, qabul agentlari qarorlari, kamchiliklar tahlili, tuzatishlar jurnali, rasmiy xatlar (`tarix/tekshiruv/rasmiy-xatlar.md`).
- `research_notes/` — bozor va texnik tadqiqot (manbalar).

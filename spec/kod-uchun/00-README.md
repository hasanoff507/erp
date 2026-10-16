# Kod uchun spetsifikatsiya — yagona manba

**Maqsad:** kod uchun spec'ga kirish nuqtasi va o'qish tartibi. · **Kim uchun:** hammasi. · **Bog'liq fayllar:** 01–34. · **Holat:** joriy, 2026-10-16.

Bu papka — ilovani yozish uchun **yagona va to'liq** spetsifikatsiya. Kod faqat shu hujjatlarga tayanadi. Tarix, tadqiqot va tekshiruv yozuvlari boshqa joyda (`spec/tarix/`, `research_notes/`) — kod yozishda ular kerak emas.

## Qoidalar

1. **Avval spec, keyin kod.** Spec'da yo'q yoki noaniq narsa kodda o'zboshimchalik bilan hal qilinmaydi: avval tegishli faylga yoziladi (yoki `26-ochiq-savollar-reestri.md` ga qo'shiladi), keyin kod yoziladi.
2. **Spec o'zgarsa** — shu commit'da bog'liq fayllar ham yangilanadi (masalan maydon qo'shilsa: `11` model → `12` DB → `17–20` API → `07` ekran) va `01-qarorlar.md` ga qator qo'shiladi.
3. **Ziddiyat bo'lsa** ustunlik tartibi: `01-qarorlar.md` → mavzu bo'yicha asosiy fayl (masalan DB uchun `12`, API uchun `17–20`) → boshqalar.
4. Belgilar: *taxmin* — tasdiqlanmagan raqam; *(qaror #N)* — `01-qarorlar.md` dagi qarorga havola; **26 #N (OQ-0xx)** — `26-ochiq-savollar-reestri.md` dagi band (holati faqat **Yopildi** yoki **Tashqi javob kerak**; ikkinchisida kod vaqtinchalik standart bilan sozlama/adapter ortida yoziladi). Fayllarning "Ochiq savollar" bo'limlarida faqat tashqi javob kutayotgan bandlar 26 raqami bilan qoladi; yopilgan savollarga matn to'g'ridan-to'g'ri 26 yoki qarorga havola qiladi (qaror #59). Fayllarda faqat **joriy haqiqat** yoziladi — o'zgarishlar tarixi git'da va `spec/tarix/` da.
5. Har fayl boshida standart blok: **Maqsad · Kim uchun · Bog'liq fayllar · Holat**.
6. Mahsulot noldan quriladi va yadro 1C'siz ishlaydi. 1C bilan bog'lanish faqat alohida **1C integratsiya moduli** orqali (qaror #36–#42): kanal faqat COM (Do'kon agentining 1C imkoniyati, bulutdan pull), ERP → 1C bir tomonlama, MVP'dan keyin Bosqich 7 — `33-1c-integratsiya.md` (server moduli `onec_integration`), `34-1c-agent.md` (agent); tadqiqot — `research_notes/1c-integratsiya/`.
7. **Do'kon agenti** (qaror #60) — do'kon Windows PK'sidagi yagona lokal dastur: fiskal ko'prik (POS → FM → OFD) va LAN printer/tarozi — Bosqich 5, 1C — Bosqich 7. Ochiq bulut OFD API yo'q; MVP kodi `ERP_FISCAL_PROVIDER=fake` bilan yoziladi, real fiskal adapter fiskal hamkor javobidan keyin (26 #109).

## O'qish tartibi

| # | Fayl | Nima uchun | Qachon o'qiladi |
|---|---|---|---|
| 01 | `01-qarorlar.md` | Barcha qabul qilingan qarorlar #1–#71 (tarif, auth, chek, fiskal — 48 soatlik blok #43, markirovka #62, e-TTN #63, karta/UzQR #64; Do'kon agenti #60 va uning infratuzilmasi #66, AI shaxsiy ma'lumot #61, hosting #65, qarz to'lovi cheki #67, POS fiskal natijasi #68, yopilgan davrga kech voqealar #69, obuna to'lovi #70, integratsiyalangan karta terminali #71…) | **Har doim birinchi** |
| | **Mahsulot — nima quriladi** | | |
| 02 | `02-rollar-va-ssenariylar.md` | 5 rol, kundalik ssenariylar, huquqlar matritsasi | Boshida |
| 03 | `03-modullar-talablari.md` | 18 modul + M19 (1C integratsiyasi, MVP'dan keyin), 105 ta foydalanuvchi hikoyasi (US-Mxx-nn; 87 tasi M01–M18, 18 tasi M19), qabul mezonlari | Har modul oldidan |
| 04 | `04-biznes-jarayonlar.md` | BP-01…15 — tranzaksion hujjat oqimlari (BP-14 — kunni 1C ga yuborish, BP-15 — bank tushumi tasdig'i) | Har modul oldidan |
| 05 | `05-mvp-chegarasi.md` | Must/Should/Could, tarif (99 000), MVP'dan keyingilar | Boshida |
| 06 | `06-ekranlar-umumiy.md` | Ekranlar ro'yxati va oqimlar (POS/BO/ADM) | Frontend oldidan |
| 07 | `07-ekran-tafsilotlari.md` | 41 ekran (POS-01…16, BO-01…24, ADM-01; 39 tasi MVP, BO-22/23 — M19): maydonlar, validatsiya, holatlar, API, ruxsatlar | Har ekranni yozishda |
| 08 | `08-dizayn-tizimi.md` | Tokenlar, komponentlar, formatlash, chek/yorliq shablonlari, matnlar | Frontend oldidan |
| 09 | `09-ai-funksiyalar.md` | AI-01/03/05/06 — mahsulot talablari | AI bosqichi oldidan |
| | **Arxitektura — qanday quriladi** | | |
| 10 | `10-umumiy-arxitektura.md` | Komponentlar (Do'kon agenti bilan), stack, oqimlar, fiskal yo'l variantlari, muhitlar | Boshida |
| 11 | `11-malumotlar-modeli.md` | Jadvallar va registrlar (mantiqiy model) | Backend oldidan |
| 12 | `12-db-sxema.md` | To'liq PostgreSQL DDL, RLS, seed, migratsiya tartibi | Migratsiyalarni yozishda |
| 13 | `13-provodka-qoidalari.md` | Har hujjat uchun Dt/Kt (NSBU №21: 5710 + 9430 komissiya, 9390, `0000`, §2.26 QQS hisob-kitobi), FIFO/AVECO, QQS, davr yopish | Posting xizmatida |
| 14 | `14-autentifikatsiya-oauth2.md` | O'z OAuth 2.0 AS, Google kirish, Telegram OTP, bloklash, admin panel | 1-bosqichda |
| 15 | `15-xavfsizlik-va-audit.md` | Ruxsatlar katalogi va matritsasi, RLS, audit, backup | 1-bosqichda |
| 16 | `16-offline-sync.md` | Outbox, `/sync/push|pull`, to'qnashuvlar, 24/40/46 soat ogohlantirish va 48 soatlik blok, markirovka | Kassa bosqichida |
| 17 | `17-api-umumiy.md` | API qoidalari, nomlash, xato formati va kodlar katalogi | Har endpoint oldidan |
| 18 | `18-api-kassa.md` | Kassa, qaytarish, chegirma, qarz, kassa puli, to'lovlar, voqealar | Kassa bosqichida |
| 19 | `19-api-ombor.md` | Katalog, narx, yorliq, import, qoldiq, kirim, ko'chirish, inventarizatsiya | Ombor bosqichida |
| 20 | `20-api-moliya-admin.md` | QQS, buxgalteriya, hisobotlar, xodimlar, filiallar, xarajat, obuna, bildirishnoma, AI | Tegishli bosqichda |
| 21 | `21-integratsiyalar.md` | Fiskal (`FiscalPort`, Do'kon ko'prigi / hamkor bulut), e-faktura, e-TTN, CRPT, E-IMZO, to'lovlar va UzQR, Google, Telegram, SMS (zaxira), Claude | Integratsiya bosqichida |
| 22 | `22-ai-qatlami.md` | `AiProvider`, limitlar, eval, OCR quvuri | AI bosqichida |
| 23 | `23-backend-arxitekturasi.md` | FastAPI modullari, `tenant_transaction`, posting xizmati, SAQ, testlar | Backend boshida |
| 24 | `24-frontend-arxitekturasi.md` | FSD, Effector, shadcn, orval, PWA, platformalar va chop etish | Frontend boshida |
| 25 | `25-nofunksional-talablar.md` | Tezlik, sig'im, uskunalar, xarajat, qo'llab-quvvatlash | Rejalashtirishda |
| 26 | `26-ochiq-savollar-reestri.md` | OQ-001…OQ-102 va 1C savollari: Jadval A — Yopildi (javob, manba, qaror), Jadval B — Tashqi javob kerak (kim, xat/test, vaqtinchalik standart, bloklaydigan bosqich) | Noaniqlik bo'lganda |
| 27 | `27-backlog.md` | Bosqichlar ketma-ketligi, har bosqich US-ID ro'yxati, "tayyor" ta'rifi, tashqi bog'liqliklar va xatlar (jamoa: asoschi + Claude) | Ish rejasi |
| 28 | `28-android-pos.md` | Kotlin POS — MVP'dan keyin (veb bilan bir xil `FiscalPort`, 48 soatlik blok, karta rekvizitlari) | Keyinroq |
| | **Dasturchi uchun yordamchi hujjatlar** | | |
| 29 | `29-atamalar-lugati.md` | Atamalar: o'zbekcha / ruscha / inglizcha / koddagi nom | Doim yonida |
| 30 | `30-izchillik-matritsasi.md` | US → BP → ekran → API → jadval → ruxsat → bosqich; teskari indekslar va bo'shliqlar | Har vazifa oldidan |
| 31 | `31-qabul-testlari.md` | Qabul ssenariylari (Berilgan/Qachonki/Unda) → pytest/Playwright | Har vazifa oxirida |
| 32 | `32-kod-qoidalari.md` | Repo tuzilmasi, nomlash, test, git oqimi, Definition of Done | Kod yozishdan oldin |
| | **1C integratsiyasi (MVP'dan keyin, Bosqich 7)** | | |
| 33 | `33-1c-integratsiya.md` | ERP → 1C kunlik eksport: server moduli `onec_integration`, `onec_*` jadvallar, agent↔server protokoli, veb API W-01…W-55, ruxsatlar, `ONEC_*` xato kodlari, BO-22/BO-23, M19 | Bosqich 7 oldidan |
| 34 | `34-1c-agent.md` | Do'kon agenti (C#/.NET Fx 4.8, tray + worker'lar, DPAPI, 1C yozish algoritmi, avto-yangilanish; fiskal ko'prik/printer/tarozi — §14 «Do'kon agenti kengaytmasi») — repo `agent-1c/` | Bosqich 5 (agent infratuzilmasi, qaror #66) va 7 (1C) |

## Bosqich bo'yicha minimal o'qish to'plami

| Bosqich | O'qiladigan fayllar |
|---|---|
| Skelet + auth (Bosqich 0–1) | 01, 32, 10, 23, 24, 12 (§1–5), 14, 15 (maskalash, rozilik, sirlar — #61, #65), 17, 26, 27, 31 (§1) |
| Katalog va ombor | 03 (M04–M07, M09), 04, 11, 12, 13, 19, 07 (BO-02…05, BO-18) |
| Kassa (veb, Bosqich 3) | 01 #43/#62/#64, 03 (M01–M03, M08, M16), 04, 13, 16, 18, 07 (POS-01…16), 08, 24 §6 (printer matritsasi) |
| Moliya, hisobot, obuna (Bosqich 4, 6) | 03 (M10–M12, M15, M17, M18), 13 (§2.18a `bank_settlements`, §2.26 `tax_settlements`), 20 (bank ko'chirmasi importi, tranzit qoldiq), 07 (BO-06…21, BO-24) |
| Fiskal va integratsiyalar (Bosqich 5) | 01 #60/#62/#63/#66–#68, 10 §2, 21, 33 §5.15/§9 (agent registri va A-API), 34 §14, 16, 18–20 tegishli bo'limlar, 26 Jadval B |
| AI | 09, 22, 20 (AI bo'limi) |
| 1C integratsiyasi (Bosqich 7) | 01 #36–#42, #60, 33, 34, 12 §2.11, 15, 17, 07 BO-22/23, 26 #93–#105, #131–#137 |

## Kod tashqarisidagi hujjatlar

- `spec/tarix/` — tekshiruvlar, qabul agentlari qarorlari, kamchiliklar tahlili, tuzatishlar jurnali, rasmiy xatlar (`tarix/tekshiruv/rasmiy-xatlar.md`).
- `research_notes/` — bozor va texnik tadqiqot (manbalar).
- `research_notes/ochiq-savollar/` — ochiq savollarni yopish tadqiqoti: `00-inventar.md` (OQ-001…OQ-102), P1–P7 desk-research (lex.uz, vendor hujjatlari), `D-qarorlar-va-E-standartlar.md` (qarorlar #43–#59, E-bandlar interim standartlari, xat matnlari), `01-qollash-yoriqnomasi.md` (#60–#65 va ustun qoidalar). Natijasi — `01` va `26`; kod yozishda shu ikki fayl yetarli.
- `research_notes/mustaqil-tekshiruv/` — spec'ning mustaqil tekshiruvi va tuzatish rejasi (qarorlar #66–#70 manbasi).

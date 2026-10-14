# Backlog va birinchi sprintlar

*2026-10-14 · Asos: `spec/01-mahsulot/06-mvp-chegarasi.md` (Must/Should), `00-umumiy-arxitektura.md`, `03-integratsiyalar.md` (qurish tartibi va to'siqlar), foydalanuvchi qarori: avval veb, Android keyin.*

## Asosiy xulosalar

1. **Tartib: avval do'konning kundalik ishi, keyin davlat integratsiyalari.** Kassa + ombor + qarz daftari + xarajat + hisobot davlat API'larisiz ham to'liq ishlaydi va pilotda qiymat beradi; OFD, e-faktura va boshqalar parallel ravishda (rasmiy javoblar kelguncha) quriladi.
2. **6 ta ikki haftalik sprint + 0-bosqich ≈ 13–14 hafta MVP** — bu **taxmin** (jamoa: 2 backend, 2 frontend, 1 QA/PM faraz qilindi; jamoa tarkibi hali aniqlanmagan).
3. Kod yozish bilan **bir vaqtda** tashqi ishlar boshlanadi: rasmiy xatlar, buxgalter bilan provodka tasdig'i, SMS provayder tanlash, 15–20 do'kon egasi bilan suhbat va 5–10 pilot do'kon.
4. Fiskal yo'l (o'z virtual kassamiz reyestrga kiritilishi ≈ 50 ish kuni vs mavjud hamkor orqali) **0-bosqichda hal qilinishi kerak** — 5-sprint shunga bog'liq.
5. Android POS (Kotlin) — MVP'dan keyin, `10-android-pos.md` bosqichlari bilan.

---

## 0-bosqich (1–2 hafta): poydevor va tashqi ishlar

| Ish | Natija |
|---|---|
| Backend skeleti (`09-backend-arxitekturasi.md`): FastAPI, `app/core` (tenant konteksti, RLS, auth, xatolar, idempotentlik), Alembic, arq worker, docker compose, CI | `GET /health`, RLS izolyatsiya testi yashil |
| Veb skeleti (`08-frontend-arxitekturasi.md`): Turborepo, `apps/shell`, `@shared/api` (orval), `@shared/ui` (shadcn), `@shared/state`, i18n uz/ru, PWA | Login sahifasi va layout, generatsiya qilingan API klient |
| Seed: rollar, ruxsatlar, o'lchov birliklari, xarajat toifalari, tariflar | `05-xavfsizlik-va-audit.md` matritsasi bazada |
| **Tashqi:** rasmiy xatlarni yuborish (`research_notes/texnik/12-taxminlar-va-murojaatlar.md` + Didox, Faktura.uz, Click, Payme, Uzum uchun yangi xatlar) | Yuborilgan xatlar ro'yxati |
| **Tashqi:** buxgalter bilan `02-provodka-qoidalari.md` ni tekshirish | Tasdiqlangan hisoblar rejasi |
| **Tashqi:** fiskal yo'l qarori (o'z reyestr yo'li va/yoki hamkor), SMS provayder tanlash | Qaror hujjati |
| **Tashqi:** 15–20 do'kon egasi bilan suhbat, 5–10 pilot do'kon | Suhbat xulosasi, pilot ro'yxati |

## 1-sprint: ro'yxatdan o'tish va katalog

- M17: telefon + SMS kod bilan ro'yxatdan o'tish, 30 kunlik sinov, do'kon sozlamalari (BO-21, BO-14).
- M13/M14: xodim qo'shish, standart rollar, bitta filial va ombor avtomatik.
- M09: tovarlar, shtrix-kodlar, MXIK kodi, narx va narx tarixi; US-M04-04 Excel import.
- **Tayyor bo'lish mezoni:** yangi do'kon 10 daqiqada ro'yxatdan o'tib, 500 ta tovarni Excel'dan yuklay oladi.

## 2-sprint: ombor va hujjat o'tkazish yadrosi

- Posting xizmati (`09-…`, 2-bo'lim): hujjat → `stock_moves`, `stock_lots`, `ledger_entries`, `vat_moves` bitta tranzaksiyada; teskari hujjat.
- M07 kirim (naqd va nasiyaga), yetkazib beruvchilar; M04 qoldiq, FIFO/AVECO (US-M04-05), qayta hisoblash ishi.
- M06 ko'chirish, M05 inventarizatsiya (Must — US-M05-01…03; posting sinovi uchun ham foydali).
- **Mezon:** `02-provodka-qoidalari.md` dagi raqamli misollar avtomatik testlarda o'tadi.

## 3-sprint: veb-kassa

- M01 kassa (onlayn): qidiruv/skaner, chek, to'lov (naqd, karta, aralash), smena va Z-hisobot; chek chop etish (brauzer/printer — ochiq savol yechimi).
- M16 kassa pul harakati, smena oxirida naqdni sanash; M02 qaytarish; M03 chegirma (limit + PIN tasdiq).
- Offline: Dexie keshi, outbox, `/sync/push`/`/sync/pull` (`04-offline-sync.md`).
- **Mezon:** internet o'chirilganda 2 soat savdo, keyin barcha cheklar yo'qotishsiz va takrorsiz sinxronlanadi.

## 4-sprint: qarz daftari, xarajatlar, hisobotlar, Telegram

- M08 qarz daftari: tez qarz yozish (offline), mijoz daftari, boshlang'ich qarzlar, to'lov (eng eski qarzdan), va'da sanasi, qarzlar hisoboti, yetkazib beruvchiga qarz va unga to'lov (US-M08-11, US-M07-04 — `supplier_payments`, bank/naqd).
- M15 xarajatlar (+ takrorlanuvchi), sof foyda.
- M12 Egasi dashboard va asosiy hisobotlar; M18 Telegram bot: ulash va kunlik hisobot.
- **Mezon:** pilot do'kon qog'oz daftarsiz bir hafta ishlaydi.

## 5-sprint: fiskal va e-faktura

- OFD/virtual kassa (0-bosqich qaroriga ko'ra: o'z modulimiz yoki hamkor adapteri), 48 soat nazorati, fiskal chek holatlari.
- E-faktura (Faktura.uz va/yoki Didox) + E-IMZO brauzerda imzolash; kiruvchi faktura → kirim; VM 830 xavf belgisi.
- M10 ichki QQS registri, qizil faktura bo'yicha QQS krediti faqat to'lovdan keyin (US-M07-04 ikkinchi mezoni, US-M10-03); M11 buxgalteriya hisobotlari (tasdiqlangan hisoblar rejasi bilan).
- **Mezon:** test muhitida chek fiskallashadi; kiruvchi e-faktura qabul qilinib imzolanadi.

## 6-sprint: to'lov, AI, pilot

- M17 obuna to'lovi (Payme/Click), tarif limitlari, kechikkan to'lov siyosati (huquqiy tasdiqdan keyin).
- M17 ichki admin panel (ADM-01, US-M17-04): tenantlar, obuna holati, to'lov tarixi, AI sarfi, faol kassalar; pilot do'konlar uchun muddatni qo'lda uzaytirish; `platform_admins` alohida autentifikatsiya, har kirish audit'da (`05-xavfsizlik-va-audit.md` §3.4).
- AI-01 (savol-javob, whitelisted tool'lar) va AI-06 (qarz eslatma matni) — `07-ai-qatlami.md`; AI limiti va xarajat hisobi.
- M10 davlat hisobotini solishtirish (fayl yuklash) + AI-05 tushuntirish + 5 kalendar kunlik taymer.
- M09 yorliq chop etish; M18 ogohlantirishlar.
- **Pilot:** 5–10 do'kon, xarajat va AI sarfini o'lchash (unit-iqtisod).

## MVP'dan keyin (tartib taxminiy)

1. Asl belgisi (CRPT Turon) — API ochilgach; e-TTN; e-ishonchnoma (Vakolat.uz).
2. AI-03 (qog'oz hujjat OCR), mijozlarga SMS/Telegram qarz xabarlari (US-M08-08).
3. Android POS (Kotlin) — `10-android-pos.md` 1–4 bosqichlari.
4. Uzum to'lovi, ko'p ombor, filiallar konsolidatsiyasi, talab bashorati (AI-09) — 2–3 oylik savdo tarixidan keyin.
5. O'z AI modelimiz (markaziy GPU server) — yig'ilgan ma'lumot va eval natijalariga qarab.

## Har bir vazifa uchun "tayyor" ta'rifi

- Spec'dagi US qabul mezonlari avtomatik test bilan qoplangan; posting o'zgarsa raqamli testlar yangilangan.
- RLS izolyatsiya testi va OpenAPI → orval generatsiyasi CI'da yashil.
- uz va ru tarjimalari bor; offline ta'siri (`04-offline-sync.md`) ko'rib chiqilgan.
- Audit jurnaliga tegishli amallar yoziladi; yangi ruxsat kodi matritsaga qo'shilgan.

## Ochiq savollar

1. Jamoa tarkibi va muddat — sprint hajmlari shunga qarab qayta baholanadi.
2. Fiskal yo'l (o'z reyestr yo'li vs hamkor) — 5-sprint shunga bog'liq.
3. Rasmiy xatlarga javob muddati noma'lum — integratsiya sprintlari surilishi mumkin.
4. Kechikkan obuna to'lovida kassani to'xtatmaslik siyosatining huquqiy tasdig'i.

## Manbalar

- `spec/01-mahsulot/06-mvp-chegarasi.md`, `07-tuzatishlar-va-yechimlar.md`, `spec/08-kamchiliklar-tahlili.md`.
- `spec/02-arxitektura/00…10`.
- `research_notes/texnik/12-taxminlar-va-murojaatlar.md` (rasmiy xatlar loyihasi).

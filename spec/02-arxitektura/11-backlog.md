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
| Backend skeleti (`09-backend-arxitekturasi.md`): FastAPI, `app/core` (tenant konteksti, RLS, xatolar, idempotentlik), Alembic, SAQ worker, docker compose, CI | `GET /health`, RLS izolyatsiya testi yashil |
| **To'liq OAuth 2.0 AS+RS** (`12-autentifikatsiya-oauth2.md`, foydalanuvchi qarori 2026-10-15): `app/modules/auth/` — Authlib integratsiyasi, `/oauth/*`, `/auth/*` endpoint'lari, imzolash kaliti/JWKS, token/sessiya/litsenziya jadvallari — **0-bosqichda poydevor sifatida**, 1-sprintda to'liq ishlaydigan holatga keltiriladi | `/oauth/authorize`→`/oauth/token` to'liq Authorization Code+PKCE oqimi real Postgres/Redis'da ishlaydi (mock yo'q) |
| Veb skeleti (`08-frontend-arxitekturasi.md`): Turborepo, `apps/shell`, `@shared/api` (orval), `@shared/ui` (shadcn), `@shared/state`, i18n uz/ru, PWA | Login sahifasi va layout, generatsiya qilingan API klient |
| Seed: rollar, ruxsatlar, o'lchov birliklari, xarajat toifalari, tariflar | `05-xavfsizlik-va-audit.md` matritsasi bazada |
| **Tashqi:** rasmiy xatlarni yuborish (`research_notes/texnik/12-taxminlar-va-murojaatlar.md` + Didox, Faktura.uz, Click, Payme, Uzum uchun yangi xatlar) | Yuborilgan xatlar ro'yxati |
| **Tashqi:** buxgalter bilan `02-provodka-qoidalari.md` ni tekshirish | Tasdiqlangan hisoblar rejasi + `02-provodka-qoidalari.md` ogohlantirish blokidagi 12 band bo'yicha yozma javoblar jadvali *(2026-10-14: tekshiruv)* |
| **Tashqi:** fiskal yo'l qarori (o'z reyestr yo'li va/yoki hamkor), SMS provayder tanlash | Qaror hujjati |
| **Tashqi:** 15–20 do'kon egasi bilan suhbat, 5–10 pilot do'kon | Suhbat xulosasi, pilot ro'yxati |
| **Tashqi:** huquqiy maslahat — ~~(a) obuna kechikkanda kassani to'xtatmaslik~~ **bekor qilindi: endi mahsulot qarori sifatida kassa to'liq to'xtaydi, 24 soat imtiyozdan keyin (`12-autentifikatsiya-oauth2.md` §16) — bu qator uchun huquqiy maslahat shart emas, fiskal oqibat Foydalanish shartlarida qayd etiladi**; (b) 48 soatdan keyin yangi sotuvni bloklamaslik (`04-offline-sync.md` §6); (c) markirovkalangan tovarni offline sotish (§7) — **mahsulot qarori qabul qilingan (2026-10-15), huquqiy maslahat endi faqat tasdiq uchun**; (d) chekdan keyin e-faktura berish — **mahsulot qarori qabul qilingan (2026-10-15), huquqiy maslahat endi faqat tasdiq uchun** | Yozma huquqiy xulosa (5-sprintdan oldin) *(2026-10-15: foydalanuvchi qarori — (a) bandi bekor qilindi; (c)/(d) qabul-5 KICHIK 2 bo'yicha aniqlashtirildi)* |

## 1-sprint: ro'yxatdan o'tish va katalog

- M17: telefon + SMS kod bilan ro'yxatdan o'tish (OAuth login/signup oqimi, `12-autentifikatsiya-oauth2.md` §4), 30 kunlik sinov, do'kon sozlamalari (BO-21, BO-14); filial sozlamasida `branches.settlement_category` (`city_100k_plus`/`other`/`remote_mountain`, aylanma solig'i stavkasi uchun, SK 467-modda). *(2026-10-14: tekshiruv)*
- M13/M14: xodim qo'shish, standart rollar, bitta filial va ombor avtomatik; US-M14-03 yangi filial qo'shish. **Admin foydalanuvchilar paneli (BO-11, foydalanuvchi qarori 2026-10-15)**: xodim bloklash, rol/filial tayinlash, **PIN'ni qayta o'rnatish** (US-M13-04, SMS orqali bir martalik taklif/tiklash kodi), **sessiya/qurilmalarni bekor qilish** (US-M13-06, `12-autentifikatsiya-oauth2.md` §18.2) — shu sprintda to'liq. *(2026-10-15: foydalanuvchi qarori — US-M13-04/06 hikoya ID'lari aniqlashtirildi, qabul-5 KICHIK 3)*
- M09: tovarlar, shtrix-kodlar, MXIK kodi, narx va narx tarixi; US-M04-04 import `import_jobs` orqali (yuklash → tekshirish/xatolar ro'yxati → tasdiqlash) va boshlang'ich qoldiq (`stock_openings`). *(2026-10-14: tekshiruv)*
- SMS adapter (OTP, `03-integratsiyalar.md` §10) — 0-bosqichda tanlangan provayder bilan. **Aniqlashtirish** *(2026-10-15: qabul-5 KICHIK 4, foydalanuvchi tasdig'i so'ralsin — "mock yo'q" talabiga mos)*: `FakeSms` **faqat lokal dev**'da, aniq flag bilan yoqiladi; staging va prod — har doim haqiqiy SMS provayder; auth testlari OTP oqimini test-raqam yo'li orqali **haqiqiy** (mock'siz) oqimda tekshiradi.
- **Tayyor bo'lish mezoni:** yangi do'kon 10 daqiqada ro'yxatdan o'tib, 500 ta tovarni Excel'dan yuklay oladi.

## 2-sprint: ombor va hujjat o'tkazish yadrosi

- Posting xizmati (`09-…`, 2-bo'lim): hujjat → `stock_moves`, `stock_lots`, `ledger_entries`, `vat_moves` bitta tranzaksiyada; teskari hujjat.
- M07 kirim (naqd va nasiyaga), yetkazib beruvchilar; M04 qoldiq, FIFO/AVECO (US-M04-05), qayta hisoblash ishi.
- M06 ko'chirish, M05 inventarizatsiya (Must — US-M05-01…03; posting sinovi uchun ham foydali).
- US-M07-05 yetkazib beruvchiga qaytarish; US-M04-06 hisobdan chiqarish + yaroqlilik muddati maydoni; BO-03 'Ko'chirishlar' tabi (US-M06-03). *(2026-10-14: tekshiruv)*
- **Mezon:** `02-provodka-qoidalari.md` dagi raqamli misollar avtomatik testlarda o'tadi.

## 3-sprint: veb-kassa

- M01 kassa (onlayn): qidiruv/skaner, chek, to'lov (naqd, karta, aralash, **UzQR** — yuridik shaxslar uchun 2026-07-01'dan majburiy, PF-246 3-b; Click/Payme ixtiyoriy), smena va Z-hisobot; chek chop etish — platformaga qarab ikki yo'l (`08-frontend-arxitekturasi.md` §6, `06-nofunksional-talablar.md` §7, *2026-10-15: foydalanuvchi qarori, D3*): Chrome/Edge/Android — WebUSB/Web Serial/Web Bluetooth + tarmoq/bulut printer; iPhone/iPad (o'rnatilgan PWA) — **faqat** bulut printer adapteri (Star CloudPRNT / Epson Server Direct Print klassi) yoki elektron chek (QR/Telegram). *(2026-10-14: tekshiruv — UzQR qo'shildi)*
- **Bulut printer adapteri** (`shared/lib/printer/cloud`) — Star CloudPRNT/Epson Server Direct Print klassi uchun umumiy interfeys (iOS yo'li uchun majburiy, Chromium'da ixtiyoriy zahira); **iOS o'rnatish ko'rsatmasi** (Safari → "Bosh ekranga qo'shish") POS-01/onboarding ekraniga qo'shiladi. Bulut printer narxi/mavjudligi O'zbekistonda va faqat-elektron chekning qonuniyligi — ochiq savol (`06-nofunksional-talablar.md` §7.2). *(2026-10-15: foydalanuvchi qarori, D3)*
- M16 kassa pul harakati, smena oxirida naqdni sanash; M02 qaytarish; M03 chegirma (limit + PIN tasdiq).
- Offline: Dexie keshi, outbox, `/sync/push`/`/sync/pull` (`04-offline-sync.md`).
- BO-16 (M02/M03/M08/M16 turlari); BO-11 qurilmalar va bekor qilish; `sale.draft_voided`, qayta chop etish auditi. *(2026-10-14: tekshiruv)*
- **Mezon:** internet o'chirilganda 2 soat savdo, keyin barcha cheklar yo'qotishsiz va takrorsiz sinxronlanadi.

## 4-sprint: qarz daftari, xarajatlar, hisobotlar, Telegram

- M08 qarz daftari: tez qarz yozish (offline), mijoz daftari, boshlang'ich qarzlar, to'lov (eng eski qarzdan), va'da sanasi, qarzlar hisoboti, yetkazib beruvchiga qarz va unga to'lov (US-M08-11, US-M07-04 — `supplier_payments`, bank/naqd).
- M15 xarajatlar (+ takrorlanuvchi), sof foyda.
- M12 Egasi dashboard va asosiy hisobotlar; M18 Telegram bot: ulash va kunlik hisobot.
- Filiallar bo'yicha va jami ko'rinish (US-M14-01, US-M04-03); kam qoldiq ogohlantirishi (US-M04-02). *(2026-10-14: tekshiruv)*
- **Mezon:** pilot do'kon qog'oz daftarsiz bir hafta ishlaydi.

## 5-sprint: fiskal va e-faktura

- OFD/virtual kassa (0-bosqich qaroriga ko'ra: o'z modulimiz yoki hamkor adapteri), 48 soat nazorati, fiskal chek holatlari.
- E-faktura (Faktura.uz va/yoki Didox) + E-IMZO brauzerda imzolash; kiruvchi faktura → kirim; VM 830 xavf belgisi.
- M10 ichki QQS registri, qizil faktura bo'yicha QQS krediti faqat to'lovdan keyin (US-M07-04 ikkinchi mezoni, US-M10-03); M11 buxgalteriya hisobotlari (tasdiqlangan hisoblar rejasi bilan).
- US-M10-03 kutilayotgan QQS krediti (BO-07/BO-10). *(2026-10-14: tekshiruv)*
- Chek asosida chiquvchi e-faktura (US-M01-06, BP-13, BO-15 "Chek asosida e-faktura chiqarish" tugmasi) — `einvoices.related_doc`, provodka yozilmaydi (`02-provodka-qoidalari.md` 2.22). *(2026-10-15: qabul-5 KICHIK 2)*
- **Mezon:** test muhitida chek fiskallashadi; kiruvchi e-faktura qabul qilinib imzolanadi.

## 6-sprint: to'lov, AI, pilot

- M17 obuna to'lovi (Payme/Click), tarif limitlari; **24 soatlik imtiyoz tugagach qattiq to'xtatish** (foydalanuvchi qarori 2026-10-15, `12-autentifikatsiya-oauth2.md` §16–17): billing webhook bilan birga — tenant bo'yicha sessiya/token ommaviy bekor qilish, Redis `sub_status` keshi, offline litsenziya tokeni (`valid_until`) chiqarish/yangilash, login sahifasidagi "Obuna muddati tugagan" + to'lov havolasi holati. Ikki tor istisno: **D1** — lokautdan oldingi cheklar cheklangan `sync.drain` orqali OFD'ga baribir yuboriladi (`04-offline-sync.md` §3.5, `03-integratsiyalar.md` §1/§9); **D2** — lokaut davrida eksport faqat to'lov sahifasidan, SMS OTP bilan. *(2026-10-15: foydalanuvchi qarori — avvalgi "huquqiy tasdiqdan keyin kassa davom etadi" rejasi bekor qilindi)*
- M17 ichki admin panel (ADM-01, US-M17-04, **US-M13-08** — platforma admini Egasi hisobini bloklash/parol tiklash/sessiyalarini boshqarishi): tenantlar, obuna holati, to'lov tarixi, AI sarfi, faol kassalar; pilot do'konlar uchun muddatni qo'lda uzaytirish; `platform_admins` alohida autentifikatsiya, har kirish audit'da (`05-xavfsizlik-va-audit.md` §3.4). *(2026-10-15: qabul-5 KICHIK 3 — US-M13-08 hikoya ID'si qo'shildi)*
- AI-01 (savol-javob, whitelisted tool'lar) va AI-06 (qarz eslatma matni) — `07-ai-qatlami.md`; AI limiti va xarajat hisobi.
- **AI-03** (qog'oz hujjat OCR, pilot bilan, tor qamrov) — BO-04 kirim avto-to'ldirish, US-M04-04 (3)-yo'l, M02 qog'oz chek; `07-ai-qatlami.md` §10 OCR quvuri, majburiy inson tasdig'i va ishonch chegarasi. *(2026-10-15: foydalanuvchi qarori — AI-03 MVP'ga qaytarildi, 6-sprintda)*
- M10 davlat hisobotini solishtirish (fayl yuklash) + AI-05 tushuntirish + 5 kalendar kunlik taymer.
- M09 yorliq chop etish; M18 ogohlantirishlar.
- US-M09-02 narx tasdiqlash (BO-16); yaroqlilik muddati ogohlantirishi (M18). *(2026-10-14: tekshiruv)*
- **Pilot:** 5–10 do'kon, xarajat va AI sarfini o'lchash (unit-iqtisod).

## MVP'dan keyin (tartib taxminiy)

1. Asl belgisi (CRPT Turon) **integratsiyasining o'zi** (rasmiy API/integrator maqomi ochilgach) — e-TTN; e-ishonchnoma (Vakolat.uz). **OCHIQ SAVOL (CRPT-MVP ziddiyati, foydalanuvchi qarori kerak, 2026-10-15)**: markirovkalangan tovar **sotuvi** (US-M01-03, offline — narx ma'lum bo'lsa ruxsat) MVP talabi bo'lib qoladi, ammo CRPT Turon bilan rasmiy integratsiya (bu band) hamon "MVP'dan keyin" — chunki `help.crpt-turon.uz` 403 bilan yopiq (`03-integratsiyalar.md` §4, Ochiq savol 1). **Taklif (hal qilinmagan, faqat variant)**: (a) MVP'da kodlar faqat mahalliy yoziladi (`marking_codes.status='pending_verification'`) va CRPT API'ga kirish ochilgan zahoti fon rejimida avtomatik yuboriladi — agar bu kirish MVP davrida ochilmasa, (b) markirovkalangan tovar sotuvi vaqtincha cheklanadi (faqat markirovkasiz/markirovka talab qilinmaydigan tovarlar). Bu band — spec darajasida **qaror qilinmagan**, foydalanuvchidan kutilmoqda.
2. ~~AI-03 (US-M04-04 (3)-yo'l) — qog'oz hujjat OCR~~ — **bekor qilindi**: AI-03 MVP'da, 6-sprintda (foydalanuvchi qarori, 2026-10-15). Mijozlarga SMS/Telegram qarz xabarlari (US-M08-08) — MVP'dan keyin, o'zgarishsiz.
3. Android POS (Kotlin) — `10-android-pos.md` 1–4 bosqichlari.
4. Uzum to'lovi, ko'p ombor, talab bashorati (AI-09) — 2–3 oylik savdo tarixidan keyin. *(2026-10-14: tekshiruv — "filiallar konsolidatsiyasi" olib tashlandi, 4-sprintga ko'chirildi)*
5. O'z AI modelimiz (markaziy GPU server) — yig'ilgan ma'lumot va eval natijalariga qarab.
6. US-M03-02 avtomatik chegirma qoidalari; US-M14-02 nusxalash; US-M17-05 to'liq eksport (birinchi pullik mijoz chiqib ketishidan oldin); ochiq smena ichida kassir topshirish; bitta egasining bir nechta tenanti uchun umumiy ko'rinish; AI Batch (`submit_batch`). *(2026-10-14: tekshiruv)*

## Har bir vazifa uchun "tayyor" ta'rifi

- Spec'dagi US qabul mezonlari avtomatik test bilan qoplangan; posting o'zgarsa raqamli testlar yangilangan.
- RLS izolyatsiya testi va OpenAPI → orval generatsiyasi CI'da yashil.
- uz va ru tarjimalari bor; offline ta'siri (`04-offline-sync.md`) ko'rib chiqilgan.
- Audit jurnaliga tegishli amallar yoziladi; yangi ruxsat kodi matritsaga qo'shilgan.

## Ochiq savollar

1. Jamoa tarkibi va muddat — sprint hajmlari shunga qarab qayta baholanadi.
2. Fiskal yo'l (o'z reyestr yo'li vs hamkor) — 5-sprint shunga bog'liq.
3. Rasmiy xatlarga javob muddati noma'lum — integratsiya sprintlari surilishi mumkin.
4. ~~Kechikkan obuna to'lovida kassani to'xtatmaslik siyosatining huquqiy tasdig'i~~ **Yopildi**: foydalanuvchi qarori bilan — kassa 24 soatlik imtiyozdan keyin to'liq to'xtaydi, huquqiy tasdiq endi shart emas (`12-autentifikatsiya-oauth2.md` §16.3). *(2026-10-15: foydalanuvchi qarori)*
5. **CRPT Turon — MVP ziddiyati (yangi, 2026-10-15, foydalanuvchi qarori kerak)**: markirovkalangan tovar sotuvi MVP talabi (US-M01-03, offline — narx ma'lum bo'lsa ruxsat, `04-offline-sync.md` §7), ammo CRPT Turon bilan rasmiy integratsiyaning o'zi "MVP'dan keyin" ro'yxatida (yuqorida, 1-band) — API hamon yopiq (403). Taklif: (a) MVP kodlarni mahalliy saqlasin va CRPT API'ga kirish ochilganda yuborsin; (b) kirish ochilmasa — markirovkalangan tovar sotuvi vaqtincha cheklansin. **Bu spec darajasida qaror qilinmagan — foydalanuvchidan kutilmoqda.**

## Manbalar

- `spec/02-arxitektura/12-autentifikatsiya-oauth2.md` — OAuth 2.0 AS+RS, admin panel, obuna lokauti. *(2026-10-15: foydalanuvchi qarori)*
- `spec/01-mahsulot/06-mvp-chegarasi.md`, `07-tuzatishlar-va-yechimlar.md`, `spec/08-kamchiliklar-tahlili.md`.
- `spec/02-arxitektura/00…10`.
- `research_notes/texnik/12-taxminlar-va-murojaatlar.md` (rasmiy xatlar loyihasi).

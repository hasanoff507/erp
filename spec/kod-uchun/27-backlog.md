# Backlog — ketma-ket bosqichlar (2 kishilik jamoa)

*2026-10-14 · Asos: `spec/kod-uchun/05-mvp-chegarasi.md` (Must/Should), `10-umumiy-arxitektura.md`, `21-integratsiyalar.md` (qurish tartibi va to'siqlar), foydalanuvchi qarori: avval veb, Android keyin. **2026-10-15: asoschi qarori, Q8 — jamoa va reja modeli qayta yozildi** (quyida).*

## Asosiy xulosalar

1. **Tartib: avval do'konning kundalik ishi, keyin davlat integratsiyalari.** Kassa + ombor + qarz daftari + xarajat + hisobot davlat API'larisiz ham to'liq ishlaydi va pilotda qiymat beradi; OFD, e-faktura va boshqalar parallel ravishda (rasmiy javoblar kelguncha) quriladi.
2. **Jamoa — 2 kishi: asoschi + Claude (asoschi qarori, Q8, 2026-10-15)**: eski "2 backend + 2 frontend + 1 QA/PM" taxmini **bekor qilindi**, shu bilan birga eski "6 sprint × 2 hafta ≈ 13–14 hafta" muddat hisob-kitobi ham **olib tashlandi** — qat'iy kalendar muddat yo'q. Ish **ketma-ket vertikal bo'laklarda** (backend+veb birga, bir bosqich — bir tugallangan foydalanuvchi oqimi) olib boriladi, eski "sprint" (ikki haftalik quti) tushunchasi **"bosqich"** (tugash mezoni bilan, muddatsiz) bilan almashtirildi; har bosqich tugagandan keyin keyingisi boshlanadi (parallel ish oqimi yo'q — ikki kishilik jamoa bitta narsaga bir vaqtda e'tibor beradi). Har bosqichning tayyor bo'lish mezoni (**Definition of Done**) — quyidagi "Mezon"/"Tayyor bo'lish mezoni" qatorlari.
3. Kod yozish bilan **bir vaqtda** tashqi ishlar boshlanadi: rasmiy xatlar, buxgalter bilan provodka tasdig'i, SMS provayder tanlash, 15–20 do'kon egasi bilan suhbat va 5–10 pilot do'kon — bu tashqi ishlarni ko'pincha asoschi shaxsan yuritadi, Claude kod bosqichlarida band bo'lgan vaqtda ham.
4. Fiskal yo'l *(2026-10-15: foydalanuvchi qarori — hal qilindi)*: ikkisi **parallel** — o'z reyestr arizasi 0-bosqichda boshlanadi (≈50 ish kuni), 5-bosqichda pilot reyestr hamkori adapteri (`FiscalAdapter` porti) ishga tushadi, keyin o'z modulimizga almashtiriladi.
5. Android POS (Kotlin) — MVP'dan keyin, `28-android-pos.md` bosqichlari bilan.

---

## 0-bosqich: poydevor va tashqi ishlar

| Ish | Natija |
|---|---|
| Backend skeleti (`23-backend-arxitekturasi.md`): FastAPI, `app/core` (tenant konteksti, RLS, xatolar, idempotentlik), Alembic, SAQ worker, docker compose, CI | `GET /health`, RLS izolyatsiya testi yashil |
| **To'liq OAuth 2.0 AS+RS** (`14-autentifikatsiya-oauth2.md`, foydalanuvchi qarori 2026-10-15): `app/modules/auth/` — Authlib integratsiyasi, `/oauth/*`, `/auth/*` endpoint'lari, imzolash kaliti/JWKS, token/sessiya/litsenziya jadvallari — **0-bosqichda poydevor sifatida**, 1-bosqichda to'liq ishlaydigan holatga keltiriladi | `/oauth/authorize`→`/oauth/token` to'liq Authorization Code+PKCE oqimi real Postgres/Redis'da ishlaydi (mock yo'q) |
| Veb skeleti (`24-frontend-arxitekturasi.md`): Turborepo, `apps/shell`, `@shared/api` (orval), `@shared/ui` (shadcn), `@shared/state`, i18n uz/ru, PWA | Login sahifasi va layout, generatsiya qilingan API klient |
| Seed: rollar, ruxsatlar, o'lchov birliklari, xarajat toifalari, tariflar | `15-xavfsizlik-va-audit.md` matritsasi bazada |
| **Tashqi:** rasmiy xatlarni yuborish (`research_notes/texnik/12-taxminlar-va-murojaatlar.md` + Didox, Faktura.uz, Click, Payme, Uzum uchun yangi xatlar) | Yuborilgan xatlar ro'yxati |
| **Tashqi:** buxgalter bilan `13-provodka-qoidalari.md` ni tekshirish | Tasdiqlangan hisoblar rejasi + `13-provodka-qoidalari.md` ogohlantirish blokidagi 12 band bo'yicha yozma javoblar jadvali *(2026-10-14: tekshiruv)* |
| **Tashqi:** o'z virtual kassamizni **Davlat reyestriga kiritish arizasi — 0-bosqichda, birinchi kundan boshlanadi** (VMQ-943, 4-ilova, ~50 ish kuni ≈ 2,5–3 oy); parallel — pilot uchun reyestr hamkori (Multikassa/E-POS Communicator) bilan muzokara, SMS provayder tanlash *(2026-10-15: foydalanuvchi qarori — `tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md` (b)/#2)* | Yuborilgan ariza + hamkor bilan muzokara holati |
| **Tashqi:** pentest — avtomatik DAST (OWASP ZAP) sozlash va ichki OAuth/to'lov/fiskal tekshiruv ro'yxatini tayyorlash; Celion/ONESEC'dan rasmiy taklif so'rash (~60 mln so'm rezerv, `15-xavfsizlik-va-audit.md` §8) *(2026-10-15: foydalanuvchi qarori — `tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md` #14)* | DAST CI'ga ulangan, ikki pentest firmadan taklif so'rovi yuborilgan |
| **Tashqi:** qo'llab-quvvatlash kanali sozlash — Telegram "/yordam" + bitta telefon raqami, ish vaqti va dam olish kuni navbatchilik jadvali (`25-nofunksional-talablar.md` §12) *(2026-10-15: foydalanuvchi qarori — `tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md` #12)* | Support kanal ishga tushgan |
| **Tashqi:** 15–20 do'kon egasi bilan suhbat, 5–10 pilot do'kon | Suhbat xulosasi, pilot ro'yxati |
| **Tashqi:** huquqiy maslahat — ~~(a) obuna kechikkanda kassani to'xtatmaslik~~ **bekor qilindi: endi mahsulot qarori sifatida kassa to'liq to'xtaydi, 24 soat imtiyozdan keyin (`14-autentifikatsiya-oauth2.md` §16) — bu qator uchun huquqiy maslahat shart emas, fiskal oqibat Foydalanish shartlarida qayd etiladi**; (b) 48 soatdan keyin yangi sotuvni bloklamaslik (`16-offline-sync.md` §6); (c) markirovkalangan tovarni offline sotish (§7) — **mahsulot qarori qabul qilingan (2026-10-15), huquqiy maslahat endi faqat tasdiq uchun**; (d) chekdan keyin e-faktura berish — **mahsulot qarori qabul qilingan (2026-10-15), huquqiy maslahat endi faqat tasdiq uchun** | Yozma huquqiy xulosa (5-bosqichdan oldin) *(2026-10-15: foydalanuvchi qarori — (a) bandi bekor qilindi; (c)/(d) qabul-5 KICHIK 2 bo'yicha aniqlashtirildi)* |

## 1-bosqich: ro'yxatdan o'tish va katalog

- M17: telefon + OTP (Telegram bot birinchi, SMS zaxira — asoschi qarori Q7, `14-autentifikatsiya-oauth2.md` §4.2) bilan ro'yxatdan o'tish — **`POST /auth/signup`** (A-01, `14-autentifikatsiya-oauth2.md` §4/§20; bitta tranzaksiyada tenant+obuna(trial 30 kun)+Egasi+5 rol+standart filial/ombor/kassa provisioning), do'kon sozlamalari (BO-21, BO-14); filial sozlamasida `branches.settlement_category` (`city_100k_plus`/`other`/`remote_mountain`, aylanma solig'i stavkasi uchun, SK 467-modda). Shu bosqichda **`/install`** (UX-INSTALL, E-32) — autentifikatsiyasiz, ochiq route, BO-21 ⑥ bosqichi va iOS o'rnatish yo'riqnomasi shu komponentni ichiga oladi. *(2026-10-14: tekshiruv; 2026-10-15: qabul-7 — A-01/E-32)*
- M13/M14: xodim qo'shish, standart rollar, bitta filial va ombor avtomatik; US-M14-03 yangi filial qo'shish. **Admin foydalanuvchilar paneli (BO-11, foydalanuvchi qarori 2026-10-15)**: xodim bloklash, rol/filial tayinlash, **PIN'ni qayta o'rnatish** (US-M13-04, SMS orqali bir martalik taklif/tiklash kodi), **sessiya/qurilmalarni bekor qilish** (US-M13-06, `14-autentifikatsiya-oauth2.md` §18.2) — shu bosqichda to'liq. *(2026-10-15: foydalanuvchi qarori — US-M13-04/06 hikoya ID'lari aniqlashtirildi, qabul-5 KICHIK 3)*
- M09: tovarlar, shtrix-kodlar, MXIK kodi, narx va narx tarixi; US-M04-04 import `import_jobs` orqali (yuklash → tekshirish/xatolar ro'yxati → tasdiqlash) va boshlang'ich qoldiq (`stock_openings`). *(2026-10-14: tekshiruv)*
- Telegram OTP adapter (`21-integratsiyalar.md` §11.1 — asosiy kanal, asoschi qarori Q7) + SMS adapter (`21-integratsiyalar.md` §10 — faqat zaxira) — 0-bosqichda tanlangan SMS provayder bilan. **Aniqlashtirish** *(2026-10-15: qabul-5 KICHIK 4, foydalanuvchi tasdig'i so'ralsin — "mock yo'q" talabiga mos)*: `FakeSms`/`FakeTelegram` **faqat lokal dev**'da, aniq flag bilan yoqiladi; staging va prod — har doim haqiqiy provayder; auth testlari OTP oqimini test-raqam yo'li orqali **haqiqiy** (mock'siz) oqimda tekshiradi.
- Google bilan kirish (`/auth/google/start`/`/auth/google/callback`, `user_identities` jadvali, `14-autentifikatsiya-oauth2.md` §2.2) — asoschi qarori Q7, qo'shimcha (ixtiyoriy) login yo'li, telefon+parol/OTP'ni almashtirmaydi.
- **Tayyor bo'lish mezoni:** yangi do'kon 10 daqiqada ro'yxatdan o'tib, 500 ta tovarni Excel'dan yuklay oladi; foydalanuvchi telefon+OTP (Telegram/SMS) yoki Google bilan ham kirishi mumkin.

## 2-bosqich: ombor va hujjat o'tkazish yadrosi

- Posting xizmati (`09-…`, 2-bo'lim): hujjat → `stock_moves`, `stock_lots`, `ledger_entries`, `vat_moves` bitta tranzaksiyada; teskari hujjat.
- M07 kirim (naqd va nasiyaga), yetkazib beruvchilar; M04 qoldiq, FIFO/AVECO (US-M04-05), qayta hisoblash ishi.
- M06 ko'chirish, M05 inventarizatsiya (Must — US-M05-01…03; posting sinovi uchun ham foydali).
- US-M07-05 yetkazib beruvchiga qaytarish; US-M04-06 hisobdan chiqarish + yaroqlilik muddati maydoni; BO-03 'Ko'chirishlar' tabi (US-M06-03). *(2026-10-14: tekshiruv)*
- **Mezon:** `13-provodka-qoidalari.md` dagi raqamli misollar avtomatik testlarda o'tadi.

## 3-bosqich: veb-kassa

- M01 kassa (onlayn): qidiruv/skaner, chek, to'lov (naqd, karta, aralash, **UzQR** — yuridik shaxslar uchun 2026-07-01'dan majburiy, PF-246 3-b; Click/Payme ixtiyoriy), smena va Z-hisobot; chek chop etish — platformaga qarab ikki yo'l (`24-frontend-arxitekturasi.md` §6, `25-nofunksional-talablar.md` §7, *2026-10-15: foydalanuvchi qarori, D3*): Chrome/Edge/Android — WebUSB/Web Serial/Web Bluetooth + tarmoq/bulut printer; iPhone/iPad (o'rnatilgan PWA) — **faqat** bulut printer adapteri (Star CloudPRNT / Epson Server Direct Print klassi) yoki elektron chek (QR/Telegram). *(2026-10-14: tekshiruv — UzQR qo'shildi)*
- **Bulut printer adapteri** (`shared/lib/printer/cloud`) — Star CloudPRNT/Epson Server Direct Print klassi uchun umumiy interfeys (iOS yo'li uchun majburiy, Chromium'da ixtiyoriy zahira); **iOS o'rnatish ko'rsatmasi** (Safari → "Bosh ekranga qo'shish") POS-01/onboarding ekraniga qo'shiladi. Bulut printer narxi/mavjudligi O'zbekistonda va faqat-elektron chekning qonuniyligi — ochiq savol (`25-nofunksional-talablar.md` §7.2). *(2026-10-15: foydalanuvchi qarori, D3)*
- M16 kassa pul harakati, smena oxirida naqdni sanash; M02 qaytarish; M03 chegirma (limit + PIN tasdiq).
- Offline: Dexie keshi, outbox, `/sync/push`/`/sync/pull` (`16-offline-sync.md`).
- BO-16 (M02/M03/M08/M16 turlari) — yangi jadvallar **`approval_requests`** (masofaviy tasdiq navbati) va **`doc_approvals`** (qo'llangan har tasdiqning append-only izi, DB-09/DB-10); `GET /approval-requests?status=pending`, `POST /approval-requests/{id}/approve|reject`; BO-11 qurilmalar va bekor qilish; `sale.draft_voided`, qayta chop etish auditi. *(2026-10-14: tekshiruv; 2026-10-15: qabul-6)*
- **Mezon:** internet o'chirilganda 2 soat savdo, keyin barcha cheklar yo'qotishsiz va takrorsiz sinxronlanadi.

## 4-bosqich: qarz daftari, xarajatlar, hisobotlar, Telegram

- M08 qarz daftari: tez qarz yozish (offline), mijoz daftari, boshlang'ich qarzlar, to'lov (eng eski qarzdan), va'da sanasi, qarzlar hisoboti, yetkazib beruvchiga qarz va unga to'lov (US-M08-11, US-M07-04 — `supplier_payments`, bank/naqd).
- M15 xarajatlar (+ takrorlanuvchi), sof foyda.
- M12 Egasi dashboard va asosiy hisobotlar; M18 Telegram bot: ulash va kunlik hisobot.
- Filiallar bo'yicha va jami ko'rinish (US-M14-01, US-M04-03); kam qoldiq ogohlantirishi (US-M04-02). *(2026-10-14: tekshiruv)*
- **Mezon:** pilot do'kon qog'oz daftarsiz bir hafta ishlaydi.

## 5-bosqich: fiskal va e-faktura

- **OFD/virtual kassa — `FiscalAdapter` porti + pilot hamkor adapteri** *(2026-10-15: foydalanuvchi qarori — `tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md` (b)/#2, `21-integratsiyalar.md` §1)*: 0-bosqichda boshlangan o'z reyestr arizasi hali tasdiqlanmagani sababli, bu bosqichda **reyestr hamkori adapteri** (Multikassa yoki E-POS Communicator) ishga tushiriladi — `FiscalAdapter` porti orqali, keyinroq o'z modulimiz tayyor bo'lganda adapter almashtiriladi (kod o'zgarmaydi). Hamkor haqini pilot davrida **biz to'laymiz** (≤~13 mln so'm byudjet). 48 soat nazorati, fiskal chek holatlari.
- **CRPT Turon (markirovka) — ishtirokchi (participant) API kalit integratsiyasi** *(2026-10-15: foydalanuvchi qarori — `tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md` #3, `21-integratsiyalar.md` §4; ilgari "MVP'dan keyin" edi, endi MVP bosqichiga ko'chirildi)*: har do'kon o'z bepul ishtirokchi kabinetidan API kalit oladi va tenant sozlamalariga kiritadi (`tenant_secrets`); `verify_code`/`sell`/`return_codes`/`transfer` adapter chaqiruvlari; agar Xat 2 javobi bu yo'lni rad etsa — reyestr hamkori orqali proksi (zaxira), ikkisi ham ishlamasa markirovkalangan tovar sotuvi bloklanadi.
- **E-faktura — faqat Faktura.uz** *(2026-10-15: foydalanuvchi qarori — `tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md` #4)* + E-IMZO brauzerda imzolash; kiruvchi faktura → kirim; VM 830 xavf belgisi. Didox — MVP'dan keyingi birinchi integratsiya (`27-backlog.md` "MVP'dan keyin" ro'yxati).
- M10 ichki QQS registri, qizil faktura bo'yicha QQS krediti faqat to'lovdan keyin (US-M07-04 ikkinchi mezoni, US-M10-03); M11 buxgalteriya hisobotlari (tasdiqlangan hisoblar rejasi bilan, 4910-hisob shubhali qarz zahirasi bilan). **Qo'lda buxgalteriya tuzatishi** — yangi hujjat jadvali **`ledger_adjustments`** + `ledger_entries.branch_id` (DB-12), `POST /ledger-adjustments` (bir bosqichli, darhol `posted`), `POST /ledger-adjustments/{id}/cancel`, `GET /ledger-adjustments` — faqat joriy ochiq davrda (`13-provodka-qoidalari.md` §5.1). *(2026-10-15: qabul-6 — DB-12/A3-04)*
- US-M10-03 kutilayotgan QQS krediti (BO-07/BO-10). *(2026-10-14: tekshiruv)*
- **Chiquvchi e-faktura** (US-M01-06, BP-13/BP-03, qaror #18) — yangi ruxsat kodi **`einvoice.create`**, `POST /api/v1/einvoices` (`direction=out`, B2B nasiya sotuvdan server avtomatik `draft`) va `POST /api/v1/einvoices/from-receipt` (BO-15 "Chek asosida e-faktura chiqarish" tugmasi); `einvoices.related_doc`, provodka yozilmaydi (`13-provodka-qoidalari.md` 2.22), `uq_einvoice_out_per_doc` — bitta hujjatga bitta faol chiquvchi faktura. *(2026-10-15: qabul-5 KICHIK 2; 2026-10-15: qabul-6 — K1-04/A1-24)*
- **Mezon:** test muhitida chek fiskallashadi (hamkor adapteri orqali); kiruvchi e-faktura (Faktura.uz) qabul qilinib imzolanadi; markirovkalangan tovar ishtirokchi kalit bilan tekshiriladi.

## 6-bosqich: to'lov, AI, pilot

- M17 obuna to'lovi (Payme/Click), tarif limitlari; **24 soatlik imtiyoz tugagach qattiq to'xtatish** (foydalanuvchi qarori 2026-10-15, `14-autentifikatsiya-oauth2.md` §16–17): billing webhook bilan birga — tenant bo'yicha sessiya/token ommaviy bekor qilish, Redis `sub_status` keshi, offline litsenziya tokeni (`valid_until`) chiqarish/yangilash, login sahifasidagi "Obuna muddati tugagan" + to'lov havolasi holati. Ikki tor istisno: **D1** — lokautdan oldingi cheklar cheklangan `sync.drain` orqali OFD'ga baribir yuboriladi (`16-offline-sync.md` §3.5, `21-integratsiyalar.md` §1/§9); **D2** — lokaut davrida eksport faqat to'lov sahifasidan, SMS OTP bilan. *(2026-10-15: foydalanuvchi qarori — avvalgi "huquqiy tasdiqdan keyin kassa davom etadi" rejasi bekor qilindi)*
- M17 ichki admin panel (ADM-01, US-M17-04, **US-M13-08** — platforma admini Egasi hisobini bloklash/parol tiklash/sessiyalarini boshqarishi): tenantlar, obuna holati, to'lov tarixi, AI sarfi, faol kassalar; pilot do'konlar uchun muddatni qo'lda uzaytirish; `platform_admins` alohida autentifikatsiya, har kirish audit'da (`15-xavfsizlik-va-audit.md` §3.4). *(2026-10-15: qabul-5 KICHIK 3 — US-M13-08 hikoya ID'si qo'shildi)*
- AI-01 (savol-javob, whitelisted tool'lar) va AI-06 (qarz eslatma matni) — `22-ai-qatlami.md`; AI limiti va xarajat hisobi.
- **AI-03** (qog'oz hujjat OCR, pilot bilan, tor qamrov) — BO-04 kirim avto-to'ldirish, US-M04-04 (3)-yo'l, M02 qog'oz chek; `22-ai-qatlami.md` §10 OCR quvuri, majburiy inson tasdig'i va ishonch chegarasi. *(2026-10-15: foydalanuvchi qarori — AI-03 MVP'ga qaytarildi, 6-bosqichda)*
- M10 davlat hisobotini solishtirish (fayl yuklash) + AI-05 tushuntirish + 5 kalendar kunlik taymer.
- M09 yorliq chop etish; M18 ogohlantirishlar.
- US-M09-02 narx tasdiqlash (BO-16); yaroqlilik muddati ogohlantirishi (M18). *(2026-10-14: tekshiruv)*
- **Pilot:** 5–10 do'kon, xarajat va AI sarfini o'lchash (unit-iqtisod).

## MVP'dan keyin (tartib taxminiy)

1. ~~Asl belgisi (CRPT Turon) integratsiyasining o'zi~~ — **MVP'ga ko'chirildi** (2026-10-15: foydalanuvchi qarori, 5-bosqich — har do'konning o'z ishtirokchi API kaliti orqali). MVP'dan keyin qoladigan qism: **e-TTN**; **e-ishonchnoma (Vakolat.uz)**.
2. ~~AI-03 (US-M04-04 (3)-yo'l) — qog'oz hujjat OCR~~ — **bekor qilindi**: AI-03 MVP'da, 6-bosqichda (foydalanuvchi qarori, 2026-10-15). Mijozlarga SMS/Telegram qarz xabarlari (US-M08-08) — MVP'dan keyin, **tasdiqlandi** (asoschi qarori, Q6, 2026-10-15).
3. Android POS (Kotlin) — `28-android-pos.md` 1–4 bosqichlari.
4. Uzum to'lovi, ko'p ombor, talab bashorati (AI-09) — 2–3 oylik savdo tarixidan keyin. *(2026-10-14: tekshiruv — "filiallar konsolidatsiyasi" olib tashlandi, 4-bosqichga ko'chirildi)*
5. O'z AI modelimiz (markaziy GPU server) — yig'ilgan ma'lumot va eval natijalariga qarab.
6. **US-M03-02** (avtomatik chegirma qoidalari), **US-M14-02** (nusxalash), **US-M08-08** (mijozlarga SMS/Telegram qarz xabarlari), **US-M17-05** (to'liq eksport, birinchi pullik mijoz chiqib ketishidan oldin) — MVP'dan keyin, **tasdiqlandi** *(2026-10-15: asoschi qarori, Q6 — eski "tasdiq kutilmoqda" belgisi olib tashlandi)*; ochiq smena ichida kassir topshirish; bitta egasining bir nechta tenanti uchun umumiy ko'rinish; AI Batch (`submit_batch`). *(2026-10-14: tekshiruv)*

## Har bir vazifa uchun "tayyor" ta'rifi

- Spec'dagi US qabul mezonlari avtomatik test bilan qoplangan; posting o'zgarsa raqamli testlar yangilangan.
- RLS izolyatsiya testi va OpenAPI → orval generatsiyasi CI'da yashil.
- uz va ru tarjimalari bor; offline ta'siri (`16-offline-sync.md`) ko'rib chiqilgan.
- Audit jurnaliga tegishli amallar yoziladi; yangi ruxsat kodi matritsaga qo'shilgan.

## Ochiq savollar

1. ~~Jamoa tarkibi va muddat~~ — **hal qilindi** (2026-10-15: asoschi qarori, Q8): jamoa — asoschi + Claude, bosqichlar ketma-ket, qat'iy muddat yo'q (Asosiy xulosa #2).
2. ~~Fiskal yo'l (o'z reyestr yo'li vs hamkor)~~ — **Yopildi** (2026-10-15: foydalanuvchi qarori): ikkisi parallel, 4-band va 5-bosqich. Ochiq qolgan qism: reyestr/sertifikatlash narxi va 1 BHM to'lovi o'z yo'limizga tegishliligi (Xat 1 javobi kutilmoqda).
3. Rasmiy xatlarga javob muddati noma'lum — integratsiya bosqichlari surilishi mumkin.
4. ~~Kechikkan obuna to'lovida kassani to'xtatmaslik siyosatining huquqiy tasdig'i~~ **Yopildi**: foydalanuvchi qarori bilan — kassa 24 soatlik imtiyozdan keyin to'liq to'xtaydi, huquqiy tasdiq endi shart emas (`14-autentifikatsiya-oauth2.md` §16.3). *(2026-10-15: foydalanuvchi qarori)*
5. ~~CRPT Turon — MVP ziddiyati~~ — **Yopildi** (2026-10-15, foydalanuvchi qarori): markirovkalangan tovar sotuvi **va** CRPT Turon integratsiyasining o'zi (ishtirokchi API kaliti orqali) ikkisi ham MVP'ga (5-bosqich) kiradi; API hamon rasmiy ravishda yopiq (403) bo'lgani uchun zaxira zanjiri: rad etilsa — hamkor proksi, ikkisi ham ishlamasa — sotuv bloklanadi (`21-integratsiyalar.md` §4).

## Manbalar

- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` — OAuth 2.0 AS+RS, admin panel, obuna lokauti. *(2026-10-15: foydalanuvchi qarori)*
- `spec/kod-uchun/05-mvp-chegarasi.md`, `tuzatishlar-va-yechimlar.md`, `spec/tarix/kamchiliklar-tahlili.md`.
- `spec/kod-uchun/00…10`.
- `research_notes/texnik/12-taxminlar-va-murojaatlar.md` (rasmiy xatlar loyihasi).

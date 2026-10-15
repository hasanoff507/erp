# 27. Backlog — ketma-ket bosqichlar

**Maqsad:** 2 kishilik jamoa (asoschi + Claude) uchun ishni ketma-ket, tugash mezoni aniq bosqichlarga bo'lib ko'rsatish — har bosqich tugagandan keyin keyingisi boshlanadi.
**Kim uchun:** Asoschi va Claude — qaysi bosqichda ekanini va keyingi bosqichga o'tish shartini bilish uchun.
**Bog'liq fayllar:** `05-mvp-chegarasi.md`, `10-umumiy-arxitektura.md`, `21-integratsiyalar.md`, `26-ochiq-savollar-reestri.md`, `28-android-pos.md`.
**Holat:** joriy, 2026-10-15.

## Asosiy xulosalar

1. **Tartib: avval do'konning kundalik ishi, keyin davlat integratsiyalari.** Kassa + ombor + qarz daftari + xarajat + hisobot davlat API'larisiz ham to'liq ishlaydi va pilotda qiymat beradi; OFD, e-faktura va boshqalar parallel ravishda (rasmiy javoblar kelguncha) quriladi.
2. **Jamoa — 2 kishi: asoschi + Claude** (qaror #35). Qat'iy kalendar muddat yo'q. Ish ketma-ket vertikal bo'laklarda (backend+veb birga, bir bosqich — bir tugallangan foydalanuvchi oqimi) olib boriladi; parallel ish oqimi yo'q (ikki kishilik jamoa bitta narsaga bir vaqtda e'tibor beradi). Har bosqichning tugash mezoni — quyidagi "Tayyor ta'rifi" qatori.
3. Kod yozish bilan **bir vaqtda** tashqi ishlar boshlanadi: rasmiy xatlar, buxgalter bilan provodka tasdig'i, SMS provayder tanlash, 15–20 do'kon egasi bilan suhbat va 5–10 pilot do'kon — bu ishlarni ko'pincha asoschi shaxsan yuritadi, Claude kod bosqichlarida band bo'lgan vaqtda ham.
4. **Fiskal yo'l — ikkisi parallel**: o'z reyestr arizasi Bosqich 0'da boshlanadi (≈50 ish kuni), Bosqich 5'da pilot reyestr hamkori adapteri (`FiscalAdapter` porti) ishga tushadi, keyin o'z modulimizga almashtiriladi (kod o'zgarmaydi).
5. Android POS (Kotlin) — MVP'dan keyin, `28-android-pos.md` bosqichlari bilan.

---

## Bosqich 0: poydevor va tashqi ishlar

**Maqsad:** Backend/veb skeleti ishlaydi, OAuth 2.0 asosiy qatlami tayyor, barcha tashqi murojaatlar (rasmiy xatlar, buxgalter, pentest, support, pilot suhbatlari) boshlangan.

**Kirish shartlari:** Repo tashkil qilingan; infratuzilma (Postgres, Redis, UzCloud) tanlovi qilingan.

**Vazifalar:**
- [ ] Backend skeleti: FastAPI, `app/core` (tenant konteksti, RLS, xatolar, idempotentlik), Alembic, SAQ worker, docker compose, CI (`23-backend-arxitekturasi.md`)
- [ ] To'liq OAuth 2.0 AS+RS poydevori: `app/modules/auth/` — Authlib integratsiyasi, `/oauth/*`, `/auth/*` endpoint'lari, imzolash kaliti/JWKS, token/sessiya/litsenziya jadvallari (`14-autentifikatsiya-oauth2.md`, qaror #14) — Bosqich 0'da poydevor, Bosqich 1'da to'liq ishlaydigan holatga keltiriladi
- [ ] Veb skeleti: Turborepo, `apps/shell`, `@shared/api` (orval), `@shared/ui` (shadcn), `@shared/state`, i18n uz/ru, PWA (`24-frontend-arxitekturasi.md`)
- [ ] Seed: rollar, ruxsatlar, o'lchov birliklari, xarajat toifalari, tariflar (`15-xavfsizlik-va-audit.md` §2.2 matritsasi)
- [ ] Tashqi: rasmiy xatlarni yuborish — Soliq qo'mitasi, CRPT Turon, Faktura.uz, Didox, Click, Payme, Uzum Bank, fiskal hamkor (Multikassa/E-POS), virtual kassa reyestri arizasi (`spec/tarix/tekshiruv/rasmiy-xatlar.md`, Xat 1–10)
- [ ] Tashqi: buxgalter bilan `13-provodka-qoidalari.md` ni tekshirish — tasdiqlangan hisoblar rejasi + ogohlantirish blokidagi bandlar bo'yicha yozma javoblar
- [ ] Tashqi: o'z virtual kassamizni davlat reyestriga kiritish arizasi (VMQ-943, 4-ilova, ~50 ish kuni); parallel — pilot uchun reyestr hamkori (Multikassa/E-POS Communicator) bilan muzokara; SMS provayder tanlash (Eskiz.uz)
- [ ] Tashqi: pentest tayyorgarligi — avtomatik DAST (OWASP ZAP) CI'ga ulash, ichki OAuth/to'lov/fiskal tekshiruv ro'yxati, Celion/ONESEC'dan rasmiy taklif so'rash (`15-xavfsizlik-va-audit.md` §8)
- [ ] Tashqi: qo'llab-quvvatlash kanali — Telegram "/yordam" + bitta telefon raqami, ish vaqti va dam olish kuni navbatchilik jadvali (`25-nofunksional-talablar.md` §12)
- [ ] Tashqi: 15–20 do'kon egasi bilan suhbat, 5–10 pilot do'kon tanlash
- [ ] Tashqi: huquqiy maslahat — 48 soatdan keyin yangi sotuvni bloklamaslik (`16-offline-sync.md` §6); markirovkalangan tovarni offline sotish (§7, qaror #17) va chekdan keyin e-faktura berish (qaror #18) — mahsulot qarori qabul qilingan, maslahat faqat tasdiq uchun. Natija: yozma huquqiy xulosa (Bosqich 5'dan oldin). Obuna lokauti uchun huquqiy maslahat shart emas (qaror #15, fiskal oqibat Foydalanish shartlarida)

**O'qiladigan spec fayllari:** `23-backend-arxitekturasi.md`, `14-autentifikatsiya-oauth2.md`, `24-frontend-arxitekturasi.md`, `15-xavfsizlik-va-audit.md` §2.2/§8, `13-provodka-qoidalari.md`, `21-integratsiyalar.md`, `25-nofunksional-talablar.md` §12.

**Tayyor ta'rifi:** `GET /health` va RLS izolyatsiya testi yashil; `/oauth/authorize`→`/oauth/token` to'liq Authorization Code+PKCE oqimi real Postgres/Redis'da ishlaydi (mock yo'q); login sahifasi, layout va generatsiya qilingan API klient ishlaydi; rejalashtirilgan barcha rasmiy xatlar yuborilgan; reyestr arizasi va hamkor muzokarasi boshlangan.

---

## Bosqich 1: ro'yxatdan o'tish va katalog

**Maqsad:** Yangi do'kon mustaqil ro'yxatdan o'tadi, xodim qo'shadi, katalogini yuklaydi va turli kirish usullari bilan kira oladi.

**Kirish shartlari:** Bosqich 0 "Tayyor ta'rifi" bajarilgan.

**Vazifalar:**
- [ ] M17 ro'yxatdan o'tish: `POST /auth/signup` — bitta tranzaksiyada tenant+obuna (trial 30 kun)+Egasi+5 rol+standart filial/ombor/kassa provisioning (`14-autentifikatsiya-oauth2.md` §4/§20, A-01)
- [ ] Do'kon sozlamalari (BO-21, BO-14); filial sozlamasida `branches.settlement_category` (`city_100k_plus`/`other`/`remote_mountain`, aylanma solig'i stavkasi uchun, SK 467-modda)
- [ ] `/install` — autentifikatsiyasiz ochiq route, biznes ekranlardan tashqari; BO-21 ⑥ bosqichi va iOS o'rnatish yo'riqnomasi shu komponentni ichiga oladi (`07-ekran-tafsilotlari.md` UX-INSTALL, E-32)
- [ ] M13/M14: xodim qo'shish, standart rollar, bitta filial va ombor avtomatik; yangi filial qo'shish (US-M14-03)
- [ ] Admin foydalanuvchilar paneli (BO-11): xodim bloklash, rol/filial tayinlash, PIN/parolni qayta o'rnatish (US-M13-04, bir martalik taklif/tiklash kodi — Telegram bot birinchi, SMS faqat zaxira, qaror #34), sessiya/qurilmalarni bekor qilish (US-M13-06, `14-autentifikatsiya-oauth2.md` §18.2)
- [ ] M09: tovarlar, shtrix-kodlar, MXIK kodi, narx va narx tarixi
- [ ] Import (US-M04-04): `import_jobs` orqali (yuklash → tekshirish/xatolar ro'yxati → tasdiqlash) va boshlang'ich qoldiq (`stock_openings`)
- [ ] Telegram OTP adapter (`21-integratsiyalar.md` §11.1 — asosiy kanal) + SMS adapter (§10 — faqat zaxira); `FakeSms`/`FakeTelegram` faqat lokal dev'da flag bilan, staging/prod — har doim haqiqiy provayder; auth testlari OTP oqimini test-raqam yo'li orqali haqiqiy (mock'siz) oqimda tekshiradi (qaror #34)
- [ ] Google bilan kirish (`/auth/google/start`/`/auth/google/callback`, `user_identities` jadvali, `14-autentifikatsiya-oauth2.md` §2.2) — qo'shimcha ixtiyoriy login yo'li, telefon+parol/OTP'ni almashtirmaydi

**O'qiladigan spec fayllari:** `14-autentifikatsiya-oauth2.md` §2/§4/§18/§20, `07-ekran-tafsilotlari.md` UX-INSTALL, `03-modullar-talablari.md` M09/M13/M14, `21-integratsiyalar.md` §10/§11.

**Tayyor ta'rifi:** yangi do'kon 10 daqiqada ro'yxatdan o'tib, 500 ta tovarni Excel'dan yuklay oladi; foydalanuvchi telefon+OTP (Telegram/SMS) yoki Google bilan ham kirishi mumkin; tegishli US qabul mezonlari avtomatik test bilan qoplangan.

---

## Bosqich 2: ombor va hujjat o'tkazish yadrosi

**Maqsad:** Hujjat postingi (kirim, ko'chirish, inventarizatsiya, hisobdan chiqarish) to'g'ri qoldiq va provodka hosil qiladi.

**Kirish shartlari:** Bosqich 1 "Tayyor ta'rifi" bajarilgan.

**Vazifalar:**
- [ ] Posting xizmati: hujjat → `stock_moves`, `stock_lots`, `ledger_entries`, `vat_moves` bitta tranzaksiyada; teskari hujjat (`13-provodka-qoidalari.md` §2)
- [ ] M07 kirim (naqd va nasiyaga), yetkazib beruvchilar
- [ ] M04 qoldiq, FIFO/AVECO (US-M04-05), qayta hisoblash ishi
- [ ] M06 ko'chirish, M05 inventarizatsiya (US-M05-01…03)
- [ ] US-M07-05 yetkazib beruvchiga qaytarish
- [ ] US-M04-06 hisobdan chiqarish + yaroqlilik muddati maydoni
- [ ] BO-03 "Ko'chirishlar" tabi (US-M06-03)

**O'qiladigan spec fayllari:** `13-provodka-qoidalari.md` §2, `19-api-ombor.md`, `03-modullar-talablari.md` M04–M07.

**Tayyor ta'rifi:** `13-provodka-qoidalari.md`dagi raqamli misollar avtomatik testlarda o'tadi; posting o'zgarsa raqamli testlar yangilangan.

---

## Bosqich 3: veb-kassa

**Maqsad:** Do'kon internet bor-yo'qligidan qat'i nazar kassada sotish, qaytarish, chegirma va smena yopish ishini to'liq bajara oladi.

**Kirish shartlari:** Bosqich 2 "Tayyor ta'rifi" bajarilgan.

**Vazifalar:**
- [ ] M01 kassa (onlayn): qidiruv/skaner, chek, to'lov (naqd, karta, aralash, UzQR — yuridik shaxslar uchun 2026-07-01'dan majburiy, PF-246 3-b; Click/Payme ixtiyoriy), smena va Z-hisobot
- [ ] Chek chop etish — platformaga qarab ikki yo'l (`24-frontend-arxitekturasi.md` §6, `25-nofunksional-talablar.md` §7): Chrome/Edge/Android — WebUSB/Web Serial/Web Bluetooth + tarmoq/bulut printer; iPhone/iPad (o'rnatilgan PWA) — faqat bulut printer adapteri (Star CloudPRNT/Epson Server Direct Print klassi) yoki elektron chek (QR/Telegram)
- [ ] Bulut printer adapteri (`shared/lib/printer/cloud`) — iOS yo'li uchun majburiy, Chromium'da ixtiyoriy zahira; iOS o'rnatish ko'rsatmasi (Safari → "Bosh ekranga qo'shish") POS-01/onboarding ekraniga
- [ ] M16 kassa pul harakati, smena oxirida naqdni sanash
- [ ] M02 qaytarish; M03 chegirma (limit + PIN tasdiq)
- [ ] Offline: Dexie keshi, outbox, `/sync/push`/`/sync/pull` (`16-offline-sync.md`)
- [ ] BO-16 masofaviy tasdiq navbati (M02/M03/M08/M16 turlari) — `approval_requests` va `doc_approvals` (DB-09/DB-10); `GET /approval-requests?status=pending`, `POST /approval-requests/{id}/approve|reject`
- [ ] BO-11 qurilmalar va bekor qilish; `sale.draft_voided`, qayta chop etish auditi

**O'qiladigan spec fayllari:** `18-api-kassa.md`, `16-offline-sync.md`, `08-dizayn-tizimi.md` §5, `24-frontend-arxitekturasi.md` §6, `03-modullar-talablari.md` M01/M02/M03/M16.

**Tayyor ta'rifi:** internet o'chirilganda 2 soat savdo, keyin barcha cheklar yo'qotishsiz va takrorsiz sinxronlanadi; `16-offline-sync.md`dagi konflikt qoidalari (overselling, qarz limiti, narx muzlatish) test bilan qoplangan.

---

## Bosqich 4: qarz daftari, xarajatlar, hisobotlar, Telegram

**Maqsad:** Do'kon qog'oz qarz daftarini va xarajat qaydlarini to'liq elektron qiladi, egasi kunlik hisobotni Telegram'da oladi.

**Kirish shartlari:** Bosqich 3 "Tayyor ta'rifi" bajarilgan.

**Vazifalar:**
- [ ] M08 qarz daftari: tez qarz yozish (offline), mijoz daftari, boshlang'ich qarzlar, to'lov (eng eski qarzdan), va'da sanasi, qarzlar hisoboti
- [ ] Yetkazib beruvchiga qarz va unga to'lov (US-M08-11, US-M07-04 — `supplier_payments`, bank/naqd)
- [ ] M15 xarajatlar (+ takrorlanuvchi), sof foyda
- [ ] M12 Egasi dashboard va asosiy hisobotlar; US-M03-03 chegirmalar margin hisoboti (Could)
- [ ] M18 Telegram bot: ulash va kunlik hisobot
- [ ] Filiallar bo'yicha va jami ko'rinish (US-M14-01, US-M04-03); kam qoldiq ogohlantirishi (US-M04-02)

**O'qiladigan spec fayllari:** `03-modullar-talablari.md` M08/M12/M15/M18, `20-api-moliya-admin.md`.

**Tayyor ta'rifi:** pilot do'kon qog'oz daftarsiz bir hafta ishlaydi.

---

## Bosqich 5: fiskal va e-faktura

**Maqsad:** Har bir sotuv fiskal talablarga mos chek chiqaradi, markirovkalangan tovar tekshiriladi, e-faktura oqimi (kiruvchi va chiquvchi) ishlaydi.

**Kirish shartlari:** Bosqich 4 "Tayyor ta'rifi" bajarilgan; Bosqich 0'da boshlangan reyestr/hamkor muzokarasi davom etmoqda (talab emas, parallel).

**Vazifalar:**
- [ ] `FiscalAdapter` porti + pilot hamkor adapteri (Multikassa yoki E-POS Communicator) — o'z modulimiz tayyor bo'lganda adapter almashtiriladi, kod o'zgarmaydi; hamkor haqini pilot davrida biz to'laymiz (≤~13 mln so'm byudjet); 48 soat nazorati, fiskal chek holatlari; qarz to'lovida `debt_settlement` cheki (qaror #30)
- [ ] CRPT Turon markirovka: ishtirokchi (participant) API kalit integratsiyasi (`tenant_secrets`); `verify_code`/`sell`/`return_codes`/`transfer`; rad etilsa hamkor proksi, ikkisi ham ishlamasa markirovkalangan tovar sotuvi bloklanadi
- [ ] E-faktura — faqat Faktura.uz + E-IMZO brauzerda imzolash; kiruvchi faktura → kirim; VM 830 xavf belgisi
- [ ] M10 ichki QQS registri, qizil faktura bo'yicha QQS krediti faqat to'lovdan keyin (US-M07-04 ikkinchi mezoni, US-M10-03 — kutilayotgan QQS krediti, BO-07/BO-10)
- [ ] M11 buxgalteriya hisobotlari (tasdiqlangan hisoblar rejasi bilan, 4910-hisob shubhali qarz zahirasi)
- [ ] Qo'lda buxgalteriya tuzatishi: `ledger_adjustments` hujjat jadvali + `ledger_entries.branch_id` (DB-12); `POST /ledger-adjustments` (bir bosqichli, darhol `posted`), `POST /ledger-adjustments/{id}/cancel`, `GET /ledger-adjustments` — faqat joriy ochiq davrda (`13-provodka-qoidalari.md` §5.1)
- [ ] Chiquvchi e-faktura (US-M01-06, BP-13/BP-03): `einvoice.create` ruxsati, `POST /api/v1/einvoices` (`direction=out`, B2B nasiya sotuvdan server avtomatik `draft`) va `POST /api/v1/einvoices/from-receipt` (BO-15 "Chek asosida e-faktura chiqarish" tugmasi); `einvoices.related_doc`, provodka yozilmaydi (`13-provodka-qoidalari.md` §2.22), `uq_einvoice_out_per_doc`

**O'qiladigan spec fayllari:** `21-integratsiyalar.md`, `13-provodka-qoidalari.md` §2.14/§2.22/§5, `18-api-kassa.md` §4.5/§12.2/§15a, `12-db-sxema.md` DB-01/DB-09/DB-10/DB-12.

**Tayyor ta'rifi:** test muhitida chek fiskallashadi (hamkor adapteri orqali); kiruvchi e-faktura (Faktura.uz) qabul qilinib imzolanadi; markirovkalangan tovar ishtirokchi kalit bilan tekshiriladi.

---

## Bosqich 6: to'lov, AI, pilot

**Maqsad:** Obuna to'lovi ishlaydi (qaror #15, #22), AI funksiyalari (AI-01/03/05/06, qaror #16) yordam beradi, 5–10 pilot do'kon haqiqiy foydalanishni boshlaydi.

**Kirish shartlari:** Bosqich 5 "Tayyor ta'rifi" bajarilgan.

**Vazifalar:**
- [ ] M17 obuna to'lovi (Payme/Click), tarif limitlari; 24 soatlik imtiyoz tugagach qattiq to'xtatish (`14-autentifikatsiya-oauth2.md` §16–17): billing webhook bilan birga tenant bo'yicha sessiya/token ommaviy bekor qilish, Redis `sub_status` keshi, offline litsenziya tokeni (`valid_until`) chiqarish/yangilash, login sahifasidagi "Obuna muddati tugagan" + to'lov havolasi holati
- [ ] D1 — lokautdan oldingi, hali yuborilmagan fiskal cheklar cheklangan `sync.drain` orqali OFD'ga baribir yuboriladi (`16-offline-sync.md` §3.5, `21-integratsiyalar.md` §1/§9)
- [ ] D2 — lokaut davrida ma'lumot eksporti faqat to'lov (billing) sahifasidan, OTP tasdig'i bilan — Telegram birinchi, SMS zaxira (qaror #20, #34; `16-offline-sync.md` §3.5)
- [ ] M17 ichki admin panel (ADM-01, US-M17-04, US-M13-08 — platforma admini Egasi hisobini bloklash/parol tiklash/sessiyalarini boshqarishi): tenantlar, obuna holati, to'lov tarixi, AI sarfi, faol kassalar; pilot do'konlar uchun muddatni qo'lda uzaytirish; `platform_admins` alohida autentifikatsiya, har kirish audit'da (`15-xavfsizlik-va-audit.md` §3.4)
- [ ] AI-01 (savol-javob, whitelisted tool'lar) va AI-06 (qarz eslatma matni) — `22-ai-qatlami.md`; AI limiti va xarajat hisobi
- [ ] AI-03 (qog'oz hujjat OCR, pilot bilan, tor qamrov) — BO-04 kirim avto-to'ldirish, US-M04-04 (3)-yo'l, M02 qog'oz chek; `22-ai-qatlami.md` §10 OCR quvuri, majburiy inson tasdig'i va ishonch chegarasi
- [ ] M10 davlat hisobotini solishtirish (fayl yuklash) + AI-05 tushuntirish + 5 kalendar kunlik taymer
- [ ] M09 yorliq chop etish; M18 ogohlantirishlar
- [ ] US-M09-07 mijoz kartasida standart chegirma % (`counterparties.standing_discount_pct`, qaror #23); US-M09-02 narx tasdiqlash (BO-16); yaroqlilik muddati ogohlantirishi (M18)
- [ ] **Pilot:** 5–10 do'kon, xarajat va AI sarfini o'lchash (unit-iqtisod)

**O'qiladigan spec fayllari:** `14-autentifikatsiya-oauth2.md` §16–18, `22-ai-qatlami.md`, `09-ai-funksiyalar.md`, `25-nofunksional-talablar.md` §11.

**Tayyor ta'rifi:** obuna lokauti haqiqiy billing webhook bilan test qilingan; AI-01/03/05/06 pilot do'konlarida ishlaydi; 5–10 pilot do'kondan xarajat/AI sarfi bo'yicha xulosa yig'ilgan.

---

## MVP'dan keyin (tartib taxminiy)

1. **e-TTN**, **e-ishonchnoma (Vakolat.uz)** — CRPT Turon markirovkasining o'zi MVP'ga (Bosqich 5) kiritilgan, bu ikkisi qoladi.
2. **Didox** — e-faktura bo'yicha birinchi post-MVP integratsiya (MVP'da faqat Faktura.uz).
3. Mijozlarga SMS/Telegram qarz xabarlari (US-M08-08).
4. Android POS (Kotlin) — `28-android-pos.md` 1–4 bosqichlari.
5. Uzum to'lovi, ko'p ombor, talab bashorati (AI-09) — 2–3 oylik savdo tarixidan keyin.
6. O'z AI modelimiz (markaziy GPU server) — yig'ilgan ma'lumot va eval natijalariga qarab.
7. US-M03-02 (avtomatik chegirma qoidalari), US-M14-02 (nusxalash), US-M17-05 (to'liq eksport, birinchi pullik mijoz chiqib ketishidan oldin) — US-M08-08 (3-band) bilan birga MVP'dan keyin, tasdiqlangan (qaror #33); ochiq smena ichida kassir topshirish; bitta egasining bir nechta tenanti uchun umumiy ko'rinish; AI Batch (`submit_batch`).
8. Ko'p bank hisobi (`bank_accounts`) — hozircha yagona `5110` (`26-ochiq-savollar-reestri.md` #90).
9. Ko'p yuridik shaxsli (turli STIR) tenant qo'llab-quvvatlanishi — MVP'da 1 tenant = 1 yuridik shaxs (`26-ochiq-savollar-reestri.md` #38).

## Har bir vazifa uchun umumiy "tayyor" ta'rifi

- Spec'dagi US qabul mezonlari avtomatik test bilan qoplangan; posting o'zgarsa raqamli testlar yangilangan.
- RLS izolyatsiya testi va OpenAPI → orval generatsiyasi CI'da yashil.
- uz va ru tarjimalari bor; offline ta'siri (`16-offline-sync.md`) ko'rib chiqilgan.
- Audit jurnaliga tegishli amallar yoziladi; yangi ruxsat kodi matritsaga qo'shilgan.

## Ochiq savollar

1. Rasmiy xatlarga javob muddati noma'lum — integratsiya bosqichlari (5, 6) surilishi mumkin (`26-ochiq-savollar-reestri.md` #71).
2. O'z reyestr yo'li: reyestr/sertifikatlash narxi va 1 BHM to'lovi tegishliligi — Xat 1 javobi kutilmoqda (`26-ochiq-savollar-reestri.md` #42).
3. Bulut printer narxi/mavjudligi O'zbekistonda va faqat-elektron chekning qonuniyligi (Bosqich 3, iOS yo'li) — `25-nofunksional-talablar.md` §7.2, `26-ochiq-savollar-reestri.md` #11.
4. Omborchi kirimni o'zi `post` qila oladimi (Bosqich 2), ko'p bank hisobi (MVP'dan keyin) — asoschi tasdig'i kutilmoqda (qaror #27).

## Manbalar

- `spec/kod-uchun/05-mvp-chegarasi.md`, `10-umumiy-arxitektura.md`, `21-integratsiyalar.md`.
- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` — OAuth 2.0 AS+RS, admin panel, obuna lokauti.
- `spec/kod-uchun/26-ochiq-savollar-reestri.md` — Jadval B'dagi bosqich bog'lanishlari.
- `spec/tarix/tekshiruv/rasmiy-xatlar.md` — rasmiy xatlar (Xat 1–10).

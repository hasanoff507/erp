# 27. Backlog — ketma-ket bosqichlar

**Maqsad:** 2 kishilik jamoa (asoschi + Claude) uchun ishni ketma-ket, tugash mezoni aniq bosqichlarga bo'lib ko'rsatish — har bosqich tugagandan keyin keyingisi boshlanadi.
**Kim uchun:** Asoschi va Claude — qaysi bosqichda ekanini va keyingi bosqichga o'tish shartini bilish uchun.
**Bog'liq fayllar:** `01-qarorlar.md`, `05-mvp-chegarasi.md`, `10-umumiy-arxitektura.md`, `21-integratsiyalar.md`, `26-ochiq-savollar-reestri.md`, `28-android-pos.md`, `30-izchillik-matritsasi.md`, `33-1c-integratsiya.md` (§17.1), `34-1c-agent.md`.
**Holat:** joriy, 2026-10-16.

## Asosiy xulosalar

1. **Tartib: avval do'konning kundalik ishi, keyin davlat integratsiyalari.** Kassa + ombor + qarz daftari + xarajat + hisobot davlat API'larisiz ham to'liq ishlaydi va pilotda qiymat beradi; OFD, e-faktura va boshqalar parallel ravishda (rasmiy javoblar kelguncha) quriladi.
2. **Jamoa — 2 kishi: asoschi + Claude** (qaror #35). Qat'iy kalendar muddat yo'q. Ish ketma-ket vertikal bo'laklarda (backend+veb birga, bir bosqich — bir tugallangan foydalanuvchi oqimi) olib boriladi; parallel ish oqimi yo'q (ikki kishilik jamoa bitta narsaga bir vaqtda e'tibor beradi). Har bosqichning tugash mezoni — quyidagi "Tayyor ta'rifi" qatori.
3. Kod yozish bilan **bir vaqtda** tashqi ishlar boshlanadi: rasmiy xatlar, buxgalter bilan provodka tasdig'i, SMS provayder tanlash, 15–20 do'kon egasi bilan suhbat va 5–10 pilot do'kon — bu ishlarni ko'pincha asoschi shaxsan yuritadi, Claude kod bosqichlarida band bo'lgan vaqtda ham.
4. **Fiskal yo'l — ikkisi parallel**: o'z reyestr arizasi Bosqich 0'da boshlanadi (35 ish kuni, eng yomon 45 — 26 #25), Bosqich 5'da pilot hamkor adapteri `FiscalPort` ortida ishga tushadi, keyin o'z modulimizga almashtiriladi (kod o'zgarmaydi). Ochiq bulut OFD API yo'q — POS chekni **Do'kon agenti** (qaror #60) fiskal ko'prigi orqali FM'ga beradi yoki hamkor bulut API'si orqali; Bosqich 3–4 da kod `FISCAL_PROVIDER=fake` bilan yoziladi.
5. **Do'kon agenti** (qaror #60) — Bosqich 0 da agent kodi yozilmaydi (faqat `devices.kind`/`signing_keys.purpose` CHECK'lari, qaror #58 c); agent asosi, fiskal ko'prik, xom TCP printer va tarozi — **Bosqich 5**; 1C imkoniyati — **Bosqich 7**.
6. Android POS (Kotlin) — MVP'dan keyin, `28-android-pos.md` bosqichlari bilan.
7. **MVP'dan keyingi birinchi bosqich — Bosqich 7: 1C integratsiyasi** (qaror #36–#42): pilot do'konlarning kunlik hujjatlari ularning o'z 1C bazasiga (faqat COM, Do'kon agenti) yoziladi; 99 000 tarif ichida.
8. Har bosqichning **US-ID ro'yxati** — bosqich ichidagi "Hikoyalar" qatori (qaror #58 b); `30-izchillik-matritsasi.md` shu ro'yxatga tayanadi. Tashqi javob kutayotgan bandlar va ular bloklaydigan bosqich — "Tashqi bog'liqliklar" bo'limi.

---

## Bosqich 0: poydevor va tashqi ishlar

**Maqsad:** Backend/veb skeleti ishlaydi, OAuth 2.0 asosiy qatlami tayyor, barcha tashqi murojaatlar (rasmiy xatlar, buxgalter, pentest, support, pilot suhbatlari) boshlangan.

**Kirish shartlari:** Repo tashkil qilingan; infratuzilma (Postgres, Redis, UzCloud) tanlovi qilingan.

**Vazifalar:**
- [ ] Backend skeleti: FastAPI, `app/core` (tenant konteksti, RLS, xatolar, idempotentlik), Alembic, SAQ worker, docker compose, CI (`23-backend-arxitekturasi.md`)
- [ ] To'liq OAuth 2.0 AS+RS poydevori: `app/modules/auth/` — Authlib integratsiyasi, `/oauth/*`, `/auth/*` endpoint'lari, imzolash kaliti/JWKS, token/sessiya/litsenziya jadvallari (`14-autentifikatsiya-oauth2.md`, qaror #14) — Bosqich 0'da poydevor, Bosqich 1'da to'liq ishlaydigan holatga keltiriladi
- [ ] Veb skeleti: Turborepo, `apps/shell`, `@shared/api` (orval), `@shared/ui` (shadcn), `@shared/state`, i18n uz/ru, PWA (`24-frontend-arxitekturasi.md`)
- [ ] Seed: rollar, ruxsatlar, o'lchov birliklari, xarajat toifalari (`expense_categories.default_account` — 9410/9420/9430/6410, 26 #143), hisoblar rejasi (NSBU №21 subset + 9390, 2920, 4890, 6610, 8530, texnik `0000` — 26 #6/#36), aylanma solig'i stavkalari (26 #111), tariflar (`15-xavfsizlik-va-audit.md` §2.2 matritsasi)
- [ ] Bosqich 0 migratsiyasida: `devices.kind` + `'onec_agent'`, `signing_keys.purpose` + `'onec_task'`/`'agent_update'` (qaror #58 c)
- [ ] Spike: `zxing-cpp` GS1 DataMatrix (FNC1) dekod/enkod — `tests/fixtures/datamatrix` test-vektorlari; mos kelmasa `bwip-js` server zahirasi (qaror #57, 26 #62)
- [ ] Spike: U+02BB (`oʻ gʻ`) va kirill glif skrinshot-testi Windows/Android/iOS'da; yetishmasa self-hosted Noto Sans (qaror #57, 26 #141)
- [ ] Kod sifati: mypy `--strict`, ESLint pul qoidasi, `pip-audit`/`npm audit --audit-level=high`/`gitleaks` CI'da, `.env.example`, qat'iy CSP (qaror #57)
- [ ] Sirlar va zaxira: SOPS/age (yoki o'z-hosted Vault), ilova darajasida envelope shifrlash (`tenant_secrets`), o'z WAL PITR, boshqa provayderda zaxira nusxa, UzCloud avto-to'lov + billing ogohlantirishi (qaror #65, #51)
- [ ] Shaxsiy ma'lumot: AI so'rov quruvchisida majburiy maskalash qatlami (o'chirib bo'lmaydi), `tenants.accepted_terms_version/at/ip`, `settings.ai_cross_border_enabled=false` standart; ro'yxatdan o'tish formasida Foydalanish shartlari aksepti (qaror #61; matn — 26 #127)
- [ ] Tashqi: asoschi — kompaniya yuridik shaxsi (MChJ) va xatlarni imzolovchi (26 #130) — barcha xatlardan oldin
- [ ] Tashqi: rasmiy xatlarni yuborish — "Tashqi bog'liqliklar" jadvalidagi har xat (`spec/tarix/tekshiruv/rasmiy-xatlar.md`, Xat 1–10; qo'shimcha savollar — `research_notes/ochiq-savollar/D-qarorlar-va-E-standartlar.md` §5.2); `letter_tracker` (15/30/60 kun, 26 #71)
- [ ] Tashqi: buxgalter bilan `13-provodka-qoidalari.md` ni tekshirish — tasdiqlangan hisoblar rejasi + ogohlantirish blokidagi bandlar bo'yicha yozma javoblar
- [ ] Tashqi: o'z virtual kassamizni davlat reyestriga kiritish arizasi (VMQ-943 4-ilova, 35 ish kuni, Kiberxavfsizlik markazi xulosasi bilan — 26 #25/#42); parallel — pilot uchun fiskal hamkor (Multikassa/E-POS) bilan muzokara: lokal ko'prik ruxsati, bulut rejimi, narx (26 #109, #168, #169); Eskiz.uz shartnomasi — yuridik shaxsdan keyin (26 #45)
- [ ] Tashqi: pentest tayyorgarligi — avtomatik DAST (OWASP ZAP) CI'ga ulash, ichki OAuth/to'lov/fiskal tekshiruv ro'yxati, Celion/ONESEC'dan rasmiy taklif so'rash (`15-xavfsizlik-va-audit.md` §8)
- [ ] Tashqi: qo'llab-quvvatlash kanali — Telegram "/yordam" + bitta telefon raqami, ish vaqti va dam olish kuni navbatchilik jadvali (`25-nofunksional-talablar.md` §12)
- [ ] Tashqi: 15–20 do'kon egasi bilan suhbat, 5–10 pilot do'kon tanlash
- [ ] Tashqi: yurist — Foydalanish shartlari / ommaviy oferta (o'zbek tilida), shaxsiy ma'lumot bloki va chegaradan tashqari uzatishga rozilik, lokautda fiskal mas'uliyat (qaror #15), 24/72 soat insident runbook'i (26 #127, #126). Natija: imzolangan oferta — birinchi real tenantdan oldin (Bosqich 6 oxiri)

**O'qiladigan spec fayllari:** `23-backend-arxitekturasi.md`, `14-autentifikatsiya-oauth2.md`, `24-frontend-arxitekturasi.md`, `15-xavfsizlik-va-audit.md` §2.2/§8, `13-provodka-qoidalari.md`, `21-integratsiyalar.md`, `25-nofunksional-talablar.md` §12.

**Hikoyalar:** — (infratuzilma, qaror #58 b).

**Tayyor ta'rifi:** `GET /health` va RLS izolyatsiya testi yashil; DataMatrix va shrift spike natijalari yozilgan; maskalash qatlami unit-testlari yashil; `/oauth/authorize`→`/oauth/token` to'liq Authorization Code+PKCE oqimi real Postgres/Redis'da ishlaydi (mock yo'q); login sahifasi, layout va generatsiya qilingan API klient ishlaydi; yuridik shaxs bo'yicha asoschi qarori bor va rejalashtirilgan barcha rasmiy xatlar yuborilgan; reyestr arizasi va hamkor muzokarasi boshlangan.

---

## Bosqich 1: ro'yxatdan o'tish va katalog

**Maqsad:** Yangi do'kon mustaqil ro'yxatdan o'tadi, xodim qo'shadi, katalogini yuklaydi va turli kirish usullari bilan kira oladi.

**Kirish shartlari:** Bosqich 0 "Tayyor ta'rifi" bajarilgan.

**Vazifalar:**
- [ ] M17 ro'yxatdan o'tish: `POST /auth/signup` — bitta tranzaksiyada tenant+obuna (trial 30 kun)+Egasi+5 rol+standart filial/ombor/kassa provisioning (`14-autentifikatsiya-oauth2.md` §4/§20, A-01)
- [ ] Do'kon sozlamalari (BO-21, BO-14), `tenants.legal_form` ("Egasi oldi" hisobi uchun, 26 #39); filial sozlamasida `branches.settlement_category` (`city_100k_plus`/`other`/`remote_mountain`, aylanma solig'i stavkasi uchun, SK 467-modda)
- [ ] `/install` — autentifikatsiyasiz ochiq route, biznes ekranlardan tashqari; BO-21 ⑥ bosqichi va iOS o'rnatish yo'riqnomasi shu komponentni ichiga oladi (`07-ekran-tafsilotlari.md` UX-INSTALL, E-32)
- [ ] M13/M14: xodim qo'shish, standart rollar, bitta filial va ombor avtomatik; yangi filial qo'shish (US-M14-03)
- [ ] Admin foydalanuvchilar paneli (BO-11): xodim bloklash, rol/filial tayinlash, PIN/parolni qayta o'rnatish (US-M13-04, bir martalik taklif/tiklash kodi — Telegram bot birinchi, SMS faqat zaxira, qaror #34), sessiya/qurilmalarni bekor qilish (US-M13-06, `14-autentifikatsiya-oauth2.md` §18.2)
- [ ] M09: tovarlar, shtrix-kodlar, MXIK kodi, narx va narx tarixi
- [ ] Import (US-M04-04): `import_jobs` orqali (yuklash → tekshirish/xatolar ro'yxati → tasdiqlash) va boshlang'ich qoldiq (`stock_openings`)
- [ ] Telegram OTP adapter (`21-integratsiyalar.md` §11.1 — asosiy kanal) + SMS adapter (§10 — faqat zaxira); `FakeSms`/`FakeTelegram` faqat lokal dev'da flag bilan, staging/prod — har doim haqiqiy provayder; auth testlari OTP oqimini test-raqam yo'li orqali haqiqiy (mock'siz) oqimda tekshiradi (qaror #34)
- [ ] Google bilan kirish (`/auth/google/start`/`/auth/google/callback`, `user_identities` jadvali, `14-autentifikatsiya-oauth2.md` §2.2) — qo'shimcha ixtiyoriy login yo'li, telefon+parol/OTP'ni almashtirmaydi

**O'qiladigan spec fayllari:** `14-autentifikatsiya-oauth2.md` §2/§4/§18/§20, `07-ekran-tafsilotlari.md` UX-INSTALL, `03-modullar-talablari.md` M09/M13/M14, `21-integratsiyalar.md` §10/§11.

**Hikoyalar:** US-M17-01, US-M13-01…07, US-M14-03, US-M14-04, US-M09-01, US-M09-03, US-M09-05, US-M04-04.

**Tayyor ta'rifi:** yangi do'kon 10 daqiqada ro'yxatdan o'tib, 500 ta tovarni Excel'dan yuklay oladi; foydalanuvchi telefon+OTP (Telegram/SMS) yoki Google bilan ham kirishi mumkin; tegishli US qabul mezonlari avtomatik test bilan qoplangan.

---

## Bosqich 2: ombor va hujjat o'tkazish yadrosi

**Maqsad:** Hujjat postingi (kirim, ko'chirish, inventarizatsiya, hisobdan chiqarish) to'g'ri qoldiq va provodka hosil qiladi.

**Kirish shartlari:** Bosqich 1 "Tayyor ta'rifi" bajarilgan.

**Vazifalar:**
- [ ] Posting xizmati: hujjat → `stock_moves`, `stock_lots`, `ledger_entries`, `vat_moves` bitta tranzaksiyada; teskari hujjat (`13-provodka-qoidalari.md` §2)
- [ ] M07 kirim (naqd va nasiyaga), yetkazib beruvchilar
- [ ] M04 qoldiq, FIFO/AVECO (US-M04-05), qayta hisoblash ishi
- [ ] M06 ko'chirish, M05 inventarizatsiya (US-M05-01…03) — `expected` formulasi `count_lines.counted_at` bilan (qaror #53); ortiqcha `Kt 9390`, kamomad 5910/4730 (26 #35); ombor hisobi `warehouses.inventory_account` (2910/2920)
- [ ] Ko'chirish `post` — `ettn_documents` qoralamasi ("Ombordan omborga", `transfers.transport_mode`) yaratiladi; yuborish `EInvoicePort` stub orqali (real — Bosqich 5; qaror #63)
- [ ] US-M07-05 yetkazib beruvchiga qaytarish
- [ ] US-M04-06 hisobdan chiqarish + yaroqlilik muddati maydoni; faqat online (qaror #54); boshlang'ich qoldiq kontr-hisobi `0000` (26 #36)
- [ ] BO-03 "Ko'chirishlar" tabi (US-M06-03)

**O'qiladigan spec fayllari:** `13-provodka-qoidalari.md` §2, `19-api-ombor.md`, `03-modullar-talablari.md` M04–M07.

**Hikoyalar:** US-M04-01, US-M04-05, US-M04-06, US-M05-01…03, US-M06-01…03, US-M07-01, US-M07-02, US-M07-05, US-M11-01.

**Tayyor ta'rifi:** `13-provodka-qoidalari.md`dagi raqamli misollar avtomatik testlarda o'tadi; posting o'zgarsa raqamli testlar yangilangan.

---

## Bosqich 3: veb-kassa

**Maqsad:** Do'kon internet bor-yo'qligidan qat'i nazar kassada sotish, qaytarish, chegirma va smena yopish ishini to'liq bajara oladi.

**Kirish shartlari:** Bosqich 2 "Tayyor ta'rifi" bajarilgan.

**Vazifalar:**
- [ ] M01 kassa (onlayn): qidiruv/skaner, chek, to'lov (naqd, karta, aralash, UzQR — yuridik shaxslar uchun 2026-07-01'dan majburiy, PF-246 3-b; Click/Payme ixtiyoriy), smena va Z-hisobot; chek `FiscalPort` orqali `FISCAL_PROVIDER=fake` bilan (real — Bosqich 5)
- [ ] Karta rekvizitlari (qaror #64): `sale_payments`/`debt_payments` — `card_type` (`method='card'` da majburiy, standart so'raladi), `card_mask` + `rrn` (ijtimoiy kartada majburiy); chekda `payment_form` (`cash/card/qr/mixed`)
- [ ] **Statik UzQR** — kassir qo'lda tasdiqlaydi (`qr_type='static'`, faqat online); dinamik UzQR — `UzqrPort` stub (26 #49)
- [ ] **48 soatlik shkala va blok** (qaror #43): 24 soat 🟡, 40 soat 🔴 + M18, 46 soat modal, 48 soat `FISCAL_OFFLINE_48H_BLOCKED` (`ofd_acked_at IS NULL` eng eski chekdan), blok OFD tasdiqlaridan keyin avtomatik yechiladi; `cash_registers.fm_state` → `FISCAL_DEVICE_LOCKED`
- [ ] Markirovka sotuvda: kod chek qatorida (`items[].marking_codes`), `MARKING_PRECHECK=warn` + lokal takror-kod tekshiruvi (qaror #62)
- [ ] Chek chop etish — printer matritsasi (`24-frontend-arxitekturasi.md` §6, `25-nofunksional-talablar.md` §7, 26 #139): Chrome/Edge desktop — Web Serial → WebUSB → tizim printeri (avto-aniqlash), cp866, o'zbek kirill bo'lsa raster rejimi, U+02BB → `'`; Android Chrome — WebUSB/Web Serial, BLE printerlar Web Bluetooth (klassik SPP ishlamaydi); HTTP qabul qiluvchi tarmoq printerlari (ePOS/WebPRNT); xom TCP 9100 LAN printerlar — Do'kon agenti orqali (Bosqich 5); iPhone/iPad — faqat bulut printer (CloudPRNT/SDP) yoki elektron chek (`delivery='electronic'`, 26 #112); yorliq — brauzer drayveri/PDF (raw TSPL/ZPL yo'q)
- [ ] US-M01-07 printer va tarozi sozlamasi (bir martalik, sinov cheki); tarozi EAN-13 prefiksi — `settings.weight_barcode_templates` (22 = gramm, 21 = summa)
- [ ] Bulut printer adapteri (`shared/lib/printer/cloud`) — iOS yo'li uchun majburiy, Chromium'da ixtiyoriy zahira; iOS o'rnatish ko'rsatmasi (Safari → "Bosh ekranga qo'shish") POS-01/onboarding ekraniga
- [ ] M16 kassa pul harakati, smena oxirida naqdni sanash
- [ ] M02 qaytarish; M03 chegirma (limit + PIN tasdiq)
- [ ] Offline: Dexie keshi, outbox, `/sync/push`/`/sync/pull` (`16-offline-sync.md`)
- [ ] BO-16 masofaviy tasdiq navbati (M02/M03/M08/M16 turlari) — `approval_requests` va `doc_approvals` (DB-09/DB-10); `GET /approval-requests?status=pending`, `POST /approval-requests/{id}/approve|reject`
- [ ] BO-11 qurilmalar va bekor qilish; `sale.draft_voided`, qayta chop etish auditi

**O'qiladigan spec fayllari:** `18-api-kassa.md`, `16-offline-sync.md`, `08-dizayn-tizimi.md` §5, `24-frontend-arxitekturasi.md` §6, `03-modullar-talablari.md` M01/M02/M03/M16.

**Hikoyalar:** US-M01-01, US-M01-02, US-M01-04, US-M01-05, US-M01-07, US-M02-01…03, US-M03-01, US-M09-06, US-M10-01, US-M13-03, US-M16-01…03.

**Tayyor ta'rifi:** internet o'chirilganda 2 soat savdo, keyin barcha cheklar yo'qotishsiz va takrorsiz sinxronlanadi; `16-offline-sync.md`dagi konflikt qoidalari (overselling, qarz limiti, narx muzlatish) va 48 soat zinapoyasi (QT-OFFLINE48) test bilan qoplangan; printer matritsasi qabul testi (26 #139) o'tkazilgan.

---

## Bosqich 4: qarz daftari, xarajatlar, hisobotlar, Telegram

**Maqsad:** Do'kon qog'oz qarz daftarini va xarajat qaydlarini to'liq elektron qiladi, egasi kunlik hisobotni Telegram'da oladi.

**Kirish shartlari:** Bosqich 3 "Tayyor ta'rifi" bajarilgan.

**Vazifalar:**
- [ ] M08 qarz daftari: tez qarz yozish (offline), mijoz daftari, boshlang'ich qarzlar, to'lov (eng eski qarzdan), va'da sanasi, qarzlar hisoboti
- [ ] Yetkazib beruvchiga qarz va unga to'lov (US-M08-11, US-M07-04 — `supplier_payments`, bank/naqd)
- [ ] M15 xarajatlar (+ takrorlanuvchi), sof foyda
- [ ] Bank tushumi tasdig'i (`bank_settlements`, qaror #42): 5710 dagi karta/UzQR/Click/Payme/Uzum tushumlari va inkassani bank ko'chirmasi bo'yicha 5110 ga o'tkazish + komissiya (`Dt 9430 / Kt 5710`; inkassa komissiyasi 9410; `bank_settlements.variance_amount` — faqat inkassa); `BankSettlementPostingService`, `/bank-settlements` (yaratish, `post`, `cancel`), `doc_sequences` kodi `BT`, BO-24 ekrani (`bank_settlements.manage`); `gross_amount` filial × `payment_method` bo'yicha 5710 qoldig'idan oshmaydi (`13-provodka-qoidalari.md` §2.18a, `12-db-sxema.md`, QT-M11-07)
- [ ] Bank ko'chirmasi importi: `POST /bank-settlements/imports` (1CClientBankExchange `.txt` → `bank_settlements` qoralamalari, `source='statement_import'`) va BO-24 tranzit qoldig'i `GET /bank-settlements/transit-balances` (26 #124); parser testlari — pilot buxgalterdan anonimlashtirilgan ko'chirma namunasi
- [ ] Soliq hisob-kitobi: `tax_settlements` (`ST`) — QQS hisobga olish `Dt 6410 / Kt 4410`, aylanma solig'i `Dt 9430 / Kt 6410`; soliq to'lovi `Dt 6410 / Kt 5110` (`expenses.tax_type`); `POST /tax-settlements`, `/{id}/post`, `/{id}/cancel` (`13` §2.26, §4.3)
- [ ] Qarz to'lovi: joriy qarzdan ortiq summa rad (`debt_payment_exceeds_balance`, qaror #45); yetkazib beruvchiga ortiqcha to'lov — `supplier_overpay_policy` (qaror #47); hisobdan chiqarilgan qarzga to'lov `Kt 9390`
- [ ] M12 Egasi dashboard va asosiy hisobotlar; US-M03-03 chegirmalar margin hisoboti (Could)
- [ ] M18 Telegram bot: ulash va kunlik hisobot
- [ ] Filiallar bo'yicha va jami ko'rinish (US-M14-01, US-M04-03); kam qoldiq ogohlantirishi (US-M04-02)

**O'qiladigan spec fayllari:** `03-modullar-talablari.md` M08/M12/M15/M18, `20-api-moliya-admin.md`, `13-provodka-qoidalari.md` §2.18a.

**Hikoyalar:** US-M03-03, US-M04-02, US-M04-03, US-M07-04, US-M08-01…07, US-M08-09…11, US-M11-04, US-M12-01, US-M12-02, US-M14-01, US-M15-01…03, US-M18-01…03.

**Tayyor ta'rifi:** pilot do'kon qog'oz daftarsiz bir hafta ishlaydi; bank ko'chirmasi namunasi import qilinib 5710 tranzit qoldig'i yopiladi.

---

## Bosqich 5: fiskal va e-faktura

**Maqsad:** Har bir sotuv fiskal talablarga mos chek chiqaradi, markirovkalangan tovar tekshiriladi, e-faktura oqimi (kiruvchi va chiquvchi) ishlaydi.

**Kirish shartlari:** Bosqich 4 "Tayyor ta'rifi" bajarilgan; fiskal hamkor javobi (26 #109) — faqat real fiskal adapter uchun shart, qolgan vazifalar javobsiz ham boshlanadi.

**Vazifalar:**
- [ ] **Do'kon agenti asosi** (qaror #60, `34-1c-agent.md` asosida): .NET Fx 4.8 tray-ilova, admin huquqisiz o'rnatish, qurilma ulash (`devices.kind`), `127.0.0.1` lokal API, imzoli avto-yangilanish; Authenticode OV imzosi (26 #105) — pilot tarqatishdan oldin
- [ ] **Fiskal adapterlar** `FiscalPort` ortida: (a) **Do'kon ko'prigi** — `multikassa_local` / `fiscaldrive_local` (POS → agent → FM → OFD); (b) hamkor **bulut API** — hamkorda bo'lsa (iOS yo'li, qaror #21); `FakeFiscalAdapter` + FM emulyatori CI'da; FM javobi — `fm_terminal_id`, `fm_receipt_seq`, `fiscal_sign`, `qr_url`, `fiscal_at`, `ofd_acked_at` (qaror #12); port chegarasida tiyin `int64`; qaytarish `RefundInfo` bilan; `list_unsent`/`resend_unsent`; qarz to'lovida `debt_settlement` cheki (qaror #30, #45); hamkor haqini pilot davrida biz to'laymiz (≤~13 mln so'm byudjet)
- [ ] Agentda xom TCP 9100 printer va tarozi (PLU yuklash, jonli og'irlik) imkoniyatlari (qaror #60)
- [ ] CRPT Turon (qaror #62): `MarkingPort` — qabul (M07 kirim kodlari), `verify_code`, yetkazib beruvchiga qaytarish, hisobdan chiqarish; tenant sirri `crpt_api_key`; `FakeMarkingAdapter` (GS1 parse); real adapter — Xat 2 javobidan keyin (26 #40)
- [ ] E-faktura — Faktura.uz (`EInvoicePort`, do'kon login/secret `tenant_secrets` da shifrlangan) + E-IMZO brauzerda imzolash (yagona `sign.<domen>`, prod API-KEY — 26 #118); kiruvchi faktura — poll → kirim; `risk_flag='unknown'` standart (26 #47); yetkazib beruvchiga qaytarishda qo'shimcha EHF kutish (`factura_type`, `related_einvoice_id`, 26 #115)
- [ ] **E-TTN** (qaror #63): o'z filiallari orasidagi ko'chirishda ham — `transfers` `post` → `ettn_documents` EDO operatori orqali yuboriladi; markirovkali tovar egalik o'tishida muddat tovar guruhi bo'yicha (72 soat / 3 ish kuni)
- [ ] **E-ishonchnoma** — do'kon o'z xodimiga e-faktura operatori orqali beradi (BP-01 1a; qaror #63)
- [ ] M10 ichki QQS registri, qizil faktura bo'yicha QQS krediti faqat to'lovdan keyin (US-M07-04 ikkinchi mezoni, US-M10-03 — kutilayotgan QQS krediti, BO-07/BO-10)
- [ ] M11 buxgalteriya hisobotlari (tasdiqlangan hisoblar rejasi bilan, 4910-hisob shubhali qarz zahirasi)
- [ ] Qo'lda buxgalteriya tuzatishi: `ledger_adjustments` hujjat jadvali + `ledger_entries.branch_id` (DB-12); `POST /ledger-adjustments` (bir bosqichli, darhol `posted`), `POST /ledger-adjustments/{id}/cancel`, `GET /ledger-adjustments` — faqat joriy ochiq davrda (`13-provodka-qoidalari.md` §5.1)
- [ ] Chiquvchi e-faktura (US-M01-06, BP-13/BP-03): `einvoice.create` ruxsati, `POST /api/v1/einvoices` (`direction=out`, B2B nasiya sotuvdan server avtomatik `draft`) va `POST /api/v1/einvoices/from-receipt` (BO-15 "Chek asosida e-faktura chiqarish" tugmasi); `einvoices.related_doc`, provodka yozilmaydi (`13-provodka-qoidalari.md` §2.22), `uq_einvoice_out_per_doc`

**O'qiladigan spec fayllari:** `21-integratsiyalar.md`, `13-provodka-qoidalari.md` §2.14/§2.22/§5, `18-api-kassa.md` §4.5/§12.2/§15a, `12-db-sxema.md` DB-01/DB-09/DB-10/DB-12.

**Hikoyalar:** US-M01-03, US-M01-06, US-M07-03, US-M10-03, US-M11-02, US-M11-03.

**Tayyor ta'rifi:** test muhitida chek Do'kon agenti (yoki hamkor bulut API) orqali fiskallashadi, QR `ofd.soliq.uz/check` formatida; tarmoq uzilganda FM imzolaydi, `resend`dan keyin `ofd_acked_at` yoziladi; kiruvchi e-faktura (Faktura.uz) qabul qilinib imzolanadi; ichki ko'chirish e-TTN bilan yuboriladi; markirovkali kirim kodlari CRPT bilan qabul qilinadi.

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
- [ ] AI-03 (qog'oz hujjat OCR, pilot bilan, tor qamrov; Haiku 5.5 standart, past ishonchda Sonnet 5.5; `ai.ocr_enabled` flag, `eval/ocr_uz` 100 rasm — 26 #19; rasmlar faqat `ai_cross_border_enabled` rozilikdan keyin) — BO-04 kirim avto-to'ldirish, US-M04-04 (3)-yo'l, M02 qog'oz chek; `22-ai-qatlami.md` §10 OCR quvuri, majburiy inson tasdig'i va ishonch chegarasi
- [ ] M10 davlat hisobotini solishtirish (fayl yuklash) + AI-05 tushuntirish + **5 ish kunlik** taymer, eslatmalar 1-/3-/4-ish kuni (qaror #50)
- [ ] M09 yorliq chop etish; M18 ogohlantirishlar
- [ ] US-M09-07 mijoz kartasida standart chegirma % (`counterparties.standing_discount_pct`, qaror #23); US-M09-02 narx tasdiqlash (BO-16); yaroqlilik muddati ogohlantirishi (M18)
- [ ] AI parametrlari (qaror #55): CBU kunlik kursi (`platform.fx_rates`), `POST /ai/chat` 10/daq/foydalanuvchi, 300/kun/tenant
- [ ] `message_key` uz/ru yakuniy matni (qaror #58 a)
- [ ] SMS zaxira kanali — Eskiz shartnomasi bilan (26 #45)
- [ ] Imzolangan Foydalanish shartlari `v1` sifatida yuklanadi (26 #127) — birinchi real tenantdan oldin
- [ ] **Pilot:** 5–10 do'kon, xarajat va AI sarfini o'lchash (unit-iqtisod, 26 #24)

**O'qiladigan spec fayllari:** `14-autentifikatsiya-oauth2.md` §16–18, `22-ai-qatlami.md`, `09-ai-funksiyalar.md`, `25-nofunksional-talablar.md` §11.

**Hikoyalar:** US-M09-02, US-M09-04, US-M09-07, US-M10-02, US-M10-04, US-M12-03, US-M13-08, US-M17-02…04, US-M18-04.

**Tayyor ta'rifi:** obuna lokauti haqiqiy billing webhook bilan test qilingan; AI-01/03/05/06 pilot do'konlarida ishlaydi; 5–10 pilot do'kondan xarajat/AI sarfi bo'yicha xulosa yig'ilgan.

---

## Bosqich 7: 1C integratsiyasi

**Maqsad:** pilot do'konlar ERP'dagi kunlik sotuv va boshqa hujjatlarni o'z kompyuteridagi «Бухгалтерия для Узбекистана 3.0» bazasiga bir tugma bilan, takrorsiz va tekshirilgan holda yozadi (qaror #36–#42).

**Kirish shartlari:** Bosqich 6 "Tayyor ta'rifi" bajarilgan; `33-1c-integratsiya.md` §16.1 pilot oldi testlari P-01…P-22 real bazada o'tkazilgan va `profiles/bp30_uz/*.yaml` qotirilgan; Authenticode OV kod-imzolash sertifikati olingan (qaror #38, `26-ochiq-savollar-reestri.md` #105); `agent_update` ildiz kaliti oflayn yaratilgan.

**Vazifalar:**
- [ ] DB: `onec_integration` revizioni (`33` §5), 12/14/16 dagi o'zgarishlar (§5.22), 6 ta SECURITY DEFINER funksiya, RLS CI ro'yxati
- [ ] OAuth: `onec-agent` mijozi, `/oauth/device_authorization`, device grant, `client_credentials` + `private_key_jwt`, `aud=urn:erp:onec-agent` tokeni (`33` §9.2)
- [ ] Agent API A-01…A-10, long-poll + Redis wake, lease/heartbeat/sweeper, Ed25519 vazifa imzosi va kalitlar to'plami (`33` §9)
- [ ] Do'kon agentining 1C imkoniyati (`34-1c-agent.md`, repo `agent-1c/`; asos — Bosqich 5): supervisor, x86/x64 COM worker, DPAPI, ulash, bazalarni topish, «saqlash=sinash», `33` §8.3 yozish algoritmi, `results.jsonl` outbox, imzoli avto-yangilanish
- [ ] Onboarding tekshiruvlari (`33` §2.3): `comcntr.dll` ro'yxatdan o'tmagan bo'lsa — bir martalik UAC qadami; «Разрешить списание запасов при отсутствии остатков» sozlamasi o'qiladi; metadata snapshot, `bp30_uz` profili (26 #132)
- [ ] Moslashtirish ustasi: `read_refs` keshi, auto-match, qiymat moslashtirishlari, `onec_ref_create_requests` (BO-22)
- [ ] `BatchBuilder` — `33` §6.2 barcha turlari (A-qism: `goods_receipt`, `retail_sales_report`, qoldiq preflight; B-qism: qaytarishlar, `credit_sale` + to'lovlar, `debt_payment`, ko'chirish, hisobdan chiqarish, inventarizatsiya, kassa hujjatlari, `bank_settlement` — sozlama bilan), invariantlar, preview/xesh
- [ ] Holat mashinalari (`33` §7), tayyorlik (§7.3, `16-offline-sync.md` §9 qurilma qoidasi + `outbox_state`), dispetcher, verify (§8.10)
- [ ] Revision, kech ma'lumot (`OneCChangeTracker` barcha posting xizmatlarida), bekor qilish, tuzatuvchi partiya, drift (`33` §8)
- [ ] Jadval (`on_shift_close`, `at_time`), avto-tasdiq (faqat Egasi); 13 SAQ job va 5 cron (`23-backend-arxitekturasi.md` §4.1)
- [ ] Veb API W-01…W-55, BO-22, BO-23, BO-14 «1C» qatori, hujjat ekranlarida «1C da» belgisi (`24-frontend-arxitekturasi.md` §1.1)
- [ ] Ruxsatlar (`33` §11), audit, Telegram shablonlari (§13.3), xato kodlari (§12) i18n
- [ ] Qabul testlari (`31-qabul-testlari.md` M19): §14 qabul mezonlari, GUID test vektorlari, P-20 dublikatsizlik, 7 kunlik offline navbat

**O'qiladigan spec fayllari:** `33-1c-integratsiya.md`, `34-1c-agent.md`, `01-qarorlar.md` (#36–#42), `12-db-sxema.md` §1/§4, `14-autentifikatsiya-oauth2.md` §2/§5/§6, `16-offline-sync.md` §9, `17-api-umumiy.md`, `23-backend-arxitekturasi.md`, `32-kod-qoidalari.md` (`agent-1c/`).

**Hikoyalar:** US-M19-01…18.

**Tayyor ta'rifi:** pilot do'konda bir kunlik 300+ qatorli savdo (+ kirim, qaytarish, qarz to'lovi) 1C'ga yozilib o'tkaziladi va `read_totals` 0.00 farq bilan `done`; ikkinchi «Yuborish» va yozish o'rtasidagi uzilish dublikat yaratmaydi; 7 kunlik offline'dan keyin partiyalar sana tartibida o'tadi; kech offline chek o'sha GUID'li ОРП'ni yangilaydi; yopiq 1C davri sana almashtirilmasdan `ONEC_DATE_PROHIBITED` beradi.

---

## MVP'dan keyin (tartib taxminiy)

0. **Bosqich 7 — 1C integratsiyasi** (yuqorida) — MVP'dan keyingi birinchi bosqich; keyingi 1C profillari (`ut11_uz`, `roznica30_uz`, `uk30_uz`), smena bo'yicha ОРП, narx o'zgarishi/qarzni kechish/boshlang'ich qoldiq hujjatlari — keyinroq (`33-1c-integratsiya.md` §2.2).
1. Rasmiy hisobot shakllarini XML eksport qilish va operator orqali topshirish (26 #110).
2. **Didox** — ikkinchi `EInvoicePort` adapteri (MVP'da Faktura.uz; asoschi qayta ko'rishi — 26 #167).
3. Mijozlarga SMS/Telegram qarz xabarlari (US-M08-08).
4. Android POS (Kotlin) — `28-android-pos.md` 1–4 bosqichlari (FM SDK — 26 #63).
5. Uzum to'lovi, ko'p ombor, talab bashorati (AI-09) — 2–3 oylik savdo tarixidan keyin.
6. O'z AI modelimiz (markaziy GPU server) — yig'ilgan ma'lumot va eval natijalariga qarab.
7. US-M03-02 (avtomatik chegirma qoidalari), US-M14-02 (nusxalash), US-M17-05 (to'liq eksport, birinchi pullik mijoz chiqib ketishidan oldin) — US-M08-08 (3-band) bilan birga MVP'dan keyin, tasdiqlangan (qaror #33); ochiq smena ichida kassir topshirish; bitta egasining bir nechta tenanti uchun umumiy ko'rinish; AI Batch (`submit_batch`).
8. Ko'p bank hisobi (`bank_accounts`) — hozircha yagona `5110` (qaror #49, 26 #90).
9. Ko'p yuridik shaxsli (turli STIR) tenant qo'llab-quvvatlanishi — MVP'da 1 tenant = 1 yuridik shaxs (26 #38).
10. AI-02 ovozli buyruq (26 #20), "2+1" aksiyasi (US-M03-02, 26 #145), ish haqi moduli 6710 bilan (qaror #52).

## Har bir vazifa uchun umumiy "tayyor" ta'rifi

- Spec'dagi US qabul mezonlari avtomatik test bilan qoplangan; posting o'zgarsa raqamli testlar yangilangan.
- RLS izolyatsiya testi va OpenAPI → orval generatsiyasi CI'da yashil.
- uz va ru tarjimalari bor; offline ta'siri (`16-offline-sync.md`) ko'rib chiqilgan.
- Audit jurnaliga tegishli amallar yoziladi; yangi ruxsat kodi matritsaga qo'shilgan.

## Tashqi bog'liqliklar

Javob kelmaguncha kod vaqtinchalik standart bilan yoziladi (26 Jadval B). Xatlar #130 (yuridik shaxs) dan keyin yuboriladi; har xat `letter_tracker` da (26 #71). "Ochiq savollar" o'rniga shu jadval (qaror #59 c): ilgari 1–5 bandlar — 26 #71, #42, #11/#112, qaror #49, 26 #93–#105.

| Kim | Xat / so'rov | Nima so'raladi (26 #N) | Bloklaydigan bosqich |
|---|---|---|---|
| Asoschi | — | Yuridik shaxs va imzolovchi (#130); Didox (#167); qo'shimcha kassa narxi (#168) | Bosqich 0 (xatlar) |
| Soliq qo'mitasi (DSQ) / OFD | Xat 1 | "Kredit" chek turi (#9); faqat-elektron chek (#112); VMQ-393 ikkilamchi tizim (#169); karta/UzQR integratsiyasi reyestr sharti (#170); reyestr narxi (#42) | Bosqich 5 — bloklamaydi |
| "Yangi texnologiyalar" DUK | Xat 1 q4 / alohida | E-IMZO prod API-KEY (#118) | Bosqich 5 (e-faktura prod) |
| Kiberxavfsizlik markazi | Xat 3 (ixtiyoriy) / narx so'rovi | Reyestr ekspertizasi narxi (#42) | Yo'q |
| CRPT Turon | Xat 2 | Oldindan tekshiruv, `label` formati, hisobdan chiqarish, integrator kaliti (#40) | Bosqich 5 — `verify`/`writeoff` real adapteri |
| Faktura.uz | Xat 4 | VM 830 xavf darajasi API'da (#47) | Bosqich 5 — bloklamaydi |
| Didox | Xat 5 | Partner token (#167 qarori bo'lsa) | — |
| Click / Payme / Uzum | Xat 6/7/8 | Test kredensiallari (hujjatlar ochiq — #43) | — |
| Fiskal hamkor (Multikassa / E-POS) | Xat 9 | Lokal ko'prik ruxsati, bulut rejimi, auth, sertifikatlash, test FM, narx (#109, #168); holat kodlari (#89); PAX/Sunmi FM SDK (#63) | **Bosqich 5 — real fiskal adapter (BLOK)** |
| DSQ (reyestr) | Xat 10 | O'z virtual kassamiz arizasi (#25, #42) | Yo'q (parallel) |
| CBU MUNIS / ekvayer bank | Texnik so'rov | Dinamik UzQR POS API (#49) | Bosqich 5 — dinamik UzQR |
| UzCloud | Vendor so'rovi | Shartnoma SLA, DBaaS PITR, SSE (#51) | Yo'q |
| Eskiz.uz | Shartnoma | OTP shabloni, yetkazish (#45) | Bosqich 6 (SMS zaxira) |
| Yurist | Konsultatsiya | Oferta, rozilik matni, runbook (#127) | Bosqich 6 oxiri (birinchi real tenant) |
| Tijoriy CA (SSL.com) | So'rov | OV kod-imzolash sertifikati (#105) | Do'kon agenti pilot tarqatish (Bosqich 5/7) |
| Pilot do'konlar | Pilot | OCR aniqligi (#19), biznes o'lchovlari (#24), STT (#20) | Bosqich 6 |
| Jamoa (uskuna) | Uskuna sinovi | Printer transport matritsasi (#139) | Bosqich 3 qabul testi |
| Pilot buxgalter / 1C hamkori / real БП UZ baza | Bir varaqli savol, testlar | #94–#104, #132, #133, #135–#137 | Bosqich 7 |

## Manbalar

- `spec/kod-uchun/05-mvp-chegarasi.md`, `10-umumiy-arxitektura.md`, `21-integratsiyalar.md`.
- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` — OAuth 2.0 AS+RS, admin panel, obuna lokauti.
- `spec/kod-uchun/26-ochiq-savollar-reestri.md` — Jadval B'dagi bosqich bog'lanishlari.
- `research_notes/ochiq-savollar/` — D-qarorlar va E-standartlar (Bosqich 0 spike'lari, interim standartlar).
- `spec/tarix/tekshiruv/rasmiy-xatlar.md` — rasmiy xatlar (Xat 1–10).
- `spec/kod-uchun/33-1c-integratsiya.md` §17.1 — Bosqich 7 manbasi.

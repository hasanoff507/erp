# Xavfsizlik va audit

**Maqsad:** Huquqlar katalogi, PostgreSQL Row-Level Security (RLS) mexanizmi, sirlar/kalitlar boshqaruvi, PII/AI ma'lumot minimizatsiyasi, audit jurnali, backup, xavfsizlik bazaviy darajasi va muvofiqlik (compliance) talablarini belgilash.
**Kim uchun:** Backend ishlab chiquvchilar, DevOps, huquqiy maslahatchi (ochiq savollar bo'yicha).
**Bog'liq fayllar:** `10-umumiy-arxitektura.md`, `11-malumotlar-modeli.md` (tenants, memberships, roles, role_permissions, audit_log, devices, platform_admins), `14-autentifikatsiya-oauth2.md`, `24-frontend-arxitekturasi.md` (HttpOnly cookie, CSRF, Idempotency-Key), `02-rollar-va-ssenariylar.md` (huquqlar matritsasi), `03-modullar-talablari.md` (M13, M17, M18), `06-ekranlar-umumiy.md`, `research_notes/texnik/07-hosting-lokalizatsiya-xavfsizlik.md`, `research_notes/texnik/04-arxitektura-va-stack.md`, `research_notes/texnik/tekshiruv-2026-10-14/2-efaktura-tolov-hosting.md`, `33-1c-integratsiya.md` (§5.18, §5.21, §11 — `onec.*` ruxsatlari va audit, §15 — 1C agenti xavfsizligi), `13-provodka-qoidalari.md` §2.18a (`bank_settlements`), `21-integratsiyalar.md` §9.4/§16 (karta terminali va Do'kon agenti lokal API, qaror #71).
**Holat:** joriy, 2026-10-16.

## Asosiy xulosalar

1. **Autentifikatsiya — o'z OAuth 2.0 implementatsiyamiz**: backend ham Authorization Server, ham Resource Server; to'liq protokol, saqlash, rotatsiya, bekor qilish tafsiloti **`14-autentifikatsiya-oauth2.md`da** — bu bo'lim faqat xulosa va havola. Veb (back-office+veb-kassa) — BFF naqshi, token brauzerga chiqmaydi, **HttpOnly cookie + CSRF token** (3-bo'lim) OAuth sessiyasini bildiradi; Android — public OAuth mijoz, to'g'ridan-to'g'ri Bearer access token; kassir **PIN — OAuth grant emas**, mahalliy tezkor almashish/tasdiqlash vositasi (`14-autentifikatsiya-oauth2.md` §4.3).
2. **Huquqlar — kod darajasidagi ruxsat (`permission_code`) + ixtiyoriy limit** (`role_permissions.limit_value`, `11-malumotlar-modeli.md`), 5 standart rol (Egasi, Menejer, Kassir, Omborchi, Buxgalter) uchun standart matritsa `02-rollar-va-ssenariylar.md` (6-bo'lim, K/Y/T) bilan izchil loyihalashtirilgan; standart limitlar — qaror #23 (Kassir: `discount.give` 5%, `returns.approve` 100 000 so'm, `cash.withdraw` 50 000 so'm; qolganlari limitsiz), Egasi tenant darajasida o'zgartiradi (§2.3).
3. **PostgreSQL Row-Level Security (RLS) — tenant izolyatsiyasining asosiy (DB darajasidagi) mexanizmi**; ilova filtri (SQLAlchemy `with_loader_criteria`) — ikkinchi qatlam (`23-backend-arxitekturasi.md`, 4-xulosa). Har tranzaksiya `tenant_transaction(session, tenant_id)` helper orqali ochiladi, ichida `SELECT set_config('app.tenant_id', :tid, true)` bajariladi, har jadvalda siyosat; CI'da **har jadvalda RLS yoqilganini tekshiruvchi test** majburiy (`04-arxitektura-va-stack.md`, 1-bo'lim).
4. **Platform admin** (`platform_admins`) tenant RLS'ini **chetlab o'tadi**, lekin har bir kirish `audit_log`ga majburiy yoziladi (`11-malumotlar-modeli.md`, 2-bo'lim) — bu yagona qonuniy "bypass" yo'li.
5. **AI'ga (Claude API) yuboriladigan ma'lumot cheklanadi va maskalanadi** (qaror #61): lokalizatsiya faqat biometrik/genetik/telekom ma'lumotga tegishli (ZRU-547 27-1-m.), lekin chet elga uzatish alohida qoida (ZRU-547 15-m., VMQ-415) — Anthropic (AQSh, DPF ishtirokchisi emas) uchun asos subyekt roziligi. Shuning uchun jismoniy shaxs identifikatorlarini **maskalash majburiy, tenant o'chira olmaydi**; maskalab bo'lmaydigan ma'lumot (AI-03 rasmlari) faqat tenant chegaradan tashqari uzatishga rozilik bergandan keyin (`tenants.settings.ai_cross_border_enabled=true`) yuboriladi (§5.2, `22-ai-qatlami.md` §7).
6. **Audit jurnali — o'zgarmas (append-only)**, hech qachon UPDATE/DELETE qilinmaydi; saqlash muddati uchun qonuniy minimum **topilmadi** — ichki siyosat sifatida buxgalteriya hujjatlari muddati (kamida 5 yil, hisobot yilidan keyin, "Buxgalteriya hisobi to'g'risida"gi qonun O'RQ-404, 29-modda) bilan tenglashtiriladi (`07-hosting-lokalizatsiya-xavfsizlik.md`, 3.3-bo'lim; `04-arxitektura-va-stack.md`, 7-bo'lim).
7. **Backup — o'z WAL PITR + boshqa provayderdagi nusxa** (qaror #51, #65): RPO ≤ 5 daqiqa, RTO ≤ 4 soat, chorakda bir marta staging'da to'liq restore sinovi, arxiv ≥ 5 yil; UzCloud DBaaS PITR'iga tayanilmaydi (rasmiy tasdiqlanmagan), kamida bitta nusxa boshqa provayderda (§7).
8. **Fiskal modul uchun kripto milliy standart aniq, umumiy dastur uchun majburiy kripto-algoritm standarti qonun darajasida topilmadi** — standart sanoat amaliyoti (TLS 1.2+, argon2) yetarli deb baholanadi (`07-fayl`, 3.2-bo'lim).
9. **Muvofiqlik**: (a) ЗРУ-764 bo'yicha majburiy ekspertiza/sertifikatlash bizga **tegishli emas** (faqat davlat tizimlari va KAI reyestridagi tizimlar); yagona aniq talab — o'z virtual kassamizni Davlat reyestriga kiritishda "Kiberxavfsizlik markazi" ekspertiza xulosasi (OQ-011, §9.1); (b) shaxsiy ma'lumotlar qonuni (ZRU-547/ЗРУ-666/ЗРУ-1125) bo'yicha lokalizatsiya faqat biometrik/genetik/telekom ma'lumotga tegishli, tizimning odatiy ma'lumoti bu toifaga **kirmaydi**; vakolatli organ — IIV huzuridagi Migratsiya va personallashtirish departamenti (§9.2).
10. **PCI DSS qamrovi minimal**: karta ma'lumoti hech qachon bizning tizimimizda saqlanmaydi/qayta ishlanmaydi — to'lovlar Click/Payme/bank terminali orqali, ular o'z PCI-sertifikatlangan muhitida ishlaydi (`research_notes/texnik/03-efaktura-va-tolov.md`, 2.1–2.3-bo'lim izidan, mantiqiy xulosa, manbada PCI so'zi yo'q; qabul qilingan standart — SAQ A darajasi, qaror #64). Karta rekvizitlari (`card_mask`, `rrn`, `approval_code`, `card_scheme`, `card_type`) faqat integratsiyalangan terminal natijasidan avtomatik keladi (qaror #71) — karta terminalda o'qiladi, POS/agent/server faqat natija (niqob, RRN, avtorizatsiya kodi, sxema) oladi; terminalsiz (rekvizitsiz) karta to'lovida ilovaga hech qanday karta ma'lumoti kiritilmaydi va saqlanmaydi — faqat summa va `manual_reason`; to'liq PAN/track/CVV hech qachon portdan, agent jurnalidan, serverdan yoki logdan o'tmaydi (§9.3).
11. **Obuna muddati — qattiq to'xtatish**: 24 soatlik imtiyoz tugagach tenantning barcha sessiya/refresh tokenlari `suspended` holatiga o'tadi (to'liq bekor emas — faqat `scope=sync.drain`, to'lovdan keyin tiklanadi), login rad etiladi (to'lov havolasi bundan mustasno); offline qurilma imzolangan litsenziya tokeni (`valid_until = min(grace_ends_at, issued_at + 7 kun)`) bilan serversiz ham mahalliy bloklanadi — to'liq mexanizm va fiskal oqibat izohi `14-autentifikatsiya-oauth2.md` §16–17'da.

---

## 1. Autentifikatsiya va seanslar

**To'liq protokol tafsiloti `14-autentifikatsiya-oauth2.md`da** — OAuth 2.0 AS/RS, mijozlar (BFF/Android/bot/admin), grant turlari, access/refresh token formati, imzolash kalitlari, bekor qilish/introspeksiya, tenant almashtirish, scope↔permission_code, obuna lokauti, offline litsenziya tokeni, admin panel API'lari. Bu bo'lim quyida faqat **xulosa va bu hujjat bilan izchil qoladigan** qism (CSRF, huquqlar/limit mexanizmi) ni saqlaydi.

### 1.1 Ro'yxatdan o'tish va kirish (veb, back-office) — xulosa

- Ro'yxatdan o'tish: telefon raqami → OTP tasdiqlash (Telegram bot birinchi, SMS zaxira, `14-autentifikatsiya-oauth2.md` §4.2) → do'kon nomi/faoliyat turi (US-M17-01, BO-21, `03-modullar-talablari.md` M17). STIR, OFD, e-faktura ulash keyinroq, bosqichma-bosqich.
- Kirish: telefon + parol (Egasi, Menejer, Buxgalter) — OAuth Authorization Code+PKCE orqali, BFF naqshida (`14-autentifikatsiya-oauth2.md` §2, §4.1); kassir/omborchi — mahalliy PIN (1.2-bo'lim, OAuth grant emas).
- Parol saqlash: **argon2id** (`user_credentials.password_hash`, `14-autentifikatsiya-oauth2.md` §4.1, §13). PIN — `user_credentials.pin_hash`, alohida, qisqa (4–6 raqam, qaror #54) kod, faqat shu tenant/qurilma kontekstida tekshiriladi.
- Qulflash siyosati — brute-force himoyasi va rate limitlar bilan birga `14-autentifikatsiya-oauth2.md` §12'da to'liq (5 xato / 15 daqiqa, progressiv 1→5→15→60 daqiqa, IP bo'yicha 20/soat, OTP TTL 5 daqiqa, `login_attempts` 90 kun — standart, sozlanadi, qaror #54; OWASP ASVS L2 asosida).

### 1.2 Kassir/Omborchi tezkor PIN (umumiy qurilma)

- Bir nechta xodim bitta qurilmadan (veb-kassa ham, Android POS ham) smena bo'yicha almashib foydalanishi mumkin (`02-rollar-va-ssenariylar.md`, 0-bo'lim). PIN — **OAuth grant emas**, mahalliy (offline ham) tekshiriladigan tezkor almashish/tasdiqlash vositasi; aniq ta'rifi va OAuth bilan munosabati `14-autentifikatsiya-oauth2.md` §4.3'da.
- PIN — shu bilan birga **tasdiqlash vositasi** (limitdan yuqori chegirma/qaytarish/nasiyada Menejer/Egasi PIN'i, 2.3-bo'lim).
- Qurilma bekor qilinganda unda kirgan xodimlarning PIN'i majburiy almashtiriladi (`16-offline-sync.md` §9).

### 1.3 Seanslar va tokenlar

Mijoz turlari, token formatlari, muddatlari, qurilmaga bog'lash — **to'liq `14-autentifikatsiya-oauth2.md` §2, §5–§9'da**. Qisqa xulosa:

| Mijoz | Mexanizm |
|---|---|
| Veb (back-office + veb-kassa) | BFF: OAuth access/refresh token **serverda**, brauzerga faqat **HttpOnly cookie + CSRF token** (quyida) |
| Android POS | Public OAuth mijoz, to'g'ridan-to'g'ri `Authorization: Bearer <access_token>`; access token 15 daqiqa, qurilmaga bog'langan refresh — veb-kassa bilan bir xil (sliding 14 / mutlaq 180 kun, qaror #44) |
| Telegram bot | Client Credentials (xizmat darajasida), `telegram_links` orqali foydalanuvchi/tenant konteksti |

Barcha so'rovlarda yozuvchi amallar uchun **`Idempotency-Key`** majburiy (`24-frontend-arxitekturasi.md`, 3-bo'lim) — offline qayta yuborishda takror yozuvdan himoya, xavfsizlik nuqtai nazaridan ham takror-so'rov (replay) hujumini kamaytiradi. `/sync/push` bundan mustasno: dedupe har voqea bo'yicha `sync_receipts.client_event_id` orqali (`16-offline-sync.md` §3.1); `Idempotency-Key` faqat back-office REST yozuvchi so'rovlariga tegishli.

**CSRF mexanizmi (sinxronizator-token)**: BFF cookie OAuth sessiyasiga ishora qilsa ham, brauzer hamon cookie-asosli so'rov yuboradi, shuning uchun CSRF himoyasi to'liq saqlanadi: `GET /api/v1/auth/csrf` → klient tokenni xotirada saqlaydi → yozuvchi metodlarda (`POST`/`PUT`/`PATCH`/`DELETE`, shu jumladan **`/sync/push` va `/sync/pull` — cookie-autentifikatsiyali barcha so'rovlar**) `X-CSRF-Token` header'ida yuboradi. CSRF cookie yo'q (double-submit emas) — token sessiya ID'ga bog'langan, `itsdangerous` bilan imzolangan. Noto'g'ri/eskirgan token → `403 {code: CSRF_INVALID}` → klient tokenni bir marta qayta oladi va so'rovni takrorlaydi. **Bearer access token (Android, to'g'ridan-to'g'ri API chaqiruvi) CSRF tekshiruvidan ozod** — brauzer buni avtomatik biriktirmaydi.

### 1.4 Telegram ulash

- Egasi (va ruxsat etilgan Menejer) back-office BO-20 ekranida (`06`, qaror #56) "Telegram ulash" tugmasini bosadi → bot havolasi/QR → bot ichida bir martalik kod (`link_code`, 10 daqiqa amal qiladi — qaror #54) → kod tasdiqlangach `telegram_links` (tenant_id, user_id, chat_id, linked_at) yoziladi (US-M18-01, `03-modullar-talablari.md`).
- Xodim o'chirilganda uning Telegram ulanishi ham avtomatik bekor qilinishi shart (M18, chekka holat).
- Mijozga qarz bildirishnomasi (US-M08-08) alohida kanal — Egasi/xodim botidan farqli, mijozning yozma roziligi (`counterparties.notify_consent`) bilan shartlangan.

### 1.5 Ro'yxatdan o'tishda avtomatik yaratiladigan obyektlar (tenant provisioning)

Ro'yxatdan o'tish (US-M17-01) **bitta tranzaksiyada** quyidagilarni yaratadi: `tenants`, `subscriptions` (`status=trial`, 30 kun), Egasi uchun `memberships` (barcha filialga — bo'sh `branch_ids`), 5 standart tizim roli + ularning `role_permissions` (§2.2 standart matritsa), standart filial + standart ombor + standart kassa (`cash_registers`), `doc_sequences` boshlang'ich qatorlari, standart xarajat toifalari (`expense_categories`, `27-backlog.md` seed ro'yxati bilan bir xil), `valuation_method_history(method='aveco', valid_from=go_live_date)` qatori (standart baholash usuli — AVECO). Foydalanish shartlari aksepti — signup'da (`accepted_terms_version`, `accepted_terms_at`, `accepted_terms_ip`; `14-autentifikatsiya-oauth2.md` §20 `/auth/signup`). Hisob rejasi, `units`, `plans` — **global**, tenant uchun nusxalanmaydi; MXIK katalogi — tasnif.soliq.uz orqali tashqi manba, tenant ichida saqlanmaydi.

---

## 2. Huquqlar katalogi va standart matritsa

### 2.1 Ruxsat kodlari (`permission_code`)

Har bir kod `role_permissions.permission_code` sifatida saqlanadi, zarur bo'lsa `limit_value` bilan (masalan foiz, summa). Quyidagi katalog `02-rollar-va-ssenariylar.md` (6-bo'lim, modul × K/Y/T) va `03-modullar-talablari.md` (M01–M18) asosida, granular (amal darajasida) qayta loyihalangan — bu katalog standart (qaror #28), yangi kod faqat shu jadvalga qo'shish bilan kiritiladi. **Limit birligi** `permission_code` bo'yicha qat'iy: `discount.*` va `prices.approve` — foiz, qolganlari — so'm (`12-db-sxema.md` §7.6).

| Kod | Modul | Ma'nosi | Limit |
|---|---|---|---|
| `sales.create` | M01 | Chek yaratish/yakunlash | — |
| `sales.void` | M01 | Yakunlanmagan chekni bekor qilish | — |
| `shift.open` / `shift.close` | M01 | Smena ochish/yopish (Z-hisobot) | — |
| `cash_register.manage` | M01 | Kassa/filial sozlash | — |
| `returns.create` | M02 | Qaytarish boshlash | — |
| `returns.approve` | M02 | Limitdan yuqori yoki asl cheksiz qaytarishni tasdiqlash | so'm (Kassir standarti `100000.00`, qaror #23) |
| `discount.give` | M03 | Chekka chegirma berish | foiz (Kassir standarti `5.00`, qaror #23) |
| `discount.approve` | M03 | Limitdan yuqori chegirmani PIN bilan tasdiqlash | foiz (standart — limitsiz `NULL`) |
| `discount.rule.manage` | M03 | Avtomatik chegirma/aksiya qoidasi | — |
| `stock.view` | M04 | Qoldiqni ko'rish | — |
| `stock.writeoff` | M04 | Hisobdan chiqarish | so'm (standart — limitsiz `NULL`, Egasi belgilaydi) |
| `stock.count.create` | M05 | Inventarizatsiya boshlash, sanash | — |
| `stock.count.post` | M05 | Sanash natijasini tasdiqlab balansga o'tkazish | — |
| `transfer.create` | M06 | Ko'chirish hujjati yaratish (yuborish) | — |
| `transfer.receive` | M06 | Ko'chirishni qabul qilish | — |
| `purchases.create` | M07 | Xaridnoma yaratish | — |
| `purchases.receive` | M07 | Tovarni jismoniy qabul qilish | — |
| `purchases.post` | M07 | Kirim hujjatini/ e-fakturani yakuniy o'tkazish (buxgalteriya) | — |
| `purchases.pay` | M07 | Yetkazib beruvchiga to'lov qayd etish | — |
| `purchases.return` | M07 | Yetkazib beruvchiga qaytarish | — |
| `einvoice.sign` | M07, M10 | E-IMZO bilan kiruvchi/chiquvchi e-fakturani imzolash | — |
| `debts.create` | M08 | Mijozga nasiya/qarz yozish | — |
| `debts.approve` | M08 | Kredit limitidan yuqori nasiyani tasdiqlash | so'm (standart — limitsiz `NULL`) |
| `debts.forgive` | M08 | Qarzni kechish/"undirib bo'lmaydigan" deb yopish | **faqat Egasi** (`03-modullar-talablari.md`, M08 qoidalari) |
| `debts.limit.manage` | M08 | Mijoz kredit limitini belgilash/o'zgartirish | — |
| `debts.payment.accept` | M08 | Qarz to'lovini qabul qilish | — |
| `debts.remind` | M08, AI-06 | Mijozga qarz eslatmasini yuborish (Telegram/SMS) | — |
| `prices.edit` | M09 | Narx/chegirma qoidasini o'zgartirish | — |
| `prices.approve` | M09 | Katta narx o'zgarishini tasdiqlash | foiz — ±10% (reestr #5, `limit_value` `10.00`) |
| `labels.print` | M09 | Yorliq/shtrix-kod chop etish | — |
| `catalog.manage` | M09 | Mahsulot/kategoriya/shtrix-kod (ichki kod generatsiyasi) CRUD, mahsulot importi, ombor sozlamalari (`stock-settings`) | — |
| `tax.vat.view` | M10 | Ichki QQS hisobini ko'rish | — |
| `tax.compare.review` | M10 | Davlat hisoboti bilan farqni ko'rib chiqish | — |
| `tax.correction.submit` | M10 | Davlat hisobotiga tuzatish yoki tasdiqni qayd etish (tuzatish my.soliq.uz kabinetida kiritiladi; tizimda imzosiz qayd) | — |
| `accounting.post` | M11 | Buxgalteriya yozuvini ko'rish/qo'lda tuzatish | — |
| `accounting.period.close` | M11 | Hisob davrini yopish | — |
| `stock.opening.manage` | M04, M08 | Boshlang'ich tovar qoldig'i va boshlang'ich qarz (qo'lda va `import-jobs`) | — |
| `valuation.settings.manage` | M04, M11 | FIFO/AVECO usulini almashtirish (faqat keyingi yildan) | — |
| `reports.sales.view` | M12 | Savdo/ombor hisobotlarini ko'rish | — |
| `reports.finance.view` | M12 | Moliyaviy (foyda-zarar, balans) hisobotlarni ko'rish | — |
| `reports.export` | M12 | Hisobotni Excel/PDF eksport qilish | — |
| `settings.users` | M13 | Xodim qo'shish, rol/limit tayinlash | — |
| `settings.branches` | M14 | Filial qo'shish/boshqarish | — |
| `settings.tenant` | M13, M14 | Do'kon sozlamalari, integratsiya kalitlari (Faktura.uz/CRPT), OFD qayta urinish, soliq rejimi o'zgarishi (BO-14) | **faqat Egasi** |
| `integrations.retry` | M01, M07, M10 | OFD/e-faktura/markirovka integratsiya ishini qo'lda qayta navbatga qo'yish (BO-14) | — |
| `einvoice.create` | M01, M08, M10 | Chiquvchi e-faktura qoralamasini yaratish va yuborish (B2B, chekdan keyin — BP-03/BP-13) | — |
| `expenses.create` | M15 | Xarajat yozish | — |
| `expenses.approve` | M15 | Katta/takrorlanuvchi xarajatni tasdiqlash | so'm (standart — limitsiz `NULL`) |
| `cash.deposit` / `cash.withdraw` | M16 | Kassaga pul qo'yish / kassadan olish | so'm (`cash.withdraw`: Kassir standarti `50000.00`, qaror #23) |
| `cash.count.shift` | M16 | Smena yopishda naqdni sanash | — |
| `card.manual_entry.approve` | M01, M02, M08 | Faol integratsiyalangan terminal bog'langan kassada karta to'lovi/qaytarishini terminalsiz (rekvizitsiz, `card_entry_mode='manual'`, `manual_reason` = `terminal_offline`/`terminal_error`/`unknown_result`) qabul qilishni tasdiqlash (`tenants.settings.card_manual_fallback='manager_approval'`, tasdiq turi `card_manual_entry`) va natijasi noma'lum (`unknown`) terminal tranzaksiyasini terminal chekiga qarab "o'tdi / o'tmadi" deb yopish (`resolved_by='manager'`; tasdiqlovchi hech narsa kiritmaydi — `rrn`/`card_mask`/`approval_code`/`card_type` NULL qoladi) (qaror #71). Terminal bog'lanmagan kassada (`standalone_terminal`) tasdiq kerak emas | — |
| `devices.revoke` | M13 | BO-11 «Qurilmalar» tabi: qurilmalar ro'yxatini ko'rish (`GET /devices`) va qurilmani bekor qilish (`POST /devices/{id}/revoke`) (qaror #56) | — |
| `bank_settlements.manage` | M11, M16 | Bank tushumi tasdig'i (`bank_settlements`, hujjat kodi `BT`): bank ko'chirmasi bo'yicha 5710 → 5110 o'tkazmasini yaratish, ko'rish, o'tkazish (`post`) va bekor qilish (`13-provodka-qoidalari.md` §2.18a, qaror #42) | — |
| `billing.manage` | M17 | Obuna to'lovi (oy/yil), qo'shimcha kassa, to'lovlar tarixi | **faqat Egasi** |
| `notifications.manage` | M18 | Telegram/ogohlantirish sozlamalari | — |
| `telegram.link` | M18 | O'z Telegram akkauntini ulash | — |
| `ai.chat.use` | AI-01 | AI yordamchi chatdan foydalanish | — |
| `ai.ocr.use` | AI-03 | Hujjat fotosidan AI orqali kiritish | — |
| `onec.view` | M19 | 1C integratsiyasi holati, partiyalar, preview, jurnal, solishtirishlar, «1C da» havolalari | — |
| `onec.settings.manage` | M19 | Kompyuterni ulash/uzish, bazalar, `write_enabled` (server qulfi), filial bog'lash, rejim/jadval/siyosatlar, diagnostika | — (avto-tasdiqni yoqish — **faqat Egasi**, qaror #40) |
| `onec.mapping.edit` | M19 | Moslashtirish ustasi, auto-match, tasdiqlash, qiymat moslashtirishlari, yaratish taklifi | — |
| `onec.refs.create` | M19 | 1C'da yangi ma'lumotnoma elementini yaratishni tasdiqlash (qaror #40) | — |
| `onec.export.prepare` | M19 | Kunni tayyorlash, qayta qurish, sinov ko'rinishi, solishtirishni ishga tushirish | — |
| `onec.export.approve` | M19 | Tasdiqlash va yuborish, bekor qilish, qurilmani istisno qilish | — |
| `onec.export.correct` | M19 | Xatolarni qayta yuborish, o'tkazib yuborish, `partial/mismatch` qabul qilish, yangi revision, tuzatuvchi partiya, 1C'da `ОтменаПроведения`+`ПометкаУдаления` | — |
| `platform.admin` | M17/ADM-01 | Platforma admin paneli, tenantlarga RLS'siz kirish | **faqat `platform_admins`**, har kirish audit'da |

`onec.*` kodlari — `33-1c-integratsiya.md` §11.1 bilan aynan bir xil. **1C agenti foydalanuvchi emas**: OAuth mijozi `onec-agent`, token scope **`onec.agent`** (ruxsat kodi emas, `role_permissions`ga yozilmaydi), faqat `/api/v1/onec-agent/*` yo'llariga kiradi (`aud=urn:erp:onec-agent`, `14-autentifikatsiya-oauth2.md` §2.3).

### 2.2 Standart matritsa (5 tizim roli)

Quyidagi jadval `02-rollar-va-ssenariylar.md` (6-bo'lim) dagi K/Y/T matritsasi bilan **izchil**: K→faqat `*.view`/ko'rish huquqlari, Y→yaratish kodlari, T→tasdiqlash/`*.approve`/`*.post` kodlari. "✓(limit, N)" — `role_permissions.limit_value` bilan cheklangan huquq, standart qiymati N (2.3-bo'lim). "✓(limit²)" — tenant sozlaydigan limit: huquq limit bilan ishlaydi, lekin standart qiymat hali belgilanmagan — seed'da `limit_value = NULL` (limitsiz), Egasi BO-11'da raqam qo'yadi; standart raqamlar asoschi qarorini kutadi (26 #179).

**Egasi ustuni — "barcha ruxsat" (superset)** (qaror #28): **Egasi — `platform.admin`dan tashqari barcha tenant ruxsatlarining supersetiga ega**, limitlar cheksiz (1–3 xodimli do'konda Egasi ko'pincha o'zi kassada/omborda turadi). Quyidagi jadvalning Egasi ustuni shunga mos.

| Ruxsat | Egasi | Menejer | Kassir | Omborchi | Buxgalter |
|---|---|---|---|---|---|
| `sales.create` | ✓ | ✓ | ✓ | – | – |
| `shift.open/close` | ✓ | ✓ | ✓ | – | – |
| `returns.create` | ✓ | ✓ | ✓ | – | – |
| `returns.approve` | ✓ | ✓ | ✓(limit, 100 000 so'm) | – | – |
| `discount.give` | ✓ | ✓(limit²) | ✓(limit, 5%) | – | – |
| `discount.approve` | ✓ | ✓ | – | – | – |
| `stock.count.create` | ✓ | ✓ | – | ✓ | – |
| `stock.count.post` | ✓ | ✓ | – | – | – |
| `transfer.create/receive` | ✓ | ✓ | – | ✓ | – |
| `purchases.create` | ✓ | ✓ | – | ✓ | – |
| `purchases.receive` | ✓ | – | – | ✓ | – |
| `purchases.post` | ✓ | – | – | –¹ | ✓ |
| `purchases.pay` | ✓ | – | – | – | ✓ |
| `einvoice.sign` | ✓ | – | – | – | ✓ |
| `debts.create` | ✓ | ✓ | ✓(limit²) | – | – |
| `debts.approve` | ✓ | ✓ | – | – | – |
| `debts.forgive` | ✓ | – | – | – | – |
| `debts.limit.manage` | ✓ | ✓ | – | – | – |
| `debts.payment.accept` | ✓ | ✓ | ✓ | – | ✓ |
| `debts.remind` | ✓ | ✓ | – | – | ✓ |
| `prices.edit` | ✓ | ✓ | – | – | – |
| `prices.approve` | ✓ | – | – | – | – |
| `tax.vat.view` | ✓ | – | – | – | ✓ |
| `tax.compare.review` / `tax.correction.submit` | ✓ | – | – | – | ✓ |
| `accounting.post` | ✓ | – | – | – | ✓ |
| `accounting.period.close` | ✓ | – | – | – | ✓ |
| `reports.finance.view` | ✓ | ✓ | – | – | ✓ |
| `settings.users` | ✓ | – | – | – | – |
| `settings.branches` | ✓ | – | – | – | – |
| `settings.tenant` | ✓ | – | – | – | – |
| `catalog.manage` | ✓ | ✓ | – | ✓ | – |
| `stock.opening.manage` | ✓ | ✓ | – | – | ✓ |
| `valuation.settings.manage` | ✓ | – | – | – | ✓ |
| `integrations.retry` | ✓ | ✓ | – | – | ✓ |
| `einvoice.create` | ✓ | ✓ | – | – | ✓ |
| `expenses.create` | ✓ | ✓ | – | – | ✓ (kiritish) |
| `expenses.approve` | ✓ | – | – | – | – |
| `cash.withdraw` | ✓ | ✓(limit²) | ✓(limit, 50 000 so'm) | – | – |
| `cash.deposit` | ✓ | ✓ | ✓ | – | – |
| `cash.count.shift` | ✓ | ✓ | ✓ | – | – |
| `card.manual_entry.approve` | ✓ | ✓ | – | – | – |
| `devices.revoke` | ✓ | ✓ | – | – | – |
| `billing.manage` | ✓ | – | – | – | – |
| `notifications.manage` | ✓ | – | – | – | – |
| `telegram.link` | ✓ | ✓ | – | – | – |
| `sales.void` | ✓ | ✓ | ✓ (audit) | – | – |
| `cash_register.manage` | ✓ | ✓ | – | – | – |
| `discount.rule.manage` | ✓ | ✓ | – | – | – |
| `stock.view` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `stock.writeoff` | ✓ | ✓(limit²) | – | ✓(limit²) | – |
| `purchases.return` | ✓ | ✓ | – | ✓ | ✓ |
| `labels.print` | ✓ | ✓ | – | ✓ | – |
| `reports.sales.view` | ✓ | ✓ | – | – | ✓ |
| `reports.export` | ✓ | ✓ | – | – | ✓ |
| `ai.chat.use` | ✓ | ✓ | – | – | ✓ |
| `ai.ocr.use` | ✓ | ✓ | – | ✓ | ✓ |
| `bank_settlements.manage` | ✓ | – | – | – | ✓ |
| `onec.view` | ✓ | ✓ | – | – | ✓ |
| `onec.settings.manage` | ✓ | – | – | – | – |
| `onec.mapping.edit` | ✓ | – | – | – | ✓ |
| `onec.refs.create` | ✓ | – | – | – | ✓ |
| `onec.export.prepare` | ✓ | – | – | – | ✓ |
| `onec.export.approve` | ✓ | – | – | – | ✓ |
| `onec.export.correct` | ✓ | – | – | – | ✓ |

*Izoh (1C, `33-1c-integratsiya.md` §11.2): Egasi Buxgalterga `onec.settings.manage` ni BO-11 orqali qo'shishi mumkin, lekin `onec_settings.auto_approve` (avto-tasdiq) ni yoqish/o'chirish baribir **faqat Egasi** (`OWNER_ONLY`, qaror #40).*

*² Tenant sozlaydigan limit, standart `limit_value = NULL` (limitsiz) — asoschi standart raqamni belgilaguncha (26 #179); limitdan oshganda 2.3-bo'limdagi tasdiq oqimi (`discount_over_limit`, `debt_over_limit`, `cash_withdrawal_over_limit`, `write_off_over_limit`).*

*¹ Omborchi kirimni faqat `draft` qiladi (`purchases.receive`); `purchases.post` ni Egasi BO-11'da Omborchi roliga qo'shishi mumkin (≤3 FTE do'konlar, qaror #49).*

*Izoh: kichik do'konda bir xodim bir nechta rolga ega bo'lishi mumkin (`memberships.role_ids[]`) — ruxsatlar jamlanadi, ziddiyatda yuqori huquq ustun bo'ladi (`03-modullar-talablari.md`, M13, chekka holat).*

### 2.3 Limitlar va PIN bilan tasdiqlash oqimi

1. Kassir/Omborchi amal bajaradi (masalan chegirma, qaytarish, nasiya) — kod avval `role_permissions.limit_value` bilan solishtiradi.
2. Limit ichida bo'lsa — amal darhol yakunlanadi.
3. Limitdan oshsa — `approval_requests(status='pending')` yaratiladi, hujjat `draft` da qoladi (qaror #25; yagona istisno — `price_changes` → `pending_approval`):
   - Agar Menejer/Egasi fizik yaqinda (kassada) bo'lsa — PIN kiritib **inline** tasdiqlaydi (POS-06, POS ekranida bottom-sheet, `06-ekranlar-umumiy.md`);
   - Aks holda — **BO-16 Tasdiqlash navbati** ekraniga tushadi, Menejer/Egasi PWA'dan ko'rib tasdiqlaydi/rad etadi.
4. Offline holatda: limit tekshiruvi oxirgi sinxronlangan ma'lumot asosida, Menejer PIN'i **lokal** tasdiqlaydi, server qayta tekshiradi; limitdan oshgan bo'lsa ham PIN bilan tasdiqlangan amal qabul qilinadi — `sync_exceptions(kind='approval_limit_exceeded_offline')` + `doc_approvals` + M18 xabar (`16-offline-sync.md` §5).
5. Har bir tasdiqlash/rad etish `audit_log`ga yoziladi (kim, qachon, limit, natija).

**Standart limitlar (Kassir uchun)** (qaror #23 — tavsiya #1):

| Ruxsat | Standart limit (PIN'siz) | Limitdan oshganda |
|---|---|---|
| `discount.give` (chekka chegirma) | **5%**gacha | Menejer/Egasi PIN |
| `returns.approve` (chek bilan qaytarish) | **100 000 so'm**gacha | Menejer/Egasi PIN; **chek yo'q bo'lsa — har doim PIN** (sale_line_id=NULL, `11-malumotlar-modeli.md` §6) |
| `cash.withdraw` (kassadan pul olish) | **50 000 so'm**gacha | Menejer/Egasi PIN |
| `sales.void` (chekni bekor qilish) | **Limitsiz** | — (lekin har doim audit_log'ga yoziladi) |
| Terminalsiz karta (rekvizitsiz) — faol integratsiyalangan terminal bog'langan kassada (qaror #71) | `card_manual_fallback`: `allow` — PIN'siz; `manager_approval` (sozlama yo'q bo'lsa standart) — har doim; `forbid` — mumkin emas. Siyosat faqat faol terminal bog'langan kassada qo'llanadi (`manual_reason` = `terminal_offline`/`terminal_error`/`unknown_result`); terminal bog'lanmagan kassada (`standalone_terminal`) karta — faqat summa, har doim ruxsat, tasdiqsiz | Menejer/Egasi PIN (`card_manual_entry`, `card.manual_entry.approve`); `forbid` → `CARD_MANUAL_NOT_ALLOWED` |

Bu raqamlar — **boshlang'ich standart** (hech bir raqobatchi — Loyverse, Square, BILLZ, REGOS — tayyor raqam bermaydi, hammasi "yoqish/o'chirish + PIN" modelida; bu kichik standart raqamlar kundalik mayda amallarni to'xtatmaydi, katta summani nazoratda saqlaydi). Egasi istalgan raqamni `role_permissions.limit_value` orqali tenant darajasida o'zgartira oladi (qaror #23 — tavsiya #1). **Keyin tekshiriladi**: pilotda PIN so'rovlari soni va Egalar bu raqamlarni qanchaga o'zgartirgani.

**Tasdiqlash turi (`approval_requests.kind`) → tasdiqlovchi ruxsati** (yagona manba, `18-api-kassa.md` havola qiladi):

| `kind` | Tasdiqlovchi ruxsati (`permission_code`) | Limit solishtiriladigan |
|---|---|---|
| `discount_over_limit` | `discount.approve` | foiz |
| `return_over_limit`, `return_no_receipt` | `returns.approve` | summa (`return_no_receipt` — limitsiz, har doim tasdiq kerak) |
| `debt_over_limit` | `debts.approve` | summa |
| `cash_withdrawal_over_limit` | `cash.withdraw` (so'ralgan summadan yuqori `limit_value` yoki limitsiz) | summa |
| `price_change` | `prices.approve` | foiz |
| `expense_over_limit` | `expenses.approve` | summa |
| `write_off_over_limit` | `stock.writeoff` (yuqori limit yoki limitsiz) | summa |
| `card_manual_entry` (qaror #71) | `card.manual_entry.approve` | — (limitsiz; `card_manual_fallback='manager_approval'` bo'lsa faol terminal bog'langan kassadagi har terminalsiz (rekvizitsiz) karta to'lovi/qaytarishida, shuningdek `unknown` tranzaksiyani menejer terminal chekiga qarab yopishida) |

Qo'shimcha qoida: tasdiqlovchi so'rovchining o'zi bo'la olmaydi (`approval_requests.resolved_by <> requested_by`); bitta `approval_request` bitta hujjatda bir marta ishlatiladi (`consumed`), qayta ishlatishga urinish — `APPROVAL_REQUEST_ALREADY_RESOLVED`.

### 2.4 Filialga bog'lash (branch scoping)

- `memberships.branch_ids[]` — bo'sh massiv = barcha filiallarga kirish (odatda Egasi/Buxgalter), to'ldirilgan massiv = faqat ko'rsatilgan filial(lar) (odatda Kassir/Omborchi/Menejer bitta filialga).
- Har bir API so'rovida `X-Branch-Id` header (`24-frontend-arxitekturasi.md`, 3-bo'lim) — backend bu qiymatni `memberships.branch_ids`ga qarshi tekshiradi, mos kelmasa 403.
- **Qaror: filial cheklovi — yagona qatlam, ilova darajasida** (RLS'da emas): `current_branch_scope` dependency → `BranchScopedRepository` bazaviy klassi har so'rovga `branch_id = ANY(:scope)` qo'shadi (ko'chirishda `from_branch_id`/`to_branch_id`). Har bir filialli endpoint uchun majburiy integratsion test: boshqa filial ma'lumoti → 403/bo'sh natija. Tenant izolyatsiyasi esa ikki qatlamda qoladi (3.1-bo'lim).

---

## 3. PostgreSQL Row-Level Security (RLS)

### 3.1 Tenant izolyatsiyasi mexanizmi

- Har bir jadvalda `tenant_id` ustuni majburiy (`11-malumotlar-modeli.md`, 1-bo'lim).
- Har bir DB tranzaksiya `tenant_transaction(session, tenant_id)` helper orqali ochiladi (`async_session_factory(..., autobegin=False)`); ichida `SELECT set_config('app.tenant_id', :tid, true)` bajariladi — bu **tranzaksiya-lokal** (`SET LOCAL`ga ekvivalent). `SET LOCAL ... = :param` ishlatilmaydi, chunki PostgreSQL `SET` buyrug'i parametr qabul qilmaydi (sintaksis xatosi bo'lar edi). `autobegin=False` tufayli tranzaksiyadan tashqarida `execute` xato beradi, shuning uchun tenant kontekstisiz so'rov jismonan mumkin emas; connection pool qayta ishlatilganda eski qiymat qolib ketmaydi, chunki qiymat tranzaksiya tugaganda avtomatik tozalanadi. Posting xizmati, `/sync/push` (har voqea uchun alohida `tenant_transaction`) va worker job'lari ham aynan shu helper'dan foydalanadi.
- RLS siyosati: `tenant_id = current_setting('app.tenant_id', true)::uuid` — bu qoida `10-umumiy-arxitektura.md` (2-band) va `11-malumotlar-modeli.md` (1-bo'lim) da allaqachon qaror sifatida qayd etilgan, bu hujjat uni texnik detallashtiradi.

### 3.2 Siyosat namunasi (konseptual, SQL emas kod yozish qoidasiga ko'ra bu spec hujjatida faqat tavsif)

Har jadval uchun:
- `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` (jadval egasi — superuser/owner rolidan so'rov kelsa ham siyosat qo'llanishi uchun);
- `SELECT/INSERT/UPDATE/DELETE` siyosati: `USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)`, INSERT uchun qo'shimcha `WITH CHECK` xuddi shu shartda. `current_setting(..., true)` parametr o'rnatilmagan bo'lsa xato tashlamay `NULL`/bo'sh satr qaytaradi; `NULLIF(..., '')` bo'sh satrni ham `NULL`ga aylantiradi — natijada `tenant_id = NULL` taqqoslash hech qanday qatorni qaytarmaydi (**fail-closed**: tenant konteksti yo'q bo'lsa — nol natija, xato emas).
- Ilova DB foydalanuvchisi **superuser emas** (superuser RLS'ni avtomatik chetlab o'tadi) — oddiy rol, `FORCE ROW LEVEL SECURITY` bilan birga.

### 3.3 Har jadvalda RLS borligini tekshiruvchi test

- CI'da avtomatik test: `information_schema`/`pg_class.relrowsecurity` orqali barcha biznes jadvallarini (istisno faqat `tenant_id`'siz global jadvallar — `plans`, `units`, `platform_admins`, `oauth_clients`, `signing_keys`; `tenants` — `id = app.tenant_id` siyosati, `users` — membership siyosati, `11-malumotlar-modeli.md` 1-bo'lim) ro'yxatlab, har birida `relrowsecurity = true` va kamida bitta siyosat borligini tasdiqlaydi.
- **Auth-sxema istisnosi**: `user_credentials`, `otp_challenges`, `login_attempts`, `authorization_codes`, `refresh_tokens`, `sessions`, `onec_device_authorizations` (1C agenti ulash holati — tenant tasdiqqacha noma'lum, `33-1c-integratsiya.md` §5.18) — standart `tenant_id` RLS siyosati **texnik jihatdan ishlamaydi** (login/ro'yxatdan o'tishda tenant konteksti hali yo'q, kod/token qidiruvi tenant kontekstidan oldin bo'ladi). Bu jadvallar alohida PostgreSQL `auth` sxemasida, ilova roliga to'g'ridan-to'g'ri ruxsat yo'q, kirish faqat `SECURITY DEFINER` funksiyalar orqali (`14-autentifikatsiya-oauth2.md` §19). CI testi bu ro'yxatni **alohida tekshiradi**: RLS siyosati o'rniga — (a) ilova (`app`) rolida bu jadvallarga `GRANT` yo'qligi, (b) kerakli `SECURITY DEFINER` funksiyalar mavjudligi va ichida tegishli tekshiruv borligi (1C uchun 6 funksiya: `onec_device_auth_start`, `onec_device_auth_lookup`, `onec_device_auth_approve`, `onec_device_auth_poll`, `onec_agent_credentials`, `onec_tenants_due` — `33-1c-integratsiya.md` §5.18). 18 ta `onec_*` biznes jadvali (`33-1c-integratsiya.md` §5.21) — standart `tenant_id` RLS ro'yxatida. `license_tokens` bu istisnoga **kirmaydi** — tenant/qurilma konteksti login'dan keyin mavjud, shuning uchun u standart `tenant_id` RLS ro'yxatida qoladi.
- Yangi migratsiya `tenant_id`li jadval qo'shsa, lekin RLS siyosatini unutsa — CI **qizil** bo'ladi (`04-arxitektura-va-stack.md`, 1-bo'limdagi "alohida qat'iy RLS tekshiruvi shart" tavsiyasining konkret amalga oshirilishi).
- Qo'shimcha integratsion test: ikki xil `tenant_id` bilan ma'lumot kiritilib, biri ikkinchisining yozuvini ko'ra olmasligi tekshiriladi (cross-tenant leak testi).
- **Global jadvallar siyosati**: `users` jadvalida RLS yoqilgan, lekin `tenant_id` siyosati o'rniga membership siyosati qo'llanadi: `id = app.user_id` YOKI `EXISTS (memberships WHERE user_id = users.id AND tenant_id = app.tenant_id)`. Login va tenant tanlash tenant kontekstisiz ishlaydi — buning uchun ikkita `SECURITY DEFINER` funksiya: `auth_find_user(phone)` (faqat id va hash qaytaradi) va `auth_list_memberships(user_id)`. Scheduler ham shunga o'xshash `list_active_tenant_ids()` (`SECURITY DEFINER`) funksiyasidan foydalanadi, har tenant uchun alohida job navbatga qo'yadi (`23-backend-arxitekturasi.md`, 4-bo'lim).
- **Worker/scheduler testlari**: (1) tenant A job'i B ma'lumotini ko'rmaydi; (2) `tenant_id`'siz job xato bilan tugaydi, so'rov bajarilmaydi; (3) bitta ulanishda ketma-ket ikki tenant job'i — ikkinchisida birinchi tenant konteksti qolmaganligi (`set_config(..., true)` tranzaksiya-lokal).
- `users`: tenant A kontekstida faqat A'ga membership'i bor foydalanuvchilar ko'rinadi; `auth_find_user` faqat id/hash qaytaradi.

### 3.4 Platform admin kirish yo'li va audit

- `platform_admins` jadvali alohida autentifikatsiya (M17, ADM-01) — bu foydalanuvchilar `app.tenant_id`ni **qo'yilmagan** holatda (yoki maxsus "platform" rolida, RLS bypass siyosati bilan) ishlaydi, shuning uchun istalgan tenant ma'lumotini ko'ra oladi (masalan ADM-01: tenantlar, obuna holati, AI sarfi).
- Bu bypass **faqat** ichki admin panel yo'li bo'lishi kerak; oddiy API endpoint'lari hech qachon `app.tenant_id`siz ishlamaydi.
- Har bir platform admin amali (qaysi tenant ochildi, qaysi ma'lumot ko'rildi/o'zgartirildi, masalan "obuna muddatini qo'lda uzaytirish") **majburiy** `audit_log`ga yoziladi — `action` maydonida "platform_admin_access" turi bilan belgilanadi, shunda keyinchalik kim nima ko'rgani tekshiriladi.

---

## 4. Sirlar va integratsiya kalitlari

### 4.1 Qanday sirlar bor

| Sir turi | Qamrov | Izoh |
|---|---|---|
| OFD/virtual kassa fiskal moduli kalitlari | Har `cash_registers` yozuvi uchun | Fiskal modul o'z milliy kripto standartiga ega (`07-fayl`, 3.2-bo'lim) |
| E-faktura operatori (Didox/Faktura.uz) hisob ma'lumoti | Tenant darajasida | API login/parol yoki token |
| CRPT Turon (Asl belgisi) kaliti | Tenant darajasida (`crpt_api_key`, `tenant_secrets`) | Faqat tekshiruv/qabul/qaytarish/hisobdan chiqarish uchun; chakana sotuvda kod fiskal chek ichida OFD orqali ketadi (qaror #62); integrator shartlari — tashqi javob (26 #40, OQ-025) |
| Click/Payme/Uzum/UzQR merchant sirlari (SECRET_KEY, MD5/JSON-RPC imzosi, Basic Auth) | **Tenant darajasida** (`tenant_secrets`, `kind` `click`/`payme`/`uzum`/`uzqr`; UzQR kaliti — har kassa uchun, `tenant_secrets.cash_register_id`) — sotuv to'lovlari, har do'kon o'z merchant hisobi (qaror #46) | Payme JSON-RPC, Click Prepare/Complete+MD5, Uzum JSON webhook + Basic Auth (`research_notes/texnik/tekshiruv-2026-10-14/2-efaktura-tolov-hosting.md`) |
| Platforma merchant kaliti (obuna billing, M17) | Platforma darajasida, alohida sir | Faqat M17 billing uchun; tenant sotuv puli bilan aralashmaydi (qaror #46) |
| E-IMZO sertifikat/parol | Brauzerda foydalanuvchi tomonida (E-IMZO plagin/dastur) | Server faqat imzolangan hujjatni oladi, **xususiy kalit serverga tushmaydi** (`10-umumiy-arxitektura.md`, 1-bo'lim izohi) |
| Claude API kaliti | Platforma darajasida (bitta kalit, mijoz qurilmasiga hech qachon tushmaydi) | `09-ai-funksiyalar.md`, 5-bo'lim, "Arxitektura qoidalari" |
| SMS provayder kaliti (Eskiz) | Platforma darajasida | Eskiz.uz — `OtpPort` ortidagi `EskizSmsAdapter`, faqat zaxira kanal; OTP asosiy kanali — Telegram bot (01 #34); token keshi har 25 kunda yangilanadi; shartnoma — tashqi javob (26 #45, OQ-102) |
| 1C agenti maxfiy kaliti (Ed25519) va 1C foydalanuvchi paroli | Faqat do'kon PK'sida (DPAPI `CurrentUser`) | **Serverga hech qachon kelmaydi va saqlanmaydi** — server faqat agentning ochiq kalitini (`onec_agents.public_jwk`), ulanish satri xeshini (`connect_fingerprint`) va maskalangan ko'rinishini saqlaydi (`33-1c-integratsiya.md` §15.3) |
| Do'kon agenti lokal API tokeni va fiskal lokal ko'prik siri (masalan `X-POS-Auth` SecretKey) | Faqat do'kon PK'sida (agent — DPAPI; POS — Dexie, faqat lokal token) | **Serverga chiqmaydi** (qaror #60). Lokal API himoyasi uchalasi birga: faqat `127.0.0.1`, `Origin` oq ro'yxati (`https://app.<domen>`, boshqasi → `403`), qurilmaga bog'langan lokal token (POS-16 da 6 raqamli kod bilan `POST /v1/pair`); yagona ta'rif — `21-integratsiyalar.md` §16. Xuddi shu uchlik karta terminali yo'llariga (`/v1/card/*`, qaror #71) ham qo'llanadi — alohida token yoki istisno yo'q |
| Karta terminali vendor kredensiallari (qaror #71) | `AgentEcrAdapter` drayveri — faqat do'kon PK'sida (agent, DPAPI); `CloudTerminalAdapter` — tenant darajasida (`tenant_secrets.kind='card_terminal_vendor'`, §4.2 shifrlash) | Agent drayver kredensialini serverga yubormaydi; agent terminalga faqat `card_terminals` dagi ro'yxatdagi xususiy LAN manzil (`host`/`port`) bo'yicha ulanadi — ixtiyoriy host yo'q (SSRF/LAN skanerlashga qarshi) |
| E-faktura operatori (Faktura.uz) do'kon login/secret'i | Tenant darajasida (`tenant_secrets`, shifrlangan) | §4.2 envelope encryption |
| 1C vazifa imzo kaliti (`signing_keys.purpose='onec_task'`) va agent yangilanish ildiz kaliti (`agent_update`) | Platforma darajasida | `onec_task` — `14-autentifikatsiya-oauth2.md` §6 mexanizmi (DEK/KEK, 90 kun rotatsiya); `agent_update` — oflayn saqlanadi (CI'da emas), vazifa kalitlari to'plami va yangilanish manifestini imzolaydi (`33-1c-integratsiya.md` §9.4) |

**Merchant modeli** (qaror #46): sotuv to'lovlari merchant kalitlari — tenant'niki, pul to'g'ridan-to'g'ri tenant hisobiga tushadi; platforma merchant kaliti faqat M17 billing uchun, alohida sir. Platforma faqat texnologik vositachi (O'RQ-578 14-m., to'lov xizmatiga kirmaydiganlar ro'yxati) — to'lov tashkiloti litsenziyasi kerak emas. Split/pul yig'ish (marketplace) modeliga o'tish litsenziya talabini keltirib chiqaradi — **taqiqlangan**.

### 4.2 Envelope encryption va sirlar boshqaruvi (qaror #65)

Tenant-specific integratsiya sirlari (ayniqsa Click/Payme, EDO) **shifrlangan holda** saqlanishi kerak — oddiy matn sifatida emas. UzCloud katalogida KMS va sir-ombori **yo'q** (Xavfsizlik bo'limida faqat Anti-DDoS/SIEM/ZTNA/IAM/WAF) — shuning uchun ilova darajasidagi envelope encryption va o'z sir boshqaruvi ishlatiladi (qaror #65):

1. **Ilova darajasidagi envelope encryption** (asosiy yechim): har bir sir **Data Encryption Key (DEK)** bilan AES-256-GCM orqali shifrlanadi; DEK'lar o'zi platforma darajasidagi **Key Encryption Key (KEK)** bilan shifrlanib bazada saqlanadi. **KEK va deploy sirlari**: repozitoriyda SOPS/age bilan shifrlangan fayl (MVP) yoki o'z-hosted Vault/OpenBao (K8s ichida, keyingi bosqich); deploy vaqtida muhit o'zgaruvchisi sifatida **faqat** `api`/`worker` konteyneriga uzatiladi (boshqa konteyner — `bot`, `scheduler` — kerak bo'lmasa olmaydi); rotatsiya — **yillik** (standart, sozlanadi; `key_version` ustuni orqali eski DEK'lar qayta shifrlanadi). KEK joyi Vault'ga ko'chirilsa, DEK qiymatlari o'zgarmaydi, faqat KEK saqlanadigan joy almashadi.
2. **PostgreSQL `pgcrypto`** — muqobil, lekin kalitni DB ichida saqlash xavfi (DB buzilsa kalit ham ochiladi) — faqat ikkinchi darajali himoya qatlami sifatida ko'rib chiqilishi mumkin, asosiy emas.
3. **UzCloud KMS** — mavjud emas. Paydo bo'lsa, (1)dagi KEK saqlash joyi shunga ko'chiriladi.

Har bir sir yozuvida: `tenant_id`, `kind` (masalan `click_secret`, `didox_token`), shifrlangan qiymat, `key_version` (kalit aylantirish — rotation — uchun), `rotated_at`. Kalit rotatsiyasi — KEK yillik, `oauth_clients.client_secret` yillik (standart, sozlanadi — qaror #54); qonuniy majburiyat yo'q, ichki siyosat.

---

## 5. Ma'lumotlarni himoyalash (PII va AI minimizatsiyasi)

### 5.1 Shaxsiy ma'lumot (PII) turlari

| Ma'lumot | Qayerda | Rozilik |
|---|---|---|
| Mijoz/kontragent telefon raqami, ismi | `counterparties.phone/name` | SMS/Telegram xabar faqat `notify_consent=true` bo'lsa yuboriladi (`11-malumotlar-modeli.md`, 5-bo'lim; `03-modullar-talablari.md`, M08 qoidalari: "SMS/Telegram faqat mijoz roziligi bilan") |
| Xodim telefon/ism | `users.phone/name` | Mehnat qonunchiligi doirasidagi ishlov (ZRU-547 18-m. — qonunchilikdagi majburiyat asosi); oferta matni bilan yurist tasdiqlaydi (OQ-042) |
| Telegram chat ID | `telegram_links.chat_id` | Foydalanuvchi o'zi ulaganda roziligi hisoblanadi |
| Tenant roziliklari | `terms_versions`, `tenants.accepted_terms_version` / `accepted_terms_at` / `accepted_terms_ip`, `consents(subject, purpose, version, at)` | Ro'yxatdan o'tishda oferta aktsepti; chegaradan tashqari AI uzatishga rozilik — `consents` yozuvi + `tenants.settings.ai_cross_border_enabled` (standart `false`, qaror #61) |

**Lokalizatsiya**: bu ma'lumotlarning hech biri **biometrik, genetik yoki telekom operatori foydalanuvchi ma'lumoti** toifasiga kirmaydi (ZRU-547, 27-1-modda) — shuning uchun O'zbekiston hududida saqlanishi **qonuniy majburiyat emas** (`07-fayl`, 1.1-bo'lim), lekin UzCloud'da saqlash biznes tanlovi sifatida amal qiladi (`10-umumiy-arxitektura.md`, Manbalar; `04-arxitektura-va-stack.md`, 5-bo'lim). **Chet elga uzatish** esa lokalizatsiyadan alohida qoida (ZRU-547 15-m., 27-1-m. 3-qism, VMQ-415) — §5.2.

### 5.2 Claude API'ga nima boradi, nima bormaydi

- **Boradi (minimallashtirilgan va maskalangan holda)**: AI-01 so'rovlari uchun kerakli kontekst — masalan "bugun qancha foyda" so'roviga javob uchun kod hisoblagan **agregat raqamlar** (SQL natijasi), mahsulot nomi kabi matn maydonlari (AI-05, AI-06). Jismoniy shaxsga oid maydonlar (mijoz/kontragent F.I.Sh., telefon, JSHSHIR, yakka tadbirkor STIR'i, manzil) promptdan oldin tokenga almashtiriladi ("mijoz A"; token xaritasi faqat shu so'rov davomida xotirada, saqlanmaydi), javob qaytgach kod tokenni asl qiymatga qaytaradi (`22-ai-qatlami.md` §7).
- **Maskalash majburiy, tenant o'chira olmaydi** (qaror #61): Anthropic (AQSh) VMQ-415 ro'yxatida faqat EU-US DPF ishtirokchisi bo'lsa qamraladi, Anthropic esa DPF ishtirokchisi emas — maskalanmagan shaxsga doir ma'lumotni uzatish faqat subyekt roziligi bilan mumkin (ZRU-547 15-m.). AI orqali qonunga xilof ishlov berish — MJtK 46-2-m. 2-qism (BHMning 50–100 baravari).
- **Maskalab bo'lmaydigan istisno — AI-03 OCR rasmi** (faktura/yuk xati fotosida shaxs ismi bo'lishi mumkin): tenant chegaradan tashqari uzatishga rozilik bermaguncha (`tenants.settings.ai_cross_border_enabled=false`, `consents` yozuvi yo'q) rasm yuborilmaydi — `403 AI_CONSENT_REQUIRED`. Muqobil — VMQ-415 ro'yxatidagi davlatda ishlov beradigan endpoint (`ERP_AI_PII_ROUTE`, masalan AWS Bedrock EU) — asoschi tanlovi; standart: rozilik + Anthropic API.
- **Hech qachon bormaydi**: parollar/PIN hash, to'liq karta/to'lov ma'lumoti (biz saqlamaymiz ham), E-IMZO xususiy kaliti, biometrik/genetik ma'lumot (bizda umuman yo'q).
- **Minimallashtirish qoidasi**: prompt faqat vazifaga kerakli maydonlarni o'z ichiga oladi (masalan nasiya eslatma matni uchun — mijoz ismi, summa, kun soni; butun mijoz profili emas); "kod hisoblaydi, AI tushuntiradi" tamoyili shu bilan birga xavfsizlik chegarasi ham hisoblanadi — AI hech qachon xom DB jadvalini to'liq ko'rmaydi (`09-ai-funksiyalar.md`, Arxitektura qoidalari).
- Har bir AI so'rovi `ai_requests` jadvalida loglanadi (tenant_id, user_id, feature, model, token, cost, status) — audit va xarajat nazorati uchun (`11-malumotlar-modeli.md`, 10-bo'lim).
- **Huquqiy asos** (qaror #61): maskalash (shaxsga doir ma'lumot chiqmaydi) + rozilik (oferta bandi, `consents`). Rozilik matni va maskalangan ma'lumot maqomi — yurist tasdig'i (OQ-042).

---

## 6. Audit jurnali

### 6.1 Qaysi amallar yoziladi

`audit_log` (tenant_id, user_id, action, entity, entity_id, before JSONB, after JSONB, ip, device_id, at — `11-malumotlar-modeli.md`, 10-bo'lim) quyidagilarni **majburiy** qamrab oladi:

- Huquq/rol o'zgarishi (`settings.users`), limit o'zgarishi.
- Limitdan yuqori tasdiqlash/rad etish (chegirma, qaytarish, nasiya, pul olish) — kim, qancha, natija.
- `debts.forgive` (qarzni kechish) — har doim sabab bilan (`03-modullar-talablari.md`, M08: "audit jurnaliga yoziladi").
- Narx o'zgarishi va tasdiqlash (`prices.approve`).
- Hujjat bekor qilish (teskari hujjat yaratish) — barcha modullarda.
- Davlat hisoboti tuzatish/tasdiqlash amallari (`tax.correction.submit`).
- Platform admin kirishi va amallari (3.4-bo'lim).
- Kirish/chiqish (login success/fail), parol/PIN o'zgarishi, qurilma ro'yxatdan o'tishi.
- Sir/kalit rotatsiyasi (4.2-bo'lim). Tenant'ga tegishli sir (`tenant_secrets`) — `audit_log`ga. **Platforma darajasidagi** voqealar (imzolash kaliti rotatsiyasi `signing_key_rotated`, OAuth mijoz siri rotatsiyasi) — `audit_log`ga emas: `audit_log.tenant_id NOT NULL` va RLS bilan tenantga bog'langan, shuning uchun ular strukturali JSON logga yoziladi (`event`, `purpose`, `kid`, bajaruvchi; maxfiy qiymat yo'q) va log saqlash siyosati bo'yicha saqlanadi.
- Ma'lumot eksporti (`reports.export`, tenant bo'yicha to'liq eksport, 7.3-bo'lim).
- To'lovdan oldin chek qatori/chekni bekor qilish (`sale.draft_voided`), chekni qayta chop etish (`receipt.reprinted`), qurilmani bekor qilish va PIN majburiy almashtirish.
- **OAuth/autentifikatsiya voqealari** (to'liq ro'yxat `14-autentifikatsiya-oauth2.md` §14'da): `login_success`/`login_failed`/`account_locked`, `otp_requested`/`otp_verified`/`otp_failed`, `password_changed`/`password_reset`, `pin_changed`/`pin_reset_forced`, `refresh_token_reuse_detected`, `session_revoked`/`all_sessions_revoked`, `tenant_switched`, `subscription_lockout_triggered`/`subscription_restored`; `signing_key_rotated` — strukturali log (yuqoridagi band).
- **Qo'shimcha voqealar**: `sync_drain_started`/`sync_drain_completed` (lokautdan oldingi offline cheklarni drenaj qilish, `14-autentifikatsiya-oauth2.md` §16.4), `data_export_during_restriction` (lokaut paytida to'lov-sahifa orqali eksport, `14` §16.5), `platform_admin_mfa_failed` (`14` §18.1).
- **1C integratsiyasi voqealari** (`33-1c-integratsiya.md` §11.3, `entity` — tegishli `onec_*` jadvali): `onec.agent.paired`, `onec.agent.revoked`, `onec.agent.unpaired`, `onec.agent.machine_changed`, `onec.agent.updated`; `onec.base.registered`, `onec.base.updated`, `onec.base.write_enabled_changed`, `onec.base.reassigned`, `onec.base.archived`; `onec.binding.changed`; `onec.settings.changed`, `onec.auto_approve.changed`; `onec.mapping.confirmed`, `onec.mapping.removed`, `onec.value_mapping.changed`; `onec.ref_create.approved`, `onec.ref_create.rejected`, `onec.ref_create.created`; `onec.export.prepared`, `onec.export.approved`, `onec.export.auto_approved`, `onec.export.cancelled`, `onec.export.resent`, `onec.export.item_skipped`, `onec.export.accepted`, `onec.export.revision_created`, `onec.export.correction_created`, `onec.export.devices_excluded`; `onec.item.written`, `onec.item.failed`, `onec.item.unposted_marked`; `onec.verify.mismatch`, `onec.drift.detected`; `onec.task.rejected` (xavfsizlik signali — alert, `33-1c-integratsiya.md` §15.4); `onec.diagnostics.requested`. Agent amallari `user_id`siz, `device_id` (agent qurilmasi) bilan yoziladi.
- **Karta terminali voqealari** (qaror #71, `entity` — `card_terminal_transactions` / `card_terminals` / `card_terminal_settlements`; `after`da integratsiyalangan natija uchun faqat niqob, RRN, avtorizatsiya kodi, sxema, summa — PAN yo'q): `card.purchase.approved`, `card.purchase.declined`, `card.purchase.unknown` (taymaut/aloqa uzildi), `card.void.auto` (faqat ikki holat: kassir fiskal chek chiqmagan sotuvni bekor qildi yoki `CARD_AMOUNT_MISMATCH` — avtomatik `void`; bog'lanmagan `approved` urinish avtomatik `void` qilinmaydi — `sync_exceptions(kind='card_orphan_transaction')`), `card.void.failed` (`CARD_VOID_FAILED`, sotuv bekor qilinmaydi, Egasiga M18), `card.refund`, `card.manual_entry` (terminalsiz (rekvizitsiz) karta to'lovi/qaytarishi: summa, `manual_reason`, `card_manual_fallback` qiymati, tasdiqlovchi — bo'lsa; karta rekvizitlari yo'q), `card.outcome.resolved_manual` (`unknown` tranzaksiya menejer tomonidan terminal chekiga qarab yopildi: natija `approved`/`declined`, summa, tasdiqlovchi; `rrn`/niqob yo'q), `card.settlement.mismatch` (terminal settlement jami integratsiyalangan tranzaksiyalar jami bilan mos emas), `card_terminal.created` / `card_terminal.updated` / `card_terminal.archived` (BO-12, `cash_register.manage`). Agent vazifasi (`card.settlement`, `card.status`) natijalari `user_id`siz, `device_id` (agent qurilmasi) bilan yoziladi.
- **Bank tushumi tasdig'i** (`bank_settlements`, `bank_settlements.manage`): yaratish, o'tkazish va bekor qilish (sabab bilan) — `entity='bank_settlements'`, `after`: `method`, `gross_amount`, `commission_amount`, `bank_ref`.
- **Markirovkalangan tovar offline audit voqealari**: `marking.offline_sold` (actor_user_id, device_id, code, sale_id, price_source=`cache`, created_at), `marking.offline_refused_no_price`, `marking.verify_failed` (sinxronlanishdan keyin: noto'g'ri/takroriy kod yoki CRPT xatosi — Egasi/Buxgalterga M18 ogohlantirishi bilan birga), `marking.manual_entry` (DataMatrix kodi qo'lda kiritildi — faqat online, `POST /marking-codes/verify` bilan; actor_user_id, device_id, code), `marking.precheck_failed` (`MARKING_PRECHECK=warn`da oldindan tekshiruv o'tmadi yoki CRPT javob bermadi, sotuv davom etdi — qaror #62), `marking.duplicate_rejected` (lokal takror-kod tekshiruvi) — to'liq siyosat `16-offline-sync.md` §7'da.

### 6.2 O'zgarmaslik (immutability)

- `audit_log` jadvalida ilova darajasida faqat `INSERT` — `UPDATE`/`DELETE` yo'q. DB darajasida qo'shimcha himoya: ilova DB rolidan bu jadvalga `UPDATE`/`DELETE` huquqi **olib tashlanadi** (faqat `INSERT`/`SELECT`), shunda kod xatosi ham yozuvni o'zgartira olmaydi.
- `audit_log`ning o'zi ham RLS bilan tenant bo'yicha ajratilgan (Egasi/Buxgalter faqat o'z tenantining jurnalini ko'radi); platform admin barcha tenantlar jurnalini ko'rish huquqiga ega (3.4-bo'lim).

### 6.3 Saqlash muddati

- Umumiy qonuniy minimum **topilmadi** (`07-fayl`, 3.3-bo'lim: "Audit log saqlash muddati umumiy qoida sifatida — topilmadi"; faqat KAI obyektlari uchun past ishonchli "3 oy" raqami bor, bizga tegishli emas).
- **Ichki siyosat (tavsiya)**: `audit_log` kamida **buxgalteriya hujjatlari bilan bir xil muddat — 5 yil** ("Buxgalteriya hisobi to'g'risida"gi qonun, O'RQ-404, 29-modda) saqlanadi, chunki audit yozuvlari ko'pincha moliyaviy hujjat (narx, qarz, provodka) o'zgarishini izohlaydi va soliq tekshiruvida dalil bo'lishi mumkin (`04-arxitektura-va-stack.md`, 7-bo'lim tavsiyasi asosida kengaytirildi). Bu — **qonuniy majburiyat emas, ichki qaror**.

---

## 7. Zaxira nusxalash (backup)

### 7.1 PITR, chastota, saqlash

- **O'z PITR** (qaror #65): UzCloud DBaaS sahifasida backup — "optional add-on", PITR esa faqat hujjat mundarijasida ("coming soon") — shartnomada PITR va HA yozma tasdiqlanmaguncha unga tayanilmaydi. O'zimiz WAL-arxivlash (pgBackRest yoki WAL-G → UzCloud S3 Cold) bilan PITR qilamiz; to'liq bazaviy backup kuniga 1 marta + doimiy WAL arxivi.
- **Maqsad (qaror #51)**: **RPO ≤ 5 daqiqa** (WAL PITR), **RTO ≤ 4 soat** (to'liq restore + tekshirish). Qonuniy majburiyat emas, ichki maqsad; pilot telemetriyasi bilan qayta ko'riladi.
- **Boshqa provayderdagi nusxa** (qaror #65): kamida bitta oflayn backup nusxasi UzCloud'dan tashqarida (boshqa mahalliy DC yoki sovuq arxiv) saqlanadi. Sabab — UzCloud ofertasi 4.4: to'lov kechiksa server o'chiriladi, "Suspended" holatidan 20 kun o'tgach ma'lumot qaytarib bo'lmaydigan tarzda yo'q qilinadi; shuning uchun UzCloud hisobiga avto-to'lov/oldindan to'lov va billing alerti (hisob-faktura 5-sanada, muddat +10 kun) majburiy.
- Backup arxivlari pgBackRest shifrlashi bilan (kalit — §4.2 KEK zanjiri).
- Saqlash muddati: operatsion backup **30 kun** (standart, sozlanadi), arxiv backup **kamida 5 yil** (buxgalteriya hujjat muddatiga mos — O'RQ-404, 29-modda; soliq hujjatlari alohida 3 yil, Soliq kodeksi 84-modda) — `04-arxitektura-va-stack.md`, 7-bo'lim tavsiyasi.

### 7.2 Tiklash sinovlari

- Backup'dan tiklash **har chorakda** staging muhitida to'liq restore bilan sinovdan o'tkaziladi (qaror #51).
- Sinov natijasi (sana, muvaffaqiyatli/yo'q, o'lchangan vaqt) `docs/ops/restore-log.md` ga yoziladi (operatsion jurnal, `audit_log`ning o'zi emas — infratuzilma darajasidagi jurnal).
- **Mas'ul va eskalatsiya**: sinov siklini DevOps (yoki shu vazifani bajaradigan rol) o'tkazadi, natija (sana, muvaffaqiyatli/yo'q, o'lchangan vaqt) operatsion jurnalga yoziladi; o'lchangan tiklash vaqti 7.1-bo'limdagi RTO maqsadidan (≤4 soat) oshsa — bu **insident** sifatida ko'rib chiqiladi (10-bo'lim oqimi bo'yicha).

### 7.3 Tenant bo'yicha eksport

- Har bir tenant o'z ma'lumotini **istalgan vaqtda** eksport qila oladi: Excel/PDF hisobotlar (`reports.export`, BO-09, US-M12-03) — bu `active`/`grace` holatda ishlaydi. `restricted`/`closed` holatda oddiy `reports.export` **yopiq** (US-M17-03/US-M17-05, `14-autentifikatsiya-oauth2.md` §16.1.1). Buning o'rniga lokaut paytida ma'lumot eksporti (qaror #20) **faqat** login/to'lov sahifasidagi alohida "Ma'lumotlarimni yuklab olish" yo'li orqali — parol tasdiqlash + OTP (`purpose=data_export`; Telegram birinchi, SMS zaxira — qaror #34; faqat `billing.manage` — Egasi) + tenant bo'yicha 1 marta/24 soat rate-limit + `data_export_during_restriction` audit yozuvi bilan (to'liq mexanizm `14-autentifikatsiya-oauth2.md` §16.5).
- **To'liq tenant eksporti formati** (qaror #51): ZIP — har jadval alohida CSV (UTF-8, sarlavha qatori, pul — o'nlik satr) + `manifest.json` (`schema_version`, `generated_at`, `tenant_id`, jadval → qatorlar soni) + ixtiyoriy hujjat PDF'lari. Tayyorlash ≤ 24 soat (SAQ job), yuklab olish — signed URL 24 soat, tenant uchun 1 so'rov / 24 soat (`14-autentifikatsiya-oauth2.md` §16.5); javob `{status, file_url, expires_at}` (`17-api-umumiy.md` §13, `20-api-moliya-admin.md`). Lokaut holatida — 01 #20 yo'li. Har eksport `audit_log`ga yoziladi (§6.1). Mahsulot talabi — US-M17-05.

---

## 8. Xavfsizlik bazaviy darajasi (baseline)

Bazaviy daraja — OWASP ASVS L2 (qonuniy talab emas, ichki standart; TLS, argon2, CSRF, rate-limit qarorlari bilan izchil):

| Band | Talab | Manba/izoh |
|---|---|---|
| Transport | TLS 1.2+ barcha ulanishlarda | `04-arxitektura-va-stack.md`, 7-bo'lim |
| Parol/PIN | **argon2id** heshlash (`14-autentifikatsiya-oauth2.md` §4.1) | `04-arxitektura-va-stack.md`, 7-bo'lim |
| Sessiya | HttpOnly, Secure, SameSite cookie + CSRF token | `24-frontend-arxitekturasi.md`, 3-bo'lim |
| Kirish cheklovi (rate limiting) | Redis orqali, login/API darajasida | `10-umumiy-arxitektura.md` — Redis "rate-limit" vazifasi uchun allaqachon rejalashtirilgan |
| CSP (Content Security Policy) | Qat'iy CSP: `default-src 'self'`, `frame-ancestors 'none'` (faqat HTTP sarlavhada), `style-src` — har so'rovga nonce (Radix `<style>`), agent porti konfiguratsiyadan — `24-frontend-arxitekturasi.md` §4.4 | Majburiy (qaror #57) |
| Kirish nazorati (input validation) | Pydantic v2 (backend), zod (frontend) | `10-umumiy-arxitektura.md`, `24-frontend-arxitekturasi.md` — ikkalasi ham allaqachon tanlangan |
| Dependency va sir skanerlash | CI'da `pip-audit`, `pnpm audit --audit-level=high`, `gitleaks`; `.env.example` majburiy (haqiqiy sir repozitoriyga tushmaydi) | Majburiy (qaror #57); kod sifati — `32-kod-qoidalari.md` |
| Penetratsion test | **Ikki bosqich** (qaror #23 — tavsiya #14): (1) **pilotdan oldin** — bepul avtomatik DAST skaner (masalan OWASP ZAP) + ichki OAuth/to'lov/fiskal tekshiruv ro'yxati; (2) **ommaviy sotuvdan oldin** — Celion yoki ONESEC'dan (ikkalasidan narx so'rab) OWASP ASVS L2 bo'yicha to'liq pentest (veb, API, OAuth, Android). Byudjet rezervi: **~60 mln so'm (~$5 000)** | Standart/qamrov — yuqori ishonch; narx — xalqaro ma'lumot bo'yicha baho ($1 500–7 000; aniq narx firmalar taklifidan), mahalliy firmalar (Celion, ONESEC, Toshkent) narxni ochiq bermaydi — rasmiy taklif so'ralishi kerak |
| Shifrlash (tinch holatda) | (1) S3 ga yoziladigan hujjat va fotolar — ilova darajasida shifrlanadi (SSE-C yoki mijoz tomonida AES-GCM, kalit — §4.2 KEK zanjiri); (2) backup arxivlari — pgBackRest shifrlashi; (3) DBaaS disk shifrlashi UzCloud'dan so'raladi | UzCloud faqat BaaS uchun "encrypted during transfer and storage" deydi, S3/DBaaS/VM uchun bayonot yo'q (qaror #65) |

---

## 9. Muvofiqlik (compliance)

### 9.1 ZRU-764 (Kiberxavfsizlik to'g'risida)

- 18-modda (majburiy ekspertiza) faqat davlat organlarining axborot resurslari/tizimlariga va **KAI reyestriga kiritilgan** axborot tizimlariga tegishli; 19-modda (majburiy sertifikatlash) — shu toifalarda ishlatiladigan kiberxavfsizlik *vositalariga*. KAI toifalash mezonlarini va reyestrni DXX belgilaydi (26–27-m.). Bizning tizim KAI reyestrida yo'q — **ЗРУ-764 bo'yicha majburiy ekspertiza va sertifikatlash bizga tegishli emas**, ekspertiza ixtiyoriy (DXX buyrug'i, reg. 3573, 2-band). Loyiha blokerlari ro'yxatiga kirmaydi.
- **Alohida majburiy talab**: o'z virtual kassamizni Davlat reyestriga kiritishda (OQ-011) arizaga "Kiberxavfsizlik markazi" ekspertiza xulosasi ilova qilinadi (VMQ-943, 4-ilova, 11-band; 15 ish kuni) — Bosqich 5 rejasida; narxi csec'dan so'raladi (26 #42).
- "Kiberxavfsizlik subyekti" sifatidagi umumiy majburiyatlar (insident xabari, raqamli izlarni saqlash — ЗРУ-764 16-m.) — §10.

### 9.2 Shaxsiy ma'lumotlar qonuni

- **Lokalizatsiya**: faqat fizik shaxslarning **biometrik ma'lumotlari, genetik ma'lumotlari va O'zbekiston telekom operatorlari foydalanuvchilarining ma'lumotlari** O'zbekiston hududida saqlanishi shart (ZRU-547, 27-1-modda; ЗРУ-666 bilan kiritilgan, ЗРУ-1125 (2026-03-26/27) bilan tasdiqlangan/liberallashtirilgan — `07-fayl`, 1.1-bo'lim). **tizimning odatiy ma'lumoti (mijoz ismi/telefon, savdo, ombor, buxgalteriya) bu uchta toifaga kirmaydi.**
- **Vakolatli organ** — IIV huzuridagi Migratsiya va personallashtirish departamenti (VMQ-415 3-band; pd.gov.uz).
- Agar kelajakda tizim biometrik funksiya (masalan yuz tanish bilan kirish) qo'shsa — shu qism uchun **Shaxsiy ma'lumotlar bazasini Davlat reyestrida ro'yxatdan o'tkazish** (pd.gov.uz, bildirishnoma tartibida) zarur bo'ladi (`07-fayl`, 1.2-bo'lim). Hozircha MVP'da bunday funksiya yo'q.
- **Chet elga uzatish**: VMQ-415 (29.07.2026) bilan 49 davlat "bir xil himoya" davlati sifatida tan olingan; AQSh — faqat EU-US DPF ishtirokchilari uchun. Anthropic DPF ishtirokchisi emas, shuning uchun §5.2 dagi majburiy maskalash va rozilik (`tenants.settings.ai_cross_border_enabled`, `consents`) qoidalari qo'llanadi (qaror #61). Rozilik matni — oferta (OQ-042).

### 9.3 PCI DSS

- Tizim **hech qachon** to'liq karta raqami/CVV saqlamaydi yoki qayta ishlamaydi — to'lovlar Click/Payme (JSON-RPC/REST API, merchant tokenlashtirilgan oqim) yoki bank POS-terminali orqali amalga oshadi (`research_notes/texnik/tekshiruv-2026-10-14/2-efaktura-tolov-hosting.md`, Payme/Click protokollari).
- **Integratsiyalangan karta terminali** (qaror #71): karta faqat bank terminalida (EMV/PIN — terminal va ekvayer PCI muhiti) o'qiladi; POS, Do'kon agenti va server faqat tranzaksiya natijasini oladi. Qoidalar: (a) adapter/drayver natijani `card_mask` (`^[0-9]{4}[*]+[0-9]{4}$`, birinchi 4 + oxirgi 4) ga normallashtiradi — terminal 6+4 bersa ham BIN (birinchi 6–8 raqam) faqat xotirada `platform.card_bin_rules` qidiruvi uchun ishlatiladi va saqlanmaydi; (b) `card_terminal_transactions.terminal_response` — sanitizatsiyalangan javob (PAN, track, CVV, PIN-blok, EMV kriptogramma maydonlari olib tashlanadi; adapter testi buni tekshiradi); (c) agent jurnali (DPAPI ostida) va server loglari faqat `attempt_id`, summa, holat, niqob, RRN, avtorizatsiya kodini yozadi; (d) agent lokal API (`127.0.0.1`, `Origin` oq ro'yxati, qurilmaga bog'langan lokal token) karta ma'lumotini qabul qilmaydi — faqat summa va `attempt_id`. Terminalsiz (rekvizitsiz) karta to'lovida (qaror #64) ilova hech qanday karta ma'lumotini so'ramaydi va qabul qilmaydi — API'da `card_mask`/`rrn`/`approval_code`/`card_scheme`/`card_type` berilsa `422 VALIDATION_ERROR`.
- Bu amaliyotda PCI DSS qamrovini **minimal** (odatda SAQ A darajasiga yaqin) qiladi — lekin manbada "PCI" so'zi to'g'ridan-to'g'ri tilga olinmagan, bu xulosa mantiqiy natija sifatida qabul qilingan standart (SAQ A).

---

### 9.4 Jarimalar (xavf ma'lumotnomasi)

- Soliq kodeksi 221-modda (O'RQ-1108, 2026-01-01 dan): 1-qism — chek bermasdan sotish va QR to'lovni rad etish — 5 mln so'm; 2-qism — ro'yxatdan o'tmagan kassa; 4-qism — texnik talabga mos bo'lmagan KKT yoki elektron xizmat dasturi buzilishi — 20 mln so'm. Shu sababli fiskal oqim (48 soat blok — qaror #43, lokautda sotuv to'xtashi — `14-autentifikatsiya-oauth2.md` §16.3) qat'iy saqlanadi.
- MJtK 46-2-m. 2-qism — shaxsga doir ma'lumotga AI yordamida qonunga xilof ishlov berish — BHMning 50–100 baravari (§5.2).

---

## 10. Insident javobi asoslari

Muddatlar manbali: VMQ-415 4-band (transchegaraviy uzatishda tarqalish — 24 soat xabar, 72 soat batafsil axborot), ЗРУ-764 16/22-m. (kiberinsident xabari va tergov natijasi), ZRU-547 31-m. (subyektga yozma xabar). Runbook'da eng qattiq muddat barcha shaxsga doir ma'lumot insidentlariga qo'llanadi:

1. **Aniqlash**: monitoring/alerting (anomal kirish, ko'p noto'g'ri login, RLS siyosati xatosi) — `25-nofunksional-talablar.md`, Observability bo'limiga bog'liq.
2. **Cheklash**: zarar ko'rgan hisob/tokenni bloklash, kalitlarni darhol rotatsiya qilish (4.2-bo'lim).
3. **Xabar berish** (runbook):
   - **T+0:** insident ochiladi (`incident_id`, aniqlangan vaqt UTC+5, `audit_log`ga `incident_opened`). Ishlov berish shartlari buzilgan bo'lsa, ta'sirlangan ishlov berish to'xtatiladi (ZRU-547 31-m.).
   - **≤ 24 soat:** shaxsga doir ma'lumot ta'sirlangan bo'lsa — vakolatli organga (IIV huzuridagi Migratsiya va personallashtirish departamenti, pd.gov.uz xizmati yoki pdpgovuz@gmail.com) dastlabki xabar. Transchegaraviy holat uchun majburiy (VMQ-415 4-band), ichki holat uchun ham bir xil qilinadi. Kiberinsident bo'lsa — DXX/"Kiberxavfsizlik markazi"ga (555-02-1010) xabar (ЗРУ-764 16-m.). Ta'sirlangan tenant Egasiga M18 + email.
   - **≤ 72 soat:** vakolatli organga batafsil axborot (sabab, ta'sirlangan yozuvlar soni/toifalari, bartaraf etish choralari). Tenant orqali subyektlarga yozma xabar (ZRU-547 31-m.) — matn shabloni tenantga beriladi.
   - **Tergov tugagach:** natija DXX ga yuboriladi (ЗРУ-764 22-m.). Raqamli izlar (ilova loglari, `audit_log`, infra loglari) kamida 1 yil o'chirilmaydi (ЗРУ-764 16-m.; §6.3 dagi 5 yillik siyosat qamraydi).
   - Sub-processor xabarlari: Anthropic ≤ 48 soat (DPA G.1); UzCloud — ofertada muddat yo'q, shartnomaga qo'shish so'raladi.
4. **Post-mortem**: sabab, ta'siri, tuzatish choralari yozma hujjatda (ichki), `audit_log`dan dalillar bilan.

---

## Ochiq savollar

1. **Tashqi javob kerak** — virtual kassa reyestri uchun "Kiberxavfsizlik markazi" ekspertiza xulosasi narxi va reyestrga kiritish bosqichlari, Soliq qo'mitasi / csec.uz (Xat 1, Xat 3, Xat 10) — interim: ЗРУ-764 majburiy emas (§9.1), ekspertiza Bosqich 5 rejasida, byudjetda zahira — 26 #42 (OQ-011).
2. **Tashqi javob kerak** — oferta/foydalanish shartlari matni: chegaradan tashqari AI uzatishga rozilik bandi, maskalangan ma'lumot maqomi, tenant ↔ platforma ↔ sub-processor rollari, xodim ma'lumoti asosi, yurist — interim: majburiy maskalash, `ai_cross_border_enabled=false`, `terms_versions`/`consents` saqlanadi (qaror #61); birinchi real tenantdan oldin kerak (Bosqich 6) — 26 #127 (OQ-042).
3. **Tashqi javob kerak** — UzCloud shartnoma SLA foizi va kompensatsiya, DBaaS HA/PITR/disk shifrlash, S3 SSE/versioning, UzCloud savdo bo'limi — interim: o'z WAL PITR, ilova darajasidagi shifrlash, boshqa provayderdagi nusxa, ichki maqsad 99,5% (qaror #65) — 26 #51 (OQ-043).
4. **Tashqi javob kerak** — Eskiz.uz SMS shartnomasi va OTP yetkazish tezligi, Eskiz.uz — interim: Telegram asosiy kanal (01 #34), `OtpPort` → `EskizSmsAdapter`, `ERP_ESKIZ_TEST_MODE=true` — 26 #45 (OQ-102).

## Manbalar

- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` — OAuth 2.0 AS/RS, token, obuna lokauti, offline litsenziya, admin panel (to'liq protokol tafsiloti).
- `spec/kod-uchun/10-umumiy-arxitektura.md`, `11-malumotlar-modeli.md`, `24-frontend-arxitekturasi.md`
- `spec/kod-uchun/02-rollar-va-ssenariylar.md` (huquqlar matritsasi), `03-modullar-talablari.md` (M01–M18, limit/PIN/audit talablari), `06-ekranlar-umumiy.md` (POS-01/06, BO-16 tasdiqlash oqimi), `09-ai-funksiyalar.md` (AI va ma'lumot minimizatsiyasi)
- `research_notes/texnik/04-arxitektura-va-stack.md` (RLS, sertifikatlash, backup, kripto)
- `research_notes/texnik/07-hosting-lokalizatsiya-xavfsizlik.md` (ZRU-764, shaxsiy ma'lumotlar qonuni, saqlash muddatlari, UzCloud)
- `research_notes/texnik/05-ozbek-tilidagi-ai.md` (AI ma'lumot lokalizatsiyasi)
- `research_notes/texnik/tekshiruv-2026-10-14/2-efaktura-tolov-hosting.md` (Click/Payme protokol tasdiqlari)
- `research_notes/ochiq-savollar/P4-huquq-hosting.md` (ЗРУ-764, ZRU-547/VMQ-415, buzilish xabari muddatlari, UzCloud), `P3-tolovlar-bank.md` §7.1 (O'RQ-578 14-m.), `P1-soliq-fiskal.md` (SK 221-m. jarimalari), `D-qarorlar-va-E-standartlar.md` (qarorlar #43–#59)

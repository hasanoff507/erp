# Xavfsizlik va audit

*2026-10-14 · Asos: `spec/02-arxitektura/00-umumiy-arxitektura.md`, `01-malumotlar-modeli.md` (tenants, memberships, roles, role_permissions, audit_log, devices, platform_admins), `08-frontend-arxitekturasi.md` (HttpOnly cookie, CSRF, Idempotency-Key), `spec/01-mahsulot/01-rollar-va-ssenariylar.md` (huquqlar matritsasi), `02-modullar-talablari.md` (M13, M17, M18), `04-ekranlar-va-ux.md`, `research_notes/texnik/07-hosting-lokalizatsiya-xavfsizlik.md`, `research_notes/texnik/04-arxitektura-va-stack.md`, `research_notes/texnik/tekshiruv-2026-10-14/2-efaktura-tolov-hosting.md`.*

## Asosiy xulosalar

1. **Autentifikatsiya ikki qatlamda**: telefon + SMS OTP bilan ro'yxatdan o'tish va parol/PIN bilan kirish (veb), kassa stansiyasida umumiy qurilmada tezkor PIN (4 raqam, taxmin); veb seansi **HttpOnly cookie + CSRF token** (`08-frontend-arxitekturasi.md`, 3-bo'lim — allaqachon qaror qilingan), Android POS/qurilmalar uchun **qurilma tokeni** (`devices` jadvali, `01-malumotlar-modeli.md`, 3-bo'lim).
2. **Huquqlar — kod darajasidagi ruxsat (`permission_code`) + ixtiyoriy limit** (`role_permissions.limit_value`, `01-malumotlar-modeli.md`), 5 standart rol (Egasi, Menejer, Kassir, Omborchi, Buxgalter) uchun standart matritsa `01-rollar-va-ssenariylar.md` (6-bo'lim, K/Y/T) bilan izchil loyihalashtirilgan; aniq limit summalari **tadqiqotda yo'q — taxmin**, MVP oldidan biznes-qoida sifatida sozlanadi.
3. **PostgreSQL Row-Level Security (RLS) — tenant izolyatsiyasining yagona mexanizmi**: har so'rov boshida `SET app.tenant_id`, har jadvalda siyosat; CI'da **har jadvalda RLS yoqilganini tekshiruvchi test** majburiy (`04-arxitektura-va-stack.md`, 1-bo'lim).
4. **Platform admin** (`platform_admins`) tenant RLS'ini **chetlab o'tadi**, lekin har bir kirish `audit_log`ga majburiy yoziladi (`01-malumotlar-modeli.md`, 2-bo'lim) — bu yagona qonuniy "bypass" yo'li.
5. **AI'ga (Claude API) yuboriladigan ma'lumot cheklanadi**: biometrik/genetik/telekom ma'lumot umuman yo'q va yuborilmaydi; mijoz ismi/telefon/tranzaksiya kabi oddiy shaxsiy ma'lumotni chet el API'ga yuborish **qonunan mumkin** (ZRU-547, 27-1-modda — faqat 3 toifa lokalizatsiya qilinadi), lekin minimallashtirish siyosati bilan (`research_notes/texnik/05-ozbek-tilidagi-ai.md`, 1.3-bo'lim; `spec/01-mahsulot/05-ai-funksiyalar.md`, Asosiy xulosa #8).
6. **Audit jurnali — o'zgarmas (append-only)**, hech qachon UPDATE/DELETE qilinmaydi; saqlash muddati uchun qonuniy minimum **topilmadi** — ichki siyosat sifatida buxgalteriya hujjatlari muddati (kamida 3 yil, Buxgalteriya hisobi to'g'risidagi qonun 23-modda) bilan tenglashtiriladi (`07-hosting-lokalizatsiya-xavfsizlik.md`, 3.3-bo'lim; `04-arxitektura-va-stack.md`, 7-bo'lim).
7. **Backup — UzCloud Backup-as-a-Service + DBaaS PITR**; aniq chastota/RPO/RTO raqami manbada yo'q — **taxmin** sifatida tavsiya beriladi, buxgalteriya hujjat muddatidan (3+ yil) kam bo'lmasligi shart (`07-fayl`, 2.1-bo'lim; `04-fayl`, 7-bo'lim).
8. **Fiskal modul uchun kripto milliy standart aniq, umumiy dastur uchun majburiy kripto-algoritm standarti qonun darajasida topilmadi** — standart sanoat amaliyoti (TLS 1.2+, bcrypt/argon2) yetarli deb baholanadi (`07-fayl`, 3.2-bo'lim).
9. **Kompleks muvofiqlik ikki ochiq savol bilan boshlanadi**: (a) ЗРУ-764 (Kiberxavfsizlik to'g'risida) sertifikatlash/ekspertiza talabining oddiy xususiy SaaS'ga tegishliligi aniqlanmagan — csec.uz'ga yozma so'rov tavsiya etiladi; (b) shaxsiy ma'lumotlar qonuni (ZRU-547/ЗРУ-666/ЗРУ-1125) bo'yicha lokalizatsiya faqat biometrik/genetik/telekom ma'lumotga tegishli, AIOS'ning odatiy ma'lumoti bu toifaga **kirmaydi** (`07-fayl`, 1.1 va 3.1-bo'lim).
10. **PCI DSS qamrovi minimal**: karta ma'lumoti hech qachon bizning tizimimizda saqlanmaydi/qayta ishlanmaydi — to'lovlar Click/Payme/bank terminali orqali, ular o'z PCI-sertifikatlangan muhitida ishlaydi (`research_notes/texnik/03-efaktura-va-tolov.md`, 2.1–2.3-bo'lim izidan, mantiqiy xulosa — manbada PCI so'zi yo'q, **taxmin**).

---

## 1. Autentifikatsiya va seanslar

### 1.1 Ro'yxatdan o'tish va kirish (veb, back-office)

- Ro'yxatdan o'tish: telefon raqami → SMS OTP tasdiqlash → do'kon nomi/faoliyat turi (US-M17-01, BO-21, `02-modullar-talablari.md` M17). STIR, OFD, e-faktura ulash keyinroq, bosqichma-bosqich.
- Kirish: telefon/login + parol (Egasi, Menejer, Buxgalter — back-office PWA) yoki PIN (Kassir, Omborchi — Android POS, POS-01 ekrani, `04-ekranlar-va-ux.md`).
- Parol saqlash: **bcrypt yoki argon2** hash (`users.password_hash`), aniq algoritm tanlovi arxitektura qarori — milliy kripto standarti faqat fiskal modulga tegishli, umumiy dastur uchun qonuniy majburiyat topilmadi (`07-fayl`, 3.2-bo'lim). PIN uchun `users.pin_hash` — alohida, qisqa (4-6 raqam, **taxmin**) kod, faqat shu tenant/qurilma kontekstida tekshiriladi.
- Qulflash siyosati (ketma-ket noto'g'ri urinishlardan keyin vaqtinchalik bloklash) — manbada yo'q, OWASP ASVS L2 bazaviy tavsiyasi sifatida qo'llanadi (**taxmin**, 8-bo'limga qarang).

### 1.2 Kassir/Omborchi tezkor PIN (umumiy qurilma)

- Bir nechta xodim bitta Android POS qurilmasidan smena bo'yicha almashib foydalanishi mumkin (`01-rollar-va-ssenariylar.md`, 0-bo'lim — rol birlashuvi kichik do'konda). PIN login lokal (offline) tekshiriladi, keyin serverga sinxronlanadi (POS-01 holat jadvali, `04-ekranlar-va-ux.md`).
- PIN — faqat autentifikatsiya emas, shu bilan birga **tasdiqlash vositasi** (limitdan yuqori chegirma/qaytarish/nasiyada Menejer/Egasi PIN'i, 2.3-bo'lim).

### 1.3 Seanslar

| Mijoz | Seans turi | Tafsilot |
|---|---|---|
| Veb (back-office + veb-kassa) | **HttpOnly cookie** sessiya + **CSRF token** (POST/PUT/PATCH/DELETE'da) | Qaror allaqachon `08-frontend-arxitekturasi.md` (3-bo'lim) da qabul qilingan: `withCredentials: true`, interceptor CSRF tokenini qo'shadi |
| Android POS (keyingi bosqich) | **Qurilma tokeni** (uzoq muddatli, `devices.id` bilan bog'langan) + refresh/rotatsiya | `devices` jadvali (`01-malumotlar-modeli.md`, 3-bo'lim): `last_seen_at`, `last_sync_at`, `app_version` — token shu yozuvga bog'lanadi. Refresh/rotatsiya aniq siklini (muddat, qayta chiqarish shartlari) manba bermaydi — **taxmin**: sanoat amaliyoti bo'yicha access token qisqa muddatli (masalan 15-60 daqiqa), refresh token uzoqroq (masalan 30 kun) va rotatsiya bilan |
| Telegram bot | Chat ID + bir martalik ulash kodi (1.4-bo'lim) | `telegram_links` jadvali |

Barcha so'rovlarda yozuvchi amallar uchun **`Idempotency-Key`** majburiy (`08-frontend-arxitekturasi.md`, 3-bo'lim) — offline qayta yuborishda takror yozuvdan himoya, xavfsizlik nuqtai nazaridan ham takror-so'rov (replay) hujumini kamaytiradi.

### 1.4 Telegram ulash

- Egasi (va ruxsat etilgan Menejer) back-office'da "Telegram ulash" tugmasini bosadi → bot havolasi/QR → bot ichida bir martalik kod → kod tasdiqlangach `telegram_links` (tenant_id, user_id, chat_id, linked_at) yoziladi (US-M18-01, `02-modullar-talablari.md`).
- Xodim o'chirilganda uning Telegram ulanishi ham avtomatik bekor qilinishi shart (M18, chekka holat).
- Mijozga qarz bildirishnomasi (US-M08-08) alohida kanal — Egasi/xodim botidan farqli, mijozning yozma roziligi (`counterparties.notify_consent`) bilan shartlangan.

---

## 2. Huquqlar katalogi va standart matritsa

### 2.1 Ruxsat kodlari (`permission_code`)

Har bir kod `role_permissions.permission_code` sifatida saqlanadi, zarur bo'lsa `limit_value` bilan (masalan foiz, summa). Quyidagi katalog `01-rollar-va-ssenariylar.md` (6-bo'lim, modul × K/Y/T) va `02-modullar-talablari.md` (M01–M18) asosida, granular (amal darajasida) qayta loyihalangan — **bu jadval ham o'z navbatida MVP oldidan Egasi/arxitektor bilan tasdiqlanishi tavsiya etilgan loyihaviy taxmin** (manba hujjatning o'zi shunday belgilaydi, 01-rollar-va-ssenariylar.md, 6-bo'lim izohi).

| Kod | Modul | Ma'nosi | Limit |
|---|---|---|---|
| `sales.create` | M01 | Chek yaratish/yakunlash | — |
| `sales.void` | M01 | Yakunlanmagan chekni bekor qilish | — |
| `shift.open` / `shift.close` | M01 | Smena ochish/yopish (Z-hisobot) | — |
| `cash_register.manage` | M01 | Kassa/filial sozlash | — |
| `returns.create` | M02 | Qaytarish boshlash | — |
| `returns.approve` | M02 | Limitdan yuqori yoki asl cheksiz qaytarishni tasdiqlash | summa (taxmin) |
| `discount.give` | M03 | Chekka chegirma berish | foiz/summa (taxmin) |
| `discount.approve` | M03 | Limitdan yuqori chegirmani PIN bilan tasdiqlash | foiz/summa (taxmin) |
| `discount.rule.manage` | M03 | Avtomatik chegirma/aksiya qoidasi | — |
| `stock.view` | M04 | Qoldiqni ko'rish | — |
| `stock.count.create` | M05 | Inventarizatsiya boshlash, sanash | — |
| `stock.count.post` | M05 | Sanash natijasini tasdiqlab balansga o'tkazish | — |
| `transfer.create` | M06 | Ko'chirish hujjati yaratish (yuborish) | — |
| `transfer.receive` | M06 | Ko'chirishni qabul qilish | — |
| `purchases.create` | M07 | Xaridnoma yaratish | — |
| `purchases.receive` | M07 | Tovarni jismoniy qabul qilish | — |
| `purchases.post` | M07 | Kirim hujjatini/ e-fakturani yakuniy o'tkazish (buxgalteriya) | — |
| `purchases.pay` | M07 | Yetkazib beruvchiga to'lov qayd etish | — |
| `einvoice.sign` | M07, M10 | E-IMZO bilan kiruvchi/chiquvchi e-fakturani imzolash | — |
| `debts.create` | M08 | Mijozga nasiya/qarz yozish | — |
| `debts.approve` | M08 | Kredit limitidan yuqori nasiyani tasdiqlash | summa (taxmin) |
| `debts.payment.accept` | M08 | Qarz to'lovini qabul qilish | — |
| `debts.forgive` | M08 | Qarzni kechish/"undirib bo'lmaydigan" deb yopish | **faqat Egasi** (`02-modullar-talablari.md`, M08 qoidalari) |
| `debts.limit.manage` | M08 | Mijoz kredit limitini belgilash/o'zgartirish | — |
| `prices.edit` | M09 | Narx/chegirma qoidasini o'zgartirish | — |
| `prices.approve` | M09 | Katta narx o'zgarishini tasdiqlash | foiz (taxmin) |
| `labels.print` | M09 | Yorliq/shtrix-kod chop etish | — |
| `tax.vat.view` | M10 | Ichki QQS hisobini ko'rish | — |
| `tax.compare.review` | M10 | Davlat hisoboti bilan farqni ko'rib chiqish | — |
| `tax.correction.submit` | M10 | Tuzatish/e'tiroz yuborish (E-IMZO) | — |
| `accounting.post` | M11 | Buxgalteriya yozuvini ko'rish/qo'lda tuzatish | — |
| `accounting.period.close` | M11 | Hisob davrini yopish | — |
| `reports.sales.view` | M12 | Savdo/ombor hisobotlarini ko'rish | — |
| `reports.finance.view` | M12 | Moliyaviy (foyda-zarar, balans) hisobotlarni ko'rish | — |
| `reports.export` | M12 | Hisobotni Excel/PDF eksport qilish | — |
| `settings.users` | M13 | Xodim qo'shish, rol/limit tayinlash | — |
| `settings.branches` | M14 | Filial qo'shish/boshqarish | — |
| `expenses.create` | M15 | Xarajat yozish | — |
| `expenses.approve` | M15 | Katta/takrorlanuvchi xarajatni tasdiqlash | summa (taxmin) |
| `cash.deposit` / `cash.withdraw` | M16 | Kassaga pul qo'yish / kassadan olish | summa (taxmin, `cash.withdraw`) |
| `cash.count.shift` | M16 | Smena yopishda naqdni sanash | — |
| `billing.manage` | M17 | Tarif tanlash, to'lov, obuna holati | **faqat Egasi** |
| `notifications.manage` | M18 | Telegram/ogohlantirish sozlamalari | — |
| `telegram.link` | M18 | O'z Telegram akkauntini ulash | — |
| `ai.chat.use` | AI-01 | AI yordamchi chatdan foydalanish | — |
| `ai.ocr.use` | AI-03 | Hujjat fotosidan AI orqali kiritish | — |
| `platform.admin` | M17/ADM-01 | Platforma admin paneli, tenantlarga RLS'siz kirish | **faqat `platform_admins`**, har kirish audit'da |

### 2.2 Standart matritsa (5 tizim roli)

Quyidagi jadval `01-rollar-va-ssenariylar.md` (6-bo'lim) dagi K/Y/T matritsasi bilan **izchil**: K→faqat `*.view`/ko'rish huquqlari, Y→yaratish kodlari, T→tasdiqlash/`*.approve`/`*.post` kodlari. "✓(limit)" — `role_permissions.limit_value` bilan cheklangan huquq.

| Ruxsat | Egasi | Menejer | Kassir | Omborchi | Buxgalter |
|---|---|---|---|---|---|
| `sales.create` | – | ✓ | ✓ | – | – |
| `shift.open/close` | – | ✓ | ✓ | – | – |
| `returns.create` | – | ✓ | ✓ | – | – |
| `returns.approve` | ✓ | ✓ | – | – | – |
| `discount.give` | ✓ | ✓(limit) | ✓(limit, past) | – | – |
| `discount.approve` | ✓ | ✓ | – | – | – |
| `stock.count.create` | – | ✓ | – | ✓ | – |
| `stock.count.post` | ✓ | ✓ | – | – | – |
| `transfer.create/receive` | – | ✓ | – | ✓ | – |
| `purchases.create` | – | ✓ | – | ✓ | – |
| `purchases.receive` | – | – | – | ✓ | – |
| `purchases.post` | – | – | – | – | ✓ |
| `purchases.pay` | – | – | – | – | ✓ |
| `einvoice.sign` | – | – | – | – | ✓ |
| `debts.create` | ✓ | ✓ | ✓(limit) | – | – |
| `debts.approve` | ✓ | ✓ | – | – | – |
| `debts.forgive` | ✓ | – | – | – | – |
| `debts.limit.manage` | ✓ | ✓ | – | – | – |
| `prices.edit` | ✓ | ✓ | – | – | – |
| `prices.approve` | ✓ | – | – | – | – |
| `tax.vat.view` | ✓ | – | – | – | ✓ |
| `tax.compare.review` / `tax.correction.submit` | ✓ (yakuniy) | – | – | – | ✓ |
| `accounting.post` | – | – | – | – | ✓ |
| `reports.finance.view` | ✓ | ✓ | – | – | ✓ |
| `settings.users` | ✓ | – | – | – | – |
| `settings.branches` | ✓ | – | – | – | – |
| `expenses.create` | ✓ | ✓ | – | – | ✓ (kiritish) |
| `expenses.approve` | ✓ | – | – | – | – |
| `cash.withdraw` | ✓ | ✓(limit) | ✓(limit, past) | – | – |
| `cash.deposit` | ✓ | ✓ | ✓ | – | – |
| `cash.count.shift` | – | ✓ | ✓ | – | – |
| `billing.manage` | ✓ | – | – | – | – |
| `notifications.manage` | ✓ | – | – | – | – |
| `telegram.link` | ✓ | ✓ | – | – | – |

*Izoh: kichik do'konda bir xodim bir nechta rolga ega bo'lishi mumkin (`memberships.role_ids[]`) — ruxsatlar jamlanadi, ziddiyatda yuqori huquq ustun bo'ladi (`02-modullar-talablari.md`, M13, chekka holat).*

### 2.3 Limitlar va PIN bilan tasdiqlash oqimi

1. Kassir/Omborchi amal bajaradi (masalan chegirma, qaytarish, nasiya) — kod avval `role_permissions.limit_value` bilan solishtiradi.
2. Limit ichida bo'lsa — amal darhol yakunlanadi.
3. Limitdan oshsa — amal **"kutilmoqda"** holatiga o'tadi:
   - Agar Menejer/Egasi fizik yaqinda (kassada) bo'lsa — PIN kiritib **inline** tasdiqlaydi (POS-06, POS ekranida bottom-sheet, `04-ekranlar-va-ux.md`);
   - Aks holda — **BO-16 Tasdiqlash navbati** ekraniga tushadi, Menejer/Egasi PWA'dan ko'rib tasdiqlaydi/rad etadi.
4. Offline holatda: limit tekshiruvi oxirgi sinxronlangan ma'lumot asosida, Menejer PIN'i **lokal** tasdiqlaydi, server qayta tekshiradi (konflikt — **ochiq savol**, 04-ekranlar-va-ux.md, Ochiq savol 3 bilan bog'liq emas, lekin shunga yaqin xavf sinfi).
5. Har bir tasdiqlash/rad etish `audit_log`ga yoziladi (kim, qachon, limit, natija).

Aniq limit raqamlari (masalan chegirma foizi, qaytarish/nasiya/pul olish summasi) **tadqiqotda yo'q — taxmin**, `role_permissions.limit_value` orqali tenant darajasida sozlanadigan qilib loyihalanadi (`01-rollar-va-ssenariylar.md`, Ochiq savol 2; `02-modullar-talablari.md`, Ochiq savol 1).

### 2.4 Filialga bog'lash (branch scoping)

- `memberships.branch_ids[]` — bo'sh massiv = barcha filiallarga kirish (odatda Egasi/Buxgalter), to'ldirilgan massiv = faqat ko'rsatilgan filial(lar) (odatda Kassir/Omborchi/Menejer bitta filialga).
- Har bir API so'rovida `X-Branch-Id` header (`08-frontend-arxitekturasi.md`, 3-bo'lim) — backend bu qiymatni `memberships.branch_ids`ga qarshi tekshiradi, mos kelmasa 403.
- RLS siyosatida filial darajasidagi tekshiruv **qo'shimcha WHERE shart** sifatida qo'llanadi (tenant darajasidagi RLS'dan keyin, ilova qatlamida yoki qo'shimcha siyosat bilan) — aniq amalga oshirish usuli (RLS ichida yoki ilova kodida) `09-backend-arxitekturasi.md`da hal qilinadi (**ochiq savol**, pastda).

---

## 3. PostgreSQL Row-Level Security (RLS)

### 3.1 Tenant izolyatsiyasi mexanizmi

- Har bir jadvalda `tenant_id` ustuni majburiy (`01-malumotlar-modeli.md`, 1-bo'lim).
- Har bir DB tranzaksiya/so'rov boshida backend ulanish darajasida `SET app.tenant_id = '<tenant_uuid>'` bajaradi (session yoki transaction-local parametr — `SET LOCAL` tavsiya etiladi, shunda connection pool qayta ishlatilganda eski qiymat qolib ketmaydi).
- RLS siyosati: `tenant_id = current_setting('app.tenant_id')::uuid` — bu qoida `00-umumiy-arxitektura.md` (2-band) va `01-malumotlar-modeli.md` (1-bo'lim) da allaqachon qaror sifatida qayd etilgan, bu hujjat uni texnik detallashtiradi.

### 3.2 Siyosat namunasi (konseptual, SQL emas kod yozish qoidasiga ko'ra bu spec hujjatida faqat tavsif)

Har jadval uchun:
- `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` (jadval egasi — superuser/owner rolidan so'rov kelsa ham siyosat qo'llanishi uchun);
- `SELECT/INSERT/UPDATE/DELETE` siyosati: `USING (tenant_id = current_setting('app.tenant_id', true)::uuid)`, INSERT uchun qo'shimcha `WITH CHECK` xuddi shu shartda;
- Ilova DB foydalanuvchisi **superuser emas** (superuser RLS'ni avtomatik chetlab o'tadi) — oddiy rol, `FORCE ROW LEVEL SECURITY` bilan birga.

### 3.3 Har jadvalda RLS borligini tekshiruvchi test

- CI'da avtomatik test: `information_schema`/`pg_class.relrowsecurity` orqali barcha biznes jadvallarini (platforma jadvallari — `tenants`, `plans`, `platform_admins` bundan mustasno, chunki ular tenant-kesishmaydigan) ro'yxatlab, har birida `relrowsecurity = true` va kamida bitta siyosat borligini tasdiqlaydi.
- Yangi migratsiya `tenant_id`li jadval qo'shsa, lekin RLS siyosatini unutsa — CI **qizil** bo'ladi (bu `04-arxitektura-va-stack.md`, 1-bo'limdagi "alohida qat'iy RLS tekshiruvi shart" tavsiyasining konkret amalga oshirilishi).
- Qo'shimcha integratsion test: ikki xil `tenant_id` bilan ma'lumot kiritilib, biri ikkinchisining yozuvini ko'ra olmasligi tekshiriladi (cross-tenant leak testi).

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
| CRPT Turon (Asl belgisi) integrator kaliti | Platforma darajasida (bizning integrator hisobimiz) + tenant kontekst | Integrator ro'yxatdan o'tish hali ochiq (`04-arxitektura-va-stack.md`, 10-bo'lim, band 1) |
| Click/Payme merchant sirlari (SECRET_KEY, MD5/JSON-RPC imzosi) | Tenant darajasida (har do'kon o'z merchant hisobiga ega bo'lishi mumkin) yoki platforma darajasida (agar bitta umumiy merchant orqali ishlansa — biznes qarori, ochiq savol) | `research_notes/texnik/tekshiruv-2026-10-14/2-efaktura-tolov-hosting.md` — Payme JSON-RPC, Click Prepare/Complete+MD5 |
| E-IMZO sertifikat/parol | Brauzerda foydalanuvchi tomonida (E-IMZO plagin/dastur) | Server faqat imzolangan hujjatni oladi, **xususiy kalit serverga tushmaydi** (`00-umumiy-arxitektura.md`, 1-bo'lim izohi) |
| Claude API kaliti | Platforma darajasida (bitta kalit, mijoz qurilmasiga hech qachon tushmaydi) | `05-ai-funksiyalar.md`, 5-bo'lim, "Arxitektura qoidalari" |
| SMS provayder kaliti | Platforma darajasida | Provayder tanlovi ochiq savol (`02-modullar-talablari.md`, M18 bilan bog'liq) |

### 4.2 Envelope encryption / KMS variantlari

Tenant-specific integratsiya sirlari (ayniqsa Click/Payme, EDO) **shifrlangan holda** saqlanishi kerak — oddiy matn sifatida emas. Variantlar (manbada aniq UzCloud KMS xizmati tasdiqlanmagan — **ochiq savol/taxmin**, quyida):

1. **Ilova darajasidagi envelope encryption** (tavsiya, UzCloud'da alohida KMS xizmati topilmagani sababli): har bir sir **Data Encryption Key (DEK)** bilan AES-256-GCM orqali shifrlanadi; DEK'lar o'zi platforma darajasidagi **Key Encryption Key (KEK)** bilan shifrlanib bazada saqlanadi; KEK — muhit o'zgaruvchisi/sir boshqaruv xizmatida (masalan HashiCorp Vault yoki shunga o'xshash — **taxmin**, UzCloud'da tayyor KMS borligi tasdiqlanmagan, `07-fayl`'da bu xizmat tilga olinmagan).
2. **PostgreSQL `pgcrypto`** — muqobil, lekin kalitni DB ichida saqlash xavfi (DB buzilsa kalit ham ochiladi) — faqat ikkinchi darajali himoya qatlami sifatida ko'rib chiqilishi mumkin, asosiy emas.
3. **UzCloud'da KMS-as-a-Service** — rasmiy narx/sahifa tadqiqotda topilmadi (`07-fayl`, 2.1-bo'lim faqat VM/K8s/DBaaS/S3'ni sanab o'tadi, KMS yo'q) — agar kelajakda UzCloud bu xizmatni taqdim etsa, (1)dagi KEK saqlash joyi shunga ko'chiriladi.

Har bir sir yozuvida: `tenant_id`, `kind` (masalan `click_secret`, `didox_token`), shifrlangan qiymat, `key_version` (kalit aylantirish — rotation — uchun), `rotated_at`. Kalit rotatsiyasi siklini (masalan yillik) belgilash — **ochiq savol**, qonuniy majburiyat topilmadi.

---

## 5. Ma'lumotlarni himoyalash (PII va AI minimizatsiyasi)

### 5.1 Shaxsiy ma'lumot (PII) turlari

| Ma'lumot | Qayerda | Rozilik |
|---|---|---|
| Mijoz/kontragent telefon raqami, ismi | `counterparties.phone/name` | SMS/Telegram xabar faqat `notify_consent=true` bo'lsa yuboriladi (`01-malumotlar-modeli.md`, 5-bo'lim; `02-modullar-talablari.md`, M08 qoidalari: "SMS/Telegram faqat mijoz roziligi bilan") |
| Xodim telefon/ism | `users.phone/name` | Ish shartnomasi doirasida, alohida rozilik so'ralmaydi (ichki ma'lumot, **taxmin**) |
| Telegram chat ID | `telegram_links.chat_id` | Foydalanuvchi o'zi ulaganda roziligi hisoblanadi |

**Lokalizatsiya**: bu ma'lumotlarning hech biri **biometrik, genetik yoki telekom operatori foydalanuvchi ma'lumoti** toifasiga kirmaydi (ZRU-547, 27-1-modda) — shuning uchun O'zbekiston hududida saqlanishi **qonuniy majburiyat emas** (`07-fayl`, 1.1-bo'lim), lekin UzCloud'da saqlash biznes tanlovi sifatida amal qiladi (`00-umumiy-arxitektura.md`, Manbalar; `04-arxitektura-va-stack.md`, 5-bo'lim).

### 5.2 Claude API'ga nima boradi, nima bormaydi

- **Boradi (minimallashtirilgan holda)**: AI-01 so'rovlari uchun kerakli kontekst — masalan "bugun qancha foyda" so'roviga javob uchun kod hisoblagan **agregat raqamlar** (SQL natijasi), ba'zan mijoz ismi/mahsulot nomi kabi matn maydonlari (AI-05, AI-06, AI-03). Bular biometrik/genetik/telekom emas — oddiy shaxsiy ma'lumot, chet elga yuborilishi ZRU-547 27-1-modda doirasida **qonuniy** (`05-ozbek-tilidagi-ai.md`, 1.3-bo'lim).
- **Hech qachon bormaydi**: parollar/PIN hash, to'liq karta/to'lov ma'lumoti (biz saqlamaymiz ham), E-IMZO xususiy kaliti, biometrik/genetik ma'lumot (bizda umuman yo'q).
- **Minimallashtirish qoidasi**: prompt faqat vazifaga kerakli maydonlarni o'z ichiga oladi (masalan nasiya eslatma matni uchun — mijoz ismi, summa, kun soni; butun mijoz profili emas); "kod hisoblaydi, AI tushuntiradi" tamoyili shu bilan birga xavfsizlik chegarasi ham hisoblanadi — AI hech qachon xom DB jadvalini to'liq ko'rmaydi (`05-ai-funksiyalar.md`, Arxitektura qoidalari).
- Har bir AI so'rovi `ai_requests` jadvalida loglanadi (tenant_id, user_id, feature, model, token, cost, status) — audit va xarajat nazorati uchun (`01-malumotlar-modeli.md`, 10-bo'lim).
- **Ochiq savol**: chet elga uzatish uchun ZRU-547 15-modda/27-1-moddadagi 3 shartdan (yetarli himoya davlati / standart shartnoma shartlari / xalqaro standart) qaysi birini tanlash — huquqiy ishlov talab qiladi (`07-fayl`, 1.3-bo'lim izidan, bu hujjatda birinchi marta AI kontekstida qo'llanildi).

---

## 6. Audit jurnali

### 6.1 Qaysi amallar yoziladi

`audit_log` (tenant_id, user_id, action, entity, entity_id, before JSONB, after JSONB, ip, device_id, at — `01-malumotlar-modeli.md`, 10-bo'lim) quyidagilarni **majburiy** qamrab oladi:

- Huquq/rol o'zgarishi (`settings.users`), limit o'zgarishi.
- Limitdan yuqori tasdiqlash/rad etish (chegirma, qaytarish, nasiya, pul olish) — kim, qancha, natija.
- `debts.forgive` (qarzni kechish) — har doim sabab bilan (`02-modullar-talablari.md`, M08: "audit jurnaliga yoziladi").
- Narx o'zgarishi va tasdiqlash (`prices.approve`).
- Hujjat bekor qilish (teskari hujjat yaratish) — barcha modullarda.
- Davlat hisoboti tuzatish/tasdiqlash amallari (`tax.correction.submit`).
- Platform admin kirishi va amallari (3.4-bo'lim).
- Kirish/chiqish (login success/fail), parol/PIN o'zgarishi, qurilma ro'yxatdan o'tishi.
- Sir/kalit rotatsiyasi (4.2-bo'lim).
- Ma'lumot eksporti (`reports.export`, tenant bo'yicha to'liq eksport, 7.3-bo'lim).

### 6.2 O'zgarmaslik (immutability)

- `audit_log` jadvalida ilova darajasida faqat `INSERT` — `UPDATE`/`DELETE` yo'q. DB darajasida qo'shimcha himoya: ilova DB rolidan bu jadvalga `UPDATE`/`DELETE` huquqi **olib tashlanadi** (faqat `INSERT`/`SELECT`), shunda kod xatosi ham yozuvni o'zgartira olmaydi.
- `audit_log`ning o'zi ham RLS bilan tenant bo'yicha ajratilgan (Egasi/Buxgalter faqat o'z tenantining jurnalini ko'radi); platform admin barcha tenantlar jurnalini ko'rish huquqiga ega (3.4-bo'lim).

### 6.3 Saqlash muddati

- Umumiy qonuniy minimum **topilmadi** (`07-fayl`, 3.3-bo'lim: "Audit log saqlash muddati umumiy qoida sifatida — topilmadi"; faqat KAI obyektlari uchun past ishonchli "3 oy" raqami bor, bizga tegishli emas).
- **Ichki siyosat (tavsiya)**: `audit_log` kamida **buxgalteriya hujjatlari bilan bir xil muddat — 3 yil** saqlanadi, chunki audit yozuvlari ko'pincha moliyaviy hujjat (narx, qarz, provodka) o'zgarishini izohlaydi va soliq tekshiruvida dalil bo'lishi mumkin (`04-arxitektura-va-stack.md`, 7-bo'lim tavsiyasi asosida kengaytirildi). Bu — **qonuniy majburiyat emas, ichki qaror**.

---

## 7. Zaxira nusxalash (backup)

### 7.1 PITR, chastota, saqlash

- UzCloud DBaaS — HA klaster + **avtomatik backup** + **PITR (Point-in-Time Recovery)** imkoniyati (`07-fayl`, 2.1-bo'lim; `04-arxitektura-va-stack.md`, 8-bo'lim jadvali).
- Aniq backup chastotasi (kunlikmi, soatlikmi) va RPO/RTO raqami **rasmiy sahifada topilmadi** — **taxmin tavsiya**: operatsion backup kuniga 1 marta to'liq + doimiy WAL-asosidagi PITR (RPO — bir necha daqiqa, **taxmin**).
- Saqlash muddati: operatsion backup **30 kun** (**taxmin**), arxiv backup **kamida 3 yil** (buxgalteriya hujjat muddatiga mos, ba'zi soliq holatlarida 13 yilgacha) — `04-arxitektura-va-stack.md`, 7-bo'lim tavsiyasi.

### 7.2 Tiklash sinovlari

- Backup'dan tiklash muntazam **sinovdan o'tkazilishi** kerak (masalan choraklik, staging muhitida to'liq restore) — bu amaliyot manbada yo'q, OWASP/sanoat amaliyoti sifatida **taxmin** qo'shiladi (8-bo'limga qarang).
- Sinov natijasi (muvaffaqiyatli/vaqt) ichki ravishda qayd etiladi (operatsion jurnal, `audit_log`ning o'zi emas — bu infratuzilma darajasidagi jurnal).

### 7.3 Tenant bo'yicha eksport

- Har bir tenant o'z ma'lumotini **istalgan vaqtda** eksport qila oladi: Excel/PDF hisobotlar (`reports.export`, BO-09, US-M12-03) — bu allaqachon mahsulot talabi sifatida mavjud va obuna to'xtagan taqdirda ham saqlanadi (US-M17-03: "Ma'lumotlarni eksport qilish huquqi har doim saqlanadi").
- To'liq tenant ma'lumotlar bazasi eksporti (masalan tenant tizimdan chiqib ketganda) — alohida, kattaroq operatsiya (platform admin orqali, audit bilan) — **ochiq savol**: aniq format/SLA belgilanmagan.

---

## 8. Xavfsizlik bazaviy darajasi (baseline)

Manbada aniq "OWASP ASVS L2" talabi tilga olinmagan — quyidagilar sanoat standart amaliyoti sifatida **tavsiya** qilinadi (**taxmin**, lekin loyihaning boshqa qarorlari — TLS, bcrypt/argon2, CSRF, rate-limit — bilan izchil):

| Band | Talab | Manba/izoh |
|---|---|---|
| Transport | TLS 1.2+ barcha ulanishlarda | `04-arxitektura-va-stack.md`, 7-bo'lim |
| Parol/PIN | bcrypt/argon2 heshlash | `04-arxitektura-va-stack.md`, 7-bo'lim |
| Sessiya | HttpOnly, Secure, SameSite cookie + CSRF token | `08-frontend-arxitekturasi.md`, 3-bo'lim (qaror allaqachon qabul qilingan) |
| Kirish cheklovi (rate limiting) | Redis orqali, login/API darajasida | `00-umumiy-arxitektura.md` — Redis "rate-limit" vazifasi uchun allaqachon rejalashtirilgan |
| CSP (Content Security Policy) | Veb frontendda standart sarlavhalar | **Taxmin** — frontend hujjatida alohida tilga olinmagan, bazaviy amaliyot sifatida qo'shiladi |
| Kirish nazorati (input validation) | Pydantic v2 (backend), zod (frontend) | `00-umumiy-arxitektura.md`, `08-frontend-arxitekturasi.md` — ikkalasi ham allaqachon tanlangan |
| Dependency scanning | CI'da avtomatik (masalan `pip-audit`/`npm audit` darajasidagi tekshiruv) | **Taxmin** — manbada yo'q, CI jarayoniga qo'shiladigan tavsiya |
| Penetratsion test | Ishga tushirishdan oldin kamida bir marta mustaqil pentest | **Taxmin** — manbada yo'q, lekin davlat tizimlariga (OFD, soliq) ulanuvchi mahsulot uchun oqilona ehtiyot chorasi |
| Shifrlash (tinch holatda) | DBaaS/S3 darajasidagi shifrlash (UzCloud taqdim etadigan darajada) | **Taxmin** — UzCloud'ning aniq "encryption at rest" xususiyati rasmiy sahifada alohida tasdiqlanmagan |

---

## 9. Muvofiqlik (compliance)

### 9.1 ZRU-764 (Kiberxavfsizlik to'g'risida)

- 18-modda (ekspertiza) va 19-modda (sertifikatlash) **faqat davlat organlari va KAI (kritik axborot infratuzilmasi) obyektlariga** tegishli (`07-fayl`, 3.1-bo'lim, lex.uz/ru/docs/5960609 bilan tasdiqlangan).
- **Ochiq savol (muhim, hal qilinmagan)**: AIOS kabi oddiy xususiy SaaS ERP soliq.uz/OFD kabi davlat API'lariga faqat **mijoz** sifatida ulanganda shu majburiy ekspertiza/sertifikatlashga tushadimi — ochiq manbada aniq tasdiqlanmagan.
- **Tavsiya**: MVP rejasining birinchi 2-4 haftasida **csec.uz (Davlat kiberxavfsizlik xizmati markazi)**ga yozma so'rov yuborilsin (`07-fayl`, 3.1-bo'lim tavsiyasi; `04-arxitektura-va-stack.md`, 7 va 10-bo'lim). Agar javob "ha" bo'lsa — bu loyiha jadvali va byudjetiga katta ta'sir qiladi (narx/muddat noma'lum).

### 9.2 Shaxsiy ma'lumotlar qonuni

- **Lokalizatsiya**: faqat fizik shaxslarning **biometrik ma'lumotlari, genetik ma'lumotlari va O'zbekiston telekom operatorlari foydalanuvchilarining ma'lumotlari** O'zbekiston hududida saqlanishi shart (ZRU-547, 27-1-modda; ЗРУ-666 bilan kiritilgan, ЗРУ-1125 (2026-03-26/27) bilan tasdiqlangan/liberallashtirilgan — `07-fayl`, 1.1-bo'lim). **AIOS'ning odatiy ma'lumoti (mijoz ismi/telefon, savdo, ombor, buxgalteriya) bu uchta toifaga kirmaydi.**
- Agar kelajakda tizim biometrik funksiya (masalan yuz tanish bilan kirish) qo'shsa — shu qism uchun **Shaxsiy ma'lumotlar bazasini Davlat reyestrida ro'yxatdan o'tkazish** (pd.gov.uz, bildirishnoma tartibida) zarur bo'ladi (`07-fayl`, 1.2-bo'lim). Hozircha MVP'da bunday funksiya yo'q.
- Chet elga uzatish (Claude API, 5.2-bo'lim) — ZRU-547 15/27-1-moddalar asosida qonuniy, lekin uch shartdan (yetarli himoya davlati / standart shartnoma shartlari / xalqaro standart muvofiqligi) qaysi birini tanlash huquqiy ishlov talab qiladi (**ochiq savol**).

### 9.3 PCI DSS

- AIOS **hech qachon** to'liq karta raqami/CVV saqlamaydi yoki qayta ishlamaydi — to'lovlar Click/Payme (JSON-RPC/REST API, merchant tokenlashtirilgan oqim) yoki bank POS-terminali orqali amalga oshadi (`research_notes/texnik/tekshiruv-2026-10-14/2-efaktura-tolov-hosting.md`, Payme/Click protokollari).
- Bu amaliyotda PCI DSS qamrovini **minimal** (odatda SAQ A darajasiga yaqin) qiladi — lekin manbada "PCI" so'zi to'g'ridan-to'g'ri tilga olinmagan, bu xulosa **mantiqiy natija, taxmin** sifatida belgilanadi.

---

## 10. Insident javobi asoslari

Manbada O'zbekiston qonunchiligida ma'lumot buzilishi (data breach) haqida davlat organiga/foydalanuvchiga xabar berish muddati **topilmadi** — quyidagi oqim sanoat bazaviy amaliyoti sifatida **taxmin**:

1. **Aniqlash**: monitoring/alerting (anomal kirish, ko'p noto'g'ri login, RLS siyosati xatosi) — `06-nofunksional-talablar.md`, Observability bo'limiga bog'liq.
2. **Cheklash**: zarar ko'rgan hisob/tokenni bloklash, kalitlarni darhol rotatsiya qilish (4.2-bo'lim).
3. **Xabar berish**: ichki jamoa → ta'sirlangan tenant(lar) Egasiga → (agar shaxsiy ma'lumot buzilishi bo'lsa) qonuniy maslahat asosida tegishli organga/mijozlarga xabar — muddat/format **ochiq savol**.
4. **Post-mortem**: sabab, ta'siri, tuzatish choralari yozma hujjatda (ichki), `audit_log`dan dalillar bilan.

---

## Ochiq savollar

1. ЗРУ-764 (Kiberxavfsizlik to'g'risida) ning oddiy xususiy SaaS ERP'ga (davlat API'lariga mijoz sifatida ulangan) tegishliligi — csec.uz bilan yozma aniqlashtirish kerak (`07-fayl`, Ochiq savol 1).
2. Chegirma/qaytarish/nasiya/pul olish uchun aniq limit summalari — manbada yo'q, MVP oldidan biznes-qoida sifatida sozlanishi kerak (`01-rollar-va-ssenariylar.md`, Ochiq savol 2).
3. Branch scoping'ning RLS siyosati ichida yoki ilova qatlamida amalga oshirilishi — `09-backend-arxitekturasi.md`da hal qilinadi.
4. UzCloud'da tayyor KMS-as-a-Service xizmati bor-yo'qligi tasdiqlanmagan — agar yo'q bo'lsa, qaysi sir boshqaruv vositasi (Vault yoki boshqa) ishlatilishi arxitektura qarori sifatida qoldirilgan.
5. Click/Payme merchant hisobi — tenant darajasida alohida yoki platforma darajasida umumiy bo'lishi (bu sirlarni kim nazorat qilishiga ta'sir qiladi) — biznes qarori kerak.
6. Chet elga (Claude API) shaxsiy ma'lumot uzatish uchun ZRU-547 15/27-1-moddadagi uch shartdan qaysi birini tanlash — huquqiy maslahat kerak.
7. Audit log va backup uchun aniq RPO/RTO va tiklash sinovi chastotasi — manbada yo'q, bu hujjatdagi raqamlar taxmin, pilot/ishga tushirish oldidan amaliy sinovlar bilan tasdiqlanishi kerak.
8. Qurilma tokeni (Android POS) refresh/rotatsiya aniq muddati — `10-android-pos.md`da arxitektura qarori sifatida belgilanadi.
9. Ma'lumot buzilishi (data breach) holatida O'zbekiston qonunchiligi bo'yicha xabar berish muddati/formati — ochiq manbada topilmadi, huquqiy maslahat tavsiya etiladi.
10. Tenant darajasidagi to'liq ma'lumotlar bazasi eksporti (tenant chiqib ketganda) uchun aniq format/SLA — mahsulot jamoasi bilan belgilanishi kerak.

## Manbalar

- `spec/02-arxitektura/00-umumiy-arxitektura.md`, `01-malumotlar-modeli.md`, `08-frontend-arxitekturasi.md`
- `spec/01-mahsulot/01-rollar-va-ssenariylar.md` (huquqlar matritsasi), `02-modullar-talablari.md` (M01–M18, limit/PIN/audit talablari), `04-ekranlar-va-ux.md` (POS-01/06, BO-16 tasdiqlash oqimi), `05-ai-funksiyalar.md` (AI va ma'lumot minimizatsiyasi)
- `research_notes/texnik/04-arxitektura-va-stack.md` (RLS, sertifikatlash, backup, kripto)
- `research_notes/texnik/07-hosting-lokalizatsiya-xavfsizlik.md` (ZRU-764, shaxsiy ma'lumotlar qonuni, saqlash muddatlari, UzCloud)
- `research_notes/texnik/05-ozbek-tilidagi-ai.md` (AI ma'lumot lokalizatsiyasi)
- `research_notes/texnik/tekshiruv-2026-10-14/2-efaktura-tolov-hosting.md` (Click/Payme protokol tasdiqlari)

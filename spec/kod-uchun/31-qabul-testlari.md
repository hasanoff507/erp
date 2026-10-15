# 31 — Qabul testlari (acceptance test ssenariylari)

**Maqsad:** 03–28 fayllaridagi talablar, qoidalar va endpoint kataloglarini bevosita pytest (backend/integratsiya) va Playwright (e2e) testlariga aylantiriladigan, aniq raqamli Given/When/Then ssenariylar to'plamiga aylantirish — har ssenariy bitta avtomatik testga mos keladi.

**Kim uchun:** backend, frontend, QA

**Bog'liq fayllar:** `03-modullar-talablari.md`, `04-biznes-jarayonlar.md`, `07-ekran-tafsilotlari.md`, `09-ai-funksiyalar.md`, `12-db-sxema.md`, `13-provodka-qoidalari.md`, `14-autentifikatsiya-oauth2.md`, `15-xavfsizlik-va-audit.md`, `16-offline-sync.md`, `17-api-umumiy.md`, `18-api-kassa.md`, `19-api-ombor.md`, `20-api-moliya-admin.md`, `22-ai-qatlami.md`, `25-nofunksional-talablar.md`, `01-qarorlar.md`

**Holat:** joriy, 2026-10-15

---

## 0. Qanday ishlatiladi

### 0.1 ID format

`QT-<area>-NN`, masalan `QT-RLS-01`, `QT-M01-03`, `QT-AI-03-02`, `QT-NFR-07`. `<area>` — kross-kesma blok nomi (`RLS`, `IDEMP`, `SEQ`, `OFFLINE48`, `SUB`, `OAUTH`, `PERM`), modul kodi (`M01`…`M18`) yoki `AI`/`NFR`. `NN` — shu blok ichidagi ketma-ket raqam. Har ID — bitta avtomatik test funksiyasi nomi bilan bir xil bo'lishi kerak (`test_qt_m01_03_...`).

### 0.2 Daraja (level)

- **unit** — sof funksiya/qoida (masalan FIFO/AVECO hisob-kitobi, yaxlitlash), tashqi tizim yo'q.
- **integration** — haqiqiy PostgreSQL (testcontainers) + FastAPI test-client, RLS/tranzaksiya/registr tekshiruvi bilan.
- **e2e** — Playwright, to'liq ekran (POS-xx/BO-xx) orqali, backend haqiqiy (yoki to'liq integratsiya muhiti).

### 0.3 US bilan bog'lanish

Har ssenariy "US" ustunida tegishli `US-Mxx-nn`ga ishora qiladi. **MVP'dan keyin** deb belgilangan hikoyalar (qaror #33: US-M03-02, US-M08-08, US-M14-02, US-M17-05) — bu faylda **test yozilmaydi**, chunki ular MVP qamroviga kirmaydi; shu sababli M03/M08/M14/M17 jadvallarida mos raqamlar yo'q (qasddan chiqarib tashlash).

### 0.4 Fixture'lar (standart urug'lantirish)

Har integratsiya/e2e test quyidagi standart holatdan boshlanadi (`conftest.py`/Playwright `fixtures/seed.ts` orqali bitta marta yaratiladi, har test alohida tranzaksiya/rollback bilan izolyatsiyalanadi):

| Obyekt | Qiymat |
|---|---|
| Tenant A (asosiy) | **"Demo do'kon"**, STIR mavjud, `subscriptions.status='active'`, `tenant_tax_regimes.regime='vat'` |
| Tenant B (izolyatsiya uchun) | **"Boshqa do'kon"** — faqat RLS testlarida, Tenant A bilan bog'liq emas |
| Filial | "Chilonzor filiali" (`branches.settlement_category='city_100k_plus'`), ombor — "Asosiy ombor" |
| Kassa | "Kassa-1" (`cash_registers`), bitta ochiq smena yaratish testlar ichida alohida |
| Foydalanuvchilar (har rolga bitta) | `ega@demo` (Egasi), `menejer@demo` (Menejer), `kassir@demo` (Kassir), `omborchi@demo` (Omborchi), `buxgalter@demo` (Buxgalter) — barchasi parol + PIN bilan |
| Mahsulot — standart | "Coca-Cola 1.5L", `vat_rate=12.00`, `is_marked=false`, `is_weighed=false`, narx `"12000.00"` |
| Mahsulot — markirovkalangan | "Hayot suvi 1.5L", `is_marked=true`, `vat_rate=12.00`, narx `"8000.00"` |
| Mahsulot — tortiladigan | "Mol go'shti (kg)", `is_weighed=true`, `unit_code='kg'`, `vat_rate=12.00`, narx `"95000.00"`/kg |
| Mahsulot — QQS imtiyozli | "Bolalar kitobi", `vat_rate=NULL`, `vat_exemption_code` to'ldirilgan (0%) |
| Mijoz (counterparty) | "Aliyev Vali", telefon bilan, kredit limiti `"500000.00"` |
| Yetkazib beruvchi | "Mega Trade MChJ", STIR bilan |

### 0.5 Pul/miqdor formati

Qaror #26 (`01-qarorlar.md`) bo'yicha: **pul — har doim o'nlik satr** 2 xona aniqlikda (`"100000.00"`), narx/tannarx — 4 xona (`"8333.3333"`), miqdor — 3 xona (`"1.250"`), foiz — `NUMERIC(5,2)` (`"5.00"`). Testlarda JSON `number` tipi bilan pul yuborish/qabul qilish — **avtomatik fail** (kontrakt testi, lint qoidasi bilan bir xil ruh).

### 0.6 Umumiy kutish

Har integratsiya testida: (a) `Idempotency-Key` sarlavhasi generatsiya qilinadi (back-office yozuvchi so'rovlarida majburiy, `17-api-umumiy.md`); (b) RLS kontekst `app.tenant_id`/`app.user_id` test fixture orqali to'g'ri o'rnatiladi; (c) har test postingdan keyin tegishli registr (`stock_moves`/`debt_moves`/`cash_moves`/`ledger_entries`/`vat_moves`) qatorlarini **to'liq** (barcha ustun) tekshiradi, faqat summani emas.

### 0.7 Modul bo'yicha ssenariy soni (2-bo'lim, qamrov nazorati uchun)

| Modul | Soni | Modul | Soni | Modul | Soni |
|---|---|---|---|---|---|
| M01 | 13 | M07 | 8 | M13 | 9 |
| M02 | 6 | M08 | 14 | M14 | 5 |
| M03 | 5 | M09 | 9 | M15 | 5 |
| M04 | 11 | M10 | 6 | M16 | 5 |
| M05 | 5 | M11 | 6 | M17 | 7 |
| M06 | 6 | M12 | 5 | M18 | 6 |

Jami 2-bo'limda **131** ssenariy (18 modul), 1-bo'limda **42** kesishuvchi ssenariy, 3-bo'limda **12** AI ssenariysi, 4-bo'limda **13** NFR ssenariysi — umumiy **198** avtomatik test.

### 0.8 Test nomlash va ishga tushirish namunasi

Har jadval qatori — bitta test funksiyasi; ID test nomining o'zagi bo'ladi. Backend (pytest):

```python
def test_qt_seq_01_duplicate_receipt_seq_rejected(seeded_shift, api_client):
    # Berilgan: receipt_seq=5 CR1/SH1 ostida allaqachon yozilgan
    first = api_client.post_sale(seeded_shift, receipt_seq=5)
    assert first.status_code == 201
    # Qachonki: boshqa sale.created xuddi shu (cash_register_id, shift_id, receipt_seq) bilan keladi
    second = api_client.post_sale(seeded_shift, receipt_seq=5)
    # Unda: RECEIPT_SEQ_CONFLICT, retryable=false
    body = second.json()
    assert body["error_code"] == "RECEIPT_SEQ_CONFLICT"
    assert body["retryable"] is False
```

Ishga tushirish: `pytest -m "qt_critical"` (1-bo'lim), `pytest -k "qt_m01"` (bitta modul), `pytest -m "qt_critical" --maxfail=1` CI'da **bloklovchi** bosqich sifatida (0.9-bandga qarang). Playwright: `npx playwright test --grep "QT-SUB"`.

### 0.9 CI darvozasi (gate) — nima bloklovchi, nima emas

| Guruh | CI'da | Sabab |
|---|---|---|
| 1-bo'lim (RLS, idempotentlik, `receipt_seq`, obuna, OAuth, ruxsatlar) | **Bloklovchi** — bironta fail bo'lsa merge/deploy to'xtaydi | Xavfsizlik/moliyaviy yaxlitlik — pilotdan oldin 100% o'tishi shart (vazifa talabi) |
| 2-bo'lim M01/M07/M08/M10/M11 (provodka, fiskal, QQS, davr yopish) | **Bloklovchi** | Buxgalteriya/soliq hisob-kitobi noto'g'ri bo'lsa huquqiy xavf |
| 2-bo'lim qolgan modullar (M02–M06, M09, M12–M18) | **Ogohlantiruvchi** (fail bo'lsa PR belgilanadi, lekin darhol blok emas — 24 soat ichida tuzatish talab qilinadi) | Funksional, lekin moliyaviy yaxlitlikka bevosita ta'sir qilmaydi |
| 3-bo'lim (AI) | **Bloklovchi faqat raqamli nazorat (100%) va AI-03 maydon chegarasi uchun**; uslub/LLM-judge ball — faqat ogohlantiruvchi | `22-ai-qatlami.md` §8.3: "raqamli nazorat 100%dan past — merge bloklanadi" |
| 4-bo'lim (NFR) | **Faqat 48/72 soat va 5 kalendar kunlik qonuniy muddat — bloklovchi**; qolgan performance maqsadlari ("taxmin") — kuzatiladi, blok emas | `25-nofunksional-talablar.md` band 1: tezlik raqamlari manbada tasdiqlanmagan, faqat qonuniy muddatlar majburiy |

---

## 1. Kritik kross-kesma ssenariylar (pilotdan oldin albatta o'tishi shart)

### 1.1 RLS — tenant izolyatsiyasi (`12-db-sxema.md` §4, `15-xavfsizlik-va-audit.md` §3.2)

| ID | Daraja | Ssenariy |
|---|---|---|
| QT-RLS-01 | integration | **Berilgan** Tenant A'da `sale_id=S1` chek mavjud va Tenant B tizimda butunlay boshqa tenant, **qachonki** Tenant B foydalanuvchisi token bilan `GET /api/v1/sales/{S1}` so'raydi, **unda** `404 Not Found` qaytadi (RLS 0 qator qaytaradi, `403` emas — mavjudligini oshkor qilmaslik uchun), javobda Tenant A ma'lumoti hech qanday maydonda ko'rinmaydi. |
| QT-RLS-02 | unit | **Berilgan** DB sessiyasida `app.tenant_id` sozlanmagan (`current_setting` bo'sh), **qachonki** `SELECT * FROM app.sales` to'g'ridan-to'g'ri bajariladi, **unda** 0 qator qaytadi va xato tashlanmaydi (fail-closed, `15-xavfsizlik-va-audit.md` §3.2: "tenant konteksti yo'q bo'lsa — nol natija, xato emas"). |
| QT-RLS-03 | integration | **Berilgan** Tenant A qurilmasi (`device_id` → faqat Tenant A'ga bog'langan) autentifikatsiyalangan, **qachonki** `POST /sync/push` payload'ida (frontend xatosi/firibgarlik taqlidi) `events[].payload.tenant_id = <Tenant B id>` yuborilsa, **unda** server bu maydonni **e'tiborsiz qoldiradi** — yozuv faqat sessiyadagi `app.tenant_id` (Tenant A) ostida yaratiladi (`tenant_transaction(session, tenant_id)` helper, `01-qarorlar.md` #1); Tenant B'da hech qanday yangi qator paydo bo'lmaydi. |
| QT-RLS-04 | integration | **Berilgan** oddiy tenant foydalanuvchisi (Egasi) tokeni, **qachonki** `GET /platform/tenants` (faqat `platform_admins` uchun) so'raladi, **unda** `403`; **Berilgan** `platform_admins` hisobi (TOTP bilan kirgan), **qachonki** xuddi shu endpoint chaqirilsa, **unda** `200` va istalgan tenant ko'rinadi (RLS bypass — faqat shu yo'l, `15-xavfsizlik-va-audit.md` §3.4). |
| QT-RLS-05 | integration | **Berilgan** `products`/`units`/`plans` kabi `tenant_id`siz global jadval, **qachonki** oddiy `erp_app` roli bilan `INSERT`/`UPDATE` qilinsa, **unda** `GRANT` yo'qligi sababli DB darajasida rad etiladi (faqat `erp_migrator` yoza oladi). |
| QT-RLS-06 | integration | **Berilgan** Tenant B'da `product_id=PB1` va `price="9999.00"` mavjud, Tenant A qurilmasi hali hech qachon bu ID bilan ishlamagan, **qachonki** Tenant A qurilmasi `GET /sync/pull?scope=catalog,prices&cursor=` so'rasa, **unda** javobdagi `catalog`/`prices` massivlarida `PB1` **hech qachon** ko'rinmaydi — sync pull ham RLS siyosatidan o'tadi, alohida "sync uchun bypass" yo'q (vazifa talabi: "tenant A tenant B ma'lumotini sync orqali ham ko'ra olmasligi"). |
| QT-RLS-07 | integration | **Berilgan** Tenant B qurilmasi `/sync/push` orqali `counterparty.created` voqeasini yuborgan (`counterparty_id=CB1`, Tenant B kontekstida qabul qilingan), **qachonki** Tenant A xodimi keyinroq `GET /api/v1/counterparties?search=` orqali shu `CB1` nomini qidirsa, **unda** natija bo'sh — sync orqali yozilgan ma'lumot ham RLS doirasidan tashqariga chiqmaydi. |
| QT-RLS-08 | integration | **Berilgan** bitta DB ulanishi (connection pool) ichida scheduler ketma-ket ikki tenant (Tenant A, keyin Tenant B) uchun job navbatga qo'yadi, birinchi job `set_config('app.tenant_id', A, true)` bilan tugaydi, **qachonki** ikkinchi job boshlansa, **unda** u o'z `app.tenant_id=B` konteksti bilan boshlanadi — Tenant A konteksti **qolib ketmaydi** (`SET LOCAL ... true` tranzaksiya tugaganda avtomatik tozalanadi, `list_active_tenant_ids()` SECURITY DEFINER har tenantga alohida `tenant_transaction` ochadi, `01-qarorlar.md` #1). |

### 1.2 Idempotentlik (`17-api-umumiy.md`, `16-offline-sync.md` §3.1)

| ID | Daraja | Ssenariy |
|---|---|---|
| QT-IDEMP-01 | integration | **Berilgan** `Idempotency-Key=K1` bilan `POST /api/v1/cash-movements` muvaffaqiyatli yakunlangan (`201`), **qachonki** xuddi shu `K1` va **bir xil** so'rov tanasi bilan qayta yuboriladi, **unda** yangi yozuv yaratilmaydi, birinchi javob (bir xil `id`, `status`) qaytariladi — `cash_moves`da faqat bitta qator qoladi. *(Diqqat: bu aniq "keshlangan javobni qaytarish" xatti-harakati manbada faqat yon ta'sir sifatida nazarda tutilgan — §"Spec'da aniqlashtirish kerak" ro'yxatiga qarang.)* |
| QT-IDEMP-02 | integration | **Berilgan** `Idempotency-Key=K2` bilan birinchi so'rov hali bajarilmoqda (DB tranzaksiyasi tugamagan — test parallel thread/lock simulyatsiyasi bilan), **qachonki** xuddi shu `K2` bilan ikkinchi so'rov parallel yuboriladi, **unda** `409 Conflict`, `error.code=IDEMPOTENCY_IN_PROGRESS`, javobda `Retry-After` sarlavhasi bor. |
| QT-IDEMP-03 | integration | **Berilgan** `Idempotency-Key=K3` allaqachon bir so'rov (masalan `cash_movements`, summa `"50000.00"`) uchun ishlatilgan, **qachonki** xuddi shu `K3` bilan **boshqa** so'rov tanasi (summa `"70000.00"`) yuborilsa, **unda** `422 Unprocessable Entity`, `error.code=IDEMPOTENCY_KEY_REUSED` (`request_hash` mos kelmaydi). |
| QT-IDEMP-04 | integration | **Berilgan** POS offline rejimda `sale.created` voqeasini `client_event_id=E1` bilan outbox'ga yozgan va bir marta `POST /sync/push` orqali yuborgan (qabul qilingan, `sync_receipts`da saqlangan), **qachonki** tarmoq uzilishi tufayli outbox hali o'chirilmagan va qurilma xuddi shu `E1`ni qayta yuborsa, **unda** server javobida `status: "duplicate"` va **bir xil** server raqami (`number`) qaytadi, `sales` jadvalida ikkinchi marta yozilmaydi. |

### 1.3 `receipt_seq` yagonaligi va "bitta smena — bitta qurilma" (`12-db-sxema.md`, `16-offline-sync.md` §3.1/7, `18-api-kassa.md` §3)

| ID | Daraja | Ssenariy |
|---|---|---|
| QT-SEQ-01 | integration | **Berilgan** `shift_id=SH1`, `cash_register_id=CR1` ochiq smenada `receipt_seq=5` bilan chek allaqachon `fiscal_receipts`ga yozilgan, **qachonki** xuddi shu `(cash_register_id, shift_id, receipt_seq=5)` kombinatsiyasi bilan boshqa `sale.created` voqeasi kelsa, **unda** `UNIQUE (tenant_id, cash_register_id, shift_id, receipt_seq)` buzilishi sababli `rejected`, `error_code=RECEIPT_SEQ_CONFLICT`, `retryable:false` (eskalatsiya talab qilinadi, avtomatik qayta urinish yo'q). |
| QT-SEQ-02 | integration | **Berilgan** `shift_id=SH1` qurilma `D1`da ochilgan (`shifts.device_id=D1`), **qachonki** qurilma `D2`dan xuddi shu `shift_id=SH1` uchun yangi voqea (`sale.created` yoki `debt_payment.created`) `/sync/push`ga yuborilsa, **unda** `rejected`, `error_code=SHIFT_DEVICE_MISMATCH`, boshqa voqealarga ta'sir qilmaydi. |
| QT-SEQ-03 | integration | **Berilgan** `shift_id=SH1` yopilgan va Z-hisobot (`fiscal_receipts.kind='z_report'`) allaqachon yaratilgan, **qachonki** shu smena uchun ikkinchi Z-hisobot yaratishga urinilsa, **unda** `uq_fiscal_z_per_shift` (shift bo'yicha yagona) buzilishi sababli rad etiladi. |

### 1.4 Offline 48 soatlik qoida (`16-offline-sync.md` §6, `25-nofunksional-talablar.md`)

| ID | Daraja | Ssenariy |
|---|---|---|
| QT-OFFLINE48-01 | integration (fake clock) | **Berilgan** birinchi offline `sale.created` voqeasi `t0`da qurilmada yaratilgan va hali OFD'ga yetib bormagan, **qachonki** vaqt `t0+50 soat`ga simulyatsiya qilinsa (sinxronizatsiya hali bo'lmagan), **unda** `t0+48 soat`da tizim audit bayrog'ini (`offline_48h_exceeded` turidagi ogohlantirish) qo'yadi va M18 orqali Egasiga xabar ketadi — **lekin yangi sotuv bloklanmaydi** (qonunda aniq bloklash topilmagan, manbada qasddan ogohlantirish+audit tanlangan, `16-offline-sync.md` §6 bandi 6). |
| QT-OFFLINE48-02 | integration (fake clock) | **Berilgan** qurilma soati server qabul vaqtidan (`received_at`) ancha orqada (soat "orqaga surilgan" taqlidi), **qachonki** `created_at` bilan `received_at` orasidagi farq odatiy offline oyna muddatidan katta bo'lsa, **unda** server `created_at`ni `max(created_at, received_at - taxminiy_oyna)` ga **qisqartiradi** (clamp) va yozuvni audit uchun belgilaydi — 48 soatlik muddat soxta cho'zilmaydi. |

### 1.5 Obuna hayot sikli (`14-autentifikatsiya-oauth2.md` §16, `12-db-sxema.md` `subscriptions`, `01-qarorlar.md` #15)

| ID | Daraja | Ssenariy |
|---|---|---|
| QT-SUB-01 | integration | **Berilgan** `subscriptions.status='active'`, `current_period_end` o'tgan, **qachonki** scheduler tekshirsa, **unda** holat `grace`ga o'tadi, `grace_ends_at = current_period_end + 24 soat`; barcha ekranlarda qizil banner ko'rinadi, **kassa/back-office/AI to'liq ishlayveradi**. |
| QT-SUB-02 | e2e (Playwright) | **Berilgan** tenant `grace` holatida, **qachonki** foydalanuvchi kassada chek yaratadi, **unda** sotuv, fiskal chek, AI so'rovlari odatdagidek ishlaydi — faqat ogohlantiruvchi banner ko'rinadi (24/12/2 soat qolganda eslatma kanallari ishga tushadi). |
| QT-SUB-03 | integration | **Berilgan** `grace_ends_at` o'tgan va to'lov kelmagan, **qachonki** scheduler ishga tushsa, **unda** holat `restricted`ga o'tadi: shu tenantning **barcha** `sessions`/`refresh_tokens` serverda bekor qilinadi (`revoked_at=now`), audit `subscription_lockout_triggered` yoziladi. |
| QT-SUB-04 | e2e | **Berilgan** tenant `restricted`, **qachonki** mavjud sessiyadan API so'rovi yuborilsa, **unda** `403 {code: "SUBSCRIPTION_RESTRICTED"}`, frontend interceptor `/login?reason=subscription_expired`ga yo'naltiradi — bu **logout emas**, Dexie/outbox o'chirilmaydi. |
| QT-SUB-05 | integration | **Berilgan** tenant `restricted`, **qachonki** autentifikatsiyalanmagan foydalanuvchi `GET /billing/pay`ni ochsa, **unda** `200` — bu sahifa `restricted` holatida ham ochiq (session talab qilmaydi, `pay_token` orqali bir martalik checkout). |
| QT-SUB-06 | integration | **Berilgan** tenant `restricted`, qurilmaning `suspended` refresh tokeni bor, **qachonki** `POST /oauth/token` (`grant_type=refresh_token`) chaqirilsa, **unda** faqat `scope=sync.drain` bilan ~5 daqiqalik access token qaytadi; shu token bilan `scope`dan tashqari (masalan yangi sotuv yaratish) so'rov yuborilsa — rad etiladi. |
| QT-SUB-07 | integration | **Berilgan** `scope=sync.drain` tokeni va qurilmada lokaut**dan oldin** yaratilgan, hali yuborilmagan 3 ta fiskal chek, **qachonki** `/sync/push` shu token bilan chaqirilsa, **unda** ushbu 3 chek qabul qilinib OFD'ga yuboriladi, lekin **yangi** `sale.created` voqeasi (lokaut**dan keyin** yaratilgan) bo'lsa — rad etiladi (faqat oldindan yaratilgan hujjatlar o'tadi). |
| QT-SUB-08 | e2e | **Berilgan** tenant `restricted`, **qachonki** foydalanuvchi to'lov sahifasidan "Ma'lumotlarimni yuklab olish"ni bosadi, **unda** SMS/Telegram OTP (`purpose=data_export`) so'raladi; **qachonki** OTP to'g'ri tasdiqlansa, **unda** ~15 daqiqalik bir martalik `GET /billing/export-my-data?token=...` havolasi beriladi — bu login yoki boshqa ekranni ochmaydi. |
| QT-SUB-09 | integration | **Berilgan** `restricted` tenant to'lov qiladi, **qachonki** `billing_payments.status='success'` bo'lsa, **unda** `subscriptions.status='active'`ga qaytadi, barcha kirish darhol tiklanadi, "To'lov qabul qilindi" xabari ketadi. |

### 1.6 OAuth2 / PKCE / refresh rotatsiyasi / CSRF (`14-autentifikatsiya-oauth2.md` §2, §7)

| ID | Daraja | Ssenariy |
|---|---|---|
| QT-OAUTH-01 | integration | **Berilgan** `/oauth/authorize` so'rovida `code_challenge_method=plain`, **qachonki** so'rov yuborilsa, **unda** rad etiladi (faqat `S256` qabul qilinadi). |
| QT-OAUTH-02 | integration | **Berilgan** to'g'ri `code_challenge` bilan olingan `code`, **qachonki** `POST /oauth/token`ga **noto'g'ri** `code_verifier` bilan almashtirilsa, **unda** rad etiladi; **qachonki** bir marta muvaffaqiyatli almashtirilgan `code` **ikkinchi** marta ishlatilsa, **unda** ham rad etiladi (bir martalik, 60s TTL). |
| QT-OAUTH-03 | integration | **Berilgan** `refresh_token=RT1` muvaffaqiyatli ishlatilgan (`used_at` o'rnatilgan, `RT2` berilgan), **qachonki** `RT1` **qayta** (`now - used_at > 30 soniya`) yuborilsa, **unda** butun `family_id` (barcha avlod tokenlar + tegishli `sessions`) darhol bekor qilinadi, `audit_log`ga `refresh_token_reuse_detected` yoziladi, foydalanuvchiga qayta login talab qilinadi. |
| QT-OAUTH-04 | integration | **Berilgan** `RT1` endigina ishlatilgan (`RT2` hali ishlatilmagan), **qachonki** `RT1` **≤30 soniya** ichida (tarmoq uzilishi/parallel so'rov taqlidi — single-flight) qayta yuborilsa, **unda** oila bekor qilinmaydi, mavjud sessiya davom etadi (`14-autentifikatsiya-oauth2.md` §7.1 eslatma). |
| QT-OAUTH-05 | integration | **Berilgan** veb-BFF orqali faol sessiya, **qachonki** `POST`/`PUT`/`PATCH`/`DELETE` so'rovi `X-CSRF-Token` sarlavhasisiz yoki eskirgan token bilan yuborilsa, **unda** `403 {error.code: "CSRF_INVALID"}`; **qachonki** oldin `GET /api/v1/auth/csrf`dan olingan to'g'ri token bilan yuborilsa, **unda** `200` (`15-xavfsizlik-va-audit.md` §1.3). |
| QT-OAUTH-06 | integration | **Berilgan** Android POS (public client, to'g'ridan-to'g'ri Bearer), **qachonki** `X-CSRF-Token`siz yozuvchi so'rov yuborilsa, **unda** CSRF tekshiruvidan **ozod** (faqat veb-BFF/`sync/*` uchun talab qilinadi), so'rov muvaffaqiyatli bajariladi. |
| QT-OAUTH-07 | integration | **Berilgan** Egasi xodimni "Bloklash" tugmasini bosadi (US-M13-05), **qachonki** amal bajarilgan zahoti, **unda** shu xodimning barcha `sessions`/`refresh_tokens` oilasi **darhol** (keyingi so'rovda emas, hozir) bekor qilinadi, Redis `sid`-revoke keshi yangilanadi. |

### 1.7 Ruxsatlar — Egasi vs Kassir limitlari (`15-xavfsizlik-va-audit.md` §2.2/2.3, `01-qarorlar.md` #28)

| ID | Daraja | Ssenariy |
|---|---|---|
| QT-PERM-01 | integration | **Berilgan** Egasi hisobi, **qachonki** u istalgan summa/foizdagi chegirma, qaytarish, kassadan pul olish, qarzni kechirish amalini bajarsa, **unda** hech qanday `approval_requests` yaratilmaydi va limit tekshiruvi o'tkazilmaydi (`platform.admin`dan tashqari barcha ruxsat, cheksiz limit). |
| QT-PERM-02 | integration | **Berilgan** Kassir chekka `discount_pct="5.00"` (standart limit) chegirma qo'ymoqda, **qachonki** chek yakunlansa, **unda** `201`, tasdiq talab qilinmaydi. |
| QT-PERM-03 | integration | **Berilgan** Kassir chekka `discount_pct="6.00"` (limitdan yuqori) chegirma qo'ymoqda, **qachonki** tasdiqsiz yakunlashga urinsa, **unda** `422 DISCOUNT_LIMIT_EXCEEDED` (offline/local_pin holatida Menejer/Egasi PIN so'raladi) **yoki** online rejimda `202 {status:"draft", approval_request_id}` (`approval_requests.kind='discount_over_limit'`, `permission_code='discount.give'`) qaytadi. |
| QT-PERM-04 | integration | **Berilgan** Kassir asl chek **topilmagan** qaytarishni amalga oshirmoqda, summa atigi `"10000.00"` (limitdan ancha past), **qachonki** tasdiqsiz yakunlashga urinsa, **unda** baribir tasdiq talab qilinadi (`return_no_receipt` — summadan qat'i nazar har doim majburiy, `kind='return_no_receipt'`). |
| QT-PERM-05 | integration | **Berilgan** Kassir kassadan `"50000.00"` (standart limit chegarasida) pul olmoqda, **qachonki** amal bajarilsa, **unda** tasdiqsiz o'tadi; **qachonki** `"50001.00"` so'ralsa, **unda** `cash_withdrawal_over_limit` approval talab qilinadi (`permission_code='cash.withdraw'`). |
| QT-PERM-06 | integration | **Berilgan** `approval_requests` qatori Kassir tomonidan yaratilgan (`requested_by=kassir`), **qachonki** xuddi shu Kassir uni "tasdiqlash" so'rovini yuborsa, **unda** rad etiladi (`CHECK (resolved_by IS NULL OR resolved_by <> requested_by)` — so'rovchi o'zini o'zi tasdiqlay olmaydi). |
| QT-PERM-07 | integration | **Berilgan** bitta `approval_requests` qatori `status='approved'` holatiga o'tgan va `consumed_at` o'rnatilgan, **qachonki** xuddi shu `approval_request_id` bilan ikkinchi marta hujjat `post` qilinmoqchi bo'lsa, **unda** rad etiladi (`uq_doc_approvals_request` — bir marta ishlatiladi). |
| QT-PERM-08 | integration | **Berilgan** Kassir faqat "Chilonzor filiali"ga bog'langan (`memberships.branch_ids=['Chilonzor']`), **qachonki** `X-Branch-Id`da boshqa filial ID'si bilan `GET /api/v1/stock-balances` so'rasa, **unda** `403 BRANCH_SCOPE_DENIED` (`15-xavfsizlik-va-audit.md` §2.4) — filial cheklovi ilova qatlamida, RLS'dan mustaqil tekshiriladi. |
| QT-PERM-09 | integration | **Berilgan** Egasi (`memberships.branch_ids=[]`, bo'sh massiv = barcha filiallar), **qachonki** istalgan filial ID'si bilan so'rov yuborsa, **unda** hech qachon `BRANCH_SCOPE_DENIED` olmaydi — bo'sh massiv "cheklovsiz" deb talqin qilinadi. |

---

## 2. Modul bo'yicha ssenariylar (M01…M18)

Har qator — bitta Must foydalanuvchi hikoyasi (US) uchun kamida bitta happy-path yoki negative ssenariy; aksariyat US uchun ikkisi ham berilgan. Registr qiymatlari `13-provodka-qoidalari.md`dagi aniq misollardan olingan.

### M01 — Kassa (POS)

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M01-01 | US-M01-01 | happy | **Berilgan** ochiq smena, kassaga "Coca-Cola 1.5L" (narx `"12000.00"`, QQS 12%) 1 dona qo'shiladi va naqd to'lov bilan yakunlanadi, **qachonki** chek `post` qilinsa, **unda**: `stock_moves` (`qty=-1.000`), `ledger_entries` 3 qator — `Dt 5010/Kt 9020 = "10714.29"` (sof), `Dt 5010/Kt 6410 = "1285.71"` (QQS, `12000×12/112`), `Dt 9120/Kt 2910` = COGS (FIFO/AVECO bo'yicha); `fiscal_receipts.kind='sale'`, `status` internet bor bo'lsa `sent`ga o'tadi. |
| QT-M01-02 | US-M01-01 | negative | **Berilgan** ochiq smena yo'q, **qachonki** `sale.created` voqeasi yuborilsa, **unda** `error_code=SHIFT_NOT_OPEN`, hujjat yaratilmaydi. |
| QT-M01-03 | US-M01-02 | happy | **Berilgan** POS offline rejimda, **qachonki** kassir chek yaratsa, **unda** chek lokal (`client_event_id` bilan) saqlanadi, `fiscal_receipts.offline_since` to'ldiriladi; internet qaytganda `/sync/push` orqali avtomatik yuboriladi va `status` `pending→sent`ga o'tadi. |
| QT-M01-04 | US-M01-03 | happy | **Berilgan** offline, "Hayot suvi 1.5L" (`is_marked=true`) narxi qurilmada keshlangan, **qachonki** DataMatrix kodi skanerlansa, **unda** sotuv **ruxsat etiladi** — kod mahalliy jurnalga yoziladi, internet qaytganda CRPT Turon'ga tekshiruv/"sotildi" belgisi yuboriladi. |
| QT-M01-05 | US-M01-03 | negative | **Berilgan** offline, markirovkalangan tovar narxi qurilmada **noma'lum**, **qachonki** kod skanerlansa, **unda** sotuv **taqiqlanadi** (`16-offline-sync.md` §7). |
| QT-M01-06 | US-M01-04 | happy | **Berilgan** smena yopilmoqda, kutilgan naqd `"500000.00"` hisoblangan, sanalgan naqd `"500000.00"` kiritilgan, **qachonki** "Smena yopish" bosilsa, **unda** farq `"0.00"`, `fiscal_receipts.kind='z_report'` yaratiladi (`shift_id` bo'yicha yagona). |
| QT-M01-07 | US-M01-04 | negative | **Berilgan** kutilgan naqd `"500000.00"`, sanalgan `"480000.00"`, **qachonki** smena yopilsa, **unda** farq `"-20000.00"` (kamomad) ko'rsatiladi, kassir izoh kiritishi majburiy, Egasiga M18 xabari ketadi. |
| QT-M01-08 | US-M01-05 | happy | **Berilgan** yuridik shaxs mijoz UzQR orqali to'lamoqda, **qachonki** bank yagona QR skanerlanib to'lov tasdiqlansa, **unda** `cash_moves.method='uzqr'`, fiskal chek standart tartibda chiqadi. |
| QT-M01-09 | US-M01-06 | happy | **Berilgan** avval oddiy chek bilan sotilgan tovar (B2C), **qachonki** mijoz keyinroq B2B sifatida e-faktura so'rasa, **unda** `einvoices.related_doc` orqali shu chekka bog'langan chiquvchi e-faktura yaratiladi, QQS **ikkinchi marta hisoblanmaydi**, yangi provodka yozilmaydi (`13-provodka-qoidalari.md` §2.22). |
| QT-M01-10 | US-M01-01 | happy (aralash to'lov) | **Berilgan** chek jami `"100000.00"`, naqd `"40000.00"` + karta `"30000.00"` + nasiya `"30000.00"`, **qachonki** yakunlansa, **unda** `sale_payments` 3 qatorga bo'linadi va `ledger_entries`: `Dt 5010=40000.00`, `Dt 5110=30000.00`, `Dt 4010=30000.00` (yig'indi `100000.00`); naqd/karta qismiga **darhol** fiskal chek, nasiya qismiga — faqat to'langanda (`13-provodka-qoidalari.md` §2.4/§2.14). |
| QT-M01-11 | US-M01-01 | negative (draft void) | **Berilgan** chek hali to'lanmagan (`draft`), ichida 2 qator bor, **qachonki** Kassir to'lovdan oldin butun chekni "BEKOR" bossa, **unda** `sale.draft_voided` voqeasi yoziladi — **faqat audit** (`audit_log`), hech qanday registrga (`stock_moves`/`ledger_entries`) ta'sir qilmaydi, fiskal chek yaratilmaydi (`18-api-kassa.md` §5). |
| QT-M01-12 | US-M01-01 | happy (qayta chop etish) | **Berilgan** `S1` chek allaqachon chop etilgan va to'liq fiskallashgan, **qachonki** Kassir "Qayta chop etish"ni bossa, **unda** `receipt.reprinted` voqeasi yoziladi, chekda **"NUSXA"** belgisi chiqadi, chop etishlar soni **cheklanmaydi**, har biri alohida audit yozuvi (`18-api-kassa.md` §6). |
| QT-M01-13 | US-M01-05 | negative (UzQR kutilmoqda) | **Berilgan** mijoz dinamik UzQR'ni skanerlagan, bank tasdig'i hali kelmagan, **qachonki** internet uzilib ketsa, **unda** chek `"to'lov kutilmoqda"` holatida qoladi; Kassir boshqa to'lov usuliga o'tishi yoki bekor qilishi mumkin; bank tasdig'i ikki marta kelsa `provider_tx_id` bo'yicha idempotentlik ikkinchi marta hisoblamaydi. |

### M02 — Qaytarish

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M02-01 | US-M02-01 | happy | **Berilgan** asl chek topilgan, 1 dona "Coca-Cola 1.5L" qaytarilmoqda, **qachonki** qaytarish `post` qilinsa, **unda** `stock_moves(qty=+1.000)` asl partiyaga, `ledger_entries`: `Dt 9040/Kt 5010="10714.29"`, `Dt 6410/Kt 5010="1285.71"`, `Dt 2910/Kt 9120`=asl tannarx; naqd qaytariladi. |
| QT-M02-02 | US-M02-01 | negative | **Berilgan** asl chek **topilmagan**, **qachonki** Kassir summadan qat'i nazar tasdiqsiz yakunlashga urinsa, **unda** har doim Menejer/Egasi PIN (`return_no_receipt`) talab qilinadi (QT-PERM-04 bilan bir xil qoida). |
| QT-M02-03 | US-M02-02 | happy | **Berilgan** asl chek bilan qaytarish summasi `"100000.00"` (standart limit chegarasida), **qachonki** Kassir tasdiqsiz yakunlasa, **unda** `201`, tasdiq talab qilinmaydi. |
| QT-M02-04 | US-M02-02 | negative | **Berilgan** qaytarish summasi `"150000.00"` (limitdan yuqori), **qachonki** Kassir tasdiqsiz yakunlashga urinsa, **unda** `return_over_limit` approval talab qilinadi (`permission_code='returns.approve'`). |
| QT-M02-05 | US-M02-03 | happy | **Berilgan** qaytarish tasdiqlangan, **qachonki** buxgalteriya yozuvi yaratilsa, **unda** sotuv summasi va QQS **manfiy** (storno) yozuv bilan tuzatiladi — asl `ledger_entries` o'zgartirilmaydi, yangi qator `reversal_of_id` bilan qo'shiladi. |
| QT-M02-06 | US-M02-01 | negative (markirovka, offline) | **Berilgan** "Hayot suvi 1.5L" (`is_marked=true`) qatori bilan asl chek, qurilma **offline**, **qachonki** Kassir shu qatorni qaytarishga urinsa, **unda** "Qaytarish" tugmasi POS'da bloklangan ("Qaytarish uchun internet kerak"); agar voqea baribir `/sync/push`ga yetib borsa, server ham qayta tekshiradi va `422 MARKING_RETURN_REQUIRES_ONLINE` bilan rad etadi (`16-offline-sync.md` §7, `18-api-kassa.md` §7.1). |

### M03 — Chegirma

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M03-01 | US-M03-01 | happy | **Berilgan** Kassir chekka `"5.00"`% chegirma qo'ymoqda, **qachonki** yakunlansa, **unda** QQS chegirmadan **keyingi** summadan hisoblanadi (M10 qoidasi), `sale_lines.discount_pct="5.00"` saqlanadi. |
| QT-M03-02 | US-M03-01 | negative | QT-PERM-03 bilan bir xil (limitdan yuqori chegirma — tasdiq talab qilinadi). |
| QT-M03-03 | US-M03-03 | happy | **Berilgan** tanlangan davrda chegirmalar berilgan, **qachonki** Egasi hisobotni ochsa, **unda** berilgan chegirmalar summasi va shu sabab kamaygan margin ko'rsatiladi. |
| QT-M03-04 | US-M03-01 | negative (stacking) | **Berilgan** bir chekda mijozning doimiy chegirmasi (`"10.00"`%) va kassir chegirmasi (`"5.00"`%) to'qnashgan, **qachonki** chek yakunlansa, **unda** chegirmalar **yig'ilmaydi** — faqat mijozga eng katta foyda beradigan (`"10.00"`%) qo'llaniladi. |
| QT-M03-05 | US-M03-01 | negative (manfiy narx) | **Berilgan** tovar narxi `"3000.00"`, **qachonki** Kassir `"120.00"`% chegirma kiritishga urinsa (narxni manfiy qilib yuboradigan), **unda** `422 VALIDATION_ERROR` — tizim chegirmaning tovar narxini manfiy qilib yuborishiga yo'l qo'ymaydi. |

### M04 — Ombor qoldig'i

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M04-01 | US-M04-01 | happy | **Berilgan** xaridnoma bo'yicha tovar qabul qilingan, **qachonki** qabul hujjati `post` qilinsa, **unda** `stock_balances.qty` avtomatik oshadi, yangi `stock_lots` qatori yaratiladi. |
| QT-M04-02 | US-M04-02 | happy | **Berilgan** tovar qoldig'i `min_stock`dan past, **qachonki** tizim kunlik tekshiruvni bajarsa, **unda** Menejerga M18 orqali ogohlantirish ketadi. |
| QT-M04-03 | US-M04-03 | happy | **Berilgan** 2 filial mavjud, **qachonki** konsolidatsiyalangan hisobot ochilsa, **unda** har bir filial alohida va jami qoldiq ko'rsatiladi. |
| QT-M04-04 | US-M04-04 | happy | **Berilgan** yangi tenant, **qachonki** Egasi "Boshlang'ich qoldiq" (`stock-openings`) kiritsa, **unda** `stock_lots`/`stock_balances` boshlang'ich partiya bilan to'ldiriladi, `ledger_entries` yaratilmaydi (faqat registr, 2.21-band). |
| QT-M04-05 | US-M04-05 | happy — FIFO | **Berilgan** 2 kirim: 100 dona × `"8000.0000"` so'm, so'ng 50 dona × `"9000.0000"` so'm, **qachonki** 120 dona sotilsa, **unda** FIFO bo'yicha COGS = 100×8000 + 20×9000 = **`"980000.00"`** so'm, qoldiq = 30 dona × `"9000.0000"` = `"270000.00"` so'm (`13-provodka-qoidalari.md` §3.2). |
| QT-M04-06 | US-M04-05 | happy — AVECO | **Berilgan** xuddi shu 2 kirim, tenant usuli AVECO, **qachonki** 120 dona sotilsa, **unda** kirim 2'dan keyin `avg_cost = "8333.3333"`; COGS = 120 × 8333.3333 → yaxlitlab **`"1000000.00"`** so'm, qoldiq qiymati = `"1250000.00" − "1000000.00" = "250000.00"` so'm (eski qiymat − COGS formulasi, yaxlitlash qoldig'i to'planmasligi uchun). |
| QT-M04-07 | US-M04-06 | happy | **Berilgan** partiyada yaroqlilik muddatiga 7 kun qolgan, **qachonki** kunlik tekshiruv ishga tushsa, **unda** Egasi/Menejerga ro'yxat (tovar, partiya, qoldiq, muddat) M18 orqali boradi. |
| QT-M04-08 | US-M04-06 | negative | **Berilgan** tovar muddati o'tgan, **qachonki** Omborchi "Hisobdan chiqarish" hujjatini sabab bilan yaratsa, **unda** `stock_moves(qty=-N)`, `ledger_entries: Dt 9430/Kt 2910` = tannarx (javobgar shaxs yo'q holati). |
| QT-M04-09 | US-M04-05 | unit — qaytarish tannarxi (FIFO) | **Berilgan** QT-M04-05'dagi sotuv (`lot_allocations`: 100×`"8000.0000"` + 20×`"9000.0000"`), **qachonki** mijoz shu chekdagi 5 donani qaytarsa, **unda** qaytarish tannarxi **asl chek qatoridagi** tannarxda (`sale_lines.cost_amount/qty`) qabul qilinadi — joriy FIFO partiya narxida **emas**; `qty_left` asl partiyalarga teskari tartibda qaytadi, `unit_cost` o'zgarmaydi (`13-provodka-qoidalari.md` §3.2a). |
| QT-M04-10 | US-M04-05 | unit — qaytarish tannarxi (AVECO) | **Berilgan** QT-M04-06'dagi holat (`avg_cost="8333.3333"` sotuv paytida), keyinroq yangi kirim bilan `avg_cost` o'zgargan, **qachonki** mijoz 5 donani qaytarsa, **unda** qaytarish **asl chek qatoridagi birlik tannarxida** (`"8333.3333"`) kirim sifatida qo'shiladi va `avg_cost` shu asosda qayta hisoblanadi — **joriy** `avg_cost`da emas (§3.2a). |

**Misol — QT-M04-05 (FIFO) to'liq provodka ko'rinishi** (`13-provodka-qoidalari.md` §3.2, pytest assertsiyasi uchun yagona manba):

| # | Dt | Kt | Summa | Izoh |
|---|---|---|---|---|
| 1 | `9120` | `2910` | `"980000.00"` | COGS = 100×`"8000.0000"` + 20×`"9000.0000"` |

Qoldiq: 30 dona × `"9000.0000"` = `"270000.00"` (`stock_lots.qty_left=30`, Kirim 2'dan). **AVECO** (QT-M04-06) uchun bitta farq — summa: `Dt 9120 "1000000.00" / Kt 2910`, qoldiq qiymati `"250000.00"` (`qty × avg_cost` emas, balki `eski_qiymat − COGS`).

| QT-M04-11 | US-M04-01 | negative (manfiy qoldiq, offline) | **Berilgan** ikki qurilma bir-biridan bexabar offline rejimda oxirgi ma'lum qoldiqdagi bitta donani sotadi (`stock_balances.qty=0`), **qachonki** ikkinchi sotuv internet qaytganda sinxronlansa, **unda** sotuv **rad etilmaydi** (`status="accepted"`, `warnings=["STOCK_NEGATIVE"]`); `stock_balances.qty` manfiy bo'lishi mumkin, tannarx vaqtincha oxirgi ma'lum narxda (`pending_cost`) yoziladi va keyingi kirimda `recost_jobs` orqali tuzatiladi; BO-03'da "⚠ manfiy qoldiq" belgisi ko'rinadi (`13-provodka-qoidalari.md` §3.3). |

### M05 — Inventarizatsiya

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M05-01 | US-M05-01 | happy | **Berilgan** inventarizatsiya boshlangan (`stock-counts`), **qachonki** Omborchi har tovar bo'yicha haqiqiy sonni kiritsa, **unda** tizim haqiqiy son bilan tizimdagi qoldiqni solishtirib farqni ko'rsatadi (hali postlanmagan). |
| QT-M05-02 | US-M05-02 | happy | **Berilgan** farq ro'yxati tayyor — "Coca-Cola 1.5L" bo'yicha kamomad 3 dona, **qachonki** Menejer/Egasi tasdiqlasa (`POST /stock-counts/{id}/post`), **unda** `stock_balances.qty` haqiqiy songa moslashtiriladi. |
| QT-M05-03 | US-M05-03 | happy | **Berilgan** inventarizatsiya tasdiqlangan (kamomad 3 dona), **qachonki** buxgalteriya yozuvi yaratilsa, **unda** `Dt 4730/Kt 2910` (javobgar shaxs aniq) yoki `Dt 5910→9430/Kt 2910` (aniqlanmagan) — tannarx bo'yicha kamomad xarajat sifatida qayd etiladi. |
| QT-M05-04 | US-M05-03 | negative | **Berilgan** inventarizatsiya **hali submit qilinmagan** (`submit-for-review` bosqichida), **qachonki** `post` chaqirilsa, **unda** rad etiladi — holat mashinasi ketma-ketligi buzilmasligi kerak. |
| QT-M05-05 | US-M05-01 | happy (mobil skaner, offline) | **Berilgan** Omborchi Android POS bilan inventarizatsiya skanerlaydi, internet yo'q, **qachonki** har tovar skanerlansa, **unda** `stock_count.line_recorded` voqealari lokal yoziladi; internet qaytganda sinxronlanadi, lekin **yakuniy tasdiqlash** (`post`) faqat online bajariladi. |

### M06 — Ko'chirish

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M06-01 | US-M06-01 | happy | **Berilgan** "Asosiy ombor"dan boshqa filialga 10 dona yuborilmoqda, **qachonki** `POST /transfers/{id}/send` chaqirilsa, **unda** `ledger_entries: Dt 2970/Kt 2910` = tannarx, yuboruvchi ombor balansi "yo'lda" holatiga o'tadi. |
| QT-M06-02 | US-M06-02 | happy | **Berilgan** tovar manzilga yetib kelgan, **qachonki** qabul qiluvchi `POST /transfers/{id}/receive` bilan tasdiqlasa, **unda** `ledger_entries: Dt 2910/Kt 2970`, qabul qiluvchi ombor balansi oshadi, partiya (`unit_cost`) saqlanadi. |
| QT-M06-03 | US-M06-02 | negative | **Berilgan** jo'natilgan 10 dona, qabulda haqiqiy 8 dona kelgan, **qachonki** qabul qiluvchi 8 dona bilan tasdiqlasa, **unda** farq (2 dona) `Dt 5910/Kt 2970` sifatida yoziladi (yo'qotilgan qism), hujjatda farq belgilanadi. |
| QT-M06-04 | US-M06-01 | happy (offline) | **Berilgan** ichki (o'z filiallari orasidagi) ko'chirish, internet yo'q, **qachonki** jo'natish/qabul lokal amalga oshirilsa, **unda** hujjat append-only jurnalga yoziladi, internet qaytganda sinxronlanadi; 72 soatlik hisoblagich offline davrni ham hisobga oladi. |
| QT-M06-05 | US-M06-03 | negative | **Berilgan** ko'chirish 72 soatdan ortiq "yo'lda" holatida, **qachonki** Menejer ro'yxatni ochsa, **unda** shu ko'chirish "kechikkan" deb belgilanadi va huquqiy xavf ogohlantirishi ko'rsatiladi (M12 hisobotida ham). |
| QT-M06-06 | US-M06-01 | negative (markirovka, offline) | **Berilgan** "Hayot suvi 1.5L" (markirovkalangan) boshqa filialga offline ko'chirilmoqda — bu M02'dagi qaytarish siyosatidan **farq qiladi**, **qachonki** jo'natish/qabul lokal bajarilsa, **unda** **ruxsat etiladi** (egalik o'zgarmaydi, tenant ichida), 72 soatlik taymer offline davrni ham hisobga olib ishlaydi (= QT-M06-04, aniqlik uchun qaytarish bilan solishtirish). |

### M07 — Xarid

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M07-01 | US-M07-01 | happy | **Berilgan** kam qolgan tovar aniqlangan, **qachonki** Menejer `POST /purchase-orders` orqali xaridnoma yaratsa, **unda** hujjat `draft`da yaratiladi; `POST /purchase-orders/{id}/send` bilan "yuborilgan" holatga o'tadi. |
| QT-M07-02 | US-M07-02 | happy | **Berilgan** xaridnomada 50 dona buyurtma qilingan, **qachonki** Omborchi `POST /goods-receipts` orqali haqiqiy 48 dona kiritib tasdiqlasa, **unda** farq (2 dona kam) belgilanadi, `stock_balances` 48 donaga oshadi. |
| QT-M07-03 | US-M07-03 | happy | **Berilgan** faktura `"1120000.00"` so'm (QQS bilan, nasiyaga), **qachonki** `POST /goods-receipts/{id}/post` bajarilsa, **unda** `ledger_entries: Dt 2910/Kt 6010="1000000.00"` (QQSsiz), `Dt 4410/Kt 6010="120000.00"` (kiritiladigan QQS) — yig'indi `Kt 6010="1120000.00"` (`13-provodka-qoidalari.md` §2.6). |
| QT-M07-04 | US-M07-03 | negative | **Berilgan** faktura **"qizil"** (yuqori xavfli) deb belgilangan, **qachonki** qabul `post` qilinsa, **unda** `Dt 4410` (kiritiladigan QQS) yozuvi **to'lovgacha yozilmaydi**; `vat_moves(kind=input)` ham yozilmaydi (VM Qarori №830). |
| QT-M07-05 | US-M07-04 | happy | **Berilgan** yetkazib beruvchiga kreditorlik `"1120000.00"` ochiq, **qachonki** Buxgalter `"1120000.00"` to'lov qilsa, **unda** `ledger_entries: Dt 6010/Kt 5110="1120000.00"`, kreditorlik balansi `"0.00"`ga tushadi; agar faktura qizil bo'lsa — shu tranzaksiyada kechiktirilgan `Dt 4410/Kt 6010` QQS yozuvi ham qo'shiladi. |
| QT-M07-06 | US-M07-05 | happy | **Berilgan** tovar muddati o'tgan, shu yetkazib beruvchidan kirim qilingan, **qachonki** Omborchi "Yetkazib beruvchiga qaytarish" hujjatini yaratsa, **unda** ombor qoldig'i kamayadi, yetkazib beruvchiga qarzimiz shu summaga kamayadi (yoki qarz yo'q bo'lsa — ular bizga qarzdor bo'ladi). |
| QT-M07-07 | US-M07-02 | negative | **Berilgan** xaridnoma allaqachon `status="cancelled"`, **qachonki** shu xaridnomaga `POST /goods-receipts` yaratishga urinilsa, **unda** `409 PURCHASE_ORDER_CLOSED`. |
| QT-M07-08 | US-M07-02 | negative (bonus tovar) | **Berilgan** yetkazib beruvchi "10+1 tekin" bonus bergan, **qachonki** qabul qilinsa, **unda** bonus qator **0 narx bilan alohida partiya** sifatida yoziladi; AVECO tanlangan bo'lsa `avg_cost` shu qo'shimcha 0-narxli miqdor hisobiga mos pasayadi. |

### M08 — Nasiya (mijoz qarzi)

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M08-01 | US-M08-01 | happy | **Berilgan** mijoz joriy qarzi `"0.00"`, kredit limiti `"500000.00"`, **qachonki** `"300000.00"`lik sotuv "nasiya" bilan yakunlansa, **unda** `debt_moves(direction='receivable', amount=+300000.00)`, `sales.status='deferred'`, **fiskal chek chiqarilmaydi** (`fiscal_receipts` yozuvi yo'q). |
| QT-M08-02 | US-M08-01 | negative | **Berilgan** mijoz joriy qarzi `"450000.00"`, limit `"500000.00"`, **qachonki** `"100000.00"`lik yangi nasiya (jami `"550000.00"` limitdan oshadi) so'ralsa online rejimda, **unda** rad etiladi yoki Menejer tasdig'i so'raladi (`DEBT_LIMIT_EXCEEDED`). |
| QT-M08-03 | US-M08-01 | negative (offline) | **Berilgan** offline rejim, oxirgi ma'lum qoldiq bo'yicha limitdan oshib ketish aniqlangan, **qachonki** kassir baribir sotishni tanlasa, **unda** sotuv **bloklanmaydi** — `debt_moves.limit_exceeded=true` bayrog'i bilan yoziladi, internet qaytganda Egasiga xabar (M18) boradi. |
| QT-M08-04 | US-M08-02 | happy | **Berilgan** Menejer mijoz limitini `"500000.00"`dan `"800000.00"`ga o'zgartiradi, **qachonki** saqlansa, **unda** yangi limit darhol kuchga kiradi va barcha kassalarga sinxronlanadi. |
| QT-M08-05 | US-M08-03 | happy | **Berilgan** mijoz qarzi to'lov muddatidan o'tgan, **qachonki** tizim kunlik tekshirsa, **unda** AI-06 orqali tayyorlangan eslatma matni taklif qilinadi (odam tasdiqlamaguncha yuborilmaydi). |
| QT-M08-06 | US-M08-04 | happy | **Berilgan** mijoz qarzi `"300000.00"`, **qachonki** `"300000.00"` naqd to'lasa, **unda** `debt_moves(direction='receivable', amount=-300000.00)`, `ledger_entries: Dt 5010/Kt 4010="300000.00"`, **`fiscal_receipts.kind='debt_settlement'`** yaratiladi — tovar qatorlari yopilgan sotuvdan proporsional olinadi. |
| QT-M08-07 | US-M08-04 | negative (qisman) | **Berilgan** mijoz qarzi `"300000.00"`, **qachonki** `"100000.00"` qisman to'lasa, **unda** qoldiq qarz `"200000.00"` saqlanadi, `debt_settlement` cheki faqat `"100000.00"`ga chiqadi. |
| QT-M08-08 | US-M08-05 | happy | **Berilgan** mijoz ro'yxatda yo'q, **qachonki** Kassir POS'da "Qarzga" tugmasi bilan faqat ism+telefon kiritib yangi mijoz yaratsa, **unda** 2-3 soniyada sotuv mijoz qarziga yoziladi, limit belgilanmagani uchun tekshiruv o'tkazilmaydi. |
| QT-M08-09 | US-M08-06 | happy | **Berilgan** mijozda bir nechta qarz/to'lov yozuvi, **qachonki** "Qarz daftari" ochilsa, **unda** sana bo'yicha har bir qarz (summa, tovarlar, kim berdi) va joriy qoldiq ko'rinadi; holat ochiq/qisman/to'liq yopilgan to'g'ri hisoblanadi. |
| QT-M08-10 | US-M08-07 | happy | **Berilgan** yangi tenant, **qachonki** Egasi "Boshlang'ich qarzlar" orqali mijoz uchun `"150000.00"` kiritsa, **unda** `debt_openings` → `ledger_entries: Dt 4010/Kt 8720="150000.00"`, tovar tarkibisiz, chek chiqarilmaydi. |
| QT-M08-11 | US-M08-09 | happy | **Berilgan** mijozning 2 ochiq qarzi (eski — `"100000.00"`, yangi — `"200000.00"`), **qachonki** `"100000.00"` to'lov kelsa, **unda** summa **eng eski qarzdan** boshlab yopiladi (`debt_payment_allocations`), eski qarz to'liq yopiladi, yangi qarz o'zgarmaydi. |
| QT-M08-12 | US-M08-10 | negative | **Berilgan** mijoz qarzi 65 kun davomida to'lanmagan, **qachonki** kunlik tekshiruv ishga tushsa, **unda** 60+ kunlik ro'yxatga tushadi va Egasiga **faqat eslatma** ketadi — tizim **o'zi avtomatik** "shubhali qarz" deb belgilamaydi (bu faqat Egasi qo'l bilan, sabab ko'rsatib bajaradigan amal). |
| QT-M08-13 | US-M08-10 | happy (writeoff) | **Berilgan** Egasi qarzni sabab bilan "kechirish" qiladi (`"150000.00"`), **qachonki** `debt_writeoffs` `post` qilinsa, **unda** `ledger_entries: Dt 9430 (yoki 4910)/Kt 4010="150000.00"`, audit jurnaliga yoziladi — faqat Egasi ruxsati. |
| QT-M08-14 | US-M08-11 | happy | **Berilgan** yetkazib beruvchidan nasiyaga xarid qilingan, **qachonki** Egasi "Men qarzdorman" daftarini ochsa, **unda** kimga/qancha/qachon to'lash ko'rinadi; to'lov BP-12 orqali yopiladi. |

**Misol — QT-M08-06/07 (`debt_settlement` proporsional allokatsiya)** (`18-api-kassa.md` §12.2, pytest assertsiyasi uchun yagona manba): mijozning ochiq qarzi ikki sotuvdan iborat — `S1` (`"200000.00"`, QQS ichida) va `S2` (`"100000.00"`), jami `"300000.00"`; to'lov `"150000.00"` keladi (eng eski, `S1`'dan boshlab):

| # | Allokatsiya | Summa | Izoh |
|---|---|---|---|
| 1 | `S1`ga | `"150000.00"` | `S1` to'liq yopilmaydi (200000−150000=50000 qoladi) |
| 2 | `S2`ga | `"0.00"` | Navbat yetmadi |

`fiscal_receipts(kind='debt_settlement')` summasi `"150000.00"`, tovar qatorlari **faqat `S1`**ning `sale_lines`idan (150000/200000 = 75% ulush bo'yicha proporsional) olinadi — `S2` qatorlari chekka kirmaydi (hali yopilmagan).

### M09 — Narxlar

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M09-01 | US-M09-01 | happy | **Berilgan** tovar joriy narxi `"12000.00"`, **qachonki** Menejer yangi narx `"13000.00"` kiritsa (`valid_from` bilan), **unda** eski narx tarix yozuviga ko'chadi, yangisi amal qilish sanasi bilan saqlanadi. |
| QT-M09-02 | US-M09-02 | negative | **Berilgan** narx o'zgarishi belgilangan limitdan (±10%, `26-ochiq-savollar-reestri.md` #5) katta, **qachonki** Menejer kiritsa, **unda** `price_changes.status='pending_approval'` (BO-16 navbatiga tushadi), Egasi tasdiqlamaguncha kuchga kirmaydi; rad etilsa sabab yoziladi. |
| QT-M09-03 | US-M09-03 | happy | **Berilgan** kassa ekrani ochiq, **qachonki** tovar tanlansa, **unda** joriy narx ko'rsatiladi, tahrirlash tugmasi Kassir uchun faol emas. |
| QT-M09-04 | US-M09-04 | happy | **Berilgan** 3 tovar narxi o'zgargan, hali yorlig'i chop etilmagan, **qachonki** Menejer "Yorliqlar" bo'limini ochsa, **unda** shu 3 tovar ro'yxatda chiqadi; tanlab chop etilgach belgilanadi. |
| QT-M09-05 | US-M09-05 | happy | **Berilgan** tovar shtrix-kodsiz, **qachonki** "Ichki shtrix-kod yaratish" bosilsa, **unda** tenant ichida noyob kod yaratiladi, ishlab chiqaruvchi diapazoni bilan to'qnashmaydi. |
| QT-M09-06 | US-M09-06 | happy | **Berilgan** "Mol go'shti (kg)" uchun tarozi yorlig'i (EAN-13 "2x" prefiks, og'irlik kodlangan), **qachonki** kassir skanerlasa, **unda** POS kod ichidan tovar va og'irlikni ajratib to'g'ri miqdor va summa bilan chekka qo'shadi. |
| QT-M09-07 | US-M09-07 | happy | **Berilgan** mijoz kartasida doimiy chegirma `"10.00"`% belgilangan, **qachonki** shu mijozga sotuv qilinsa, **unda** chegirma avtomatik qo'llanadi (QT-M03-04 bilan bir xil "eng foydali bittasi" qoidasi). |
| QT-M09-08 | US-M09-01 | negative (shtrix-kod takrori) | **Berilgan** shtrix-kod `"4780000000012"` "Coca-Cola 1.5L"da bor, **qachonki** shu kod "Mol go'shti (kg)"ga ham berilmoqchi bo'lsa, **unda** `409 BARCODE_DUPLICATE`. |
| QT-M09-09 | US-M03-02-ga yaqin (M09 chekka holat) | negative (aksiya muddati) | **Berilgan** aksiya narxi `valid_to="2026-10-14"` bilan tugagan, **qachonki** 2026-10-15'da sotuv qilinsa, **unda** aksiya **avtomatik tugaydi**, chekka asl narx qo'llaniladi — offline qurilmada eski qoida qolgan bo'lsa, server posting vaqtida qayta tekshiradi. |

### M10 — QQS

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M10-01 | US-M10-01 | happy | **Berilgan** tovar `vat_rate=12.00`, **qachonki** sotuv amalga oshsa, **unda** QQS summasi avtomatik hisoblanib chekka va `ledger_entries`ga (`Kt 6410`) kiradi. |
| QT-M10-02 | US-M10-02 | happy | **Berilgan** davlat QQS hisoboti my.soliq.uz'da e'lon qilingan va ichki hisobga mos keladi, **qachonki** Buxgalter uni kiritsa, **unda** holat `kutilmoqda → mos keladi`ga o'tadi. |
| QT-M10-03 | US-M10-02 | negative | **Berilgan** davlat hisoboti ichki hisobdan farq qiladi, **qachonki** Buxgalter kiritsa, **unda** holat `farq topildi`ga o'tadi, **1-, 3-, 4-kun**larda ogohlantirish yuboriladi; **qachonki** **5 kalendar kun** ichida javob berilmasa, **unda** holat `avtomatik qabul qilingan`ga o'tadi (Soliq kodeksi 81-modda). |
| QT-M10-04 | US-M10-03 | happy | **Berilgan** faktura "qizil" deb belgilangan, **qachonki** Buxgalter QQS hisobotini tayyorlasa, **unda** bu faktura alohida ko'rsatiladi, krediti "hali tasdiqlanmagan" deb belgilanadi. |
| QT-M10-05 | US-M10-04 | happy | **Berilgan** tenant aylanma solig'i rejimida (`regime='turnover'`), filial `settlement_category='city_100k_plus'`, **qachonki** oy yakunida hisoblansa, **unda** stavka **4%** qo'llaniladi (467-modda), QQS/`vat_moves` yozuvlari yaratilmaydi. |
| QT-M10-06 | US-M10-01 | unit (formula) | **Berilgan** `price="3000.00"` (QQS kiritilgan), `vat_rate="12.00"`; **qachonki** `vat_amount = ROUND_HALF_UP(price × rate/(100+rate), 2)` hisoblansa, **unda** natija aynan `"321.43"` (3000×12/112=321.4285714…→ yarim yuqoriga yaxlitlash), sof summa `"2678.57"` (`01-qarorlar.md` #26, `13-provodka-qoidalari.md` §2.1 izohi). |

### M11 — Buxgalteriya

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M11-01 | US-M11-01 | happy | **Berilgan** sotuv yakunlangan, **qachonki** tizim buxgalteriya modulini ishga tushirsa, **unda** kassa/hisob-kitob/tovar-moddiy zaxira/QQS/daromad hisoblari bo'yicha ikki tomonlama (`Dt`=`Kt`) yozuv avtomatik yaratiladi. |
| QT-M11-02 | US-M11-02 | happy | **Berilgan** oy yakunlanmoqda, barcha `recost_jobs` tugagan, **qachonki** Buxgalter "oy yopish"ni boshlasa, **unda** `period_closings` yozuvi yaratiladi, balans/P&L hisoboti shakllanadi. |
| QT-M11-03 | US-M11-02 | negative | **Berilgan** oy allaqachon yopilgan (`period_closings` mavjud), **qachonki** shu davrga tegishli yangi `ledger_entries` yozishga (yoki `recost_job`) urinilsa, **unda** `409 PERIOD_CLOSED` bilan rad etiladi; tuzatish faqat **joriy ochiq oyda**, storno+tuzatuvchi yozuv bilan kiritiladi, asl yopilgan davr o'zgarmaydi. |
| QT-M11-04 | US-M11-03 | happy | **Berilgan** tanlangan davr, **qachonki** Egasi dashboard'ni ochsa, **unda** aylanma, xarajat, sof foyda sodda raqamlar sifatida ko'rsatiladi. |
| QT-M11-05 | US-M11-02 | negative (tayyor emas) | **Berilgan** davrda tugallanmagan `recost_jobs` yoki hali OFD'ga yuborilmagan offline chek bor, **qachonki** `POST /period-closings` chaqirilsa, **unda** `409 PERIOD_CLOSE_NOT_READY`, `params.blockers` ro'yxati bilan (`20-api-moliya-admin.md`). |
| QT-M11-06 | US-M11-02 | negative (qayta yopish) | **Berilgan** davr allaqachon yopilgan, **qachonki** `POST /period-closings` yana shu davr uchun chaqirilsa, **unda** `409 PERIOD_ALREADY_CLOSED`. |

### M12 — Hisobotlar

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M12-01 | US-M12-01 | happy | **Berilgan** kun davomida 2 filialda savdo bo'lgan, **qachonki** Egasi kunlik hisobotni ochsa, **unda** jami savdo, chek soni, o'rtacha chek summasi filial bo'yicha ajratib ko'rsatiladi. |
| QT-M12-02 | US-M12-02 | happy | **Berilgan** tanlangan davr, **qachonki** Menejer hisobot so'rasa, **unda** tovarlar sotuv miqdori bo'yicha kamayish tartibida ro'yxatlanadi. |
| QT-M12-03 | US-M12-03 | happy | **Berilgan** M10 solishtirish yakunlangan, **qachonki** Buxgalter "eksport"ni bossa, **unda** hisobot Excel/PDF formatda yuklab olinadi. |
| QT-M12-04 | US-M12-01 | negative | **Berilgan** ba'zi offline qurilmalar hali sinxronlanmagan, **qachonki** Egasi hisobotni ochsa, **unda** "faqat sinxronlangan ma'lumot" ogohlantirishi ko'rsatiladi, raqamlar to'liq emasligi aniq belgilanadi. |
| QT-M12-05 | US-M12-03 | negative (eksport muddati) | **Berilgan** eksport job yaratilgan, 24 soatdan ko'p vaqt o'tgan, **qachonki** eski `file_url` orqali yuklab olinsa, **unda** signed URL muddati tugagan (`403`/`410`-ga mos xato) — foydalanuvchi eksportni qaytadan so'rashi kerak. |

### M13 — Huquqlar

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M13-01 | US-M13-01 | happy | **Berilgan** yangi xodim ma'lumoti kiritilgan, **qachonki** Egasi "Kassir" rolini belgilasa, **unda** xodim shu rolga mos `role_permissions` ruxsatlarini oladi. |
| QT-M13-02 | US-M13-02 | happy | **Berilgan** xodimga "Kassir" va "Omborchi" ikkala rol berilgan, **qachonki** u login qilsa, **unda** ikki rolning jamlangan huquqlariga ega bo'ladi (yuqori huquq ustun, M13 chekka holat). |
| QT-M13-03 | US-M13-03 | happy | **Berilgan** Menejer `discount.give.limit_value`ni `"5.00"`dan `"8.00"`ga o'zgartiradi, **qachonki** saqlansa, **unda** yangi limit tegishli rol/xodim uchun darhol kuchga kiradi. |
| QT-M13-04 | US-M13-04 | happy | **Berilgan** Egasi yangi xodim qo'shadi (telefon, ism, rol, filial), **qachonki** saqlansa, **unda** bir martalik taklif kodi (OTP, `purpose=invite`) Telegram (birinchi) yoki SMS (zaxira) orqali yuboriladi; parol/PIN hech qachon ochiq matnda yuborilmaydi. |
| QT-M13-05 | US-M13-05 | happy | **Berilgan** xodim ro'yxatda tanlangan, **qachonki** Egasi "Bloklash"ni bossa, **unda** xodimning barcha faol sessiyalari darhol bekor qilinadi (QT-OAUTH-07), u login qila olmaydi toki blokdan chiqarilmaguncha. |
| QT-M13-06 | US-M13-06 | happy | **Berilgan** xodim parolini unutgan, **qachonki** Egasi "Parolni tiklash" bossa, **unda** eski parol/PIN bekor qilinadi, barcha sessiyalar tugatiladi, bir martalik tiklash kodi (`purpose=admin_reset`) yuboriladi. |
| QT-M13-07 | US-M13-07 | happy | **Berilgan** xodimning 2 faol sessiyasi bor, **qachonki** Egasi bittasini "Bekor qilish" bossa, **unda** shu sessiyaning tokeni darhol bekor qilinadi, **ikkinchisiga ta'sir qilmaydi**. |
| QT-M13-08 | US-M13-08 | happy | **Berilgan** platforma admin paneli, **qachonki** admin tenant Egasi hisobini bloklasa/parolini tiklasa, **unda** amal bajariladi; **lekin** admin oddiy Kassir/Menejer/Buxgalter ma'lumotiga **kira olmaydi** (faqat Egasi/obuna darajasi). |
| QT-M13-09 | US-M13-03 | negative | **Berilgan** Egasi o'zining yagona hisobini bloklashga urinmoqda, **unda** tizim rad etadi (tenant egasiz qolib ketmasin); faqat platforma admin orqali tiklash yo'li saqlanadi. |

### M14 — Filiallar

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M14-01 | US-M14-01 | happy | **Berilgan** 2 filial mavjud, **qachonki** Egasi umumiy dashboard'ni ochsa, **unda** har bir filial alohida va jami ko'rinishda ko'rsatiladi. |
| QT-M14-02 | US-M14-03 | happy | **Berilgan** biznes yangi do'kon ochyapti, **qachonki** Egasi yangi filialni (nom, manzil, kassa soni) ro'yxatdan o'tkazsa, **unda** filial tenant ichida yangi mustaqil ombor/kassa birligi sifatida yaratiladi. |
| QT-M14-03 | US-M14-04 | happy | **Berilgan** yangi filial yaratilmoqda, **qachonki** Egasi "aholi punkti toifasi"ni "Boshqa aholi punkti" deb tanlasa, **unda** aylanma solig'i stavkasi **2%** qo'llanadi (`branch_tax_settings`, `valid_from` bilan). |
| QT-M14-04 | US-M14-04 | negative | **Berilgan** toifa tanlanmagan, **qachonki** filial saqlansa, **unda** standart qiymat "Shahar, 100 ming+" (**4%**, eng ehtiyotkor) qo'yiladi va Egasiga tekshirish eslatmasi ko'rsatiladi. |
| QT-M14-05 | US-M14-04 | unit (tarix) | **Berilgan** filial toifasi `"other"`dan `"city_100k_plus"`ga `valid_from="2026-11-01"` bilan o'zgartirilgan, **qachonki** 2026-10 oyi uchun aylanma solig'i hisoblansa, **unda** **eski** toifa (`"other"`, 2%) qo'llanadi — o'tgan davrlar qayta hisoblanmaydi (`branch_tax_settings` tarix bilan saqlanadi). |

### M15 — Xarajatlar

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M15-01 | US-M15-01 | happy | **Berilgan** "Xarajat qo'shish" ochilgan, **qachonki** summa `"500000.00"`, toifa "Ijara", manba "kassa naqdi" kiritilsa, **unda** `expenses` yoziladi va M16'da avtomatik "kassadan chiqim" (`cash_moves`, `direction=out`) yaratiladi, `ledger_entries: Dt 9410/Kt 5010="500000.00"`. |
| QT-M15-02 | US-M15-02 | happy | **Berilgan** oylik ijara takrorlanuvchi xarajat sifatida sozlangan, **qachonki** muddat kelsa, **unda** "Ijara to'lash vaqti: 3 000 000 so'm" eslatmasi beriladi, Egasi bir bosishda tasdiqlaydi (avtomatik to'lanmaydi). |
| QT-M15-03 | US-M15-03 | happy | **Berilgan** davr tanlangan, sotuv tushumi, COGS va xarajatlar ma'lum, **qachonki** dashboard ochilsa, **unda** Sof foyda = Sotuv tushumi − COGS − Xarajatlar formulasi bo'yicha, toifalar taqsimoti bilan ko'rsatiladi. |
| QT-M15-04 | US-M15-01 | negative | **Berilgan** xarajat allaqachon `post` qilingan, **qachonki** Egasi uni "bekor qilsa", **unda** yozuv **o'chirilmaydi** — teskari (storno) yozuv bilan bekor qilinadi, audit jurnaliga tushadi. |
| QT-M15-05 | US-M15-01 | negative (limit) | **Berilgan** xarajat summasi Menejer uchun belgilangan `expenses.approve.limit_value`dan katta, **qachonki** `POST /expenses/{id}/post` chaqirilsa, **unda** `403 EXPENSE_LIMIT_EXCEEDED` yoki `202 APPROVAL_REQUIRED` (`kind='expense_over_limit'`) — Egasi cheksiz limit bilan muammosiz o'tkazadi (QT-PERM-01). |

### M16 — Kassa pul harakati (naqd)

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M16-01 | US-M16-01 | happy | **Berilgan** smena ochiq, **qachonki** Kassir `"40000.00"` kassadan "Boshqa" sababi bilan olsa (limit `"50000.00"`dan past), **unda** tasdiqsiz o'tadi, `cash_moves(amount=-40000.00, method='cash')` yoziladi. |
| QT-M16-02 | US-M16-01 | negative | QT-PERM-05 bilan bir xil (`"50001.00"` — tasdiq talab qilinadi). |
| QT-M16-03 | US-M16-02 | happy | **Berilgan** smena yopilmoqda: boshlang'ich naqd `"200000.00"`, naqd sotuvlar `"350000.00"`, naqd qarz to'lovlari `"50000.00"`, qo'yilgan `"0.00"`, olingan `"40000.00"`, **qachonki** sanalgan naqd `"560000.00"` kiritilsa, **unda** kutilgan naqd = 200000+350000+50000−40000 = `"560000.00"`, farq `"0.00"`. |
| QT-M16-04 | US-M16-03 | happy | **Berilgan** tanlangan davr, **qachonki** "Kassa harakati" hisoboti ochilsa, **unda** har smena bo'yicha boshlanish/sotuv/qo'yilgan-olingan/kutilgan-sanalgan/farq to'liq ko'rinadi. |
| QT-M16-05 | US-M16-02 | happy (karta jami) | **Berilgan** smenada qo'lda belgilangan "Karta" to'lovlari jami `"450000.00"` (3 ta `terminal_ref` bilan), **qachonki** smena yopilsa, **unda** Z-hisobotda naqd bilan bir qatorda **"karta" jami** `"450000.00"` alohida ko'rsatiladi (`counted_card_total`), Egasi buni bank ko'chirmasi bilan solishtiradi. |

### M17 — Obuna va ro'yxatdan o'tish

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M17-01 | US-M17-01 | happy | **Berilgan** yangi foydalanuvchi telefon+parol bilan ro'yxatdan o'tmoqda, Telegram ulanmagan, **qachonki** OTP so'ralsa, **unda** SMS zaxira orqali 6 xonali kod yuboriladi (5 daqiqa TTL); tasdiqlangach `users`, `subscriptions(status='trial', 30 kun)` yaratiladi. |
| QT-M17-02 | US-M17-01 | happy (Google) | **Berilgan** foydalanuvchi "Google bilan kirish"ni tanlaydi, **qachonki** OIDC oqimi muvaffaqiyatli yakunlansa, **unda** `user_identities` yozuvi yaratiladi, alohida parol/OTP talab qilinmaydi, 30 kunlik sinov boshlanadi. |
| QT-M17-03 | US-M17-02 | happy | **Berilgan** Egasi qo'shimcha kassa qo'shmoqchi, **qachonki** "Qo'shimcha kassa qo'shish" bosilsa, **unda** `"39000.00"` so'm/oy obuna summasiga qo'shiladi, keyingi to'lovdan qo'llanadi. |
| QT-M17-04 | US-M17-02 | negative | **Berilgan** faol kassalar soni 3 (1 asosiy + 2 qo'shimcha), **qachonki** Egasi qo'shimchalardan voz kechib yangi sonni 1ga tushirsa, **unda** ortiqcha 2 kassa arxivlanishi so'raladi, ularning tarixi **o'chirilmaydi**. |
| QT-M17-05 | US-M17-04 | happy | **Berilgan** platforma admin paneli, **qachonki** admin pilot tenant uchun obuna muddatini qo'lda uzaytirsa, **unda** `POST /platform/tenants/{id}/extend-subscription` orqali `billing_payments` qatori yaratilmasdan `current_period_end` uzayadi. |
| QT-M17-06 | US-M17-01 | negative (OTP kanal) | **Berilgan** foydalanuvchi telefon raqami hali Telegram botga ulanmagan, SMS provayder (Eskiz) ham vaqtincha ishlamayapti, **qachonki** OTP so'ralsa, **unda** `503 OTP_CHANNEL_UNAVAILABLE` (ikkisi ham muvaffaqiyatsiz) — ro'yxatdan o'tish yakunlanmaydi. |
| QT-M17-07 | US-M17-02 | negative (webhook idempotentlik) | **Berilgan** Click/Payme webhook `provider_tx_id=TX1` bilan allaqachon `billing_payments`da qayd etilgan, **qachonki** tashqi tizim xuddi shu `TX1` bilan webhookni **qayta** yuborsa (tarmoq retry), **unda** server eski natijani `200` bilan qaytaradi, ikkinchi marta `subscriptions.current_period_end` **oshirilmaydi**. |

### M18 — Bildirishnomalar va Telegram bot

| ID | US | Turi | Ssenariy va kutilgan natija |
|---|---|---|---|
| QT-M18-01 | US-M18-01 | happy | **Berilgan** back-office'da "Telegram ulash" bosilgan, **qachonki** Egasi bot havolasini ochib "Start" bossa, **unda** akkaunt bir martalik kod orqali tenantga bog'lanadi (`telegram_links`). |
| QT-M18-02 | US-M18-02 | happy | **Berilgan** kun yopilgan, **qachonki** belgilangan soat kelsa, **unda** bot kechqurungi hisobotni yuboradi: bugungi savdo, sof foyda (M15), naqd (M16), yangi/qaytgan qarzlar, ertangi qarzdorlar (M08). |
| QT-M18-03 | US-M18-03 | happy | **Berilgan** smena yopilganda kassa farqi topilgan (M16), **qachonki** shu hodisa bo'lsa, **unda** Egasiga darhol Telegram xabari ketadi (yoqilgan bo'lsa). |
| QT-M18-04 | US-M18-04 | happy | **Berilgan** bot ulangan, **qachonki** Egasi "Bugun qancha sotdik?" deb yozsa, **unda** AI-01 orqali tool-chaqiruv + raqamli nazoratdan o'tgan javob qaytadi, AI oylik limitidan hisoblanadi. |
| QT-M18-05 | US-M18-01 | negative | **Berilgan** xodim Telegram'ga ulangan, keyin Egasi uni tizimdan o'chiradi, **qachonki** o'chirish amalga oshsa, **unda** uning Telegram ulanishi ham bekor qilinadi, ulanmagan chatga hech narsa yuborilmaydi. |
| QT-M18-06 | US-M18-03 | happy (ogohlantirish yoqish/o'chirish) | **Berilgan** Egasi "kam qolgan tovar" ogohlantirishini `notification-settings`da **o'chirgan**, **qachonki** `P1` qoldig'i minimal chegaraga tushsa, **unda** M04'dagi ichki bayroq/ro'yxat baribir yaratiladi (BO-03'da ko'rinadi), lekin Telegram/SMS orqali **xabar yuborilmaydi** (foydalanuvchi o'z xohishi bilan o'chirgan kanal). |

---

## 3. AI qabul mezonlari (`09-ai-funksiyalar.md`, `22-ai-qatlami.md`)

| ID | Daraja | Ssenariy |
|---|---|---|
| QT-AI-01-01 | integration | **Berilgan** AI-01 eval to'plami (`backend/ai/eval/ai01_qna/cases.jsonl`, 50–100 holat, lotin/kirill/rus aralash), **qachonki** CI regression gate ishga tushsa, **unda** har javobdagi **har bir raqam** tool natijasi bilan **100%** mos kelishi shart (nol tolerantlik) — bironta holat mos kelmasa, merge **bloklanadi**. |
| QT-AI-01-02 | integration | **Berilgan** "Bugun qancha sotdik?" / "бугунги savdo qancha?" / "сколько продали сегодня?" uch xil tildagi bir xil savol, **qachonki** AI-01 chaqirilsa, **unda** uchtasi ham bir xil whitelisted tool'ga map qilinishi va bir xil raqamli javob berishi kutiladi. |
| QT-AI-03-01 | integration | **Berilgan** 100 ta O'zbekiston hujjatidan iborat test to'plami (≈40% toza, 40% foto/skaner, 20% qo'lda yozilgan; lotin/kirill/rus), **qachonki** AI-03 OCR quvuri ishga tushirilsa, **unda** maydon aniqligi: **summa ≥95%**, **sana ≥90%**, **miqdor va tovar nomi ≥80%**; shu to'plamda summa yoki sana **90%dan past** chiqsa — AI-03 **pilotga chiqarilmaydi** (ishga tushirish shartining o'zi). |
| QT-AI-03-02 | integration | **Berilgan** OCR natijasida bir maydon ishonch darajasi field-chegaradan past, **qachonki** foydalanuvchiga ko'rsatilsa, **unda** shu maydon **sariq** (past ishonchli) deb belgilanadi va qo'lda tasdiqlash/tahrir talab qilinadi — tasdiqsiz avtomatik `post` qilinmaydi. |
| QT-AI-03-03 | unit | **Berilgan** AI-03 qamrovi (faqat: QQS to'lovchi bo'lmagan yetkazib beruvchining qog'oz yuk xati / texnik uzilishdagi qog'oz faktura / qaytarish uchun qog'oz chek), **qachonki** standart QQS to'lovchilar o'rtasidagi elektron e-faktura/e-TTN yuklansa, **unda** bu hujjat AI-03 orqali **emas**, EDO operatori import yo'li orqali kiradi (chegara tekshiruvi). |
| QT-AI-05-01 | integration | **Berilgan** AI-05 eval to'plami, **qachonki** CI gate ishga tushsa, **unda** raqamli nazorat o'tish darajasi **100%** (nol tolerantlik) va har javobda manba hujjatga to'g'ri havola ko'rsatilishi talab qilinadi. |
| QT-AI-06-01 | integration | **Berilgan** AI-06 (qarz eslatmasi) matn generatsiyasi, **qachonki** natija tekshirilsa, **unda** matndagi **har bir raqam** (summa, sana) kod tomonidan **qo'yilgan** bo'lishi shart — AI tomonidan "to'qib chiqarilgan" (0 ta) raqam bo'lmasligi (metrika: fabricated-number count = 0). |
| QT-AI-LIMIT-01 | integration | **Berilgan** tenant oylik AI token limiti (`"2500000"` token, standart tarif) tugagan, **qachonki** yangi AI so'rovi yuborilsa, **unda** `hard-stop` — foydalanuvchiga "bu oy uchun AI limiti tugadi" xabari, **overage yo'q**; kassa/ombor/buxgalteriya **to'liq ishlayveradi** (AI bilan bog'liq emas). |
| QT-AI-GUARD-02 | integration | **Berilgan** Claude API ishlamay qolgan (timeout/5xx/circuit breaker ochiq), **qachonki** bir necha urinishdan keyin ham muvaffaqiyatsiz bo'lsa, **unda** AI-01 uchun "AI hozir javob bera olmayapti" xabari, AI-05/06 uchun ko'rsatma **AI matnisiz, faqat kod raqami** bilan ko'rsatiladi; `ai_requests.status='failed'` loglanadi. |
| QT-AI-GUARD-04 | unit | **Berilgan** AI-01'ga "Bugun eng ko'p sotgan kassir kim va u nega ishdan ketmoqchi?" kabi mavjud tool/ma'lumot bazasida **javobi yo'q** savol beriladi, **qachonki** model javob bersa, **unda** raqam/fakt **to'qib chiqarilmaydi** — model "bu haqda ma'lumotim yo'q" deb javob berishi kutiladi (hallucination guard, raqam promptdan tashqarida generatsiya qilinmasligi). |
| QT-AI-OCR-01 | integration | **Berilgan** AI-03 OCR'ga yuklangan rasm **o'qib bo'lmaydigan** (butunlay qora/noaniq); **qachonki** `POST /ai/ocr/jobs/{job_id}` natijasi so'ralsa, **unda** `ai_ocr_jobs.status='failed'`, `error_code=OCR_IMAGE_UNREADABLE`, foydalanuvchiga "aniqroq suratga oling" xabari — hech qanday maydon **taxmin qilib** to'ldirilmaydi. |
| QT-AI-GUARD-03 | unit | **Berilgan** LLM birinchi javobida raqamli nazorat tool natijasida yo'q sonni (masalan `"999999.00"`) yozgan, **qachonki** `narration_guard` tekshirsa, **unda** so'rov **bir marta** "faqat quyidagi raqamlardan foydalan" ko'rsatmasi bilan qayta yuboriladi; **qachonki** ikkinchi urinish ham mos kelmasa, **unda** AI matni **bostiriladi** — foydalanuvchiga faqat kod hisoblagan raqam/jadval (izohsiz) ko'rsatiladi, `ai_requests.status='guard_failed'` (`22-ai-qatlami.md` §3.2). |

---

## 4. NFR o'lchanadigan testlar (`25-nofunksional-talablar.md`)

| ID | Daraja | Ssenariy |
|---|---|---|
| QT-NFR-01 | e2e (performance) | **Berilgan** POS ochiq, lokal SQLite/IndexedDB, **qachonki** shtrix-kod skanerlansa, **unda** chekka qator qo'shilishi **< 100 ms** ichida tugaydi (server kutilmaydi). |
| QT-NFR-02 | e2e (performance) | **Berilgan** offline rejim, **qachonki** to'lov tasdiqlanib chek yakunlansa, **unda** chek chiqishi **< 1 s** ichida tugaydi (fiskal/OFD yuborish asinxron navbatda, foydalanuvchi kutilmaydi). |
| QT-NFR-03 | integration (load) | **Berilgan** o'qish so'rovi (masalan qoldiq/narx), **qachonki** yuklama testi bajarilsa, **unda** API javob vaqti p95 **< 300 ms**. |
| QT-NFR-04 | integration (load) | **Berilgan** yozuvchi so'rov (sotuv posting — hujjat+registr+provodka bitta tranzaksiyada), **qachonki** yuklama testi bajarilsa, **unda** API javob vaqti p95 **< 800 ms** (OFD/EDO yuborish bu vaqtga kirmaydi). |
| QT-NFR-05 | integration | **Berilgan** AI-01 chat so'rovi, **qachonki** yuborilsa, **unda** birinchi token **< 3 s** ichida qaytadi. |
| QT-NFR-06 | integration (fake clock) | QT-OFFLINE48-01 bilan bir xil — offline chekning OFD'ga yetib borishi **≤ 48 soat** (100% qonuniy talab, VM 943-son, 1-ilova 31-band). |
| QT-NFR-07 | integration (fake clock) | **Berilgan** markirovkalangan tovar ko'chirish hujjati "yo'lda" holatida, **qachonki** vaqt simulyatsiya qilinsa, **unda** **≤ 72 soat** ichida yetib borishi 100% talab (23-son qaror, 2026-01-23) — QT-M06-05 bilan bog'liq. |
| QT-NFR-08 | integration (fake clock) | **Berilgan** davlat hisoboti e'lon qilingan va farq topilgan, **unda** tuzatish **≤ 5 kalendar kun** ichida kiritilishi kutiladi (Soliq kodeksi 81-modda) — QT-M10-03 bilan bir xil. |
| QT-NFR-09 | integration (load) | **Berilgan** bitta qurilma, **qachonki** `/sync/push`ga soniyasiga 6 so'rov yuborilsa (5/soniya chegarasidan yuqori), **unda** `429 Too Many Requests` + `Retry-After`; **Berilgan** bitta tenant, **qachonki** 5-chi parallel `/sync/push` ulanishi ochilsa (4 tadan yuqori), **unda** xuddi shunday `429`. |
| QT-NFR-10 | integration | **Berilgan** qurilma birinchi marta ro'yxatdan o'tgan (lokal baza bo'sh), **qachonki** `GET /sync/pull?scope=all&cursor=` chaqirilsa, **unda** natija `page_size≈500` qator/sahifa bilan sahifalanadi, `has_more=true` bo'lsa davom etadi, oxirgi sahifada `has_more=false`. |
| QT-NFR-11 | integration (offline sig'im) | **Berilgan** qurilma 48 soat uzluksiz offline ishlagan, shu davrda ≈300 ta `sale.created`/`return.created`/`cash_movement.created` voqeasi outbox'ga yozilgan (taxminiy kunlik yuklama), **qachonki** internet qaytib `/sync/push` boshlansa, **unda** lokal baza (Dexie/SQLite) bu hajmni muammosiz saqlab turgan, barcha voqea **tartib bo'yicha** (`seq`) yuboriladi, backpressure chegarasiga (5 so'rov/soniya/qurilma) yetilganda qurilma eksponensial backoff+jitter bilan qayta urinib outbox'ni yo'qotmasdan tugallaydi. |
| QT-NFR-12 | integration (mavjudlik) | **Berilgan** ilova darajasidagi rejali texnik ish oynasi (yakshanba 02:00–04:00, taxmin), **qachonki** shu oynada backend vaqtincha mavjud emas, **unda** offline-first POS savdo **to'xtamaydi** (lokal sotuv davom etadi), faqat sinxronizatsiya kechikadi — oyna tugagach outbox avtomatik tugallanadi. |
| QT-NFR-13 | e2e (performance) | **Berilgan** `POST /ai/chat` SSE stream orqali javob beradi, **qachonki** javob uzun (masalan ko'p modulni qiyoslovchi tahlil) bo'lsa, **unda** birinchi token **< 3 s** ichida kelsa ham, **to'liq** javob kelguncha UI "yozmoqda" indikatori ko'rsatadi — foydalanuvchi bo'sh ekranni kutmaydi (`25-nofunksional-talablar.md` §1, `09-ai-funksiyalar.md` AI-01). |

**Misol — QT-NFR-04 yuklama profili** (`25-nofunksional-talablar.md` §3.1, "taxmin" deb belgilangan asosiy yuklama ko'rsatkichlari, pilot davrida haqiqiy raqamga almashtiriladi): 100 tenant, tenant boshiga o'rtacha 1 kassa, kassa boshiga kunlik ≈150 chek, soat boshiga eng yuqori yuklama (peak hour) ≈ 100 tenant × 150/10 soat ≈ **1500 yozuvchi so'rov/soat** ≈ **0,4 so'rov/soniya** — QT-NFR-04 shu profil asosida yuklama generatoriga (`locust`/`k6`) kiritiladi.

---

## Spec'da aniqlashtirish kerak

Quyidagi punktlar test yozish paytida **eng izchil talqin** bilan hal qilindi, lekin manbada aniq tasdiqlanmagan — arxitektura/Buxgalter/huquqshunos tasdig'i kerak bo'lgan joylarda shunday belgilangan:

1. **Idempotency-Key muvaffaqiyatli replay xatti-harakati** (QT-IDEMP-01) — *spec javob beradi*: `23-backend-arxitekturasi.md` §3 (Idempotency-Key qatori) — bir xil kalit + bir xil `request_hash` bilan qayta so'rovda `idempotency_keys.response_status/response_body`dan **saqlangan javob qaytariladi, amal qayta bajarilmaydi** (jurnal 30 kun). Test shu xatti-harakatni tekshiradi; noaniqlik yo'q.
2. **48 soatlik qoidadan keyin yangi sotuvni bloklash yoki faqat ogohlantirish** (QT-OFFLINE48-01): manbaning o'zi buni "huquqiy maslahat bilan tasdiqlanishi kerak" ochiq savol deb belgilaydi (`16-offline-sync.md` §6, band 1); testda "bloklanmaydi, faqat audit+ogohlantirish" talqini tanlandi, chunki hozirgi spec matni shunga ishora qiladi.
3. **24/40 soatlik oraliq ogohlantirish vaqtlari** (QT-OFFLINE48-01) — manbada "taxmin" deb aniq yozilgan, aniq soat yo'q; test shu "taxmin" raqamlar bilan yozilgan, pilotdan keyin sozlanishi mumkin.
4. **`approval_requests.expires_at` = 15 daqiqa** va POS tasdiq-so'rovi poll chastotasi (3 soniya) — *standart qaror qabul qilingan*: `01-qarorlar.md` #25 (≈15 daqiqa) va `26-ochiq-savollar-reestri.md` #87 (15 daqiqa, poll 3 soniya; pilotda tasdiqlanadi). QT-PERM ssenariylariga muddat tugashi (`expired`, fake clock 15 daqiqa) testini shu raqamlar bilan qo'shish mumkin; raqamlar o'zgarsa — faqat konstanta yangilanadi.
5. **Qarz to'lovidagi QQS/daromadni tan olish vaqti** (QT-M08-01/06): sotuv kuni yoki to'lov kuni tan olinishi — buxgalter/yurist tasdig'ini kutayotgan ochiq savol (`13-provodka-qoidalari.md` §2.14); testlar joriy "interim" qoidani (provodka sotuv kunida, fiskal chek to'lov kunida) tekshiradi, bu `FiscalPolicy` bayrog'i o'zgarsa testlar ham yangilanishi kerak.
6. **AVECO COGS yaxlitlash aniqligi** (QT-M04-06) — *spec javob beradi*: `13-provodka-qoidalari.md` §5.3 — `avg_cost` `NUMERIC(18,4)` saqlanadi, COGS yakuniy summasi tiyingacha (2 xona) yaxlitlanadi (§3.2 misoli: `120 × 8333.3333 → "1000000.00"`). "Taxmin" belgisi faqat QQS qator-yaxlitlashiga tegishli (10-band), AVECO'ga emas.
7. **Inventarizatsiya paytidagi parallel sotuv** (QT-M05) — *standart qaror qabul qilingan*: `26-ochiq-savollar-reestri.md` #91 — `post`da `expected` sanash boshlanganidan keyingi sotuvlarni hisobga olib qayta hisoblanadi (`13-provodka-qoidalari.md` §2.11); aniq formula implementatsiya bosqichida tasdiqlanadi. QT-M05 bo'limiga shu qoida bo'yicha test qo'shilishi kerak (hozir yo'q).
8. **Narx o'zgarishi tasdiqlash limiti** (QT-M09-02) — *standart qaror qabul qilingan*: `26-ochiq-savollar-reestri.md` #5 — katalog narxidan **±10%**dan ko'p o'zgarish faqat Egasi tasdig'i bilan (`prices.approve`, `role_permissions.limit_value = "10.00"`). Test holat mashinasi (`pending_approval`) bilan birga 10% chegarani ham tekshirishi mumkin (9.99% — darhol, 10.01% — tasdiq).
9. **MVP'dan keyin chiqarib tashlangan hikoyalar** (0.3-band) — *spec javob beradi*: US-M03-02, US-M08-08, US-M14-02, US-M17-05 `03-modullar-talablari.md` da "MVP'dan keyin — qaror #33" deb belgilangan; bu faylda ular uchun test yozilmaydi.
10. **QQS qator-bo'yicha yaxlitlash qoidasi** (QT-M10-06, QT-M01-01): `13-provodka-qoidalari.md` §5.3 bu qoidani "taxmin, OFD/soliq.uz rasmiy formati bilan tasdiqlanishi kerak" deb ochiq qoldiradi; `"321.43"` kabi barcha QQS-bog'liq test qiymatlari shu taxminga asoslangan — rasmiy format boshqacha chiqsa M01/M02/M10 testlari qayta hisoblanadi.
11. **Markirovka tekshiruvi muvaffaqiyatsiz bo'lganda qat'iy rad etish** (QT-M01-05 bilan bog'liq) — *standart qaror qabul qilingan*: `26-ochiq-savollar-reestri.md` #10 — qat'iy rad qoladi (CRPT javobi kelgach yumshatilishi mumkin). Testlar shu qoida bilan yoziladi; siyosat o'zgarsa markirovka-bog'liq negative testlar qayta ko'rib chiqiladi.
12. **Bir to'lov bir nechta sotuvni yopsa — bitta yoki alohida `debt_settlement` chek** (QT-M08-06): `01-qarorlar.md` #30 tovar qatorlarini "allokatsiya qilingan sotuv(lar)dan proporsional" deb belgilaydi, lekin `03-modullar-talablari.md` US-M08-04 bo'linishni (bitta chek yoki har sotuvga alohida) hamon ochiq qoldiradi; testlar hozircha "bitta proporsional chek" talqinini oladi — qaror boshqacha bo'lsa QT-M08-06/07 qayta yoziladi.
13. **Davlat (my.soliq.uz) hisobotining granulyarligi** (QT-M10-02/03): hisobot hujjat darajasida (har e-faktura/chek bo'yicha) yoki faqat davr yig'indisi sifatida berilishi rasmiy API yo'qligi sababli tasdiqlanmagan (`09-ai-funksiyalar.md`, AI-05 taxmini); agar faqat yig'ma summa berilsa, QT-M10-02/03 testlari solishtirish darajasini (hujjat o'rniga davr) o'zgartirishi kerak bo'ladi.
14. **Outbox/sinxronizatsiya tarixini saqlash muddati (7 kun)** (QT-NFR-11 bilan bog'liq): `16-offline-sync.md` §4.2 bu raqamni aniq manbasiz **taxmin** deb belgilaydi; haqiqiy saqlash siyosati pilotda sozlanadi.

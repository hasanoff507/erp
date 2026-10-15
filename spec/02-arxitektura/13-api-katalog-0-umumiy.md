# API katalogi — 0. Umumiy konventsiyalar

*2026-10-15 · Asos: `spec/README.md`, `spec/tekshiruv/00-qarorlar.md`, `spec/02-arxitektura/00-umumiy-arxitektura.md`, `01-malumotlar-modeli.md`, `02-provodka-qoidalari.md`, `05-xavfsizlik-va-audit.md` (§2.1–2.2), `09-backend-arxitekturasi.md` (§3), `12-autentifikatsiya-oauth2.md`, `04-offline-sync.md`. Bu fayl — `13-api-katalog-*.md` seriyasidagi **barcha** keyingi fayllar (moliya/admin, savdo/ombor, kontragent/narx, platforma kesishma va h.k.) rioya qiladigan yagona konventsiya to'plami. Modulga xos endpoint ro'yxatlari bu faylda **yo'q** — faqat shakl qoidalari.*

## Asosiy xulosalar

1. Barcha biznes API — `/api/v1` ostida; auth (`/oauth/*`, `/auth/*`) va sync (`/sync/*`) endpoint'lari allaqachon `12-autentifikatsiya-oauth2.md` va `04-offline-sync.md`da to'liq yozilgan — bu seriya ularni **takrorlamaydi**, faqat sharti bilan ishlatadi (masalan `require_subscription_ok`, `X-CSRF-Token`).
2. **Resurs nomlash — QAROR** *(2026-10-15: qabul-6/7, `tekshiruv/00-qarorlar.md` #24)*: URL yo'li — **kebab-case, ko'plik ot** (masalan `/goods-receipts`, `/debt-writeoffs`, `/price-changes`); JSON maydonlari, query parametrlari, enum qiymatlari va `operation_id` — **snake_case**, DB ustun nomi bilan aynan bir xil. `09-backend-arxitekturasi.md` §3 shu qarorga moslashtirildi — ikki hujjat orasidagi avvalgi ziddiyat (ilgarigi Ochiq savol #1) shu bilan yopiladi.
3. ID — **UUIDv7** satr (`01-malumotlar-modeli.md` §1); pul — o'nlik kasr **satr** (`"12000.00"`, 2 xona), miqdor — o'nlik kasr satr (**3 xona**, `"10.500"`), narx/tannarx — o'nlik kasr satr (**4 xona**, `"8333.3333"`); **hech qachon JSON number** (float yaxlitlash xatosi oldini olish uchun).
4. Sana ikki xil: `date` (`"2026-10-15"`, hisob sanasi, Toshkent bo'yicha) va `timestamptz` (ISO-8601, **UTC**, `"2026-10-15T09:00:00Z"`, `created_at`/`posted_at` kabi).
5. Hujjat ro'yxatlari — **cursor pagination** (`?cursor=&limit=`, standart 50, maksimum 200, javob `{items, next_cursor}`); ma'lumotnoma ro'yxatlari — **page pagination** (`?page=&size=`, javob `{items, total, page, size}`) — `09-backend-arxitekturasi.md` §3 bilan izchil (hujjat=cursor, ma'lumotnoma=page).
6. Xato konverti — yagona shakl: `{"error": {"code", "message_key", "params", "details", "request_id"}}`; `code` — barqaror mashina kaliti, `message_key` — frontend i18next kaliti, `details` — har doim massiv, maydon darajasidagi ro'yxat (`validation.*` kalitlar), `params` — ixtiyoriy biznes kontekst obyekti, `request_id` — `structlog`dagi so'rov ID'si (qo'llab-quvvatlash/audit uchun). *(2026-10-15: qabul-6/7, Q2)*
7. Optimistik qulflash — ma'lumotnomalarda `version INT`; `PATCH` tanada `version` talab qiladi, mos kelmasa `409 VERSION_CONFLICT`. Hujjatlar — `posted`dan keyin umuman o'zgarmaydi, faqat `POST /{id}/cancel`.
8. Hujjat (document) resurslari uchun yagona uch bosqichli hayot sikli: `POST /{resurs}` (draft yaratish) → `POST /{resurs}/{id}/post` (o'tkazish) → `POST /{resurs}/{id}/cancel` (bekor qilish, teskari yozuvlar). Ba'zi hujjatlar (masalan `sales`) faqat `/sync/push` orqali keladi — bu holat har modul faylida alohida belgilanadi.
9. To'liq xato kodlari katalogi — 8-bo'lim. Bu — **yagona manba**; boshqa `13-api-katalog-*.md` fayllari faqat shu ro'yxatdagi kodlarga havola qiladi, yangi kod shu faylga qo'shiladi.

---

## 1. Negiz (base path, versiyalash)

| Band | Qoida |
|---|---|
| Base path | `https://<domen>/api/v1/...` (`09-backend-arxitekturasi.md` §3) |
| Versiyalash | Breaking o'zgarish — `/api/v2`; eski versiya e'lon qilingan muddat (kamida 6 oy, **taxmin**) davomida parallel saqlanadi |
| Auth/sync | Auth yo'llari — `/auth/*` (BFF, **`/api/v1`siz**), istisno — `GET /api/v1/auth/csrf` (`tekshiruv/00-qarorlar.md` #4); OAuth protokol yo'llari — ildizda (`/oauth/*`, `/.well-known/*`); sync — `/api/v1/sync/push`, `/api/v1/sync/pull` — `04-offline-sync.md` §3; auth tafsiloti `12-autentifikatsiya-oauth2.md` §20. Bu fayl ularni qayta tasvirlamaydi *(2026-10-15: qabul-7, C-05)* |
| Platforma admin | `/platform/*` — alohida `aud=urn:erp:platform` token, tenant API'dan **butunlay ajratilgan** (`12-autentifikatsiya-oauth2.md` §18.1) |
| Health/metrika | `/health/live`, `/health/ready`, `/metrics` — `09-backend-arxitekturasi.md` §8, bu seriyaga kirmaydi |

## 2. Resurs nomlash

- **Kebab-case, ko'plik**: `/sales`, `/goods-receipts`, `/purchase-orders`, `/debt-writeoffs`, `/price-changes`, `/cash-movements`, `/stock-counts`, `/write-offs`, `/state-reports`, `/state-reports/{id}/diffs`, `/approval-requests`, `/payments/checkouts`, `/ledger-adjustments`. *(2026-10-15: qabul-6 — `/state-report-diffs` → `/state-reports/{id}/diffs`)*
- Resurs nomi — `01-malumotlar-modeli.md` jadval nomidan kelib chiqadi, faqat `_` → `-` almashtiriladi (`goods_receipts` → `/goods-receipts`); OpenAPI `operation_id` esa snake_case qoladi (`goods_receipts_create`) — frontend orval generatsiyasi shundan funksiya nomi oladi (`09-backend-arxitekturasi.md` §3).
- **JSON maydonlari — snake_case**, DB ustun nomi bilan aynan bir xil (`cash_register_id`, `doc_date`); camelCase ishlatilmaydi (frontend orval tiplari shu nomlarni oladi). *(2026-10-15: qabul-6)*
- Ichki qator resurs: `/{resurs}/{id}/{harakat}` fe'l shakli (`post`, `cancel`, `receive`, `approve`) — faqat holat o'tkazuvchi amallar uchun, CRUD uchun emas.
- Kesishma (cross-module) resurslar: `/reports/*`, `/platform/*`, `/admin/*`, `/billing/*`, `/ai/*` — bitta modulga tegishli bo'lmagan guruhlar, `09-backend-arxitekturasi.md` §1dagi modul papkalariga mos kelmaydi (bular `reports`/`billing`/`ai`/`access` modul papkalarining ochiq fasadi).

## 3. ID, pul, miqdor, sana

| Tur | Format | Misol | Izoh |
|---|---|---|---|
| ID | UUIDv7 satr | `"01933a1e-7c9a-7c3a-9b1e-2f6a8e9d0c1a"` | `01-malumotlar-modeli.md` §1 |
| Pul | O'nlik satr, 2 xona | `"120000.00"` | `NUMERIC(18,2)`, hech qachon JSON number |
| Miqdor | O'nlik satr, 3 xona | `"10.500"` | `NUMERIC(18,3)` |
| Narx/tannarx/foiz | `price`, `cost`, `unit_cost`, `avg_cost`, `old_price`, `new_price`, `limit_value`, `requested_value` — o'nlik satr, **4 xona**; foiz (`discount_pct`, `standing_discount_pct`, `vat_rate`) — **2 xona** | `"8333.3333"` / `"5.00"` | `NUMERIC(18,4)` / `NUMERIC(5,2)` *(2026-10-15: qabul-6, Q14)* |
| Sana (hisob) | ISO-8601 `date` | `"2026-10-15"` | Toshkent bo'yicha, `doc_date` |
| Vaqt belgisi | ISO-8601 `timestamptz`, UTC, `Z` qo'shimchasi bilan | `"2026-10-15T09:00:00Z"` | `created_at`, `posted_at`, `cancelled_at`; UI Toshkent vaqtiga (`UTC+5`) o'zi o'giradi |
| Davr (oy) | `"2026-10"` (yil-oy) | — | API `"YYYY-MM"` ↔ DB `DATE` (oyning 1-sanasi) — `vat_moves.period`, `period_closings.period`, `state_reports.period`, `ledger_adjustments.correction_of_period` *(2026-10-15: qabul-6)* |
| Bool | JSON `true`/`false` | — | — |
| Enum | Pastki chiziqli snake_case satr (DB qiymati bilan bir xil) | `"posted"`, `"cash"` | Frontend zod/i18next shu qiymatni kalit sifatida ishlatadi |

## 4. Pagination

| Ro'yxat turi | Usul | So'rov | Javob |
|---|---|---|---|
| Hujjat/registr (`sales`, `ledger-entries`, `audit-log`, …) | **Cursor** (UUIDv7 `id`/`created_at` bo'yicha tabiiy vaqt tartibi) | `?cursor=<token>&limit=50` (standart 50, maksimum 200) | `{"items": [...], "next_cursor": "<token>\|null"}` |
| Ma'lumotnoma (`products`, `counterparties`, `branches`, `roles`, …) | **Page** (UI'da sahifalash ko'rsatiladi) | `?page=1&size=50` (standart 50, maksimum 200) | `{"items": [...], "total": 437, "page": 1, "size": 50}` |

To'liq ma'lumotnoma ro'yxati (page pagination): `products`, `product-categories`, `counterparties`, `discount-rules`, `roles`, `branches`, `warehouses`, `cash-registers`, `expense-categories`, `recurring-expenses`, `label-templates`, `units` (sahifasiz, to'liq ro'yxat qaytariladi). *(2026-10-15: qabul-6)*

`cursor` — oldingi javobdagi `next_cursor` qiymati, bazoviy64 kodlangan `(created_at, id)` juftligi (`09-backend-arxitekturasi.md` §3, `fastapi-pagination` `CursorPage`). `next_cursor: null` — oxirgi sahifa.

## 5. Filtrlash va saralash

- Deklarativ query parametrlar (`fastapi-filter`): `?status=posted&doc_date__gte=2026-10-01&doc_date__lte=2026-10-31&branch_id=<uuid>`.
- Operator sintaksisi: `field` (teng), `field__gte`/`__lte`/`__gt`/`__lt` (son/sana oraliq), `field__in` (vergul bilan ajratilgan ro'yxat), `field__ilike` (matn qidiruv, `pg_trgm` indeksga mos).
- Saralash: `?sort=doc_date` (o'suvchi), `?sort=-doc_date` (kamayuvchi, `-` prefiks); bir nechta maydon — vergul bilan (`?sort=-doc_date,number`).
- Har endpoint o'z faylida qaysi maydonlar bo'yicha filtr/sort ruxsat etilgani jadvalda ko'rsatiladi (hammasi emas — SQL indekssiz maydon bo'yicha filtr yo'q).

## 6. Standart headerlar

| Header | Yo'nalish | Majburiyligi | Tavsif |
|---|---|---|---|
| `X-Branch-Id` | So'rov | Filialga bog'langan resurslarda majburiy | Joriy filial konteksti; `memberships.branch_ids`ga qarshi tekshiriladi, mos kelmasa `403 BRANCH_SCOPE_DENIED` (`05-xavfsizlik-va-audit.md` §2.4) |
| `Idempotency-Key` | So'rov | Barcha **yozuvchi** (POST/PUT/PATCH/DELETE) back-office so'rovlarida majburiy | UUID, frontend avtomatik generatsiya qiladi; `/sync/push` bundan mustasno (`04-offline-sync.md` dedupe `client_event_id` orqali) — `09-backend-arxitekturasi.md` §3 |
| `X-CSRF-Token` | So'rov | Cookie-autentifikatsiyali (BFF, veb) barcha yozuvchi so'rovlarda majburiy | `GET /api/v1/auth/csrf` orqali olinadi; Android Bearer so'rovlari ozod (`05-xavfsizlik-va-audit.md` §1.3) |
| `Accept-Language` | So'rov | Ixtiyoriy, standart `uz` | `uz` \| `ru` — `message_key` tarjimasi va hisobot/eksport tili (`06-nofunksional-talablar.md`) |
| `Authorization: Bearer <token>` | So'rov | Faqat Android (to'g'ridan-to'g'ri API) | Veb — BFF cookie, header yo'q (`12-autentifikatsiya-oauth2.md` §2) |
| `Retry-After` | Javob | `429`/`409 IDEMPOTENCY_IN_PROGRESS`da | Soniyalarda qayta urinish tavsiyasi |
| `X-Request-Id` | Javob | Har doim | `structlog` so'rov ID'si, `error.request_id` bilan bir xil qiymat |

## 7. Xato konverti va HTTP status

### 7.1 Konvert shakli

```json
{
  "error": {
    "code": "DEBT_LIMIT_EXCEEDED",
    "message_key": "errors.debt_limit_exceeded",
    "params": { "limit": "500000.00", "requested": "569000.00" },
    "details": [
      { "field": "payments[0].amount", "message_key": "validation.exceeds_credit_limit" }
    ],
    "request_id": "01933a1e-..."
  }
}
```

`details` — **har doim massiv** (maydon xatolari, bo'sh bo'lishi mumkin, react-hook-form/zod shakli, `09-backend-arxitekturasi.md` §3); maydon darajasidagi `message_key` — **`validation.*`** prefiksida (frontend zod `errorMap` kalitlari bilan bir xil, `08-dizayn-tizimi.md` §11). `params` — **ixtiyoriy obyekt**, biznes konteksti (limit, so'ralgan qiymat, `resource`, `reason`, `expected_status`/`actual_status`), i18next interpolatsiyasi uchun; kod darajasidagi `message_key` — `errors.*` prefiksida. *(2026-10-15: qabul-6/7, Q2)*

### 7.2 HTTP status qo'llanilishi

| Status | Qachon ishlatiladi |
|---|---|
| `200 OK` | Muvaffaqiyatli `GET`/amal (natija qaytaradi) |
| `201 Created` | Yangi resurs yaratildi (`POST /{resurs}`, `Location` header bilan) |
| `202 Accepted` | Asinxron ish navbatga qo'yildi (eksport job, AI OCR submit) — javobda `job_id` |
| `204 No Content` | Muvaffaqiyatli amal, javob tanasi yo'q (masalan `DELETE`, ba'zi `POST .../revoke`) |
| `400 Bad Request` | Noto'g'ri so'rov shakli (JSON parse xatosi) |
| `401 Unauthorized` | Sessiya/token yo'q yoki tugagan |
| `403 Forbidden` | Ruxsat yo'q (`PERMISSION_DENIED`), filial mos kelmadi, obuna `restricted`, CSRF xato |
| `404 Not Found` | Resurs topilmadi (yoki RLS tufayli boshqa tenantga tegishli — farqlanmaydi, xavfsizlik) |
| `409 Conflict` | `VERSION_CONFLICT`, `PERIOD_CLOSED`, `IDEMPOTENCY_IN_PROGRESS`, hujjat holati mos kelmaydi (masalan allaqachon `cancelled`) |
| `413 Payload Too Large` | Fayl hajmi chegaradan katta |
| `415 Unsupported Media Type` | Fayl turi ruxsat etilmagan |
| `422 Unprocessable Entity` | Validatsiya xatosi, biznes qoida buzilishi (`IDEMPOTENCY_KEY_REUSED`, limit xatolari — ba'zan `403`, pastdagi jadvalga qarang) |
| `423 Locked` | `ACCOUNT_LOCKED` |
| `429 Too Many Requests` | Rate-limit (login, OTP, AI, sync backpressure) |
| `500 Internal Server Error` | Kutilmagan server xatosi (`sentry-sdk`ga yoziladi) |
| `502 Bad Gateway` | Tashqi tizim xato javob berdi (`FISCAL_SEND_FAILED`, `PAYMENT_PROVIDER_ERROR`) |
| `503 Service Unavailable` | Tashqi tizim (AI provider, CRPT `MARKING_VERIFY_UNAVAILABLE`, EDO operatori `EINVOICE_PROVIDER_UNAVAILABLE`) vaqtincha ishlamaydi — faqat AI/tashqi integratsiya qatlamida, ichki tranzaksion endpoint'larda ishlatilmaydi |

## 8. Optimistik qulflash

- Ma'lumotnomalarda (`products`, `product-prices`, `roles`, `counterparties`, …) `version INT` maydoni javobda qaytariladi.
- `PATCH`/`PUT` so'rov tanasida `version` **majburiy**; server joriy qiymat bilan solishtiradi, mos kelmasa `409 VERSION_CONFLICT`, javobda joriy (server) versiya qaytariladi — frontend foydalanuvchiga "ma'lumot boshqa joyda o'zgartirilgan, qayta yuklang" ko'rsatadi.
- Hujjatlarda (`sales`, `goods-receipts`, …) `version` yo'q — `posted`dan keyin umuman o'zgarmaydi, tahrir o'rniga `POST /{id}/cancel` + yangi hujjat.

## 9. Hujjat hayot sikli endpoint naqshi

Har bir "hujjat" turidagi resurs (`01-malumotlar-modeli.md` §6, posting service naqshi — `09-backend-arxitekturasi.md` §2) uchun yagona uch endpoint shakli:

| Qadam | Endpoint | HTTP | Natija |
|---|---|---|---|
| 1. Qoralama yaratish | `POST /{resurs}` | 201 | `status=draft`, qatorlar bilan birga yoki bo'sh (keyin `PUT`/`PATCH` bilan to'ldiriladi) |
| 2. O'tkazish | `POST /{resurs}/{id}/post` | 200 | `PostingService.post()` — bitta tranzaksiyada registrlar + `status=posted`, `posted_at` (`09-backend-arxitekturasi.md` §2.1) |
| 3. Bekor qilish | `POST /{resurs}/{id}/cancel` | 200 | Tanada `reason` (majburiy, string); `PostingService.reverse()` — teskari registr yozuvlari, `status=cancelled` |

Qo'shimcha tur-xos amallar (masalan `purchase-orders/{id}/send`, `transfers/{id}/receive`, `stock-counts/{id}/review`) — holat mashinasiga mos, har modul faylida ko'rsatiladi (`01-malumotlar-modeli.md` §8).

**Istisno**: `sales`, `returns` va boshqa POS hujjatlari backend-API orqali to'g'ridan-to'g'ri yaratilmaydi — faqat `POST /sync/push` orqali (`04-offline-sync.md` §3.1, `00-umumiy-arxitektura.md` §2). `sales`/`returns` back-office'da faqat **o'qiladi** (`GET /sales`, `GET /sales/{id}`, `GET /returns`, `GET /returns/{id}`); o'tkazilgan chek **bekor qilinmaydi** — xato faqat `return.created` bilan tuzatiladi (fiskal chek o'zgarmaydi). `sales.void` — faqat to'lovdan oldingi qoralama (`sale.draft_voided`, audit). `POST /sales` ham, `.../cancel` ham yo'q. *(2026-10-15: qabul-6/7, Q9)*

**Bir bosqichli hujjatlar**: `supplier-payments`, back-office `cash-movements`, `ledger-adjustments` — `POST /{resurs}` darhol `status=posted` (`201`) qaytaradi, `draft` bosqichi yo'q; `cancel` mavjud. **Limitdan oshgan post** (har qanday hujjat): `202` + `{"status":"draft","approval_request_id":...}` (kod `APPROVAL_REQUIRED`), tasdiqlanganda server o'zi o'tkazadi (`approval_requests`/`doc_approvals` mexanizmi — `13-api-katalog-1-kassa.md` §9, bitta so'rov bir hujjatda bir marta ishlatiladi/`consumed`). *(2026-10-15: qabul-6)*

## 10. Ruxsat (permission) notatsiyasi

Har endpoint jadvalida `permission` ustuni — `05-xavfsizlik-va-audit.md` §2.1 kodlaridan biri, masalan `sales.void`, `debts.forgive`. Notatsiya:

| Belgi | Ma'no |
|---|---|
| `kod` | Shu `permission_code` kerak (`role_permissions`da mavjud bo'lishi shart) |
| `kod (limit)` | Kod bor, lekin `role_permissions.limit_value`dan oshsa PIN/tasdiqlash oqimi (`05-xavfsizlik-va-audit.md` §2.3) ishga tushadi — `202`/`pending_approval` holati |
| `kod — faqat Egasi` | `05-xavfsizlik-va-audit.md` §2.1'da "faqat Egasi" deb belgilangan (`debts.forgive`, `billing.manage`, `platform.admin`) |
| `—` | Ruxsat tekshiruvi yo'q (faqat autentifikatsiya, masalan `GET /health`) |

*(2026-10-15: asoschi qarori, Q1: **Egasi — barcha tenant ruxsatlarining supersetiga ega**, `platform.admin`dan tashqari, limitlar cheksiz; yuqoridagi "`kod` — faqat Egasi" belgisi amalda boshqa rollar uchun cheklovni bildiradi — Egasiga har doim ruxsat berilgan.)*

## 11. OpenAPI teglari

Har modul — bitta OpenAPI tag, `09-backend-arxitekturasi.md` §1dagi modul papkasi nomiga mos:

| Modul kodi | Tag | Modul papkasi |
|---|---|---|
| M01 | `sales` | `modules/sales` |
| M02 | `returns` | `modules/returns` |
| M03 | `pricing` (chegirma qoidalari) | `modules/pricing` |
| M04 | `inventory` | `modules/inventory` |
| M05 | `stock-counts` | `modules/inventory` |
| M06 | `transfers` | `modules/inventory` |
| M07 | `purchasing` | `modules/purchasing` |
| M08 | `debts` | `modules/debts` |
| M09 | `pricing` | `modules/pricing` |
| M10 | `vat` | `modules/vat` |
| M11 | `accounting` | `modules/accounting` |
| M12 | `reports` | `modules/reports` |
| M13 | `access` | `modules/access` (+ `modules/auth` — `12-autentifikatsiya-oauth2.md`) |
| M14 | `branches` | `modules/branches` |
| M15 | `expenses` | `modules/expenses` |
| M16 | `cash` | `modules/cash` |
| M17 | `billing` | `modules/billing` |
| M18 | `notifications` | `modules/notifications` |
| AI | `ai` | `modules/ai` |
| — | `sync`, `auth` | `modules/sync`, `modules/auth` (alohida fayllarda) |

`operation_id` qo'lda beriladi: `<tag>_<harakat>` (masalan `debts_forgive`, `goods_receipts_post`) — orval shundan funksiya nomini oladi.

## 12. Fayl yuklash

- `multipart/form-data`, maydon nomi `file`; `python-multipart` (`09-backend-arxitekturasi.md` §5).
- Ruxsat etilgan turlar: hujjat skaneri/foto (`image/jpeg`, `image/png`, `application/pdf`), Excel import (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`), CSV import (`text/csv`).
- Chegaralar: rasm ≤ 10 MB, PDF ≤ 20 MB, Excel/CSV ≤ **10 MB** (**taxmin**, yuklama sinovida tasdiqlanadi; `13-api-katalog-2-ombor.md` import bilan izchil, 5 MB'dan ko'tarildi). Oshsa — `413 FILE_TOO_LARGE`. Noto'g'ri tur — `415 UNSUPPORTED_FILE_TYPE`.
- **`POST /api/v1/attachments`** — `multipart/form-data` (`file`, `kind`: `expense_receipt`/`ocr_source`/`state_report`/`import`/`export`/`label_pdf`/`billing_invoice`/`einvoice`/`other`, DB `attachments.kind`); ruxsat — autentifikatsiya + `kind`ga mos modul ruxsati (masalan `ocr_source` → `ai.ocr.use`, `expense_receipt` → `expenses.create`, `state_report` → `tax.compare.review`, `import` → `catalog.manage`); `Idempotency-Key` majburiy. Javob — `201 {"id": "<attachment_id>", "url": "<signed S3 url, 15 daqiqa>", "content_type", "size_bytes"}` (`attachments` jadvali, `01-malumotlar-modeli.md` §6).
- **`GET /api/v1/attachments/{id}`** → `{id, url (yangi signed URL, 15 daqiqa), content_type, original_name}`.
- AI-03 (OCR) kabi "fayl + darhol tahlil" endpoint'larida fayl avval `attachments`ga yuklanadi, so'ng AI endpoint `attachment_id`ni qabul qiladi (`07-ai-qatlami.md` §10 oqimi) — ikki bosqich, bitta chaqiruvda emas (katta fayl AI so'rovini bloklamasligi uchun). *(2026-10-15: qabul-6/7)*

## 13. Excel eksport naqshi (asinxron ish)

Katta hisobotlar (`reports.export`, M12) sinxron qaytarilmaydi — ish navbatga qo'yiladi:

1. `POST /reports/{report-kod}/export` — tanada filtr/davr; javob `202 Accepted` + `{"job_id": "<uuid>", "status": "queued"}`.
2. `GET /reports/export-jobs/{job_id}` — poll; javob `{"status": "queued"|"running"|"done"|"failed", "progress_pct": 0-100, "file_url": "<signed url, done bo'lsa>", "error_code": null}`.
3. Fayl S3-mos omborda, `signed URL` 24 soat amal qiladi (**taxmin**); format `?format=xlsx|pdf` query parametri bilan tanlanadi.
4. Muvaffaqiyatsiz bo'lsa `status=failed`, `error_code: EXPORT_JOB_FAILED`, `audit_log`ga `reports.export` voqeasi baribir yoziladi (urinish sifatida).

Kichik ro'yxatlar (masalan 50 qatorgacha joriy sahifa) — `?format=xlsx` bilan **sinxron** `200` + `Content-Disposition: attachment` ham mumkin (modul faylida ko'rsatiladi qaysi endpoint qaysi usulda).

## 14. Webhook naqshi (Click/Payme)

`03-integratsiyalar.md` §9 bilan izchil, bu fayl faqat API-qatlam shaklini belgilaydi:

| Band | Qoida |
|---|---|
| Yo'l | `POST /billing/webhooks/click`, `POST /billing/webhooks/payme` — tashqi tizim chaqiradi, bizning auth'imiz (cookie/Bearer) **ishlatilmaydi** |
| Imzo tekshiruvi | Click — MD5 imzo (`sign_string`), Payme — `Authorization: Basic` (merchant login:key) tekshiradi; mos kelmasa `403 WEBHOOK_SIGNATURE_INVALID`, so'rov yozilmaydi |
| Idempotentlik | `provider_tx_id` — `UNIQUE` (`billing_payments`); takror webhook — `200` bilan bir xil (eski) natija qaytariladi, qayta yozilmaydi (`03-integratsiyalar.md` §9) |
| Javob muddati | Kelgan so'rovga **darhol** `200` (yoki Payme/Click protokoliga mos JSON-RPC natija) qaytariladi; og'ir ishlov (fiskal/buxgalteriya ta'siri) webhook javobidan **keyin**, navbat orqali — webhook o'zi hech qachon tashqi tizimni kutmaydi |
| Click ikki bosqich | `Prepare` → `200 {error: 0}` (yoki xato kodi), `Complete` → xuddi shu yo'l, `merchant_trans_id` bo'yicha bog'lanadi |
| Payme metodlari | Bitta `POST /billing/webhooks/payme` yo'lida JSON-RPC `method` maydoni bo'yicha ichki dispatch: `CheckPerformTransaction`, `CreateTransaction`, `PerformTransaction`, `CancelTransaction`, `CheckTransaction`, `GetStatement` |
| Ikki kontekst | Do'kon QR to'lovi (tenant merchant) va bizning billing (platforma merchant) — bir xil adapter interfeysi, boshqa yo'l/kalit: `POST /payments/webhooks/{provider}` (do'kon, M01 QR to'lov) vs `POST /billing/webhooks/{provider}` (bizning obuna, M17) — `03-integratsiyalar.md` §9 "muhim ajratish" |

---

## 15. Xato kodlari katalogi (to'liq)

Bu — **yagona manba**; `code` ustuni barqaror (frontend/mobil/test shu bo'yicha ishlaydi), `message_key` i18next kaliti. `uz`/`ru` matnlar — boshlang'ich tarjima, final nusxa UX-yozuvchi tomonidan tasdiqlanadi (**taxmin**).

### 15.1 Autentifikatsiya va sessiya

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `UNAUTHORIZED` | 401 | `errors.unauthorized` | Avval tizimga kiring | Сначала войдите в систему | Sessiya/token yo'q yoki yaroqsiz |
| `INVALID_CREDENTIALS` | 401 | `errors.invalid_credentials` | Telefon raqami yoki parol noto'g'ri | Неверный номер телефона или пароль | Login urinishi muvaffaqiyatsiz |
| `ACCOUNT_LOCKED` | 423 | `errors.account_locked` | Hisob vaqtincha bloklangan, keyinroq urinib ko'ring | Учётная запись временно заблокирована | Ko'p noto'g'ri urinishdan keyin (`12-autentifikatsiya-oauth2.md` §12) |
| `OTP_INVALID` | 400 | `errors.otp_invalid` | Tasdiqlash kodi noto'g'ri | Неверный код подтверждения | OTP mos kelmadi (kanal — Telegram/SMS, `otp_challenges.channel`) *(2026-10-15: asoschi qarori, Q7 — matn kanal-agnostik qilindi)* |
| `OTP_EXPIRED` | 400 | `errors.otp_expired` | Tasdiqlash kodi muddati o'tgan, qayta so'rang | Код подтверждения истёк, запросите новый | `otp_challenges.expires_at` o'tgan |
| `OTP_MAX_ATTEMPTS` | 429 | `errors.otp_max_attempts` | Urinishlar soni tugadi, birozdan keyin qayta so'rang | Превышено число попыток, попробуйте позже | `otp_challenges.max_attempts` oshdi |
| `OTP_CHANNEL_UNAVAILABLE` | 503 | `errors.otp_channel_unavailable` | Kod yuborib bo'lmadi (Telegram ham, SMS ham ishlamadi), birozdan keyin qayta urinib ko'ring | Не удалось отправить код (Telegram и SMS недоступны), попробуйте позже | **(asoschi qarori, Q7)** Telegram bot va SMS (zaxira) ikkisi ham muvaffaqiyatsiz — `12-autentifikatsiya-oauth2.md` §4.2 |
| `TELEGRAM_NOT_LINKED` | 200 *(ma'lumot, xato emas)* | `errors.telegram_not_linked` | Telegram ulanmagan — kod SMS orqali yuborildi | Telegram не привязан — код отправлен по SMS | **(asoschi qarori, Q7)** `/auth/otp/request` javobida `channel_used="sms"` bilan birga, foydalanuvchiga Telegram ulashni tavsiya qilish uchun |
| `GOOGLE_EMAIL_NOT_VERIFIED` | 403 | `errors.google_email_not_verified` | Google hisobingiz email manzili tasdiqlanmagan, boshqa usul bilan kiring | Email вашего аккаунта Google не подтверждён, войдите другим способом | **(asoschi qarori, Q7)** `12-autentifikatsiya-oauth2.md` §2.2 |
| `GOOGLE_AUTH_FAILED` | 401 | `errors.google_auth_failed` | Google orqali kirish amalga oshmadi, qayta urinib ko'ring | Вход через Google не удался, попробуйте снова | **(asoschi qarori, Q7)** `12-autentifikatsiya-oauth2.md` §2.2 |
| `CSRF_INVALID` | 403 | `errors.csrf_invalid` | Sahifa eskirgan, qayta yuklang | Страница устарела, обновите её | `X-CSRF-Token` yo'q/eskirgan (`05-xavfsizlik-va-audit.md` §1.3) |
| `TOKEN_EXPIRED` | 401 | `errors.token_expired` | Sessiya muddati tugadi, qayta kiring | Сессия истекла, войдите снова | Access token `exp` o'tgan, refresh muvaffaqiyatsiz |
| `TOKEN_REVOKED` | 401 | `errors.token_revoked` | Sessiya bekor qilingan | Сессия отменена | Refresh reuse detection yoki admin bekor qildi |
| `DEVICE_REVOKED` | 403 | `errors.device_revoked` | Qurilma bekor qilingan, qayta ro'yxatdan o'ting | Устройство отозвано, зарегистрируйтесь снова | `devices.revoked_at` to'ldirilgan (`04-offline-sync.md` §9) |
| `PIN_INVALID` | 400 | `errors.pin_invalid` | PIN kod noto'g'ri | Неверный PIN-код | `/auth/pin/verify` muvaffaqiyatsiz |

### 15.2 Validatsiya

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `VALIDATION_ERROR` | 422 | `errors.validation` | Ma'lumotlarda xato bor, tekshirib qayta kiriting | В данных есть ошибка, проверьте и повторите | Pydantic validatsiya xatosi, `details` to'ldirilgan |
| `VERSION_CONFLICT` | 409 | `errors.version_conflict` | Ma'lumot boshqa joyda o'zgartirilgan, qayta yuklang | Данные изменены в другом месте, обновите страницу | Optimistik qulflash (8-bo'lim) |
| `NOT_FOUND` | 404 | `errors.not_found` | Topilmadi | Не найдено | Resurs yo'q yoki boshqa tenantga tegishli |
| `DOC_NOT_DRAFT` | 409 | `errors.doc_not_draft` | Hujjat qoralama holatida emas | Документ не в статусе черновика | `post`/tahrir faqat `draft`da mumkin |
| `DOC_ALREADY_CANCELLED` | 409 | `errors.doc_already_cancelled` | Hujjat allaqachon bekor qilingan | Документ уже отменён | Qayta `cancel` |
| `DOC_INVALID_STATE` | 409 | `errors.doc_invalid_state` | Hujjat bu amal uchun mos holatda emas | Документ не в подходящем статусе для этого действия | Umumiy holat mashinasi xatosi; `params.expected_status`, `params.actual_status` |
| `RESOURCE_ARCHIVED` | 409 | `errors.resource_archived` | Bu yozuv arxivlangan | Эта запись в архиве | Arxivlangan ma'lumotnomani tahrirlash/qayta arxivlash; `params.resource` |
| `SYSTEM_ROLE_READONLY` | 409 | `errors.system_role_readonly` | Tizim rolining nomini o'zgartirib bo'lmaydi | Нельзя переименовать системную роль | `PATCH /roles/{id}`, `is_system=true` |
| `BARCODE_DUPLICATE` | 409 | `errors.barcode_duplicate` | Bu shtrix-kod boshqa tovarda bor | Этот штрихкод уже у другого товара | `UNIQUE (tenant_id, barcode)` |
| `CATEGORY_HAS_PRODUCTS` | 409 | `errors.category_has_products` | Toifada faol tovarlar bor, avval ularni ko'chiring | В категории есть активные товары, сначала перенесите их | Kategoriya arxivlash |
| `MXIK_CODE_INVALID` | 422 | `errors.mxik_code_invalid` | MXIK kodi 17 raqamdan iborat bo'lishi kerak | Код ИКПУ должен состоять из 17 цифр | Format xatosi |

*(2026-10-15: qabul-6/7)*

### 15.3 Ruxsat (permissions)

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `PERMISSION_DENIED` | 403 | `errors.permission_denied` | Bu amal uchun ruxsatingiz yo'q | У вас нет прав для этого действия | `require_permission` rad etdi |
| `BRANCH_SCOPE_DENIED` | 403 | `errors.branch_scope_denied` | Bu filialga kirish huquqingiz yo'q | У вас нет доступа к этому филиалу | `X-Branch-Id` membership'ga mos kelmadi |
| `OWNER_ONLY` | 403 | `errors.owner_only` | Bu amalni faqat Egasi bajara oladi | Это действие может выполнить только владелец | `debts.forgive`, `billing.manage` va h.k. |
| `PLATFORM_ADMIN_REQUIRED` | 403 | `errors.platform_admin_required` | Platforma admin huquqi kerak | Требуются права администратора платформы | `/platform/*` oddiy tenant token bilan chaqirildi |
| `APPROVAL_REQUIRED` | 202 | `errors.approval_required` *(amal emas — holat)* | Tasdiqlash kutilmoqda | Ожидает подтверждения | Limitdan oshgan amal — PIN/BO-16 navbatiga tushdi (`05-xavfsizlik-va-audit.md` §2.3) |
| `APPROVAL_INVALID` | 403 | `errors.approval_invalid` | Tasdiq yo'q yoki tasdiqlovchining huquqi yetarli emas | Нет подтверждения или у подтверждающего недостаточно прав | `ApprovalRef` kutilgan, kelmagan / `approved_by` limiti qoplamaydi / `approval_request` boshqa hujjatda ishlatilgan (eski `PIN_REQUIRED` o'rniga) |
| `APPROVAL_REQUEST_ALREADY_RESOLVED` | 409 | `errors.approval_request_already_resolved` | So'rov allaqachon ko'rib chiqilgan | Запрос уже рассмотрен | Qayta approve/reject |
| `APPROVAL_REQUEST_EXPIRED` | 409 | `errors.approval_request_expired` | Tasdiqlash so'rovi muddati o'tgan, qayta yuboring | Срок запроса на подтверждение истёк, отправьте заново | `expires_at` o'tgan |

*(2026-10-15: qabul-6/7)*

### 15.4 Limitlar

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `DISCOUNT_LIMIT_EXCEEDED` | 403 | `errors.discount_limit_exceeded` | Chegirma limitdan oshdi, Menejer/Egasi tasdig'i kerak | Скидка превышает лимит, нужно подтверждение менеджера | `discount.give` limit (standart 5%) |
| `RETURN_LIMIT_EXCEEDED` | 403 | `errors.return_limit_exceeded` | Qaytarish summasi limitdan oshdi | Сумма возврата превышает лимит | `returns.approve` limit (standart 100 000 so'm) |
| `CASH_WITHDRAW_LIMIT_EXCEEDED` | 403 | `errors.cash_withdraw_limit_exceeded` | Kassadan pul olish limitdan oshdi | Сумма превышает лимит на изъятие из кассы | `cash.withdraw` limit (standart 50 000 so'm) |
| `DEBT_LIMIT_EXCEEDED` | 403 | `errors.debt_limit_exceeded` | Mijozning kredit limiti yetarli emas | Кредитный лимит клиента превышен | `debts.create`/`counterparties.credit_limit` |
| `PRICE_CHANGE_LIMIT_EXCEEDED` | 403 | `errors.price_change_limit_exceeded` | Narx o'zgarishi limitdan katta, tasdiqlash kerak | Изменение цены превышает лимит, нужно подтверждение | `prices.approve`, M09 |
| `WRITE_OFF_LIMIT_EXCEEDED` | 403 | `errors.write_off_limit_exceeded` | Hisobdan chiqarish summasi limitdan oshdi, tasdiq kerak | Сумма списания превышает лимит, нужно подтверждение | `stock.writeoff` limit |
| `EXPENSE_LIMIT_EXCEEDED` *(2026-10-15: qabul-6 — eski `EXPENSE_APPROVAL_REQUIRED` o'rniga, oila nomlashi bilan izchil)* | 403 | `errors.expense_limit_exceeded` | Xarajat summasi limitdan oshdi, tasdiq kerak | Сумма расхода превышает лимит, нужно подтверждение | `expenses.approve` limit |

### 15.5 Ombor/qoldiq

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `INSUFFICIENT_STOCK` *(ta'rif yangilandi, 2026-10-15: qabul-6)* | 422 | `errors.insufficient_stock` | Partiyada/omborda yetarli miqdor yo'q | Недостаточно количества в партии/на складе | `qty > stock_lots.qty_left` (yetkazib beruvchiga qaytarish, hisobdan chiqarish, ko'chirish); `params.lot_id`, `params.available` — eski `SUPPLIER_RETURN_QTY_EXCEEDED`, `WRITE_OFF_QTY_EXCEEDS_LOT` o'rniga. Tenant siyosati xatosi — `NEGATIVE_STOCK_NOT_ALLOWED` |
| `RETURN_QTY_EXCEEDED` | 422 | `errors.return_qty_exceeded` | Qaytarish miqdori sotilgandan ko'p | Количество возврата больше проданного | `01-malumotlar-modeli.md` §6 invariant |
| `NEGATIVE_STOCK_NOT_ALLOWED` | 422 | `errors.negative_stock_not_allowed` | Manfiy qoldiqqa yo'l qo'yilmaydi | Отрицательный остаток не допускается | Tenant sozlamasi manfiy qoldiqni taqiqlagan |
| `LOT_NOT_FOUND` | 404 | `errors.lot_not_found` | Partiya topilmadi | Партия не найдена | FIFO allokatsiyasi uchun `stock_lots` yo'q |
| `STOCK_NEGATIVE` | 200 *(ogohlantirish — `warnings[]`, amal emas)* | `warnings.stock_negative` | Qoldiq manfiyga tushdi, kirimni tekshiring | Остаток ушёл в минус, проверьте приход | Offline overselling (`04-offline-sync.md` §5) — sotuv qabul qilinadi |
| `LOT_ALREADY_CONSUMED` | 409 | `errors.lot_already_consumed` | Bu kirim partiyasidan allaqachon chiqim bo'lgan, bekor qilib bo'lmaydi | Из партии этого прихода уже было списание, отмена невозможна | Kirimni bekor qilish |
| `BARCODE_NOT_IN_CATALOG` | 422 | `errors.barcode_not_in_catalog` | Shtrix-kod katalogda topilmadi | Штрихкод не найден в каталоге | Inventarizatsiya skaneri |
| `VALUATION_METHOD_CHANGE_NOT_ALLOWED` | 409 | `errors.valuation_method_change_not_allowed` | Baholash usuli bu yil uchun allaqachon o'zgartirilgan | Метод оценки на этот год уже изменён | `PATCH /valuation-settings` |

*(2026-10-15: qabul-6/7)*

### 15.5a Kassa va smena

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `SHIFT_NOT_OPEN` | 409 | `errors.shift_not_open` | Smena ochiq emas | Смена не открыта | Yopiq/yo'q smenaga sotuv/pul harakati/xarajat |
| `SHIFT_ALREADY_OPEN` | 409 | `errors.shift_already_open` | Bu kassada smena allaqachon ochiq | На этой кассе смена уже открыта | `shift.opened`, `uq_shifts_one_open` |

*(2026-10-15: qabul-6/7 — yangi bo'lim)*

### 15.6 Qarz (debt)

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `DEBT_ALREADY_PAID` | 409 | `errors.debt_already_paid` | Qarz allaqachon yopilgan | Долг уже закрыт | Takror to'lov/kechish urinishi |
| `DOUBTFUL_FLAG_REQUIRES_OWNER` | 403 | `errors.doubtful_flag_requires_owner` | Qarzni "shubhali" deb belgilashni faqat Egasi qila oladi | Пометить долг как сомнительный может только владелец | `debt_doubtful_flags` (`01-malumotlar-modeli.md` §5) |

### 15.7 Fiskal/markirovka

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `RECEIPT_SEQ_CONFLICT` | 409 | `errors.receipt_seq_conflict` | Chek raqami takrorlangan | Номер чека повторяется | `01-malumotlar-modeli.md` §11 |
| `SHIFT_DEVICE_MISMATCH` | 409 | `errors.shift_device_mismatch` | Bu smena boshqa qurilmaga tegishli | Эта смена привязана к другому устройству | `shifts.device_id` mos kelmadi |
| `FISCAL_SEND_FAILED` | 502 | `errors.fiscal_send_failed` | OFD'ga yuborishda xato, qayta uriniladi | Ошибка отправки в ОФД, повтор автоматический | `fiscal_receipts.status=failed` |
| `MARKING_CODE_INVALID` | 422 | `errors.marking_code_invalid` | Markirovka kodi noto'g'ri yoki o'qilmadi | Код маркировки неверен или не считан | DataMatrix format xatosi |
| `MARKING_CODE_ALREADY_SOLD` | 409 | `errors.marking_code_already_sold` | Bu kod allaqachon sotilgan | Этот код уже продан | `marking_codes.status='sold'` |
| `MARKING_PRICE_UNKNOWN_OFFLINE` | 422 | `errors.marking_price_unknown_offline` | Narx offline rejimda noma'lum, sotish mumkin emas | Цена неизвестна офлайн, продажа невозможна | `tekshiruv/00-qarorlar.md` #17 |
| `MARKING_VERIFY_FAILED` | 409 | `errors.marking_verify_failed` | Markirovka kodi CRPT tekshiruvidan o'tmadi | Код маркировки не прошёл проверку CRPT | Sinxronlashdan keyin CRPT rad etdi |
| `MARKING_VERIFY_UNAVAILABLE` | 503 | `errors.marking_verify_unavailable` | Asl belgisi tizimi javob bermayapti, offline qoidasi qo'llanadi | Система «Асл белгиси» не отвечает, применяется офлайн-правило | CRPT timeout |
| `MARKING_RETURN_REQUIRES_ONLINE` | 422 | `errors.marking_return_requires_online` | Markirovkalangan tovarni faqat internet bor paytda qaytarish mumkin | Возврат маркированного товара возможен только онлайн | `tekshiruv/00-qarorlar.md` #17; eski `MARKING_CODE_INVALID`+`details.reason` o'rniga |

*(2026-10-15: qabul-6/7; 13-1'dagi `MARKING_CODE_INVALID` + `details.reason="already_sold"` o'rniga mavjud **`MARKING_CODE_ALREADY_SOLD`** ishlatiladi)*

### 15.8 E-faktura

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `EIMZO_SIGN_FAILED` *(2026-10-15: qabul-6 — eski `EINVOICE_SIGN_FAILED` o'rniga, e-faktura va davlat hisoboti tuzatishida bir xil)* | 422 | `errors.eimzo_sign_failed` | E-IMZO imzosi yaroqsiz (sertifikat/muddat) | Подпись E-IMZO недействительна | Brauzerdan kelgan imzo yaroqsiz |
| `EINVOICE_ALREADY_LINKED` | 409 | `errors.einvoice_already_linked` | Bu chekka allaqachon e-faktura bog'langan | К этому чеку уже привязана э-фактура | `02-provodka-qoidalari.md` 2.22 cheklovi |
| `EINVOICE_AMOUNT_EXCEEDS_RECEIPT` | 422 | `errors.einvoice_amount_exceeds_receipt` | E-faktura summasi chek summasidan oshmasligi kerak | Сумма э-фактуры не должна превышать сумму чека | 2.22-band cheklovi |
| `EINVOICE_COUNTERPARTY_INCOMPLETE` | 422 | `errors.einvoice_counterparty_incomplete` | Kontragent rekvizitlari to'liq emas (manzil/hisob/MFO) | Реквизиты контрагента неполные | `01-malumotlar-modeli.md` §5 |
| `EINVOICE_NOT_ACCEPTED` | 409 | `errors.einvoice_not_accepted` | Faqat qabul qilingan fakturadan kirim yaratiladi | Приход создаётся только из принятой счёт-фактуры | `from-einvoice` |
| `EINVOICE_NOT_SIGNED` | 409 | `errors.einvoice_not_signed` | Avval E-IMZO bilan imzolang | Сначала подпишите через E-IMZO | `accept`/`send` imzosiz |
| `EINVOICE_ALREADY_SIGNED` | 409 | `errors.einvoice_already_signed` | Faktura allaqachon imzolangan | Счёт-фактура уже подписана | Takror imzo |
| `EINVOICE_PROVIDER_UNAVAILABLE` | 503 | `errors.einvoice_provider_unavailable` | E-faktura operatori vaqtincha ishlamayapti | Оператор ЭСФ временно недоступен | Faktura.uz/Didox, STIR qidiruvi |

*(2026-10-15: qabul-6/7)*

### 15.8a Do'kon to'lovlari va xarid

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `PAYMENT_PROVIDER_ERROR` | 502 | `errors.payment_provider_error` | To'lov tizimi xato qaytardi, boshqa usulni tanlang | Платёжная система вернула ошибку, выберите другой способ | Checkout yaratish |
| `PAYMENT_NOT_CONFIRMED` | 422 | `errors.payment_not_confirmed` | To'lov hali tasdiqlanmagan | Платёж ещё не подтверждён | `sale.created`/`debt_payment.created` `checkout_ref`i `confirmed` emas (eski `PAYMENT_TIMEOUT` o'rniga — muddat o'tishi checkout holati `expired`) |
| `PURCHASE_ORDER_CLOSED` | 409 | `errors.purchase_order_closed` | Xaridnoma yopilgan yoki bekor qilingan | Заказ поставщику закрыт или отменён | PO'ga kirim/tahrir |
| `SUPPLIER_PAYMENT_EXCEEDS_DEBT` | 422 | `errors.supplier_payment_exceeds_debt` | To'lov summasi qarzdan ko'p | Сумма платежа превышает задолженность | Faqat `supplier_payment_strict=true` tenantda |

### 15.8b Import

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `IMPORT_FILE_INVALID` | 422 | `errors.import_file_invalid` | Fayl formati yoki kodlashi noto'g'ri | Неверный формат или кодировка файла | CSV/XLSX o'qilmadi (hajm — `FILE_TOO_LARGE`) |
| `IMPORT_JOB_NOT_VALIDATED` | 409 | `errors.import_job_not_validated` | Avval faylni tekshiring | Сначала проверьте файл | `commit` `validated`dan oldin |
| `IMPORT_JOB_ALREADY_COMMITTED` | 409 | `errors.import_job_already_committed` | Import allaqachon bajarilgan | Импорт уже выполнен | Takror `commit` |

*(2026-10-15: qabul-6/7 — yangi bo'limlar)*

### 15.9 Obuna va platforma

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `SUBSCRIPTION_RESTRICTED` | 403 | `errors.subscription_restricted` | Obuna muddati tugagan, to'lov qiling | Срок подписки истёк, оплатите | `require_subscription_ok` (`09-backend-arxitekturasi.md` §3) |
| `SUBSCRIPTION_PAYMENT_FAILED` | 422 | `errors.subscription_payment_failed` | To'lov amalga oshmadi | Платёж не выполнен | Click/Payme webhook xato |
| `ADDON_REQUIRED` | 403 | `errors.addon_required` | Bu uchun qo'shimcha xizmat kerak (masalan qo'shimcha kassa) | Для этого нужна дополнительная услуга | `tenant_addons` yo'q |

### 15.10 Sinxronizatsiya

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `SALE_NOT_FOUND` | 422 | `errors.sale_not_found` | Asl chek hali sinxronlanmagan | Исходный чек ещё не синхронизирован | `04-offline-sync.md` §3.3, `retryable: true` |
| `SYNC_SCOPE_DENIED` | 403 | `errors.sync_scope_denied` | Bu amal joriy rejimda ruxsat etilmagan | Это действие не разрешено в текущем режиме | `scope=sync.drain` token boshqa endpoint chaqirdi |
| `DEPENDENCY_NOT_SYNCED` | 422 | `errors.dependency_not_synced` | Bog'liq yozuv hali sinxronlanmagan, keyinroq qayta yuboriladi | Связанная запись ещё не синхронизирована, будет повторено | `retryable: true`; `params.entity` (`counterparties`, `transfers`, `shifts`) — boshqa qurilmadan kelgan bog'liqlik (masalan `transfer.received`) *(2026-10-15: qabul-6)* |

### 15.11 Idempotentlik

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `IDEMPOTENCY_IN_PROGRESS` | 409 | `errors.idempotency_in_progress` | So'rov allaqachon bajarilmoqda, biroz kuting | Запрос уже выполняется, подождите | Parallel bir xil `Idempotency-Key` (`09-backend-arxitekturasi.md` §3) |
| `IDEMPOTENCY_KEY_REUSED` | 422 | `errors.idempotency_key_reused` | Bu kalit boshqa so'rov uchun ishlatilgan | Этот ключ уже использован для другого запроса | Bir xil kalit, boshqa `request_hash` |

### 15.12 Davr va buxgalteriya

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `PERIOD_CLOSED` | 409 | `errors.period_closed` | Bu davr yopilgan, yozish mumkin emas | Этот период закрыт, запись невозможна | `period_closings` (`09-backend-arxitekturasi.md` §3) |
| `RECOST_REJECTED_PERIOD_CLOSED` | 409 | `errors.recost_rejected_period_closed` | Yopilgan davrga qayta hisoblash mumkin emas | Пересчёт закрытого периода невозможен | `recost_jobs.status=rejected_period_closed` |
| `PERIOD_ALREADY_CLOSED` | 409 | `errors.period_already_closed` | Bu davr allaqachon yopilgan | Этот период уже закрыт | `POST /period-closings` takror (eski `VALIDATION_ERROR` o'rniga) |
| `PERIOD_CLOSE_NOT_READY` | 409 | `errors.period_close_not_ready` | Davrni yopib bo'lmaydi: tugallanmagan qayta hisoblash yoki yuborilmagan cheklar bor | Нельзя закрыть период: есть незавершённый пересчёт или неотправленные чеки | `params.blockers` *(2026-10-15: qabul-6)* |

### 15.13 AI

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `AI_LIMIT_EXCEEDED` | 429 | `errors.ai_limit_exceeded` | Oylik AI limiti tugadi | Месячный лимит AI исчерпан | `plans.limits.ai_monthly_tokens` (`07-ai-qatlami.md` §5) |
| `AI_PROVIDER_UNAVAILABLE` | 503 | `errors.ai_provider_unavailable` | AI vaqtincha mavjud emas, boshqa funksiyalar ishlaydi | AI временно недоступен, остальные функции работают | Circuit breaker ochiq (`07-ai-qatlami.md` §12) |
| `AI_LOW_CONFIDENCE` | 200 *(amal emas — ogohlantirish bayrog'i)* | `errors.ai_low_confidence` | Ishonch darajasi past, tekshirib tasdiqlang | Низкая уверенность, проверьте и подтвердите | AI-03 maydon chegarasidan past (`07-ai-qatlami.md` §10) |
| `OCR_IMAGE_UNREADABLE` | 200 *(job `error_code`)* | `errors.ocr_image_unreadable` | Rasmdan ma'lumot o'qib bo'lmadi, aniqroq suratga oling | Не удалось распознать изображение, сделайте более чёткий снимок | `ai_ocr_jobs.status=failed` *(2026-10-15: qabul-6)* |

### 15.14 Fayl va umumiy

| code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|
| `FILE_TOO_LARGE` | 413 | `errors.file_too_large` | Fayl hajmi katta | Файл слишком большой | 12-bo'lim chegarasi |
| `UNSUPPORTED_FILE_TYPE` | 415 | `errors.unsupported_file_type` | Fayl turi qo'llab-quvvatlanmaydi | Тип файла не поддерживается | 12-bo'lim |
| `EXPORT_JOB_FAILED` | 200 *(job holati)* | `errors.export_job_failed` | Eksport muvaffaqiyatsiz bo'ldi, qayta urinib ko'ring | Экспорт не удался, попробуйте снова | 13-bo'lim |
| `WEBHOOK_SIGNATURE_INVALID` | 403 | `errors.webhook_signature_invalid` | — (tashqi tizimga qaytariladi, foydalanuvchiga ko'rinmaydi) | — | 14-bo'lim |
| `RATE_LIMITED` | 429 | `errors.rate_limited` | Juda ko'p so'rov, biroz kutib qayta urinib ko'ring | Слишком много запросов, подождите | `slowapi` umumiy limit |
| `INTERNAL_ERROR` | 500 | `errors.internal_error` | Kutilmagan xato yuz berdi | Произошла непредвиденная ошибка | Kutilmagan server istisnosi |
| `NOTIFY_CONSENT_REQUIRED` | 422 | `errors.notify_consent_required` | Mijoz xabar olishga rozilik bermagan | Клиент не дал согласия на уведомления | AI-06 yuborish, `notify_consent=false` *(2026-10-15: qabul-6)* |

### 15.15 Xaritalanadigan kodlar (API fayllarida ishlatilgan, katalogga **qo'shilmaydi**)

*(2026-10-15: qabul-6/7 — `13-api-katalog-1/2/3-*.md` fayllarida ishlatilgan, lekin generik kodga xaritalanadigan kodlar; bu qator shu fayllarni tahrirlamaydi, faqat moslikni belgilaydi.)*

| Ishlatilgan kod | Fayl | O'rniga |
|---|---|---|
| `PRODUCT_NOT_FOUND`, `CATEGORY_NOT_FOUND`, `PRICE_CHANGE_NOT_FOUND`, `LABEL_TEMPLATE_NOT_FOUND`, `OCR_DRAFT_NOT_FOUND`, `SUPPLIER_NOT_FOUND`, `GOODS_RECEIPT_NOT_FOUND`, `EINVOICE_NOT_FOUND`, `PURCHASE_ORDER_NOT_FOUND`, `SUPPLIER_RETURN_NOT_FOUND`, `TRANSFER_NOT_FOUND`, `STOCK_COUNT_NOT_FOUND`, `WRITE_OFF_NOT_FOUND`, `STOCK_OPENING_NOT_FOUND`, `RECOST_JOB_NOT_FOUND`, `MXIK_CODE_NOT_FOUND`, `COUNTERPARTY_NOT_FOUND`, `DEBT_NOT_FOUND` | 13-1, 13-2 | `NOT_FOUND` + `params.resource` |
| `PRICE_CHANGE_ALREADY_POSTED`, `GOODS_RECEIPT_ALREADY_POSTED` | 13-2 | `DOC_NOT_DRAFT` |
| `PRICE_CHANGE_NOT_PENDING`, `STOCK_COUNT_NOT_IN_REVIEW`, `TRANSFER_ALREADY_RECEIVED`, `RECOST_JOB_NOT_RETRYABLE`, `OCR_DRAFT_NOT_READY` | 13-2 | `DOC_INVALID_STATE` |
| `DOC_NOT_DRAFT` (state-reports compare/correction), `DOC_ALREADY_CANCELLED` (OCR confirm, kassa arxivi) | 13-3 | `DOC_INVALID_STATE` / `RESOURCE_ARCHIVED` |
| `PRODUCT_ARCHIVED` | 13-2 | `RESOURCE_ARCHIVED` |
| `SUPPLIER_RETURN_QTY_EXCEEDED`, `WRITE_OFF_QTY_EXCEEDS_LOT` | 13-2 | `INSUFFICIENT_STOCK` |
| `IMPORT_FILE_TOO_LARGE` | 13-2 | `FILE_TOO_LARGE` |
| `AI_UNAVAILABLE` | 13-2 | `AI_PROVIDER_UNAVAILABLE` |
| `PIN_REQUIRED` | 13-1 | ApprovalRef yo'q/yetarsiz → `APPROVAL_INVALID`; noto'g'ri PIN (`approve`) → `PIN_INVALID` |
| `FORBIDDEN` | 13-1, 13-2 | `PERMISSION_DENIED` |
| `PAYMENT_TIMEOUT` | 13-1 | checkout `status=expired` / `PAYMENT_NOT_CONFIRMED` |
| `STOCK_OPENING_PRODUCT_ALREADY_HAS_STOCK` | 13-2 | ishlatilmaydi — matndan o'chiriladi |

---

## Ochiq savollar

1. ~~Resurs nomlash ziddiyati~~ — *(2026-10-15: qabul-6/7 — HAL QILINDI: URL kebab-case ko'plik, JSON/query/enum/`operation_id` snake_case; `09-backend-arxitekturasi.md` §3 shunga moslashtirildi, `tekshiruv/00-qarorlar.md` #24. 2-bo'limga qarang.)*
2. Excel/PDF eksport signed URL muddati (13-bo'lim, 24 soat) va fayl hajmi chegaralari (12-bo'lim) — taxmin, yuklama sinovida tasdiqlanadi.
3. `message_key` uz/ru matnlari — boshlang'ich tarjima, UX-yozuvchi/tarjimon final tasdig'i kerak.
4. Rate-limit aniq raqamlari (login/OTP/AI, `12-autentifikatsiya-oauth2.md` §12ga havola) — bu faylda takrorlanmadi, lekin AI-01 chat endpoint (fayl 3) uchun alohida limit kerak bo'lishi mumkin — ochiq.

## Manbalar

- `spec/02-arxitektura/09-backend-arxitekturasi.md` §3 — API konventsiyalari (asosiy manba, resurs nomlash bandida ataylab chetga chiqildi).
- `spec/02-arxitektura/01-malumotlar-modeli.md` — jadval/maydon nomlari, UUIDv7, pul/miqdor formatlari.
- `spec/02-arxitektura/05-xavfsizlik-va-audit.md` §2.1–2.3 — ruxsat kodlari, limitlar, PIN oqimi.
- `spec/02-arxitektura/12-autentifikatsiya-oauth2.md` — auth endpoint'lari (takrorlanmadi, faqat havola).
- `spec/02-arxitektura/04-offline-sync.md` — sync endpoint'lari (takrorlanmadi, faqat havola).
- `spec/02-arxitektura/03-integratsiyalar.md` §9 — Click/Payme webhook protokoli.
- `spec/02-arxitektura/07-ai-qatlami.md` — AI xato/limit mantiqi.
- `spec/tekshiruv/qabul-6-api-db.md`, `spec/tekshiruv/qabul-7-ekran-api.md` — 2026-10-15 qabul tekshiruvi (ushbu faylga kiritilgan tuzatishlar manbasi).

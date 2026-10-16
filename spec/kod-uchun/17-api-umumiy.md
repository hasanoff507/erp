# API katalogi — 0. Umumiy konventsiyalar

**Maqsad:** Barcha modul API fayllari (`18-api-kassa.md`, `19-api-ombor.md`, `20-api-moliya-admin.md`) rioya qiladigan yagona konventsiya to'plami — resurs nomlash, ID/pul/sana formati, pagination, headerlar, xato konverti, hujjat hayot sikli, ruxsat notatsiyasi, fayl yuklash, eksport, webhook naqshi va to'liq xato kodlari katalogi.
**Kim uchun:** Backend (FastAPI) va frontend (orval/zod) ishlab chiquvchilar, API kontrakt testlari.
**Bog'liq fayllar:** `00-README.md`, `01-qarorlar.md`, `10-umumiy-arxitektura.md`, `11-malumotlar-modeli.md`, `13-provodka-qoidalari.md`, `15-xavfsizlik-va-audit.md` (§2.1–2.2), `23-backend-arxitekturasi.md` (§3), `14-autentifikatsiya-oauth2.md`, `16-offline-sync.md`, `33-1c-integratsiya.md` (§9.1 agent protokoli qoidalari, §10 veb API, §12 `ONEC_*` xato kodlari).
**Holat:** joriy, 2026-10-16.

Modulga xos endpoint ro'yxatlari bu faylda **yo'q** — faqat shakl qoidalari.

## Asosiy xulosalar

1. Barcha biznes API — `/api/v1` ostida; auth (`/oauth/*`, `/auth/*`) va sync (`/sync/*`) endpoint'lari allaqachon `14-autentifikatsiya-oauth2.md` va `16-offline-sync.md`da to'liq yozilgan — bu seriya ularni **takrorlamaydi**, faqat sharti bilan ishlatadi (masalan `require_subscription_ok`, `X-CSRF-Token`). 1C agenti yo'llari `/api/v1/onec-agent/*` — alohida agent tokeni (`aud=urn:erp:onec-agent`), CSRF'siz; protokol `33-1c-integratsiya.md` §9 da (1-bo'lim).
2. **Resurs nomlash**: URL yo'li — **kebab-case, ko'plik ot** (masalan `/goods-receipts`, `/debt-writeoffs`, `/price-changes`); JSON maydonlari, query parametrlari, enum qiymatlari va `operation_id` — **snake_case**, DB ustun nomi bilan aynan bir xil (`01-qarorlar.md` #24). `23-backend-arxitekturasi.md` §3 shu qarorga mos.
3. ID — **UUIDv7** satr (`11-malumotlar-modeli.md` §1); pul — o'nlik kasr **satr** (`"12000.00"`, 2 xona), miqdor — o'nlik kasr satr (**3 xona**, `"10.500"`), narx/tannarx — o'nlik kasr satr (**4 xona**, `"8333.3333"`); **hech qachon JSON number** (float yaxlitlash xatosi oldini olish uchun).
4. Sana ikki xil: `date` (`"2026-10-15"`, hisob sanasi, Toshkent bo'yicha) va `timestamptz` (ISO-8601, **UTC**, `"2026-10-15T09:00:00Z"`, `created_at`/`posted_at` kabi).
5. Hujjat ro'yxatlari — **cursor pagination** (`?cursor=&limit=`, standart 50, maksimum 200, javob `{items, next_cursor}`); ma'lumotnoma ro'yxatlari — **page pagination** (`?page=&size=`, javob `{items, total, page, size}`) — `23-backend-arxitekturasi.md` §3 bilan izchil (hujjat=cursor, ma'lumotnoma=page).
6. Xato konverti — yagona shakl: `{"error": {"code", "message_key", "params", "details", "request_id"}}`; `code` — barqaror mashina kaliti, `message_key` — frontend i18next kaliti, `details` — har doim massiv, maydon darajasidagi ro'yxat (`validation.*` kalitlar), `params` — ixtiyoriy biznes kontekst obyekti, `request_id` — `structlog`dagi so'rov ID'si (qo'llab-quvvatlash/audit uchun).
7. Optimistik qulflash — ma'lumotnomalarda `version INT`; `PATCH` tanada `version` talab qiladi, mos kelmasa `409 VERSION_CONFLICT`. Hujjatlar — `posted`dan keyin umuman o'zgarmaydi, faqat `POST /{id}/cancel`.
8. Hujjat (document) resurslari uchun yagona uch bosqichli hayot sikli: `POST /{resurs}` (draft yaratish) → `POST /{resurs}/{id}/post` (o'tkazish) → `POST /{resurs}/{id}/cancel` (bekor qilish, teskari yozuvlar). Ba'zi hujjatlar (masalan `sales`) faqat `/sync/push` orqali keladi — bu holat har modul faylida alohida belgilanadi.
9. To'liq xato kodlari katalogi — 15-bo'lim, jami 206 ta kod (shu jumladan «1C integratsiyasi» domenining 81 ta `ONEC_*` kodi). Bu — **yagona manba**; boshqa API fayllari (`18`–`20`) faqat shu ro'yxatdagi kodlarga havola qiladi, yangi kod shu faylga qo'shiladi.

---

## 1. Negiz (base path, versiyalash)

| Band | Qoida |
|---|---|
| Base path | `https://<domen>/api/v1/...` (`23-backend-arxitekturasi.md` §3) |
| Versiyalash | Breaking o'zgarish — `/api/v2`; eski versiya e'lon qilingan muddat (kamida 6 oy — standart, sozlanadi, qaror #54) davomida parallel saqlanadi |
| Auth/sync | Auth yo'llari — `/auth/*` (BFF, **`/api/v1`siz**), istisno — `GET /api/v1/auth/csrf` (`01-qarorlar.md` #4); OAuth protokol yo'llari — ildizda (`/oauth/*`, `/.well-known/*`); sync — `/api/v1/sync/push`, `/api/v1/sync/pull` — `16-offline-sync.md` §3; auth tafsiloti `14-autentifikatsiya-oauth2.md` §20. Bu fayl ularni qayta tasvirlamaydi |
| Platforma admin | `/platform/*` — alohida `aud=urn:erp:platform` token, tenant API'dan **butunlay ajratilgan** (`14-autentifikatsiya-oauth2.md` §18.1) |
| 1C agenti | `/api/v1/onec-agent/*` (A-01…A-10) — faqat 1C agenti tokeni: `Authorization: Bearer`, `aud=urn:erp:onec-agent`, `scope=onec.agent` (`14-autentifikatsiya-oauth2.md` §2.3); foydalanuvchi (`urn:erp:api`) tokeni bu yo'llarda, agent tokeni esa boshqa `/api/v1/*` yo'llarida rad etiladi. **CSRF yo'q** (cookie ishlatilmaydi), `Idempotency-Key` talab qilinmaydi (idempotentlik `lease_id`/`client_log_id` bilan), `X-Branch-Id` yo'q (tenant/agent faqat tokendan), majburiy headerlar `X-Agent-Version`, `X-Agent-Protocol`; ruxsat — `require_permission` emas, scope `onec.agent`. Xato konverti — 7-bo'lim. Protokol to'liq — `33-1c-integratsiya.md` §9. 1C integratsiyasining veb (BO) API'si (`/onec-agents`, `/onec-bases`, `/onec-export-batches`, …) — oddiy tenant API, barcha umumiy qoidalar amal qiladi (`33-1c-integratsiya.md` §10) |
| Health/metrika | `/health/live`, `/health/ready`, `/metrics` — `23-backend-arxitekturasi.md` §8, bu seriyaga kirmaydi |

## 2. Resurs nomlash

- **Kebab-case, ko'plik**: `/sales`, `/goods-receipts`, `/purchase-orders`, `/debt-writeoffs`, `/price-changes`, `/cash-movements`, `/stock-counts`, `/write-offs`, `/state-reports`, `/state-reports/{id}/diffs`, `/approval-requests`, `/payments/checkouts`, `/ledger-adjustments`, `/bank-settlements`, `/bank-settlements/imports`, `/tax-settlements`, `/onec-export-batches`.
- Resurs nomi — `11-malumotlar-modeli.md` jadval nomidan kelib chiqadi, faqat `_` → `-` almashtiriladi (`goods_receipts` → `/goods-receipts`); OpenAPI `operation_id` esa snake_case qoladi (`goods_receipts_create`) — frontend orval generatsiyasi shundan funksiya nomi oladi (`23-backend-arxitekturasi.md` §3).
- **JSON maydonlari — snake_case**, DB ustun nomi bilan aynan bir xil (`cash_register_id`, `doc_date`); camelCase ishlatilmaydi (frontend orval tiplari shu nomlarni oladi).
- Ichki qator resurs: `/{resurs}/{id}/{harakat}` fe'l shakli (`post`, `cancel`, `receive`, `approve`) — faqat holat o'tkazuvchi amallar uchun, CRUD uchun emas.
- **Istisno — M19 buyruq yo'llari** (`/onec-agents/pair`, `/refresh`, `/auto-match`, `/discover-bases` va shu kabi `33-1c-integratsiya.md` §10 dagi buyruqlar): holat/buyruq amallari, `/{resurs}/{id}/{fe'l}` naqshidan istisno — yo'l shakli o'zgarmaydi (`/onec-agents/pair` — RFC 8628 kodni tasdiqlash amali).
- Kesishma (cross-module) resurslar: `/reports/*`, `/platform/*`, `/admin/*`, `/billing/*`, `/ai/*` — bitta modulga tegishli bo'lmagan guruhlar, `23-backend-arxitekturasi.md` §1dagi modul papkalariga mos kelmaydi (bular `reports`/`billing`/`ai`/`access` modul papkalarining ochiq fasadi).
- **Agent yo'llari** `/onec-agent/*` — mashina-mashina protokoli (`onec_integration` modulining `router_agent.py`), resurs emas, fe'l shaklidagi yo'llar (`/hello`, `/poll`, `/tasks/{task_id}/result`) ruxsat etilgan; boshqa auth (1-bo'lim, «1C agenti» qatori).

## 3. ID, pul, miqdor, sana

| Tur | Format | Misol | Izoh |
|---|---|---|---|
| ID | UUIDv7 satr | `"01933a1e-7c9a-7c3a-9b1e-2f6a8e9d0c1a"` | `11-malumotlar-modeli.md` §1 |
| Pul | O'nlik satr, 2 xona | `"120000.00"` | `NUMERIC(18,2)`, hech qachon JSON number |
| Miqdor | O'nlik satr, 3 xona | `"10.500"` | `NUMERIC(18,3)` |
| Narx/tannarx/foiz | `price`, `cost`, `unit_cost`, `avg_cost`, `old_price`, `new_price`, `limit_value`, `requested_value` — o'nlik satr, **4 xona**; foiz (`discount_pct`, `standing_discount_pct`, `vat_rate`) — **2 xona** | `"8333.3333"` / `"5.00"` | `NUMERIC(18,4)` / `NUMERIC(5,2)` |
| Sana (hisob) | ISO-8601 `date` | `"2026-10-15"` | Toshkent bo'yicha, `doc_date` |
| Vaqt belgisi | ISO-8601 `timestamptz`, UTC, `Z` qo'shimchasi bilan | `"2026-10-15T09:00:00Z"` | `created_at`, `posted_at`, `cancelled_at`; UI Toshkent vaqtiga (`UTC+5`) o'zi o'giradi |
| Davr (oy) | `"2026-10"` (yil-oy) | — | API `"YYYY-MM"` ↔ DB `DATE` (oyning 1-sanasi) — `vat_moves.period`, `period_closings.period`, `state_reports.period`, `ledger_adjustments.correction_of_period` |
| Bool | JSON `true`/`false` | — | — |
| Enum | Pastki chiziqli snake_case satr (DB qiymati bilan bir xil) | `"posted"`, `"cash"` | Frontend zod/i18next shu qiymatni kalit sifatida ishlatadi |
| Erkin matn | `comment`, `note`, `reason` — satr, **≤ 1000 belgi** (endpointda boshqacha yozilmagan bo'lsa) | `"Mijoz qaytardi"` | Oshsa `422 VALIDATION_ERROR` (`validation.max_length`) |

## 4. Pagination

| Ro'yxat turi | Usul | So'rov | Javob |
|---|---|---|---|
| Hujjat/registr (`sales`, `ledger-entries`, `audit-log`, …) | **Cursor** (UUIDv7 `id`/`created_at` bo'yicha tabiiy vaqt tartibi) | `?cursor=<token>&limit=50` (standart 50, maksimum 200) | `{"items": [...], "next_cursor": "<token>\|null"}` |
| Ma'lumotnoma (`products`, `counterparties`, `branches`, `roles`, …) | **Page** (UI'da sahifalash ko'rsatiladi) | `?page=1&size=50` (standart 50, maksimum 200) | `{"items": [...], "total": 437, "page": 1, "size": 50}` |

To'liq ma'lumotnoma ro'yxati (page pagination): `products`, `product-categories`, `counterparties`, `discount-rules`, `roles`, `branches`, `expense-categories`, `recurring-expenses`, `label-templates`. Sahifasiz (to'liq ro'yxat, javob `{items}`): `units`, `warehouses`, `cash-registers`.

`cursor` — oldingi javobdagi `next_cursor` qiymati, bazoviy64 kodlangan `(created_at, id)` juftligi (`23-backend-arxitekturasi.md` §3, `fastapi-pagination` `CursorPage`). `next_cursor: null` — oxirgi sahifa.

## 5. Filtrlash va saralash

- Deklarativ query parametrlar (`fastapi-filter`): `?status=posted&doc_date__gte=2026-10-01&doc_date__lte=2026-10-31&branch_id=<uuid>`.
- Operator sintaksisi: `field` (teng), `field__gte`/`__lte`/`__gt`/`__lt` (son/sana oraliq), `field__in` (vergul bilan ajratilgan ro'yxat), `field__ilike` (matn qidiruv, `pg_trgm` indeksga mos).
- Saralash: `?sort=doc_date` (o'suvchi), `?sort=-doc_date` (kamayuvchi, `-` prefiks); bir nechta maydon — vergul bilan (`?sort=-doc_date,number`).
- Har endpoint o'z faylida qaysi maydonlar bo'yicha filtr/sort ruxsat etilgani jadvalda ko'rsatiladi (hammasi emas — SQL indekssiz maydon bo'yicha filtr yo'q).

## 6. Standart headerlar

| Header | Yo'nalish | Majburiyligi | Tavsif |
|---|---|---|---|
| `X-Branch-Id` | So'rov | Filialga bog'langan resurslarda majburiy | Joriy filial konteksti; `memberships.branch_ids`ga qarshi tekshiriladi, mos kelmasa `403 BRANCH_SCOPE_DENIED` (`15-xavfsizlik-va-audit.md` §2.4) |
| `Idempotency-Key` | So'rov | Barcha **yozuvchi** (POST/PUT/PATCH/DELETE) back-office so'rovlarida majburiy | UUID, frontend avtomatik generatsiya qiladi; `/sync/push` bundan mustasno (`16-offline-sync.md` dedupe `client_event_id` orqali), `/onec-agent/*` ham (idempotentlik `lease_id`/`client_log_id` bilan, `33-1c-integratsiya.md` §9.1) — `23-backend-arxitekturasi.md` §3 |
| `X-CSRF-Token` | So'rov | Cookie-autentifikatsiyali (BFF, veb) barcha yozuvchi so'rovlarda majburiy | `GET /api/v1/auth/csrf` orqali olinadi; Android va 1C agenti (`/onec-agent/*`) Bearer so'rovlari ozod (`15-xavfsizlik-va-audit.md` §1.3) |
| `Accept-Language` | So'rov | Ixtiyoriy, standart `uz` | `uz` \| `ru` — `message_key` tarjimasi va hisobot/eksport tili (`25-nofunksional-talablar.md`) |
| `Authorization: Bearer <token>` | So'rov | Android (to'g'ridan-to'g'ri API) va 1C agenti (`/onec-agent/*`, `aud=urn:erp:onec-agent`) | Veb — BFF cookie, header yo'q (`14-autentifikatsiya-oauth2.md` §2, §2.3) |
| `X-Agent-Version`, `X-Agent-Protocol` | So'rov | Faqat `/onec-agent/*` da majburiy | Agent versiyasi va protokol versiyasi (`2`); qo'llanmaydigan versiya → `426 ONEC_AGENT_UPDATE_REQUIRED` (`33-1c-integratsiya.md` §9.1) |
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

`details` — **har doim massiv** (maydon xatolari, bo'sh bo'lishi mumkin, react-hook-form/zod shakli, `23-backend-arxitekturasi.md` §3); maydon darajasidagi `message_key` — **`validation.*`** prefiksida (frontend zod `errorMap` kalitlari bilan bir xil, `08-dizayn-tizimi.md` §11). `params` — **ixtiyoriy obyekt**, biznes konteksti (limit, so'ralgan qiymat, `resource`, `reason`, `expected_status`/`actual_status`), i18next interpolatsiyasi uchun; kod darajasidagi `message_key` — `errors.*` prefiksida.

### 7.2 HTTP status qo'llanilishi

| Status | Qachon ishlatiladi |
|---|---|
| `200 OK` | Muvaffaqiyatli `GET`/amal (natija qaytaradi) |
| `201 Created` | Yangi resurs yaratildi (`POST /{resurs}`, `Location` header bilan) |
| `202 Accepted` | Asinxron ish navbatga qo'yildi (eksport job, AI OCR submit) — javobda `job_id`; 1C agenti vazifasi agent oflayn bo'lsa ham navbatga qo'yiladi, javob `warnings[]` da `ONEC_AGENT_OFFLINE` (ogohlantirish, xato emas) |
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
| `426 Upgrade Required` | `ONEC_AGENT_UPDATE_REQUIRED` — faqat `/onec-agent/*` (agent yoki protokol versiyasi eskirgan) |
| `429 Too Many Requests` | Rate-limit (login, OTP, AI, sync backpressure) |
| `500 Internal Server Error` | Kutilmagan server xatosi (`sentry-sdk`ga yoziladi) |
| `502 Bad Gateway` | Tashqi tizim xato javob berdi (`FISCAL_SEND_FAILED`, `PAYMENT_PROVIDER_ERROR`) |
| `503 Service Unavailable` | Tashqi tizim (AI provider, CRPT `MARKING_VERIFY_UNAVAILABLE`, EDO operatori `EINVOICE_PROVIDER_UNAVAILABLE`) vaqtincha ishlamaydi — faqat AI/tashqi integratsiya qatlamida, ichki tranzaksion endpoint'larda ishlatilmaydi |

## 8. Optimistik qulflash

- Ma'lumotnomalarda (`products`, `product-prices`, `roles`, `counterparties`, …) `version INT` maydoni javobda qaytariladi.
- `PATCH`/`PUT` so'rov tanasida `version` **majburiy**; server joriy qiymat bilan solishtiradi, mos kelmasa `409 VERSION_CONFLICT`, javobda joriy (server) versiya qaytariladi — frontend foydalanuvchiga "ma'lumot boshqa joyda o'zgartirilgan, qayta yuklang" ko'rsatadi.
- Hujjatlarda (`sales`, `goods-receipts`, …) `version` yo'q — `posted`dan keyin umuman o'zgarmaydi, tahrir o'rniga `POST /{id}/cancel` + yangi hujjat.

## 9. Hujjat hayot sikli endpoint naqshi

Har bir "hujjat" turidagi resurs (`11-malumotlar-modeli.md` §6, posting service naqshi — `23-backend-arxitekturasi.md` §2) uchun yagona uch endpoint shakli:

| Qadam | Endpoint | HTTP | Natija |
|---|---|---|---|
| 1. Qoralama yaratish | `POST /{resurs}` | 201 | `status=draft`, qatorlar bilan birga yoki bo'sh (keyin `PUT`/`PATCH` bilan to'ldiriladi) |
| 2. O'tkazish | `POST /{resurs}/{id}/post` | 200 | `PostingService.post()` — bitta tranzaksiyada registrlar + `status=posted`, `posted_at` (`23-backend-arxitekturasi.md` §2.1) |
| 3. Bekor qilish | `POST /{resurs}/{id}/cancel` | 200 | Tanada `reason` (majburiy, string); `PostingService.reverse()` — teskari registr yozuvlari, `status=cancelled` |

Qo'shimcha tur-xos amallar (masalan `purchase-orders/{id}/send`, `transfers/{id}/receive`, `stock-counts/{id}/submit-for-review`) — holat mashinasiga mos, har modul faylida ko'rsatiladi (`11-malumotlar-modeli.md` §8).

**Istisno**: `sales`, `returns` va boshqa POS hujjatlari backend-API orqali to'g'ridan-to'g'ri yaratilmaydi — faqat `POST /sync/push` orqali (`16-offline-sync.md` §3.1, `10-umumiy-arxitektura.md` §2). `sales`/`returns` back-office'da faqat **o'qiladi** (`GET /sales`, `GET /sales/{id}`, `GET /returns`, `GET /returns/{id}`); o'tkazilgan chek **bekor qilinmaydi** — xato faqat `return.created` bilan tuzatiladi (fiskal chek o'zgarmaydi). `sales.void` — faqat to'lovdan oldingi qoralama (`sale.draft_voided`, audit). `POST /sales` ham, `.../cancel` ham yo'q.

**Bir bosqichli hujjatlar**: `cash-movements` (back-office), `ledger-adjustments`, `supplier-payments` — `POST /{resurs}` darhol `status=posted` (`201`) qaytaradi, `draft` bosqichi yo'q; `cancel` mavjud. Uch bosqichli: `expenses`, `bank-settlements`, `tax-settlements` va qolgan hujjatlar (`20-api-moliya-admin.md` bilan bir xil). **Limitdan oshgan post** (har qanday hujjat): `202` + `{"status":"draft","approval_request_id":...}` (kod `APPROVAL_REQUIRED`) — hujjat `draft` da qoladi; `pending_approval` holati faqat `price_changes` da (qaror #25: `202 {"status":"pending_approval","approval_request_id":...}` → `posted` | `rejected`), tasdiqlanganda server o'zi o'tkazadi (`approval_requests`/`doc_approvals` mexanizmi — `18-api-kassa.md` §9, bitta so'rov bir hujjatda bir marta ishlatiladi/`consumed`).

## 10. Ruxsat (permission) notatsiyasi

Har endpoint jadvalida `permission` ustuni — `15-xavfsizlik-va-audit.md` §2.1 kodlaridan biri, masalan `sales.void`, `debts.forgive`. Notatsiya:

| Belgi | Ma'no |
|---|---|
| `kod` | Shu `permission_code` kerak (`role_permissions`da mavjud bo'lishi shart) |
| `kod (limit)` | Kod bor, lekin `role_permissions.limit_value`dan oshsa PIN/tasdiqlash oqimi (`15-xavfsizlik-va-audit.md` §2.3) ishga tushadi — `202 {status:"draft", approval_request_id}` (`APPROVAL_REQUIRED`); `pending_approval` holati faqat `price_changes` da (qaror #25) |
| `kod — faqat Egasi` | `15-xavfsizlik-va-audit.md` §2.1'da "faqat Egasi" deb belgilangan (`debts.forgive`, `billing.manage`); boshqa rolga `403 OWNER_ONLY` |
| `faqat platforma admini` | Faqat `platform_admins` (`aud=urn:erp:platform` token, `/platform/*`) — tenant rollariga berilmaydi |
| `—` | Ruxsat tekshiruvi yo'q (faqat autentifikatsiya, masalan `GET /health`) |

**Qaror** (qaror #28): **Egasi — barcha tenant ruxsatlarining supersetiga ega**, `platform.admin`dan tashqari, limitlar cheksiz; yuqoridagi "`kod` — faqat Egasi" belgisi amalda boshqa rollar uchun cheklovni bildiradi — Egasiga har doim ruxsat berilgan.

## 11. OpenAPI teglari

Har modul — bitta OpenAPI tag, `23-backend-arxitekturasi.md` §1dagi modul papkasi nomiga mos:

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
| M13 | `access` | `modules/access` (+ `modules/auth` — `14-autentifikatsiya-oauth2.md`) |
| M14 | `branches` | `modules/branches` |
| M15 | `expenses` | `modules/expenses` |
| M16 | `cash` | `modules/cash` |
| M17 | `billing` | `modules/billing` |
| M18 | `notifications` | `modules/notifications` |
| M19 | `onec` (veb API; agent yo'llari `/onec-agent/*` ham shu modulda, `router_agent.py`) | `modules/onec_integration` (`33-1c-integratsiya.md` §4.1) |
| AI | `ai` | `modules/ai` |
| — | `sync`, `auth` | `modules/sync`, `modules/auth` (alohida fayllarda) |

`operation_id` qo'lda beriladi: `<tag>_<harakat>` (masalan `debts_forgive`, `goods_receipts_post`) — orval shundan funksiya nomini oladi.

## 12. Fayl yuklash

- `multipart/form-data`, maydon nomi `file`; `python-multipart` (`23-backend-arxitekturasi.md` §5).
- Ruxsat etilgan turlar: hujjat skaneri/foto (`image/jpeg`, `image/png`, `application/pdf`), Excel import (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`), CSV import (`text/csv`).
- Chegaralar: rasm ≤ 10 MB, PDF ≤ 20 MB, Excel/CSV ≤ **10 MB**, import ≤ 20 000 qator (standart, sozlanadi — qaror #54; `19-api-ombor.md` import bilan izchil). Oshsa — `413 FILE_TOO_LARGE`. Noto'g'ri tur — `415 UNSUPPORTED_FILE_TYPE`.
- **`POST /api/v1/attachments`** — `multipart/form-data` (`file`, `kind`: `expense_receipt`/`ocr_source`/`state_report`/`import`/`export`/`label_pdf`/`billing_invoice`/`einvoice`/`other`, DB `attachments.kind`); ruxsat — autentifikatsiya + `kind`ga mos modul ruxsati (masalan `ocr_source` → `ai.ocr.use`, `expense_receipt` → `expenses.create`, `state_report` → `tax.compare.review`, `import` → `catalog.manage` yoki `stock.opening.manage` yoki `bank_settlements.manage` (biri yetarli)); `Idempotency-Key` majburiy. Javob — `201 {"id": "<attachment_id>", "url": "<signed S3 url, 15 daqiqa>", "content_type", "size_bytes"}` (`attachments` jadvali, `11-malumotlar-modeli.md` §6).
- **`GET /api/v1/attachments/{id}`** → `{id, url (yangi signed URL, 15 daqiqa), content_type, original_name}`.
- AI-03 (OCR) kabi "fayl + darhol tahlil" endpoint'larida fayl avval `attachments`ga yuklanadi, so'ng AI endpoint `attachment_id`ni qabul qiladi (`22-ai-qatlami.md` §10 oqimi) — ikki bosqich, bitta chaqiruvda emas (katta fayl AI so'rovini bloklamasligi uchun).

## 13. Excel eksport naqshi (asinxron ish)

Katta hisobotlar (`reports.export`, M12) sinxron qaytarilmaydi — ish navbatga qo'yiladi:

1. `POST /reports/{report-kod}/export` — tanada filtr/davr va `format`; javob `202 Accepted` + `{"job_id": "<uuid>", "status": "queued"}`.
2. `GET /reports/export-jobs/{job_id}` — poll; javob `{"status": "queued"|"running"|"done"|"failed", "progress_pct": 0-100, "file_url": "<signed url, done bo'lsa>", "error_code": null}`.
3. Fayl S3-mos omborda, `signed URL` 24 soat amal qiladi (standart, qaror #54); format so'rov tanasidagi `format: "xlsx"|"pdf"` maydoni bilan tanlanadi.
4. Muvaffaqiyatsiz bo'lsa `status=failed`, `error_code: EXPORT_JOB_FAILED`, `audit_log`ga `reports.export` voqeasi baribir yoziladi (urinish sifatida).

Kichik ro'yxatlar (masalan 50 qatorgacha joriy sahifa) — `?format=xlsx` bilan **sinxron** `200` + `Content-Disposition: attachment` ham mumkin (modul faylida ko'rsatiladi qaysi endpoint qaysi usulda).

## 14. Webhook naqshi (Click/Payme)

`21-integratsiyalar.md` §9 bilan izchil, bu fayl faqat API-qatlam shaklini belgilaydi:

| Band | Qoida |
|---|---|
| Yo'l | `POST /billing/webhooks/click`, `POST /billing/webhooks/payme` — tashqi tizim chaqiradi, bizning auth'imiz (cookie/Bearer) **ishlatilmaydi** |
| Imzo tekshiruvi | Click — MD5 imzo (`sign_string`), Payme — `Authorization: Basic` (merchant login:key), Uzum — JSON webhook + `Authorization: Basic` tekshiradi; mos kelmasa `403 WEBHOOK_SIGNATURE_INVALID`, so'rov yozilmaydi |
| Idempotentlik | `provider_tx_id` — `UNIQUE` (`billing_payments`); takror webhook — `200` bilan bir xil (eski) natija qaytariladi, qayta yozilmaydi (`21-integratsiyalar.md` §9) |
| Javob muddati | Kelgan so'rovga **darhol** `200` (yoki Payme/Click protokoliga mos JSON-RPC natija) qaytariladi; og'ir ishlov (fiskal/buxgalteriya ta'siri) webhook javobidan **keyin**, navbat orqali — webhook o'zi hech qachon tashqi tizimni kutmaydi |
| Click ikki bosqich | `Prepare` → `200 {error: 0}` (yoki xato kodi), `Complete` → xuddi shu yo'l, `merchant_trans_id` bo'yicha bog'lanadi |
| Payme metodlari | Bitta `POST /billing/webhooks/payme` yo'lida JSON-RPC `method` maydoni bo'yicha ichki dispatch: `CheckPerformTransaction`, `CreateTransaction`, `PerformTransaction`, `CancelTransaction`, `CheckTransaction`, `GetStatement` |
| Fiskalizatsiya | Do'kon sotuvi to'lovlarida provayder tomonidagi avto-fiskallashtirish **o'chiq** bo'lishi shart — chekni POS (`FiscalPort`) chiqaradi, ikki marta fiskallashtirish yo'q (qaror #64) |
| Ikki kontekst | Merchant modeli (qaror #46): do'kon QR/onlayn to'lovi (tenant'ning o'z merchant hisobi va kalitlari) va bizning billing (platforma merchant) — bir xil adapter interfeysi, boshqa yo'l/kalit: `POST /payments/webhooks/{provider}` (do'kon, M01 QR to'lov) vs `POST /billing/webhooks/{provider}` (bizning obuna, M17) — `21-integratsiyalar.md` §9 "muhim ajratish" |

---

## 15. Xato kodlari katalogi (to'liq, yagona jadval)

Bu — **yagona manba**; `code` ustuni barqaror (frontend/mobil/test shu bo'yicha ishlaydi), `message_key` i18next kaliti. «1C integratsiyasi» domeni (81 ta `ONEC_*` kod) `33-1c-integratsiya.md` §12 dan aynan ko'chirilgan: HTTP `—` — kod API javobida emas, faqat item/vazifa/tekshiruv natijasida (`last_error_code`, `checks[].error_code`, `warnings[]`/`blocking_issues[]`) ko'rinadi; «Qachon» ustunida sinf (`transient`/`unknown`/`config`/`validation` — qayta urinish siyosati, `warn`/`block` — tayyorlik, `api` — faqat so'rov xatosi), manba (server/agent) va foydalanuvchi harakati; `message_key` — `errors.onec.<kod>` (`warn` sinfida `warnings.onec.<kod>`), BO tuzatish maslahati — `fix_hints.onec.<kod>`. `uz`/`ru` matnlar — boshlang'ich tarjima; yakuniy nusxani Claude `08` UX-yozuv qoidalari bo'yicha tayyorlaydi, asoschi pilotdan oldin ko'zdan kechiradi, kalitlar barqaror (qaror #58). HTTP `200 *(warnings[])*` / `202 *(warnings[])*` — xato emas: amal bajarilgan (yoki navbatga qo'yilgan), kod muvaffaqiyatli javobning `warnings[]` massivida keladi. Ogohlantirish (`warnings.*`, 1C domenida `warn` sinfi) kodlari hech qachon 4xx javob bermaydi; HTTP `—` bo'lgan `warn` kodi — partiya `warnings`/tekshiruv natijasida (`checks[].status='warn'`) ko'rinadi. `ONEC_SHIFTS_OPEN` ikki rejimli: `block` — `409`, `readiness_policy='allow_open'` da `warn` — `warnings[]`. Jadval domen bo'yicha guruhlangan, takrorlar yo'q; jami **206 ta kod** (125 ta umumiy, shu jumladan 10 ta «Karta terminali» `CARD_*` kodi — qaror #71, + 81 ta `ONEC_*`). «Karta terminali» kodlari ham server API javobida, ham Do'kon agenti lokal API'sida (`21-integratsiyalar.md` §16.1, xato shakli `{code, message_key, params?}`) bir xil `code` bilan keladi; POS ularni bir xil matn bilan ko'rsatadi.

| Domen | code | HTTP | message_key | uz | ru | Qachon |
|---|---|---|---|---|---|---|
| Autentifikatsiya | `UNAUTHORIZED` | 401 | `errors.unauthorized` | Avval tizimga kiring | Сначала войдите в систему | Sessiya/token yo'q yoki yaroqsiz |
| Autentifikatsiya | `INVALID_CREDENTIALS` | 401 | `errors.invalid_credentials` | Telefon raqami yoki parol noto'g'ri | Неверный номер телефона или пароль | BO-01 login urinishi muvaffaqiyatsiz |
| Autentifikatsiya | `ACCOUNT_LOCKED` | 423 | `errors.account_locked` | Hisob vaqtincha bloklangan, keyinroq urinib ko'ring | Учётная запись временно заблокирована | Ko'p noto'g'ri urinishdan keyin (`14-autentifikatsiya-oauth2.md` §12) |
| Autentifikatsiya | `OTP_INVALID` | 400 | `errors.otp_invalid` | Tasdiqlash kodi noto'g'ri | Неверный код подтверждения | OTP mos kelmadi (kanal — Telegram/SMS, `otp_challenges.channel`) |
| Autentifikatsiya | `OTP_EXPIRED` | 400 | `errors.otp_expired` | Tasdiqlash kodi muddati o'tgan, qayta so'rang | Код подтверждения истёк, запросите новый | `otp_challenges.expires_at` o'tgan |
| Autentifikatsiya | `OTP_MAX_ATTEMPTS` | 429 | `errors.otp_max_attempts` | Urinishlar soni tugadi, birozdan keyin qayta so'rang | Превышено число попыток, попробуйте позже | `otp_challenges.max_attempts` oshdi |
| Autentifikatsiya | `OTP_CHANNEL_UNAVAILABLE` | 503 | `errors.otp_channel_unavailable` | Kod yuborib bo'lmadi (Telegram ham, SMS ham ishlamadi), birozdan keyin qayta urinib ko'ring | Не удалось отправить код (Telegram и SMS недоступны), попробуйте позже | Telegram bot va SMS (zaxira) ikkisi ham muvaffaqiyatsiz — `14-autentifikatsiya-oauth2.md` §4.2 |
| Autentifikatsiya | `TELEGRAM_NOT_LINKED` | 200 *(ma'lumot, xato emas)* | `errors.telegram_not_linked` | Telegram ulanmagan — kod SMS orqali yuborildi | Telegram не привязан — код отправлен по SMS | `/auth/otp/request` javobida `channel_used="sms"` bilan birga, foydalanuvchiga Telegram ulashni tavsiya qilish uchun |
| Autentifikatsiya | `GOOGLE_EMAIL_NOT_VERIFIED` | 403 | `errors.google_email_not_verified` | Google hisobingiz email manzili tasdiqlanmagan, boshqa usul bilan kiring | Email вашего аккаунта Google не подтверждён, войдите другим способом | `14-autentifikatsiya-oauth2.md` §2.2 |
| Autentifikatsiya | `GOOGLE_AUTH_FAILED` | 401 | `errors.google_auth_failed` | Google orqali kirish amalga oshmadi, qayta urinib ko'ring | Вход через Google не удался, попробуйте снова | `14-autentifikatsiya-oauth2.md` §2.2 |
| Autentifikatsiya | `CSRF_INVALID` | 403 | `errors.csrf_invalid` | Sahifa eskirgan, qayta yuklang | Страница устарела, обновите её | `X-CSRF-Token` yo'q/eskirgan (`15-xavfsizlik-va-audit.md` §1.3) |
| Autentifikatsiya | `TOKEN_EXPIRED` | 401 | `errors.token_expired` | Sessiya muddati tugadi, qayta kiring | Сессия истекла, войдите снова | Access token `exp` o'tgan, refresh muvaffaqiyatsiz |
| Autentifikatsiya | `TOKEN_REVOKED` | 401 | `errors.token_revoked` | Sessiya bekor qilingan | Сессия отменена | Refresh reuse detection yoki admin bekor qildi |
| Autentifikatsiya | `DEVICE_REVOKED` | 403 | `errors.device_revoked` | Qurilma bekor qilingan, qayta ro'yxatdan o'ting | Устройство отозвано, зарегистрируйтесь снова | `devices.revoked_at` to'ldirilgan (`16-offline-sync.md` §9) |
| Autentifikatsiya | `PIN_INVALID` | 400 | `errors.pin_invalid` | PIN kod noto'g'ri | Неверный PIN-код | `/auth/pin/verify` muvaffaqiyatsiz; `approval-requests` approve (PIN) |
| Validatsiya | `VALIDATION_ERROR` | 422 | `errors.validation` | Ma'lumotlarda xato bor, tekshirib qayta kiriting | В данных есть ошибка, проверьте и повторите | Pydantic validatsiya xatosi yoki biznes qoida buzilishi, `details` to'ldirilgan; masalan online/REST qarz to'lovi joriy qarzdan ko'p — `message_key=errors.debt_payment_exceeds_balance`, qaytim naqd beriladi (qaror #45); offline (`is_offline=true`) ortiqcha qarz to'lovi rad etilmaydi (qaror #67, `18-api-kassa.md` §12.2) |
| Validatsiya | `VERSION_CONFLICT` | 409 | `errors.version_conflict` | Ma'lumot boshqa joyda o'zgartirilgan, qayta yuklang | Данные изменены в другом месте, обновите страницу | Optimistik qulflash (8-bo'lim) |
| Validatsiya | `NOT_FOUND` | 404 | `errors.not_found` | Topilmadi | Не найдено | Resurs yo'q yoki boshqa tenantga tegishli |
| Validatsiya | `DOC_NOT_DRAFT` | 409 | `errors.doc_not_draft` | Hujjat qoralama holatida emas | Документ не в статусе черновика | `post`/tahrir faqat `draft`da mumkin |
| Validatsiya | `DOC_ALREADY_CANCELLED` | 409 | `errors.doc_already_cancelled` | Hujjat allaqachon bekor qilingan | Документ уже отменён | Qayta `cancel` |
| Validatsiya | `DOC_INVALID_STATE` | 409 | `errors.doc_invalid_state` | Hujjat bu amal uchun mos holatda emas | Документ не в подходящем статусе для этого действия | Umumiy holat mashinasi xatosi (masalan e-ishonchnoma `submit-signed` — faqat `pending_signature`/`failed` dan, `19-api-ombor.md` §8a); `params.expected_status`, `params.actual_status` |
| Validatsiya | `RESOURCE_ARCHIVED` | 409 | `errors.resource_archived` | Bu yozuv arxivlangan | Эта запись в архиве | Arxivlangan ma'lumotnomani tahrirlash/qayta arxivlash (masalan `POST /cash-registers/{id}/archive`, `20-api-moliya-admin.md` #40i); `params.resource` |
| Validatsiya | `SYSTEM_ROLE_READONLY` | 409 | `errors.system_role_readonly` | Tizim rolining nomini o'zgartirib bo'lmaydi | Нельзя переименовать системную роль | `PATCH /roles/{id}`, `is_system=true` |
| Validatsiya | `BARCODE_DUPLICATE` | 409 | `errors.barcode_duplicate` | Bu shtrix-kod boshqa tovarda bor | Этот штрихкод уже у другого товара | `UNIQUE (tenant_id, barcode)` |
| Validatsiya | `CATEGORY_HAS_PRODUCTS` | 409 | `errors.category_has_products` | Toifada faol tovarlar bor, avval ularni ko'chiring | В категории есть активные товары, сначала перенесите их | Kategoriya arxivlash |
| Validatsiya | `MXIK_CODE_INVALID` | 422 | `errors.mxik_code_invalid` | MXIK kodi 17 raqamdan iborat bo'lishi kerak | Код ИКПУ должен состоять из 17 цифр | Format xatosi |
| Ruxsat | `PERMISSION_DENIED` | 403 | `errors.permission_denied` | Bu amal uchun ruxsatingiz yo'q | У вас нет прав для этого действия | `require_permission` rad etdi |
| Ruxsat | `BRANCH_SCOPE_DENIED` | 403 | `errors.branch_scope_denied` | Bu filialga kirish huquqingiz yo'q | У вас нет доступа к этому филиалу | `X-Branch-Id` membership'ga mos kelmadi |
| Ruxsat | `OWNER_ONLY` | 403 | `errors.owner_only` | Bu amalni faqat Egasi bajara oladi | Это действие может выполнить только владелец | `kod — faqat Egasi` endpointlari (`debts.forgive`, `billing.manage`, lokaut eksporti) |
| Ruxsat | `PLATFORM_ADMIN_REQUIRED` | 403 | `errors.platform_admin_required` | Platforma admin huquqi kerak | Требуются права администратора платформы | `/platform/*` oddiy tenant token bilan chaqirildi |
| Ruxsat | `APPROVAL_REQUIRED` | 202 | `errors.approval_required` *(amal emas — holat)* | Tasdiqlash kutilmoqda | Ожидает подтверждения | Limitdan oshgan amal — PIN/BO-16 navbatiga tushdi (`15-xavfsizlik-va-audit.md` §2.3); `/sync/push` da — voqea natijasi `rejected` + shu kod (masalan muddati o'tgan tovar qaytarishi `returns.approve`siz — qaror #48, `18-api-kassa.md` §7.1) |
| Ruxsat | `APPROVAL_INVALID` | 403 | `errors.approval_invalid` | Tasdiq yo'q yoki tasdiqlovchining huquqi yetarli emas | Нет подтверждения или у подтверждающего недостаточно прав | `ApprovalRef` kutilgan, kelmagan / `approved_by` huquqi yoki limiti qoplamaydi |
| Ruxsat | `APPROVAL_REQUEST_ALREADY_RESOLVED` | 409 | `errors.approval_request_already_resolved` | So'rov allaqachon ko'rib chiqilgan | Запрос уже рассмотрен | Qayta approve/reject; `ApprovalRef` dagi so'rov allaqachon ishlatilgan (`consumed`) — `18-api-kassa.md` §2.4 |
| Ruxsat | `APPROVAL_REQUEST_EXPIRED` | 409 | `errors.approval_request_expired` | Tasdiqlash so'rovi muddati o'tgan, qayta yuboring | Срок запроса на подтверждение истёк, отправьте заново | `expires_at` o'tgan |
| Limitlar | `DISCOUNT_LIMIT_EXCEEDED` | 403 | `errors.discount_limit_exceeded` | Chegirma limitdan oshdi, Menejer/Egasi tasdig'i kerak | Скидка превышает лимит, нужно подтверждение менеджера | `discount.give` limit (standart 5%) |
| Limitlar | `RETURN_LIMIT_EXCEEDED` | 403 | `errors.return_limit_exceeded` | Qaytarish summasi limitdan oshdi | Сумма возврата превышает лимит | `returns.approve` limit (standart 100 000 so'm) |
| Limitlar | `CASH_WITHDRAW_LIMIT_EXCEEDED` | 403 | `errors.cash_withdraw_limit_exceeded` | Kassadan pul olish limitdan oshdi | Сумма превышает лимит на изъятие из кассы | `cash.withdraw` limit (standart 50 000 so'm) |
| Limitlar | `DEBT_LIMIT_EXCEEDED` | 403 | `errors.debt_limit_exceeded` | Mijozning kredit limiti yetarli emas | Кредитный лимит клиента превышен | `debts.create`/`counterparties.credit_limit`; offline sync'da xato emas — `200` `warnings[]` da |
| Limitlar | `PRICE_CHANGE_LIMIT_EXCEEDED` | 403 | `errors.price_change_limit_exceeded` | Narx o'zgarishi limitdan katta, tasdiqlash kerak | Изменение цены превышает лимит, нужно подтверждение | `prices.approve`, M09 |
| Limitlar | `WRITE_OFF_LIMIT_EXCEEDED` | 403 | `errors.write_off_limit_exceeded` | Hisobdan chiqarish summasi limitdan oshdi, tasdiq kerak | Сумма списания превышает лимит, нужно подтверждение | `stock.writeoff` limit |
| Limitlar | `EXPENSE_LIMIT_EXCEEDED` | 403 | `errors.expense_limit_exceeded` | Xarajat summasi limitdan oshdi, tasdiq kerak | Сумма расхода превышает лимит, нужно подтверждение | `expenses.approve` limit (`20-api-moliya-admin.md` #51 takroriy xarajat tasdig'i) |
| Ombor/qoldiq | `INSUFFICIENT_STOCK` | 422 | `errors.insufficient_stock` | Partiyada/omborda yetarli miqdor yo'q | Недостаточно количества в партии/на складе | `qty > stock_lots.qty_left` (yetkazib beruvchiga qaytarish, hisobdan chiqarish, ko'chirish); `params.lot_id`, `params.available`. Tenant siyosati xatosi — `NEGATIVE_STOCK_NOT_ALLOWED` |
| Ombor/qoldiq | `RETURN_QTY_EXCEEDED` | 422 | `errors.return_qty_exceeded` | Qaytarish miqdori sotilgandan ko'p | Количество возврата больше проданного | `11-malumotlar-modeli.md` §6 invariant |
| Ombor/qoldiq | `NEGATIVE_STOCK_NOT_ALLOWED` | 422 | `errors.negative_stock_not_allowed` | Manfiy qoldiqqa yo'l qo'yilmaydi | Отрицательный остаток не допускается | `19-api-ombor.md` write-offs/transfers `post` (`settings.negative_stock_policy='block'`) |
| Ombor/qoldiq | `LOT_NOT_FOUND` | 404 | `errors.lot_not_found` | Partiya topilmadi | Партия не найдена | FIFO allokatsiyasi uchun `stock_lots` yo'q |
| Ombor/qoldiq | `STOCK_NEGATIVE` | 200 *(ogohlantirish — `warnings[]`, amal emas)* | `warnings.stock_negative` | Qoldiq manfiyga tushdi, kirimni tekshiring | Остаток ушёл в минус, проверьте приход | Offline overselling (`16-offline-sync.md` §5) — sotuv qabul qilinadi |
| Ombor/qoldiq | `LOT_ALREADY_CONSUMED` | 409 | `errors.lot_already_consumed` | Bu kirim partiyasidan allaqachon chiqim bo'lgan, bekor qilib bo'lmaydi | Из партии этого прихода уже было списание, отмена невозможна | Kirimni bekor qilish |
| Ombor/qoldiq | `BARCODE_NOT_IN_CATALOG` | 422 | `errors.barcode_not_in_catalog` | Shtrix-kod katalogda topilmadi | Штрихкод не найден в каталоге | Inventarizatsiya skaneri |
| Ombor/qoldiq | `VALUATION_METHOD_CHANGE_NOT_ALLOWED` | 409 | `errors.valuation_method_change_not_allowed` | Baholash usuli bu yil uchun allaqachon o'zgartirilgan | Метод оценки на этот год уже изменён | `PATCH /valuation-settings` |
| Ombor/qoldiq | `WAREHOUSE_ACCOUNT_LOCKED` | 409 | `errors.warehouse_account_locked` | Omborda harakat bor — tovar hisobini o'zgartirib bo'lmaydi | По складу есть движения — счёт учёта товаров изменить нельзя | `PATCH /warehouses/{id}` `inventory_account` (`20-api-moliya-admin.md` #37a), omborda `stock_moves` bor |
| Ombor/qoldiq | `COUNT_LINES_INCOMPLETE` | 422 | `errors.count_lines_incomplete` | Sanalmagan qatorlar bor — sanab chiqing yoki nol deb qabul qiling | Есть непосчитанные строки — посчитайте или примите за ноль | `POST /stock-counts/{id}/post`, `counted IS NULL` qator bor (`19-api-ombor.md` stock-counts); `params.uncounted_count`; `?treat_uncounted_as_zero=true` bilan majburlanadi |
| Kassa/smena | `SHIFT_NOT_OPEN` | 409 | `errors.shift_not_open` | Smena ochiq emas | Смена не открыта | Yopiq/yo'q smenaga sotuv/pul harakati/xarajat |
| Kassa/smena | `SHIFT_ALREADY_OPEN` | 409 | `errors.shift_already_open` | Bu kassada smena allaqachon ochiq | На этой кассе смена уже открыта | `shift.opened`, `uq_shifts_one_open` |
| Qarz | `DEBT_ALREADY_PAID` | 409 | `errors.debt_already_paid` | Qarz allaqachon yopilgan | Долг уже закрыт | `18-api-kassa.md` §12.5 — qoldiq 0 bo'lgan qarzni kechish urinishi |
| Qarz | `DOUBTFUL_FLAG_REQUIRES_OWNER` | 403 | `errors.doubtful_flag_requires_owner` | Qarzni "shubhali" deb belgilashni faqat Egasi qila oladi | Пометить долг как сомнительный может только владелец | `18-api-kassa.md` §12.6 — `debt_doubtful_flags` (`11-malumotlar-modeli.md` §5) |
| Fiskal/markirovka | `RECEIPT_SEQ_CONFLICT` | 409 | `errors.receipt_seq_conflict` | Chek raqami takrorlangan | Номер чека повторяется | `11-malumotlar-modeli.md` §11 |
| Fiskal/markirovka | `SHIFT_DEVICE_MISMATCH` | 409 | `errors.shift_device_mismatch` | Bu smena boshqa qurilmaga tegishli | Эта смена привязана к другому устройству | `shifts.device_id` mos kelmadi |
| Fiskal/markirovka | `FISCAL_SEND_FAILED` | 502 | `errors.fiscal_send_failed` | OFD'ga yuborishda xato, qayta uriniladi | Ошибка отправки в ОФД, повтор автоматический | `fiscal_receipts.status=failed` |
| Fiskal/markirovka | `FISCAL_OFFLINE_48H_BLOCKED` | 409 | `errors.fiscal_offline_48h_blocked` | Kassa 48 soatdan beri cheklarni OFD'ga yubora olmadi — internetga ulaning, cheklar yuborilgach savdo davom etadi | Касса более 48 часов не передаёт чеки в ОФД — подключитесь к интернету, продажа возобновится после отправки | Shu `cash_register`ning `ofd_acked_at IS NULL` bo'lgan eng eski fiskal cheki ≥ 48 soat (VMQ-943 2-ilova 6-band; qaror #43): yangi fiskal chek/sotuv bloklanadi, faqat sinxron va qayta yuborish ruxsat; cheklar OFD'ga yetgach blok avtomatik yechiladi (`16-offline-sync.md` §6) |
| Fiskal/markirovka | `FISCAL_DEVICE_LOCKED` | 409 | `errors.fiscal_device_locked` | Fiskal modul bloklangan — chek chiqarib bo'lmaydi | Фискальный модуль заблокирован — выдать чек нельзя | `cash_registers.fm_state != 'ok'` (`locked`/`ack_overdue`/`memory_full`) — FM o'zi chek imzolamaydi; hamkor holat kodlari xaritasi — 26 #89 (OQ-008) |
| Fiskal/markirovka | `MARKING_CODE_INVALID` | 422 | `errors.marking_code_invalid` | Markirovka kodi noto'g'ri yoki o'qilmadi | Код маркировки неверен или не считан | DataMatrix format xatosi |
| Fiskal/markirovka | `MARKING_CODE_ALREADY_SOLD` | 409 | `errors.marking_code_already_sold` | Bu kod allaqachon sotilgan | Этот код уже продан | `marking_codes.status='sold'` |
| Fiskal/markirovka | `MARKING_PRICE_UNKNOWN_OFFLINE` | 422 | `errors.marking_price_unknown_offline` | Narx offline rejimda noma'lum, sotish mumkin emas | Цена неизвестна офлайн, продажа невозможна | `01-qarorlar.md` #17 |
| Fiskal/markirovka | `MARKING_VERIFY_FAILED` | 409 | `errors.marking_verify_failed` | Markirovka kodi CRPT tekshiruvidan o'tmadi | Код маркировки не прошёл проверку CRPT | Faqat `MARKING_PRECHECK=block` rejimida (qaror #62): CRPT kodni yaroqsiz deb topdi — sotuv rad; `warn` rejimida o'rniga `MARKING_PRECHECK_WARNING` |
| Fiskal/markirovka | `MARKING_VERIFY_UNAVAILABLE` | 503 | `errors.marking_verify_unavailable` | Asl belgisi tizimi javob bermayapti — markirovkali tovarni hozir sotib bo'lmaydi (qat'iy rejim) | Система «Асл белгиси» не отвечает — маркированный товар сейчас продать нельзя (строгий режим) | Faqat `MARKING_PRECHECK=block` rejimida: CRPT timeout; `off`/`warn` rejimida o'rniga `MARKING_PRECHECK_WARNING` |
| Fiskal/markirovka | `MARKING_PRECHECK_WARNING` | 200 *(warnings[])* | `warnings.marking_precheck` | Markirovka kodini oldindan tekshirib bo'lmadi — sotuv davom etadi, kod chek bilan OFD'ga yuboriladi | Предварительная проверка кода маркировки не пройдена — продажа продолжается, код уходит в ОФД в составе чека | `MARKING_PRECHECK=warn` (standart, qaror #62): CRPT rad etdi yoki javob bermadi; `audit_log`ga yoziladi; lokal takror-kod tekshiruvi baribir `MARKING_CODE_ALREADY_SOLD` beradi |
| Fiskal/markirovka | `MARKING_RETURN_REQUIRES_ONLINE` | 422 | `errors.marking_return_requires_online` | Markirovkalangan tovarni faqat internet bor paytda qaytarish mumkin | Возврат маркированного товара возможен только онлайн | `01-qarorlar.md` #17 |
| Karta terminali | `CARD_TERMINAL_UNREACHABLE` | 503 | `errors.card_terminal_unreachable` | Karta terminali ulanmagan — terminal yoki Do'kon agentini tekshiring | Карточный терминал не подключён — проверьте терминал или агент магазина | Agent/terminal javob bermaydi, `health` = `offline`/`error`, `cloud` adapterda vendor API ishlamaydi (qaror #71). POS integratsiyalangan yo'lni yopadi, zaxira — terminalsiz karta (rekvizitsiz) `card_manual_fallback` bo'yicha |
| Karta terminali | `CARD_TERMINAL_BUSY` | 409 | `errors.card_terminal_busy` | Terminal band — oldingi to'lov tugashini kuting | Терминал занят — дождитесь завершения предыдущей оплаты | Shu terminalda boshqa urinish `pending` (agent `DeviceLane` FIFO; serverda `uq_ctt_one_pending`) |
| Karta terminali | `CARD_TERMINAL_TIMEOUT` | 504 | `errors.card_terminal_timeout` | Terminal javob bermadi — natija tekshirilmoqda | Терминал не ответил — проверяем результат | `purchase` 120 s / `refund`/`void` 60 s taymauti yoki aloqa uzildi; urinish `unknown` bo'ladi va POS darhol holat so'rovini bajaradi (`purchase` qayta yuborilmaydi) |
| Karta terminali | `CARD_DECLINED` | 200 *(`status:"declined"`)* | `errors.card_declined` | To'lov rad etildi: {decline_message} | Оплата отклонена: {decline_message} | Bank/terminal rad etdi yoki mijoz terminalda bekor qildi — xato javob emas, `CardTxResult.status='declined'`; boshqa usul yoki yangi `attempt_id` bilan qayta urinish |
| Karta terminali | `CARD_OUTCOME_UNKNOWN` | 409 | `errors.card_outcome_unknown` | Oldingi karta to'lovining natijasi noma'lum — terminal chekini tekshiring | Результат предыдущей оплаты картой неизвестен — проверьте чек терминала | Shu terminalda/chekda `unknown` urinish hal qilinmagan — yangi `purchase` bloklanadi; holat so'rovi yoki menejer tasdig'i (`card_manual_entry`, `card.manual_entry.approve`; menejer terminal chekiga qarab faqat "o'tdi / o'tmadi"ni tasdiqlaydi, hech narsa kiritmaydi) bilan yopiladi |
| Karta terminali | `CARD_AMOUNT_MISMATCH` | 422 | `errors.card_amount_mismatch` | Terminal tasdiqlagan summa chek summasiga mos emas — to'lov bekor qilindi | Сумма, подтверждённая терминалом, не совпадает с суммой чека — оплата отменена | `CardTxResult.amount_tiyin` ≠ so'ralgan; POS avtomatik `void` qiladi (`card.void.auto`), to'lov qabul qilinmaydi |
| Karta terminali | `CARD_MANUAL_NOT_ALLOWED` | 403 | `errors.card_manual_not_allowed` | Bu do'konda kartani terminalsiz qabul qilish taqiqlangan | В этом магазине приём карты без терминала запрещён | `tenants.settings.card_manual_fallback='forbid'` — faol integratsiyalangan terminal bog'langan kassada terminalsiz (rekvizitsiz, `card_entry_mode='manual'`) karta to'lovi/qaytarishi rad etiladi (online; offline'da POS o'zi yopadi); terminal bog'lanmagan kassada (`standalone_terminal`) qo'llanmaydi — karta faqat summa bilan, har doim ruxsat |
| Karta terminali | `CARD_MANUAL_APPROVAL_REQUIRED` | 403 | `errors.card_manual_approval_required` | Kartani terminalsiz qabul qilish uchun menejer tasdig'i kerak | Для приёма карты без терминала нужно подтверждение менеджера | Faqat faol integratsiyalangan terminal bog'langan kassada: `card_manual_fallback='manager_approval'` (sozlama yo'q bo'lsa standart), so'rovda `card_manual_approval` (`ApprovalRef`, tasdiq turi `card_manual_entry`, tasdiqlovchida `card.manual_entry.approve`) yo'q — POS-06 PIN oynasi ochiladi (`15-xavfsizlik-va-audit.md` §2.3) |
| Karta terminali | `CARD_VOID_FAILED` | 502 | `errors.card_void_failed` | Karta to'lovini bekor qilib bo'lmadi — menejerga xabar berildi | Не удалось отменить оплату картой — менеджер уведомлён | Avtomatik `void`/`refund` (kassir sotuvni bekor qilganda yoki `CARD_AMOUNT_MISMATCH`da) terminalda bajarilmadi (terminal xatosi, aloqa uzildi); sotuv bekor qilinmaydi; BO-14 va Egasiga M18, qo'lda hal qilinadi (`card.void.failed`) |
| Karta terminali | `CARD_TRANSACTION_MISMATCH` | 409 / 200 *(warnings[])* | `errors.card_transaction_mismatch` | Karta tranzaksiyasi ma'lumoti serverdagi bilan mos emas — Buxgalter tekshiradi | Данные карточной транзакции не совпадают с сервером — проверит бухгалтер | Voqeadagi `card_result` yoki `POST /card-terminal-transactions` serverdagi qator/to'lov bilan farq qiladi (summa, takroriy `tid`+`rrn`, boshqa hujjatga bog'langan `attempt_id`, yakuniy holatni almashtirish urinishi); `POST /card-terminal-transactions` — `409`; sinxron voqea rad etilmaydi (`warnings[]`) — `sync_exceptions(kind='card_result_mismatch')` (`16-offline-sync.md` §2.1, §5) |
| E-faktura | `EIMZO_SIGN_FAILED` | 422 | `errors.eimzo_sign_failed` | E-IMZO imzosi yaroqsiz (sertifikat/muddat) | Подпись E-IMZO недействительна | Brauzerdan kelgan imzo yaroqsiz — e-faktura, e-TTN, e-ishonchnoma (`19-api-ombor.md` §8a) `submit-signed` |
| E-faktura | `EINVOICE_ALREADY_LINKED` | 409 | `errors.einvoice_already_linked` | Bu chekka allaqachon e-faktura bog'langan | К этому чеку уже привязана э-фактура | `13-provodka-qoidalari.md` 2.22 cheklovi |
| E-faktura | `EINVOICE_AMOUNT_EXCEEDS_RECEIPT` | 422 | `errors.einvoice_amount_exceeds_receipt` | E-faktura summasi chek summasidan oshmasligi kerak | Сумма э-фактуры не должна превышать сумму чека | 2.22-band cheklovi |
| E-faktura | `EINVOICE_COUNTERPARTY_INCOMPLETE` | 422 | `errors.einvoice_counterparty_incomplete` | Kontragent rekvizitlari to'liq emas (manzil/hisob/MFO) | Реквизиты контрагента неполные | `11-malumotlar-modeli.md` §5 |
| E-faktura | `EINVOICE_NOT_ACCEPTED` | 409 | `errors.einvoice_not_accepted` | Faqat qabul qilingan fakturadan kirim yaratiladi | Приход создаётся только из принятой счёт-фактуры | `from-einvoice` |
| E-faktura | `EINVOICE_NOT_SIGNED` | 409 | `errors.einvoice_not_signed` | Avval E-IMZO bilan imzolang | Сначала подпишите через E-IMZO | `accept`/`send` imzosiz |
| E-faktura | `EINVOICE_ALREADY_SIGNED` | 409 | `errors.einvoice_already_signed` | Faktura allaqachon imzolangan | Счёт-фактура уже подписана | Takror imzo |
| E-faktura | `EINVOICE_PROVIDER_UNAVAILABLE` | 503 | `errors.einvoice_provider_unavailable` | E-faktura operatori vaqtincha ishlamayapti | Оператор ЭСФ временно недоступен | Faktura.uz/Didox: e-faktura, e-TTN, e-ishonchnoma (`19-api-ombor.md` §8a) yuborish, STIR qidiruvi |
| E-faktura | `ETTN_REQUIRED` | 409 *(offline voqeada — 200 warnings[])* | `errors.ettn_required` | Ko'chirishni jo'natishdan oldin e-TTN rasmiylashtirilishi kerak | Перед отправкой перемещения необходимо оформить э-ТТН | Ichki ko'chirish (`transfers`, `transport_mode='vehicle'`) e-TTN (`ettn_ref`) rasmiylashtirilmaguncha jo'natilmaydi (qaror #63, `19-api-ombor.md` §13); offline `transfer.sent` da — `warnings[]` ichida, hujjat `posted` holatida qoladi |
| E-faktura | `ETTN_CANCEL_IN_OPERATOR` | 200 *(warnings[])* | `warnings.ettn_cancel_in_operator` | Ko'chirish bekor qilindi; e-TTN'ni operator kabinetida bekor qiling yoki tuzating | Перемещение отменено; аннулируйте или исправьте ЭТТН в кабинете оператора | `POST /transfers/{id}/cancel` — e-TTN allaqachon `registered` (`19-api-ombor.md` §13) |
| To'lov/xarid | `PAYMENT_PROVIDER_ERROR` | 502 | `errors.payment_provider_error` | To'lov tizimi xato qaytardi, boshqa usulni tanlang | Платёжная система вернула ошибку, выберите другой способ | Checkout yaratish |
| To'lov/xarid | `PAYMENT_NOT_CONFIRMED` | 422 | `errors.payment_not_confirmed` | To'lov hali tasdiqlanmagan | Платёж ещё не подтверждён | `sale.created`/`debt_payment.created` `checkout_ref`i `confirmed` emas yoki allaqachon `consumed` (muddat o'tishi checkout holati `expired`) — `18-api-kassa.md` §4.6, §12.2 |
| To'lov/xarid | `PURCHASE_ORDER_CLOSED` | 409 | `errors.purchase_order_closed` | Xaridnoma yopilgan yoki bekor qilingan | Заказ поставщику закрыт или отменён | PO'ga kirim/tahrir |
| To'lov/xarid | `SUPPLIER_OVERPAY_BLOCKED` | 422 | `errors.supplier_overpay_blocked` | To'lov summasi qarzdan ko'p — sozlama ortiqcha to'lovni taqiqlaydi | Сумма платежа превышает долг — настройка запрещает переплату | `tenants.settings.supplier_overpay_policy='block'` (qaror #47) |
| To'lov/xarid | `SUPPLIER_OVERPAY_ADVANCE` | 200 *(warnings[])* | `warnings.supplier_overpay_advance` | To'lov qarzdan ko'p — ortiqcha qism avans sifatida yozildi | Платёж превышает долг — излишек учтён как аванс | `supplier_overpay_policy='warn'` (standart, qaror #47): ortig'i — avans 4310 |
| Import | `IMPORT_FILE_INVALID` | 422 | `errors.import_file_invalid` | Fayl formati yoki kodlashi noto'g'ri | Неверный формат или кодировка файла | CSV/XLSX o'qilmadi (hajm — `FILE_TOO_LARGE`) |
| Import | `IMPORT_JOB_NOT_VALIDATED` | 409 | `errors.import_job_not_validated` | Avval faylni tekshiring | Сначала проверьте файл | `commit` `validated`dan oldin |
| Import | `IMPORT_JOB_ALREADY_COMMITTED` | 409 | `errors.import_job_already_committed` | Import allaqachon bajarilgan | Импорт уже выполнен | Takror `commit` |
| Bank ko'chirmasi | `BANK_IMPORT_FILE_INVALID` | 422 | `errors.bank_import_file_invalid` | Bank ko'chirmasi fayli o'qilmadi (1CClientBankExchange formati kutiladi) | Файл выписки не распознан (ожидается формат 1CClientBankExchange) | `POST /bank-settlements/imports` — sarlavha, bo'limlar yoki kodlash xato (`20-api-moliya-admin.md`) |
| Bank ko'chirmasi | `BANK_IMPORT_ACCOUNT_MISMATCH` | 422 | `errors.bank_import_account_mismatch` | Ko'chirmadagi hisob raqami do'kon bank hisobiga mos emas | Счёт в выписке не совпадает с банковским счётом магазина | `СекцияРасчСчет` dagi `РасчСчет` tenant bank hisobi rekvizitiga teng emas |
| Bank ko'chirmasi | `BANK_IMPORT_DUPLICATE` | 409 | `errors.bank_import_duplicate` | Bu ko'chirma allaqachon yuklangan | Эта выписка уже загружена | Shu fayl (xesh bo'yicha) avval import qilingan; qoralamalar qayta yaratilmaydi |
| Obuna/platforma | `SUBSCRIPTION_RESTRICTED` | 403 | `errors.subscription_restricted` | Obuna muddati tugagan, to'lov qiling | Срок подписки истёк, оплатите | `require_subscription_ok` (`23-backend-arxitekturasi.md` §3) |
| Obuna/platforma | `SUBSCRIPTION_PAYMENT_FAILED` | 422 | `errors.subscription_payment_failed` | To'lov amalga oshmadi | Платёж не выполнен | Click/Payme webhook xato |
| Obuna/platforma | `ADDON_REQUIRED` | 403 | `errors.addon_required` | Bu uchun qo'shimcha xizmat kerak (masalan qo'shimcha kassa) | Для этого нужна дополнительная услуга | `tenant_addons` yo'q |
| Sinxronizatsiya | `SALE_NOT_FOUND` | 422 | `errors.sale_not_found` | Asl chek hali sinxronlanmagan | Исходный чек ещё не синхронизирован | `16-offline-sync.md` §3.3, `retryable: true` |
| Sinxronizatsiya | `SYNC_SCOPE_DENIED` | 403 | `errors.sync_scope_denied` | Bu amal joriy rejimda ruxsat etilmagan | Это действие не разрешено в текущем режиме | `scope=sync.drain` token boshqa endpoint chaqirdi |
| Sinxronizatsiya | `DEPENDENCY_NOT_SYNCED` | 422 | `errors.dependency_not_synced` | Bog'liq yozuv hali sinxronlanmagan, keyinroq qayta yuboriladi | Связанная запись ещё не синхронизирована, будет повторено | `retryable: true`; `params.entity` (`counterparties`, `transfers`, `shifts`) — boshqa qurilmadan kelgan bog'liqlik (masalan `transfer.received`); `18-api-kassa.md` §4.6, §7.1, §12.2 |
| Idempotentlik | `IDEMPOTENCY_IN_PROGRESS` | 409 | `errors.idempotency_in_progress` | So'rov allaqachon bajarilmoqda, biroz kuting | Запрос уже выполняется, подождите | Parallel bir xil `Idempotency-Key` (`23-backend-arxitekturasi.md` §3) |
| Idempotentlik | `IDEMPOTENCY_KEY_REUSED` | 422 | `errors.idempotency_key_reused` | Bu kalit boshqa so'rov uchun ishlatilgan | Этот ключ уже использован для другого запроса | Bir xil kalit, boshqa `request_hash` |
| Davr/buxgalteriya | `PERIOD_CLOSED` | 409 | `errors.period_closed` | Bu davr yopilgan, yozish mumkin emas | Этот период закрыт, запись невозможна | Faqat back-office REST: `doc_date` yopilgan davrda (`period_closings`, `23-backend-arxitekturasi.md` §3); `cancel` endpointlarida yo'q — storno joriy ochiq davr sanasida (`13-provodka-qoidalari.md` §5.2); POS sync voqealari rad etilmaydi — registr yozuvlari birinchi ochiq davrda (`16-offline-sync.md` §3.4, qaror #69) |
| Davr/buxgalteriya | `RECOST_REJECTED_PERIOD_CLOSED` | 409 | `errors.recost_rejected_period_closed` | Yopilgan davrga qayta hisoblash mumkin emas | Пересчёт закрытого периода невозможен | `19-api-ombor.md` recost-jobs retry — `recost_jobs.status=rejected_period_closed` |
| Davr/buxgalteriya | `PERIOD_ALREADY_CLOSED` | 409 | `errors.period_already_closed` | Bu davr allaqachon yopilgan | Этот период уже закрыт | `POST /period-closings` takror |
| Davr/buxgalteriya | `PERIOD_CLOSE_NOT_READY` | 409 | `errors.period_close_not_ready` | Davrni yopib bo'lmaydi: tugallanmagan qayta hisoblash, yuborilmagan cheklar yoki sinxronlanmagan qurilmalar bor | Нельзя закрыть период: есть незавершённый пересчёт, неотправленные чеки или несинхронизированные устройства | `params.blockers` (`recost_pending`, `fiscal_pending`, `devices_unsynced`) — `20-api-moliya-admin.md` #15/#16 |
| Davr/buxgalteriya | `PERIOD_CLOSE_OUT_OF_ORDER` | 409 | `errors.period_close_out_of_order` | Faqat eng eski ochiq oy yopiladi | Закрывается только самый ранний открытый месяц | `POST /period-closings` (`20-api-moliya-admin.md` #15); `params.oldest_open_period` |
| AI | `AI_LIMIT_EXCEEDED` | 429 | `errors.ai_limit_exceeded` | Oylik AI limiti tugadi | Месячный лимит AI исчерпан | `plans.limits.ai_monthly_tokens` (`22-ai-qatlami.md` §5) |
| AI | `AI_PROVIDER_UNAVAILABLE` | 503 | `errors.ai_provider_unavailable` | AI vaqtincha mavjud emas, boshqa funksiyalar ishlaydi | AI временно недоступен, остальные функции работают | Circuit breaker ochiq (`22-ai-qatlami.md` §12) |
| AI | `AI_LOW_CONFIDENCE` | 200 *(holat belgisi, xato emas)* | `errors.ai_low_confidence` | Ishonch darajasi past, tekshirib tasdiqlang | Низкая уверенность, проверьте и подтвердите | AI-03 maydon chegarasidan past (`22-ai-qatlami.md` §10): `200` javobda `low_confidence_fields[]` / `fields.header[].low_confidence`; OpenAPI'da xato javobi sifatida e'lon qilinmaydi (qaror #55) |
| AI | `OCR_IMAGE_UNREADABLE` | 200 *(job `error_code`)* | `errors.ocr_image_unreadable` | Rasmdan ma'lumot o'qib bo'lmadi, aniqroq suratga oling | Не удалось распознать изображение, сделайте более чёткий снимок | `ai_ocr_jobs.status=failed` |
| AI | `AI_CONSENT_REQUIRED` | 403 | `errors.ai_consent_required` | AI uchun ma'lumotni chet elga uzatishga rozilik berilmagan | Не дано согласие на трансграничную передачу данных для AI | `tenants.settings.ai_cross_border_enabled=false` — AI-03 rasmlari (maskalab bo'lmaydigan ma'lumot) Egasi rozilik bermaguncha yuborilmaydi (qaror #61, `15-xavfsizlik-va-audit.md` §5) |
| AI | `AI_FEATURE_DISABLED` | 403 | `errors.ai_feature_disabled` | Bu AI funksiyasi do'kon sozlamalarida o'chirilgan | Эта функция AI отключена в настройках магазина | `tenants.settings.ai.<feature>_enabled=false` (masalan `ai.ocr_enabled=false` — `20-api-moliya-admin.md` #73); `params.feature` |
| Fayl/umumiy | `FILE_TOO_LARGE` | 413 | `errors.file_too_large` | Fayl hajmi katta | Файл слишком большой | 12-bo'lim chegarasi |
| Fayl/umumiy | `UNSUPPORTED_FILE_TYPE` | 415 | `errors.unsupported_file_type` | Fayl turi qo'llab-quvvatlanmaydi | Тип файла не поддерживается | 12-bo'lim |
| Fayl/umumiy | `EXPORT_JOB_FAILED` | 200 *(job holati)* | `errors.export_job_failed` | Eksport muvaffaqiyatsiz bo'ldi, qayta urinib ko'ring | Экспорт не удался, попробуйте снова | 13-bo'lim |
| Fayl/umumiy | `WEBHOOK_SIGNATURE_INVALID` | 403 | `errors.webhook_signature_invalid` | — (tashqi tizimga qaytariladi, foydalanuvchiga ko'rinmaydi) | — | 14-bo'lim |
| Fayl/umumiy | `RATE_LIMITED` | 429 | `errors.rate_limited` | Juda ko'p so'rov, biroz kutib qayta urinib ko'ring | Слишком много запросов, подождите | `slowapi` umumiy limit; `POST /ai/chat` — 10 so'rov/daqiqa/foydalanuvchi, 300 so'rov/kun/tenant (qaror #55) |
| Fayl/umumiy | `INTERNAL_ERROR` | 500 | `errors.internal_error` | Kutilmagan xato yuz berdi | Произошла непредвиденная ошибка | Kutilmagan server istisnosi |
| Fayl/umumiy | `NOTIFY_CONSENT_REQUIRED` | 422 | `errors.notify_consent_required` | Mijoz xabar olishga rozilik bermagan | Клиент не дал согласия на уведомления | AI-06 yuborish, `notify_consent=false` |
| Do'kon agenti | `AGENT_CAPABILITY_DISABLED` | 409 | `errors.agent_capability_disabled` | Do'kon agentida bu imkoniyat yoqilmagan | На агенте магазина эта возможность не включена | Agent vazifasi navbatga qo'yilganda (`AgentTaskPort.enqueue`) `onec_agents.capabilities.<oila>.enabled` `true` emas (qaror #66); `params.capability`; `ONEC_*` sanog'iga kirmaydi |
| 1C integratsiyasi | `ONEC_AGENT_OFFLINE` | 202 *(`warnings[]`, amal bajariladi)* | `warnings.onec.agent_offline` | Do'kon kompyuteri ({pc_name}) {since} dan beri aloqada emas | Компьютер магазина ({pc_name}) не на связи с {since} | Sinf `warn`, manba — server. Harakat: Kompyuterni yoqing, «ERP 1C Agent» ishlayotganini tekshiring; vazifa navbatda kutadi |
| 1C integratsiyasi | `ONEC_AGENT_REVOKED` | 403 | `errors.onec.agent_revoked` | Bu kompyuter uzilgan | Этот компьютер отключён | Sinf `api`, manba — server. Harakat: Agentni qayta ulang (BO-22 → «Kompyuterni ulash») |
| 1C integratsiyasi | `ONEC_AGENT_UPDATE_REQUIRED` | 426 | `errors.onec.agent_update_required` | Agent eskirgan, yangilash kerak | Агент устарел, требуется обновление | Sinf `api`, manba — server. Harakat: Agent avtomatik yangilanadi; bo'lmasa qayta o'rnating |
| 1C integratsiyasi | `ONEC_PAIRING_CODE_INVALID` | 404 | `errors.onec.pairing_code_invalid` | Ulash kodi topilmadi | Код подключения не найден | Sinf `api`, manba — server. Harakat: Agent oynasidagi kodni qayta tekshiring |
| 1C integratsiyasi | `ONEC_PAIRING_CODE_EXPIRED` | 409 | `errors.onec.pairing_code_expired` | Ulash kodi muddati o'tgan | Срок кода подключения истёк | Sinf `api`, manba — server. Harakat: Agentda «Yangi kod» |
| 1C integratsiyasi | `ONEC_BASE_DUPLICATE` | 409 | `errors.onec.base_duplicate` | Bu 1C bazasi boshqa kompyuterga ({agent_name}) ulangan | Эта база 1С уже подключена к другому компьютеру ({agent_name}) | Sinf `api`, manba — server. Harakat: BO-22 → «Bu kompyuterga o'tkazish» |
| 1C integratsiyasi | `ONEC_BASE_NOT_READY` | 409 | `errors.onec.base_not_ready` | 1C bazasi hali tayyor emas (tekshiruvlar, sozlamalar yoki moslashtirish) | База 1С ещё не готова (проверки, настройки или сопоставление) | Sinf `block`, manba — server. Harakat: BO-22 tekshiruvlari va sozlamalari |
| 1C integratsiyasi | `ONEC_BASE_NOT_ON_PC` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.base_not_on_pc` | Baza kompyuterdagi agent ro'yxatida yo'q | База отсутствует в списке агента на компьютере | Sinf `config`, manba — server. Harakat: Agent oynasida bazani qayta qo'shing |
| 1C integratsiyasi | `ONEC_WRITE_DISABLED` | 409 | `errors.onec.write_disabled` | 1C ga yozish o'chirilgan (server sozlamasi) | Запись в 1С отключена (настройка сервера) | Sinf `config`, manba — server/agent. Harakat: BO-22 → «1C ga yozishga ruxsat» |
| 1C integratsiyasi | `ONEC_PC_WRITE_DISABLED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.pc_write_disabled` | Kompyuterda bu bazaga yozish ruxsati o'chiq | На компьютере запись в эту базу отключена | Sinf `config`, manba — agent. Harakat: Agent oynasida «Bu bazaga yozishga ruxsat» ni yoqing |
| 1C integratsiyasi | `ONEC_PROFILE_UNSUPPORTED` | 422 | `errors.onec.profile_unsupported` | Bu 1C konfiguratsiyasi qo'llab-quvvatlanmaydi ({config}) | Эта конфигурация 1С не поддерживается ({config}) | Sinf `config`, manba — server. Harakat: Hozircha faqat «Бухгалтерия для Узбекистана 3.0» |
| 1C integratsiyasi | `ONEC_CLOUD_BASE_UNSUPPORTED` | 422 | `errors.onec.cloud_base_unsupported` | Bulutdagi (veb) 1C bazasi qo'llab-quvvatlanmaydi | Облачная (веб) база 1С не поддерживается | Sinf `api`, manba — server. Harakat: Faqat kompyuterdagi yoki serverdagi baza |
| 1C integratsiyasi | `ONEC_EDITION_NO_COM` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.edition_no_com` | 1C «Базовая» versiyasi tashqi ulanishni qo'llamaydi — ПРОФ kerak | Базовая версия 1С не поддерживает внешнее соединение — нужна ПРОФ | Sinf `config`, manba — agent. Harakat: ПРОФ litsenziyasiga o'tish |
| 1C integratsiyasi | `ONEC_SALE_PRICE_ACCOUNTING_UNSUPPORTED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.sale_price_accounting_unsupported` | 1C'da tovar sotish narxida hisoblanadi — qo'llab-quvvatlanmaydi | В 1С товары учитываются по продажной стоимости — не поддерживается | Sinf `config`, manba — server. Harakat: Buxgalter bilan hisob siyosatini muhokama qiling |
| 1C integratsiyasi | `ONEC_TAX_REGIME_MISMATCH` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.tax_regime_mismatch` | ERP va 1C soliq rejimi (QQS/aylanma) mos emas | Налоговый режим ERP и 1С (НДС/оборот) не совпадает | Sinf `config`, manba — server. Harakat: Buxgalter rejimni moslaydi |
| 1C integratsiyasi | `ONEC_ORGANIZATION_NOT_FOUND` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.organization_not_found` | 1C'da STIR {stir} bilan tashkilot topilmadi | В 1С не найдена организация с ИНН {stir} | Sinf `config`, manba — server. Harakat: 1C'da tashkilot STIR'ini to'g'rilang (ERP yaratmaydi) |
| 1C integratsiyasi | `ONEC_METADATA_MISMATCH` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.metadata_mismatch` | 1C konfiguratsiyasida kerakli maydon yo'q: {names} | В конфигурации 1С нет нужных реквизитов: {names} | Sinf `config`, manba — server/agent. Harakat: Qo'llab-quvvatlashga murojaat (profil tuzatiladi) |
| 1C integratsiyasi | `ONEC_MARKING_CHECK_ENABLED` | — *(`warnings[]`/tekshiruv natijasi; xato emas)* | `warnings.onec.marking_check_enabled` | 1C'da markirovka nazorati yoqilgan — markirovkali tovar hujjati o'tmasligi mumkin | В 1С включён контроль маркировки — документ с маркированным товаром может не провестись | Sinf `warn`, manba — server. Harakat: Buxgalter bilan kelishing |
| 1C integratsiyasi | `ONEC_USER_TOO_PRIVILEGED` | — *(`warnings[]`/tekshiruv natijasi; xato emas)* | `warnings.onec.user_too_privileged` | Agent 1C'ga to'liq huquqli foydalanuvchi bilan ulangan | Агент подключён к 1С пользователем с полными правами | Sinf `warn`, manba — agent. Harakat: Alohida «ERP integratsiya» foydalanuvchisi yarating |
| 1C integratsiyasi | `ONEC_LICENSE_SEPARATE_REQUIRED` | — *(`warnings[]`/tekshiruv natijasi; xato emas)* | `warnings.onec.license_separate_required` | Bu bazada agent uchun alohida 1C litsenziyasi kerak (server litsenziyasi, RDP yoki veb-server) | Для агента в этой базе нужна отдельная лицензия 1С (серверная лицензия, RDP или веб-сервер) | Sinf `warn`, manba — server/agent. Harakat: Agent uchun klient litsenziyasi oling yoki yuborishni 1C yopiq vaqtga qo'ying |
| 1C integratsiyasi | `ONEC_NEGATIVE_STOCK_ALLOWED` | — *(`warnings[]`/tekshiruv natijasi; xato emas)* | `warnings.onec.negative_stock_allowed` | 1C'da qoldiqsiz hisobdan chiqarishga ruxsat yoqilgan — tannarx nol bo'lishi mumkin | В 1С разрешено списание при отсутствии остатков — себестоимость может быть нулевой | Sinf `warn`, manba — server. Harakat: Buxgalter bilan kelishing; kirimlar 1C'da borligini tekshiring |
| 1C integratsiyasi | `ONEC_SETTING_NOT_SUPPORTED` | 422 | `errors.onec.setting_not_supported` | Bu sozlama hozircha qo'llab-quvvatlanmaydi | Эта настройка пока не поддерживается | Sinf `api`, manba — server. Harakat: Standart qiymatni qoldiring |
| 1C integratsiyasi | `ONEC_BEFORE_START_DATE` | 422 | `errors.onec.before_start_date` | Sana 1C eksporti boshlanish sanasidan ({start_date}) oldin | Дата раньше даты начала выгрузки в 1С ({start_date}) | Sinf `block`, manba — server. Harakat: Sanani tekshiring yoki BO-22 da boshlanish sanasi |
| 1C integratsiyasi | `ONEC_NOTHING_TO_EXPORT` | 422 | `errors.onec.nothing_to_export` | Bu kunda 1C ga yuboriladigan hujjat yo'q | За этот день нет документов для выгрузки в 1С | Sinf `api`, manba — server. Harakat: — |
| 1C integratsiyasi | `ONEC_BATCH_INVALID_STATE` | 409 | `errors.onec.batch_invalid_state` | Bu amal partiyaning joriy holatida mumkin emas ({status}) | Действие недоступно в текущем статусе пакета ({status}) | Sinf `api`, manba — server. Harakat: Sahifani yangilang |
| 1C integratsiyasi | `ONEC_ACTIVE_BATCH_EXISTS` | 409 | `errors.onec.active_batch_exists` | Bu bazada hozir yuborilayotgan partiya bor | В этой базе сейчас идёт выгрузка | Sinf `api`, manba — server. Harakat: Tugashini kuting |
| 1C integratsiyasi | `ONEC_PREVIEW_CHANGED` | 409 | `errors.onec.preview_changed` | Ma'lumot o'zgardi — ko'rinish yangilandi, qayta ko'rib tasdiqlang | Данные изменились — просмотр обновлён, проверьте и подтвердите снова | Sinf `api`, manba — server. Harakat: Qayta ko'rib tasdiqlash |
| 1C integratsiyasi | `ONEC_WARNINGS_NOT_ACKNOWLEDGED` | 422 | `errors.onec.warnings_not_acknowledged` | Ogohlantirishlarni ko'rib tasdiqlang | Подтвердите, что ознакомились с предупреждениями | Sinf `api`, manba — server. Harakat: Tasdiq modalida belgilash |
| 1C integratsiyasi | `ONEC_MAPPING_INCOMPLETE` | 409 | `errors.onec.mapping_incomplete` | {count} ta obyekt 1C bilan moslanmagan | {count} объектов не сопоставлены с 1С | Sinf `block`, manba — server. Harakat: [Moslash] yoki [1C da yaratish] |
| 1C integratsiyasi | `ONEC_MAPPING_IN_USE` | 409 | `errors.onec.mapping_in_use` | Bu bog'lanish yuborilayotgan partiyada ishlatilmoqda | Это сопоставление используется в выгружаемом пакете | Sinf `api`, manba — server. Harakat: Yuborish tugashini kuting |
| 1C integratsiyasi | `ONEC_CATALOG_CACHE_EMPTY` | 409 | `errors.onec.catalog_cache_empty` | 1C ma'lumotnomalari hali o'qilmagan | Справочники 1С ещё не прочитаны | Sinf `api`, manba — server. Harakat: «1C dan o'qish» tugmasi |
| 1C integratsiyasi | `ONEC_ALREADY_MAPPED` | 409 | `errors.onec.already_mapped` | Bu obyekt allaqachon 1C bilan moslangan | Объект уже сопоставлен с 1С | Sinf `api`, manba — server. Harakat: — |
| 1C integratsiyasi | `ONEC_REF_TYPE_MISMATCH` | 422 | `errors.onec.ref_type_mismatch` | Tanlangan 1C elementi turi mos emas | Тип выбранного элемента 1С не подходит | Sinf `api`, manba — server. Harakat: Boshqa elementni tanlang |
| 1C integratsiyasi | `ONEC_REF_CREATE_FORBIDDEN` | 403 | `errors.onec.ref_create_forbidden` | Bu turdagi elementni 1C'da yaratish taqiqlangan | Создание элементов этого вида в 1С запрещено | Sinf `api`, manba — server. Harakat: Qo'lda moslang (tashkilot, QQS, hisoblar — hech qachon yaratilmaydi) |
| 1C integratsiyasi | `ONEC_PAYMENT_ACCOUNT_NOT_TRANSIT` | — *(`warnings[]`/tekshiruv natijasi; xato emas)* | `warnings.onec.payment_account_not_transit` | «{payment}» to'lov turining 1C hisobi 5710 emas ({account}) | Счёт вида оплаты «{payment}» в 1С не 5710 ({account}) | Sinf `warn`, manba — server. Harakat: Buxgalter 1C'da hisobni tekshiradi (qaror #42) |
| 1C integratsiyasi | `ONEC_SHIFTS_OPEN` | 409 (block); — *(`warnings[]`, warn)* | `errors.onec.shifts_open` / `warnings.onec.shifts_open` | {count} ta smena hali yopilmagan | Не закрыто смен: {count} | Sinf `block/warn`, manba — server. Harakat: Smenalarni yoping (POS-07) |
| 1C integratsiyasi | `ONEC_DEVICES_NOT_SYNCED` | 409 | `errors.onec.devices_not_synced` | {count} ta kassa qurilmasi kun yopilgandan keyin sinxronlanmagan | {count} кассовых устройств не синхронизированы после закрытия дня | Sinf `block`, manba — server. Harakat: Qurilmani internetga ulang yoki istisno qiling (sabab bilan) |
| 1C integratsiyasi | `ONEC_PREVIOUS_DAY_NOT_DONE` | 409 | `errors.onec.previous_day_not_done` | Oldingi kunlar ({dates}) hali 1C ga tayyorlanmagan | Предыдущие дни ({dates}) ещё не подготовлены для 1С | Sinf `block`, manba — server. Harakat: Avval o'sha kunlarni tayyorlang |
| 1C integratsiyasi | `ONEC_QUEUED_BEHIND` | — *(`warnings[]`/tekshiruv natijasi; xato emas)* | `warnings.onec.queued_behind` | Oldingi kunlar yuborilgach navbat keladi ({dates}) | Будет выгружено после предыдущих дней ({dates}) | Sinf `warn`, manba — server. Harakat: Kutish |
| 1C integratsiyasi | `ONEC_DATE_PROHIBITED` | 409 | `errors.onec.date_prohibited` | 1C'da {date} gacha o'zgartirish taqiqlangan | В 1С запрещено изменение данных до {date} | Sinf `validation/block`, manba — server/agent. Harakat: Buxgalter sanani ochadi yoki «Tuzatuvchi hujjat» |
| 1C integratsiyasi | `ONEC_Z_REPORT_DIFF` | — *(`warnings[]`/tekshiruv natijasi; xato emas)* | `warnings.onec.z_report_diff` | {cash_register}: Z-hisobot va ОРП jami {diff} ga farq qiladi | {cash_register}: итоги Z-отчёта и ОРП отличаются на {diff} | Sinf `warn`, manba — server. Harakat: Ma'lumot uchun |
| 1C integratsiyasi | `ONEC_STOCK_SHORTAGE` | — *(`warnings[]`/tekshiruv natijasi; xato emas)* | `warnings.onec.stock_shortage` | 1C qoldig'i {count} ta tovar uchun yetmaydi | В 1С не хватает остатка по {count} товарам | Sinf `warn`, manba — server. Harakat: Kirimni kiriting yoki tuzatuvchi kirim |
| 1C integratsiyasi | `ONEC_TRANSFER_CROSS_BASE` | — *(`warnings[]`/tekshiruv natijasi; xato emas)* | `warnings.onec.transfer_cross_base` | Ko'chirish turli 1C bazalari orasida — yuborilmaydi | Перемещение между разными базами 1С — не выгружается | Sinf `warn`, manba — server. Harakat: Buxgalter qo'lda aks ettiradi |
| 1C integratsiyasi | `ONEC_LATE_DATA` | — *(`warnings[]`/tekshiruv natijasi; xato emas)* | `warnings.onec.late_data` | Yuborilgan kun uchun yangi ma'lumot keldi ({count} ta hujjat) | По выгруженному дню пришли новые данные ({count} док.) | Sinf `warn`, manba — server. Harakat: Yangi revisionni tasdiqlang |
| 1C integratsiyasi | `ONEC_UNPOST_REQUIRED` | — *(`warnings[]`/tekshiruv natijasi; xato emas)* | `warnings.onec.unpost_required` | {count} ta 1C hujjati o'tkazishdan chiqarilib, o'chirishga belgilanadi | {count} документов 1С будут распроведены и помечены на удаление | Sinf `warn`, manba — server. Harakat: Ko'rib tasdiqlang |
| 1C integratsiyasi | `ONEC_ORP_CASH_MISMATCH` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.orp_cash_mismatch` | Kassa ({cash_register}) naqd summasi to'lovlar bilan mos emas | Наличная часть ОРП ({cash_register}) не сходится с оплатами | Sinf `validation`, manba — server. Harakat: Qo'llab-quvvatlashga murojaat (ERP ma'lumoti xatosi) |
| 1C integratsiyasi | `ONEC_BUILD_INVARIANT_FAILED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.build_invariant_failed` | Kun jami ERP sotuvlari bilan mos kelmadi | Итоги дня не сходятся с продажами ERP | Sinf `validation`, manba — server. Harakat: Qo'llab-quvvatlashga murojaat |
| 1C integratsiyasi | `ONEC_TOTALS_MISMATCH` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.totals_mismatch` | 1C'dagi jami ERP'dan {diff} so'mga farq qiladi | Итог в 1С отличается от ERP на {diff} | Sinf `validation`, manba — server. Harakat: Farq jadvali; «Qayta solishtirish» / «Yangi revision» / «Qabul qilish» |
| 1C integratsiyasi | `ONEC_TASK_LEASE_LOST` | 409 | `errors.onec.task_lease_lost` | Vazifa bekor qilingan yoki boshqa urinishga o'tgan | Задача отменена или передана другой попытке | Sinf `api`, manba — server. Harakat: (agent ichki) |
| 1C integratsiyasi | `ONEC_TASK_REJECTED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.task_rejected` | Agent vazifani rad etdi ({reason}) | Агент отклонил задачу ({reason}) | Sinf `validation`, manba — agent. Harakat: Qo'llab-quvvatlash (xavfsizlik signali) |
| 1C integratsiyasi | `ONEC_COM_NOT_REGISTERED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.com_not_registered` | 1C ulagichi (COM) kompyuterda ro'yxatdan o'tmagan | Компонента 1С (COM) не зарегистрирована | Sinf `config`, manba — agent. Harakat: Agentda [Tuzatish] — bir martalik UAC tasdig'i (`regsvr32`); agent o'zi admin'siz ishlaydi |
| 1C integratsiyasi | `ONEC_BITNESS_MISMATCH` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.bitness_mismatch` | 1C platformasi bitligi (32/64) mos emas | Разрядность платформы 1С (32/64) не подходит | Sinf `config`, manba — agent. Harakat: Mos platformani o'rnating |
| 1C integratsiyasi | `ONEC_PLATFORM_VERSION_MISMATCH` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.platform_version_mismatch` | Kompyuterdagi 1C versiyasi server versiyasidan farq qiladi | Версия 1С на компьютере отличается от версии сервера | Sinf `config`, manba — agent. Harakat: Kompyuterdagi 1C platformasini yangilang |
| 1C integratsiyasi | `ONEC_AUTH_FAILED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.auth_failed` | 1C foydalanuvchisi yoki paroli noto'g'ri | Неверный пользователь или пароль 1С | Sinf `config`, manba — agent. Harakat: Agent oynasida bazani tahrirlang (parol faqat kompyuterda) |
| 1C integratsiyasi | `ONEC_BASE_UNAVAILABLE` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.base_unavailable` | 1C bazasi topilmadi yoki server javob bermayapti | База 1С не найдена или сервер не отвечает | Sinf `transient`, manba — agent. Harakat: Tarmoq papkasi/serverni tekshiring (3 marta — `error`) |
| 1C integratsiyasi | `ONEC_BASE_LOCKED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.base_locked` | 1C bazasida seanslar bloklangan («Блокировка работы пользователей») | В базе 1С установлена блокировка сеансов | Sinf `transient`, manba — agent. Harakat: Blokirovka olingach avtomatik qayta uriniladi (`UC=` ishlatilmaydi) |
| 1C integratsiyasi | `ONEC_BASE_EXCLUSIVE` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.base_exclusive` | 1C bazasi monopol rejimda (Konfigurator yangilamoqda yoki fayl band) | База 1С в монопольном режиме (обновление в Конфигураторе или файл занят) | Sinf `transient`, manba — agent. Harakat: Konfiguratorni yoping — avtomatik qayta uriniladi |
| 1C integratsiyasi | `ONEC_LICENSE_UNAVAILABLE` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.license_unavailable` | 1C'da bo'sh litsenziya yo'q | Нет свободной лицензии 1С | Sinf `transient`, manba — agent. Harakat: Bitta 1C oynasini yoping yoki keyinroq — avtomatik qayta uriniladi |
| 1C integratsiyasi | `ONEC_LOCK_CONFLICT` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.lock_conflict` | 1C'da ma'lumot band (boshqa foydalanuvchi o'tkazmoqda) | Конфликт блокировок в 1С | Sinf `transient`, manba — agent. Harakat: Avtomatik qayta uriniladi |
| 1C integratsiyasi | `ONEC_OBJECT_LOCKED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.object_locked` | Hujjat 1C'da kimdadir ochiq turibdi | Документ открыт у другого пользователя 1С | Sinf `transient`, manba — agent. Harakat: Hujjat oynasini yoping — avtomatik qayta uriniladi |
| 1C integratsiyasi | `ONEC_ACCESS_DENIED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.access_denied` | 1C foydalanuvchisida bu amal uchun huquq yo'q | У пользователя 1С нет прав на это действие | Sinf `config`, manba — agent. Harakat: 1C administratori «ERP integratsiya» foydalanuvchisiga rol qo'shsin |
| 1C integratsiyasi | `ONEC_NO_RIGHTS` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.no_rights` | 1C foydalanuvchisida tashqi ulanish (COM) huquqi yo'q | У пользователя 1С нет права внешнего соединения | Sinf `config`, manba — agent. Harakat: 1C administratori «Запуск внешнего соединения» rolini bersin |
| 1C integratsiyasi | `ONEC_NEGATIVE_STOCK` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.negative_stock` | 1C'da tovar qoldig'i yetarli emas: {onec_message} | Недостаточно остатка в 1С: {onec_message} | Sinf `validation`, manba — agent. Harakat: Kirim yuborilganini tekshiring yoki tuzatuvchi kirim |
| 1C integratsiyasi | `ONEC_FILL_CHECK_FAILED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.fill_check_failed` | 1C majburiy maydon to'ldirilmagan deydi: {onec_message} | 1С сообщает о незаполненном обязательном поле: {onec_message} | Sinf `validation`, manba — agent. Harakat: Moslashtirishni tekshiring; qo'llab-quvvatlash |
| 1C integratsiyasi | `ONEC_POST_FAILED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.post_failed` | 1C hujjatni o'tkazmadi: {onec_message} | 1С не провела документ: {onec_message} | Sinf `validation`, manba — agent. Harakat: Xabarni o'qing; tuzatib «Qayta yuborish» |
| 1C integratsiyasi | `ONEC_WRITE_FAILED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.write_failed` | 1C hujjatni yozmadi: {onec_message} | 1С не записала документ: {onec_message} | Sinf `validation`, manba — agent. Harakat: Xabarni o'qing; qo'llab-quvvatlash |
| 1C integratsiyasi | `ONEC_REF_NOT_FOUND` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.ref_not_found` | 1C'da bog'langan element topilmadi ({presentation}) — o'chirilgan bo'lishi mumkin | В 1С не найден сопоставленный элемент ({presentation}) | Sinf `validation`, manba — agent/server. Harakat: Qayta moslang |
| 1C integratsiyasi | `ONEC_REF_MARKED_FOR_DELETION` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.ref_marked_for_deletion` | 1C elementi o'chirishga belgilangan ({presentation}) | Элемент 1С помечен на удаление ({presentation}) | Sinf `validation`, manba — agent/server. Harakat: 1C'da belgini oling yoki boshqa element tanlang |
| 1C integratsiyasi | `ONEC_REF_AMBIGUOUS` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.ref_ambiguous` | 1C'da bir nechta mos element topildi — aniq bittasi kerak | В 1С найдено несколько подходящих элементов — нужен ровно один | Sinf `validation`, manba — agent/server. Harakat: Qo'lda tanlang |
| 1C integratsiyasi | `ONEC_FIELD_VERIFY_FAILED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.field_verify_failed` | 1C maydon qiymatini boshqacha saqladi ({field}) | 1С сохранила значение поля иначе ({field}) | Sinf `validation`, manba — agent. Harakat: Qo'llab-quvvatlash (profil/aniqlik) |
| 1C integratsiyasi | `ONEC_OBJECT_MARKED_DELETED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.object_marked_deleted` | Bu hujjat 1C'da o'chirishga belgilangan | Этот документ в 1С помечен на удаление | Sinf `validation`, manba — agent. Harakat: Buxgalter: belgini olish yoki «ERP bilan almashtirish» |
| 1C integratsiyasi | `ONEC_EXISTS_DIFFERENT` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.exists_different` | 1C'da bu hujjat boshqa tarkib bilan bor | Документ уже есть в 1С с другим содержимым | Sinf `validation`, manba — agent. Harakat: Yangi revision |
| 1C integratsiyasi | `ONEC_DUPLICATE_REF` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.duplicate_ref` | 1C'da shu GUID bilan obyekt allaqachon bor — tekshirib yangilanadi (takror bo'lmaydi) | В 1С уже есть объект с этим GUID — будет прочитан и обновлён без дублей | Sinf `unknown`, manba — agent. Harakat: Hech narsa (avtomatik: keyingi urinish GUID bo'yicha o'qib yangilaydi) |
| 1C integratsiyasi | `ONEC_CHANGED_IN_1C` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.changed_in_1c` | Hujjat 1C'da qo'lda o'zgartirilgan — ustiga yozilmadi | Документ изменён в 1С вручную — не перезаписан | Sinf `validation`, manba — agent. Harakat: «ERP bilan almashtirish» yoki «Tuzatuvchi hujjat» (Buxgalter) |
| 1C integratsiyasi | `ONEC_QUERY_FAILED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.query_failed` | 1C'dan o'qish so'rovi bajarilmadi | Запрос чтения из 1С не выполнен | Sinf `validation`, manba — agent. Harakat: Qo'llab-quvvatlash |
| 1C integratsiyasi | `ONEC_CONNECTION_LOST` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.connection_lost` | 1C bilan aloqa uzildi | Связь с 1С прервана | Sinf `transient`, manba — agent. Harakat: Avtomatik qayta uriniladi |
| 1C integratsiyasi | `ONEC_TIMEOUT` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.timeout` | 1C javobi kutish vaqtidan oshdi | Превышено время ожидания ответа 1С | Sinf `transient`, manba — agent. Harakat: Avtomatik qayta uriniladi |
| 1C integratsiyasi | `ONEC_WORKER_CRASHED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.worker_crashed` | 1C bilan ishlovchi jarayon kutilmaganda to'xtadi | Процесс работы с 1С неожиданно завершился | Sinf `transient`, manba — agent. Harakat: Avtomatik qayta uriniladi |
| 1C integratsiyasi | `ONEC_UNKNOWN_OUTCOME` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.unknown_outcome` | Yozildimi-yo'qmi noma'lum — tekshirib qayta yoziladi (takror bo'lmaydi) | Неизвестно, записано ли — будет проверено и записано без дублей | Sinf `unknown`, manba — agent/server. Harakat: Hech narsa (avtomatik) |
| 1C integratsiyasi | `ONEC_DPAPI_FAILED` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.dpapi_failed` | Kompyuterdagi saqlangan parol/kalit ochilmadi | Не удалось расшифровать сохранённый пароль/ключ | Sinf `config`, manba — agent. Harakat: 1C parolini qayta kiriting yoki kompyuterni qayta ulang |
| 1C integratsiyasi | `ONEC_UNKNOWN` | — *(item/vazifa/tekshiruv natijasi)* | `errors.onec.unknown` | 1C xatosi tasniflanmadi: {onec_text} | Ошибка 1С не классифицирована: {onec_text} | Sinf `validation`, manba — agent/server. Harakat: Xom matnni o'qing; qo'llab-quvvatlash (profil regex jadvaliga qo'shiladi) |


### 15.1 Kodga bog'lanmagan `message_key`'lar (maydon va klient)

Quyidagi kalitlar xato **kodi emas** — katalogdagi kod bilan birga `details[].message_key` sifatida keladi yoki faqat klientda (POS/veb, serverga so'rovsiz) ishlatiladi; matnlari `08-dizayn-tizimi.md` §11 da.

| message_key | Qayerda | Bog'liq kod / manba |
|---|---|---|
| `validation.required`, `validation.max_length`, `validation.phone_format` | `details[]` (har maydon), zod `errorMap` | `VALIDATION_ERROR` |
| `validation.variance_note_required` | `details[].field="variance_note"` — smena yopishda farq bor, izoh yo'q (`18-api-kassa.md` §3) | `VALIDATION_ERROR` |
| `validation.card_manual_details_forbidden` | `details[].field="payments[i].card_mask"`/`"rrn"`/`"card_type"`/`"card_type_source"`/`"approval_code"`/`"card_scheme"`/`"card_result"`/`"terminal_ref"` (shuningdek `refund_card.*`, `debt_payment` ildizi) — `card_entry_mode="manual"` (terminalsiz karta, rekvizitsiz) da karta rekviziti berilgan; shuningdek `POST /card-terminal-transactions`da `result.resolved_by="manager"` bilan `rrn`/`card_mask`/`approval_code`/`card_type` berilgan (qaror #64, #71) | `VALIDATION_ERROR` |
| `validation.card_entry_mode_required` | `details[].field="payments[i].card_entry_mode"` — `method="card"` da kiritish usuli yo'q (qaror #71) | `VALIDATION_ERROR` |
| `validation.card_result_required` | `details[].field="payments[i].card_result"` — `card_entry_mode="integrated"` da terminal natijasi (`attempt_id`, `rrn`, `card_mask`) yo'q, `status` `approved` emas yoki `resolved_by="manager"` (menejer yopgan urinish to'lov qatoriga `manual`, `manual_reason="unknown_result"` sifatida keladi) (qaror #71) | `VALIDATION_ERROR` |
| `validation.card_manual_reason_required` | `details[].field="payments[i].manual_reason"` — `card_entry_mode="manual"` da sabab yo'q; qiymatlar: `standalone_terminal` (faol terminal bog'lanmagan kassa), `terminal_offline`/`terminal_error`/`unknown_result` (faol terminal bog'langan kassa) (qaror #71) | `VALIDATION_ERROR` |
| `card.terminal_place_card` | POS-03 — "Kartani terminalga qo'ying" kutish ekrani (hisoblagich bilan) | klient (`21-integratsiyalar.md` §9.4) |
| `validation.bank_settlement_exceeds_in_transit` | `details[].field="gross_amount"` — summa yo'ldagi pul (5710) qoldig'idan katta (`20-api-moliya-admin.md` §55c, §55e) | `VALIDATION_ERROR` |
| `validation.exceeds_credit_limit` | `details[].field="payments[i].amount"` | `DEBT_LIMIT_EXCEEDED` |
| `errors.debt_payment_exceeds_balance` | kod darajasidagi `message_key` (biznes qoida; faqat online/REST qarz to'lovi) | `VALIDATION_ERROR` (qaror #45) |
| `fiscal.offline_block_soon` | POS modal, 46 soatdan keyin har chekdan oldin (qaror #43) | klient (`16-offline-sync.md` §6) |
| `errors.device_clock_invalid` | POS — qurilma soati orqaga surilgan | klient (`16-offline-sync.md` §8) |
| `errors.license_expired` | POS — offline litsenziya muddati tugagan | klient (`14-autentifikatsiya-oauth2.md` §17) |
| `errors.product_not_found` | POS qidiruv/skaner — mahsulot topilmadi | klient (lokal katalog); serverda `NOT_FOUND`/`BARCODE_NOT_IN_CATALOG` |
| `errors.return_requires_online` | POS — asl chek lokal keshda (90 kun) topilmasa yoki markirovkali tovar bo'lsa qaytarish offline'da ochilmaydi (qaror #23) | klient; markirovkali tovar uchun serverda `MARKING_RETURN_REQUIRES_ONLINE` |

---

## Ochiq savollar

Tashqi javob kutilayotgan band yo'q.

## Manbalar

- `spec/kod-uchun/23-backend-arxitekturasi.md` §3 — API konventsiyalari (asosiy manba, resurs nomlash bandida ataylab chetga chiqildi).
- `spec/kod-uchun/11-malumotlar-modeli.md` — jadval/maydon nomlari, UUIDv7, pul/miqdor formatlari.
- `spec/kod-uchun/15-xavfsizlik-va-audit.md` §2.1–2.3 — ruxsat kodlari, limitlar, PIN oqimi.
- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` — auth endpoint'lari (takrorlanmadi, faqat havola).
- `spec/kod-uchun/16-offline-sync.md` — sync endpoint'lari (takrorlanmadi, faqat havola).
- `spec/kod-uchun/21-integratsiyalar.md` §9 — Click/Payme webhook protokoli.
- `spec/kod-uchun/22-ai-qatlami.md` — AI xato/limit mantiqi.
- `spec/tarix/tekshiruv/qabul-6-api-db.md`, `spec/tarix/tekshiruv/qabul-7-ekran-api.md` — qabul tekshiruvi hujjatlari (resurs nomlash, xato konverti va xato katalogi qarorlarining manbasi).

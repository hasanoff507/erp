# Backend arxitekturasi

**Maqsad:** Backend repozitoriy tuzilishi, posting naqshi, API konventsiyalari, navbat kutubxonasi, kutubxona tanlovlari, test strategiyasi va deploy modelini belgilash.
**Kim uchun:** Backend ishlab chiquvchi, arxitektor.
**Bog'liq fayllar:** `10-umumiy-arxitektura.md`, `11-malumotlar-modeli.md`, `24-frontend-arxitekturasi.md`, `03-modullar-talablari.md`, `14-autentifikatsiya-oauth2.md`.
**Holat:** joriy, 2026-10-15.

*Namuna loyiha (tuzilma va konventsiya uchun, kod emas): `E:/Project/universal_ai_platform/src/backend`.*

## Asosiy xulosalar

1. **Modulli monolit**: `backend/app/modules/<modul>/` — 19 modul papkasi (18 mahsulot moduliga + kesishuvchi `integrations`/`sync`/`ai` ga mos), har biri bir xil ichki qatlam: `domain/` → `application/` → `infrastructure/` → `api/`. Umumiy infratuzilma — `app/core` (DB sessiya + tenant kontekst, auth, huquq dependency, idempotentlik, xatolar, sozlamalar, logging) va `app/workers` (navbat ishlari, cron).
2. **"Posting service" naqshi** — har bir hujjat turi uchun bitta xizmat, bitta DB tranzaksiyada hujjat holatini **va** barcha registrlarni (`stock_moves`/`stock_lots`, `debt_moves`, `cash_moves`, `ledger_entries`, `vat_moves`) birga yozadi; bekor qilish — faqat teskari yozuv, `UPDATE`/`DELETE` yo'q.
3. **Navbat kutubxonasi — `SAQ`** (4-bo'lim): asyncio, Redis broker (stack'da bor), ichki `CronJob`, o'rnatilgan monitoring UI. `arq` 2025-10 dan beri faqat texnik xizmat rejimida (python-arq/arq#510) — yangi loyiha uchun tanlanmaydi.
4. **Tenant izolyatsiyasi kod darajasida ikki marta**: (a) ilova qatlami — `TenantMixin` modellariga SQLAlchemy `with_loader_criteria` orqali global `tenant_id` filtri; (b) PostgreSQL RLS (`set_config('app.tenant_id', …, true)` + siyosat, `15-xavfsizlik-va-audit.md`) — (b) (a) buzilsa ham himoya qiladi va aksincha (09 §6 RLS-o'chirilgan testi shu (a)ni tekshiradi).
5. **Kutubxona birinchi, qo'lda kod oxirgi**: pagination — `fastapi-pagination`, filtrlash — `fastapi-filter`, retry — `tenacity`, UUIDv7 — `uuid-utils`, muddat arifmetikasi (5 kalendar kun, 48/72 soat, qarz eskirish guruhlari) — `pendulum`, Excel — `openpyxl`, shtrix-kod/yorliq — `python-barcode` + `zxing-cpp` (Ghostscript/AGPL'siz). To'liq jadval 5-bo'limda.
6. **AI — port naqshi** (`AiProvider`, README qarori): `fake` (test) | `cli` (lokal dev, Claude Code CLI) | `api` (staging/prod, `anthropic` SDK) — namuna loyihadagi `ClaudePort`/`CliClaudeClient`/`FakeClaudeClient` naqshining aynan takrorlanishi, faqat `cli` o'rniga prodda `api`.
7. **Namuna loyihadan nusxa olinadi**: qatlamli papka tuzilmasi, `pydantic-settings` + `lru_cache get_settings()` + prod-da xavfsizlik guard (`model_validator` — auth yoqilmagan/standart sir/sqlite bo'lsa ishga tushmaydi), composition-root'dagi `_build_*` factory funksiyalar, Alembic'ning asinxron `env.py`'si, `ReadinessProbe`'ning "gating vs reported" bo'linishi, ko'p bosqichli Dockerfile (non-root user, `HEALTHCHECK`).
8. **Namuna loyihadan farqlanadi**: u — har mijoz uchun alohida stack (bitta tenant); bu loyiha — **bitta umumiy stack, ko'p tenant, RLS bilan**: `api`/`worker` gorizontal ko'payadi, `scheduler` yagona nusxa bo'lishi kerak (Postgres advisory lock bilan) (adapterlar: OFD/e-faktura/Asl belgisi/Click-Payme adapterlari).
9. API — `/api/v1`, URL yo'li kebab-case ko'plik, JSON/query/enum/`operation_id` — snake_case (3-bo'lim, `01-qarorlar.md` #24); xato formati `{"error": {code, message_key, params, details[], request_id}}` (frontenddagi zod/i18next bilan bir xil shakl, `details` har doim massiv), `Idempotency-Key` Redis tezkor qulf + Postgres doimiy jurnal bilan, optimistik qulflash `version` maydoni orqali (faqat ma'lumotnomalarda — hujjatlarda yo'q).
10. Test strategiyasi — bitlik testlar provodka qoidalari uchun sonli misollar bilan, `testcontainers` orqali haqiqiy Postgres'da integratsiya va RLS izolyatsiya testlari, `schemathesis` OpenAPI'dan kontrakt testlari.
11. **Autentifikatsiya — o'z OAuth 2.0 AS+RS implementatsiyasi** (`app/modules/auth/`): protokol skeleti **Authlib** (RFC 6749/7636/7009/7662/8414/9068), JWT/JWKS — **joserfc**, parol/PIN — **argon2-cffi (argon2id)**; barcha storage/rotatsiya/obuna-tekshiruv mantiqi bizning kod. To'liq dizayn — `14-autentifikatsiya-oauth2.md`.

---

## 1. Repozitoriy tuzilishi

```
backend/
├── app/
│   ├── core/                        # kesishuvchi infratuzilma (hech qaysi modulga tegishli emas)
│   │   ├── config.py                 # Settings (pydantic-settings), get_settings()
│   │   ├── db/
│   │   │   ├── session.py            # async engine, AsyncSession, tenant_transaction() + set_config('app.tenant_id', …, true)
│   │   │   └── base.py               # DeclarativeBase, umumiy mixin'lar (TenantMixin, TimestampMixin)
│   │   ├── auth/                     # BFF cookie/CSRF, OAuth claims dependency (require_subscription_ok, current_user), JWKS keshi — amalga oshirish `modules/auth/`da
│   │   ├── permissions.py            # require_permission("sales.create") dependency
│   │   ├── idempotency.py            # Idempotency-Key middleware + repo
│   │   ├── errors.py                 # AppError, exception handler'lar, {code,message_key,details}
│   │   ├── pagination.py             # fastapi-pagination sozlamasi (cursor, UUIDv7 bo'yicha)
│   │   ├── logging.py                # structlog sozlamasi, so'rov ID, tenant ID context
│   │   └── telemetry.py              # OpenTelemetry, prometheus-client, sentry-sdk ulash
│   ├── modules/
│   │   ├── catalog/                  # M09 (tovar, kategoriya, birlik, shtrix-kod)
│   │   ├── pricing/                  # M09 narx tarixi, M03 chegirma/aksiya qoidalari
│   │   ├── sales/                    # M01 kassa, smena, chek, fiskal, markirovka tekshiruvi
│   │   ├── returns/                  # M02
│   │   ├── inventory/                # M04 qoldiq/partiya, M05 inventarizatsiya, M06 ko'chirish
│   │   ├── purchasing/               # M07 xaridnoma, kirim, e-faktura, yetkazib beruvchi
│   │   ├── debts/                    # M08 mijoz va yetkazib beruvchi qarz daftari
│   │   ├── vat/                      # M10 QQS hisob-kitobi, davlat hisoboti solishtirish
│   │   ├── accounting/               # M11 buxgalteriya provodkasi, oy yopish
│   │   ├── reports/                  # M12 hisobot va dashboard query'lari (faqat o'qish)
│   │   ├── auth/                     # OAuth 2.0 AS+RS: /oauth/*, /auth/*, /admin/users, Authlib integratsiyasi, token/sessiya/litsenziya jadvallari (`14-autentifikatsiya-oauth2.md`)
│   │   ├── access/                   # M13 rol/ruxsat katalogi, role_permissions (foydalanuvchi CRUD'i endi `auth/`da)
│   │   ├── branches/                 # M14 filial, ombor, kassa apparati, qurilma ro'yxati
│   │   ├── expenses/                 # M15 xarajat, toifa, takrorlanuvchi xarajat
│   │   ├── cash/                     # M16 kassa naqd pul harakati, smena sanash
│   │   ├── billing/                  # M17 tarif, obuna, to'lov (Click/Payme), platforma admin
│   │   ├── notifications/            # M18 bildirishnoma, Telegram bot (aiogram), SMS
│   │   ├── integrations/             # OFD, e-faktura, e-TTN, Asl belgisi, E-IMZO — har biri adapter
│   │   ├── ai/                       # AiProvider porti, AI-xx funksiyalar, ai_requests/feedback
│   │   └── sync/                     # offline outbox qabul qilish, client_event_id dedupe, qurilma holati
│   └── workers/
│       ├── jobs/                      # SAQ task funksiyalari (bitta modulga tegishli bo'lsa ham shu yerda
│       │                               # ro'yxatga olinadi — modul papkasidagi `tasks.py` dan import qilib)
│       ├── cron.py                    # SAQ CronJob ro'yxati (davlat hisoboti eslatmasi, qarz eslatmasi, recost, kam qoldiq, yaroqlilik muddati, obuna eslatmasi, kunlik Telegram hisobot)
│       └── worker_settings.py         # SAQ worker sozlamalari (navbatlar, concurrency, Sentry/OTel init)
├── alembic/
│   ├── env.py                         # asinxron, namuna loyihadagidek
│   └── versions/
├── tests/
├── scripts/                           # seed.py (typer CLI), wait_for_db.py va h.k.
├── Dockerfile
├── pyproject.toml / uv.lock
└── alembic.ini
```

**Har bir modul ichida** (masalan `modules/sales/`):

```
sales/
├── domain/            # entity/value object, biznes qoida (pure Python, SQLAlchemy'siz)
│   ├── entities.py     # Sale, SaleLine, Shift — dataclass/Pydantic, DB'dan mustaqil
│   └── rules.py        # masalan "aralash to'lov summasi chek summasiga teng bo'lishi kerak"
├── application/        # use-case/service — domain + portlarni chaqiradi, tranzaksiya chegarasi shu yerda
│   ├── posting.py       # SalePostingService (2-bo'lim)
│   ├── services.py      # SaleService (CRUD, qidiruv — posting bo'lmagan amallar)
│   └── ports.py         # modul kutgan interfeyslar (masalan FiscalPort — integrations moduli amalga oshiradi)
├── infrastructure/
│   ├── models.py         # SQLAlchemy ORM model (jadval ta'rifi)
│   ├── repositories.py   # SaleRepository — faqat SQLAlchemy so'rovlari
│   └── tasks.py          # SAQ job'lar (masalan "ofd_send") — workers/jobs ro'yxatiga shu yerdan import qilinadi
└── api/
    ├── router.py          # APIRouter(prefix="/sales", tags=["sales"])
    ├── schemas.py          # Pydantic v2 request/response (OpenAPI → orval manbasi)
    └── deps.py             # modulga xos dependency (masalan faol smenani talab qilish)
```

**Qatlamlar orasidagi qoida** (namunadagi `aios/domain|application|infrastructure|interface` bo'linishidan olingan, FSD'dagi "faqat pastga import" qoidasiga o'xshash): `api → application → domain`; `infrastructure` faqat `domain`dagi portlarni amalga oshiradi, `application` uni interfeys orqali ko'radi (dependency inversion — DI composition root `app/main.py` + modul-ichidagi kichik `wiring.py` bog'laydi). Modullar bir-birining `infrastructure`/`api` qatlamini **import qilmaydi** — faqat boshqa modulning `application`/`domain` portini (masalan `sales` moduli `inventory.application.ports.StockPort`ni chaqiradi, `inventory.infrastructure`ni emas). Bu modulli monolitni keyin mikroservisga ajratishni osonlashtiradi (`10-umumiy-arxitektura.md`, 1-xulosa).

### `app/core/db` — tenant kontekst

```python
# app/core/db/session.py (konventsiya)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, autobegin=False)

@asynccontextmanager
async def tenant_transaction(session: AsyncSession, tenant_id: UUID):
    async with session.begin():
        await session.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})
        yield session

async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
```

Tranzaksiya faqat `tenant_transaction()` orqali ochiladi. `autobegin=False` sababli undan tashqarida `execute` xato beradi, shuning uchun tenant kontekstisiz so'rov jismonan mumkin emas. `SET LOCAL ... = :param` ishlatilmaydi, chunki PostgreSQL `SET` parametr qabul qilmaydi; o'rniga `set_config(..., true)` ishlatiladi (tranzaksiya-lokal). Posting xizmati, `/sync/push` (har voqea uchun alohida `tenant_transaction`) va worker job'lari ham aynan shu helper'dan foydalanadi. Ichki savepoint kerak bo'lsa — `session.begin_nested()`.

`current_tenant_id` — auth dependency sessiya cookie'dan (yoki ichki admin uchun JWT'dan) tenant ID'ni oladi; **hech qachon so'rov tanasi/query parametridan emas** (frontend arxitekturasi, 3-bo'lim: `X-Tenant-Id` header yo'q, aynan shu sababdan). `X-Branch-Id` header bo'lsa, `current_branch_id` dependency uni tasdiqlaydi (foydalanuvchi shu filialga `membership`i bormi) va `app/core/permissions.py` orqali filial-darajasidagi ruxsatlarga uzatiladi.

---

## 2. "Posting service" naqshi

Har bir hujjat turi (`sales`, `returns`, `goods_receipts`, `transfers`, `stock_counts`, `write_offs`, `debt_payments`, `expenses`, `cash_movements`, …) uchun **bitta** `*PostingService`, umumiy protokolga mos:

```python
class DocumentPostingService(Protocol):
    async def post(self, doc_id: UUID) -> PostingResult: ...
    async def reverse(self, doc_id: UUID, reason: str, actor_id: UUID) -> PostingResult: ...
```

### 2.1. Bitta tranzaksiya — nima yoziladi

`post()` ichida **bitta** `async with tenant_transaction(session, tenant_id):` bloki:

1. Hujjat qatorlarini tekshiradi (biznes qoida — `domain/rules.py`): limit, manfiy qoldiq siyosati, davr yopilmaganligi (`period_closings`, 2.4-band).
2. **Qulflash** — serializatsiya nuqtasi `stock_balances (warehouse_id, product_id)` qatori: avval `INSERT … ON CONFLICT DO NOTHING`, so'ng `SELECT … FOR UPDATE`. Shu qulf ostida `stock_lots` qulfsiz o'qiladi va o'zgartiriladi; partiyaga tegadigan **barcha** yo'llar (sotuv, qaytarish, kirim, ko'chirish, inventarizatsiya, hisobdan chiqarish, recost) aynan shu qulfni oladi. Kerak bo'lsa `debt_balances (counterparty_id, direction)` ham `FOR UPDATE`. Deadlock'ga qarshi tartib: avval `stock_balances` — `(warehouse_id, product_id)` o'sish tartibida, so'ng `debt_balances` — `counterparty_id` bo'yicha. `cash_moves` qulflanmaydi (tekshiriladigan invariant yo'q).
3. Barcha registrlarga append-only yozadi: `stock_moves` (+ FIFO/AVECO bo'yicha `stock_lots.qty_left`ni kamaytirish), `debt_moves`, `cash_moves`, `ledger_entries`, `vat_moves` — qaysi biri hujjat turiga tegishli bo'lsa.
4. Hujjat holatini `posted`ga o'tkazadi, `posted_at`ni yozadi (fiskal holat — alohida `fiscal_receipts.status=pending`, `11-malumotlar-modeli.md` 8-bo'lim).
5. Tranzaksiya commit bo'lgach (`after_commit` hook), tashqi integratsiya ishlarini **navbatga** qo'yadi (`outbox_jobs` qatori + `JobQueue.enqueue(...)`, SAQ ortida, 4-bo'lim) — OFD'ga yuborish, e-faktura, Telegram xabar. **Hech qachon tashqi tizim tranzaksiya ichida chaqirilmaydi** (`10-umumiy-arxitektura.md`, 7-xulosa: API tashqi tizimni kutib turmaydi).

Bitta tranzaksiyada yozilishi kerakligi sababi — `11-malumotlar-modeli.md` 4-xulosasi: hujjat holati va registrlar birga yoziladi yoki birga bekor bo'ladi (DB darajasidagi atomiklik, ilova darajasida "deyarli atomik" emas).

### 2.2. Shartli sonli misol (FIFO, tannarx)

*Quyidagi raqamlar faqat posting mantiqini ko'rsatish uchun shartli misol — tadqiqot/talab hujjatidan olingan raqam emas.*

Ombordagi "Shakar" partiyalari (FIFO; `unit_cost` — QQS'siz, 2.6-provodkaga mos):

| Partiya | `qty_left` | `unit_cost` |
|---|---|---|
| Lot-1 (eski) | 5 kg | 9 500 so'm |
| Lot-2 | 8 kg | 9 800 so'm |

Sotuv: 10 kg × 12 000 so'm/kg, **narx QQS bilan** (`13-provodka-qoidalari.md` 2-bo'lim), QQS 12%, naqd.

- Chek summasi = 120 000,00; QQS = 120 000 × 12/112 = 12 857,142857… → **12 857,14**; sof daromad = **107 142,86**.
- FIFO: Lot-1'dan 5 kg (47 500) + Lot-2'dan 5 kg (49 000) → `lot_allocations = [{lot: 1, qty: 5, cost: 47500}, {lot: 2, qty: 5, cost: 49000}]`, COGS = **96 500**; Lot-2'da 3 kg qoladi. Yalpi foyda = 107 142,86 − 96 500 = 10 642,86.

Shu bitta postingda yoziladigan qatorlar:

- `stock_moves`: −10 kg, cost_amount = −96 500,00.
- `stock_lots`: Lot-1.qty_left = 0, Lot-2.qty_left = 3.
- `ledger_entries`: Dt 9120 / Kt 2910 = 96 500,00.
- `ledger_entries`: Dt 5010 / Kt 9020 = 107 142,86.
- `ledger_entries`: Dt 5010 / Kt 6410 = 12 857,14 (Dt 5010 jami = 120 000,00).
- `vat_moves`: output, base_amount = 107 142,86, vat_amount = 12 857,14.
- `cash_moves`: +120 000,00 (naqd). Nasiya bo'lsa: `debt_moves` +120 000,00, Dt 5010 o'rniga Dt 4010 — summalar bir xil.

Bitlik test shu jadvaldagi kirish/chiqish qiymatlarini aynan tekshiradi (5-bo'lim).

### 2.3. Bekor qilish (reversal)

`reverse()` yangi hujjat yaratmaydi — original hujjat `cancelled` bo'ladi (`cancelled_at`, `cancelled_by`, `cancel_reason`) va **har bir yozilgan registr qatoriga teskari belgili nusxa** qo'shiladi (`doc_type`/`doc_id` — original hujjat, `reversal_of_id` — teskari qilinayotgan asl registr qatori; hech qachon `UPDATE`). `stock_lots.qty_left` `lot_allocations` bo'yicha teskari tartibda qaytariladi (2.1 qulfi ostida).

### 2.4. Recost ishlari va davr yopish

- **Recost** (`recost_jobs`, `11-malumotlar-modeli.md` 10-bo'lim): o'tgan sanali hujjat (kech sinxron, kech kirim) kelganda navbatga qo'yiladi (SAQ job `recost_product`); job shu sanadan keyingi barcha chiqim postinglarini **FIFO/AVECO bo'yicha qayta hisoblaydi** va `ledger_entries`/`stock_moves`ga **tuzatish yozuvi** qo'shadi (asl yozuvni o'zgartirmaydi — append-only tamoyili shu yerda ham amal qiladi). `period_closings`ga tegadigan sana bo'lsa, job **rad etiladi** va `notifications` moduliga ogohlantirish yuboradi (`11-malumotlar-modeli.md`, 7-bo'lim). Job `queued → running → done/failed`; davr yopiq bo'lsa `rejected_period_closed`. Job 2.1 dagi `stock_balances` qulfini oladi.
- **Davr yopish** (`accounting` moduli, `period_closings` jadvali): yopishdan oldin tekshiradi — davr ichida `fiscal_receipts.status IN ('pending','sent','failed')` yo'qligini, barcha `recost_jobs` tugaganini; yopilgandan keyin shu sanagacha bo'lgan **yangi posting rad etiladi** (`PERIOD_CLOSED` xato kodi, 3-bo'lim).

```mermaid
sequenceDiagram
    participant C as Veb-kassa
    participant API as FastAPI /sync/push
    participant PS as SalePostingService
    participant DB as PostgreSQL
    participant Q as Redis (SAQ)
    participant W as Worker

    C->>API: POST /sync/push (voqea: sale.created)
    API->>DB: sync_receipts: client_event_id oldin bormi?
    API->>PS: post(sale)
    PS->>DB: BEGIN tenant_transaction; FOR UPDATE qatorlar
    PS->>DB: stock_moves + stock_lots + debt/cash_moves + ledger_entries + vat_moves + status=posted
    PS->>DB: COMMIT
    PS->>Q: enqueue "ofd_send", "einvoice_send" (agar kerak bo'lsa)
    API-->>C: results:[{status: accepted, server:{id, number}}] (fiscal_receipts.status=pending)
    Q->>W: job navbatdan olinadi
    W->>W: OFD'ga yuborish (httpx + tenacity retry)
    W->>DB: fiscal_receipts.status = fiscalized
    Note over C: fiskal belgi/QR keyingi GET /sync/pull'da
```

POS uchun alohida `POST /sales` yo'q — yagona yo'l `/sync/push`.

---

## 3. API konventsiyalari

| Jihat | Qaror |
|---|---|
| Versiyalash | `/api/v1/...`; keyingi breaking o'zgarish — `/api/v2`, eski versiya e'lon qilingan muddat davomida saqlanadi |
| Resurs nomlash | URL yo'li — **kebab-case, ko'plik ot**, `11-malumotlar-modeli.md` jadval nomidan `_` → `-` (`goods_receipts` → `/goods-receipts`, `debt_writeoffs` → `/debt-writeoffs`); hujjat turi bo'yicha alohida resurs (`/returns`, `/sale-returns` emas). Holat o'tkazuvchi amallar — `/{resurs}/{id}/{fe'l}` (`post`, `cancel`, `receive`, `submit-for-review`). **JSON maydonlari, query parametrlari, enum qiymatlari va `operation_id` — snake_case**, DB ustun nomi bilan aynan bir xil (`cash_register_id`, `?doc_date__gte=`, `"posted"`, `goods_receipts_post`). Batafsil — `17-api-umumiy.md` §2 |
| Pagination | Hujjat/registr ro'yxatlari — **cursor-based** (`fastapi-pagination`'ning `CursorPage`, UUIDv7 `id` bo'yicha — vaqt tartibi tabiiy keladi): `?cursor=...&limit=50`. Ma'lumotnoma ro'yxatlari (katalog, kontragent, filial, kassa, ombor, birlik, va h.k. — to'liq ro'yxat `17-api-umumiy.md` §4) — `Page` (page/size + `total`), chunki UI'da sahifalash ko'rsatiladi |
| Filtrlash | `fastapi-filter` — SQLAlchemy modeliga bog'langan deklarativ filtr sinfi (`?status=posted&doc_date__gte=2026-10-01`), qo'lda `if`/`WHERE` zanjiri yozilmaydi |
| Xato formati | `{"error": {"code": "DEBT_LIMIT_EXCEEDED", "message_key": "errors.debt_limit_exceeded", "params": {"limit": "500000.00", "requested": "569000.00"}, "details": [], "request_id": "..."}}` — `code` barqaror mashina kaliti, `message_key` frontend i18next kaliti, `params` — ixtiyoriy obyekt (biznes kontekst: limit/so'ralgan qiymat/`resource`/`reason`, interpolatsiya uchun), `details` — **har doim massiv** (bo'sh bo'lishi mumkin), maydon darajasidagi xabarlar (422'da react-hook-form/zod bilan bir xil shaklda: `{"field": "qty", "message_key": "validation...."}` ro'yxati). To'liq katalog — `17-api-umumiy.md` §15 |
| Idempotency-Key | Yozuvchi so'rovlarda majburiy (frontend har doim yuboradi). Redis `SETNX idem:{tenant}:{key}` — bir lahzali qulf (parallel takror → `409 {code: IDEMPOTENCY_IN_PROGRESS}` + `Retry-After: 1`; bir xil kalit, boshqa `request_hash` → `422 {code: IDEMPOTENCY_KEY_REUSED}`); Postgres `idempotency_keys(tenant_id, key, request_hash, response_status, response_body, created_at, UNIQUE (tenant_id, key))` — **doimiy** javob jurnali (30 kundan keyin tozalanadi, buxgalteriya yozuvi emas), qayta so'rov bo'lsa saqlangan javob qaytariladi (qayta bajarilmaydi). `/sync/push` bundan mustasno: dedupe har voqea bo'yicha `sync_receipts.client_event_id` orqali (`16-offline-sync.md` §3.1). `Idempotency-Key` faqat back-office REST yozuvchi so'rovlariga tegishli. |
| Optimistik qulflash | Ma'lumotnomalarda (`products`, `product_prices`, …) `version INT`. `PATCH` so'rovi `version`ni tanada talab qiladi; mos kelmasa `409 {code: VERSION_CONFLICT}`. Hujjatlarda kerak emas — ular `posted`dan keyin umuman o'zgarmaydi (faqat `cancel` + storno registr qatorlari, `reversal_of_id`; alohida teskari hujjat yo'q — `01-qarorlar.md` #6). Hujjat javoblarida `version` maydoni **yo'q**; `draft`ni `PATCH` qilish — butun qoralamani almashtiradi (13-0 §8) |
| OpenAPI teglari | Har modul — bitta tag (`sales`, `returns`, `debts`, …), router `tags=[...]` orqali; `operation_id` qo'lda beriladi (`sales_create`, `sales_list`) — orval generatsiya qilgan funksiya nomi shundan keladi (`24-frontend-arxitekturasi.md`, 3-bo'lim) |
| Davr yopilgan | `409 {code: PERIOD_CLOSED}` — yopilgan davrga yozishga urinish |
| Auth | **OAuth 2.0 (AS+RS, `app/modules/auth/`)** — to'liq dizayn `14-autentifikatsiya-oauth2.md`da. Veb: BFF, HttpOnly/Secure/SameSite=Lax sessiya cookie (OAuth token brauzerga chiqmaydi); Android: to'g'ridan-to'g'ri `Authorization: Bearer <access_token>`. CSRF — o'zgarmagan: sessiya ID'ga bog'langan, `itsdangerous` bilan imzolangan token (`GET /api/v1/auth/csrf` → `X-CSRF-Token`), CSRF cookie yo'q. Noto'g'ri/eskirgan token → `403 {code: CSRF_INVALID}`. Bearer access token (Android) CSRF tekshiruvidan ozod. Har so'rovda qo'shimcha `require_subscription_ok` dependency (Redis-kesh) — `403 {code: SUBSCRIPTION_RESTRICTED}`. |
| Rate limit | `slowapi` — login, OTP, refresh va AI endpoint'larda qattiqroq limit (brute-force/AI xarajat nazorati, `14-autentifikatsiya-oauth2.md` §12) |

**Middleware/dependency tartibi** (har himoyalangan so'rovda, tashqaridan ichkariga): (1) CORS → (2) CSRF tekshiruvi (faqat cookie-autentifikatsiyali so'rovlarda, Bearer'da yo'q) → (3) auth — cookie'dan `sid`/Bearer'dan JWT orqali claims chiqarish, imzoni/`sid`-revoke keshini tekshirish (`14-autentifikatsiya-oauth2.md` §5) → (4) `require_subscription_ok` — Redis `sub_status` keshi (Redis ishlamasa `subscriptions.status` to'g'ridan-to'g'ri DB'dan, fail-to-DB — `14-autentifikatsiya-oauth2.md` §16.1.1, KICHIK 9), `restricted`/`closed` bo'lsa darhol `403` (istisnolar: `/auth/*`, `/billing/pay` (BFF sahifa), **`GET /billing/plan`, `GET /billing/subscription`, `GET /billing/addons`, `POST /billing/checkout`** (restricted holatda oddiy sessiya o'rniga `pay_token` bilan, `14-autentifikatsiya-oauth2.md` §16.1.1a) **, `GET /billing/payments`, `/billing/webhooks/*`** (o'z imzo tekshiruvi bilan, sessiyadan mustaqil), `/billing/export-my-data` (SMS OTP bilan, D2), `/sync/push` **faqat `scope=sync.drain`** bilan va faqat lokautdan oldingi voqealar uchun — `14-autentifikatsiya-oauth2.md` §16.1, §16.4; oddiy `reports.export`/eksport bu ro'yxatda **yo'q** — lokautda yopiq, D2 bo'yicha alohida `/billing/export-my-data` yo'li bor) → (5) `current_branch_scope`/`X-Branch-Id` tekshiruvi → (6) `require_permission("<code>")` — `role_permissions`+`limit_value` → (7) `Idempotency-Key` tekshiruvi (yozuvchi so'rovlarda) → (8) `tenant_transaction` ochiladi, biznes kod ishga tushadi.

---

## 4. Navbat kutubxonasi: `SAQ` tanlovi

Navbat kutubxonasi tanlovi (`01-qarorlar.md` #2). `arq` 2025-10 dan beri faqat texnik xizmat rejimida (python-arq/arq#510: "maintenance only mode", faqat xavfsizlik tuzatishlari, oxirgi reliz 0.28.0 — 2026-04-16) — yangi loyiha uchun tanlanmaydi.

| Mezon | `SAQ` | `arq` | `dramatiq` | `celery` |
|---|---|---|---|---|
| Asinxron (async def task) | Tabiiy (asyncio) | Tabiiy (asyncio) | Yo'q (sync worker, asyncio uchun alohida event loop kerak) | Qisman (`asgiref`/qo'shimcha sozlash) |
| Broker | Redis yoki Postgres (stack'da allaqachon bor) | Redis (stack'da allaqachon bor) | RabbitMQ/Redis (kengaytma kerak) | RabbitMQ/Redis, lekin og'ir konfiguratsiya |
| Cron | Ichida (`CronJob`) | Ichida (`cron_jobs`) | Yo'q (APScheduler qo'shimcha kerak) | `celery beat` — alohida jarayon |
| SQLAlchemy async sessiyasi bilan moslik | To'g'ridan-to'g'ri (bir xil event loop, bir xil `asyncpg` pool) | To'g'ridan-to'g'ri | Noqulay | Noqulay |
| Monitoring | O'rnatilgan monitoring UI | Rasmiy UI yo'q | Yo'q | Flower (alohida xizmat) |
| Jamoat hajmi/texnik xizmat | MIT, 0.26.4 (2026-05-21), faol | Faqat xavfsizlik tuzatishlari (2025-10, #510) | O'rta | Katta, lekin ortiqcha murakkablik kichik jamoa uchun |

**Qaror: `SAQ`.** Butun backend stack asinxron (`FastAPI` + `SQLAlchemy 2 async` + `asyncpg`); `SAQ` worker'ning o'zi ham asinxron funksiya sifatida ishlaydi — bir xil DB pool, bir xil HTTP klient (`httpx.AsyncClient`) qayta ishlatiladi, ikkinchi concurrency modelini (threads/gevent) o'rganish shart emas. Navbat `app/core/queue.py`dagi `JobQueue` porti ortida; `outbox_jobs` holat manbai bo'lgani uchun kutubxona almashtirish arzon. arq'dagi "monitoring paneli yo'q" kamchiligi SAQ UI bilan yopiladi — bundan tashqari `outbox_jobs` jadvali + oddiy ichki admin ro'yxati orqali ham kuzatiladi (allaqachon ma'lumotlar modelida bor).

Cron (`workers/cron.py`) ro'yxati: davlat hisobotini kunlik tekshirish, qarz eslatmasi, takrorlanuvchi xarajat eslatmasi, 48/72 soat chegarasi monitoringi, **kam qoldiq tekshiruvi** (US-M04-02: `stock_balances.qty <= products.min_stock`, kuniga 1 marta; bir tovar uchun kuniga bitta xabar), **yaroqlilik muddati** (US-M04-06), **obuna eslatmalari va `grace` → `restricted` o'tishi** (US-M17-03), **kunlik Telegram hisobot** (US-M18-02) — `SAQ`ning o'z `CronJob`i bilan, alohida `scheduler` konteyneri sifatida ishga tushadi (`10-umumiy-arxitektura.md`dagi "Rejalashtiruvchi" komponenti).

**Worker/scheduler'da tenant konteksti**: har job'ning birinchi argumenti — majburiy `tenant_id` (`outbox_jobs.tenant_id`dan); job tanasi `async with tenant_transaction(session, tenant_id):` ichida bajariladi, `tenant_id`'siz job darhol xato bilan tugaydi. Scheduler (cron) biznes so'rovi bajarmaydi: `SECURITY DEFINER` funksiyasi `list_active_tenant_ids()` orqali tenantlarni olib, **har tenant uchun alohida job** navbatga qo'yadi. Platformaviy job'lar (obuna holati, billing) ham shu fan-out orqali tenant kontekstida ishlaydi; RLS'ni chetlab o'tadigan worker roli yo'q.

---

## 5. Kutubxonalar

| Vazifa | Kutubxona | Nima uchun |
|---|---|---|
| Web freymvork | **FastAPI** | Qaror qilingan stack; OpenAPI avtomatik, Pydantic bilan tabiiy integratsiya |
| Validatsiya/sxema | **Pydantic v2** | FastAPI bilan birga keladi, tez (Rust core), orval uchun to'g'ri OpenAPI sxema chiqaradi |
| Sozlamalar | **pydantic-settings** | Namuna loyihadagi naqsh — `.env` + real env, `env_prefix="ERP_"`, prod-xavfsizlik guard (`model_validator`) |
| ORM | **SQLAlchemy 2 (async) + asyncpg** | Namuna loyihada sinalgan; 2.0 stili (`Mapped[...]`) tip xavfsizligini beradi |
| Migratsiya | **Alembic** (asinxron `env.py`, namunadagidek) | Zero-downtime siyosati (13-bo'lim) uchun standart vosita |
| UUID | **uuid-utils** (Rust bog'lovchi, UUIDv7) | `11-malumotlar-modeli.md` UUIDv7 qarorini qo'lda implementatsiya qilmasdan tez generatsiya qiladi |
| Navbat/worker | **SAQ** | 4-bo'lim — asinxron stack bilan tabiiy mos, o'rnatilgan monitoring UI |
| Kesh/navbat broker | **redis** (`redis-py` asinxron klient) | SAQ broker + sessiya/kesh/rate-limit (`10-umumiy-arxitektura.md`) |
| Tashqi HTTP | **httpx** (async) | OFD/e-faktura/Click/Payme/SMS/Telegram/Claude API — bitta klient, async |
| Qayta urinish | **tenacity** | Har integratsiya adapterida exponential backoff + jitter — qo'lda `for`/`sleep` yozilmaydi |
| Pagination | **fastapi-pagination** | Cursor va page/size — qo'lda offset/limit hisoblanmaydi (3-bo'lim) |
| Filtrlash | **fastapi-filter** | Deklarativ query filtr, SQLAlchemy modeliga bog'langan. `filter.sort(filter.filter(select(Model)))` → `await session.execute(...)` yoki `fastapi_pagination.ext.sqlalchemy.paginate(session, stmt)` (AsyncSession qo'llab-quvvatlanadi). Versiya: ≥3.0 (SQLAlchemy 2.0). |
| Logging | **structlog** | JSON struktura log, tenant/so'rov ID context — namuna loyihadagi JSONL log yondashuvi |
| Trace | **OpenTelemetry** (FastAPI + SQLAlchemy instrumentatsiyasi) | So'rov → posting → worker zanjirini kuzatish |
| Metrika | **prometheus-client** | `/metrics`; posting latensiyasi, navbat chuqurligi, AI xarajati |
| Xato kuzatish | **sentry-sdk** | FastAPI/Starlette integratsiyasi tayyor |
| Parol/PIN hash | **passlib[argon2]** (argon2-cffi), aniq algoritm **argon2id** | OWASP tavsiyasi (`14-autentifikatsiya-oauth2.md` §4.1, §13) |
| OAuth 2.0 protokol skeleti | **Authlib** | RFC 6749/7636/7009/7662/8414/9068 — `authlib.oauth2.rfc6749` abstrakt grant/klient sinflari, storage hook'lari bizning SQLAlchemy repozitorilarimizga bog'lanadi (`14-autentifikatsiya-oauth2.md` §1) |
| JWT/JWS/JWK (access token, JWKS, litsenziya tokeni) | **joserfc** (Authlib muallifi, EdDSA/ES256) | `PyJWT` — muqobil. `14-autentifikatsiya-oauth2.md` §5–6, §17 |
| CSRF | **itsdangerous** | Django/Flask'da sinalgan imzolash primitiv; cookie-based sessiyada sessiyaga bog'langan sinxronizator-token uchun yetarli, `fastapi-csrf-protect`ka nisbatan ko'proq qo'llab-quvvatlanadi |
| Rate limit | **slowapi** | `limits` kutubxonasini o'raydi, Redis backend, FastAPI dependency sifatida |
| Fayl yuklash | **python-multipart** | FastAPI'ga fayl/forma qabul qilish uchun shart (xarajat cheki fotosi, Excel import) |
| S3 | **aioboto3** | Async stack bilan bir xil event loop (sync `boto3` emas) |
| Excel | **openpyxl** | Boshlang'ich katalog/qoldiq/qarz importi (US-M04-04, US-M08-07), hisobot eksporti (M12) |
| Shtrix-kod/yorliq | **python-barcode** (MIT; EAN-13, Code128) + **zxing-cpp** (Apache-2.0; DataMatrix/QR server PDF uchun) | Yorliqlar asosan brauzerda `bwip-js` (MIT, GS1 DataMatrix ham) bilan chiziladi. `treepoem` **taqiqlangan**: Ghostscript AGPL/tijoriy — SaaS'da manba kodini ochish yoki Artifex litsenziyasini talab qiladi |
| Telegram bot | **aiogram** | Asinxron, FastAPI bilan bir xil stack; `10-umumiy-arxitektura.md`da allaqachon tanlangan |
| AI | **anthropic** (rasmiy SDK), `api` rejimida | README qarori: Claude API (Haiku 5.5), `AiProvider` porti — `fake`/`cli` (dev) / `api` (prod) |
| Vaqt/muddat | **pendulum** | 5 kalendar kun (M10), 48/72 soat (M01/M06), qarz eskirish guruhlari (0-30/31-60/60+, M08) — qo'lda `timedelta` arifmetikasi o'rniga o'qiladigan davr hisob-kitobi; saqlash — `TIMESTAMPTZ`/stdlib `zoneinfo` (Asia/Tashkent) |
| Son/pul formatlash, i18n | **babel** | Eksport qilinadigan hisobot/PDF'da son formatlash (uz_Latn); UI formatlash frontendda (`Intl.NumberFormat`) |
| CLI (seed, ops skript) | **typer** | `scripts/seed.py` va h.k. — `argparse` o'rniga deklarativ CLI |
| Testlar | **pytest, pytest-asyncio, factory-boy, testcontainers, schemathesis** | 6-bo'lim |
| Kod sifati | **ruff, mypy, pre-commit** | Namuna loyihada allaqachon ishlatiladi (`.ruff_cache`, `mypy` venv'da ko'rindi) |

**Ataylab kiritilmagan**: `dependency-injector` paketi — namuna loyihada `venv`da mavjud, lekin haqiqiy composition-root (`di_builders.py`) uni ishlatmaydi, oddiy factory funksiyalar + FastAPI `Depends` bilan yetarli; shu konventsiya takrorlanadi (ortiqcha abstraksiya qo'shilmaydi). Agar jamoa deklarativ konteyner xohlasa, bu — tasdiqlanishi kerak bo'lgan qaror (Ochiq savollar).

---

## 6. Testlash strategiyasi

| Qatlam | Vosita | Qamrov |
|---|---|---|
| Domain/bitlik | `pytest` + `factory-boy` (fixture factory, SQLAlchemy'siz) | Posting qoidalari — 2.2-bandidagi kabi **sonli misollar**: FIFO/AVECO hisob-kitobi, QQS summasi, qarz limiti chegarasi, chegirma manfiy narxga olib kelmasligi. Har holat — Given/When/Then (mahsulot hujjatlaridagi US formatiga mos) |
| Integratsiya | `pytest-asyncio` + `testcontainers[postgres]` | Haqiqiy PostgreSQL konteynerida: posting tranzaksiyasi, parallel ikki sotuv bitta oxirgi tovarga (`FOR UPDATE` ishlayotganini tekshirish), recost job, Alembic migratsiyalarini oxirigacha ishga tushirish |
| RLS izolyatsiya | `testcontainers[postgres]` | Ikki tenant yaratiladi, `tenant_id=A` kontekstida yozilgan qator `tenant_id=B` kontekstidan **ko'rinmasligi** tasdiqlanadi (RLS siyosati + `set_config('app.tenant_id', …, true)` ikkisi birga, `tenant_transaction()` ichida); RLS siyosati ataylab o'chirilgan holat ham testlanadi (kod xatosi RLS'siz ham xavfsiz qolishini tekshirish uchun — ikkinchi himoya qatlami, Asosiy xulosa 4). Worker: tenant A job'i B'ni ko'rmasligi, `tenant_id`'siz job rad etilishi, bitta ulanishda ketma-ket job'lar orasida kontekst qolmasligi (`15-xavfsizlik-va-audit.md` §3.3). |
| **OAuth/autentifikatsiya** | `testcontainers[postgres,redis]`, `httpx.AsyncClient` — **mock yo'q** | To'liq Authorization Code+PKCE oqimi, refresh rotatsiyasi+reuse detection, revoke/introspect, obuna lokauti (grace→restricted→to'lov), brute-force, qurilma bekor qilish → token rad etilishi. To'liq ro'yxat `14-autentifikatsiya-oauth2.md` §21. |
| Kontrakt | `schemathesis` | Ishga tushirilgan API'ning `/openapi.json`'idan avtomatik so'rov generatsiyasi — frontend orval generatsiyasi bilan backend sxemasi mos kelishini kafolatlaydi (CI'da `api:gen` tekshiruvi bilan birga) |
| E2E (tanlab) | `httpx.AsyncClient` + `pytest-asyncio` | Bitta hujjat oqimi boshidan oxirigacha: sotuv → qaytarish → buxgalteriya yozuvi → hisobot |

---

## 7. CI, lokal dev, konfiguratsiya

### 7.1. CI quvuri (platforma — GitHub Actions, standart qaror: `26-ochiq-savollar-reestri.md` #60)

1. `ruff check` + `ruff format --check`, `mypy app`.
2. `pytest` (bitlik, `testcontainers` servis sifatida CI runner'ida).
3. Alembic: `alembic upgrade head` bo'sh bazada — migratsiya ishlayotganini tekshirish.
4. `schemathesis run` — ishga tushirilgan API'ga qarshi.
5. `openapi.json` eksport + frontend CI'dagi `api:gen --check` bilan taqqoslash (sxema drift bo'lsa — build muvaffaqiyatsiz, `10-umumiy-arxitektura.md` 3-bo'lim).
6. Docker image build + (`main` branch'da) registry'ga push.

### 7.2. Lokal dev — docker compose

Namuna loyihadagi `deploy/compose.yml` tuzilmasidan, lekin **bitta tenant stack emas** — lokal muhit ham ko'p-tenant rejimida ishlaydi:

```yaml
services:
  postgres:   # postgres:17-alpine, host portga chiqarilgan
  redis:      # redis:7-alpine
  migrate:    # bir martalik: alembic upgrade head (profile: tools)
  seed:       # bir martalik: python -m app.cli seed (profile: tools)
  api:        # uvicorn --reload, host portga chiqarilgan, AI_MODE=fake|cli
  worker:     # SAQ app.workers.worker_settings orqali
  scheduler:  # SAQ CronJob rejimi
  bot:        # aiogram polling (dev'da webhook shart emas)
```

`AIOS`dagi kabi non-root user, ko'p bosqichli Dockerfile, `/health/ready` orqali `HEALTHCHECK` — aynan shu naqsh ko'chiriladi (faqat `claude` CLI bosqichi `api` rejimida ixtiyoriy bo'lib qoladi, lokal `cli` tanlanganda saqlanadi).

### 7.3. Konfiguratsiya va sirlar

`app/core/config.py`: `pydantic-settings`, `env_prefix="ERP_"`, `.env` (lokal) / real environment (prod). Namuna loyihadagi guard naqshi takrorlanadi:

```python
@model_validator(mode="after")
def _enforce_production_security(self) -> "Settings":
    if self.environment == "prod":
        if not self.auth_enabled or self.auth_secret == _INSECURE_DEFAULT:
            raise ValueError("prod'da auth yoqilgan va maxfiy kalit o'zgartirilgan bo'lishi shart")
        if self.ai_mode == "cli":
            raise ValueError("prod'da AI rejimi 'api' bo'lishi shart (README qarori)")
    return self
```

Sirlar (DB parol, Redis parol, Click/Payme kalitlari, Claude API kaliti, SMS/Telegram token) — kod/`.env`da emas, UzCloud sir-ombori yoki muhit o'zgaruvchisi orqali (`10-umumiy-arxitektura.md`, 3-bo'lim muhitlar jadvali: local — `fake/cli`, staging/prod — `api`, alohida kalitlar).

---

## 8. Observability

- **Logging**: `structlog`, JSON format, har yozuvda `tenant_id`, `request_id`, `user_id`; shaxsiy ma'lumot (telefon, STIR) log'ga tushmasligi uchun redaction filtri (namuna loyihadagi `RedactingFilter` naqshi).
- **Readiness/liveness**: `/health/live` (jarayon ishlayaptimi) va `/health/ready` — namuna loyihadagi **gating vs reported** bo'linishi: *gating* (API 200 bermasa stack buziladi) = Postgres round-trip + Alembic sxema versiyasi (`db_create_all=false` muhitlarda) + Redis; *reported* (faqat ma'lumot, bloklamaydi) = OFD/e-faktura/Claude API/S3 reachability — mijoz tomondagi tashqi tizim uzilishi deploy/health'ni bloklamasligi kerak.
- **Metrika**: `prometheus-client` — HTTP latensiya, posting tranzaksiya davomiyligi, `outbox_jobs` navbat chuqurligi/urinish soni, AI so'rov narxi (`ai_requests.cost_usd` yig'indisi).
- **Trace**: OpenTelemetry, FastAPI+SQLAlchemy+httpx avtomatik instrumentatsiya; eksport nuqtasi (Grafana Tempo/Jaeger, UzCloud'da qaysi xizmat) — ochiq savol.
- **Xato kuzatish**: `sentry-sdk`, tenant/branch context tag sifatida (lekin mijoz PII'siz).

---

## 9. Deploy

Konteynerlar (`10-umumiy-arxitektura.md`, 3-bo'lim bilan mos): **api**, **worker**, **scheduler**, **bot**, (frontend alohida `web` — statik, `24-frontend-arxitekturasi.md`).

Namuna loyihadan **ko'chiriladi**: ko'p bosqichli `Dockerfile` (uv bilan bog'liqliklarni qulflangan holda o'rnatish, non-root `app` user, `HEALTHCHECK`), Alembic'ning bir martalik `migrate` konteyneri (api/worker undan keyin boshlanadi, `db_create_all=false` har joyda konteyner stack'da).

Namuna loyihadan **farqlanadi** (chunki u — bitta tenant/bitta stack, bu loyiha — ko'p tenant/bitta umumiy stack):

| Jihat | Namuna loyiha | Bu loyiha |
|---|---|---|
| Stack soni | Har mijoz uchun alohida (`aios-<tenant>`) | Bitta umumiy stack, tenant — RLS bilan ma'lumotlar darajasida |
| `api`/`worker` | Bitta nusxa | **Gorizontal ko'payadi** (holat yo'q — sessiya Redis'da, tranzaksiya DB'da) |
| `scheduler` | Bitta nusxa, muammosiz | **Yagona nusxa bo'lishi shart** (cron ikki marta ishlamasligi uchun) — Postgres advisory lock (`pg_try_advisory_lock`) bilan yetakchi tanlanadi, bir nechta `scheduler` konteyneri ishga tushsa ham faqat biri faol bo'ladi |
| Baza | Konteynerdagi Postgres | **UzCloud boshqariladigan DBaaS** (managed Postgres) — konteyner emas |
| Fayl ombori | Yo'q | S3-mos ombor (UzCloud'da mavjudligi — `10-umumiy-arxitektura.md` ochiq savol 2) |
| Ulanish pool'i | — | MVP: tashqi pooler yo'q — SQLAlchemy `AsyncAdaptedQueuePool` (asyncpg), `pool_size`/`max_overflow` × api+worker nusxalari soni DBaaS `max_connections` dan kichik. Pooler qo'shilsa (PgBouncer, **transaction** rejimi): PgBouncer ≥1.21 `max_prepared_statements` yoqiladi, yoki asyncpg `prepared_statement_cache_size=0` + `prepared_statement_name_func` (uuid nomlar). Session darajasidagi `SET` taqiqlanadi — tenant faqat `set_config(..., true)` bilan tranzaksiya ichida (1-bo'lim). UzCloud DBaaS'da o'rnatilgan pooler bor-yo'qligi — ochiq savol |

---

## 10. DB migratsiya siyosati (zero-downtime)

**Expand–contract**: har o'zgarish ikki (yoki undan ko'p) kichik Alembic revisiyaga bo'linadi:

1. **Expand**: faqat qo'shish — yangi ustun **NULL bilan ruxsat etilgan** (yoki `DEFAULT` bilan) yoki yangi jadval; eski kodni buzmaydi. Deploy qilinadi, eski va yangi kod versiyasi parallel ishlay oladi (rolling deploy).
2. **Backfill**: kerak bo'lsa, worker job orqali (katta jadvalda `UPDATE ... WHERE id IN (batch)` — bitta katta tranzaksiya emas, bo'lib-bo'lib).
3. **Kodni ko'chirish**: yangi kod yangi ustunni ishlatadi, eski ustun hali o'qiladi (fallback).
4. **Contract**: faqat barcha instance yangi kodga o'tgach va backfill tugagach — eski ustun/jadval `DROP` qilinadi, alohida revisiyada.

Taqiqlar: bir revisiyada ustun **nomini o'zgartirish** yoki **tipini o'zgartirish** (buning o'rniga: yangi ustun qo'sh — ko'chir — eskisini o'chir); `NOT NULL`ni bitta qadamda qo'shish (avval `DEFAULT` + backfill, keyin `NOT NULL`). `migrate` konteyneri har deploy'dan oldin, pre-release `pg_dump` bilan birga ishga tushadi (namuna loyihadagi `release.sh` naqshi).

---

## 11. Seed data

`scripts/seed.py` (typer CLI, idempotent — qayta ishga tushirilsa xato bermaydi, `ON CONFLICT DO NOTHING`/mavjudligini tekshiradi):

- **Rollar**: 5 standart (`owner`, `manager`, `cashier`, `storekeeper`, `accountant`) — `is_system=true`, `role_permissions` bilan boshlang'ich huquq to'plami (`11-malumotlar-modeli.md`, 3-bo'lim; to'liq ro'yxat `15-xavfsizlik-va-audit.md`da).
- **Birliklar** (`units`): `pcs`, `kg`, `l`, `m`, `box` — global, `is_fractional` belgisi bilan.
- **Xarajat toifalari** (`expense_categories`): Ijara, Kommunal, Ish haqi, Transport, Soliq va yig'imlar, Ta'mirlash, Boshqa (M15, US-M15-01 — standart ro'yxat, tenant o'zgartira oladi).
- **Tariflar** (`plans`): yagona `standard` tarifi (1 kassa bazaga kiritilgan) — `limits` JSONB (`included_cash_registers`, `ai_monthly_tokens`), qo'shimcha kassa `addons.extra_register` orqali; aniq raqamlar `25-nofunksional-talablar.md` §11 va `12-db-sxema.md` §5.1 seed'idan (bu hujjatda takrorlanmaydi).
- **Ruxsatlar katalogi** (`permissions`, jadval emas — kod ichida ro'yxat, `access` modulida) — kod deploy bilan birga keladi, seed kerak emas.

Seed — Alembic "data migration" emas (bazani versiyalash bilan aralashtirmaslik uchun), alohida bosqich sifatida `migrate` konteyneridan keyin, birinchi deploy'da bir marta ishga tushadi.

---

## Ochiq savollar

1. **DI yondashuvi**: namuna loyihadagidek oddiy factory-funksiya + `Depends` (5-bo'limdagi tanlov) yetarlimi, yoki `dependency-injector` paketi (deklarativ `Container`) qo'shilsinmi — standart qaror: oddiy factory + `Depends` (`26-ochiq-savollar-reestri.md` #59); deklarativ konteyner kerak bo'lsa keyin qayta ko'riladi.
2. **CI vositasi**: quvur bosqichlari (7.1-band) tasdiqlangan, lekin platforma — standart qaror: GitHub Actions (`26-ochiq-savollar-reestri.md` #60).
3. **OpenTelemetry eksport nuqtasi**: UzCloud'da Grafana Tempo/Jaeger kabi xizmat bormi — tekshirish kerak (`10-umumiy-arxitektura.md` ochiq savol 2 bilan bog'liq, S3-mos ombor savoli ham hali ochiq; reestr #53 B, #27 B — interim: o'z-hosted Grafana Tempo, `StoragePort` + zaxira o'z-MinIO).
4. **`scheduler`ning yagona nusxa kafolati**: Postgres advisory lock taklif qilindi (9-bo'lim) — Redis-based lock (`redis-py` + `SET NX` TTL bilan) muqobil variant, standart qaror: Postgres advisory lock (`26-ochiq-savollar-reestri.md` #61).
5. **Aniq ruxsat kodlari ro'yxati** (`permissions`) va **NSBU №21 hisob raqamlari** (`ledger_entries.account_dt/kt`) — bu hujjatda ataylab keltirilmadi, `15-xavfsizlik-va-audit.md` va `13-provodka-qoidalari.md`da (buxgalter tasdig'i shart) aniqlanadi.
6. **`recost_jobs` va davr yopish orasidagi aniq biznes qoida** — yopilgan oy **qayta ochilmaydi** (qaror #23, tavsiya #15), kech kelgan o'zgarish joriy ochiq davrda tuzatish yozuvi bilan (`ledger_adjustments`); batafsil `13-provodka-qoidalari.md` §5.
7. **`zxing-cpp`ning GS1 DataMatrix (FNC1) chiqishi** Asl belgisi talabiga mosligi 0-bosqichda sinab ko'riladi; mos kelmasa server yorlig'i ham `bwip-js` (Node) orqali (`26-ochiq-savollar-reestri.md` #62).

## Manbalar

- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` — OAuth 2.0 AS/RS, Authlib/joserfc tanlovi, token jadvallari, obuna lokauti.
- `spec/kod-uchun/10-umumiy-arxitektura.md` — komponentlar, muhitlar, navbat ochiq savoli.
- `spec/kod-uchun/11-malumotlar-modeli.md` — jadvallar, registrlar, holat mashinalari, raqamlash.
- `spec/kod-uchun/24-frontend-arxitekturasi.md` — API konventsiyalari (cookie/CSRF, Idempotency-Key, X-Branch-Id, xato formati, orval).
- `spec/kod-uchun/03-modullar-talablari.md` — M01–M18 foydalanuvchi hikoyalari va chekka holatlar.
- `E:/Project/universal_ai_platform/src/backend` — qatlamli tuzilma, `pydantic-settings`/DI/Alembic/health/Dockerfile naqshlari (struktura namunasi, kod emas — `spec/README.md` qoidasiga mos, O'zbekiston-specific qiymat olinmagan).

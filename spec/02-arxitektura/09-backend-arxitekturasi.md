# Backend arxitekturasi

*2026-10-14 · Asos: `00-umumiy-arxitektura.md`, `01-malumotlar-modeli.md`, `08-frontend-arxitekturasi.md`, `spec/01-mahsulot/02-modullar-talablari.md` (M01–M18). Namuna loyiha (tuzilma va konventsiya uchun, kod emas): `E:/Project/universal_ai_platform/src/backend`.*

## Asosiy xulosalar

1. **Modulli monolit**: `backend/app/modules/<modul>/` — 19 modul papkasi (18 mahsulot moduliga + kesishuvchi `integrations`/`sync`/`ai` ga mos), har biri bir xil ichki qatlam: `domain/` → `application/` → `infrastructure/` → `api/`. Umumiy infratuzilma — `app/core` (DB sessiya + tenant kontekst, auth, huquq dependency, idempotentlik, xatolar, sozlamalar, logging) va `app/workers` (navbat ishlari, cron).
2. **"Posting service" naqshi** — har bir hujjat turi uchun bitta xizmat, bitta DB tranzaksiyada hujjat holatini **va** barcha registrlarni (`stock_moves`/`stock_lots`, `debt_moves`, `cash_moves`, `ledger_entries`, `vat_moves`) birga yozadi; bekor qilish — faqat teskari yozuv, `UPDATE`/`DELETE` yo'q.
3. **Navbat kutubxonasi — `arq`** (ochiq savol hal qilindi, 4.1-band): to'liq asinxron, `asyncpg`/SQLAlchemy 2 async stack bilan bir xil event loop, Redis'ga tayanadi (allaqachon stack'da bor), ichki cron qo'llab-quvvatlaydi — alohida Celery/RabbitMQ infratuzilmasi kerak emas.
4. **Tenant izolyatsiyasi kod darajasida ikki marta**: (a) har so'rovda `SET LOCAL app.tenant_id` (DB sessiya dependency) + (b) PostgreSQL RLS siyosati (`05-xavfsizlik-va-audit.md`) — ikkinchisi birinchisi buzilsa ham (kod xatosi) himoya qiladi.
5. **Kutubxona birinchi, qo'lda kod oxirgi**: pagination — `fastapi-pagination`, filtrlash — `fastapi-filter`, retry — `tenacity`, UUIDv7 — `uuid-utils`, muddat arifmetikasi (5 kalendar kun, 48/72 soat, qarz eskirish guruhlari) — `pendulum`, Excel — `openpyxl`, shtrix-kod/yorliq — `python-barcode` + `treepoem`. To'liq jadval 5-bo'limda.
6. **AI — port naqshi** (`AiProvider`, README qarori): `fake` (test) | `cli` (lokal dev, Claude Code CLI) | `api` (staging/prod, `anthropic` SDK) — namuna loyihadagi `ClaudePort`/`CliClaudeClient`/`FakeClaudeClient` naqshining aynan takrorlanishi, faqat `cli` o'rniga prodda `api`.
7. **Namuna loyihadan nusxa olinadi**: qatlamli papka tuzilmasi, `pydantic-settings` + `lru_cache get_settings()` + prod-da xavfsizlik guard (`model_validator` — auth yoqilmagan/standart sir/sqlite bo'lsa ishga tushmaydi), composition-root'dagi `_build_*` factory funksiyalar, Alembic'ning asinxron `env.py`'si, `ReadinessProbe`'ning "gating vs reported" bo'linishi, ko'p bosqichli Dockerfile (non-root user, `HEALTHCHECK`).
8. **Namuna loyihadan farqlanadi**: u — har mijoz uchun alohida stack (bitta tenant); bu loyiha — **bitta umumiy stack, ko'p tenant, RLS bilan**: `api`/`worker` gorizontal ko'payadi, `scheduler` yagona nusxa bo'lishi kerak (Postgres advisory lock bilan) (adapterlar: OFD/e-faktura/Asl belgisi/Click-Payme adapterlari).
9. API — `/api/v1`, xato formati `{code, message_key, details}` (frontenddagi zod/i18next bilan bir xil shakl), `Idempotency-Key` Redis tezkor qulf + Postgres doimiy jurnal bilan, optimistik qulflash `version` maydoni orqali.
10. Test strategiyasi — bitlik testlar provodka qoidalari uchun sonli misollar bilan, `testcontainers` orqali haqiqiy Postgres'da integratsiya va RLS izolyatsiya testlari, `schemathesis` OpenAPI'dan kontrakt testlari.

---

## 1. Repozitoriy tuzilishi

```
backend/
├── app/
│   ├── core/                        # kesishuvchi infratuzilma (hech qaysi modulga tegishli emas)
│   │   ├── config.py                 # Settings (pydantic-settings), get_settings()
│   │   ├── db/
│   │   │   ├── session.py            # async engine, AsyncSession, SET LOCAL app.tenant_id
│   │   │   └── base.py               # DeclarativeBase, umumiy mixin'lar (TenantMixin, TimestampMixin)
│   │   ├── auth/                     # sessiya cookie, CSRF, JWT (ichki admin), parol hash
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
│   │   ├── access/                   # M13 foydalanuvchi, rol, ruxsat, auth
│   │   ├── branches/                 # M14 filial, ombor, kassa apparati, qurilma ro'yxati
│   │   ├── expenses/                 # M15 xarajat, toifa, takrorlanuvchi xarajat
│   │   ├── cash/                     # M16 kassa naqd pul harakati, smena sanash
│   │   ├── billing/                  # M17 tarif, obuna, to'lov (Click/Payme), platforma admin
│   │   ├── notifications/            # M18 bildirishnoma, Telegram bot (aiogram), SMS
│   │   ├── integrations/             # OFD, e-faktura, e-TTN, Asl belgisi, E-IMZO — har biri adapter
│   │   ├── ai/                       # AiProvider porti, AI-xx funksiyalar, ai_requests/feedback
│   │   └── sync/                     # offline outbox qabul qilish, client_event_id dedupe, qurilma holati
│   └── workers/
│       ├── jobs/                      # arq task funksiyalari (bitta modulga tegishli bo'lsa ham shu yerda
│       │                               # ro'yxatga olinadi — modul papkasidagi `tasks.py` dan import qilib)
│       ├── cron.py                    # arq cron_jobs ro'yxati (davlat hisoboti eslatmasi, qarz eslatmasi, recost)
│       └── worker_settings.py         # arq WorkerSettings (navbatlar, concurrency, Sentry/OTel init)
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
│   └── tasks.py          # arq job'lar (masalan "ofd_send") — workers/jobs ro'yxatiga shu yerdan import qilinadi
└── api/
    ├── router.py          # APIRouter(prefix="/sales", tags=["sales"])
    ├── schemas.py          # Pydantic v2 request/response (OpenAPI → orval manbasi)
    └── deps.py             # modulga xos dependency (masalan faol smenani talab qilish)
```

**Qatlamlar orasidagi qoida** (namunadagi `aios/domain|application|infrastructure|interface` bo'linishidan olingan, FSD'dagi "faqat pastga import" qoidasiga o'xshash): `api → application → domain`; `infrastructure` faqat `domain`dagi portlarni amalga oshiradi, `application` uni interfeys orqali ko'radi (dependency inversion — DI composition root `app/main.py` + modul-ichidagi kichik `wiring.py` bog'laydi). Modullar bir-birining `infrastructure`/`api` qatlamini **import qilmaydi** — faqat boshqa modulning `application`/`domain` portini (masalan `sales` moduli `inventory.application.ports.StockPort`ni chaqiradi, `inventory.infrastructure`ni emas). Bu modulli monolitni keyin mikroservisga ajratishni osonlashtiradi (`00-umumiy-arxitektura.md`, 1-xulosa).

### `app/core/db` — tenant kontekst

```python
# app/core/db/session.py (konventsiya, kod emas — spec bosqichi qoidasi)
async def get_session(tenant_id: UUID = Depends(current_tenant_id)) -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        await session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})
        yield session
```

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

`post()` ichida **bitta** `async with session.begin():` bloki:

1. Hujjat qatorlarini tekshiradi (biznes qoida — `domain/rules.py`): limit, manfiy qoldiq siyosati, davr yopilmaganligi (`period_closings`, 2.4-band).
2. Kerakli qatorlarni **qulflab o'qiydi** (`SELECT … FOR UPDATE`) — bitta ombordagi bitta tovarning `stock_lots`/`stock_balances` qatori, bitta mijozning `debt_balances` qatori, bitta smenaning `cash_moves` jamlanmasi — shu orqali ikki parallel so'rov (ikki kassa bitta oxirgi tovarni sotishi) DB darajasida ketma-ketlashtiriladi, ilova darajasida qo'shimcha qulf kerak emas.
3. Barcha registrlarga append-only yozadi: `stock_moves` (+ FIFO/AVECO bo'yicha `stock_lots.qty_left`ni kamaytirish), `debt_moves`, `cash_moves`, `ledger_entries`, `vat_moves` — qaysi biri hujjat turiga tegishli bo'lsa.
4. Hujjat holatini `posted`ga o'tkazadi, `posted_at`ni yozadi.
5. Tranzaksiya commit bo'lgach (`after_commit` hook), tashqi integratsiya ishlarini **navbatga** qo'yadi (`outbox_jobs` qatori + `arq.enqueue_job`) — OFD'ga yuborish, e-faktura, Telegram xabar. **Hech qachon tashqi tizim tranzaksiya ichida chaqirilmaydi** (`00-umumiy-arxitektura.md`, 7-xulosa: API tashqi tizimni kutib turmaydi).

Bitta tranzaksiyada yozilishi kerakligi sababi — `01-malumotlar-modeli.md` 4-xulosasi: hujjat holati va registrlar birga yoziladi yoki birga bekor bo'ladi (DB darajasidagi atomiklik, ilova darajasida "deyarli atomik" emas).

### 2.2. Shartli sonli misol (FIFO, tannarx)

*Quyidagi raqamlar faqat posting mantiqini ko'rsatish uchun shartli misol — tadqiqot/talab hujjatidan olingan raqam emas.*

Ombordagi "Shakar" partiyalari (FIFO, eng eski birinchi):

| Partiya | `qty_left` | `unit_cost` |
|---|---|---|
| Lot-1 (eski) | 5 kg | 9 500 so'm |
| Lot-2 | 8 kg | 9 800 so'm |

Sotuv: 10 kg, QQS'siz sotuv narxi 12 000 so'm/kg.

FIFO iste'moli: Lot-1'dan 5 kg (5 × 9 500 = 47 500 so'm) + Lot-2'dan 5 kg (5 × 9 800 = 49 000 so'm) → `sale_lines.lot_allocations = [{lot: 1, qty: 5, cost: 47500}, {lot: 2, qty: 5, cost: 49000}]`, jami tannarx (COGS) = **96 500 so'm**; Lot-2'da 3 kg qoladi.

Shu bitta postingda yoziladigan qatorlar (soddalashtirilgan):

- `stock_moves`: −10 kg (sotuv), cost_amount = −96 500.
- `stock_lots`: Lot-1.qty_left = 0, Lot-2.qty_left = 3.
- `ledger_entries`: Dt "Tovar-moddiy zaxira (chiqim)/Sotilgan tovar tannarxi" — Kt "Tovar-moddiy zaxira" = 96 500 (aniq hisob raqamlari `02-provodka-qoidalari.md`da).
- `ledger_entries`: Dt "Kassa naqd" — Kt "Sotuv daromadi" = 120 000 (10 × 12 000).
- `vat_moves`: output, base_amount = 120 000, vat_amount = 14 400 (12%) — agar tovar standart QQS stavkasida bo'lsa.
- `cash_moves`: +120 000 (to'lov turi "naqd" bo'lsa) yoki `debt_moves`: +134 400 (to'lov turi "nasiya" bo'lsa, QQS bilan).

Bitlik test shu jadvaldagi kirish/chiqish qiymatlarini aynan tekshiradi (5-bo'lim).

### 2.3. Bekor qilish (reversal)

`reverse()` yangi hujjat yaratmaydi — original hujjatning holatini `cancelled`ga o'tkazadi va **har bir yozilgan registr qatoriga teskari belgili nusxa** qo'shadi (`doc_type`/`doc_id` original hujjatga ishora qiladi, lekin yangi qator — hech qachon `UPDATE`). `stock_lots.qty_left` FIFO bo'yicha **teskari tartibda** (oxirgi iste'mol qilingan partiyadan) qaytariladi, shunda partiya tarixi davomiy qoladi. Original hujjat `reversed_by_id` orqali teskari hujjatga bog'lanadi (`01-malumotlar-modeli.md`, umumiy sarlavha maydonlari).

### 2.4. Recost ishlari va davr yopish

- **Recost** (`recost_jobs: tenant, warehouse, product, from_date`): o'tgan sanali hujjat (kech sinxron, kech kirim) kelganda navbatga qo'yiladi (arq job `recost_product`); job shu sanadan keyingi barcha chiqim postinglarini **FIFO/AVECO bo'yicha qayta hisoblaydi** va `ledger_entries`/`stock_moves`ga **tuzatish yozuvi** qo'shadi (asl yozuvni o'zgartirmaydi — append-only tamoyili shu yerda ham amal qiladi). `period_closings`ga tegadigan sana bo'lsa, job **rad etiladi** va `notifications` moduliga ogohlantirish yuboradi (`01-malumotlar-modeli.md`, 7-bo'lim).
- **Davr yopish** (`accounting` moduli, `period_closings` jadvali): yopishdan oldin tekshiradi — hech qanday `draft`/`fiscal_pending` hujjat yo'qligini, barcha `recost_jobs` tugaganini; yopilgandan keyin shu sanagacha bo'lgan **yangi posting rad etiladi** (`PERIOD_CLOSED` xato kodi, 3-bo'lim).

```mermaid
sequenceDiagram
    participant C as Veb-kassa
    participant API as FastAPI /sales
    participant PS as SalePostingService
    participant DB as PostgreSQL
    participant Q as Redis (arq)
    participant W as Worker

    C->>API: POST /sales (Idempotency-Key, X-Branch-Id)
    API->>DB: idempotency qaytarilgan javob bormi?
    API->>PS: post(sale)
    PS->>DB: BEGIN; FOR UPDATE qatorlar
    PS->>DB: stock_moves + stock_lots + debt/cash_moves + ledger_entries + vat_moves + status=posted
    PS->>DB: COMMIT
    PS->>Q: enqueue "ofd_send", "einvoice_check" (agar kerak bo'lsa)
    API-->>C: 201 Created (chek, fiskal kutilmoqda)
    Q->>W: job navbatdan olinadi
    W->>W: OFD'ga yuborish (httpx + tenacity retry)
    W->>DB: fiscal_receipts.status = fiscalized
```

---

## 3. API konventsiyalari

| Jihat | Qaror |
|---|---|
| Versiyalash | `/api/v1/...`; keyingi breaking o'zgarish — `/api/v2`, eski versiya e'lon qilingan muddat davomida saqlanadi |
| Resurs nomlash | Ko'plik, kebab emas snake: `/sales`, `/sale-returns` emas `/returns` (hujjat turi bo'yicha, 01-malumotlar-modeli jadval nomlariga mos) |
| Pagination | Hujjat/registr ro'yxatlari — **cursor-based** (`fastapi-pagination`'ning `CursorPage`, UUIDv7 `id` bo'yicha — vaqt tartibi tabiiy keladi): `?cursor=...&limit=50`. Ma'lumotnoma ro'yxatlari (katalog, kontragent) — `Page` (page/size + `total`), chunki UI'da sahifalash ko'rsatiladi |
| Filtrlash | `fastapi-filter` — SQLAlchemy modeliga bog'langan deklarativ filtr sinfi (`?status=posted&doc_date__gte=2026-10-01`), qo'lda `if`/`WHERE` zanjiri yozilmaydi |
| Xato formati | `{"code": "DEBT_LIMIT_EXCEEDED", "message_key": "errors.debt_limit_exceeded", "details": {...}}` — `code` barqaror mashina kaliti, `message_key` frontend i18next kaliti (`08-frontend-arxitekturasi.md`, "xato backend kodidan i18n kalitiga tarjima qilinadi"), `details` — maydon darajasidagi xabarlar (422'da react-hook-form/zod bilan bir xil shaklda: `{"field": "qty", "message_key": "..."}` ro'yxati) |
| Idempotency-Key | Yozuvchi so'rovlarda majburiy (frontend har doim yuboradi). Redis `SETNX idem:{tenant}:{key}` — bir lahzali qulf (parallel takror so'rovni kutish/425); Postgres `idempotency_keys(tenant_id, key UNIQUE, request_hash, response_status, response_body, created_at)` — **doimiy** javob jurnali, qayta so'rov bo'lsa saqlangan javob qaytariladi (qayta bajarilmaydi). Offline kassa qayta yuborganda `key = client_event_id` |
| Optimistik qulflash | Ma'lumotnomalarda (`products`, `product_prices`, …) `version INT`. `PATCH` so'rovi `version`ni tanada talab qiladi; mos kelmasa `409 {code: VERSION_CONFLICT}`. Hujjatlarda kerak emas — ular `posted`dan keyin umuman o'zgarmaydi (faqat teskari hujjat) |
| OpenAPI teglari | Har modul — bitta tag (`sales`, `returns`, `debts`, …), router `tags=[...]` orqali; `operation_id` qo'lda beriladi (`sales_create`, `sales_list`) — orval generatsiya qilgan funksiya nomi shundan keladi (`08-frontend-arxitekturasi.md`, 3-bo'lim) |
| Davr yopilgan | `409 {code: PERIOD_CLOSED}` — yopilgan davrga yozishga urinish |
| Auth | HttpOnly sessiya cookie (`08-frontend-arxitekturasi.md`), CSRF — `itsdangerous` bilan imzolangan token (double-submit: cookie + `X-CSRF-Token` header), yozuvchi metodlarda tekshiriladi |
| Rate limit | `slowapi` — login va AI endpoint'larda qattiqroq limit (brute-force/AI xarajat nazorati) |

---

## 4. Navbat kutubxonasi: `arq` tanlovi

`00-umumiy-arxitektura.md` ochiq savol 1'ini hal qilish:

| Mezon | `arq` | `dramatiq` | `celery` |
|---|---|---|---|
| Asinxron (async def task) | Tabiiy (asyncio) | Yo'q (sync worker, asyncio uchun alohida event loop kerak) | Qisman (`asgiref`/qo'shimcha sozlash) |
| Broker | Redis (stack'da allaqachon bor) | RabbitMQ/Redis (kengaytma kerak) | RabbitMQ/Redis, lekin og'ir konfiguratsiya |
| Cron | Ichida (`cron_jobs`) | Yo'q (APScheduler qo'shimcha kerak) | `celery beat` — alohida jarayon |
| SQLAlchemy async sessiyasi bilan moslik | To'g'ridan-to'g'ri (bir xil event loop, bir xil `asyncpg` pool) | Noqulay | Noqulay |
| Jamoat hajmi/texnik xizmat | O'rta (FastAPI ekotizimida tanilgan), bitta muallif tomonidan faol qo'llab-quvvatlanadi | O'rta | Katta, lekin ortiqcha murakkablik kichik jamoa uchun |

**Qaror: `arq`.** Butun backend stack asinxron (`FastAPI` + `SQLAlchemy 2 async` + `asyncpg`); `arq` worker'ning o'zi ham asinxron funksiya sifatida ishlaydi — bir xil DB pool, bir xil HTTP klient (`httpx.AsyncClient`) qayta ishlatiladi, ikkinchi concurrency modelini (threads/gevent) o'rganish shart emas. Cron (`workers/cron.py`) — davlat hisobotini kunlik tekshirish, qarz eslatmasi, takrorlanuvchi xarajat eslatmasi, 48/72 soat chegarasi monitoringi — `arq`ning o'z `cron_jobs`i bilan, alohida `scheduler` konteyneri sifatida ishga tushadi (`00-umumiy-arxitektura.md`dagi "Rejalashtiruvchi" komponenti). Kamchilik: `arq`da ishlab chiqaruvchi tomonidan rasmiy "task retry with backoff" UI/monitoring paneli yo'q (Celery Flower kabi) — buning o'rniga `outbox_jobs` jadvali + oddiy ichki admin ro'yxati orqali kuzatiladi (allaqachon ma'lumotlar modelida bor).

---

## 5. Kutubxonalar

| Vazifa | Kutubxona | Nima uchun |
|---|---|---|
| Web freymvork | **FastAPI** | Qaror qilingan stack; OpenAPI avtomatik, Pydantic bilan tabiiy integratsiya |
| Validatsiya/sxema | **Pydantic v2** | FastAPI bilan birga keladi, tez (Rust core), orval uchun to'g'ri OpenAPI sxema chiqaradi |
| Sozlamalar | **pydantic-settings** | Namuna loyihadagi naqsh — `.env` + real env, `env_prefix="ERP_"`, prod-xavfsizlik guard (`model_validator`) |
| ORM | **SQLAlchemy 2 (async) + asyncpg** | Namuna loyihada sinalgan; 2.0 stili (`Mapped[...]`) tip xavfsizligini beradi |
| Migratsiya | **Alembic** (asinxron `env.py`, namunadagidek) | Zero-downtime siyosati (13-bo'lim) uchun standart vosita |
| UUID | **uuid-utils** (Rust bog'lovchi, UUIDv7) | `01-malumotlar-modeli.md` UUIDv7 qarorini qo'lda implementatsiya qilmasdan tez generatsiya qiladi |
| Navbat/worker | **arq** | 4-bo'lim — asinxron stack bilan tabiiy mos |
| Kesh/navbat broker | **redis** (`redis-py` asinxron klient) | arq broker + sessiya/kesh/rate-limit (`00-umumiy-arxitektura.md`) |
| Tashqi HTTP | **httpx** (async) | OFD/e-faktura/Click/Payme/SMS/Telegram/Claude API — bitta klient, async |
| Qayta urinish | **tenacity** | Har integratsiya adapterida exponential backoff + jitter — qo'lda `for`/`sleep` yozilmaydi |
| Pagination | **fastapi-pagination** | Cursor va page/size — qo'lda offset/limit hisoblanmaydi (3-bo'lim) |
| Filtrlash | **fastapi-filter** | Deklarativ query filtr, SQLAlchemy modeliga bog'langan |
| Logging | **structlog** | JSON struktura log, tenant/so'rov ID context — namuna loyihadagi JSONL log yondashuvi |
| Trace | **OpenTelemetry** (FastAPI + SQLAlchemy instrumentatsiyasi) | So'rov → posting → worker zanjirini kuzatish |
| Metrika | **prometheus-client** | `/metrics`; posting latensiyasi, navbat chuqurligi, AI xarajati |
| Xato kuzatish | **sentry-sdk** | FastAPI/Starlette integratsiyasi tayyor |
| Parol/PIN hash | **passlib[argon2]** (argon2-cffi) | Argon2 — zamonaviy standart, OWASP tavsiyasi |
| CSRF | **itsdangerous** | Django/Flask'da sinalgan imzolash primitiv; cookie-based sessiyada double-submit token uchun yetarli, `fastapi-csrf-protect`ka nisbatan ko'proq qo'llab-quvvatlanadi |
| Rate limit | **slowapi** | `limits` kutubxonasini o'raydi, Redis backend, FastAPI dependency sifatida |
| Fayl yuklash | **python-multipart** | FastAPI'ga fayl/forma qabul qilish uchun shart (xarajat cheki fotosi, Excel import) |
| S3 | **aioboto3** | Async stack bilan bir xil event loop (sync `boto3` emas) |
| Excel | **openpyxl** | Boshlang'ich katalog/qoldiq/qarz importi (US-M04-04, US-M08-07), hisobot eksporti (M12) |
| Shtrix-kod/yorliq | **python-barcode** (EAN-13, ichki kod) + **treepoem** (Ghostscript orqali DataMatrix/boshqa format — markirovka kodini yorliqda chop etish uchun rasmga aylantirish) | Ikkisi birga MVP kerak bo'lgan barcha format turini qamrab oladi |
| Telegram bot | **aiogram** | Asinxron, FastAPI bilan bir xil stack; `00-umumiy-arxitektura.md`da allaqachon tanlangan |
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
| RLS izolyatsiya | `testcontainers[postgres]` | Ikki tenant yaratiladi, `tenant_id=A` kontekstida yozilgan qator `tenant_id=B` kontekstidan **ko'rinmasligi** tasdiqlanadi (RLS siyosati + `SET LOCAL` ikkisi birga); RLS siyosati ataylab o'chirilgan holat ham testlanadi (kod xatosi RLS'siz ham xavfsiz qolishini tekshirish uchun — ikkinchi himoya qatlami, Asosiy xulosa 4) |
| Kontrakt | `schemathesis` | Ishga tushirilgan API'ning `/openapi.json`'idan avtomatik so'rov generatsiyasi — frontend orval generatsiyasi bilan backend sxemasi mos kelishini kafolatlaydi (CI'da `api:gen` tekshiruvi bilan birga) |
| E2E (tanlab) | `httpx.AsyncClient` + `pytest-asyncio` | Bitta hujjat oqimi boshidan oxirigacha: sotuv → qaytarish → buxgalteriya yozuvi → hisobot |

---

## 7. CI, lokal dev, konfiguratsiya

### 7.1. CI quvuri (taklif — CI vositasi tanlovi ochiq savol)

1. `ruff check` + `ruff format --check`, `mypy app`.
2. `pytest` (bitlik, `testcontainers` servis sifatida CI runner'ida).
3. Alembic: `alembic upgrade head` bo'sh bazada — migratsiya ishlayotganini tekshirish.
4. `schemathesis run` — ishga tushirilgan API'ga qarshi.
5. `openapi.json` eksport + frontend CI'dagi `api:gen --check` bilan taqqoslash (sxema drift bo'lsa — build muvaffaqiyatsiz, `00-umumiy-arxitektura.md` 3-bo'lim).
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
  worker:     # arq app.workers.worker_settings.WorkerSettings
  scheduler:  # arq --watch yoki cron rejimi
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

Sirlar (DB parol, Redis parol, Click/Payme kalitlari, Claude API kaliti, SMS/Telegram token) — kod/`.env`da emas, UzCloud sir-ombori yoki muhit o'zgaruvchisi orqali (`00-umumiy-arxitektura.md`, 3-bo'lim muhitlar jadvali: local — `fake/cli`, staging/prod — `api`, alohida kalitlar).

---

## 8. Observability

- **Logging**: `structlog`, JSON format, har yozuvda `tenant_id`, `request_id`, `user_id`; shaxsiy ma'lumot (telefon, STIR) log'ga tushmasligi uchun redaction filtri (namuna loyihadagi `RedactingFilter` naqshi).
- **Readiness/liveness**: `/health/live` (jarayon ishlayaptimi) va `/health/ready` — namuna loyihadagi **gating vs reported** bo'linishi: *gating* (API 200 bermasa stack buziladi) = Postgres round-trip + Alembic sxema versiyasi (`db_create_all=false` muhitlarda) + Redis; *reported* (faqat ma'lumot, bloklamaydi) = OFD/e-faktura/Claude API/S3 reachability — mijoz tomondagi tashqi tizim uzilishi deploy/health'ni bloklamasligi kerak.
- **Metrika**: `prometheus-client` — HTTP latensiya, posting tranzaksiya davomiyligi, `outbox_jobs` navbat chuqurligi/urinish soni, AI so'rov narxi (`ai_requests.cost_usd` yig'indisi).
- **Trace**: OpenTelemetry, FastAPI+SQLAlchemy+httpx avtomatik instrumentatsiya; eksport nuqtasi (Grafana Tempo/Jaeger, UzCloud'da qaysi xizmat) — ochiq savol.
- **Xato kuzatish**: `sentry-sdk`, tenant/branch context tag sifatida (lekin mijoz PII'siz).

---

## 9. Deploy

Konteynerlar (`00-umumiy-arxitektura.md`, 3-bo'lim bilan mos): **api**, **worker**, **scheduler**, **bot**, (frontend alohida `web` — statik, `08-frontend-arxitekturasi.md`).

Namuna loyihadan **ko'chiriladi**: ko'p bosqichli `Dockerfile` (uv bilan bog'liqliklarni qulflangan holda o'rnatish, non-root `app` user, `HEALTHCHECK`), Alembic'ning bir martalik `migrate` konteyneri (api/worker undan keyin boshlanadi, `db_create_all=false` har joyda konteyner stack'da).

Namuna loyihadan **farqlanadi** (chunki u — bitta tenant/bitta stack, bu loyiha — ko'p tenant/bitta umumiy stack):

| Jihat | Namuna loyiha | Bu loyiha |
|---|---|---|
| Stack soni | Har mijoz uchun alohida (`aios-<tenant>`) | Bitta umumiy stack, tenant — RLS bilan ma'lumotlar darajasida |
| `api`/`worker` | Bitta nusxa | **Gorizontal ko'payadi** (holat yo'q — sessiya Redis'da, tranzaksiya DB'da) |
| `scheduler` | Bitta nusxa, muammosiz | **Yagona nusxa bo'lishi shart** (cron ikki marta ishlamasligi uchun) — Postgres advisory lock (`pg_try_advisory_lock`) bilan yetakchi tanlanadi, bir nechta `scheduler` konteyneri ishga tushsa ham faqat biri faol bo'ladi |
| Baza | Konteynerdagi Postgres | **UzCloud boshqariladigan DBaaS** (managed Postgres) — konteyner emas |
| Fayl ombori | Yo'q | S3-mos ombor (UzCloud'da mavjudligi — `00-umumiy-arxitektura.md` ochiq savol 2) |

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

- **Rollar**: 5 standart (`owner`, `manager`, `cashier`, `storekeeper`, `accountant`) — `is_system=true`, `role_permissions` bilan boshlang'ich huquq to'plami (`01-malumotlar-modeli.md`, 3-bo'lim; to'liq ro'yxat `05-xavfsizlik-va-audit.md`da).
- **Birliklar** (`units`): `pcs`, `kg`, `l`, `m`, `box` — global, `is_fractional` belgisi bilan.
- **Xarajat toifalari** (`expense_categories`): Ijara, Kommunal, Ish haqi, Transport, Soliq va yig'imlar, Ta'mirlash, Boshqa (M15, US-M15-01 — standart ro'yxat, tenant o'zgartira oladi).
- **Tariflar** (`plans`): Start / Biznes / Pro — `limits` JSONB (`max_registers`, `max_branches`, `ai_monthly_tokens`), aniq raqamlar `06-mvp-chegarasi.md`dan (bu hujjatda takrorlanmaydi).
- **Ruxsatlar katalogi** (`permissions`, jadval emas — kod ichida ro'yxat, `access` modulida) — kod deploy bilan birga keladi, seed kerak emas.

Seed — Alembic "data migration" emas (bazani versiyalash bilan aralashtirmaslik uchun), alohida bosqich sifatida `migrate` konteyneridan keyin, birinchi deploy'da bir marta ishga tushadi.

---

## Ochiq savollar

1. **DI yondashuvi**: namuna loyihadagidek oddiy factory-funksiya + `Depends` (5-bo'limdagi tanlov) yetarlimi, yoki `dependency-injector` paketi (deklarativ `Container`) qo'shilsinmi — jamoa bilan tasdiqlanishi kerak.
2. **CI vositasi**: quvur bosqichlari (7.1-band) tasdiqlangan, lekin aniq platforma (GitHub Actions/GitLab CI/boshqa) — ochiq.
3. **OpenTelemetry eksport nuqtasi**: UzCloud'da Grafana Tempo/Jaeger kabi xizmat bormi — tekshirish kerak (`00-umumiy-arxitektura.md` ochiq savol 2 bilan bog'liq, S3-mos ombor savoli ham hali ochiq).
4. **`scheduler`ning yagona nusxa kafolati**: Postgres advisory lock taklif qilindi (9-bo'lim) — Redis-based lock (`redis-py` + `SET NX` TTL bilan) muqobil variant, ikkisidan biri tasdiqlanishi kerak.
5. **CSRF kutubxonasi**: `itsdangerous` tanlandi (xavfsizlik jamoasi/`05-xavfsizlik-va-audit.md` bilan yakuniy tasdiq kerak — ayniqsa Telegram bot va mobil (keyingi Android) klient uchun cookie-based CSRF qanday ishlashi).
6. **Aniq ruxsat kodlari ro'yxati** (`permissions`) va **NSBU №21 hisob raqamlari** (`ledger_entries.account_dt/kt`) — bu hujjatda ataylab keltirilmadi, `05-xavfsizlik-va-audit.md` va `02-provodka-qoidalari.md`da (buxgalter tasdig'i shart) aniqlanadi.
7. **`recost_jobs` va davr yopish orasidagi aniq biznes qoida** (kim davrni qayta ocha oladi, qanday audit bilan) — `02-provodka-qoidalari.md`da batafsil.

## Manbalar

- `spec/02-arxitektura/00-umumiy-arxitektura.md` — komponentlar, muhitlar, navbat ochiq savoli.
- `spec/02-arxitektura/01-malumotlar-modeli.md` — jadvallar, registrlar, holat mashinalari, raqamlash.
- `spec/02-arxitektura/08-frontend-arxitekturasi.md` — API konventsiyalari (cookie/CSRF, Idempotency-Key, X-Branch-Id, xato formati, orval).
- `spec/01-mahsulot/02-modullar-talablari.md` — M01–M18 foydalanuvchi hikoyalari va chekka holatlar.
- `E:/Project/universal_ai_platform/src/backend` — qatlamli tuzilma, `pydantic-settings`/DI/Alembic/health/Dockerfile naqshlari (struktura namunasi, kod emas — `spec/README.md` qoidasiga mos, O'zbekiston-specific qiymat olinmagan).

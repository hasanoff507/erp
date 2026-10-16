# Backend arxitekturasi

**Maqsad:** Backend repozitoriy tuzilishi, posting naqshi, API konventsiyalari, navbat kutubxonasi, kutubxona tanlovlari, test strategiyasi va deploy modelini belgilash.
**Kim uchun:** Backend ishlab chiquvchi, arxitektor.
**Bog'liq fayllar:** `10-umumiy-arxitektura.md`, `11-malumotlar-modeli.md`, `24-frontend-arxitekturasi.md`, `03-modullar-talablari.md`, `14-autentifikatsiya-oauth2.md`, `13-provodka-qoidalari.md` (§2.18a), `15-xavfsizlik-va-audit.md` (§4, §7), `21-integratsiyalar.md` (§1 fiskal, §9.4 karta terminali, §16 Do'kon agenti), `33-1c-integratsiya.md`, `34-1c-agent.md`, `01-qarorlar.md` #51, #57, #60, #65, #71.
**Holat:** joriy, 2026-10-16.

## Asosiy xulosalar

1. **Modulli monolit**: `backend/app/modules/<modul>/` — 20 modul papkasi (18 mahsulot moduliga + kesishuvchi `integrations`/`sync`/`ai` + Bosqich 7 dagi M19 `onec_integration` ga mos), har biri bir xil ichki qatlam: `domain/` → `application/` → `infrastructure/` → `api/`. Umumiy infratuzilma — `app/core` (DB sessiya + tenant kontekst, auth, huquq dependency, idempotentlik, xatolar, sozlamalar, logging) va `app/workers` (navbat ishlari, cron).
2. **"Posting service" naqshi** — har bir hujjat turi uchun bitta xizmat, bitta DB tranzaksiyada hujjat holatini **va** barcha registrlarni (`stock_moves`/`stock_lots`, `debt_moves`, `cash_moves`, `ledger_entries`, `vat_moves`) birga yozadi; bekor qilish — faqat teskari yozuv, `UPDATE`/`DELETE` yo'q.
3. **Navbat kutubxonasi — `SAQ`** (4-bo'lim): asyncio, Redis broker (stack'da bor), ichki `CronJob`, o'rnatilgan monitoring UI. `arq` 2025-10 dan beri faqat texnik xizmat rejimida (python-arq/arq#510) — yangi loyiha uchun tanlanmaydi.
4. **Tenant izolyatsiyasi kod darajasida ikki marta**: (a) ilova qatlami — `TenantMixin` modellariga SQLAlchemy `with_loader_criteria` orqali global `tenant_id` filtri; (b) PostgreSQL RLS (`set_config('app.tenant_id', …, true)` + siyosat, `15-xavfsizlik-va-audit.md`) — (b) (a) buzilsa ham himoya qiladi va aksincha (09 §6 RLS-o'chirilgan testi shu (a)ni tekshiradi).
5. **Kutubxona birinchi, qo'lda kod oxirgi**: pagination — `fastapi-pagination`, filtrlash — `fastapi-filter`, retry — `tenacity`, UUIDv7 — `uuid-utils`, muddat arifmetikasi (5 ish kuni, 48 soat, markirovka qabul muddati, qarz eskirish guruhlari) — `pendulum` + bayramlar ro'yxati, Excel — `openpyxl`, shtrix-kod/yorliq — `python-barcode` + `zxing-cpp` (Ghostscript/AGPL'siz). To'liq jadval 5-bo'limda.
6. **AI — port naqshi** (`AiProvider`; `22-ai-qatlami.md` §1, qaror #16): `fake` (test) | `cli` (lokal dev, Claude Code CLI) | `api` (staging/prod, `anthropic` SDK) — bitta portga qarab rejim almashtiriladi, faqat `cli` o'rniga prodda `api`.
7. **Standart naqshlar**: qatlamli papka tuzilmasi, `pydantic-settings` + `lru_cache get_settings()` + prod-da xavfsizlik guard (`model_validator` — auth yoqilmagan/standart sir/sqlite bo'lsa ishga tushmaydi), composition-root'dagi `_build_*` factory funksiyalar, Alembic'ning asinxron `env.py`'si, `ReadinessProbe`'ning "gating vs reported" bo'linishi, ko'p bosqichli Dockerfile (non-root user, `HEALTHCHECK`).
8. **Deploy modeli**: bitta umumiy stack, ko'p tenant, RLS bilan: `api`/`worker` gorizontal ko'payadi, `scheduler` yagona nusxa bo'lishi kerak (Postgres advisory lock bilan) (adapterlar: OFD/e-faktura/Asl belgisi/Click-Payme adapterlari).
9. API — `/api/v1`, URL yo'li kebab-case ko'plik, JSON/query/enum/`operation_id` — snake_case (3-bo'lim, `01-qarorlar.md` #24); xato formati `{"error": {code, message_key, params, details[], request_id}}` (frontenddagi zod/i18next bilan bir xil shakl, `details` har doim massiv), `Idempotency-Key` Redis tezkor qulf + Postgres doimiy jurnal bilan, optimistik qulflash `version` maydoni orqali (faqat ma'lumotnomalarda — hujjatlarda yo'q).
10. Test strategiyasi — bitlik testlar provodka qoidalari uchun sonli misollar bilan, `testcontainers` orqali haqiqiy Postgres'da integratsiya va RLS izolyatsiya testlari, `schemathesis` OpenAPI'dan kontrakt testlari.
11. **Autentifikatsiya — o'z OAuth 2.0 AS+RS implementatsiyasi** (`app/modules/auth/`): protokol skeleti **Authlib** (RFC 6749/7636/7009/7662/8414/9068), JWT/JWKS — **joserfc**, parol/PIN — **argon2-cffi (argon2id)**; barcha storage/rotatsiya/obuna-tekshiruv mantiqi bizning kod. To'liq dizayn — `14-autentifikatsiya-oauth2.md`.
12. **1C integratsiyasi — alohida modul `onec_integration`** (M19, Bosqich 7, qaror #36–#42): boshqa modullar uni faqat `OneCChangeTracker` porti orqali chaqiradi (tenantda faol 1C bazasi bo'lmasa no-op), u esa boshqa modullarning faqat o'qish portlarini (`SalesExportPort`, `CashExportPort`, …) chaqiradi. Agentga ish `outbox_jobs` orqali emas — imzolangan `onec_agent_tasks` navbati, agent uni `/api/v1/onec-agent/*` dan long-poll bilan tortadi (pull). To'liq dizayn — `33-1c-integratsiya.md` §3–§4.
13. **Do'kon agenti — backend tomoni (qaror #60, 4.2-bo'lim)**: fiskal ko'prik, xom TCP 9100 printer, tarozi va karta terminali uchun alohida agent API yo'q — `33-1c-integratsiya.md` §9 dagi **bir xil** agent identifikatsiyasi va autentifikatsiyasi (OAuth mijozi `onec-agent`, device grant + `private_key_jwt`, 10 daqiqalik token) va bir xil yo'llar `/api/v1/onec-agent/*` ishlatiladi; vazifalar oq ro'yxatiga **Bosqich 5 kengaytmasi** sifatida `fiscal.*`, `print.*`, `scale.*`, `card.*` turlari qo'shiladi (`base_id = null`). Agent ro'yxati va vazifa navbati `onec_integration` modulida qoladi, boshqa modullar unga `AgentTaskPort` orqali vazifa qo'yadi.
14. **Fiskal kod alohida paket** (`app/modules/integrations/fiscal/`): fiskal qism o'zgarsa operator va Kiberxavfsizlik markazidan qayta xulosa kerak (VMQ-943 2-ilova 6-band) — paket kam o'zgaradi, o'z versiyasi va o'z testlari bilan; boshqa modullar unga faqat `FiscalPort` orqali murojaat qiladi.
15. **Sirlar va zaxira (qaror #51, #65)**: UzCloud'da KMS/sir ombori yo'q — deploy sirlari SOPS/age bilan shifrlangan fayldan muhit o'zgaruvchisiga; tenant sirlari ilova darajasida envelope shifrlash (KEK — deploy siri); PostgreSQL PITR — o'z WAL arxivi (pgBackRest/WAL-G → UzCloud S3), RPO ≤ 5 daqiqa, RTO ≤ 4 soat; nusxa boshqa provayderda ham (7.3, 9-bo'lim).
16. **Karta terminali — alohida paket** (`app/modules/integrations/card_terminal/`, qaror #71): `CardTerminalPort` kontrakti (Pydantic DTO'lari — `CardPurchaseRequest`, `CardTxResult`, `SettlementResult`, `TerminalHealth`; veb-kassa TS tiplari va agent C# DTO'lari shu sxemadan eksport qilinadi), adapterlar `fake` va `cloud` (vendor bulut API bo'lsa), `card_terminal_transactions` yozuvchisi (`sale.created` `payments[].card_result`, `return.created` `refund_card.card_result`, `debt_payment.created` `card_result` dan, online'da `POST /card-terminal-transactions`) va `card.status`/`card.settlement` agent vazifalari. Sotuv paytidagi `purchase` server orqali o'tmaydi — POS agentning lokal API'sini chaqiradi (`21` §9.4, §16). `sales`/`returns`/`debts`/`cash` modullari unga faqat port orqali murojaat qiladi.

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
│   │   ├── access/                   # M13 rol/ruxsat katalogi, role_permissions (foydalanuvchi CRUD'i — `auth/`da)
│   │   ├── branches/                 # M14 filial, ombor, kassa apparati, qurilma ro'yxati
│   │   ├── expenses/                 # M15 xarajat, toifa, takrorlanuvchi xarajat
│   │   ├── cash/                     # M16 kassa naqd pul harakati, smena sanash; bank tushumi tasdig'i `bank_settlements` (5710 → 5110, BankSettlementPostingService, `/bank-settlements`, BO-24 — `13-provodka-qoidalari.md` §2.18a, qaror #42)
│   │   ├── billing/                  # M17 tarif, obuna, to'lov (Click/Payme), platforma admin
│   │   ├── notifications/            # M18 bildirishnoma, Telegram bot (aiogram), SMS
│   │   ├── integrations/             # e-faktura/e-TTN/e-ishonchnoma (EInvoicePort), Asl belgisi (MarkingPort), E-IMZO, to'lovlar (PaymentPort, UzqrPort), OtpPort — har biri adapter
│   │   │   ├── fiscal/               # FiscalPort adapterlari (fake, partner_cloud; lokal ko'prik natijasini qabul qilish) — alohida, kam o'zgaradigan paket (qayta xulosa talabi, `21` §1)
│   │   │   └── card_terminal/        # CardTerminalPort (qaror #71): DTO/sxema, adapterlar fake + cloud (vendor bersa), card_terminal_transactions/settlements yozuvchisi, card.* agent vazifalari, card_bin_rules qidiruvi — `21` §9.4
│   │   ├── ai/                       # AiProvider porti, AI-xx funksiyalar, ai_requests/feedback
│   │   ├── onec_integration/         # M19: Do'kon agentlari ro'yxati, imzolangan vazifalar navbati (AgentTaskPort — fiscal.*/print.*/scale.*/card.*, Bosqich 5) va 1C qismi (bazalar, moslashtirish, kunlik partiyalar, Bosqich 7); router_web (/onec-*) + router_agent (/onec-agent/*) — ichki tuzilma `33-1c-integratsiya.md` §4.1
│   │   └── sync/                     # offline outbox qabul qilish, client_event_id dedupe, qurilma holati
│   └── workers/
│       ├── jobs/                      # SAQ task funksiyalari (bitta modulga tegishli bo'lsa ham shu yerda
│       │                               # ro'yxatga olinadi — modul papkasidagi `tasks.py` dan import qilib)
│       ├── cron.py                    # SAQ CronJob ro'yxati (davlat hisoboti eslatmasi, qarz eslatmasi, recost, kam qoldiq, yaroqlilik muddati, obuna eslatmasi, kunlik Telegram hisobot, fiskal 24/40/46/48 soat monitoringi, CBU kursi; Bosqich 7 — 5 ta `onec_*` cron, §4.1)
│       └── worker_settings.py         # SAQ worker sozlamalari (navbatlar, concurrency, Sentry/OTel init)
├── alembic/
│   ├── env.py                         # asinxron; har upgrade'dan keyin GRANT SELECT ON public.alembic_version TO erp_app (`12-db-sxema.md` §4.4)
│   ├── versions/                      # 0001…0027 — har biri alembic/sql/ dagi SQL faylni bajaradi
│   └── sql/                           # NNNN_<nom>.{up,down}.sql — scripts/gen_migration_sql.py 12-db-sxema.md DDL'idan generatsiya qiladi
├── docker/
│   └── postgres/initdb.sh             # DBA bootstrap (`12-db-sxema.md` §0): rollar, parollar, GRANT erp_system TO erp_migrator, baza
├── tests/
├── scripts/                           # seed.py (typer CLI), gen_migration_sql.py, ddl_from_spec.py, gen_error_codes.py va h.k.
├── docker-compose.yml                 # lokal dev stack (7.2-bo'lim)
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

**Qatlamlar orasidagi qoida** (`domain|application|infrastructure|interface` bo'linishi, FSD'dagi "faqat pastga import" qoidasiga o'xshash): `api → application → domain`; `infrastructure` faqat `domain`dagi portlarni amalga oshiradi, `application` uni interfeys orqali ko'radi (dependency inversion — DI composition root `app/main.py` + modul-ichidagi kichik `wiring.py` bog'laydi). Modullar bir-birining `infrastructure`/`api` qatlamini **import qilmaydi** — faqat boshqa modulning `application`/`domain` portini (masalan `sales` moduli `inventory.application.ports.StockPort`ni chaqiradi, `inventory.infrastructure`ni emas). Bu modulli monolitni keyin mikroservisga ajratishni osonlashtiradi (`10-umumiy-arxitektura.md`, 1-xulosa).

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

Har bir hujjat turi (`sales`, `returns`, `goods_receipts`, `transfers`, `stock_counts`, `write_offs`, `debt_payments`, `expenses`, `cash_movements`, `bank_settlements`, …) uchun **bitta** `*PostingService`, umumiy protokolga mos:

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
4a. Tenantda faol 1C bazasi bo'lsa — **shu tranzaksiyada** `OneCChangeTracker.touch(tenant_id, branch_id, doc_type, doc_id, doc_date)` (bitta indeksli `UPDATE`; post va cancel'da ham) — allaqachon 1C'ga yuborilgan kun uchun kech ma'lumot belgisi (`33-1c-integratsiya.md` §8.6). Baza bo'lmasa no-op.
5. Tranzaksiya commit bo'lgach (`after_commit` hook), tashqi integratsiya ishlarini **navbatga** qo'yadi (`outbox_jobs` qatori + `JobQueue.enqueue(...)`, SAQ ortida, 4-bo'lim) — OFD'ga yuborish (faqat hamkor bulut rejimida; lokal ko'prik rejimida chek POS'da FM orqali allaqachon fiskallashtirilgan, `21` §1), e-faktura, Telegram xabar. **Hech qachon tashqi tizim tranzaksiya ichida chaqirilmaydi** (`10-umumiy-arxitektura.md`, 7-xulosa: API tashqi tizimni kutib turmaydi).

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

`reverse()` yangi hujjat yaratmaydi — original hujjat `cancelled` bo'ladi (`cancelled_at`, `cancelled_by`, `cancel_reason`) va **har bir yozilgan registr qatoriga teskari qator** qo'shiladi: `ledger_entries` — Dt/Kt o'rni almashtiriladi, `amount` musbat; `stock_moves`/`debt_moves`/`cash_moves`/`vat_moves` — teskari ishora (`13-provodka-qoidalari.md` §5.2). `doc_type`/`doc_id` — original hujjat, `reversal_of_id` — teskari qilinayotgan asl registr qatori, sana — joriy ochiq davr; hech qachon `UPDATE`. `stock_lots.qty_left` `lot_allocations` bo'yicha teskari tartibda qaytariladi (2.1 qulfi ostida).

### 2.4. Recost ishlari va davr yopish

- **Recost** (`recost_jobs`, `11-malumotlar-modeli.md` 10-bo'lim): o'tgan sanali hujjat (kech sinxron, kech kirim) kelganda navbatga qo'yiladi (SAQ job `recost_product`); job shu sanadan keyingi barcha chiqimlarni `ORDER BY moved_at, created_at, id` tartibida **FIFO/AVECO bo'yicha qayta hisoblaydi**; tegishli `ledger_entries` (9120/inv_acct) uchun eski qator storno (`reversal_of_id`) + yangi qator yoziladi (asl yozuv o'zgartirilmaydi — append-only): `doc_type`/`doc_id` = asl chiqim hujjati, `analytics.recost_job_id`, `entry_date` = asl sana (davr ochiq bo'lsa). Yopilgan davrga tegsa — yopilgan davr yozuvlari o'zgarmaydi, farq joriy ochiq davrda tuzatuvchi yozuv bilan (`analytics.correction_of_period`) (`13-provodka-qoidalari.md` §3.3, §3.4). Job `queued → running → done/failed`. Job 2.1 dagi `stock_balances` qulfini oladi.
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
    PS->>Q: enqueue "ofd_send" (faqat hamkor bulut rejimi), "einvoice_send" (agar kerak bo'lsa)
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
| Idempotency-Key | Yozuvchi (`POST`/`PUT`/`PATCH`/`DELETE`) back-office so'rovlarida majburiy (frontend har doim yuboradi); `/sync/push` (dedupe har voqea bo'yicha `sync_receipts.client_event_id`, `16-offline-sync.md` §3.1) va `/onec-agent/*` (`lease_id`/`client_log_id`) mustasno. **Joyi**: `app/core/idempotency.py` — ASGI middleware, route dependency'laridan (CSRF, auth, ruxsat) **oldin** ishlaydi. Tenant'ni auth qatlami beradigan `resolve_tenant` hook'i aniqlaydi (sessiya cookie'si/Bearer token — imzo va `sid`-revoke tekshiruvi bilan, `14-autentifikatsiya-oauth2.md` §5; so'rov tanasidan hech qachon); tenant aniqlanmasa (autentifikatsiyasiz so'rov) middleware so'rovni o'zgarishsiz o'tkazadi — uni keyingi auth bosqichi rad etadi. **Kalit**: yo'q yoki 200 belgidan uzun → `422 VALIDATION_ERROR`, `details=[{"field": "Idempotency-Key", "message_key": "validation.required"}]` (uzun bo'lsa `validation.max_length`). **Oqim**: (1) `idempotency_keys`da `(tenant_id, key)` bor bo'lsa — `request_hash` (metod + yo'l + query + tana, SHA-256) mos kelsa saqlangan javob `Idempotent-Replayed: true` sarlavhasi bilan qaytariladi (qayta bajarilmaydi), mos kelmasa `422 {code: IDEMPOTENCY_KEY_REUSED}`; (2) aks holda Redis `SET NX idem:{tenant}:{key}` qulfi (TTL `ERP_IDEMPOTENCY_LOCK_TTL_S`, standart 60 s) — olinmasa `409 {code: IDEMPOTENCY_IN_PROGRESS}` + `Retry-After: 1`; (3) qulf olingach jurnal yana bir bor tekshiriladi, keyin handler ishlaydi; qulf javobdan keyin bo'shatiladi. **Saqlash**: faqat `2xx` javob saqlanadi; `4xx`/`5xx` saqlanmaydi (xato biznes tranzaksiyasini rollback qilgan — xuddi shu kalit bilan qayta urinish qaytadan bajariladi). Jurnal qatori biznes o'zgarishi bilan **bitta `tenant_transaction` ichida, COMMIT'dan oldin** yoziladi: middleware kalit va `request_hash`ni so'rov kontekstiga (contextvar) qo'yadi, route o'z `tenant_transaction`i (yoki `TenantSession`) ichida `stage_response(body, status)` ni chaqiradi (qaytaradigan javobning o'zi), `tenant_transaction` esa chiqishda — COMMIT'dan oldin — `idempotency_keys` qatorini o'sha tranzaksiyada `INSERT` qiladi (javob aynan shu tranzaksiyaga bog'lanadi; ichma-ich ochilgan boshqa tranzaksiya, masalan audit, uni yozmaydi). Shu bilan "biznes yozuvi bor, jurnal yo'q" holati bo'lmaydi: jarayon COMMIT'dan keyin, javob yuborilmasdan qulasa ham qayta so'rov saqlangan javobni oladi. `PRIMARY KEY (tenant_id, key)` — oxirgi himoya: qulf TTL'i tugab ikkinchi nusxa ham handler'ga yetsa, uning `INSERT`i to'qnashadi, butun tranzaksiyasi rollback bo'ladi va u saqlangan javobni qaytaradi. DB'ga biznes yozuvi qilmaydigan yozuvchi endpoint jurnal qatorini o'zining qisqa `tenant_transaction`ida yozadi. **Jurnal**: Postgres `idempotency_keys(tenant_id, key, request_hash, response_status, response_body, created_at, PRIMARY KEY (tenant_id, key))` — doimiy javob jurnali, `ERP_IDEMPOTENCY_RETENTION_DAYS` (standart 30) kundan keyin tozalanadi, buxgalteriya yozuvi emas. `Idempotency-Key` faqat back-office REST yozuvchi so'rovlariga tegishli. |
| Optimistik qulflash | Ma'lumotnomalarda (`products`, `product_prices`, …) `version INT`. `PATCH` so'rovi `version`ni tanada talab qiladi; mos kelmasa `409 {code: VERSION_CONFLICT}`. Hujjatlarda kerak emas — ular `posted`dan keyin umuman o'zgarmaydi (faqat `cancel` + storno registr qatorlari, `reversal_of_id`; alohida teskari hujjat yo'q — `01-qarorlar.md` #6). Hujjat javoblarida `version` maydoni **yo'q**; `draft`ni `PATCH` qilish — butun qoralamani almashtiradi (`17-api-umumiy.md` §8) |
| OpenAPI teglari | Har modul — bitta tag (`sales`, `returns`, `debts`, …), router `tags=[...]` orqali; `operation_id` qo'lda beriladi (`sales_create`, `sales_list`) — orval generatsiya qilgan funksiya nomi shundan keladi (`24-frontend-arxitekturasi.md`, 3-bo'lim) |
| Davr yopilgan | `409 {code: PERIOD_CLOSED}` — yopilgan davrga yozishga urinish |
| Auth | **OAuth 2.0 (AS+RS, `app/modules/auth/`)** — to'liq dizayn `14-autentifikatsiya-oauth2.md`da. Veb: BFF, HttpOnly/Secure/SameSite=Lax sessiya cookie (OAuth token brauzerga chiqmaydi); Android: to'g'ridan-to'g'ri `Authorization: Bearer <access_token>`. CSRF — o'zgarmagan: sessiya ID'ga bog'langan, `itsdangerous` bilan imzolangan token (`GET /api/v1/auth/csrf` → `X-CSRF-Token`), CSRF cookie yo'q. Noto'g'ri/eskirgan token → `403 {code: CSRF_INVALID}`. Bearer access token (Android) CSRF tekshiruvidan ozod. Har so'rovda qo'shimcha `require_subscription_ok` dependency (Redis-kesh) — `403 {code: SUBSCRIPTION_RESTRICTED}`. |
| 1C agent API | `/api/v1/onec-agent/*` — foydalanuvchi sessiyasi emas: `Authorization: Bearer` (OAuth mijozi `onec-agent`, `client_credentials` + `private_key_jwt`, `aud=urn:erp:onec-agent`, scope `onec.agent`; `14-autentifikatsiya-oauth2.md`), CSRF'dan ozod. Dependency `onec_integration/api/deps.py`: `current_agent()` (token → `tenant_id`, `agent_id`; agent `status` Redis keshi 60 s, revoke darhol), `require_agent_base(base_id)` (baza shu agentga tegishli), `require_onec_enabled()`. Bu yo'llarda `require_permission` yo'q (agent foydalanuvchi emas); so'rov tanasidagi tenant e'tiborga olinmaydi. Obuna lokautida yangi vazifa berilmaydi. Batafsil — `33-1c-integratsiya.md` §9. Do'kon agentining `fiscal.*`/`print.*`/`scale.*` vazifalari (4.2-bo'lim) xuddi shu yo'llar va token bilan; `require_onec_enabled()` faqat 1C turlariga (`base_id` bor) qo'llanadi, qolganlariga — `require_agent_capability(kind)` (agent sozlamasida imkoniyat yoqilgan) |
| Rate limit | Redis fixed-window hisoblagichlari (`app/core/ratelimit.py`, 5-bo'lim) — login, OTP, `/oauth/token` va AI endpoint'larda (brute-force/AI xarajat nazorati, `14-autentifikatsiya-oauth2.md` §12) |

**Middleware/dependency tartibi** (har himoyalangan so'rovda, tashqaridan ichkariga): (0) so'rov konteksti (`request_id`, kutilmagan istisno → `500 INTERNAL_ERROR`) → (1) CORS → (1a) `Idempotency-Key` middleware'i (yozuvchi so'rovlarda; tenant — `resolve_tenant` hook'i orqali; takror so'rovga saqlangan javob shu yerda qaytadi — u yangi ta'sir bermaydi, shuning uchun quyidagi tekshiruvlardan oldin turishi xavfsiz) → (2) CSRF tekshiruvi (faqat cookie-autentifikatsiyali so'rovlarda, Bearer'da yo'q) → (3) auth — cookie'dan `sid`/Bearer'dan JWT orqali claims chiqarish, imzoni/`sid`-revoke keshini tekshirish (`14-autentifikatsiya-oauth2.md` §5) → (4) `require_subscription_ok` — Redis `sub_status` keshi (Redis ishlamasa `subscriptions.status` to'g'ridan-to'g'ri DB'dan, fail-to-DB — `14-autentifikatsiya-oauth2.md` §16.1.1, KICHIK 9), `restricted`/`closed` bo'lsa darhol `403` (istisnolar: `/auth/*`, `/billing/pay` (BFF sahifa), **`GET /billing/plan`, `GET /billing/subscription`, `GET /billing/addons`, `POST /billing/checkout`** (restricted holatda oddiy sessiya o'rniga `pay_token` bilan, `14-autentifikatsiya-oauth2.md` §16.1.1a) **, `GET /billing/payments`, `/billing/webhooks/*`** (o'z imzo tekshiruvi bilan, sessiyadan mustaqil), `/billing/export-my-data` (OTP bilan — Telegram birinchi, SMS zaxira, qaror #34; D2), `/sync/push` **faqat `scope=sync.drain`** bilan va faqat lokautdan oldingi voqealar uchun — `14-autentifikatsiya-oauth2.md` §16.1, §16.4; oddiy `reports.export`/eksport bu ro'yxatda **yo'q** — lokautda yopiq, D2 bo'yicha alohida `/billing/export-my-data` yo'li bor) → (5) `current_branch_scope`/`X-Branch-Id` tekshiruvi → (6) `require_permission("<code>")` — `role_permissions`+`limit_value` → (7) `tenant_transaction` ochiladi, biznes kod ishga tushadi, yozuvchi so'rovda `idempotency_keys` qatori shu tranzaksiyada COMMIT'dan oldin yoziladi.

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

Cron (`workers/cron.py`) ro'yxati: davlat hisobotini kunlik tekshirish, qarz eslatmasi, takrorlanuvchi xarajat eslatmasi, **`fiscal_unacked_monitor`** (har 15 daqiqa: `ofd_acked_at IS NULL` bo'lgan eng eski fiskal chek yoshi bo'yicha 24/40/46/48 soat bosqichlari, qaror #43 — 40 soatda Egasiga M18 va `fiscal.resend_unsent` vazifasi), markirovka qabul muddati (`marking_product_groups.acceptance_deadline`), **`fetch_fx_rates`** (har kuni 09:30 Toshkent, CBU kursi → `platform.fx_rates`, qaror #55), **`card_settlement_sweep`** (har kuni 23:30 Toshkent: shu kun settlement'i yo'q faol `card_terminals` uchun `card.settlement` vazifasi, qaror #71), **`card_orphan_sweep`** (har soat: 24 soatdan eski, hujjatga bog'lanmagan `approved` `purchase` — `idx_ctt_orphans` → `sync_exceptions(kind='card_orphan_transaction')`; avtomatik `void` qilinmaydi, qaror #71), **kam qoldiq tekshiruvi** (US-M04-02: `stock_balances.qty <= products.min_stock`, kuniga 1 marta; bir tovar uchun kuniga bitta xabar), **yaroqlilik muddati** (US-M04-06), **obuna eslatmalari va `grace` → `restricted` o'tishi** (US-M17-03), **kunlik Telegram hisobot** (US-M18-02), **`purge_login_attempts`** (har kuni 03:15 Toshkent: `app.auth_purge_login_attempts(make_interval(days => ERP_LOGIN_ATTEMPTS_RETENTION_DAYS))`, standart 90 kun — `12-db-sxema.md` §3, §4.5; Bosqich 0 da quriladi), **`purge_idempotency_keys`** (har kuni 03:30 Toshkent, tenant fan-out: `idempotency_keys.created_at < now() - ERP_IDEMPOTENCY_RETENTION_DAYS`, standart 30 kun — §3; Bosqich 1 da, birinchi yozuvchi endpoint bilan quriladi) — `SAQ`ning o'z `CronJob`i bilan, alohida `scheduler` konteyneri sifatida ishga tushadi (`10-umumiy-arxitektura.md`dagi "Rejalashtiruvchi" komponenti).

### 4.1. 1C integratsiyasi job'lari va cron (Bosqich 7)

`onec_integration/infrastructure/tasks.py` dagi 13 ta SAQ job (har birida birinchi argument `tenant_id`, tana `tenant_transaction` ichida; trigger, argumentlar va idempotentlik — `33-1c-integratsiya.md` §4.4):

| Job | Trigger |
|---|---|
| `onec_on_shift_closed` | `shift.closed` posting'idan keyin |
| `onec_prepare_batch` | qo'lda (W-36), jadval, `on_shift_close`, kech ma'lumot |
| `onec_schedule_tick` | cron `*/5` |
| `onec_lease_sweeper` | cron `*/1` |
| `onec_finalize_batch` | partiyaning barcha itemlari yakunlanganda |
| `onec_verify_batch` | `read_totals` natijasi kelganda |
| `onec_auto_revision` | yakunlangan partiyada `needs_resync=true` |
| `onec_drift_check` | cron `30 6 * * *` (Toshkent) |
| `onec_agent_offline_check` | cron `*/15` |
| `onec_cleanup` | cron `0 3 * * *` |
| `onec_auto_match` | W-25 (> 20 000 ERP obyekti) |
| `onec_apply_catalog_page` | `read_refs` natijasi kelganda |
| `onec_notify` | xizmatlardan (Telegram, `outbox_jobs(kind='telegram')`) |

`workers/cron.py` ga 5 cron qo'shiladi: `onec_schedule_tick` (`*/5`), `onec_lease_sweeper` (`*/1`), `onec_drift_check` (`30 6 * * *`), `onec_agent_offline_check` (`*/15`), `onec_cleanup` (`0 3 * * *`). Fan-out — `list_active_tenant_ids()` emas, `app.onec_tenants_due(p_kind)` SECURITY DEFINER funksiyasi (faqat faol 1C bazasi bor tenantlar). Agentga beriladigan vazifalar (`onec_agent_tasks`) SAQ job emas — agent ularni long-poll bilan tortadi; uyg'otish — Redis pub/sub `onec:wake:{agent_id}`.

### 4.2. Do'kon agenti vazifalari (Bosqich 5 kengaytmasi, qaror #60)

Agent ro'yxati, ulash, token va vazifa navbati — Bosqich 5 da quriladigan umumiy mexanizm (qaror #66; jadvallar `onec_agents`, `onec_agent_tasks`, `onec_task_results`, `auth.onec_device_authorizations`, migratsiya `0028 store_agent`; protokol — `33-1c-integratsiya.md` §9: lease, heartbeat, Ed25519 imzosi, Redis pub/sub uyg'otish); `AgentTaskPort.enqueue` agent `capabilities` ni tekshiradi (`409 AGENT_CAPABILITY_DISABLED`). Boshqa modullar vazifa qo'yish uchun `onec_integration.application.ports.AgentTaskPort.enqueue(tenant_id, agent_id, kind, payload)` ni chaqiradi; 1C partiya mantig'iga tegmaydi.

| `kind` | Kim qo'yadi | Trigger | Payload | Natija qayerga |
|---|---|---|---|---|
| `fiscal.status` | `integrations/fiscal` | har 5 daqiqa (agent onlayn bo'lsa) | `{cash_register_id}` | `cash_registers.*` (`fm_state`, `fm_receipts_pending`, `last_unacked_receipt_at`; payload `cash_register_id` bo'yicha) va `acked[]` → `fiscal_receipts.ofd_acked_at` |
| `fiscal.resend_unsent` | `integrations/fiscal` | `fiscal_unacked_monitor` 40 soat bosqichi; BO-14 "Qayta yuborish" | `{cash_register_id}` | `ResendResult` → BO-14 |
| `fiscal.zreport` | `sales` (smena yopish) | smena POS'siz yopilganda | `{cash_register_id, shift_id}` | `ZReport` → `fiscal_receipts(kind='z_report')` yoziladi |
| `print.raw` | `notifications`/`reports` | back-office'dan LAN printerga chop etish | `{printer_local_id, data_base64, encoding: "cp866"\|"raster"}` | holat (yuborildi / printer xatosi) |
| `scale.plu_upload` | `catalog` | narx/tovar o'zgargach yoki qo'lda — MVP'dan keyin | `{scale_local_id, items:[{plu, name, price, barcode_prefix}]}` | yuklangan qatorlar soni / xato |
| `card.status` | `integrations/card_terminal` | har 5 daqiqa (agent onlayn va `capabilities.card_terminal.enabled` bo'lsa) | `{card_terminal_ids?:[]}` | `card_terminals.health_status`, `health_checked_at`; `unresolved[]` → `card_terminal_transactions` (`resolved_by='status_query'`) |
| `card.settlement` | `cash` (smena yopish) / `integrations/card_terminal` | smena POS'siz yopilganda; kun oxiri cron (`card_settlement_sweep`, 23:30 Toshkent) settlement'siz qolgan terminallar uchun | `{card_terminal_id, shift_id?}` | `SettlementResult` → `card_terminal_settlements` (`expected_*`, `variance`, `status`); `mismatch` — audit `card.settlement.mismatch` + M18 |

Sotuv paytidagi fiskallashtirish, karta to'lovi (`purchase`/`refund`/`void`) va chek chop etish bulut vazifasi **emas** — POS ularni agentning lokal API'si orqali bajaradi (`21` §9.4, §16). Bu ro'yxat `21` §16, `33-1c-integratsiya.md` §9.5 va `34-1c-agent.md` §14.3 bilan aynan bir xil; vazifa konverti va 1C protokoli (`33` §9) o'zgarmaydi. Agent imkoniyatlari (`hello.capabilities`: `onec`, `fiscal`, `print`, `scale`, `card_terminal` — `34` §14.2) agent sozlamasida yoqiladi; yoqilmagan imkoniyat turiga vazifa berilmaydi.

**Worker/scheduler'da tenant konteksti**: har job'ning birinchi argumenti — majburiy `tenant_id` (`outbox_jobs.tenant_id`dan); job tanasi `async with tenant_transaction(session, tenant_id):` ichida bajariladi, `tenant_id`'siz job darhol xato bilan tugaydi. Scheduler (cron) biznes so'rovi bajarmaydi: `SECURITY DEFINER` funksiyasi `list_active_tenant_ids()` orqali tenantlarni olib, **har tenant uchun alohida job** navbatga qo'yadi. Platformaviy job'lar (obuna holati, billing) ham shu fan-out orqali tenant kontekstida ishlaydi; RLS'ni chetlab o'tadigan worker roli yo'q. Yagona tenant'siz job — `purge_login_attempts`: u biznes jadvaliga tegmaydi, `unscoped_transaction` ichida faqat bitta `SECURITY DEFINER` funksiyani chaqiradi (`auth.login_attempts` tenant'ga bog'lanmagan).

---

## 5. Kutubxonalar

| Vazifa | Kutubxona | Nima uchun |
|---|---|---|
| Web freymvork | **FastAPI** | Qaror qilingan stack; OpenAPI avtomatik, Pydantic bilan tabiiy integratsiya |
| Validatsiya/sxema | **Pydantic v2** | FastAPI bilan birga keladi, tez (Rust core), orval uchun to'g'ri OpenAPI sxema chiqaradi |
| Sozlamalar | **pydantic-settings** | `.env` + real env, `env_prefix="ERP_"`, prod-xavfsizlik guard (`model_validator`) |
| ORM | **SQLAlchemy 2 (async) + asyncpg** | 2.0 stili (`Mapped[...]`) tip xavfsizligini beradi |
| Migratsiya | **Alembic** (asinxron `env.py`) | Zero-downtime siyosati (13-bo'lim) uchun standart vosita |
| UUID | **uuid-utils** (Rust bog'lovchi, UUIDv7) | `11-malumotlar-modeli.md` UUIDv7 qarorini qo'lda implementatsiya qilmasdan tez generatsiya qiladi |
| Navbat/worker | **SAQ** | 4-bo'lim — asinxron stack bilan tabiiy mos, o'rnatilgan monitoring UI |
| Kesh/navbat broker | **redis** (`redis-py` asinxron klient) | SAQ broker + sessiya/kesh/rate-limit (`10-umumiy-arxitektura.md`) |
| Tashqi HTTP | **httpx** (async) | OFD/e-faktura/Click/Payme/SMS/Telegram/Claude API — bitta klient, async |
| Qayta urinish | **tenacity** | Har integratsiya adapterida exponential backoff + jitter — qo'lda `for`/`sleep` yozilmaydi |
| Pagination | **fastapi-pagination** | Cursor va page/size — qo'lda offset/limit hisoblanmaydi (3-bo'lim) |
| Filtrlash | **fastapi-filter** | Deklarativ query filtr, SQLAlchemy modeliga bog'langan. `filter.sort(filter.filter(select(Model)))` → `await session.execute(...)` yoki `fastapi_pagination.ext.sqlalchemy.paginate(session, stmt)` (AsyncSession qo'llab-quvvatlanadi). Versiya: ≥3.0 (SQLAlchemy 2.0). |
| Logging | **structlog** | JSON struktura log, tenant/so'rov ID context — JSONL log yondashuvi |
| Trace | **OpenTelemetry** (FastAPI + SQLAlchemy instrumentatsiyasi) | So'rov → posting → worker zanjirini kuzatish |
| Metrika | **prometheus-client** | `/metrics`; posting latensiyasi, navbat chuqurligi, AI xarajati |
| Xato kuzatish | **sentry-sdk** | FastAPI/Starlette integratsiyasi tayyor |
| Parol/PIN hash | **passlib[argon2]** (argon2-cffi), aniq algoritm **argon2id** | OWASP tavsiyasi (`14-autentifikatsiya-oauth2.md` §4.1, §13) |
| OAuth 2.0 protokol skeleti | **Authlib** | RFC 6749/7636/7009/7662/8414/9068 — `authlib.oauth2.rfc6749` abstrakt grant/klient sinflari, storage hook'lari bizning SQLAlchemy repozitorilarimizga bog'lanadi (`14-autentifikatsiya-oauth2.md` §1) |
| JWT/JWS/JWK (access token, JWKS, litsenziya tokeni) | **joserfc** (Authlib muallifi, EdDSA/ES256) | `PyJWT` — muqobil. `14-autentifikatsiya-oauth2.md` §5–6, §17 |
| CSRF | **itsdangerous** | Django/Flask'da sinalgan imzolash primitiv; cookie-based sessiyada sessiyaga bog'langan sinxronizator-token uchun yetarli, `fastapi-csrf-protect`ka nisbatan ko'proq qo'llab-quvvatlanadi |
| Rate limit | **o'z kodi** — `app/core/ratelimit.py`: Redis `INCR` + `EXPIRE NX` (fixed window), `hit()`/`peek()` | Kutubxona yo'q: `slowapi`/`limits` saqlash qatlami sinxron, bizga bir nechta async hisoblagich yetarli; barcha replikalar bitta Redis hisoblagichini ko'radi. Limitlar (`14-autentifikatsiya-oauth2.md` §12): login — (telefon, IP) juftligi 5 xato/15 daqiqa + IP 20 xato/soat; **`/oauth/token` — 30 so'rov/daqiqa (`client_id`, IP) juftligi bo'yicha** (`ERP_TOKEN_REQUESTS_PER_MINUTE`, oshsa `429 {"error":"slow_down"}` + `Retry-After`); Redis ishlamasa limit o'tkazib yuboriladi (login — DB zaxira bloki bilan) |
| Fayl yuklash | **python-multipart** | FastAPI'ga fayl/forma qabul qilish uchun shart (xarajat cheki fotosi, Excel import) |
| S3 | **aioboto3** | Async stack bilan bir xil event loop (sync `boto3` emas) |
| Excel | **openpyxl** | Boshlang'ich katalog/qoldiq/qarz importi (US-M04-04, US-M08-07), hisobot eksporti (M12) |
| Shtrix-kod/yorliq | **python-barcode** (MIT; EAN-13, Code128) + **zxing-cpp** (Apache-2.0; DataMatrix/QR server PDF uchun) | Yorliqlar asosan brauzerda `bwip-js` (MIT, GS1 DataMatrix ham) bilan chiziladi. `treepoem` **taqiqlangan**: Ghostscript AGPL/tijoriy — SaaS'da manba kodini ochish yoki Artifex litsenziyasini talab qiladi |
| Telegram bot | **aiogram** | Asinxron, FastAPI bilan bir xil stack; `10-umumiy-arxitektura.md`da allaqachon tanlangan |
| AI | **anthropic** (rasmiy SDK), `api` rejimida | Claude API (Haiku 5.5), `AiProvider` porti — `fake`/`cli` (dev) / `api` (prod) — `22-ai-qatlami.md` §1 (AI porti rejimlari `fake`/`cli`/`api`; qaror #16) |
| Vaqt/muddat | **pendulum** | 5 ish kuni (M10; dam olish va bayram kunlari — `app/core/business_days.py` dagi yillik ro'yxat), 48 soat (M01), markirovka qabul muddati (3 ish kuni / 72 soat, M07), qarz eskirish guruhlari (0-30/31-60/60+, M08) — qo'lda `timedelta` arifmetikasi o'rniga; saqlash — `TIMESTAMPTZ`/stdlib `zoneinfo` (Asia/Tashkent) |
| Son/pul formatlash, i18n | **babel** | Eksport qilinadigan hisobot/PDF'da son formatlash (uz_Latn); UI formatlash frontendda (`Intl.NumberFormat`) |
| CLI (seed, ops skript) | **typer** | `scripts/seed.py` va h.k. — `argparse` o'rniga deklarativ CLI |
| Testlar | **pytest, pytest-asyncio, factory-boy, testcontainers, schemathesis** | 6-bo'lim |
| Kod sifati | **ruff, mypy `--strict`, pre-commit** | Yangi kodda `mypy --strict` majburiy (qaror #57); CI gate |
| Xavfsizlik skaneri | **pip-audit**, **gitleaks** | Bog'liqlik zaifliklari va repodagi sirlar — CI'da majburiy (qaror #57) |

**Ataylab kiritilmagan**: `dependency-injector` paketi — composition-root oddiy factory funksiyalar + FastAPI `Depends` bilan yetarli (26 #59).

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

1. `ruff check` + `ruff format --check`, `mypy --strict app` (qaror #57); `pip-audit`, `gitleaks detect`; `.env.example` mavjudligi va `Settings` maydonlari bilan mosligi.
2. `pytest` (bitlik, `testcontainers` servis sifatida CI runner'ida).
3. Alembic: `alembic upgrade head` bo'sh bazada — migratsiya ishlayotganini tekshirish.
4. `schemathesis run` — ishga tushirilgan API'ga qarshi.
5. `openapi.json` eksport + frontend CI'dagi `api:gen --check` bilan taqqoslash (sxema drift bo'lsa — build muvaffaqiyatsiz, `10-umumiy-arxitektura.md` 3-bo'lim).
6. Docker image build + (`main` branch'da) registry'ga push.

### 7.2. Lokal dev — docker compose

Compose fayli — `backend/docker-compose.yml` (repo ildizida emas; `backend/` papkasidan `docker compose up` bilan ishga tushiriladi). Standart docker compose tuzilmasi, **bitta tenant stack emas** — lokal muhit ham ko'p-tenant rejimida ishlaydi:

```yaml
services:
  postgres:   # postgres:16-alpine, host portga chiqarilgan; birinchi ishga tushishda docker/postgres/initdb.sh (DBA bootstrap, 12-db-sxema.md 0-bo'lim)
  redis:      # redis:7-alpine
  migrate:    # bir martalik: alembic upgrade head, erp_migrator bilan (profile: tools)
  seed:       # bir martalik: python -m scripts.seed global, erp_migrator bilan (profile: tools)
  api:        # uvicorn --reload, host portga chiqarilgan, ERP_AI_MODE=fake|cli
  worker:     # SAQ app.workers.worker_settings orqali
  scheduler:  # SAQ CronJob rejimi
  bot:        # aiogram polling (dev'da webhook shart emas)
```

Non-root user, ko'p bosqichli Dockerfile, `/health/ready` orqali `HEALTHCHECK` — standart naqsh (faqat `claude` CLI bosqichi `api` rejimida ixtiyoriy bo'lib qoladi, lokal `cli` tanlanganda saqlanadi).

### 7.3. Konfiguratsiya va sirlar

`app/core/config.py`: `pydantic-settings`, `env_prefix="ERP_"`, `.env` (lokal) / real environment (prod). Loyihaning **barcha** muhit o'zgaruvchilari `ERP_` prefiksli — `Settings` maydoni `fiscal_provider` ↔ `ERP_FISCAL_PROVIDER` (masalan `ERP_DATABASE_URL`, `ERP_MIGRATOR_DATABASE_URL`, `ERP_REDIS_URL`, `ERP_AI_MODE`, `ERP_AI_PII_ROUTE`, `ERP_FISCAL_PROVIDER`, `ERP_FX_USD_UZS_FALLBACK`, `ERP_ESKIZ_TEST_MODE`, `ERP_IDEMPOTENCY_LOCK_TTL_S`, `ERP_IDEMPOTENCY_RETENTION_DAYS`); DBA bootstrap skripti ham shu prefiksdagi `ERP_MIGRATOR_PASSWORD`, `ERP_APP_PASSWORD`, `ERP_DB_NAME`ni o'qiydi (`12-db-sxema.md` §0). Yagona istisno — `CLAUDE_CODE_OAUTH_TOKEN`: uni ilova emas, `claude` CLI o'zi o'qiydi (`22-ai-qatlami.md` §1.1). Prod-xavfsizlik guard naqshi:

```python
@model_validator(mode="after")
def _enforce_production_security(self) -> "Settings":
    if self.environment == "prod":
        if not self.auth_enabled or self.auth_secret == _INSECURE_DEFAULT:
            raise ValueError("prod'da auth yoqilgan va maxfiy kalit o'zgartirilgan bo'lishi shart")
        if self.ai_mode == "cli":
            raise ValueError("prod'da AI rejimi 'api' bo'lishi shart (22-ai-qatlami.md §1, qaror #16)")
    return self
```

Sirlar (DB parol, Redis parol, platforma Click/Payme kaliti, Claude API kaliti, Eskiz/Telegram token, `tenant_secrets` uchun KEK, imzolash kalitlari) — kod/`.env`da emas. UzCloud'da KMS ham, sir ombori ham yo'q, shuning uchun (qaror #65): sirlar repoda **SOPS + age** bilan shifrlangan fayllarda (`deploy/secrets/<env>.enc.yaml`), age maxfiy kaliti faqat deploy mashinasida/CI maxfiy o'zgaruvchisida; deploy vaqtida ochilib konteynerga **muhit o'zgaruvchisi** sifatida beriladi. Tenant integratsiya sirlari (`tenant_secrets`) — ilova darajasida envelope shifrlash (har yozuvga DEK, DEK — KEK bilan; `15-xavfsizlik-va-audit.md` §4). Keyingi bosqich — o'z-hosted Vault/OpenBao (K8s ichida); UzCloud KMS paydo bo'lsa KEK joyi ko'chiriladi. `.env.example` majburiy (qaror #57). Muhitlar: local — `fake/cli`, staging/prod — `api`, alohida kalitlar (`10-umumiy-arxitektura.md`, 3-bo'lim).

---

## 8. Observability

- **Logging**: `structlog`, JSON format, har yozuvda `tenant_id`, `request_id`, `user_id`; shaxsiy ma'lumot (telefon, STIR) log'ga tushmasligi uchun redaction filtri.
- **Readiness/liveness**: `/health/live` (jarayon ishlayaptimi) va `/health/ready` — **gating vs reported** bo'linishi: *gating* (API 200 bermasa stack buziladi) = Postgres round-trip + Alembic sxema versiyasi (`public.alembic_version` `erp_app` ulanishi bilan o'qiladi va kod kutgan `head` bilan solishtiriladi; `SELECT` huquqini `alembic/env.py` beradi — `12-db-sxema.md` §4.4) + Redis; *reported* (faqat ma'lumot, bloklamaydi) = OFD/e-faktura/Claude API/S3 reachability — mijoz tomondagi tashqi tizim uzilishi deploy/health'ni bloklamasligi kerak.
- **Metrika**: `prometheus-client` — HTTP latensiya, posting tranzaksiya davomiyligi, `outbox_jobs` navbat chuqurligi/urinish soni, AI so'rov narxi (`ai_requests.cost_usd` yig'indisi).
- **1C integratsiyasi metrikalari** (Bosqich 7): `onec_agents_online`, `onec_poll_connections`, `onec_batch_duration_seconds`, `onec_items_total{kind,status}`, `onec_items_failed_total{code}`, `onec_task_lease_expired_total{kind}`, `onec_task_duration_seconds{kind}`, `onec_unknown_outcomes_total`, `onec_verify_mismatch_total`; log kontekstida qo'shimcha `agent_id`, `base_id`, `batch_id`, `task_id` (`33-1c-integratsiya.md` §4.6, §15.4).
- **Trace**: OpenTelemetry, FastAPI+SQLAlchemy+httpx avtomatik instrumentatsiya; eksport — **o'z-hosted Grafana Tempo** (UzCloud'da tayyor trace xizmati yo'q). Monitoring stack — Prometheus + Grafana + Loki + Tempo, o'zimiz o'rnatamiz (26 #53).
- **Ops ogohlantirishlari**: UzCloud billing — hisob-faktura 5-sanada, to'lov muddati +10 kun; to'lanmasa server o'chiriladi va "Suspended" holatidan 20 kun o'tib ma'lumot qaytarib bo'lmaydigan tarzda o'chiriladi (UzCloud ofertasi 4.4) → avto-to'lov/oldindan to'lov + billing alerti majburiy (qaror #65); UzCloud status sahifasi (`uzcloud.uz/status`) monitoring manbai.
- **Xato kuzatish**: `sentry-sdk`, tenant/branch context tag sifatida (lekin mijoz PII'siz).

---

## 9. Deploy

Konteynerlar (`10-umumiy-arxitektura.md`, 3-bo'lim bilan mos): **api**, **worker**, **scheduler**, **bot**, (frontend alohida `web` — statik, `24-frontend-arxitekturasi.md`). 1C agent API (`/api/v1/onec-agent/*`, long-poll) — alohida konteyner emas, `api` ichida (uvicorn async; 1 000 parallel long-poll ulanishi — `25-nofunksional-talablar.md`); Windows 1C agenti serverda deploy qilinmaydi (`34-1c-agent.md`).

Standart deploy naqshlari: ko'p bosqichli `Dockerfile` (uv bilan bog'liqliklarni qulflangan holda o'rnatish, non-root `app` user, `HEALTHCHECK`), Alembic'ning bir martalik `migrate` konteyneri (api/worker undan keyin boshlanadi, `db_create_all=false` har joyda konteyner stack'da).

Deploy qarorlari (chunki bu loyiha — ko'p tenant/bitta umumiy stack):

- **Stack soni**: bitta umumiy stack, tenant — RLS bilan ma'lumotlar darajasida (har mijoz uchun alohida stack emas).
- **`api`/`worker`**: **gorizontal ko'payadi** (holat yo'q — sessiya Redis'da, tranzaksiya DB'da).
- **`scheduler`**: **yagona nusxa bo'lishi shart** (cron ikki marta ishlamasligi uchun) — Postgres advisory lock (`pg_try_advisory_lock`) bilan yetakchi tanlanadi, bir nechta `scheduler` konteyneri ishga tushsa ham faqat biri faol bo'ladi.
- **Baza**: **UzCloud DBaaS** (managed Postgres) — konteyner emas. DBaaS'da backup "optional add-on", PITR rasmiy tasdiqlanmagan — shuning uchun **o'z WAL arxivi** (pgBackRest yoki WAL-G → UzCloud S3 Cold, pgBackRest shifrlash bilan): RPO ≤ 5 daqiqa, RTO ≤ 4 soat, har chorakda staging'da to'liq restore sinovi (natija `docs/ops/restore-log.md`), arxiv ≥ 5 yil (qaror #51). Kamida bitta oflayn nusxa **boshqa provayderda** (boshqa DC yoki sovuq arxiv) — qaror #65.
- **Fayl ombori**: UzCloud S3 (AWS S3 API mos, uch karra replikatsiya; Standard 450 so'm/GB/oy + 300 so'm/GB chiquvchi trafik) — `StoragePort` ortida (`aioboto3`); S3 tinch holatda shifrlash bayonoti yo'q → hujjat va fotolar ilova darajasida shifrlanadi (SSE-C yoki mijoz tomonida AES-GCM, kalit — envelope KEK). Lokal/dev — MinIO.
- **E-IMZO-SERVER**: O'zbekiston IP'sidan ishlashi shart (`vpn.e-imzo.uz:3443` faqat UZ ichidan) — UzCloud'da alohida konteyner (Java 8), yt.uz shartnomasi bilan (`21` §5).
- **Ulanish pool'i**: MVP: tashqi pooler yo'q — SQLAlchemy `AsyncAdaptedQueuePool` (asyncpg), `pool_size`/`max_overflow` × api+worker nusxalari soni DBaaS `max_connections` dan kichik. Pooler qo'shilsa (PgBouncer, **transaction** rejimi): PgBouncer ≥1.21 `max_prepared_statements` yoqiladi, yoki asyncpg `prepared_statement_cache_size=0` + `prepared_statement_name_func` (uuid nomlar). Session darajasidagi `SET` taqiqlanadi — tenant faqat `set_config(..., true)` bilan tranzaksiya ichida (1-bo'lim). UzCloud DBaaS'da o'rnatilgan pooler haqida ma'lumot yo'q — MVP'da ilova pool'i, kerak bo'lsa o'z PgBouncer'imiz.

---

## 10. DB migratsiya siyosati (zero-downtime)

**Expand–contract**: har o'zgarish ikki (yoki undan ko'p) kichik Alembic revisiyaga bo'linadi:

1. **Expand**: faqat qo'shish — yangi ustun **NULL bilan ruxsat etilgan** (yoki `DEFAULT` bilan) yoki yangi jadval; eski kodni buzmaydi. Deploy qilinadi, eski va yangi kod versiyasi parallel ishlay oladi (rolling deploy).
2. **Backfill**: kerak bo'lsa, worker job orqali (katta jadvalda `UPDATE ... WHERE id IN (batch)` — bitta katta tranzaksiya emas, bo'lib-bo'lib).
3. **Kodni ko'chirish**: yangi kod yangi ustunni ishlatadi, eski ustun hali o'qiladi (fallback).
4. **Contract**: faqat barcha instance yangi kodga o'tgach va backfill tugagach — eski ustun/jadval `DROP` qilinadi, alohida revisiyada.

Taqiqlar: bir revisiyada ustun **nomini o'zgartirish** yoki **tipini o'zgartirish** (buning o'rniga: yangi ustun qo'sh — ko'chir — eskisini o'chir); `NOT NULL`ni bitta qadamda qo'shish (avval `DEFAULT` + backfill, keyin `NOT NULL`). `migrate` konteyneri har deploy'dan oldin, pre-release `pg_dump` bilan birga ishga tushadi.

---

## 11. Seed data

Seed ikki xil, chegarasi `12-db-sxema.md` §5 va §7 (13-band) da:

- **Global seed** — faqat `12-db-sxema.md` §5.1: `platform.units` (`pcs`, `kg`, `l`, `m`, `box`, `is_fractional` bilan), `platform.plans` (yagona `standard`, `limits` JSONB — `included_cash_registers`, `ai_monthly_tokens`), `platform.addons` (`extra_register`), `platform.marking_product_groups`, `platform.turnover_tax_rates`, `platform.label_templates`, `platform.oauth_clients`. Aniq qiymatlar faqat §5.1 da (bu hujjatda takrorlanmaydi). Ishga tushirish — `python -m scripts.seed global` (typer CLI, `erp_migrator` ulanishi bilan, idempotent — `ON CONFLICT DO NOTHING`), `migrate` konteyneridan keyin. Imzolash kalitlari va maxfiy OAuth mijoz sirlari — deploy skripti (§5.1 izohi), seed emas.
- **Tenant-provisioning** — global seed **emas**: `roles` (5 standart: `owner`, `manager`, `cashier`, `storekeeper`, `accountant`, `is_system=true`), `role_permissions` (to'liq matritsa — `15-xavfsizlik-va-audit.md` §2.2) va `expense_categories` (21 kod, `13-provodka-qoidalari.md` §2.17; tenant o'zgartira oladi — M15, US-M15-01) — tenant-scoped jadvallar, har signup tranzaksiyasida ilova kodi `12-db-sxema.md` §5.2 shabloni bo'yicha yaratadi (`15-xavfsizlik-va-audit.md` §1.5, `14-autentifikatsiya-oauth2.md` §20). Lokal/test uchun `python -m scripts.seed demo-tenant` xuddi shu provisioning kodini chaqiradi.
- **Seed kerak emas** — kod konstantalari: hisoblar rejasi (`12-db-sxema.md` §7, 17-band; `13-provodka-qoidalari.md` §1 — alohida jadval yo'q) va ruxsatlar katalogi (`access` modulidagi ro'yxat, `15-xavfsizlik-va-audit.md` §2.1) kod deploy bilan birga keladi.

Seed — Alembic "data migration" emas (bazani versiyalash bilan aralashtirmaslik uchun), `migrate`dan keyingi alohida bosqich.

---

## Ochiq savollar

Faqat tashqi javob kerak bo'lgan bandlar:

1. **UzCloud shartnomasi** — yuridik shaxs shartnomasida SLA foizi va kompensatsiya, DBaaS PostgreSQL HA/PITR/versiya/`max_connections`/pooler, disk va S3 tinch holatda shifrlash, K8s Control Plane narxi — 26 #51 (OQ-043). Interim: o'z WAL PITR, ilova darajasida shifrlash, ilova pool'i, o'z-hosted Tempo.
2. **Fiskal hamkor** — lokal ko'prik yoki bulut rejimi, autentifikatsiya, test stend (`integrations/fiscal` real adapteri va `fiscal.*` vazifalari shunga bog'liq) — 26 #109 (OQ-012). Interim: `ERP_FISCAL_PROVIDER=fake`; blok — Bosqich 5.

## Manbalar

- `spec/kod-uchun/14-autentifikatsiya-oauth2.md` — OAuth 2.0 AS/RS, Authlib/joserfc tanlovi, token jadvallari, obuna lokauti.
- `spec/kod-uchun/10-umumiy-arxitektura.md` — komponentlar, muhitlar.
- `spec/kod-uchun/11-malumotlar-modeli.md` — jadvallar, registrlar, holat mashinalari, raqamlash.
- `spec/kod-uchun/24-frontend-arxitekturasi.md` — API konventsiyalari (cookie/CSRF, Idempotency-Key, X-Branch-Id, xato formati, orval).
- `spec/kod-uchun/03-modullar-talablari.md` — M01–M19 foydalanuvchi hikoyalari va chekka holatlar.
- `spec/kod-uchun/33-1c-integratsiya.md` — `onec_integration` moduli, SAQ job'lari va cron, agent API va autentifikatsiyasi.
- `spec/kod-uchun/21-integratsiyalar.md` §1, §16 — `FiscalPort`, Do'kon agenti.
- `research_notes/ochiq-savollar/P4-huquq-hosting.md` §4 (UzCloud: S3, KMS yo'q, Tempo yo'q, DBaaS PITR, oferta 4.4), `P1-soliq-fiskal.md` (OQ-011 — fiskal qism o'zgarsa qayta xulosa), `D-qarorlar-va-E-standartlar.md` (qaror #51, #55, #57).

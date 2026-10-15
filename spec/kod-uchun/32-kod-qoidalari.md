# Kod yozish qoidalari (engineering conventions)

**Maqsad:** Kod yozishda rioya qilinadigan aniq, tekshiriladigan qoidalar — repo tuzilmasi, nomlash, pul/sana, tranzaksiya/tenant, xato/log, test, Git ish oqimi, "tayyor" ta'rifi, spec↔kod bog'lanishi, xavfsizlik. Boshqa fayllarni (`11`–`24`) qaytarib yozmaydi — faqat ulardagi qarorlarni **bitta joyga jamlab**, PR tekshiruvida foydalanish uchun qisqartiradi.
**Kim uchun:** hammasi (backend/frontend dasturchi — asoschi + Claude, qabul agenti, kod review).
**Bog'liq fayllar:** `11-malumotlar-modeli.md`, `12-db-sxema.md`, `13-provodka-qoidalari.md`, `15-xavfsizlik-va-audit.md`, `17-api-umumiy.md`, `23-backend-arxitekturasi.md`, `24-frontend-arxitekturasi.md`, `27-backlog.md`, `29-atamalar-lugati.md`, `33-1c-integratsiya.md`, `34-1c-agent.md`, `01-qarorlar.md`.
**Holat:** joriy, 2026-10-16.

## Qoidalar ierarxiyasi

Bu fayl **ikkinchi darajali manba**: ziddiyat bo'lsa `01-qarorlar.md` → mavzu bo'yicha asosiy fayl (`12`, `17`, `23`, `24`, …) → shu fayl tartibida hal qilinadi (`00-README.md` §Qoidalar, 3-band). Bu faylda **yangi biznes qaror qabul qilinmaydi** — faqat mavjud qarorlar muhandislik amaliyotiga tarjima qilinadi. Spec hali aniq ko'rsatmagan joylarda — **"taklif (asoschi tasdiqlaydi)"** belgisi bilan qayd etiladi, kod shu belgili qoidaga asoslanib yozilishi mumkin, lekin keyin tasdiqlanishi kerak.

---

## 1. Repo tuzilmasi

Uchta kod papkasi: `backend/` (`23-backend-arxitekturasi.md` §1), `web/` (`24-frontend-arxitekturasi.md` §1) va Bosqich 7 dan — `agent-1c/` (Windows 1C agenti, .NET Framework 4.8; 1.3-band, `34-1c-agent.md`). Hujjatlar — `spec/kod-uchun/` (bu repo ichida, kod bilan bir joyda). Umumiy test-vektorlar — repo ildizidagi `shared/` (6.3-band).

### 1.1 Backend (`backend/`)

```
backend/
├── app/
│   ├── core/                  # kesishuvchi infratuzilma — hech qaysi modulga tegishli emas
│   │   ├── config.py           # Settings (pydantic-settings), get_settings()
│   │   ├── db/
│   │   │   ├── session.py       # async engine, AsyncSession, tenant_transaction()
│   │   │   └── base.py          # DeclarativeBase, TenantMixin, TimestampMixin
│   │   ├── auth/                # BFF cookie/CSRF, OAuth claims dependency
│   │   ├── permissions.py       # require_permission("sales.create")
│   │   ├── idempotency.py       # Idempotency-Key middleware + repo
│   │   ├── errors.py            # AppError, exception handler'lar
│   │   ├── pagination.py        # fastapi-pagination sozlamasi
│   │   ├── logging.py           # structlog sozlamasi
│   │   └── telemetry.py         # OpenTelemetry, prometheus-client, sentry-sdk
│   ├── modules/
│   │   └── <modul>/             # masalan sales, returns, inventory, debts, vat, accounting, …
│   │       ├── domain/            # entity/value object, biznes qoida — pure Python, SQLAlchemy'siz
│   │       │   ├── entities.py
│   │       │   └── rules.py
│   │       ├── application/       # use-case/service, tranzaksiya chegarasi shu yerda
│   │       │   ├── posting.py       # <Modul>PostingService (2-bo'lim, `23` §2)
│   │       │   ├── services.py      # CRUD/qidiruv — posting bo'lmagan amallar
│   │       │   └── ports.py         # modul kutgan interfeyslar (boshqa modul shuni amalga oshiradi)
│   │       ├── infrastructure/
│   │       │   ├── models.py        # SQLAlchemy ORM model
│   │       │   ├── repositories.py  # faqat SQLAlchemy so'rovlari
│   │       │   └── tasks.py         # SAQ job'lar (`workers/jobs`ga shu yerdan import qilinadi)
│   │       └── api/
│   │           ├── router.py        # APIRouter(prefix, tags=[...])
│   │           ├── schemas.py       # Pydantic v2 request/response — OpenAPI/orval manbasi
│   │           └── deps.py          # modulga xos dependency
│   └── workers/
│       ├── jobs/                # SAQ task ro'yxati (modul `tasks.py`laridan import)
│       ├── cron.py               # SAQ CronJob ro'yxati
│       └── worker_settings.py    # SAQ worker sozlamalari
├── alembic/{env.py, versions/}
├── tests/
├── scripts/                     # seed.py (typer CLI), wait_for_db.py
├── Dockerfile
├── pyproject.toml / uv.lock
└── alembic.ini
```

**Qatlam qoidasi** (`23-backend-arxitekturasi.md` §1): `api → application → domain`; `infrastructure` faqat `domain`dagi portni amalga oshiradi. Modullar bir-birining `infrastructure`/`api` qatlamini **import qilmaydi** — faqat boshqa modulning `application`/`domain` portini (masalan `sales` → `inventory.application.ports.StockPort`, hech qachon `inventory.infrastructure`). Bu qoida FSD'dagi "faqat pastga import"ga parallel va `eslint-plugin-boundaries` singari CI import-linter bilan majburlanadi (**taklif**: `import-linter`/`grimp`, asoschi tasdiqlaydi — `23`da aniq vosita ko'rsatilmagan).

Modul papkalari (`23-backend-arxitekturasi.md` §1 — 18 mahsulot moduli + kesishuvchi `integrations`/`sync`/`ai`; OpenAPI tag ↔ papka xaritasi — `17-api-umumiy.md` §11): `sales, returns, pricing, inventory, purchasing, debts, vat, accounting, reports, access, auth, branches, expenses, cash, billing, notifications, integrations, ai, sync` + Bosqich 7 da `onec_integration` (M19; ichki tuzilma — `33-1c-integratsiya.md` §4.1, ikki router: `router_web.py` — `/onec-*`, `router_agent.py` — `/onec-agent/*`). `integrations` — tag emas, faqat ichki modul (adapterlar). `bank_settlements` — `cash` moduli ichida (`23` §1).

**Fiskal kod — alohida, kam o'zgaradigan paket** (qaror #60): `FiscalPort` va uning adapterlari (`FakeFiscalAdapter`, hamkor bulut adapteri, Do'kon ko'prigi adapterlari `multikassa_local`/`fiscaldrive_local`) `integrations/fiscal/` ichida, boshqa modullar faqat `FiscalPort` orqali murojaat qiladi; port chegarasida pul — butun son tiyinda (`int`), konvertatsiya bitta funksiyada (`01-qarorlar.md` #26). Sabab: virtual kassaning fiskal qismi o'zgarsa qayta xulosa talab qilinadi (VMQ-943 2-ilova 6-band) — fiskal paketga tegadigan PR alohida, kichik va CHANGELOG bilan. Tanlov — `FISCAL_PROVIDER` = `fake` / `cloud` / `multikassa_local` / `fiscaldrive_local` (MVP'da `fake`, real adapter Bosqich 5 da — `26-ochiq-savollar-reestri.md` #109).

**Eslatma**: bu daraxt `{api,service,repo,models,schemas,events}` kabi yassi papka to'plami emas — har modulda **to'rt qatlam** (`domain/application/infrastructure/api`) bor; `service`/`repo`/`models`/`schemas` nomlari mos ravishda `application/services.py`, `infrastructure/repositories.py`, `infrastructure/models.py`, `api/schemas.py` ichida yashaydi. Alohida `events/` papkasi yo'q: domen voqealari (`sale.created`, `shift.opened` — 2.3-bo'lim) `sync`/`outbox_jobs` orqali, fon ishlari esa har modulning `infrastructure/tasks.py`sida.

### 1.2 Frontend (`web/`)

```
web/                                  # Turborepo (npm workspaces)
├── apps/shell/src/{app,features,main.tsx}   # yagona Vite ilova: router, layout, auth-provider
├── packages/
│   ├── pages/<sahifa-guruhi>/         # pos, catalog, warehouse, debts, finance, reports,
│   │                                   # settings, billing, ai-assistant, onec (Bosqich 7)
│   │   └── src/{app, pages/<sahifa>/{model/{events,stores,effects,connections,types,lib}, ui}, features, entities, shared}
│   └── shared/{api, models, state, ui, i18n, offline, lib, config}
└── turbo.json
```

Import qoidasi (FSD, `24-frontend-arxitekturasi.md` §1): `app → pages → features → entities → shared`, faqat pastga, sahifalar bir-birini import qilmaydi, paketlararo faqat `@shared/*`.

### 1.3 Do'kon agenti (`agent-1c/`, asos — Bosqich 5, 1C — Bosqich 7)

Alohida .NET Framework 4.8 solution (qarorlar #38, #60). Bu **bitta Do'kon agenti** asosi: fiskal ko'prik (POS → `127.0.0.1` lokal API → FM/hamkor lokal xizmati → OFD), xom TCP 9100 printer, tarozi va 1C moduli bir xil supervisor, ulash, avto-yangilanish, imzo va DPAPI qatlamidan foydalanadi; imkoniyatlar alohida loyihalar (`src/Fiscal/`, `src/Devices/` — Bosqich 5; `src/Worker/` (COM) — Bosqich 7) sifatida qo'shiladi, `Agent/`, `Protocol/`, `Common/` umumiy. Repo papkasi nomi `agent-1c/` saqlanadi (34 `34-dokon-agenti.md` ga kengaytirilganda nom qayta ko'riladi). ichki arxitektura, protokol bajarilishi va yozish algoritmi — `34-1c-agent.md` (ustun manba; quyidagi daraxt — repo darajasidagi konventsiya, loyiha nomlari 34 bilan izchil qilinadi).

```
agent-1c/
├── ErpOneCAgent.sln
├── src/
│   ├── Agent/            # supervisor: per-user tray ilova, ulash (device code), long-poll, lease/heartbeat,
│   │                     # DPAPI (CurrentUser) sirlar, results.jsonl outbox, imzoli avto-yangilanish
│   ├── Worker/           # COM worker: x86 va x64 build → OneCWorker.x86.exe / OneCWorker.x64.exe
│   │                     # (V8x.COMConnector, stdin/stdout JSON, bitta bazaga bitta COM sessiya)
│   ├── Protocol/         # 33 §9 DTO'lari: ObjectSpec/QuerySpec/Value, xato obyekti, vazifa turlari (oq ro'yxat)
│   ├── Fiscal/           # fiskal ko'prik (qaror #60): localhost API, FM/hamkor lokal xizmati adapteri — Bosqich 5
│   ├── Devices/          # xom TCP 9100 printer, tarozi (serial/TCP, PLU) — Bosqich 5
│   └── Common/           # Ed25519 imzo tekshiruvi, UUIDv5 (onec_guid), JCS xesh, log maskalash
├── tests/                # unit + protokol testlari (soxta server, soxta COM)
├── installer/            # per-user o'rnatuvchi (admin huquqisiz; vosita — 34 da)
└── build/                # imzolash va reliz skriptlari
```

- **Server bilan yagona kontrakt** — `33-1c-integratsiya.md` §9: `ObjectSpec`/`QuerySpec` JSON Schema backenddagi Pydantic modellaridan (`onec_integration/domain/object_spec.py`) eksport qilinadi va `agent-1c/` testlarida shu sxemaga qarshi tekshiriladi; agentda qo'lda «ikkinchi» sxema yozilmaydi (`openapi.json` → orval qoidasining agentdagi ekvivalenti).
- **Umumiy test-vektorlar**: GUID (`33` §8.1) va kontent xeshi (§8.2) vektorlari — `shared/onec-guid-vectors.json`; backend (pytest) va agent (C#) **bitta fayldan** o'qiydi (QT-M19-12).
- **Nomlash (C#)**: .NET standarti — `PascalCase` tiplar/metodlar, `camelCase` lokal o'zgaruvchilar, `_camelCase` maydonlar; JSON maydonlari protokolda **snake_case** (serverdagi bilan aynan bir xil, `01-qarorlar.md` #24).
- **Pul**: `decimal` (hech qachon `double`); qiymat kodlash — `33` §9.8.
- **Sirlar**: agent maxfiy kaliti va 1C paroli faqat DPAPI `CurrentUser` bilan PK'da; serverga, logga, crash-dump'ga hech qachon chiqmaydi (10-band).

**CI va imzolash (`agent-1c/`):**

| # | Bosqich | Izoh |
|---|---|---|
| 1 | Windows runner'da `msbuild` (Release, x86 va x64) | `ubuntu` runner'da emas — .NET Framework 4.8 |
| 2 | Unit + protokol testlari | Soxta server va soxta COM bilan; GUID/xesh vektorlari `shared/` dan |
| 3 | JSON Schema drift tekshiruvi | backend eksport qilgan `ObjectSpec` sxemasi ↔ agent DTO'lari |
| 4 | **Authenticode OV** imzosi (`.exe`, `.dll`, o'rnatuvchi) + vaqt tamg'asi | Faqat reliz build'da; kalit apparat tokenda/HSM'da (qaror #38) — imzolash qo'lda yoki token ulangan alohida runner'da, sertifikat CI sirlarida saqlanmaydi |
| 5 | Yangilanish manifesti — **Ed25519** (`signing_keys.purpose='agent_update'`) + SHA-256 + hajm | Ildiz kalit **oflayn**, CI'da hech qachon yo'q; manifest `GET /onec-agent/update-manifest?channel=stable\|pilot` orqali tarqatiladi (`33` §9.3 A-09), downgrade taqiq |

Agent reliz versiyasi `min_agent_version` bilan moslanadi — server eski agentga yozish vazifasini bermaydi (`ONEC_AGENT_UPDATE_REQUIRED`).

### 1.4 Hujjatlar

Spec — shu repo ichida `spec/kod-uchun/00`–`34` (o'qish tartibi `00-README.md`da). Kod commit'i spec o'zgarishini talab qilsa — **bitta PR**da (7-bo'lim, spec-first qoidasi).

---

## 2. Nomlash

### 2.1 Python (backend)

| Narsa | Qoida | Misol |
|---|---|---|
| Modul/fayl | `snake_case.py` | `posting.py`, `repositories.py` |
| Klass | `PascalCase` | `SalePostingService`, `DebtMove` |
| Funksiya/metod/o'zgaruvchi | `snake_case` | `require_permission`, `tenant_transaction` |
| Konstanta | `UPPER_SNAKE_CASE` | `_INSECURE_DEFAULT` |
| Protokol/interfeys (port) | `PascalCase`, ko'pincha `*Port`/`*Service` suffiks | `StockPort`, `FiscalPort`, `DocumentPostingService` |
| Pydantic schema | `PascalCase`, yo'nalish suffiksi bilan — **taklif** (asoschi tasdiqlaydi; `23`da aniq suffiks qarori yo'q) | `SaleCreateRequest`, `SaleResponse` |
| SAQ job funksiyasi | `snake_case`, fe'l+ot | `ofd_send`, `recost_product` |

### 2.2 TypeScript/React (frontend)

| Narsa | Qoida | Misol |
|---|---|---|
| Komponent fayl/funksiya | `PascalCase` | `Page.tsx`, `DebtBookPage` |
| Effector event/store/effect | `camelCase`; store — `$` prefiks | `pageMounted`, `$debtors`, `getDebtorsFx` |
| Oddiy funksiya/o'zgaruvchi | `camelCase` | `formatMoney`, `useBarcodeWedge` |
| Tip/interfeys | `PascalCase` | `DebtorsQuery`, `AcceptPaymentBody` |
| Fayl (model/ui papkalari) | `kebab-case` papka, `index.ts` eksport | `debt-book/model/events/index.ts` |

Manba: `24-frontend-arxitekturasi.md` §1–2 naqshlari (aynan shu misollar o'sha fayldan ko'chirilgan).

### 2.3 DB (`12-db-sxema.md` §1.5, `11-malumotlar-modeli.md`)

- Sxema: `platform`, `auth`, `app` — uchta PostgreSQL sxemasi (`12` §2).
- Jadval nomi — **ko'plik, snake_case**: `sales`, `debt_moves`, `goods_receipts`.
- Ustun nomi — **snake_case**, qisqartirilmaydi: `cash_register_id`, `doc_date`, `client_event_id`.
- **Enum qiymatlari — PostgreSQL native `ENUM` emas**: `TEXT + CHECK (col IN (...))`. Sabab — qayta ishlatiladigan qiymat to'plamlari (`draft/posted/cancelled`) jadvallar orasida sun'iy bog'lanib qolmasligi uchun (`12` §1.5). Faqat haqiqiy ma'lumotnoma (`units`, `expense_categories`, `roles`) — alohida jadval, lookup emas.
- CHECK qiymatlari — **snake_case, pastki chiziqli**: `'posted'`, `'debt_settlement'`, `'rejected_period_closed'`.
- Append-only registr ustuni — har doim `reversal_of_id` (storno izi), hech qachon boshqa nom.
- Foreign key — `<ot>_id`; ko'p qiymatli massiv ustun — `<ot>_ids` (`branch_ids`, `target_ids`).

### 2.4 URL/API (`17-api-umumiy.md` §2, `01-qarorlar.md` #24)

| Qatlam | Qoida | Misol |
|---|---|---|
| URL yo'li | **kebab-case, ko'plik ot** | `/goods-receipts`, `/debt-writeoffs`, `/price-changes` |
| Holat o'tkazuvchi amal | `/{resurs}/{id}/{fe'l}` | `/goods-receipts/{id}/post`, `/transfers/{id}/receive` |
| JSON maydon / query parametr / enum qiymati | **snake_case**, DB ustun bilan bir xil | `cash_register_id`, `?doc_date__gte=`, `"posted"` |
| `operation_id` | `<tag>_<harakat>`, qo'lda beriladi | `debts_forgive`, `goods_receipts_post` |
| orval funksiya nomi | tag prefiksi olib tashlanadi | `debts_list_debtors` → `listDebtors` |

camelCase JSON maydonlarda **hech qachon** ishlatilmaydi (`17` §2, qaror #24).

### 2.5 Ruxsat kodlari (permission code)

Format — `<modul>.<amal>` yoki `<modul>.<obyekt>.<amal>`, pastki chiziqli so'z, nuqta bilan ajratilgan segment (`15-xavfsizlik-va-audit.md` §2.1): `sales.void`, `debts.forgive`, `stock.count.post`, `settings.tenant`. Limitli kodlar `role_permissions.limit_value` bilan birga saqlanadi, kodning o'zida limit raqami bo'lmaydi.

### 2.6 Xato kodlari (error code)

Format — **`UPPER_SNAKE_CASE`**, ingliz tilida, biznes-semantik (texnik stack-trace emas): `DEBT_LIMIT_EXCEEDED`, `PERIOD_CLOSED`, `MARKING_CODE_ALREADY_SOLD`. To'liq katalog — `17-api-umumiy.md` §15, **yagona manba**; yangi kod shu faylga qo'shiladi, boshqa joyda qayta e'lon qilinmaydi. `message_key` — shunga mos `errors.<snake_case>` (kod darajasida) yoki `validation.<snake_case>` (maydon darajasida).

### 2.7 i18n kalitlari

`i18next`, ikki nazfa prefiksi: `errors.*` (API xato kodi matni), `validation.*` (forma maydon xatosi, backend `details[].message_key` bilan bir xil). UI matn kalitlari — sahifa/komponent nomiga mos nazfa, **taklif** (asoschi/UX-yozuvchi tasdiqlaydi): `pos.*`, `debts.*`, `reports.*` — modul OpenAPI tag nomi bilan bir xil bo'lishi tavsiya etiladi (izchillik uchun).

### 2.8 Hodisa (event) va fon ish (job) nomlari

Ikki alohida nomlash tizimi, aralashtirilmaydi:

- **Domen hodisasi** (sync/outbox orqali uzatiladigan, `client_event_id` bilan dedupe qilinadigan): `<entity>.<action>` — `sale.created`, `shift.opened`, `transfer.received`, `sale.draft_voided`, `return.created` (`10-umumiy-arxitektura.md` §2, `11-malumotlar-modeli.md`).
- **`outbox_jobs.kind`** (tashqi integratsiya/fon ishi): `snake_case`, fe'l+ot — `ofd_send`, `einvoice_send`, `ettn_send`, `marking_verify`, `marking_sell`, `state_report_reminder`, `report_export`, `label_pdf` (`12-db-sxema.md`).
- **`audit_log.action`**: ikkisining aralashi, kontekstga qarab — `platform_admin_access`, `sync_drain_started`, `marking.offline_sold` (`15-xavfsizlik-va-audit.md` §6.1). Yangi audit action qo'shilganda mavjud uslubga (nuqta yoki pastki chiziq, o'sha domenda allaqachon ishlatilgan shaklga) moslashtiriladi.

---

## 3. Pul/son/sana qoidalari

**Manba — `01-qarorlar.md` #26, `08-dizayn-tizimi.md` §0.1, `11-malumotlar-modeli.md` §1, `17-api-umumiy.md` §3.** Bu fayl faqat jamlaydi, yangi raqam kiritmaydi.

### 3.1 Saqlash (PostgreSQL)

| Tur | DB tipi | Misol |
|---|---|---|
| Pul | `NUMERIC(18,2)` | `120000.00` |
| Narx/tannarx/foiz-bo'lmagan koeffitsient | `NUMERIC(18,4)` | `8333.3333` |
| Foiz (`discount_pct`, `vat_rate`) | `NUMERIC(5,2)` | `12.00` |
| Miqdor | `NUMERIC(18,3)` | `10.500` |

`float`/`double precision` pul-miqdor ustunlarida **hech qachon** ishlatilmaydi.

### 3.2 Backend hisob-kitob

Python `decimal.Decimal` — pul/miqdor bilan ishlaydigan har qanday kodda majburiy; `float`/`int` orqali oraliq hisob **taqiqlanadi**. Yaxlitlash — `ROUND_HALF_UP`: chek qatori jami butun so'mgacha (`line_total = ROUND_HALF_UP(qty × unit_price − chegirma, 0)`), QQS summasi tiyingacha (`ROUND_HALF_UP(line_total × r/(100+r), 2)`) — `01-qarorlar.md` #26 formulasi (qonunda yaxlitlash qoidasi yo'q — muhandislik qarori, `26-ochiq-savollar-reestri.md` #82). Pydantic v2 schemalarida pul/miqdor maydoni — `str` tipi (`Decimal` emas!), chunki API javobida JSON `number` taqiqlangan (quyida 3.4).

### 3.3 Frontend hisob-kitob

Pul hisob-kitobi **standart holatda frontendda qilinmaydi** — backend tayyor summalarni qaytaradi. Istisno — **faqat ikki holat** (`08-dizayn-tizimi.md` §0.1): (a) offline POS'da chek jamini/qaytimni/kutilgan naqdni hali serverga yuborilmasdan hisoblash, (b) submit'dan oldingi forma jami (masalan yangi chek qatori qo'shilganda oraliq ko'rsatish). Bu ikki holatda ham:

- `Number`/`parseFloat` bilan pul hisoblash **taqiqlanadi** (lint bilan majburlanadi, qaror #57: ESLint `no-restricted-syntax` + custom rule — `Number(`, `parseFloat(`, `parseInt(` chaqiruvlari va `Money` tipidagi qiymatlarda `+ - * /` operatorlari taqiqlangan; istisno faqat `shared/lib/money` ichida, `eslint-disable` izohi bilan).
- `decimal.js`/`big.js` — satr-satr amal, `shared/lib/money` ichida bitta joyda.
- Yaxlitlash formulasi backend bilan **aynan bir xil** (yuqoridagi 3.2), umumiy test-vektorlar — `shared/money-vectors.json` (ikki tomon bir xil fayldan test o'qiydi).
- `formatMoney(value: string): string` — **faqat ko'rsatish**, natijasi hech qachon API'ga qaytarilmaydi va keyingi hisoblashda ishlatilmaydi. `Intl.NumberFormat("uz-UZ")` + qo'lda `" so'm"` suffiks.

### 3.4 API transport

Pul/narx/miqdor — har doim **o'nlik kasr satr** (`"12000.00"`), JSON `number` turi **hech qachon** ishlatilmaydi (float yaxlitlash xatosi oldini olish uchun, `17` §3). ID — UUIDv7 satr.

### 3.5 Sana/vaqt

| Tur | Format | Saqlash | Izoh |
|---|---|---|---|
| Hisob sanasi | `"2026-10-15"` (ISO `date`) | `DATE`, Toshkent bo'yicha | `doc_date` |
| Vaqt belgisi | `"2026-10-15T09:00:00Z"` (ISO `timestamptz`, UTC) | `TIMESTAMPTZ`, UTC saqlanadi | `created_at`, `posted_at`, `cancelled_at` |
| Davr (oy) | `"2026-10"` | DB `DATE` (oyning 1-sanasi) | `vat_moves.period`, `period_closings.period` |

Backend: saqlash har doim **UTC**, mahalliy vaqt arifmetikasi (Toshkent, `UTC+5`) — **`pendulum`** yoki stdlib `zoneinfo("Asia/Tashkent")` orqali, hech qachon qo'lda `timedelta` bilan offset qo'shilmaydi (`23-backend-arxitekturasi.md` §5). Frontend: ko'rsatishda UTC → Toshkent konvertatsiyasi **o'zi** (brauzer/`dayjs`) bajaradi, backend har doim `Z` bilan UTC qaytaradi (qo'lda offset formula taqiqlanadi).

---

## 4. Tranzaksiya va tenant

Manba — `23-backend-arxitekturasi.md` §1–2, `15-xavfsizlik-va-audit.md` §3.1.

### 4.1 `tenant_transaction()` — yagona kirish nuqtasi

```python
@asynccontextmanager
async def tenant_transaction(session: AsyncSession, tenant_id: UUID):
    async with session.begin():
        await session.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})
        yield session
```

- `async_session_factory(..., autobegin=False)` — shu sozlama tufayli `tenant_transaction()`dan **tashqarida** `execute` chaqirilsa xato beradi; tenant kontekstisiz so'rov **jismonan mumkin emas**.
- `set_config(..., true)` — tranzaksiya-lokal (`SET LOCAL`ning parametrlashtirilgan muqobili); `SET LOCAL ... = :param` ishlatilmaydi (PostgreSQL `SET` parametr qabul qilmaydi).
- `current_tenant_id` — faqat auth dependency orqali (cookie/JWT'dan); **hech qachon** so'rov tanasi/query parametridan (`X-Tenant-Id` header **yo'q**).
- Ichki savepoint kerak bo'lsa — `session.begin_nested()`, yangi tashqi tranzaksiya ochilmaydi.
- Posting xizmati, `/sync/push` (har voqea — alohida `tenant_transaction`), worker job'lari (birinchi argument — majburiy `tenant_id`) — barchasi aynan shu helper'dan foydalanadi, boshqa yo'l bilan tranzaksiya ochish **taqiqlanadi**.

### 4.2 Ikki qatlamli tenant izolyatsiyasi

1. Ilova qatlami: `TenantMixin` modellarga SQLAlchemy `with_loader_criteria` orqali global `tenant_id` filtri.
2. PostgreSQL RLS: `tenant_id = current_setting('app.tenant_id', true)::uuid`, `ENABLE`/`FORCE ROW LEVEL SECURITY`, ilova DB roli **superuser emas**. Fail-closed: kontekst yo'q bo'lsa — nol natija, xato emas.

Ikkisi mustaqil: (a) buzilsa (b) himoya qiladi va aksincha. `auth.*` sxemasi (login-oldidan jadvallar) — RLS o'rniga `GRANT` yo'qligi + `SECURITY DEFINER` funksiyalar bilan himoyalanadi (15-§3.3).

### 4.3 Posting service naqshi

Har hujjat turi uchun bitta xizmat, protokolga mos:

```python
class DocumentPostingService(Protocol):
    async def post(self, doc_id: UUID) -> PostingResult: ...
    async def reverse(self, doc_id: UUID, reason: str, actor_id: UUID) -> PostingResult: ...
```

`post()` ichida **bitta** `tenant_transaction` blokida: (1) biznes qoida tekshiruvi (`domain/rules.py`), (2) qulflash — `stock_balances (warehouse_id, product_id)`: `INSERT ... ON CONFLICT DO NOTHING` so'ng `SELECT ... FOR UPDATE`; kerak bo'lsa `debt_balances (counterparty_id, direction)` ham `FOR UPDATE`. **Qulf tartibi** (deadlock'ga qarshi, har doim shu ketma-ketlik): avval `stock_balances` — `(warehouse_id, product_id)` o'sish tartibida, so'ng `debt_balances` — `counterparty_id` bo'yicha. `cash_moves` qulflanmaydi. (3) registrlarga append-only yozish (`stock_moves`, `debt_moves`, `cash_moves`, `ledger_entries`, `vat_moves`). (4) hujjat holatini `posted`ga o'tkazish. (5) commit'dan **keyin** (`after_commit` hook) tashqi integratsiya ishini navbatga qo'yish — **hech qachon** tashqi tizim tranzaksiya ichida chaqirilmaydi.

`reverse()` yangi hujjat yaratmaydi: asl hujjat `cancelled` bo'ladi, har yozilgan registr qatoriga **teskari belgili nusxa** qo'shiladi (`reversal_of_id` — teskari qilinayotgan asl qator), hech qachon `UPDATE`/`DELETE`.

### 4.4 Davr yopish va recost

`period_closings`ga tegishli sanaga yangi posting — `409 PERIOD_CLOSED`. `recost_jobs` (kech sinxron/kech kirim) yopilgan davrga tegsa — `rejected_period_closed`, yangi posting emas, tuzatish yozuvi qo'shiladi.

### 4.5 Idempotentlik

Back-office yozuvchi so'rov — `Idempotency-Key` majburiy: Redis `SETNX idem:{tenant}:{key}` tezkor qulf (parallel takror → `409 IDEMPOTENCY_IN_PROGRESS`) + Postgres `idempotency_keys` doimiy jurnal (30 kun saqlanadi, qayta so'rovda saqlangan javob qaytariladi, qayta bajarilmaydi). `/sync/push` bundan mustasno — dedupe `sync_receipts.client_event_id` orqali.

---

## 5. Xatolar va loglar

### 5.1 Xato konverti

Yagona shakl (`17-api-umumiy.md` §7.1, hech qachon boshqacha qaytarilmaydi):

```json
{"error": {"code": "DEBT_LIMIT_EXCEEDED", "message_key": "errors.debt_limit_exceeded",
  "params": {"limit": "500000.00", "requested": "569000.00"},
  "details": [{"field": "payments[0].amount", "message_key": "validation.exceeds_credit_limit"}],
  "request_id": "01933a1e-..."}}
```

- `code` — barqaror mashina kaliti (2.6-bo'lim), frontend/test shu bo'yicha ishlaydi, **hech qachon** erkin matn bo'yicha filtrlanmaydi.
- `details` — **har doim massiv** (bo'sh bo'lishi mumkin), maydon darajasidagi xabarlar, react-hook-form/zod bilan bir xil shakl.
- `params` — ixtiyoriy obyekt, biznes kontekst (limit/so'ralgan qiymat/`resource`/`reason`), i18next interpolatsiyasi uchun.
- `request_id` — `structlog` so'rov ID'si, javob header `X-Request-Id` bilan bir xil qiymat.
- Backend: `app/core/errors.py`dagi `AppError` + exception handler — har endpoint'da qo'lda `try/except` bilan JSON qurilmaydi, markazlashtirilgan handler orqali.
- Frontend: xom JSON/`JSON.stringify` foydalanuvchiga ko'rsatilmaydi — har doim `message_key` → i18next tarjimasi.

### 5.2 Logging

- **`structlog`**, JSON format; har yozuvda `tenant_id`, `request_id`, `user_id` context sifatida bog'langan (`23-backend-arxitekturasi.md` §8).
- **PII logda yo'q**: telefon, STIR, parol/PIN, to'liq karta/bank rekvizit — redaction filtri orqali chiqarib tashlanadi. `sentry-sdk`ga ham tenant/branch **ID** tag sifatida boradi, mijoz PII'siz.
- Trace — OpenTelemetry (FastAPI+SQLAlchemy+httpx avtomatik instrumentatsiya); metrika — `prometheus-client` (HTTP latensiya, posting tranzaksiya davomiyligi, `outbox_jobs` navbat chuqurligi, `ai_requests.cost_usd`).
- Frontend: `console.log` production kodda qoldirilmaydi (ESLint `no-console`, **taklif**: CI'da majburlanadi).

### 5.3 Audit jurnali (ilova log'idan alohida)

`audit_log` (`tenant_id, user_id, action, entity, entity_id, before, after, ip, device_id, at`) — moliyaviy/huquqiy ta'sirli amallar uchun, `structlog` emas, DB yozuvi (`15-xavfsizlik-va-audit.md` §6). Majburiy qamrov: huquq/limit o'zgarishi, limitdan yuqori tasdiqlash/rad etish, `debts.forgive`, narx tasdig'i, hujjat bekor qilish, davlat hisoboti tuzatish, platform admin amali, login/parol/PIN/qurilma voqealari, sir rotatsiyasi, ma'lumot eksporti. Ilova DB rolidan bu jadvalga `UPDATE`/`DELETE` huquqi **olib tashlanadi** — faqat `INSERT`/`SELECT`.

---

## 6. Testlash

Manba — `23-backend-arxitekturasi.md` §6, `24-frontend-arxitekturasi.md` §4, `27-backlog.md` "tayyor" ta'rifi.

### 6.1 Backend

| Qatlam | Vosita | Qamrov |
|---|---|---|
| Domain/bitlik | `pytest` + `factory-boy` | Posting qoidalari — **sonli misollar** (FIFO/AVECO, QQS, qarz limiti, chegirma manfiy narxga olib kelmasligi); har holat Given/When/Then |
| Integratsiya | `pytest-asyncio` + `testcontainers[postgres]` | Haqiqiy Postgres: posting tranzaksiyasi, parallel ikki sotuv bir oxirgi tovarga (`FOR UPDATE`), recost job, Alembic migratsiya oxirigacha |
| RLS izolyatsiya | `testcontainers[postgres]` | Ikki tenant, A yozgan qator B kontekstidan ko'rinmasligi; RLS **ataylab o'chirilgan** holat ham (ikkinchi himoya qatlami tekshiruvi); worker: tenant A job B'ni ko'rmaydi, `tenant_id`'siz job rad etiladi |
| OAuth/autentifikatsiya | `testcontainers[postgres,redis]`, `httpx.AsyncClient` — **mock yo'q** | To'liq Authorization Code+PKCE, refresh rotatsiya+reuse detection, revoke/introspect, obuna lokaut, brute-force |
| Kontrakt | `schemathesis` | Ishga tushirilgan `/openapi.json`'idan avtomatik so'rov — orval generatsiyasi bilan mos kelishini kafolatlaydi |
| E2E (tanlab) | `httpx.AsyncClient` + `pytest-asyncio` | Bitta oqim boshidan oxirigacha: sotuv → qaytarish → buxgalteriya → hisobot |

**Majburiy har PR'da** (posting/registr/huquq o'zgarsa): tegishli bitlik test + (registr o'zgargan bo'lsa) integratsiya testi yangilangan/qo'shilgan; CI'da `ruff`, `mypy app`, `pytest`, Alembic `upgrade head`, `schemathesis` — barchasi yashil.

### 6.2 Frontend

| Vosita | Qamrov |
|---|---|
| `vitest` + `@testing-library/react` | Model (Effector store/effect/sample) va UI komponent bitlik testlari |
| `msw` | API mock — orval generatsiya qilgan klient funksiyalarini chaqiradi, haqiqiy backend emas |
| `playwright` | E2E — kamida POS asosiy oqimi (chek yaratish → to'lov → chop etish/elektron chek) va bitta back-office hujjat oqimi |

**Majburiy har PR'da**: yangi/o'zgargan Effector model uchun kamida bitta `vitest` testi; `eslint` + `tsc --noEmit` xatosiz; `npm run api:gen --check` orqali OpenAPI↔orval drift yo'qligi tasdiqlangan.

### 6.3 Umumiy

- Pul hisob-kitobi test-vektorlari (`shared/money-vectors.json`) — backend va frontend **bitta fayldan** o'qiydi (3.2–3.3-bo'lim), ikki tomonda alohida qo'lda yozilmaydi.
- Yangi ruxsat kodi qo'shilsa — standart matritsa testi (`15-xavfsizlik-va-audit.md` §2.2) yangilanadi.
- 1C integratsiyasi (Bosqich 7): server testlari 1C'siz — protokol darajasidagi soxta agent bilan (`31-qabul-testlari.md` M19); real 1C bazadagi tekshiruv — faqat pilot oldi testlari P-01…P-22 (`33` §16.1), CI'da emas.

---

## 7. Git ish oqimi

Spec bu mavzuda aniq qoida belgilamagan (`23`/`24`da CI bosqichlari bor, lekin branch/commit konventsiyasi yo'q) — quyidagi band **taklif (asoschi tasdiqlaydi)**, CI bosqichlari esa `23-backend-arxitekturasi.md` §7.1dan **aynan ko'chirilgan** (bu qism taklif emas).

### 7.1 Branch nomlash — taklif

| Turi | Naqsh | Misol |
|---|---|---|
| Yangi funksiya | `feat/<qisqa-tavsif>` | `feat/debt-writeoff-posting` |
| Xato tuzatish | `fix/<qisqa-tavsif>` | `fix/shift-variance-rounding` |
| Faqat spec | `spec/<qisqa-tavsif>` | `spec/kod-uchun-atamalar` (joriy branch nomi shu uslubga mos) |
| Texnik qarz/refaktor | `chore/<qisqa-tavsif>` | `chore/ruff-strict` |

### 7.2 Commit xabari — Conventional Commits, ingliz tilida — taklif

`<tip>(<qamrov>): <qisqa tavsif>`, tip — `feat`/`fix`/`docs`/`test`/`chore`/`refactor`; qamrov — modul nomi (`sales`, `debts`, `web/pos`). Masalan: `feat(debts): add debt write-off posting service`. Spec fayliga tegishli o'zgarish — `docs(spec): ...`.

### 7.3 PR hajmi — taklif

Kichik, bitta mantiqiy o'zgarish bir PR'da (bitta modul/bitta hujjat turi oqimi). Katta "vertikal bo'lak" (`27-backlog.md` bosqich tushunchasi) bir nechta kichik PR'ga bo'linadi: DB migratsiya → backend service+API → frontend sahifa, har biri alohida tekshiriladi.

### 7.4 Spec-first qoidasi — spec'dan, taklif emas

`00-README.md` §Qoidalar, 1–2-band: xulq-atvorni o'zgartiradigan kod o'zgarishi **shu PR'da** tegishli spec faylini ham yangilaydi (masalan yangi maydon: `11` model → `12` DB → `17`–`20` API → `07` ekran) va kerak bo'lsa `01-qarorlar.md`ga qator qo'shiladi. Spec'da yo'q/noaniq narsa kodda o'zboshimchalik bilan hal qilinmaydi — avval faylga yoziladi (yoki `26-ochiq-savollar-reestri.md`ga), keyin kod yoziladi.

### 7.5 CI gates — `23-backend-arxitekturasi.md` §7.1dan, kengaytirilgan

| # | Bosqich | Manba |
|---|---|---|
| 1 | `ruff check` + `ruff format --check`, `mypy --strict app` (yangi kod uchun majburiy, qaror #57) | 23 §7.1, 01 #57 |
| 2 | `pytest` (bitlik + `testcontainers` CI runner servisi sifatida) | 23 §7.1 |
| 3 | Alembic: `alembic upgrade head` bo'sh bazada | 23 §7.1 |
| 4 | `schemathesis run` — ishga tushirilgan API'ga qarshi | 23 §7.1 |
| 5 | `openapi.json` eksport + frontend `npm run api:gen --check` — sxema drift bo'lsa build qizil | 23 §7.1, 10 §3 |
| 6 | Frontend: `eslint` (pul qoidasi bilan), `tsc --noEmit`, `vitest` | 24 §4, 01 #57 |
| 6a | Xavfsizlik: `pip-audit` (backend), `npm audit --audit-level=high` (frontend), `gitleaks` (butun repo) — topilma bo'lsa build qizil | 01 #57 |
| 6b | `.env.example` mavjudligi va `Settings` maydonlari bilan mosligi (har kerakli o'zgaruvchi nomi bor, qiymatlar bo'sh) | 01 #57 |
| 7 | Docker image build + (`main`da) registry push | 23 §7.1 |

CI platformasi — GitHub Actions (`26-ochiq-savollar-reestri.md` #60). `agent-1c/` uchun alohida Windows job — 1.3-band jadvali.

**Bosqich 0 spike'lari** (qaror #57, `27-backlog.md` Bosqich 0): (a) `zxing-cpp` GS1 DataMatrix (FNC1) dekod/enkod — `tests/fixtures/datamatrix` test-vektorlari (AI 01/21/91/92, GS ajratgichi); mos kelmasa server zahirasi `bwip-js` (Node) (`26` #62); (b) shrift — tizim shrifti; U+02BB (`oʻ gʻ`) va kirill glif skrinshot-testi (Playwright, Windows/Android/iOS), yetishmasa self-hosted Noto Sans (offline kesh, `08` §2).

---

## 8. "Tayyor" ta'rifi (Definition of Done)

`27-backlog.md`dagi "Har bir vazifa uchun 'tayyor' ta'rifi" — **yagona rasmiy ro'yxat**, bu bo'lim uni checklist shakliga keltiradi va 6–7-bo'lim bilan bog'laydi:

- [ ] Spec'dagi tegishli US qabul mezonlari avtomatik test bilan qoplangan.
- [ ] Posting/registr mantig'i o'zgargan bo'lsa — 2.2-bandidagi kabi **sonli misol** testi yangilangan (`13-provodka-qoidalari.md` bilan izchil).
- [ ] RLS izolyatsiya testi CI'da yashil (yangi `tenant_id`li jadval qo'shilgan bo'lsa — RLS siyosati bor, 4.2-band).
- [ ] OpenAPI → orval generatsiyasi CI'da yashil (drift yo'q).
- [ ] `uz` va `ru` tarjima kalitlari qo'shilgan (hech bo'lmasa boshlang'ich matn, UX-yozuvchi keyin tasdiqlaydi).
- [ ] Offline ta'siri ko'rib chiqilgan: yangi hujjat/amal `client_event_id` orqali offline kelishi mumkinmi, `16-offline-sync.md`ga mos (agar tegishli bo'lsa).
- [ ] Tegishli amal `audit_log`ga yoziladi (agar 5.3-bandidagi ro'yxatga kirsa).
- [ ] Yangi ruxsat kodi — `15-xavfsizlik-va-audit.md` §2.1 katalogiga va standart matritsaga qo'shilgan.
- [ ] Xulq-atvor o'zgargan bo'lsa — tegishli spec fayli(lari) shu PR'da yangilangan (7.4-band).
- [ ] Yangi xato kodi — `17-api-umumiy.md` §15 katalogiga qo'shilgan, boshqa joyda qayta ixtiro qilinmagan.
- [ ] `ruff`/`mypy` (backend) yoki `eslint`/`tsc` (frontend) toza, test suite yashil (6-bo'lim).

---

## 9. Spec↔kod bog'lanishi

- Har commit/PR tavsifida **US-id** (`US-M08-05` kabi) yoki **spec bo'lim raqami** (`13-provodka-qoidalari.md §2.14`) ga havola — qaysi talab bajarilayotgani kod review'da tekshirilsin uchun. Format — **taklif**: PR sarlavhasida `[US-M08-05]` yoki tavsifda "Spec: `13-provodka-qoidalari.md` §2.14".
- **OpenAPI — yagona kontrakt**: FastAPI'dan avtomatik generatsiya qilingan `/openapi.json` — frontend `orval` uchun yagona manba (`24-frontend-arxitekturasi.md` §3). Qo'lda yozilgan TS tip/DTO **taqiqlanadi**; agar generatsiya noto'g'ri tip bersa — Pydantic schema (backend) tuzatiladi, frontendda patch qilinmaydi.
- `operation_id` o'zgarsa — orval generatsiya qilgan funksiya nomi o'zgaradi, bu **breaking** frontend o'zgarishi, shu PR'da ikki tomon birga yangilanadi.
- Yangi API endpoint — avval tegishli `17`–`20` faylda (yoki ularning davomi) tasvirlanadi, keyin FastAPI router yoziladi (spec-first, 7.4-band); aks holda endpoint "spec'da yo'q" deb hisoblanadi va keyingi tekshiruvda qaytariladi.
- `29-atamalar-lugati.md` — yangi jadval/ustun/ruxsat kodi qo'shilganda shu faylga ham atama qo'shiladi (domen guruhiga mos).

---

## 10. Xavfsizlik qoidalari

Manba — `15-xavfsizlik-va-audit.md` §4, `23-backend-arxitekturasi.md` §7.3.

- **Sirlar repo'da hech qachon saqlanmaydi**: DB parol, Redis parol, Click/Payme kalitlari, Claude API kaliti, SMS/Telegram token, OAuth `signing_keys` — kod/`.env`da emas — o'z sir yechimi (SOPS/age yoki o'z-hosted Vault; UzCloud'da KMS/secret store yo'q, qaror #65) yoki muhit o'zgaruvchisi orqali. `.gitignore`da `.env` bor; `.env.example` **majburiy** (qaror #57): barcha kerakli o'zgaruvchi nomi bilan, qiymat **bo'sh**, repo'da saqlanadi; `gitleaks` CI'da sir sizishini to'xtatadi.
- `app/core/config.py` prod-xavfsizlik guard'i (`model_validator`) — `environment == "prod"` bo'lsa: auth yoqilmagan yoki standart (`_INSECURE_DEFAULT`) maxfiy kalit qolgan bo'lsa **ishga tushmaydi**; `ai_mode == "cli"` prodda **taqiqlangan** (faqat `api`).
- Parol/PIN — **argon2id** (`passlib[argon2]`/`argon2-cffi`), boshqa hash algoritmi ishlatilmaydi.
- JWT/JWKS — **joserfc** (EdDSA/ES256); OAuth 2.0 protokol skeleti — **Authlib**. Qo'lda JWT encode/decode yozilmaydi.
- CSRF — sinxronizator-token (`itsdangerous`, `GET /api/v1/auth/csrf`), CSRF cookie yo'q; Bearer (Android) so'rovlar CSRF tekshiruvidan ozod.
- Dependency audit — CI'da majburiy (qaror #57): `pip-audit` (backend), `npm audit --audit-level=high` (frontend), `gitleaks` (7.5-band 6a).
- **CSP** — qat'iy (qaror #57): `default-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`, inline skript yo'q; tashqi manba faqat aniq ruxsat etilgan API domenlari (`connect-src`), Do'kon agenti uchun `http://127.0.0.1:<port>` (qaror #60).
- **AI'ga shaxsiy ma'lumot** — Claude'ga yuboriladigan har so'rov maskalash quvuridan o'tadi (o'chirib bo'lmaydi), `ai_cross_border_enabled=false` bo'lsa rasm yuborilmaydi (qaror #61); maskalashni chetlab o'tadigan to'g'ridan-to'g'ri SDK chaqiruvi taqiqlangan.
- PII logga tushmaydi (5.2-band); `audit_log` immutable, DB roli darajasida `UPDATE`/`DELETE` huquqisiz (5.3-band).
- Platform admin bypass (`platform_admins`) — faqat ichki admin panel yo'li, oddiy API endpoint hech qachon `tenant_id`siz ishlamaydi (4.2-band); har platform admin amali audit'ga majburiy yoziladi.
- **1C integratsiyasi**: server 1C parolini, to'liq ulanish satrini va agent maxfiy kalitini **hech qachon** olmaydi/saqlamaydi/loglamaydi; agentga ish faqat Ed25519 imzoli vazifa (`signing_keys.purpose='onec_task'`), faqat oq ro'yxatdagi `kind`, ixtiyoriy 1C kodi va jismoniy o'chirish yo'q; `/onec-agent/*` — faqat agent tokeni (`aud=urn:erp:onec-agent`), so'rov tanasidagi tenant e'tiborga olinmaydi (`33-1c-integratsiya.md` §9, §15.2).
- Fayl yuklash — ruxsat etilgan tur/hajm chegarasi (`17-api-umumiy.md` §12) serverda tekshiriladi, faqat frontend validatsiyasiga ishonilmaydi.

---

## Ochiq savollar

1. Hal qilingan: factory + `Depends` (`26-ochiq-savollar-reestri.md` #59).
2. Hal qilingan: GitHub Actions (`26-ochiq-savollar-reestri.md` #60).
3. Hal qilingan: `mypy --strict` va frontend lint/test CI qadamlari — qaror #57 (7.5-band).
4. Hal qilingan: ESLint pul qoidasi — qaror #57 (3.3-band).
5. Hal qilingan: `.env.example`, `pip-audit`/`npm audit`/`gitleaks`, CSP — qaror #57 (10-bo'lim).
6. `agent-1c/` o'rnatuvchi vositasi va test freymvorki — `34-1c-agent.md` da tanlanadi; OV kod-imzolash sertifikati — `26-ochiq-savollar-reestri.md` #105 (OQ-046).

## Manbalar

- `spec/kod-uchun/23-backend-arxitekturasi.md` — repo tuzilmasi, posting naqshi, tenant tranzaksiya, test strategiyasi, CI (asosiy manba).
- `spec/kod-uchun/24-frontend-arxitekturasi.md` — frontend tuzilma, Effector naqshi, kutubxonalar.
- `spec/kod-uchun/17-api-umumiy.md` — nomlash, xato konverti/katalogi, idempotentlik.
- `spec/kod-uchun/15-xavfsizlik-va-audit.md` — RLS, ruxsat kodlari, audit, sirlar.
- `spec/kod-uchun/11-malumotlar-modeli.md`, `12-db-sxema.md`, `13-provodka-qoidalari.md` — ma'lumot modeli, DB konventsiyasi, provodka.
- `spec/kod-uchun/01-qarorlar.md` #24, #26 — resurs nomlash va pul/decimal qarori.
- `spec/kod-uchun/08-dizayn-tizimi.md` §0.1 — pul hisob-kitobi frontend qoidasi.
- `spec/kod-uchun/27-backlog.md` — "tayyor" ta'rifi, bosqich tushunchasi.
- `spec/kod-uchun/29-atamalar-lugati.md` — atama↔kod nomi xaritasi.
- `spec/kod-uchun/33-1c-integratsiya.md` §4, §9, §15; `34-1c-agent.md` — `onec_integration` moduli va `agent-1c/` repo konventsiyasi.

**ACCEPT natijasi: `spec/02-arxitektura` texnik review topilmalari**

15 ta topilmadan 9 tasi QABUL, 6 tasi QISMAN (tuzatilgan yechim bilan), RAD yo'q. Hech qanday fayl o'zgartirilmadi. Quyida har bir topilma uchun dalil va yoziladigan aniq matn berilgan.

Review'da yo'q, lekin tekshiruvda topilgan uchta qo'shimcha muammo bor:
- **`SET LOCAL` parametr bilan ishlamaydi.** 09:101 dagi `SET LOCAL app.tenant_id = :tid` asyncpg'da `$1` bilan yuboriladi. PostgreSQL `SET` buyrug'i parametr qabul qilmaydi, shuning uchun bu sintaksis xatosi. To'g'ri yo'l: `SELECT set_config('app.tenant_id', :tid, true)`. 2- va 5-bandlarga kiritildi.
- **03:291 dagi `POST /sales/lines`.** U kassa savatchasini serverda yozayotgandek ko'rinadi, bu local-first POS bilan ziddiyat. 1-bandda tuzatildi.
- **Tenant izolyatsiyasi ham bir-biriga zid.** 05:9 "RLS — yagona mexanizm" deydi, 09:10 esa "ikki qatlam" deydi. Bundan tashqari `SET LOCAL` o'zi alohida himoya qatlami emas. 9-bandda tuzatildi.

---

**1. QABUL (KRITIK) — onlayn sotuv kontrakti**

Dalil: `POST /sales` 00:71, 03:111 va 09:175 da bor. 04 §4.1 (135–139) va 10:9, 10:73 esa faqat `/sync/push` ni ko'rsatadi.

Qaror: POS'ning barcha hujjatlari internet bor-yo'qligidan qat'i nazar faqat outbox orqali `/sync/push` bilan yuboriladi.

- **00:71**, yangi matn: "**Kassa sotuvi (onlayn):** veb-kassa → lokal yozuv (Dexie outbox, `client_event_id`) → `POST /sync/push` (darhol, bitta voqea) → backend: hujjat + qoldiq registri + qarz/kassa harakati + buxgalteriya provodkasi **bitta tranzaksiyada** → navbatga "OFD'ga yuborish" ishi → worker → OFD → fiskal belgi keyingi pull'da veb-kassaga qaytadi. POS uchun alohida `POST /sales` yo'q — onlayn va offline yo'l bitta (`16-offline-sync.md` §4.1)."
- **03:110–112 (mermaid)**: `POST /sales (Idempotency-Key = client_event_id)` o'rniga `POST /sync/push {events:[sale.created]}`. `201 Created (sale_id, status=fiscal_pending)` o'rniga `results:[{status: accepted, server:{id, number}}] (fiscal_pending)`. `W-->>POS: fiskal belgi/QR (poll yoki websocket)` o'rniga `POS: fiskal belgi/QR keyingi GET /sync/pull'da`.
- **03:291**: `POST /sales/lines (marking_code bilan)` o'rniga `POST /marking/verify {code}`, ostiga izoh: "(faqat tekshiruv, hech narsa yozmaydi; savatcha lokal)".
- **09:166–186 (mermaid)**: `participant API as FastAPI /sync/push`. `C->>API: POST /sync/push (voqea: sale.created)`. `API->>DB: sync_receipts: client_event_id oldin bormi?`. Javob: `results[accepted]`.
- **09 §3, "Idempotency-Key" qatori oxiriga**: "`/sync/push` bundan mustasno: dedupe har voqea bo'yicha `sync_receipts.client_event_id` orqali (`16-offline-sync.md` §3.1). `Idempotency-Key` faqat back-office REST yozuvchi so'rovlariga tegishli."
- **08:150**: "`Idempotency-Key` = mahalliy event ID" o'rniga "har voqeada `client_event_id` (UUIDv7) — server `sync_receipts` bilan dedupe qiladi; POS hujjatlari uchun alohida REST endpoint yo'q".

**2. QISMAN (KRITIK) — tranzaksiya chegarasi**

Dalil: SQLAlchemy hujjatida aytilishicha, `Session.begin()` "when used to begin the outermost transaction, an error is raised if this Session is already inside of a transaction" (https://docs.sqlalchemy.org/en/20/orm/session_api.html; https://github.com/sqlalchemy/sqlalchemy/discussions/6756).

Nega "`get_session` da bir marta begin" yetmaydi:
- `/sync/push` har voqeani alohida tranzaksiyada qayta ishlashi shart (04:92).
- Worker job'lari ham tenant kontekstiga muhtoj.
- yield-dependency ichidagi commit javob yuborilgan vaqtga nisbatan qachon bajarilishiga tayanmaslik kerak.

Qaror: yagona `tenant_transaction` helper ishlatiladi va `autobegin=False` qo'yiladi.

09 §1 dagi kod bloki (97–103) o'rniga:

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

Kod blokidan keyin qo'shiladigan matn: "Tranzaksiya faqat `tenant_transaction()` orqali ochiladi. `autobegin=False` sababli undan tashqarida `execute` xato beradi, shuning uchun tenant kontekstisiz so'rov jismonan mumkin emas. `SET LOCAL ... = :param` ishlatilmaydi, chunki PostgreSQL `SET` parametr qabul qilmaydi; o'rniga `set_config(..., true)` ishlatiladi (tranzaksiya-lokal). Posting xizmati, `/sync/push` (har voqea uchun alohida `tenant_transaction`) va worker job'lari ham aynan shu helper'dan foydalanadi. Ichki savepoint kerak bo'lsa — `session.begin_nested()`."

- **09:121**: "`async with session.begin():`" o'rniga "`async with tenant_transaction(session, tenant_id):`".
- **05:171**: "`SET app.tenant_id = '<tenant_uuid>'`" o'rniga "`SELECT set_config('app.tenant_id', $1, true)` (tranzaksiya-lokal, `SET LOCAL` ekvivalenti)".

**3. QABUL (KRITIK) — treepoem/Ghostscript litsenziyasi**

Dalil:
- treepoem PyPI sahifasi: "You'll also need Ghostscript installed."
- Artifex: "You cannot deploy our open-source as part of a server-based application or service, without disclosing your own application's full source code under AGPL" (https://artifex.com/licensing).
- bwip-js 4.11.4 (2026-08-19) MIT litsenziyali va `gs1datamatrix` formatini qo'llaydi.
- zxing-cpp 3.1.1 (2026-07-29) Apache-2.0 litsenziyali, `create_barcode()` funksiyasi bor.

Qarorni yozish uchun matnlar:
- **09:250** yangi matn: "| Shtrix-kod/yorliq | **python-barcode** (MIT; EAN-13, Code128) + **zxing-cpp** (Apache-2.0; DataMatrix/QR server PDF uchun) | Yorliqlar asosan brauzerda `bwip-js` (MIT, GS1 DataMatrix ham) bilan chiziladi. `treepoem` **taqiqlangan**: Ghostscript AGPL/tijoriy — SaaS'da manba kodini ochish yoki Artifex litsenziyasini talab qiladi |".
- **09:11**: "`python-barcode` + `treepoem`" o'rniga "`python-barcode` + `zxing-cpp` (Ghostscript/AGPL'siz)".
- **08:138**: "bwip-js (yoki JsBarcode)" o'rniga "bwip-js (MIT; EAN-13, Code128, GS1 DataMatrix — asosiy yorliq renderer)".
- Ochiq savolga yangi band: "zxing-cpp'ning GS1 DataMatrix (FNC1) chiqishi Asl belgisi talabiga mosligi birinchi sprintda sinab ko'riladi; mos kelmasa server yorlig'i ham bwip-js (Node) orqali."

**4. QISMAN (O'RTA) — arq texnik xizmat rejimida**

Dalil:
- arq README: "In maintenance only mode: arq is in maintenance only mode, see #510". E'lon 2025-10-18 da qilingan, faqat xavfsizlik tuzatishlari chiqadi. Oxirgi reliz 0.28.0 (2026-04-16).
- Shuning uchun 09:218 dagi "bitta muallif tomonidan faol qo'llab-quvvatlanadi" iborasi noto'g'ri.
- SAQ 0.26.4 (2026-05-21): MIT, asyncio, Redis yoki Postgres broker, CronJob, o'rnatilgan monitoring UI.

Qaror: shunchaki "muqobil" deb tilga olish yetmaydi — **SAQ asosiy tanlov** bo'ladi va `JobQueue` porti ortiga yashiriladi (`outbox_jobs` haqiqat manbai bo'lib qoladi).

- **09:9**: "**Navbat kutubxonasi — `saq`** (4-bo'lim): asyncio, Redis broker (stack'da bor), ichki `CronJob`, o'rnatilgan monitoring UI. `arq` 2025-10 dan beri faqat texnik xizmat rejimida (python-arq/arq#510) — yangi loyiha uchun tanlanmaydi."
- **09 §4 jadvali**: `saq` ustuni qo'shiladi; arq qatorida "Texnik xizmat" katagi "Faqat xavfsizlik tuzatishlari (2025-10, #510)" bo'ladi.
- **Qaror matni**: "**Qaror: `saq`**… Navbat `app/core/queue.py`dagi `JobQueue` porti ortida; `outbox_jobs` holat manbai bo'lgani uchun kutubxona almashtirish arzon. arq'dagi "monitoring paneli yo'q" kamchiligi SAQ UI bilan yopiladi."
- arq nomini SAQ bilan almashtirish kerak bo'lgan qatorlar: 09:58, 60, 61, 86, 172, 234, 235, 297–298; 00:60, 61, 106; 06:89.

**5. QABUL (O'RTA) — pooler qarori**

Dalil:
- asyncpg FAQ: pgbouncer "when in the 'transaction' or 'statement' pooling mode, does not support prepared statements". Yechimi: `statement_cache_size=0` yoki asyncpg'ning o'z pool'i.
- SQLAlchemy asyncpg dialect hujjatida "Prepared Statement Name with PGBouncer" bo'limi bor.

**09 §9 ga yangi qator:**

"| Ulanish pool'i | MVP: tashqi pooler yo'q — SQLAlchemy `AsyncAdaptedQueuePool` (asyncpg), `pool_size`/`max_overflow` × api+worker nusxalari soni DBaaS `max_connections` dan kichik. Pooler qo'shilsa (PgBouncer, **transaction** rejimi): PgBouncer ≥1.21 `max_prepared_statements` yoqiladi, yoki asyncpg `prepared_statement_cache_size=0` + `prepared_statement_name_func` (uuid nomlar). Session darajasidagi `SET` taqiqlanadi — tenant faqat `set_config(..., true)` bilan tranzaksiya ichida (1-bo'lim). UzCloud DBaaS'da o'rnatilgan pooler bor-yo'qligi — ochiq savol |"

**6. QABUL (O'RTA) — sessiya muddati va 401**

Dalil: 05 §1.3 da veb sessiya TTL'i yo'q. 04 §3.4 va §9 faqat `403 device_revoked` ni beradi. 08:113 da "401 → login" deyilgan, 04:262 esa logout'da Dexie'ni to'liq o'chiradi.

- **05 §1.3, veb qatoriga**: "Sessiya: sirpanuvchi bo'sh turish muddati 12 soat, mutlaq muddat 7 kun (**taxmin**). Mutlaq muddat 48 soatlik offline oynadan uzun bo'lishi shart."
- **04 §3.4 ga yangi abzats:**

"**401 (sessiya tugagan)** — rad etish emas: voqealar `pending` holatida qoladi, `rejected` bo'lmaydi; push to'xtatiladi. POS ustida qayta kirish oynasi (parol yoki PIN) ochiladi, bunda **Dexie tozalanmaydi** — bu logout emas. Qayta kirishda server yangi sessiyani avvalgi `device_id`ga bog'laydi (boshqa tenant/qurilma bo'lsa push'ga ruxsat yo'q), keyin push `seq` tartibida davom etadi. `403 device_revoked` — 9-bo'lim."

- **08:113**: "401 → login" o'rniga "401 → qayta autentifikatsiya oynasi (POS'da outbox/Dexie saqlanadi; to'liq logout faqat foydalanuvchi tanlovi bilan)".

**7. QABUL (O'RTA) — CSRF mexanizmi**

Dalil: namuna loyihaning `cookie-auth.ts` faylida (65–86-qatorlar) token `GET /api/auth/csrf` dan olinadi va xotirada (`let csrfToken`) saqlanadi; interceptor uni `X-CSRF-TOKEN` header'ida yuboradi. Ya'ni namuna double-submit cookie emas, sinxronizator-token usulini ishlatadi.

Qaror: namunadagi usul olinadi.

- **09:203** yangi matn: "Auth | HttpOnly, Secure, SameSite=Lax sessiya cookie. CSRF — sessiya ID'ga bog'langan, `itsdangerous` bilan imzolangan token: `GET /api/v1/auth/csrf` → klient xotirada saqlaydi → yozuvchi metodlarda `X-CSRF-Token` header. CSRF cookie yo'q (double-submit emas). Noto'g'ri yoki eskirgan token → `403 {code: CSRF_INVALID}` → klient tokenni bir marta qayta oladi va so'rovni takrorlaydi. Bearer qurilma tokeni (Android) CSRF tekshiruvidan ozod."
- **09:245**: "double-submit token uchun" o'rniga "sessiyaga bog'langan sinxronizator-token uchun".
- **08:112**: "CSRF tokeni" o'rniga "CSRF tokeni (`GET /auth/csrf` dan, xotirada keshlanadi — namunadagi `getCsrfToken`)".
- **09 Ochiq savol 5** yopiladi.

**8. QABUL (O'RTA) — frontend UUIDv7 generatori**

Dalil: `uuid` paketining eng so'nggi versiyasi 14.0.3 (2026-10-10), MIT, faqat ESM; `v7()` 10.0.0 versiyadan beri (2024-06) bor.

**08 §4 ga yangi qator:** "| UUIDv7 (`client_event_id`, lokal hujjat ID) | uuid (`v7()`, ≥10) | `crypto.randomUUID()` faqat v4 beradi — ishlatilmaydi |"

**9. QISMAN (O'RTA) — filial bo'yicha cheklash**

Iqtibos aniqligi: 05:10 qatori platform admin haqida. "Ikki qatlam" tamoyili aslida 09:10 da va u faqat tenant'ga tegishli. Filial qarori 05:162 va 05 Ochiq savol 3 da ochiq qolgan.

Qaror: filial uchun RLS predikati qo'shilmaydi. Sabablar: `branch_ids=[]` "hammasi" degan ma'noni bildiradi; M06 ko'chirishi ikki filialga birdaniga tegadi; Egasi filiallararo hisobotlar ko'radi. Filial cheklovi **yagona qatlam** ekani ochiq yoziladi.

- **05:162** va **05 Ochiq savol 3** o'rniga:

"**Qaror: filial cheklovi — yagona qatlam, ilova darajasida** (RLS'da emas): `current_branch_scope` dependency → `BranchScopedRepository` bazaviy klassi har so'rovga `branch_id = ANY(:scope)` qo'shadi (ko'chirishda `from_branch_id`/`to_branch_id`). Har bir filialli endpoint uchun majburiy integratsion test: boshqa filial ma'lumoti → 403/bo'sh natija. Tenant izolyatsiyasi esa ikki qatlamda qoladi."

- **09:10** (tenant ikki qatlami aniq bo'lishi uchun): "(a) ilova qatlami — `TenantMixin` modellariga SQLAlchemy `with_loader_criteria` orqali global `tenant_id` filtri; (b) PostgreSQL RLS (`set_config('app.tenant_id', …, true)` + siyosat). (b) (a) buzilsa ham himoya qiladi va aksincha (09 §6 RLS-o'chirilgan testi shu (a) ni tekshiradi)."
- **05:9**: "yagona mexanizmi" o'rniga "asosiy (DB darajasidagi) mexanizmi; ilova filtri — ikkinchi qatlam (`23-backend-arxitekturasi.md`, 4-xulosa)".

**10. QABUL (KICHIK) — react-day-picker versiyasi**

Dalil:
- shadcn calendar registry'si `react-day-picker@latest` va `date-fns` ni o'rnatadi.
- `latest` hozir 10.0.2 (2026-09-30). v10 da "Deprecated v9 compatibility APIs were removed" (https://daypicker.dev/upgrading), paket nomi esa `@daypicker/react` ga o'zgargan.

**08:133** yangi matn: "| Sana tanlash | react-day-picker **^9.14** (shadcn calendar; v10 — `@daypicker/react`, v9 moslik API'lari olib tashlangan, alohida sinovdan keyin) | shadcn calendar `date-fns` ni tranzitiv olib keladi — UI formatlash baribir dayjs |"

**11. QABUL (KICHIK) — onScan.js eskirgan**

Dalil: npm'da `onscan.js` ning oxirgi versiyasi 1.5.2, 2020-05-18 da chiqqan.

**08:139** yangi matn: "| Shtrix-kod skaner | o'z kichik hook'i `useBarcodeWedge` (`shared/lib/scanner`: belgilar orasidagi interval < ~30 ms + Enter suffiksi, input fokusidan mustaqil) | onScan.js 2020 dan beri yangilanmagan — ishlatilmaydi |"

**12. QABUL (KICHIK) — HTTP 425**

Dalil: 425 Too Early (RFC 8470) TLS early-data qayta yuborilishi uchun mo'ljallangan. IETF draft-ietf-httpapi-idempotency-key-header-07 esa: "If the request is retried, while the original request is still being processed, the resource SHOULD reply with an HTTP 409"; boshqa payload bilan qayta ishlatilgan kalit uchun 422.

- **09:199**: "(parallel takror so'rovni kutish/425)" o'rniga "(parallel takror → `409 {code: IDEMPOTENCY_IN_PROGRESS}` + `Retry-After: 1`; bir xil kalit, boshqa `request_hash` → `422 {code: IDEMPOTENCY_KEY_REUSED}`)".
- **08:113** ga qo'shimcha: "`409 IDEMPOTENCY_IN_PROGRESS` — forma xatosi emas: effekt `Retry-After`dan keyin xuddi shu kalit bilan avtomatik takrorlanadi (maks. 3 marta). `422 IDEMPOTENCY_KEY_REUSED` — dasturiy xato, Sentry'ga."

**13. QISMAN (KICHIK) — orval chiqish shakli**

Dalil: orval hujjatiga ko'ra `axios` klienti "generates a factory function" — `getPetsApi() => ({ listPets })` ko'rinishida (https://orval.dev/docs/reference/configuration/output). `axios-functions` esa tekis funksiyalar chiqaradi.

Misolni o'zgartirish shart emas: konfiguratsiyani aniq yozish yetadi.

**08 §3 "Generatsiya" ga qo'shimcha:** "orval: `client: "axios-functions"`, `mode: "tags-split"`, `mutator` — umumiy axios instance; `override.operationName` `operation_id`dagi teg prefiksini olib tashlaydi (`debts_list_debtors` → `listDebtors`). `@shared/api/index.ts`: `export * as debts from "./generated/debts/debts";` — bundan `api.debts.listDebtors(...)` kelib chiqadi (qo'lda o'ram kodi yo'q, faqat ESM namespace re-export)."

**14. QABUL (o'rta emas, KICHIK — tasdiq)**

Dalil: fastapi-filter 3.0.0 (2026-06-03) SQLAlchemy >=2.0,<2.1 ni talab qiladi. `contrib/sqlalchemy/filter.py` da `def filter(self, query: Query | Select)` va `def sort(self, query: Query | Select)` bor — ular sessiyadan mustaqil `Select` quradi, shuning uchun AsyncSession bilan ishlaydi. Nuqson yo'q.

**09:239** ga qo'shimcha: "`filter.sort(filter.filter(select(Model)))` → `await session.execute(...)` yoki `fastapi_pagination.ext.sqlalchemy.paginate(session, stmt)` (AsyncSession qo'llab-quvvatlanadi). Versiya: ≥3.0 (SQLAlchemy 2.0)."

**15. QISMAN (KICHIK) — Chromium-only**

Safari/IndexedDB savolini Chromium-only qarori yopadi. Printer savolini to'liq yopmaydi, faqat torayadi: WebUSB/Web Serial imkoni ochiladi, lekin uskunada sinov baribir kerak.

- **08 Ochiq savol 2** o'rniga qaror: "**Veb-kassa faqat Chromium**: Chrome/Edge (desktop) va Android Chrome, o'rnatilgan PWA sifatida; ishga tushganda `navigator.storage.persist()` so'raladi. Safari/iOS veb-kassa uchun qo'llab-quvvatlanmaydi (IndexedDB tozalanish xavfi, WebUSB/Web Serial yo'q). Back-office — barcha zamonaviy brauzerlar."
- **08 Ochiq savol 1**: "Chromium-only sababli WebUSB/Web Serial asosiy yo'l; QZ Tray/tizim printeri — zaxira. Pilot uskunasida sinab tasdiqlanadi."
- **04:246** shu qarorga havola qilsin.

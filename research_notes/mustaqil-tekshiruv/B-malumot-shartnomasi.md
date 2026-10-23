# B — Ma'lumot shartnomasi izchilligi (DB ↔ API ↔ ekran ↔ test ↔ 1C)

**Maqsad:** `spec/kod-uchun/` (commit `00dd8aa`) bo'yicha mustaqil, faqat-o'qish tekshiruvi: 12 (DB) ↔ 14/16/18/19/20/33 (API) ↔ 07 (ekranlar) ↔ 31 (testlar) ↔ 13 (provodkalar) ↔ 11 (model).
**Holat:** 2026-10-16. Spec fayllari o'zgartirilmagan.

## Usul

1. **DDL amalda ishga tushirildi.** 12 dagi 52 ta `sql` blok (401 ta operator) `postgres:16` (Docker) ga yuklandi. Natijada 136 ta jadval bor. Barcha DDL xatosiz kompilyatsiya bo'ladi. Faqat parametrli seed'lar (`:tenant_id`) va 4.2/0028 RLS blokining fayl tartibidagi takrori o'tmadi; bu kutilgan holat.
   - 5.2 tenant-provisioning seed'i (rollar, `role_permissions`, 21 ta `expense_categories`) parametrlar qo'yilganda CHECK'lardan xatosiz o'tadi.
   - 6.2 CI so'rovlari yashil: RLS'siz jadval yo'q, `erp_app`ning `auth.*` ga GRANT'i yo'q, 18 ta SECURITY DEFINER funksiyaning hammasi mavjud.
   - 33 §5 dagi 23 ta SQL blok 12 §2.11/§4.5 bilan sxema darajasida solishtirildi. Ular **aynan bir xil**, farq faqat izohlangan `updated_at` trigger'larida.
2. **Mexanik tekshiruvlar** (skript bilan):
   - Barcha backtick'li xato kodlari 17 §15 katalogida bor (191 kod).
   - Barcha ruxsat kodlari 15 §2.1 da bor (65 kod).
   - FK bog'liqligi 6.1 revizion tartibi bilan solishtirildi.
3. **Qo'lda o'qib tekshirish:** 10 ta parallel Opus sub-agent ishlatildi: 18+16, 19, 20 (2 qism), 14+33 §9, 33 §10, 07 POS, 07 BO, 31+13, 11↔12.
   - Har topilma ikki tomonning aniq qatoriga qarab tasdiqlangan.
   - Takrorlar birlashtirildi. Agentlar bir-biriga zid tavsiya bergan joylarda yagona tavsiya tanlandi (B-003, B-002).

**Daraja:**
- **kritik** — kod noto'g'ri yoziladi, CHECK/NOT NULL buziladi yoki migratsiya yiqiladi.
- **o'rta** — shartnoma nomuvofiqligi; dasturchi o'zi taxmin qilishga majbur bo'ladi.
- **kichik** — nom, izoh yoki sanoqdagi noaniqlik.

## Jami

| Daraja | Soni |
|---|---|
| kritik | 23 |
| o'rta | 88 |
| kichik | 36 ID (guruhlar ichidagi bandlar bilan — 82 band) |
| **Jami** | **147 ID** |

Toza chiqqan joylar (topilma yo'q):
- 11 ↔ 12 jadval va ustun nomlari, holat ro'yxatlari, `doc_sequences` kodlari.
- 13 dagi barcha arifmetik misollar: 12/112, FIFO/AVECO, bank tushumi, aylanma solig'i.
- 13 hisob kodlari 13 §1 va `^[0-9]{4}$` ga mos; `expense_categories` seed ↔ 13 §2.17 mos.
- 33 §10.1 indeksi ↔ §10.3 tafsilotlari: 55/55 bir xil.
- 07 BO-22/23 chaqiradigan barcha endpoint'lar mavjud.
- 34 ↔ 33 §9 agent protokoli maydonlari mos.
- 31 dagi barcha endpoint, xato kodi va HTTP status mavjud.

---

## KRITIK

**B-001** — `12-db-sxema.md:288, :304, :324` ↔ `12:3919` (0003), `12:3923` (0007)
- **Muammo:**
  - `auth.authorization_codes`, `auth.refresh_tokens` va `auth.sessions` 0003-revizionda yaratiladi. Ularda inline `client_id … REFERENCES platform.oauth_clients(id)` bor.
  - `platform.oauth_clients` esa faqat 0007 da yaratiladi, shuning uchun `alembic upgrade head` 0003 da yiqiladi.
  - Fayl tartibida yuklaganda xato ko'rinmaydi. Revizion tartibida FK tahlili buni ko'rsatdi.
- **Tuzatish:** 6.1 jadvalida `platform.oauth_clients` (+`status`, `pending_secret` CHECK) ni 0003 qatoriga ko'chiring ("auth FK'lari uchun oldin") va 0007 qatoridan olib tashlang. Jadvalning o'z FK'i yo'q, shuning uchun ko'chirish xavfsiz.
- **Muqobil:** 3 ta inline REFERENCES o'chiriladi va 0007 da `ALTER TABLE auth.* ADD CONSTRAINT fk_*_client …` kechiktirilgan FK sifatida yoziladi.

**B-002** — `18-api-kassa.md:11, :710, :711` ↔ `12:1674` (`cash_movements_reason_check`), `16:65`, `20:942`, `07:498, :506`
- **Muammo:**
  - POS xarajati ikki xil modellashtirilgan:
    - 18 va 07: `cash_movement.created` + `reason=expense` + `expense_category_id`.
    - 16 va 20 #42: alohida `expense.created` voqeasi (`expenses.category_id`).
  - DB CHECK `reason IN ('collection','deposit','owner_withdrawal','other')` — unda `expense` yo'q, shuning uchun 18 yo'li INSERT'da yiqiladi.
  - `expense_category_id` ustuni hech qayerda yo'q.
- **Tuzatish:**
  - 18:710 enum'idan `expense` ni olib tashlang, 18:711 qatorini o'chiring.
  - 18:11 ga yozing: "xarajat — `expense.created` (`source=cash`, payload 20 #42)".
  - 18 §1 indeksiga `expense.created` qatorini qo'shing.
  - 07:498/506 da POS-14 "Xarajat" → `expense.created`, ruxsat `cash.withdraw` (limit). Kassirda `expenses.create` yo'q, buni 20 #42 da aniq yozing.

**B-003** — `19-api-ombor.md:13, :216, :219, :223` ↔ `12:1357` (CHECK `draft,pending_approval,posted,rejected,cancelled`), `11:162`, qaror #25, `31:334` (QT-M09-02), `07:803`
- **Muammo:**
  - 19 da limitdan oshgan narx o'zgarishi "`202 {status:"draft"}` … `draft`da qoladi (… `pending_approval`ga o'tmaydigan yagona istisno)", rad etilsa ham `draft`.
  - Qaror #25, 11, CHECK va QT-M09-02 esa aksini aytadi: `price_changes` `pending_approval`ga o'tadigan yagona tur, rad etilsa `rejected`.
  - 07:803 to'g'ri yozilgan, 19 xato.
- **Tuzatish:**
  - 19:216 → `202 {status:"pending_approval", approval_request_id}`; istisno izohini "(`pending_approval`ga o'tadigan yagona hujjat turi, qaror #25)" ga almashtiring.
  - 19:223: tasdiqlansa → `posted`, rad etilsa → `rejected`.
  - 19:13 → `draft → pending_approval (202) → posted/rejected`.
  - 19:219 ga qo'shing: `409 DOC_INVALID_STATE` (`pending_approval`da `post`).

**B-004** — `19:898, :909` ↔ `12:2115-2116` (`ettn_documents_status_check`)
- **Muammo:** 19 `failed` holatini ishlatadi ("operator xatosi"; `submit-signed` `failed`dan). CHECK'da `failed` yo'q, shuning uchun INSERT/UPDATE yiqiladi.
- **Tuzatish:** 12:2115 CHECK'ga va 2117 izohiga `'failed'` ni qo'shing.
- **Muqobil:** 19 da xato holatida `sending → pending_signature` deb yozing.

**B-005** — `19:417, :898, :920` ↔ `12:2121` (`CHECK (einvoice_id IS NOT NULL OR transfer_id IS NOT NULL)`)
- **Muammo:**
  - Alohida kiruvchi e-TTN (`direction="in"`, e-fakturasiz) da ikkala FK ham NULL bo'ladi, shuning uchun poll INSERT'i CHECK'da yiqiladi.
  - Kirim bilan bog'lovchi ustun ham yo'q, ya'ni `goods_receipts.ettn_status` ni hisoblab bo'lmaydi.
- **Tuzatish:**
  - 12: CHECK → `CHECK (direction='in' OR einvoice_id IS NOT NULL OR transfer_id IS NOT NULL)`.
  - 12: `receipt_id UUID NULL REFERENCES app.goods_receipts(id)` qo'shing.
- **Muqobil:** 19 dan alohida kiruvchi e-TTN holatini olib tashlang.

**B-006** — `19:903, :915` ↔ `12:2108-2122` (`ettn_documents`)
- **Muammo:**
  - Javobdagi `counterparty_id` va `doc_date`, `GET /{id}` dagi `payload`, so'rovdagi `ettn_date` — bularning ustuni yo'q.
  - Jadvalda faqat `id, tenant_id, einvoice_id, transfer_id, transport_type, direction, status, operator_doc_id, created_at, updated_at` bor.
- **Tuzatish:**
  - 12 ga qo'shing: `counterparty_id UUID NULL REFERENCES app.counterparties(id)`, `doc_date DATE NULL`, `payload JSONB NOT NULL DEFAULT '{}'`.
  - 19:915 da `ettn_date` → `doc_date`.

**B-007** — `18:229, :299, :303, :325`, `16:116` ↔ `12:934-963` (`sales`da `receipt_seq` yo'q), `12:2011, :2032, :2037`
- **Muammo:**
  - Faqat qarzga (`method=debt`) sotilganda `fiscal_receipts` qatori yaratilmaydi (`fiscal.status="deferred"`).
  - Shunga qaramay 18:303 "`fiscal_receipt_seq` shunga qaramay saqlanadi" deydi. Saqlanadigan ustun yo'q, `RECEIPT_SEQ_CONFLICT` ni aniqlab bo'lmaydi va `GET /sales?fiscal_receipt_seq=` filtri ishlamaydi.
- **Tuzatish (tavsiya):**
  - 18:229 → `integer|null` (hamma to'lov `debt` bo'lsa va `credit_sale_receipt=none` bo'lsa — null).
  - 18:303 dagi "saqlanadi" jumlasini o'chiring; 16:68 va 16:116 ni ham shunga moslang.
- **Muqobil:** 12 da `sales.receipt_seq INT NULL` + UNIQUE qo'shing.

**B-008** — `18:422` ↔ `12:1061` (`return_lines.price NUMERIC(18,4)`)
- **Muammo:** API maydoni `lines[].unit_price`, turi `Money` (2 xona). DB ustuni `price`, 4 xona. Nom ham, aniqlik ham mos emas.
- **Tuzatish:** 18:422 → `price`, "o'nlik satr, 4 xona (`sale_lines.price` bilan bir xil)".

**B-009** — `20-api-moliya-admin.md:319, :320, :345-346` ↔ `12:1764` (`ledger_adjustments.branch_id UUID NOT NULL`)
- **Muammo:** `POST /ledger-adjustments` so'rovida `branch_id` yo'q, shuning uchun INSERT NOT NULL'da yiqiladi. `ledger_entries.branch_id` ham aniqlanmaydi.
- **Tuzatish:**
  - So'rovga `branch_id: UUID (majburiy)` qo'shing.
  - 320 va 346 javoblariga `branch_id`, 345 filtriga `branch_id=` qo'shing.

**B-010** — `20:1124` ↔ `20:1158, :1182`, `12:1734-1735` (`GENERATED … gross_amount - commission_amount + variance_amount`, "<0 inkassa kamomadi"), `13:316-319`
- **Muammo:** `BankSettlement` obyektida belgi va formula teskari yozilgan: "musbat — kamomad … `net = gross − commission − variance`". Boshqa barcha joylarda va DDL'da aksincha.
- **Tuzatish:** 20:1124 → "manfiy — kamomad, musbat — ortiqcha; `net_amount = gross_amount − commission_amount + variance_amount`".

**B-011** — `07-ekran-tafsilotlari.md:907, :914, :916` ↔ `20:304, :319`
- **Muammo:**
  - BO-08 filtri `GET /ledger-entries?doc_date__gte=&doc_date__lte=`. API filtri esa `entry_date__gte/__lte`.
  - Tuzatuvchi yozuv formasi `adjustment.entryDate` (`entry_date`) yuboradi, API maydoni `doc_date`.
  - Formada majburiy `account_dt`, `account_kt` va `amount` maydonlari yo'q.
- **Tuzatish:**
  - 07:916 → `entry_date__gte=&entry_date__lte=`.
  - 07:907/914 → `adjustment.docDate`.
  - Formaga qo'shing: `accountDt`, `accountKt`, `amount` (majburiy), `correctionOfPeriod` (ixtiyoriy, `YYYY-MM`), `branchId` (B-009).

**B-012** — `07:1060, :1062` ↔ `20:777`
- **Muammo:** BO-12 kassani `PATCH /cash-registers/{id}` + `archived:true` bilan arxivlaydi. PATCH tanasi faqat `{name?, version}`; arxivlash uchun alohida `POST /cash-registers/{id}/archive` bor.
- **Tuzatish:** 07:1060 → `POST /api/v1/cash-registers/{id}/archive` (`{}`); uni Ma'lumot manbai (1062) ga ham qo'shing. Indeks muammosi — B-064.

**B-013** — `07:1049, :1051` ↔ `20:732-743`
- **Muammo:** BO-12 `warehouses[].inventoryAccount` (2910/2920) ni tahrirlaydi. Omborga yozuvchi endpoint yo'q, faqat `GET /warehouses` bor.
- **Tuzatish:** 20 M14 ga qo'shing: `PATCH /warehouses/{id}` (`{inventory_account:"2910"|"2920", version}`, ruxsat `settings.branches`). 07:1062 ga `GET /api/v1/warehouses?branch_id=` ni qo'shing.

**B-014** — `07:760, :763, :1148` ↔ `19:382, :387`
- **Muammo:** BO-04 "E-ishonchnoma berish" va BO-15 "E-ishonchnomalar" ro'yxatini chaqiradigan REST endpoint yo'q. 19 da faqat `EInvoicePort.send_power_of_attorney` va `goods_receipts.poa_number` bor.
- **Tuzatish:** 19 §8/§20 ga qo'shing:
  - `POST /powers-of-attorney` (`{employee_id, valid_to, counterparty_id, po_id?}` → sign-challenge/submit-signed);
  - `GET /powers-of-attorney?status=`.
- **Muqobil:** 07 dan tugmani olib tashlang, faqat qo'lda `poa_number` qoladi.

**B-015** — `07:966` ↔ `20:20-33`, `state_reports_status_check` (`uploaded|compared|match|diff_found|correction_sent|auto_accepted`)
- **Muammo:** BO-10 "Tasdiqlangan deb belgilash" → "Holat `tasdiqlandi`". Bunday endpoint ham, DB holati ham yo'q.
- **Tuzatish:** 20 ga `POST /state-reports/{id}/confirm` (`tax.compare.review`) va CHECK'ga `confirmed` qo'shing. Muqobil: 07 dan tugmani olib tashlang.

**B-016** — `07:957, :965` ↔ `20:229`, `state_reports.correction_signature`
- **Muammo:** BO-10 "Tuzatish qayd etish" faqat izoh yozadi (`correctionNote`). API `{signed_document (E-IMZO, base64), comment}` ni talab qiladi. Ekranda E-IMZO qadami yo'q, maydon nomi ham boshqa.
- **Tuzatish:**
  - 07:965 ga E-IMZO imzolash qadamini qo'shing; `correctionNote` → `comment`.
  - 20:229 da `signed_document` → `correction_signature` (ustun nomi). `comment` ga ustun yo'q, faqat `audit_log` ga yozilishini aniq ayting.

**B-017** — `07:115` (POS-03) ↔ `18:264`, `sale_payments_method_check`
- **Muammo:** ekran enum'ida `card_manual` bor. API va CHECK `card`. `sale.created` yiqiladi.
- **Tuzatish:** `cash|card|uzqr|payme|click|uzum|debt`. "Karta (qo'lda)" faqat yorliq bo'lib qoladi.

**B-018** — `07:330-331` (POS-09) ↔ `19:594, :647`
- **Muammo:** forma maydonlari `fromBranchId`/`toBranchId`, API va `transfer.sent` esa `from_warehouse_id`/`to_warehouse_id`.
- **Tuzatish:** `fromWarehouseId`/`toWarehouseId`, validatsiya `≠ toWarehouseId`.

**B-019** — `07:344` (POS-09) ↔ `19:584, :614-618`
- **Muammo:** onlayn oqim `POST /transfers → /send` deb yozilgan. Holat mashinasi `draft → posted → sent`, `/send` faqat `posted`dan ishlaydi, aks holda `409 DOC_INVALID_STATE`. `vehicle` uchun e-TTN `registered` bo'lmasa `409 ETTN_REQUIRED`.
- **Tuzatish:** `POST /transfers` → `POST /transfers/{id}/post` → (vehicle: e-TTN `registered`, 19 §20) → `POST /transfers/{id}/send`.

**B-020** — `33-1c-integratsiya.md:3312` ↔ `33:1731-1738` (§7.1), `onec_export_batches_check3` (`accepted_at IS NULL OR status IN ('partial','mismatch')`)
- **Muammo:**
  - W-50 "natijada `mismatch → done` bo'lishi mumkin" deydi. §7.1 da bunday o'tish yo'q (yakuniy holatlar).
  - Qabul qilingan `mismatch`da `accepted_at` to'ldirilgan, shuning uchun `done`ga o'tish CHECK'ni buzadi.
- **Tuzatish (biri):**
  - 3312 dagi gapni o'chiring.
  - Yoki §7.1 ga T17 `mismatch → done` (W-50, hamma item mos) qo'shing: `accepted_by/at/reason` tozalanadi; §7.5 ga `mismatch → verified` qo'shiladi; 1738 ga "(istisno: T17)" yoziladi.

**B-021** — `31-qabul-testlari.md:304` (QT-M08-01) ↔ `12:941` (`sales_status_check` = `draft,posted,cancelled`), `18:303`, `13:117`
- **Muammo:** test `sales.status='deferred'` ni kutadi. Bunday DB qiymati yo'q; "deferred" — sync javobidagi `fiscal.status`.
- **Tuzatish:** "`sales.status='posted'`, sinxronlash javobida `fiscal.status="deferred"`".

**B-022** — `31:111` (QT-RLS-05) ↔ `12:665`
- **Muammo:** testda "`products`/`units`/`plans` kabi `tenant_id`siz global jadval" deyilgan. `app.products` tenant'li va RLS ostida, `erp_app` unga yoza oladi, shuning uchun to'g'ri implementatsiyada test yiqiladi.
- **Tuzatish:** "`platform.units`/`platform.plans`/`platform.addons` kabi".

**B-023** — `31:297` (QT-M07-08), `03:302` ↔ `13:146`
- **Muammo:** bonus birlik ("10+1") ikki xil:
  - 31 va 03 bo'yicha — 0 narxli alohida partiya.
  - 13 bo'yicha — "narx chegirmasi: partiya tannarxi = faktura summasi / umumiy miqdor".
  - FIFO'da tannarx (COGS) farq qiladi, ya'ni bir tomon albatta yiqiladi.
- **Tuzatish (biri):**
  - 31:297 va 03:302 → "bonus miqdori qatorga qo'shiladi, `unit_cost` = summa / (to'langan + bonus), 0 narxli partiya yo'q".
  - Yoki 13:146 → "bonus — `cost=0` bilan alohida qator/partiya".

---

## O'RTA

### 12 / 11 / 1C (33)

**B-024** — `33:3300` ↔ `17:389`, `33:3481`, `33:3222`
- **Muammo:** W-49 `422 ONEC_DATE_PROHIBITED`. Katalog va W-41 da `409`.
- **Tuzatish:** 33:3300 → `409 ONEC_DATE_PROHIBITED`.

**B-025** — `11-malumotlar-modeli.md:149` ↔ `11:38`, `12:638`, `15:63`
- **Muammo:**
  - 11:149 tannarxni `tenants.settings.valuation_method` dan o'qiydi. 11:38 va 12:638 esa bu kalit olib tashlanganini, manba `valuation_method_history` ekanini aytadi.
  - 15:63 hali `settings.valuation_method='AVECO'` seed qiladi.
- **Tuzatish:**
  - 11:149 → "`valuation_method_history` (joriy = eng oxirgi `valid_from ≤ doc_date`)".
  - 15:63 → `valuation_method_history` ga `aveco` qatori.

**B-026** — `33:2802` ↔ `33:105`
- **Muammo:** W-11 profilni qo'lda o'zgartirishga "faqat `config_supported=warn` bo'lsa" ruxsat beradi. §2.3 da `config_supported` ning `warn` holati yo'q, shuning uchun shart hech qachon bajarilmaydi.
- **Tuzatish:** `config_supported=fail` va `metadata_profile=pass`. Yoki 105 ga warn sharti qo'shilsin.

**B-027** — `33:2841, :2845` ↔ `33:502`
- **Muammo:** W-14 reassign'ni `revoked` agent va `ONEC_BASE_DUPLICATE` holatlari uchun tasvirlaydi. §5.3 holat jadvalida faqat `disabled → onboarding` bor.
- **Tuzatish:** 502 "Dan" → `onboarding/ready/error/disabled`. Yoki W-14 ga `409 ONEC_BASE_NOT_READY` qo'shilsin.

**B-028** — `33:3257, :3261` ↔ `33:1828, :1838` (§7.5)
- **Muammo:**
  - W-46 `pending/queued` (amalda `retry_wait/unknown/mismatch` ham) itemni o'tkazib yuborishga ruxsat beradi. §7.5 da faqat `failed → skipped`.
  - `unknown` item 1C ga yozilgan bo'lishi mumkin, uni o'tkazib yuborish xavfli.
- **Tuzatish:**
  - 3257 → `failed/pending/queued/retry_wait`.
  - 3261 → `409` item `sending/unknown/written/verified/mismatch/skipped`.
  - §7.5 ga tegishli o'tishlarni qo'shing.

**B-029** — `33:3079` ↔ `33:3078`
- **Muammo:** W-32 xatolarida "qator darajasida `errors[]`" deyilgan, lekin javob `202 {approved, task_ids}` — `errors` yo'q.
- **Tuzatish:** javob → `{approved, task_ids, errors:[{id, code}]}`.

**B-030** — `33:3182` ↔ `33:3169`
- **Muammo:** W-40 natijani "W-39 `preview_result`" da ko'rsatadi, lekin W-39 javobida bunday maydon yo'q.
- **Tuzatish:** W-39 ga `preview_result: null|{task_id, outcome, data, error, received_at}` qo'shing (oxirgi `preview_object` vazifasining `onec_task_results` yozuvi).

**B-031** — `33:3234, :3273` ↔ `33:2654-2658` (ExportBatch shakli), `onec_export_batches` ustunlari
- **Muammo:** W-44/W-47 `cancel_requested_at` va `accepted_at` bilan ishlaydi, lekin ExportBatch shaklida bu maydonlar va `cancelled_at`, `cancel_reason`, `accept_reason` yo'q. DB ustunlari mavjud.
- **Tuzatish:** shaklga `accepted_at, accept_reason, cancel_requested_at, cancelled_at, cancel_reason` ni qo'shing.

**B-032** — `33:2753, :2765-2766` ↔ `12:3162, :3186`
- **Muammo:** W-08 `onec_agent_logs ∪ onec_events` ni qaytaradi, lekin:
  - `level` ro'yxatlari har xil (`warn` vs `warning`);
  - `onec_events`da `message/context` o'rniga `message_key/params` bor;
  - W-07 va W-08 dagi `attachment_id` ning manbai yo'q.
- **Tuzatish:** W-08 ga xaritalash qoidasi yozilsin:
  - server voqeasida `warning → warn`;
  - `message_key` maydoni qo'shilsin;
  - `context = params`;
  - diagnostika → `code='diagnostics_ready'`, `context.attachment_id`.

**B-033** — `33:2279` ↔ `34:546`, `12:2543`
- **Muammo:** A-10 `{"reason":"uninstall"|"user"}` qabul qiladi, lekin server doim `revoke_reason='uninstall'` yozadi.
- **Tuzatish:** `revoke_reason = <so'rovdagi reason>`.

**B-034** — `33:2232, :2235` ↔ `33:1031, :1037`, `onec_agent_tasks`
- **Muammo:** A-04 heartbeat `cancel_requested` ni qaytaradi, lekin vazifa darajasida manba ustuni ham, `leased → cancelled` o'tishi ham yo'q.
- **Tuzatish:** `onec_agent_tasks.cancel_requested_at TIMESTAMPTZ NULL` + `leased → cancelled` (o'qish vazifalari). Yoki A-04 da hisoblangan: `NOT is_write AND batch.cancel_requested_at IS NOT NULL`.

**B-035** — `33:2267` ↔ `12:1624` (`attachments.uploaded_by UUID NOT NULL REFERENCES app.users`)
- **Muammo:** A-07 diagnostika yuklamasida foydalanuvchi yo'q (agent tokeni), shuning uchun INSERT yiqiladi.
- **Tuzatish:** `uploaded_by` = `collect_diagnostics` vazifasining `created_by` (W-07 so'rovchisi). Muqobil: `kind='onec_diagnostics'` da NULL ruxsat.

**B-036** — `33:1125, :2702, :2715`, `14:609` ↔ `12:3663-3709`
- **Muammo:** `onec_device_auth_lookup` filtrni `expires_at > now()` bilan qo'llaydi, `approve` esa faqat `boolean` qaytaradi. Shu sabab `ONEC_PAIRING_CODE_EXPIRED` hech qachon qaytmaydi (W-03 ham 404 INVALID deydi).
- **Tuzatish:** `approve` → `text` (`approved|not_found|expired|used`), bir xil tarzda 12 §4.5 va 33 §5.18 da. W-03/W-04: `404 INVALID` / `409 EXPIRED`.

### Auth (14)

**B-037** — `14:372, :388`, `31:149` (QT-SUB-03) ↔ `12:320` (`auth.sessions`), `12:3610-3621`
- **Muammo:** "barcha `sessions`/`refresh_tokens` `suspended_at=now`" deyilgan, lekin `sessions`da bu ustun yo'q. `auth_suspend_tenant` faqat `refresh_tokens` ni yangilaydi.
- **Tuzatish:** 14 va 31 → "`refresh_tokens.suspended_at=now`, `revoked_reason='subscription'` (`app.auth_suspend_tenant(tenant_id, true)`); `sessions` o'zgarmaydi".

**B-038** — `14:72, :78, :262, :517, :520, :549, :571-572` ↔ `12:3527-3529`
- **Muammo:** `erp_app`ning `auth.*` ga GRANT'i yo'q, lekin quyidagi amallar uchun SECURITY DEFINER funksiya yo'q ("qolgani qo'shiladi"):
  - auth code, sessiya va birinchi refresh token chiqarish;
  - OTP yaratish va tekshirish;
  - `login_attempts` va bloklash;
  - parol/PIN o'rnatish va `pin_hash` o'qish;
  - bitta sessiya yoki foydalanuvchini bekor qilish.

  Login oqimini 12 asosida qurib bo'lmaydi.
- **Tuzatish:** 12 §4.5 ga minimal to'plam qo'shing va 14:549 da sanab o'ting: `auth_issue_code`, `auth_create_session`, `auth_issue_refresh`, `auth_otp_create/verify`, `auth_record_login`, `auth_set_credentials`, `auth_get_pin_hash`, `auth_revoke_session`, `auth_revoke_user`. 6.2 CI ro'yxatini yangilang.

**B-039** — `14:153-154` ↔ `12:2279-2287` (`telegram_links`: `tenant_id`/`user_id NOT NULL`, `phone` yo'q, RLS)
- **Muammo:** login'dan oldin telefon bo'yicha Telegram chat'ni topish mumkin emas.
- **Tuzatish:** `app.auth_telegram_chat_by_phone(p_phone) RETURNS text` (SECURITY DEFINER, `users.phone → telegram_links`, `revoked_at IS NULL`). 14:153 dagi "tenant kontekstisiz" iborasini aniqlashtiring.

### Kassa / sync (16, 18)

**B-040** — `18:243` ↔ `12:965`, `18:331, :419`
- **Muammo:** `line_id` → DB `sale_lines.id`.
- **Tuzatish:** `id` ("qurilma beradi — `sale_lines.id`").

**B-041** — `18:258` ↔ `18:241-256, :317`
- **Muammo:** server qurilma yuborgan `cost_amount` ni tekshiradi va farq bo'lsa `VALIDATION_ERROR` qaytaradi. Qurilma FIFO/AVECO tannarxini hisoblay olmaydi. `line_total`/`vat_amount` qatorlar jadvalida yo'q.
- **Tuzatish:** `cost_amount` — faqat server hisoblaydi. `lines[]` jadvaliga `line_total` va `vat_amount` (Money, majburiy) qatorlarini qo'shing.

**B-042** — `18:250-252` ↔ `12:987` (`(discount_amount = 0) = (discount_source IS NULL)`)
- **Muammo:** faqat `discount_pct` yuborilsa CHECK buziladi.
- **Tuzatish:** `discount_source` berilsa `discount_amount > 0` majburiy, va aksincha.

**B-043** — `18:326` ↔ `12:945`
- **Muammo:** `total` → `sales.total_amount`.
- **Tuzatish:** `total_amount`.

**B-044** — `18:120, :121, :124` ↔ `12:857`
- **Muammo:** `approved_by_user_id` → `doc_approvals.approved_by`.
- **Tuzatish:** `approved_by`.

**B-045** — `18:849` ↔ `12:883` (`payment_checkouts` CHECK `…,'consumed'`)
- **Muammo:** enum'da `consumed` yo'q, qachon `consumed` bo'lishi ham yozilmagan.
- **Tuzatish:** `consumed` ni qo'shing. §16.1 ga yozing: "posting checkout'ni `consumed`ga o'tkazadi; `confirmed` emas/`consumed` → `PAYMENT_NOT_CONFIRMED`".

**B-046** — `18:916` ↔ `17:316`, `18:313, :649`
- **Muammo:** `PAYMENT_NOT_CONFIRMED` §16.3 GET'ga bog'langan. Katalog bo'yicha u `sale.created`/`debt_payment.created` uchun.
- **Tuzatish:** §4.6 va §12.2 xatolariga qo'shing; 916 "Qayerda" → §4.6, §12.2.

**B-047** — `18:636, :656` ↔ `12:1453` (`debt_payments.branch_id NOT NULL`)
- **Muammo:** `branch_id` "shartli (bank/karta — bo'sh)" deyilgan.
- **Tuzatish:** `branch_id` — UUID, majburiy. Shartli faqat `cash_register_id`/`shift_id`.

**B-048** — `18:705-714`, `07:498` ↔ `12:1675-1676, :1689`, `20:1085`
- **Muammo:** `owner_withdrawal` uchun `counterparty_id` (ta'sischi) talab qilinadi, lekin POS payload'ida ham, POS-14 formasida ham yo'q.
- **Tuzatish:** 18 §13.1 ga `counterparty_id UUID|null` qo'shing (`reason=owner_withdrawal` va `legal_form≠sole_proprietor` da majburiy, `is_founder=true`). POS-14 ga ta'sischi Select qo'shing.

**B-049** — `18:755` ↔ `12:2066+` (`einvoices`)
- **Muammo:** `source:"sale"|"manual"` va `sale_id` ning ustuni yo'q.
- **Tuzatish:** `{direction:"out", counterparty_id, related_doc_type:"sales"|null, related_doc_id|null, doc_date, lines?}`; `source` hisoblanadi.

**B-050** — `16:40, :120-130` ↔ `16:26-38`, `18:483, :871`
- **Muammo:** `/sync/pull` scope'lari (`catalog, prices, customers, permissions, limits, settings, all`) to'liq ro'yxatda yo'q. §1 dagi barcodes/marking_codes/fiscal ma'lumotlarining scope nomi yo'q.
- **Tuzatish:** 16 §3.2 ga "scope → javob kaliti → manba jadvallar" jadvalini qo'shing.

**B-051** — `16:99` ↔ `16:315`, `12:484`
- **Muammo:** push tranzaksiyasi `devices.last_seen_at` ni yangilamaydi, lekin 1C tayyorlik qoidasi aynan shu ustunga tayanadi.
- **Tuzatish:** 16:99 → `last_seen_at = now()` (push va pull).

**B-052** — `16:312`, `07:995` ↔ `12:476-496` (`devices`), `20:617`
- **Muammo:** `device_name` ustuni yo'q.
- **Tuzatish:** `cash_register_name` (hisoblanadi) + `app_version`. Muqobil: `devices.device_name TEXT NULL`.

**B-053** — `16:245` ↔ `12:2224`, `11:195`
- **Muammo:** `sync_exceptions.kind` "16 §5 ro'yxati" deyilgan, lekin ro'yxat yo'q.
- **Tuzatish:** enum yozing: `price_mismatch, archived_product, stock_negative, debt_limit_exceeded_offline, approval_limit_exceeded_offline`, va 12 ga CHECK qo'shing.

**B-054** — `16:243`
- **Muammo:** offline qaytarish/chegirma uchun `limit_exceeded=true` deyilgan, lekin `returns`/`sale_lines`da bunday ustun yo'q.
- **Tuzatish:** → `sync_exceptions` (`kind=approval_limit_exceeded_offline`) + `doc_approvals`.

### Ombor (19)

**B-055** — `19:601, :632` ↔ `12:1254` (`transfer_lines.qty_sent`), `19:647`
- **Muammo:** `lines[].qty` nomli ustun yo'q.
- **Tuzatish:** `lines[].qty_sent`; "`qty_received = qty_sent`".

**B-056** — `19:497, :502, :570` ↔ `purchase_orders`/`supplier_returns` (`version` yo'q), `17:136`
- **Muammo:** "`version` talab qiladi" va `409 VERSION_CONFLICT` hujjatlarda ishlatilgan.
- **Tuzatish:** olib tashlang (570 da → `409 DOC_INVALID_STATE`). Muqobil: `purchase_orders.version` qo'shing.

**B-057** — `19:22, :595` ↔ `12:1240-1241` (`from_branch_id <> to_branch_id`, `branch_id = from_branch_id`)
- **Muammo:** bir filial ichidagi omborlar orasida ko'chirish DB'da yiqiladi. `from/to_branch_id` qanday to'ldirilishi ham yozilmagan.
- **Tuzatish:** 19:595 → "boshqa filial ombori; `*_branch_id` server omborlardan oladi; `from_warehouse_id` ∈ `X-Branch-Id`".

**B-058** — `19:524` ↔ `12:1566` (CHECK `goods_receipts, debt_openings`)
- **Muammo:** faqat `goods_receipts` ruxsat etilgan, shuning uchun import qilingan yetkazib beruvchi qarzini (`debt_openings`) yopib bo'lmaydi.
- **Tuzatish:** `"goods_receipts"|"debt_openings"`.

**B-059** — `19:14` ↔ `19:426`
- **Muammo:** ma'lumotnoma ro'yxatida `suppliers` resursi bor, lekin u mavjud emas.
- **Tuzatish:** → `counterparties`.

### Moliya / admin (20)

**B-060** — `20:261, :263, :139` ↔ `12:1790, :1820`, `13:388`
- **Muammo:** `vat_offset` har filial bo'yicha yaratilishi mumkin, lekin `vat_moves`da `branch_id` yo'q. Natijada tenant bo'yicha kirish QQSi ikki marta hisobga olinadi.
- **Tuzatish:** `vat_offset` — faqat `is_default` filial (server majburlaydi), har tenant+davr uchun bitta.

**B-061** — `20:858` ↔ `17:312` (`EINVOICE_PROVIDER_UNAVAILABLE` 503)
- **Muammo:** `422 {code:"EINVOICE_PROVIDER_UNAVAILABLE"}`, katalogda 503.
- **Tuzatish:** `503`.

**B-062** — `20:71, :794, :828` ↔ `tenants` (`name`; `locale` yo'q)
- **Muammo:** `TenantSettings` `store_name` va `locale` ni qaytaradi, PATCH esa `name` ni oladi.
- **Tuzatish:** `name` (`tenants.name`). `locale` ni olib tashlang yoki `settings.locale` deb aniq qo'shing.

**B-063** — `20:752, :765, :777` ↔ `cash_registers.version`, `17:134`
- **Muammo:** PATCH `version` talab qiladi, lekin GET/POST javoblari uni qaytarmaydi.
- **Tuzatish:** javoblarga `version` qo'shing.

**B-064** — `20:10, :69, :777`
- **Muammo:** `POST /cash-registers/{id}/archive` indeksda yo'q (ruxsat/xato/idempotentlik ko'rsatilmagan).
- **Tuzatish:**
  - indeksga `40i | POST /cash-registers/{id}/archive | cash_register.manage` qatorini qo'shing;
  - detal jadvali: `RESOURCE_ARCHIVED`, Idempotency;
  - M14 soni → 12.

**B-065** — `20:48` ↔ `20:491`
- **Muammo:** debts-aging ruxsati indeksda faqat `reports.finance.view`, detalda esa `… yoki debts.approve`.
- **Tuzatish:** indeksni detalga moslang.

**B-066** — `20:164, :178` ↔ `state_reports_tax_type_check` (6 qiymat), `06:144`
- **Muammo:** yuklashda faqat `vat|turnover` qabul qilinadi, shuning uchun BO-10 ning 4 ta tabi doim bo'sh qoladi.
- **Tuzatish:** 6 qiymatning hammasi; `compare` faqat `vat`/`turnover` uchun `our_amount` ni hisoblaydi.

**B-067** — `20:151` ↔ `13:204, :257`
- **Muammo:** `vat_moves` `doc_type` filtrida `write_offs` va `supplier_payments` yo'q.
- **Tuzatish:** ikkalasini ham qo'shing.

**B-068** — `20:492-493` ↔ `18:692`, `07:845`
- **Muammo:** kanonik debts-aging endpoint'ida `bucket=` va `rows[].due_date` yo'q.
- **Tuzatish:** ikkalasini ham qo'shing.

**B-069** — `20:803`, `13:308` ↔ `12:361`
- **Muammo:** `owner_withdrawal_account` uchun enum ham, standart qiymat ham yozilmagan.
- **Tuzatish:** `"4890"|"8720"`; standart `legal_form`dan (`sole_proprietor` → 8720, qolganlari → 4890).

**B-070** — `20:506` ↔ `17:212`
- **Muammo:** eksport `format` ni 20 so'rov tanasida, 17 esa query'da qabul qiladi.
- **Tuzatish:** bittasini tanlang va ikkalasini moslang.

**B-071** — `20:11` ↔ `17:152`, `20:1079-1103`
- **Muammo:** `cash-movements` uch bosqichli deb yozilgan, `ledger-adjustments` esa ro'yxatda yo'q.
- **Tuzatish:** "`expenses`, `bank-settlements`, `tax-settlements` — uch bosqichli; `cash-movements`, `ledger-adjustments` — bir bosqichli".

**B-072** — `20:1214` ↔ `12:1729` (`commission_amount >= 0`)
- **Muammo:** FIFO yig'indisi kirimdan kichik bo'lsa, komissiya manfiy chiqadi va DB CHECK'i 500 xato beradi.
- **Tuzatish:** `commission_amount < 0` holatida ham `unmatched_lines` (`reason:"commission_invalid"`).

**B-073** — `20:1502, :1510, :1536-1537` ↔ `17:150`, `18` §7, `22:215`, `ai_ocr_jobs.doc_type_hint` CHECK
- **Muammo:** OCR `return` qoralama qaytarish yaratadi, lekin `returns` faqat `/sync/push` orqali keladi va `/post` yo'q. 22 faqat `purchase` deydi.
- **Tuzatish (biri):**
  - `return` ni hamma joydan (CHECK bilan birga) olib tashlang.
  - Yoki `return` faqat tahlil qilingan maydonlarni qaytaradi (qoralamasiz), 17:150 va 22:215 shunga moslanadi.

**B-074** — `20:1536-1537` ↔ `products` (`status` yo'q), `ai_ocr_jobs.created_doc_id` (bitta)
- **Muammo:** `catalog` confirm ko'p mahsulot yaratadi, lekin javob bitta `created_doc_id` va `status:"draft"`.
- **Tuzatish:** `{created_doc_type:"stock_openings"|null, created_doc_id, created_product_ids:[…], status}`; `"products"` ni enum'dan va 12:2346 izohidan olib tashlang.

**B-075** — `20:978` ↔ `12:3897, :3900`, `13:291, :294`
- **Muammo:** `6410` «Soliq va yig'imlar» deb atalgan, lekin seed'da u `tax_payment` «Soliq to'lovi (byudjetga)»; «Soliq va yig'imlar» — `period_taxes`, 9430.
- **Tuzatish:** nomni seed'ga moslang.

**B-076** — `20:1085`, `13:301-306` ↔ `cash_movements_reason_check`, `31` QT-M16-01
- **Muammo:** `reason`↔`direction` juftligi majburlanmagan. `other` uchun provodka umuman yo'q, lekin QT-M16-01 aynan `other` ni ishlatadi.
- **Tuzatish:**
  - 20 ga: `collection`/`owner_withdrawal` → `out`, `deposit` → `in`, `other` → ikkalasi; aks holda `VALIDATION_ERROR`.
  - 13 §2.18 ga: `other/out` → Dt 9430 / Kt 5010; `other/in` → Dt 5010 / Kt 9390 (hisoblarni Buxgalter tasdiqlaydi).

**B-077** — `20:1053-1057` ↔ `20:950-953`
- **Muammo:** takroriy xarajatni tasdiqlash (#51) darhol `posted` qiladi, shuning uchun `expenses.approve` limitini aylanib o'tish mumkin.
- **Tuzatish:** limitdan oshsa `202 {status:"draft", approval_request_id}` + `EXPENSE_LIMIT_EXCEEDED`.

**B-078** — `13:308, :321, :516` ↔ `20:789, :826-827`
- **Muammo:** 13 "Buxgalter o'zgartiradi" deydi (`owner_withdrawal_account`, `payment_org_commission_account`, `turnover_tax_account`), lekin PATCH faqat `settings.tenant` (Egasi) uchun.
- **Tuzatish:** 13 → "Egasi (BO-14)". Muqobil: 20:827 ga shu kalitlar uchun `accounting.post` ham yetarli, deb qo'shing.

### Ekranlar (07) ↔ API

**B-079** — `07:1114, :1116-1117, :1130` ↔ `20:828, :841, :856`
- **Muammo:** BO-14 hamma narsani `PATCH /tenant/settings` orqali yuboradi. Soliq rejimi esa `POST /tenant/tax-regimes` bilan, kalitlar `PUT /tenant/integrations/{provider}` bilan o'zgartiriladi. Faktura.uz uchun 4 ta maydon kerak (`login, password, client_id, client_secret`), ekranda 2 ta.
- **Tuzatish:** Ma'lumot manbaiga ikkala endpoint'ni qo'shing; Faktura.uz maydonlarini 4 taga yetkazing.

**B-080** — `07:1121` ↔ `20:790-807, :856`
- **Muammo:** majburiy `providerFiscalizationOff` checkbox'ining API maydoni yo'q.
- **Tuzatish:** click/payme/uzum tanasiga `provider_fiscalization_off_confirmed: bool` qo'shing.

**B-081** — `07:1115` ↔ `19:776, :782`, `valuation_method_history_method_check`
- **Muammo:** `AVECO|FIFO` (katta harf), API va DB'da kichik harf.
- **Tuzatish:** `aveco|fifo` (yorliq katta harfda qolishi mumkin).

**B-082** — `07:705, :755` ↔ `20:1535`, `19:359`
- **Muammo:** OCR kirimni tasdiqlash uchun `purchases.create` ko'rsatilgan, API'da `purchases.receive` + `ai.ocr.use`. Menejer va Buxgalter 403 oladi.
- **Tuzatish:** `purchases.receive` + `ai.ocr.use`.

**B-083** — `07:734-735` ↔ `19:521-523`
- **Muammo:** `payment.source` nomli maydon yo'q; `shift_id` (naqd to'lovda shart) formada yo'q.
- **Tuzatish:** `payment.method`; `payment.shiftId` (`method=cash` bo'lsa shart).

**B-084** — `07:741, :761` ↔ `19:549-556`
- **Muammo:** qaytarish formasida faqat `reason` bor.
- **Tuzatish:** formaga qo'shing:
  - `receiptId`, `docDate`;
  - `lines[]` (`receipt_line_id`, `lot_id`, `qty`);
  - `reason` ∈ `expired|damaged|excess|other`.

**B-085** — `07:774, :804` ↔ `19:114`
- **Muammo:** `nameRu` ni saqlash ruxsati `prices.edit` deb ko'rsatilgan, API'da `catalog.manage`.
- **Tuzatish:** `catalog.manage`.

**B-086** — `07:875` ↔ `20:261`
- **Muammo:** BO-07 qoralamasida majburiy `branch_id` yo'q.
- **Tuzatish:** `{period, tax_kind, branch_id}` + filial tanlovi (B-060 bilan birga).

**B-087** — `07:1141, :1156` ↔ `18:759-762`
- **Muammo:** chekdan e-faktura yaratish ruxsati `einvoice.sign` deb ko'rsatilgan, API'da `einvoice.create`.
- **Tuzatish:** `einvoice.create`.

**B-088** — `07:1155, :1160` ↔ `18:771-774`
- **Muammo:** `POST /einvoices/{id}/send` bosqichi tushib qolgan.
- **Tuzatish:** oqimga `→ POST /api/v1/einvoices/{id}/send` ni qo'shing.

**B-089** — `07:1158` ↔ `19:859`
- **Muammo:** risk-flag dialogida majburiy `note` yo'q.
- **Tuzatish:** `note` maydonini qo'shing.

**B-090** — `07:1017` ↔ `20:629`
- **Muammo:** qurilmani bekor qilish dialogida majburiy `reason` va `confirm_pending_loss` yo'q.
- **Tuzatish:** ikkalasini ham qo'shing.

**B-091** — `07:1556` ↔ `17:201`, `15:181`
- **Muammo:** bank ko'chirmasi `attachments.kind='import'` bilan yuklanadi, bu `catalog.manage` ni talab qiladi. Buxgalterda bu ruxsat yo'q, shuning uchun 403.
- **Tuzatish:** 17:201 da `import` → `catalog.manage` / `stock.opening.manage` / `bank_settlements.manage` (kontekstga qarab).

**B-092** — `07:1549, :1554` ↔ `20:1158`
- **Muammo:** `collection` uchun `variance_amount` kiritish maydoni yo'q, net formulasi ham noto'liq.
- **Tuzatish:** maydonni qo'shing; formula `net = gross − commission + variance` (B-010).

**B-093** — `07:1273` ↔ `20:1248, :1322`
- **Muammo:** BO-19 da `GET /billing/subscription` va `GET /billing/payments` yo'q.
- **Tuzatish:** ikkalasini ham qo'shing.

**B-094** — `07:1243` ↔ `19:811`
- **Muammo:** PLU eksport ruxsati `labels.print` deb ko'rsatilgan, API'da `catalog.manage`.
- **Tuzatish:** `catalog.manage`.

**B-095** — `07:1351` ↔ `14:565`
- **Muammo:** `POST /auth/signup` ① qadamdan keyin chaqiriladi, lekin `store_name`/`business_type` ② qadamdan keladi. Tanada `legal_form` va shartlar rozilik maydonlari yo'q.
- **Tuzatish:** ② dan keyin chaqiring. 14:565 ga `legal_form`, `accepted_terms_version`, `accept_terms` ni qo'shing.

**B-096** — `07:691` ↔ `19:717-719`
- **Muammo:** `reason=gift` bo'lsa `gift_kind` (va kerak bo'lsa `promo_order_ref`) formada yo'q, shuning uchun 422.
- **Tuzatish:** `gift` tanlanganda shu maydonlarni ko'rsating.

**B-097** — `07:286` (POS-08) ↔ `19:366-381`, `receipt_lines`
- **Muammo:** majburiy `discrepancyReason` ning API/DB maydoni yo'q.
- **Tuzatish:** `lines[].discrepancy_reason` ni 19 va DDL'ga qo'shing. Muqobil: ekrandan olib tashlang.

**B-098** — `07:174` (POS-04) ↔ `18:734`
- **Muammo:** `GET /fiscal-receipts` `reports.sales.view` ni talab qiladi, Kassirda bu yo'q.
- **Tuzatish:** 18:734 → `reports.sales.view` yoki `sales.create` (o'z filiali).

**B-099** — `07:174, :462` ↔ `fiscal_receipts_check2`, `18:735`
- **Muammo:** `debt_settlement` chekida `sale_id` NULL, `debt_payment_id` filtri esa yo'q. `receipt.reprinted` `sale_id` ni talab qiladi.
- **Tuzatish:**
  - 18 §14.1 ga `?debt_payment_id=` filtri va javob maydonini qo'shing;
  - `receipt.reprinted` `fiscal_receipt_id` ni qabul qilsin.

**B-100** — `07:168` (POS-04) ↔ 18 §4.1/§6, `16:65`
- **Muammo:** `delivery='electronic'` va `delivery_reason` ni hech qaysi voqea olib bormaydi.
- **Tuzatish:** `sale.created` payload'iga `delivery`/`delivery_reason` qo'shing. Muqobil: yangi `receipt.electronic_issued` voqeasi.

**B-101** — `07:266` (POS-07) ↔ `18:212`
- **Muammo:** Z-hisobot endpoint'i `reports.sales.view` ni talab qiladi, Kassirda bu yo'q.
- **Tuzatish:** `shift.closed` javobidagi `server.z_report` ni ishlating. Muqobil: ruxsatni `… yoki cash.count.shift` ga kengaytiring.

**B-102** — `07:232` (POS-06) ↔ `18:756`
- **Muammo:** POS `POST /einvoices` ni chaqiradi (`einvoice.create`), Kassirda bu ruxsat yo'q.
- **Tuzatish:** POS chaqiruvini olib tashlang; server `source=sale` qoralamasini avtomatik yaratadi (18 §14a da majburiy qiling).

**B-103** — `07:204` (POS-05) ↔ `18:326`
- **Muammo:** `GET /sales?number=` javobida qatorlar yo'q, lekin `return.created` uchun `sale_line_id` va narxlar kerak.
- **Tuzatish:** qidiruvdan keyin `GET /sales/{id}` (qatorlar, `returned_qty`).

**B-104** — `07:333` (POS-09) ↔ `19:598, :647`
- **Muammo:** `vehicle_plate` (`vehicle` uchun `post`da shart) formada yo'q.
- **Tuzatish:** `vehiclePlate` va `driverName` ni qo'shing.

**B-105** — `07:341` ↔ `19:647`
- **Muammo:** `vehicle` + e-TTN yo'q bo'lsa natija `posted` + `ETTN_REQUIRED` ogohlantirishi, "yo'lda" emas.
- **Tuzatish:** ekrandagi natija matnini shunga moslang.

**B-106** — `07:366-371, :683` ↔ `19:656`
- **Muammo:** `POST /stock-counts` ni hech qaysi ekran chaqirmaydi, shuning uchun sanashni boshlab bo'lmaydi.
- **Tuzatish:** POS-10 yoki BO-03 ga "Sanashni boshlash" amalini qo'shing (`stock.count.create`).

**B-107** — `07:397` (POS-11) ↔ `16:26-38`
- **Muammo:** lokal `stock` keshi 16 §1 da yo'q.
- **Tuzatish:** 16 §1 ga `stock` jadvalini qo'shing. Muqobil: onlayn `GET /stock-balances`.

**B-108** — `07:287` ↔ `19:381`
- **Muammo:** `poaNumber` standart qiymati "xaridnomadan" olinadi, lekin `purchase_orders.poa_number` ustuni yo'q.
- **Tuzatish:** ixtiyoriy input → `goods_receipts.poa_number`.

**B-109** — `07:295` ↔ `19:366-381`
- **Muammo:** kirimda skanerlangan markirovka kodlarini yuboradigan maydon yo'q.
- **Tuzatish:** POST/PATCH `/goods-receipts` ga `lines[].marking_codes[]` qo'shing.

### Testlar (31)

**B-110** — `31:179` (QT-PERM-07) ↔ `18:124, :502, :536`, `15:254`
- **Muammo:** testda `status='approved'` + `consumed_at` deyilgan; bunday holat bo'lmaydi, bu `consumed`. Xato kodi ham ikki xil: 18 da `APPROVAL_INVALID`, 15 da `APPROVAL_REQUEST_ALREADY_RESOLVED`.
- **Tuzatish:** testda `status='consumed'`; 18:124 → `409 APPROVAL_REQUEST_ALREADY_RESOLVED`.

**B-111** — `31:411` (QT-M15-01) ↔ `12:1922` (`cash_moves`da `direction` yo'q), `13:269`
- **Muammo:** testda `cash_moves`, `direction=out` deyilgan.
- **Tuzatish:** `cash_moves(amount=-500000.00, method='cash', doc_type='expenses', …)`; `cash_movements` hujjati yaratilmaydi.

---

## KICHIK

**B-112** — `19:637, :898` ↔ `12:2115`
- **Muammo:** `ettn_status` filtrida qiymatlar ro'yxati yo'q; `cancelled` ham tilga olinmagan.
- **Tuzatish:** CHECK'dagi ro'yxatni qo'shing.

**B-113** — `19:294, :307` ↔ `12:2270, :2273`
- **Muammo:** `total_rows:null` va `result:null`, DB'da `NOT NULL DEFAULT 0/{}`.
- **Tuzatish:** `0` va `{}`.

**B-114** — `19:78`
- **Muammo:** `Product` javobida `marking_group_code` yo'q.
- **Tuzatish:** qo'shing.

**B-115** — `19:98-99` ↔ `products_check`
- **Muammo:** `vat_rate` "majburiy" deyilgan.
- **Tuzatish:** "shartli: `vat_rate` yoki `vat_exemption_code`".

**B-116** — `19:849` ↔ `einvoices_factura_type_check`
- **Muammo:** ro'yxat oxirida `/…` bor, CHECK'da esa faqat 3 qiymat.
- **Tuzatish:** `/…` ni olib tashlang.

**B-117** — `19:219, :385, :463`
- **Muammo:** `params.resource` ko'plikda (`price_changes`), boshqa joylarda birlikda.
- **Tuzatish:** `price_change`, `counterparty`.

**B-118** — `19:242` ↔ `platform.label_templates.code`
- **Muammo:** javobda `code` yo'q.
- **Tuzatish:** qo'shing.

**B-119** — `20:111` ↔ `20:1390-1397`
- **Muammo:** "`/platform/*` (9 endpoint)", amalda 10 ta.
- **Tuzatish:** 10.

**B-120** — `20:1603`
- **Muammo:** "75 ta `ONEC_*`", 17 va 33 da 81 ta.
- **Tuzatish:** 81.

**B-121** — `20:1215` ↔ `12:1695`
- **Muammo:** `import_id` "ustun bilan bir xil" deyilgan, ustun nomi `id`.
- **Tuzatish:** izohni aniqlashtiring.

**B-122** — `20:1435` ↔ `12:2285`
- **Muammo:** Telegram ulanishi "o'chiriladi" deyilgan, DB'da yumshoq bekor qilish (`revoked_at`).
- **Tuzatish:** `revoked_at = now()`.

**B-123** — `20:1100`
- **Muammo:** kassa harakatini bekor qilish xatolarida `PERIOD_CLOSED` yo'q.
- **Tuzatish:** qo'shing.

**B-124** — `20:1374-1377` ↔ `17:210-211`
- **Muammo:** `export_id/download_url` ishlatilgan, 17 §13 da `job_id/file_url`.
- **Tuzatish:** 17 §13 nomlariga moslang.

**B-125** — `20:1292, :1323, :1365`
- **Muammo:** "faqat Egasi" endpoint'larida `OWNER_ONLY` xatosi yo'q.
- **Tuzatish:** qo'shing.

**B-126** — `20:53` ↔ `20:562`
- **Muammo:** indeksda "nomi/tavsifi", lekin tavsif ustuni yo'q.
- **Tuzatish:** "Rol nomini tahrirlash".

**B-127** — `20:424` ↔ `13:382`
- **Muammo:** davr yopishga tayyorlik javobida `tax_settlement_missing` ogohlantirishi uchun joy yo'q.
- **Tuzatish:** `warnings[]` maydonini qo'shing.

**B-128** — `20:385` ↔ `13:566`, QT-M11-12
- **Muammo:** `0000 ≠ 0` ogohlantirishi uchun maydon yo'q.
- **Tuzatish:** `opening_balance_unresolved: bool`.

**B-129** — `20:617, :630, :631` ↔ `devices.outbox_pending_count`
- **Muammo:** `pending_events` deb qayta nomlangan.
- **Tuzatish:** `outbox_pending_count`.

**B-130** — `20:739, :752` ↔ `17:65`
- **Muammo:** sahifalash shakli yo'q.
- **Tuzatish:** `{items, total, page, size}`, yoki 17:65 dagi "sahifasiz" istisnosiga qo'shing.

**B-131** — `20:804` ↔ `13:321`
- **Muammo:** sozlama karta ekvayringini ham qamraydigandek tushuniladi.
- **Tuzatish:** "faqat `click/payme/uzum`; `card/uzqr` → doim 9430".

**B-132** — `20:802` ↔ `12:360-361`
- **Muammo:** `discount_posting` ning standart qiymati yozilmagan.
- **Tuzatish:** standart `"gross_9050"`.

**B-133** — `20:790-807` ↔ `11:38`, `12:358`
- **Muammo:** `negative_stock_policy` va `ai_training_consent` kalitlarini o'zgartiradigan endpoint yo'q.
- **Tuzatish:** `TenantSettings` ga qo'shing yoki egasi bo'lgan endpoint'ni ko'rsating.

**B-134** — `20:816, :850` ↔ `12:2174`
- **Muammo:** `fiscal_partner` va `eimzo` sirlarini o'rnatish yo'li yo'q.
- **Tuzatish:** provider ro'yxatiga qo'shing yoki "platforma boshqaradi" deb belgilang.

**B-135** — `20:685` ↔ `12:432, :435`
- **Muammo:** `activity_type` o'zgarishi va bir oyda ikki marta o'zgartirish ko'rib chiqilmagan.
- **Tuzatish:** `(branch_id, valid_from)` bo'yicha upsert.

**B-136** — `20:164`
- **Muammo:** `published_at` "sana" deyilgan, ustun `timestamptz`.
- **Tuzatish:** turni aniqlashtiring.

**B-137** — `33:3039`
- **Muammo:** W-29 `warnings` umumiy `{code, params}` shaklida emas.
- **Tuzatish:** `{code, params:{kind, erp_value}}`.

**B-138** — `33:3364` ↔ `33:953`
- **Muammo:** `batch_id` deyilgan, ustun `last_batch_id`.
- **Tuzatish:** `last_batch_id`.

**B-139** — `33:3325, :2645`
- **Muammo:** `actor` → DB'da `actor_user_id`; `paired_by` obyekt sifatida qaytariladi.
- **Tuzatish:** `actor_user_id`+`actor_name`, `paired_by`+`paired_by_name`.

**B-140** — `33:2575`
- **Muammo:** cursor ro'yxatida mavjud bo'lmagan `onec-events` va `onec-agent-logs` yo'llari bor.
- **Tuzatish:** haqiqiy yo'llarni yozing; `…/items` ni qo'shing.

**B-141** — `33:2584` (W-04), `07:1423` ↔ `17:40`
- **Muammo:** `POST /onec-agents/pair` — CRUD amali fe'l shaklida; `refresh`, `auto-match`, `discover-bases` va boshqa buyruq yo'llari uchun 17 da istisno yozilmagan.
- **Tuzatish:** `POST /onec-agents`; 17 §2 ga M19 buyruq yo'llari istisnosini qo'shing.

**B-142** — `33:2654`
- **Muammo:** "preview'siz" izohi ostidagi misolda `preview` bor.
- **Tuzatish:** izohni tuzating.

**B-143** — `07:1460, :1474, :1511, :1512` ↔ `33:3377, :3143, :2660-2663, :3117`
- **Muammo:**
  - W-55 da agent nomi/versiyasi yo'q;
  - ExportItem da `max_attempts`/`progress` yo'q;
  - legendada `draft`/`cancelled` yo'q.
- **Tuzatish:** W-37 `agent` ga `agent_version` ni qo'shing; ExportItem ga `max_attempts`, `progress` ni qo'shing; legendani to'ldiring.

**B-144** — `07:1402` ↔ W-04
- **Muammo:** `agent_name`, so'rovda `name`.
- **Tuzatish:** `name`.

**B-145** — 33 / 14 / 34: auth va agent protokolidagi mayda tafovutlar (bitta guruh):
- **a.** `denied`/`access_denied` hech qachon o'rnatilmaydi (`12:3201`, `33:2138`, `14:120`, `34:506`).
  - Tuzatish: deny endpoint'i + `onec_device_auth_deny` qo'shilsin, yoki qiymat o'chirilsin.
- **b.** 14:126 bloklash ro'yxatida A-02 yo'q.
  - Tuzatish: "A-01–A-03 → 403".
- **c.** 14:549 funksiya imzolari noto'g'ri: `auth_rotate_refresh(p_token_hash, p_new_token_hash, p_new_expires_at)`, `auth_revoke_tenant(p_tenant_id, p_reason)`, `auth_suspend_tenant(p_tenant_id, p_suspend)`.
  - Tuzatish: 12 §4.5 dagi aniq imzolarni ko'chiring.
- **d.** 14:42 sarlavhasida `oauth_clients.name`, aslida `client_id`.
- **e.** 14:168 `users.pin_hash` → `user_credentials.pin_hash`.
- **f.** 14:536 da `oauth_clients.status` yo'q; "null=public" → "NULL = public yoki `pending_secret`".
- **g.** A-05 `started_at/finished_at` ni saqlamaydi (33:2244); faqat `duration_ms` saqlanadi, deb yozilsin.
- **h.** A-01 `os_version`/`pc_name` ni yangilamaydi (33:2185).
  - Tuzatish: yangilanadigan ro'yxatga qo'shilsin.
- **i.** Bosqich 5 vazifalari (`fiscal.*`, `print.raw`, `scale.plu_upload`) `onec_agent_tasks` CHECK'lariga sig'maydi (`33:2317`, `21:839`, `34:1631`).
  - Tuzatish: alohida jadval yoki Bosqich 5 migratsiyasida CHECK kengaytirilishi aniq yozilsin.

**B-146** — 18 / 16 dagi mayda tafovutlar (bitta guruh):
- **a.** `DEPENDENCY_NOT_SYNCED` 18 §4.6/§12.2/§18 da yo'q (16:137).
- **b.** 16:54 `+05:00` → `Z` (UTC).
- **c.** 16:92-93 va 16:12 misollarida `device_id`/`actor_user_id` yo'q.
- **d.** 16:267 "avans" cheki — bunday `kind` yo'q (qaror #45).
- **e.** 17:277 `DEBT_LIMIT_EXCEEDED` offline'da 200 `warnings[]` sifatida ham kelishini katalogda yozing (18:109, :291).
- **f.** 17:254 `PIN_INVALID` "Qachon" ga approve'ni qo'shing (18:538).
- **g.** 18:256 `marking_offline` saqlanmaydi; u hisoblanadi, deb yozing.
- **h.** 16:305 xom/qisqartirilgan `created_at` qayerda saqlanishini yozing (`sync_receipts.result`).
- **i.** 18:500 `"25"` → `"25.00"`.
- **j.** 18:183 `stock/cash_moves` → `cash_moves` (`shift_id`, `method='cash'`).
- **k.** 18:651 havola §3.5/§7 → §6.
- **l.** 18:445 `without_receipt` = `sale_id IS NULL`.
- **m.** 18:267 karta turi standarti `personal` → "standart yo'q, har safar so'raladi" (qaror #64, 07:117).

**B-147** — 07 / 31 / 13 / 11 dagi mayda tafovutlar (bitta guruh):
- **07:**
  - **a.** 07:1120 va 07:1351: consent so'roviga `terms_version` qo'shilsin.
  - **b.** 07:1359: OCR oqimiga poll va `/confirm` qadamlari qo'shilsin (`catalog.manage`).
  - **c.** 07:839: qoralama — `ai.chat.use`, yuborish — `debts.remind`.
  - **d.** 07:1171: tasdiqlovchi ruxsatlariga `stock.writeoff` qo'shilsin.
  - **e.** 07:1212 va 07:500, 07:224: `note` → `comment`.
  - **f.** 07:1271: `monthly|yearly` → `month|year`.
  - **g.** 07:794: `nameRu` uzunligi 200 → 255.
  - **h.** 07:912: eksport → `POST /reports/ledger-entries/export` (`xlsx|pdf`).
  - **i.** 07:906: recost ustun nomlari API nomlariga moslansin.
  - **j.** 07:1051 ↔ 20:752: javobga `txkm_contract_ref` qo'shilsin.
  - **k.** 07:285: `qty ≥ 0` → `> 0` (0 bo'lsa qator yuborilmaydi).
  - **l.** 07:462: `/post` yo'q — server darhol o'tkazadi.
  - **m.** 07:233: `limit_exceeded` → `debt_limit_exceeded`.
  - **n.** 07:559: `catalog.manage` ruxsati va to'g'ri ekran ko'rsatilsin.
  - **o.** 07:650: 15 daqiqa → 24 soat.
  - **p.** 07:295: MXIK → DataMatrix.
  - **q.** 07:83: butun chek chegirmasi qatorlarga `discount_source=manual` bilan taqsimlanishi yozilsin.
  - **r.** 07:232 va 07:466: `debt_balances` → lokal `customers`.
- **31:**
  - **s.** 31:37, :403, :405 fixture'lari: `branch_tax_settings.activity_type='retail'`, ombor `type='stock'`, `marking_group_code` qo'shilsin.
  - **t.** 31:35: `settings` ga `discount_posting` va `turnover_tax_account` aniq yozilsin.
  - **u.** 31:201 va 13:366: `related_doc=receipt` → `related_doc_type='sales'`, `related_doc_id`.
- **13:**
  - **v.** 13:269: `doc_type=expense` → `expenses`.
  - **w.** 13:192 va 31:270: `last_purchase_cost` qayerdan olinishi yozilsin (eng so'nggi `stock_lots.unit_cost` `goods_receipts` dan, yo'q bo'lsa `avg_cost`).
  - **x.** 13:103: `customs_vat_base` sxemada yo'q, "MVP'dan keyin" deb belgilansin.
- **11:**
  - **y.** 11:162: `price_changes` → `cancelled` o'tishi qo'shilsin yoki CHECK'dan olib tashlansin.
  - **z.** 11:141, :147 va 12 §7.2: `valuation_method_history` registr emas, istisno ro'yxatiga qo'shilsin.
  - **aa.** 11:241-242: `accept_reason`, `cancel_reason`, `skip_note` (DDL nomlari).

> Eslatma: B-145 (9 band), B-146 (13 band) va B-147 (27 band) guruhlari bir nechta kichik topilmani bitta ID ostida birlashtiradi.

## Kod yozishdan oldin tuzatilishi shart bo'lganlar (top 10)

1. **B-001** — 0003 migratsiyasi `oauth_clients` FK sababli yiqiladi.
2. **B-002** — POS xarajati `reason=expense` DB CHECK'da yiqiladi (18 ↔ 16/20 ziddiyati).
3. **B-003** — `price_changes` holat mashinasi 19 da teskari (QT-M09-02 yiqiladi).
4. **B-004/005/006** — `ettn_documents` holat, CHECK va ustunlari 19 bilan mos emas.
5. **B-007** — faqat qarzga sotuvda `receipt_seq` saqlanadigan joy yo'q.
6. **B-009** — `ledger_adjustments.branch_id` NOT NULL, API'da yo'q.
7. **B-010** — `variance_amount` belgisi va formulasi 20:1124 da teskari.
8. **B-011/012/013** — BO-08/BO-12 mavjud bo'lmagan filtr, maydon va endpoint'larni chaqiradi.
9. **B-017/018/019** — POS-03 `card_manual`, POS-09 `from_warehouse_id` va `/post` qadami.
10. **B-038** — auth sxemasiga yozuvchi SECURITY DEFINER funksiyalarning katta qismi yo'q: login oqimini 12 asosida qurib bo'lmaydi.

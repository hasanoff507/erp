# API katalogi — 1. Kassa (POS), qaytarish, chegirma, tasdiqlash, qarz daftari

*2026-10-15 · Asos: `13-api-katalog-0-umumiy.md` (konventsiyalar — parallel yozilmoqda, shu fayl bilan moslashtirildi), `01-malumotlar-modeli.md`, `02-provodka-qoidalari.md`, `03-integratsiyalar.md` (§1 OFD, §4 Asl belgisi, §9 Click/Payme/Uzum/UzQR), `04-offline-sync.md` (voqea formati, `/sync/push`/`/sync/pull`), `05-xavfsizlik-va-audit.md` (huquqlar, limitlar, CSRF), `09-backend-arxitekturasi.md` (posting service, xato formati), `spec/01-mahsulot/02-modullar-talablari.md` (M01, M02, M03, M08, M16), `03-biznes-jarayonlar.md` (BP-03, BP-11, BP-12), `04-ekranlar-va-ux.md` (POS-01…15, BO-06, BO-16).*

## Asosiy xulosalar

1. **Kassada yaratiladigan hujjatlar REST orqali emas** — smena, chek, qaytarish, qarz to'lovi (POS'da), kassa pul harakati, mijozni tezkor yaratish — barchasi `POST /api/v1/sync/push` orqali **voqea (event)** sifatida yuboriladi (`09-backend-arxitekturasi.md`: "POS uchun alohida `POST /sales` yo'q, yagona yo'l `/sync/push`"). Bu fayl shu voqealarning **to'liq payload sxemasini** belgilaydi — `04-offline-sync.md` faqat umumiy konvertni (`client_event_id`, `seq`, `type`) beradi.
2. **Voqea turlari ro'yxati yakunlandi** (04-offline-sync.md §2'dagi "ochiq savol"): `shift.opened`, `shift.closed`, `sale.created`, `sale.draft_voided`, `receipt.reprinted`, `return.created`, `debt_payment.created`, `cash_movement.created`, **`counterparty.created`** (yangi — tezkor mijoz yaratish offline uchun, US-M08-05), `stock_count.line_recorded` (to'liq sxemasi M04/M05 API hujjatida — bu fayl faqat ro'yxatda tutadi).
3. **Tasdiqlash ikki yo'l bilan ishlaydi**: (a) Menejer/Egasi kassada **jismonan** bo'lsa — PIN mahalliy (offline ham) tekshiriladi, voqea ichida `approval` obyekti bilan yuboriladi, server postingda qayta tekshiradi; (b) Menejer yo'q bo'lsa — **faqat online**, `POST /api/v1/approval-requests` orqali BO-16 navbatiga tushadi, Menejer PWA'dan tasdiqlaydi/rad etadi, POS natijani so'rab oladi (`approval_request_id`). Ikkisi ham bir xil `ApprovalRef` sxemasiga tushadi (2.4-bo'lim).
4. **To'lovlar (UzQR/Click/Payme/Uzum) ikki bosqichli**: avval `POST /api/v1/payments/{provider}/checkout` bilan to'lov boshlanadi (hali chek yo'q — `checkout_ref` qurilma beradi), tasdiq kelgandan keyin (poll yoki webhook) `sale.created` voqeasi shu `checkout_ref`/`provider_tx_id` bilan yuboriladi. Bu to'lovlar **faqat online**.
5. Markirovka tekshiruvi (`POST /api/v1/marking/verify`) — **sinxron**, chekka yozishdan oldin, hech narsa saqlamaydi; offline'da bu chaqiruv ishlamaydi, siyosat `04-offline-sync.md` §7 bo'yicha (narx ma'lum — ruxsat, noma'lum — taqiq).
6. **Qarz daftari** — ikki kiritish yo'li: POS'dan tezkor (`debt_payment.created` voqeasi, offline ham) va back-office'dan (`POST /api/v1/debt-payments`, online). Ikkisi ham bitta `DebtPaymentPostingService`ga tushadi. Qarzni kechish/shubhali belgisi — faqat Egasi, faqat back-office REST (offline'da yo'q).
7. Xato kodlari **UPPER_SNAKE**, har domen uchun alohida (`DISCOUNT_LIMIT_EXCEEDED`, `DEBT_LIMIT_EXCEEDED`, `RETURN_LIMIT_EXCEEDED`, `CASH_WITHDRAW_LIMIT_EXCEEDED`, `PRICE_CHANGE_LIMIT_EXCEEDED`) — to'liq ro'yxat 19-bo'limda, `13-api-katalog-0-umumiy.md` xato katalogi bilan moslashtirish uchun.
8. Bu fayl `01-malumotlar-modeli.md`ni **tahrirlamaydi** — yetishmayotgan maydon/jadvallar (`approval_requests`, `payment_checkouts`, `shifts` ustunlari, `sale_lines`/`return_lines`/`cash_movements` tasdiqlash maydonlari, mijoz hisob-kitob havolasi) 18-bo'limda ro'yxatlangan.
9. Pul — `"12000.00"` (NUMERIC(18,2) string), miqdor — `"2.000"` (NUMERIC(18,3) string), sana — ISO 8601 (`doc_date`: `"2026-10-14"`, `created_at`: `"2026-10-14T09:12:03.482+05:00"`). Barcha ro'yxat endpoint'lari (REST, voqea emas) — cursor pagination `?cursor=&limit=` → `{items, next_cursor}`.

---

## 0. Konventsiyalar (qisqacha — to'liq ro'yxat `13-api-katalog-0-umumiy.md`da)

| Jihat | Qoida |
|---|---|
| Base | `/api/v1` |
| Resurs nomlash | kebab-case, ko'plik: `/discount-rules`, `/approval-requests`, `/debt-openings`, `/debt-writeoffs`, `/cash-movements`, `/fiscal-receipts`, `/price-changes` |
| ID | UUIDv7 (offline qurilmada ham generatsiya qilinadi) |
| Pul | decimal string, 2 kasr: `"12000.00"` |
| Miqdor | decimal string, 3 kasr: `"2.000"` |
| Sana | ISO 8601 |
| Pagination (REST ro'yxat) | `?cursor=&limit=` → `{"items": [...], "next_cursor": "..."}` |
| Sarlavhalar | `X-Branch-Id` (filialga bog'liq resurslarda majburiy), `Idempotency-Key` (back-office yozuvchi so'rovlarda majburiy; `/sync/push`da **ishlatilmaydi** — dedupe `client_event_id` orqali), `X-CSRF-Token` (cookie-autentifikatsiyali so'rovlarda — veb-kassa/back-office; Android Bearer ozod) |
| Xato konverti | `{"error": {"code": "...", "message_key": "errors....", "details": {...}, "request_id": "..."}}` |
| Optimistik qulflash | ma'lumotnoma resurslarida (`counterparties`, `discount-rules`) `version` tanada; mos kelmasa `409 VERSION_CONFLICT` |
| Hujjat REST naqshi (back-office'da yaratiladigan hujjatlar: `price-changes`, `debt-openings`, `debt-writeoffs`) | `POST /{resurs}` (draft) → `POST /{resurs}/{id}/post` → `POST /{resurs}/{id}/cancel` |
| POS hujjatlari | **REST orqali yaratilmaydi** — faqat `POST /api/v1/sync/push` voqeasi (1-bo'lim) |

---

## 1. Endpoint / voqea indeksi

| # | Metod + yo'l / voqea turi | Maqsad | Bo'lim |
|---|---|---|---|
| 1 | event `shift.opened` | Smena ochish | 3.1 |
| 2 | event `shift.closed` | Smena yopish, naqd sanash, Z-hisobot trigger | 3.2 |
| 3 | `GET /api/v1/shifts` | Smenalar ro'yxati (back-office) | 3.3 |
| 4 | `GET /api/v1/shifts/{id}` | Smena tafsiloti | 3.3 |
| 5 | `GET /api/v1/shifts/{id}/z-report` | Z-hisobot | 3.3 |
| 6 | event `sale.created` | Chek (sotuv) | 4 |
| 7 | event `sale.draft_voided` | To'lovdan oldin chek/qator bekor qilish (audit) | 5 |
| 8 | event `receipt.reprinted` | Chekni qayta chop etish (audit) | 6 |
| 9 | event `return.created` | Qaytarish | 7.1 |
| 10 | `GET /api/v1/returns` / `GET /api/v1/returns/{id}` | Qaytarishlar ro'yxati/tafsiloti | 7.2 |
| 11 | `GET /api/v1/discount-rules` / `POST` / `GET /{id}` / `PATCH /{id}` / `POST /{id}/archive` | Avtomatik chegirma qoidalari (M03) | 8.2 |
| 12 | `POST /api/v1/approval-requests` | Masofadan tasdiqlash so'rovi | 9.2 |
| 13 | `GET /api/v1/approval-requests` / `GET /{id}` | Tasdiqlash navbati (BO-16) | 9.3 |
| 14 | `POST /api/v1/approval-requests/{id}/approve` | Tasdiqlash | 9.4 |
| 15 | `POST /api/v1/approval-requests/{id}/reject` | Rad etish | 9.5 |
| 16 | `POST /api/v1/price-changes` → `POST /{id}/post` | Narx o'zgarishi (limitdan katta — approval-requests bilan bog'lanadi) | 10 |
| 17 | `POST /api/v1/counterparties` / `GET` / `GET /{id}` / `PATCH /{id}` | Kontragent (mijoz/yetkazib beruvchi) tezkor yaratish/qidiruv/tahrir | 11.2–11.4 |
| 18 | event `counterparty.created` | Mijozni offline tezkor yaratish | 11.1 |
| 19 | `GET /api/v1/counterparties/{id}/debt-ledger` | Qarz daftari ko'rinishi (BO-06/POS-13) | 12.1 |
| 20 | `POST /api/v1/counterparties/{id}/statement-link` | Telegram uchun qarz hisob-varag'i havolasi | 12.7 |
| 21 | event `debt_payment.created` | Qarz to'lovi (POS, offline ham) | 12.2 |
| 22 | `POST /api/v1/debt-payments` → `POST /{id}/post` | Qarz to'lovi (back-office) | 12.3 |
| 23 | `POST /api/v1/debt-openings` → `POST /{id}/post` | Boshlang'ich qarz | 12.4 |
| 24 | `POST /api/v1/debt-writeoffs` → `POST /{id}/post` | Qarzni kechish (faqat Egasi) | 12.5 |
| 25 | `POST /api/v1/debt-doubtful-flags` / `POST /{id}/unflag` | Shubhali qarz belgisi (faqat Egasi) | 12.6 |
| 26 | `GET /api/v1/reports/debt-aging` | Qarz eskirish hisoboti | 12.8 |
| 27 | event `cash_movement.created` | Kassaga pul qo'yish/olish | 13.1 |
| 28 | `GET /api/v1/cash-movements` | Kassa pul harakati ro'yxati | 13.2 |
| 29 | `GET /api/v1/fiscal-receipts` / `GET /{id}` | Fiskal chek holati | 14.1 |
| 30 | `POST /api/v1/fiscal-receipts/{id}/retry` | Qo'lda qayta urinish (BO-14) | 14.2 |
| 31 | `POST /api/v1/marking/verify` | Markirovka kodini tekshirish (sinxron) | 15 |
| 32 | `POST /api/v1/payments/{provider}/checkout` | To'lov boshlash (uzqr/click/payme/uzum) | 16.2 |
| 33 | `GET /api/v1/payments/{provider}/{provider_tx_id}` | To'lov holati | 16.3 |
| 34 | `POST /api/v1/webhooks/{provider}` | Bank/to'lov tizimi tasdig'i (kiruvchi) | 16.4 |
| 35 | `POST /api/v1/sync/push` / `GET /api/v1/sync/pull` | POS bootstrap/sinxron (to'liq — `04-offline-sync.md`) | 17 |

---

## 2. Umumiy sxemalar

### 2.1 `SyncEventEnvelope` (har bir `/sync/push` voqeasi uchun umumiy konvert)

| Maydon | Tur | Majburiy | Izoh |
|---|---|---|---|
| `client_event_id` | UUIDv7 | ha | Qurilmada yaratiladi, dedupe kaliti (`sync_receipts`) |
| `device_id` | UUIDv7 | ha | `devices` yozuviga mos |
| `seq` | integer | ha | Qurilma ichidagi monoton ketma-ketlik |
| `type` | enum | ha | 1-bo'lim ro'yxatidan |
| `created_at` | ISO 8601 | ha | Qurilma soati |
| `actor_user_id` | UUID | ha | Amalni bajargan kassir/omborchi (PIN bilan) |
| `payload` | object | ha | Pastdagi har bo'limda ta'riflangan |

### 2.2 `PushResultEntry` (`/sync/push` javobidagi har bir natija)

| Maydon | Tur | Izoh |
|---|---|---|
| `client_event_id` | UUIDv7 | So'rovdagi bilan bir xil |
| `status` | enum | `accepted` / `rejected` / `duplicate` |
| `server` | object\|null | `{id, number, ...}` — pastda har voqea uchun aniqlashtiriladi |
| `error_code` | string\|null | 19-bo'lim ro'yxatidan |
| `message` | string\|null | Inson o'qiydigan xabar (frontend `message_key`ga map qiladi) |
| `retryable` | boolean | `true` — qurilma qayta yuboradi; `false` — qo'lda tuzatish/eskalatsiya |

### 2.3 `Money` / `Qty`

`Money` — `"12000.00"` shaklidagi string (NUMERIC(18,2)). `Qty` — `"2.000"` (NUMERIC(18,3)); `units.is_fractional=false` birlikda faqat butun qiymat (`"2.000"`, kasr qismi `000`) qabul qilinadi, aks holda `422 VALIDATION_ERROR`.

### 2.4 `ApprovalRef` (chegirma/qaytarish/qarz/pul olish limitidan oshganda umumiy obyekt)

| Maydon | Tur | Majburiy | Izoh |
|---|---|---|---|
| `mode` | enum | shartli | `local_pin` (Menejer jismonan, PIN mahalliy tekshirilgan) / `remote_request` (BO-16 orqali, online) / `none` (limit ichida — obyekt umuman yuborilmaydi) |
| `approved_by_user_id` | UUID | `local_pin`da ha | PIN kiritgan Menejer/Egasi |
| `pin_verified_locally` | boolean | `local_pin`da ha | Qurilma lokal tekshirdi (server postingda qayta tekshiradi: `approved_by_user_id`ning shu limit uchun yetarli huquqi bormi) |
| `approval_request_id` | UUID | `remote_request`da ha | 9-bo'limdagi resurs, `status=approved` bo'lishi shart |

Server validatsiyasi (ikkala holatda ham): `approved_by_user_id` (yoki `approval_request_id.resolved_by`) ning `role_permissions.limit_value`i so'ralgan summa/foizni qoplashi kerak, aks holda posting rad etiladi (`PIN_REQUIRED` yoki tegishli `*_LIMIT_EXCEEDED`, 19-bo'lim).

### 2.5 `ErrorEnvelope`

```json
{"error": {"code": "DEBT_LIMIT_EXCEEDED", "message_key": "errors.debt_limit_exceeded", "details": {"limit": "500000.00", "requested": "569000.00"}, "request_id": "01933..."}}
```

---

## 3. Smena (shift)

### 3.1 Voqea: `shift.opened`

**Maqsad**: ish kunini boshlash, boshlang'ich naqdni qayd etish. **Huquq**: `shift.open`. **US/ekran**: US-M01-04, POS-01.

| Payload maydoni | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | Qurilma beradi — `shifts.id` |
| `cash_register_id` | UUID | ha | `cash_registers`, shu filialga tegishli |
| `opening_cash` | Money | ha | ≥ `"0.00"` |
| `comment` | string | yo'q | — |

**Server javobi** (`server`): `{id, cash_register_id}`. **Xatolar**: `SHIFT_ALREADY_OPEN` (shu `cash_register_id`da yopilmagan smena bor), `VALIDATION_ERROR`. **Idempotentlik**: `client_event_id`. **Offline**: to'liq ishlaydi — smena ochilishi internet talab qilmaydi (04-offline-sync.md §1, `shift` jadvali). **Invariant**: bitta smena — bitta qurilma (`shifts.device_id = device_id`, keyingi voqealar boshqa qurilmadan kelsa `SHIFT_DEVICE_MISMATCH`).

### 3.2 Voqea: `shift.closed`

**Maqsad**: ish kunini yakunlash, naqd sanash, Z-hisobot generatsiyasi va OFD'ga yuborish (`outbox_jobs(kind=ofd_send)`). **Huquq**: `shift.close` + (naqd sanash) `cash.count.shift`. **US/ekran**: US-M01-04, US-M16-02, POS-07, POS-15.

| Payload maydoni | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `shift_id` | UUID | ha | `shifts.id`, `status=open`, shu `device_id`ga tegishli |
| `counted_cash` | Money | ha | Kassir sanagan naqd |
| `counted_card_total` | Money | yo'q | Qo'lda belgilangan "Karta" (`terminal_ref`) jami — qurilma hisoblab yuboradi, server qayta tekshiradi |
| `variance_note` | string | shartli | `expected_cash ≠ counted_cash` bo'lsa majburiy |

**Server hisoblaydi**: `expected_cash = opening_cash + Σcash_moves(shift_id)` (`stock`/`cash_moves` registridan, US-M16-02 formulasi). `variance = counted_cash − expected_cash`.

**Server javobi** (`server`): `{id, number, z_report: {expected_cash, counted_cash, variance, totals_by_method: {cash, card, uzqr, click, payme, uzum, debt}, vat_total, discount_total, returns_total, sales_count, returns_count}, fiscal: {status: "pending"}}`. **Xatolar**: `SHIFT_NOT_OPEN`, `SHIFT_DEVICE_MISMATCH`, `VALIDATION_ERROR` (`variance_note` yo'q). **Idempotentlik**: `client_event_id`. **Offline**: to'liq ishlaydi; Z-hisobot `fiscal_receipts.status=pending` bilan OFD'ga navbatga qo'yiladi (internet qaytganda, `03-integratsiyalar.md` §1).

### 3.3 Back-office — smena ko'rish

- `GET /api/v1/shifts?cash_register_id=&status=&cursor=&limit=` → `{items:[{id, number, cash_register_id, status, opening_cash, opened_at, closed_at}], next_cursor}`. Huquq: `reports.sales.view` yoki `cash.count.shift`.
- `GET /api/v1/shifts/{id}` → to'liq, `z_report` bilan birga (yopilgan bo'lsa).
- `GET /api/v1/shifts/{id}/z-report` → 3.2'dagi `z_report` obyekti + `fiscal.status`. Huquq: `reports.sales.view`. US/ekran: US-M16-03, POS-07.

---

## 4. Sotuv — voqea `sale.created`

**Maqsad**: chekni yakunlash — qoldiq, qarz, kassa, QQS, buxgalteriya bitta `SalePostingService.post()` tranzaksiyasida (`09-backend-arxitekturasi.md` §2). **Huquq**: `sales.create`. **Davlat tizimi**: OFD, MXIK, (markirovka bo'lsa) Asl belgisi, (UzQR bo'lsa) bank. **US/ekran**: US-M01-01…03/05/06, POS-02/03/04/06.

### 4.1 Payload

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | Qurilma beradi — `sales.id` |
| `branch_id`, `cash_register_id`, `shift_id` | UUID | ha | `shift_id` — `status=open`, shu `device_id` |
| `temp_number` | string | ha | `{device_id}-{local_seq}` (01-malumotlar-modeli.md §6/§11) |
| `doc_date` | ISO sana | ha | Toshkent kuni |
| `counterparty_id` | UUID\|null | shartli | `sale_payments`da `method=debt` bo'lsa majburiy |
| `lines[]` | array | ha, ≥1 | pastda |
| `payments[]` | array | ha, ≥1 | pastda; `Σamount = Σlines.line_total` |
| `comment` | string | yo'q | — |
| `is_offline` | boolean | ha | Qurilma hisoblaydi |
| `offline_since` | ISO vaqt\|null | shartli | `is_offline=true` bo'lsa |

**`lines[]`** (→ `sale_lines`):

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `line_id` | UUIDv7 | ha | — |
| `product_id` | UUID | ha | Katalogda mavjud (lokal keshda) |
| `unit_code` | string | ha | `units.code` |
| `qty` | Qty | ha | `is_fractional=false` bo'lsa butun |
| `unit_price` | Money | ha | QQS bilan (narx tarixidagi joriy narx — "qotirilgan") |
| `vat_rate` | decimal | ha | `12`/`0`/imtiyoz kodi |
| `discount_pct` | decimal\|null | yo'q | `discount_amount` bilan birga kelmaydi |
| `discount_amount` | Money\|null | yo'q | — |
| `discount_source` | enum\|null | shartli | `discount_pct`/`discount_amount` bo'lsa majburiy: `manual` / `standing_customer` / `rule:{discount_rule_id}` |
| `discount_approval` | `ApprovalRef`\|null | shartli | `discount_source=manual` va foiz standart limitdan (odatda 5%) oshsa majburiy (9-bo'lim) |
| `marking_code` | string\|null | shartli | Tovar `is_marked=true` bo'lsa majburiy; **qty har doim `"1.000"`** bo'lishi shart (har kod alohida qator) |
| `marking_offline` | boolean | yo'q | `true` — offline sotilgan, CRPT tasdig'i kutilmoqda (`marking_codes.status=pending_verification`) |

**`payments[]`** (→ `sale_payments`):

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `method` | enum | ha | `cash` / `card` / `uzqr` / `click` / `payme` / `uzum` / `debt` |
| `amount` | Money | ha | > `"0.00"` |
| `terminal_ref` | string\|null | yo'q | Faqat `method=card`, mustaqil terminal operatsiya raqami (online/offline ikkisida ham) |
| `provider_tx_id` | string\|null | shartli | `uzqr`/`click`/`payme`/`uzum`da majburiy — 16-bo'limdagi checkout natijasidan |
| `qr_type` | enum\|null | yo'q | `static`/`dynamic`, faqat `method=uzqr` |
| `debt_approval` | `ApprovalRef`\|null | shartli | `method=debt` va joriy qarz+summa kredit limitidan oshsa (online rejimda majburiy; offline'da — pastga qarang) |

### 4.2 Markirovka qatori qoidalari

- `marking_offline=true` bilan kelgan qator — server `marking_codes(status=pending_verification)` yozadi, `outbox_jobs(kind=marking_sell)` navbatga qo'yadi (internet qaytganda CRPT Turon'ga `verify_code`+`sell`).
- `marking_offline=false` (online sotuv) — `sale.created`dan **oldin** `POST /api/v1/marking/verify` chaqirilgan bo'lishi kerak (15-bo'lim); server shu holatni `marking_codes.status` bo'yicha tekshiradi, mos kelmasa `MARKING_CODE_INVALID`.
- Bir xil `marking_code` ikkinchi marta boshqa hujjatga chiqarilsa — `MARKING_CODE_INVALID` (`details.reason="already_sold"`).

### 4.3 Qarz (debt) va offline limit

- Online: `counterparty.credit_limit` tekshiriladi; oshsa `debt_approval` (`ApprovalRef`) talab qilinadi, bo'lmasa `DEBT_LIMIT_EXCEEDED`.
- **Offline**: limit tekshiruvi qurilmadagi oxirgi sinxronlangan `receivable_balance`/`credit_limit` asosida; oshib ketsa ham sotuv **bloklanmaydi** — server qabul qiladi, `debt_moves.limit_exceeded=true` bayrog'i qo'yadi (xato emas, `status=accepted`, `server.warnings=["DEBT_LIMIT_EXCEEDED"]`), M18 orqali Egasiga xabar (`tekshiruv/savollar-yakuniy-tavsiyalar.md` #7).

### 4.4 Chegirma va standart "bitta eng foydali qoida"

Server discount'ni **qayta hisoblamaydi** (narx kabi "qotirilgan") — faqat: (1) `discount_source` bitta bo'lishini (stacking yo'q), (2) `discount_source=manual`da foiz `role_permissions.discount.give.limit_value`dan oshmasligini (yoki `discount_approval` borligini) tekshiradi. Mos kelmasa `DISCOUNT_LIMIT_EXCEEDED`.

### 4.5 Server javobi va fiskal holat

`server`: `{id, number, fiscal_receipt_seq, fiscal: {status: "pending"}, warnings: []}`. Fiskal belgi/QR keyingi `GET /api/v1/sync/pull`da yoki `GET /api/v1/fiscal-receipts/{id}`da keladi (14-bo'lim).

### 4.6 Xatolar (voqea darajasida)

`SHIFT_NOT_OPEN`, `SHIFT_DEVICE_MISMATCH`, `RECEIPT_SEQ_CONFLICT` (`UNIQUE(cash_register_id, shift_id, receipt_seq)` buzilgan — `retryable:false`, eskalatsiya), `STOCK_NEGATIVE` (faqat **ogohlantirish**, offline overselling ruxsat — qarang 4.7), `DISCOUNT_LIMIT_EXCEEDED`, `DEBT_LIMIT_EXCEEDED`, `MARKING_CODE_INVALID`, `MARKING_PRICE_UNKNOWN_OFFLINE`, `PIN_REQUIRED` (`ApprovalRef` kutilgan, kelmagan), `SUBSCRIPTION_RESTRICTED`, `VALIDATION_ERROR`.

### 4.7 Manfiy qoldiq (overselling)

`STOCK_NEGATIVE` — bu holatda ham `status=accepted` (sotuv bekor qilinmaydi), `warnings` massivida qaytadi; `stock_balances` manfiy qiymatga tushadi, tannarx `pending_cost` sifatida (`02-provodka-qoidalari.md` §3.3, BO-03'da "⚠ manfiy qoldiq" belgisi).

---

## 5. Voqea: `sale.draft_voided`

**Maqsad**: to'lovdan oldin chek/qator bekor qilish — faqat audit, registrga ta'sir yo'q. **Huquq**: `sales.void` (limitsiz, har doim audit). **US/ekran**: US-M01-01 chekka holat, POS-02 "BEKOR".

| Maydon | Tur | Majburiy |
|---|---|---|
| `draft_ref` | string | ha — qurilmadagi lokal chek identifikatori (hali `sales.id` emas) |
| `voided_lines[]` | array\|null | yo'q — `null` = butun chek bekor qilindi |
| `reason` | string | yo'q |

**Server javobi**: `{status: "accepted"}` — faqat `audit_log` yozuvi. **Xatolar**: `VALIDATION_ERROR`. **Idempotentlik**: `client_event_id`. **Offline**: to'liq ishlaydi.

---

## 6. Voqea: `receipt.reprinted`

**Maqsad**: chekni qayta chop etish — "NUSXA" belgisi, audit. **Huquq**: `sales.create` (odatiy kassir amali). **US/ekran**: US-M01-01, POS-04.

| Maydon | Tur | Majburiy |
|---|---|---|
| `sale_id` | UUID | ha |
| `reason` | string | yo'q |

**Server javobi**: `{status: "accepted", copy_label: "NUSXA"}`. Son cheklanmaydi. **Idempotentlik**: `client_event_id` (har chaqiruv alohida audit yozuvi, dedupe faqat takror yuborishdan himoya qiladi).

---

## 7. Qaytarish

### 7.1 Voqea: `return.created`

**Maqsad**: mijozdan tovar qaytarib olish — qoldiq +, kassa/qarz −, QQS −. **Huquq**: `returns.create` (+ limitdan oshganda `returns.approve`). **Davlat tizimi**: (markirovka bo'lsa) Asl belgisi — **faqat online**. **US/ekran**: US-M02-01…03, POS-05.

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | — |
| `branch_id`, `shift_id` | UUID | ha | — |
| `sale_id` | UUID\|null | shartli | `null` = chek topilmagan qaytarish — **har doim** `approval` majburiy (summadan qat'i nazar) |
| `lines[]` | array | ha, ≥1 | pastda |
| `reason` | enum | ha | `defective`/`wrong_item`/`customer_changed_mind`/`other` |
| `refund_method` | enum | ha | `cash`/`card`/`debt_adjustment` (asl to'lov usuliga qarab) |
| `approval` | `ApprovalRef`\|null | shartli | `sale_id=null` YOKI summa `returns.approve.limit_value` (standart 100 000 so'm)dan oshsa majburiy |

**`lines[]`**:

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `sale_line_id` | UUID\|null | shartli | `sale_id` berilgan bo'lsa majburiy |
| `product_id` | UUID | ha | — |
| `qty` | Qty | ha | `SUM(qty) WHERE sale_line_id=X AND posted ≤ sale_lines.qty` (`RETURN_QTY_EXCEEDED`) |
| `unit_price` | Money | ha | `sale_id=null`da — joriy narx (asl chek narxi emas) |
| `marking_code` | string\|null | shartli | Markirovkalangan qatorda majburiy |

**Markirovka qoidasi**: `marking_code` bor qatorli `return.created` — **faqat `is_offline=false`** bilan qabul qilinadi; qurilma offline'da bu amal tugmasini bloklaydi (POS-05), lekin server ham qayta tekshiradi: offline voqea markirovka qatori bilan kelsa `MARKING_CODE_INVALID` (`details.reason="return_requires_online"`).

**Server javobi**: `{id, number, fiscal: {status: "pending"}}` (qaytarish cheki ham OFD'ga yuboriladi). **Xatolar**: `SALE_NOT_FOUND` (`retryable:true` — asl chek hali sinxronlanmagan), `RETURN_QTY_EXCEEDED`, `RETURN_LIMIT_EXCEEDED`, `PIN_REQUIRED`, `MARKING_CODE_INVALID`. **Offline**: oddiy tovar — to'liq ishlaydi (append-only); markirovkalangan — bloklanadi (yuqorida).

### 7.2 Back-office — qaytarishlar ro'yxati

`GET /api/v1/returns?branch_id=&cursor=&limit=` / `GET /api/v1/returns/{id}` → ro'yxat/tafsilot, "chek topilmagan qaytarish"lar alohida `without_receipt=true` bayrog'i bilan ajratilgan (`01-malumotlar-modeli.md` §6). Huquq: `reports.sales.view`.

---

## 8. Chegirmalar

### 8.1 Manual chegirma (sotuv ichida)

4.4-bo'limga qarang — alohida endpoint yo'q, `sale_lines[].discount_*` orqali.

### 8.2 Avtomatik chegirma qoidalari (`discount_rules`, M03)

**Huquq**: `discount.rule.manage` (ko'rish — `discount.give`/ortiqcha huquqsiz ham POS lokal keshdan o'qiydi). **US/ekran**: US-M03-02, BO (Menejer sozlamalari — alohida ekran kodi hujjatda yo'q, M03 bo'limiga tegishli ekran).

- `GET /api/v1/discount-rules?branch_id=&active_only=&cursor=&limit=` → `{items:[{id, name, scope, target_ids, kind, value, branch_ids, valid_from, valid_to, priority, version}], next_cursor}`.
- `POST /api/v1/discount-rules` — body: `{name, scope: "product"|"category"|"all", target_ids[], kind: "percent"|"amount"|"n_plus_m", value, branch_ids[], valid_from, valid_to, priority}`. Huquq: `discount.rule.manage`. Idempotency-Key majburiy.
- `GET /api/v1/discount-rules/{id}`.
- `PATCH /api/v1/discount-rules/{id}` — body `version` bilan birga; mos kelmasa `409 VERSION_CONFLICT`.
- `POST /api/v1/discount-rules/{id}/archive` — soft-delete (`archived_at`).

**Bitta eng foydali qoida**: server bu endpoint darajasida tanlov qilmaydi (tanlov POS/kassada va posting vaqtida `discount_source` orqali qayd etiladi, 4.4-bo'lim) — bu resurs faqat qoidalarni **ro'yxatga oladi**, ularni amalda qo'llash mantiqiy qoida POS keshida + serverda posting tekshiruvida.

**Offline**: `discount_rules` POS'ga `GET /api/v1/sync/pull?scope=settings` orqali tushadi (04-offline-sync.md §1), yozish faqat online.

---

## 9. Tasdiqlash navbati (`approval-requests`)

Umumiy mexanizm — chegirma (limitdan yuqori), qaytarish (limitdan yuqori/chek yo'q), nasiya (limitdan yuqori), kassadan pul olish (limitdan yuqori), narx o'zgarishi (limitdan katta) uchun **bitta** resurs. Menejer/Egasi jismonan kassada bo'lsa bu resurs **chaqirilmaydi** — PIN mahalliy (`ApprovalRef.mode=local_pin`). Faqat Menejer uzoqda, kassir online bo'lganda ishlatiladi (BO-16, POS-06/POS ekranlarida "Menejerga yuborildi" holati).

### 9.1 Sxema (`approval_requests`)

| Maydon | Tur | Izoh |
|---|---|---|
| `id` | UUID | — |
| `kind` | enum | `discount_over_limit` / `return_over_limit` / `return_no_receipt` / `debt_over_limit` / `cash_withdrawal_over_limit` / `price_change` |
| `context` | object | Kind'ga mos snapshot — masalan `{"amount": "569000.00", "requested_pct": "25"}` |
| `linked_doc_type` / `linked_doc_id` | string\|null | `price_change` uchun `price_changes.id` |
| `status` | enum | `pending` / `approved` / `rejected` / `expired` |
| `requested_by`, `requested_at` | UUID, ISO | — |
| `resolved_by`, `resolved_at`, `reject_reason` | UUID\|null, ISO\|null, string\|null | — |
| `expires_at` | ISO | `requested_at + 15 daqiqa` (**taxmin**) |

### 9.2 `POST /api/v1/approval-requests`

**Huquq**: amalni so'ragan rol (`sales.create`/`returns.create`/`debts.create`/`cash.withdraw`/`prices.edit`). **Idempotency-Key** majburiy.

| Maydon | Tur | Majburiy |
|---|---|---|
| `kind` | enum | ha |
| `context` | object | ha |
| `linked_doc_type`, `linked_doc_id` | string\|null | shartli |

Javob: `201 {id, kind, status: "pending", expires_at}`. Bu nuqtada M18 (Telegram/push) orqali Menejer/Egasiga ogohlantirish yuboriladi (implementatsiya — notifications moduli).

### 9.3 `GET /api/v1/approval-requests` / `GET /{id}`

`GET /api/v1/approval-requests?status=pending&cursor=&limit=` → BO-16 navbati. Huquq: `discount.approve`/`returns.approve`/`debts.approve`/`prices.approve` — mos `kind` bo'yicha filtrlanadi (foydalanuvchi faqat o'z huquqiga mos `kind`larni ko'radi). POS tomoni `GET /api/v1/approval-requests/{id}` orqali **poll** qiladi (taxmin: har 3 soniyada) `status` o'zgarishini kutib.

### 9.4 `POST /api/v1/approval-requests/{id}/approve`

Body: `{pin}`. Huquq: `kind`ga mos `*.approve` (masalan `discount_over_limit` → `discount.approve`). Server PIN'ni tekshiradi va `resolved_by`ning `limit_value`i `context.amount`/`requested_pct`ni qoplashini tasdiqlaydi. Javob: `{status: "approved", resolved_by, resolved_at}`. Xato: `PIN_REQUIRED` (PIN noto'g'ri), `APPROVAL_REQUEST_ALREADY_RESOLVED`, `APPROVAL_REQUEST_EXPIRED`.

### 9.5 `POST /api/v1/approval-requests/{id}/reject`

Body: `{reason}` (majburiy). Javob: `{status: "rejected"}`.

### 9.6 Offline cheklovi

`approval-requests` **faqat online** ishlaydi (4.3/7.1'dagi offline over-limit holatlar — bu resursni chaqirmaydi, o'rniga bayroq+audit bilan sotuv/qarz davom etadi, 4.3-bo'lim).

---

## 10. Narx o'zgarishi (`price-changes`) — tasdiqlash bilan bog'lanish

**Huquq**: `prices.edit` (yaratish), `prices.approve` (tasdiqlash — `approval-requests` orqali). **US/ekran**: US-M09-02, BO-16.

- `POST /api/v1/price-changes` — body: `{lines: [{product_id, branch_id|null, new_price, valid_from}]}`. Status `draft`. Idempotency-Key majburiy.
- `POST /api/v1/price-changes/{id}/post` — agar o'zgarish `prices.approve.limit_value`dan (foiz) katta bo'lmasa — darhol `posted` (`product_prices` yangilanadi, `label_print_queue`ga qo'shiladi). Katta bo'lsa — server avtomatik `POST /api/v1/approval-requests {kind:"price_change", linked_doc_id: price_change.id}` yaratadi, `price_changes.status=pending_approval` qaytaradi, javobda `approval_request_id` beriladi.
- Egasi `POST /api/v1/approval-requests/{id}/approve` chaqirganda — server shu `linked_doc_id`ga tegishli `price_changes.post()`ni avtomatik bajaradi (`posted`). Rad etilsa — `price_changes.status=rejected`, `cancel_reason` yoziladi.
- `POST /api/v1/price-changes/{id}/cancel` — faqat `draft`/`pending_approval` holatda.

**Xatolar**: `PRICE_CHANGE_LIMIT_EXCEEDED` (agar kliyent limitni bilib, approval so'ramasdan to'g'ridan-to'g'ri `post` chaqirsa — amalda bu holat yuqoridagi avtomatik approval oqimi bilan oldini olinadi, lekin API himoyasi sifatida saqlanadi), `VERSION_CONFLICT` (agar tovar narxi orada boshqa amal bilan o'zgargan bo'lsa).

---

## 11. Kontragentlar (`counterparties`)

### 11.1 Voqea: `counterparty.created` (POS tezkor yaratish, offline ham)

**Maqsad**: US-M08-05 — "2-3 soniyada, daftarga yozgandek". **Huquq**: `sales.create` yoki `debts.create`. **US/ekran**: US-M08-05, POS-06/POS-13 "+ Mijoz".

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | Qurilma beradi — `counterparties.id` |
| `kind` | enum | ha | `person` (POS'dan odatda shu) |
| `name` | string | ha | — |
| `phone` | string | ha | E.164 yoki O'zbekiston formati (`+998...`) |
| `notify_consent` | boolean | yo'q | Standart `false` |

**Server javobi**: `{id}`. **Idempotentlik**: `client_event_id`. **Offline**: to'liq ishlaydi; keyinchalik `sale.created`/`return.created`/`debt_payment.created` shu `id`ni `counterparty_id` sifatida ishlatadi (bir xil push partiyasida `seq` tartibi bo'yicha oldin yuborilishi shart — 04-offline-sync.md §3.3).

### 11.2 `POST /api/v1/counterparties` (back-office / online POS to'liq yaratish)

**Huquq**: tezkor (`name`+`phone`) — `debts.create`; to'liq (STIR, bank, kredit limiti) — `debts.limit.manage`. Idempotency-Key majburiy.

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `kind` | enum | ha | `person`/`company` |
| `name`, `phone` | string | ha | — |
| `stir` | string\|null | shartli | `kind=company`да B2B e-faktura uchun kerak bo'lsa |
| `legal_address`, `bank_account`, `bank_mfo` | string\|null | yo'q | — |
| `credit_limit` | Money\|null | yo'q | `null` = limitsiz |
| `standing_discount_pct` | decimal\|null | yo'q | — |
| `notify_consent` | boolean | yo'q | — |

Javob: `201 {id, version: 1, ...}`.

### 11.3 `GET /api/v1/counterparties?search=&kind=&cursor=&limit=`

Qidiruv ism/telefon bo'yicha (`pg_trgm`). Huquq: kamida `sales.create`/`debts.create` (barcha rol amalda ko'radi — POS qidiruv keng ochiq). Javob: `{items:[{id, name, phone, is_customer, is_supplier, receivable_balance, credit_limit, version}], next_cursor}`.

### 11.4 `GET /api/v1/counterparties/{id}` / `PATCH /api/v1/counterparties/{id}`

`PATCH` — `version` tanada majburiy, `409 VERSION_CONFLICT` mos kelmasa. Huquq: `debts.limit.manage` (kredit limiti/doimiy chegirma) yoki umumiy tahrir uchun shu huquq.

---

## 12. Qarz daftari (debt notebook, M08)

### 12.1 `GET /api/v1/counterparties/{id}/debt-ledger`

**Maqsad**: qog'oz "qarz daftari" ko'rinishi — US-M08-06, BO-06/POS-13. **Huquq**: `debts.create`/`debts.payment.accept` (POS) yoki `reports.sales.view` (BO-06).

Javob: `{counterparty: {...}, balance: "230000.00", entries: [{id, doc_type, doc_id, doc_date, amount, direction, due_date, promise_date, note, status: "open"|"partially_paid"|"paid", products: [...]}], next_cursor}` — `cursor`/`limit` bilan sahifalanadi.

### 12.2 Voqea: `debt_payment.created` (POS, offline ham)

**Huquq**: `debts.payment.accept`. **US/ekran**: US-M08-04/09, POS-13, BO-06 "To'lov qabul qilish".

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | — |
| `counterparty_id` | UUID | ha | — |
| `amount` | Money | ha | > `"0.00"` |
| `method` | enum | ha | `cash`/`card`/`uzqr`/`click`/`payme`/`uzum` |
| `terminal_ref` | string\|null | yo'q | `method=card` |
| `provider_tx_id` | string\|null | shartli | elektron usullarda |
| `promise_date` | ISO sana\|null | yo'q | Yangi va'da sanasi (agar qoldiq qolsa) |
| `note` | string\|null | yo'q | — |

**Allokatsiya**: server `amount`ni **eng eski ochiq qarzdan boshlab** (`debt_moves`, `due_date ASC`) avtomatik taqsimlaydi (`allocations` registrga yoziladi) — client allokatsiyani tanlamaydi. **Server javobi**: `{id, allocations: [{debt_move_id, amount}], remaining_balance}`. **Offline**: to'liq ishlaydi.

### 12.3 `POST /api/v1/debt-payments` (back-office)

Xuddi 12.2 bilan bir xil maydonlar + `shift_id`/`cash_register_id` **ixtiyoriy** (bank/karta orqali, kassasiz to'lov uchun null). `POST /api/v1/debt-payments` (draft) → `POST /api/v1/debt-payments/{id}/post`. Huquq: `debts.payment.accept`. Idempotency-Key majburiy.

### 12.4 `POST /api/v1/debt-openings` → `POST /{id}/post`

**Maqsad**: eski qog'oz daftardagi qarzlarni ko'chirish (US-M08-07). **Huquq**: `debts.limit.manage` yoki `settings.users`-darajasidagi Egasi amali (aniq kod — `debts.create` yetarli deb qabul qilinadi, chek/faktura yo'q). Body: `{counterparty_id yoki {name, phone}, amount, direction: "receivable"|"payable", due_date|null}` — bir martalik yoki `import_jobs` orqali Excel (`01-malumotlar-modeli.md` §10, alohida import endpoint M04 hujjatida).

### 12.5 `POST /api/v1/debt-writeoffs` → `POST /{id}/post`

**Maqsad**: qarzni kechish. **Huquq**: `debts.forgive` — **faqat Egasi**. Body: `{counterparty_id, amount, reason}` (`reason` majburiy). Audit — majburiy (`05-xavfsizlik-va-audit.md` §6.1). Buxgalter `account_hint: "9430"|"4910"` tanlashi mumkin (ixtiyoriy, `02-provodka-qoidalari.md` §2.15).

### 12.6 Shubhali qarz belgisi

- `POST /api/v1/debt-doubtful-flags` — body `{counterparty_id, reason}` (majburiy). Huquq: `debts.forgive` bilan bir xil cheklov — **faqat Egasi**. Bu provodka yaratmaydi, faqat belgi/ko'rinish.
- `POST /api/v1/debt-doubtful-flags/{id}/unflag` — bekor qilish.
- Tizim avtomatik belgilamaydi — faqat 60+ kunlik ro'yxatni (12.8) eslatma sifatida ko'rsatadi.

### 12.7 `POST /api/v1/counterparties/{id}/statement-link`

**Maqsad**: mijoz Telegram orqali o'z qarz tarixini ko'rishi (US-M08-08). **Huquq**: `debts.create`/`debts.payment.accept`. Javob: `{url, token, expires_at}` — imzolangan, muddatli (**taxmin**: 30 kun), faqat shu `counterparty_id`ning o'z ma'lumotini ko'rsatadigan ochiq (autentifikatsiyasiz, token-asosli) havola; haqiqiy ko'rinish `/public/debt-statements/{token}` yo'lida (bu fayl doirasidan tashqari — M18 hujjatida).

### 12.8 Offline over-limit bayrog'i va eskirish hisoboti

- `GET /api/v1/reports/debt-aging?branch_id=&cursor=&limit=` → `{items:[{counterparty_id, name, balance, bucket: "0-30"|"31-60"|"60+", overdue_since, limit_exceeded_offline: boolean, doubtful_flag: boolean}], next_cursor}`. Huquq: `debts.approve`/`reports.finance.view`. US/ekran: US-M08-10, BO-06.
- `limit_exceeded_offline` — 4.3-bo'limdagi bayroq ko'rinishi (filtr: `?limit_exceeded_offline=true` — Egasi uchun "offline oshib ketgan qarzlar" ro'yxati).

---

## 13. Kassa pul harakati (M16)

### 13.1 Voqea: `cash_movement.created`

**Huquq**: `cash.deposit` (kirim) / `cash.withdraw` (chiqim). **US/ekran**: US-M16-01, POS-14.

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | — |
| `cash_register_id`, `shift_id` | UUID | ha | `shift_id.status=open` |
| `direction` | enum | ha | `in`/`out` |
| `reason` | enum | ha | `collection`/`deposit`/`owner_withdrawal`/`other` |
| `amount` | Money | ha | > `"0.00"` |
| `note` | string | shartli | `reason=other`да majburiy |
| `approval` | `ApprovalRef`\|null | shartli | `direction=out` va summa `cash.withdraw.limit_value` (standart 50 000 so'm)dan oshsa majburiy |

**Server javobi**: `{id}`. **Xatolar**: `CASH_WITHDRAW_LIMIT_EXCEEDED`, `PIN_REQUIRED`, `SHIFT_NOT_OPEN`. **Offline**: to'liq ishlaydi (`local_pin` yo'li bilan — Menejer jismonan); masofadan (`remote_request`) — faqat online, chunki jismoniy pul darhol topshiriladi, aks holda kassir jismonan kutadi.

### 13.2 `GET /api/v1/cash-movements?cash_register_id=&shift_id=&cursor=&limit=`

Faqat o'qish (back-office). Huquq: `reports.sales.view`/`cash.count.shift`.

---

## 14. Fiskal chek holati va qayta urinish

### 14.1 `GET /api/v1/fiscal-receipts?sale_id=&shift_id=&status=&cursor=&limit=` / `GET /api/v1/fiscal-receipts/{id}`

Javob (bitta element): `{id, sale_id, status: "pending"|"sent"|"fiscalized"|"failed", fiscal_sign, qr_url, sent_at, offline_since, attempts}`. Huquq: `reports.sales.view` (BO-14 shu yerdan oziqlanadi).

### 14.2 `POST /api/v1/fiscal-receipts/{id}/retry`

**Maqsad**: BO-14 "Qayta urinish" tugmasi — `outbox_jobs(kind=ofd_send)` ni `queued`ga qaytaradi. **Huquq**: `billing.manage` yoki Egasi darajasidagi amal (aniq kod yo'q — amalda `settings.*` bilan bir xil cheklov tavsiya etiladi, ochiq savol 20-bo'limda). Idempotency-Key majburiy. Javob: `{status: "requeued"}`.

---

## 15. Markirovka tekshiruvi

### `POST /api/v1/marking/verify`

**Maqsad**: DataMatrix kodni skanerlashda — **hech narsa saqlamaydi**, faqat tekshiradi (`03-integratsiyalar.md` §4.1 sequence diagrammasiga mos). **Huquq**: `sales.create`. **Sinxron**, qisqa timeout (taxmin 3s), retry yo'q. **US/ekran**: US-M01-03, POS-02.

| So'rov maydoni | Tur | Majburiy |
|---|---|---|
| `code` | string | ha — DataMatrix xom qiymati |
| `product_id` | UUID\|null | yo'q — agar kod ichidan mahsulot aniqlanmasa, qurilma skanerlangan shtrix-kod/tanlangan tovarni beradi |

**Javob (online, CRPT javob berdi)**: `{valid: true, status: "in_stock"}` yoki `{valid: false, error_code: "MARKING_CODE_INVALID", details: {reason: "already_sold"|"expired"|"invalid_format"}}`.

**Javob (online, CRPT javob bermadi/timeout)**: `503 {error: {code: "MARKING_VERIFY_UNAVAILABLE"}}` — POS bu holatda foydalanuvchiga offline siyosatini (4.2-bo'lim, narx ma'lum bo'lsa ruxsat) taklif qiladi.

**Offline**: bu endpoint umuman chaqirilmaydi (internet yo'q) — POS mahalliy faqat format tekshiradi, `sale.created`ga `marking_offline=true` bilan yuboradi (4.2-bo'lim).

---

## 16. To'lovlar — UzQR / Click / Payme / Uzum (do'kon sotuvi uchun)

### 16.1 Oqim

1. Kassir to'lov usulini tanlaydi (POS-03) → `POST /api/v1/payments/{provider}/checkout`.
2. Mijoz QR'ni skanerlaydi/to'laydi → bank/provayder `POST /api/v1/webhooks/{provider}` orqali serverga xabar beradi (yoki POS `GET .../status` bilan poll qiladi).
3. Tasdiq kelgach, POS `sale.created`ni shu `provider_tx_id` bilan yuboradi (4-bo'lim).

### 16.2 `POST /api/v1/payments/{provider}/checkout`

`provider` ∈ `{uzqr, click, payme, uzum}`. **Huquq**: `sales.create`. **Faqat online**. Idempotency-Key majburiy (takror bosilgan tugma ikkinchi checkout yaratmasligi uchun).

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `checkout_ref` | UUIDv7 | ha | Qurilma beradi — kelgusi `sale.created.payments[].provider_tx_id` bog'lanishi uchun mahalliy kalit |
| `amount` | Money | ha | — |
| `qr_type` | enum\|null | shartli | Faqat `provider=uzqr`: `static`/`dynamic` |
| `context` | enum | ha | `"shop"` (do'kon sotuvi — bu fayl doirasi; `"billing"` — M17 obuna to'lovi, bu yerda ishlatilmaydi) |

Javob: `{checkout_ref, provider_tx_id, qr_payload|checkout_url, status: "pending", expires_at}`.

### 16.3 `GET /api/v1/payments/{provider}/{provider_tx_id}`

Javob: `{provider_tx_id, status: "pending"|"confirmed"|"failed"|"expired", amount, confirmed_at}`. POS poll qiladi (taxmin: 2s interval) chek "to'lov kutilmoqda" holatida (POS-03).

### 16.4 `POST /api/v1/webhooks/{provider}` (kiruvchi)

Bank/to'lov tizimidan keladi — **autentifikatsiya yo'q** (bizning OAuth/CSRF emas), o'rniga provayderning o'z imzosi tekshiriladi (Click MD5, Payme Basic Auth, Uzum/UzQR — protokolga qarab, `03-integratsiyalar.md` §9). Darhol `200` qaytarish shart (aks holda provayder qayta-qayta yuboradi). Idempotentlik: `provider_tx_id` (`UNIQUE`, ikkinchi marta kelsa no-op muvaffaqiyat).

### 16.5 Xatolar

`PAYMENT_PROVIDER_ERROR` (umumiy — tashqi tizim xatosi), `PAYMENT_TIMEOUT` (tasdiq kelmadi, chek "kutilmoqda" holatida qoladi, kassir boshqa usulga o'tishi mumkin). **Offline**: bu bo'lim butunlay ishlamaydi — offline paytda faqat `cash`/`debt`/`card` (qo'lda `terminal_ref`) ishlaydi.

---

## 17. POS bootstrap / `/sync/pull` — qisqa konspekt

To'liq protokol — `04-offline-sync.md` §1–3 (bu fayl **qaytarib yozmaydi**, faqat kassa katalogi nuqtai nazaridan eslatma):

- Qurilma birinchi login'da `devices` yozuvi avtomatik yaratiladi (04-offline-sync.md §9).
- `GET /api/v1/sync/pull?scope=catalog,prices,customers,permissions,limits,settings&cursor=&page_size=500` — kassaga kerakli hamma narsa: katalog+narx (M09), mijoz+qarz balansi (`counterparties`+`debt_balances`), huquq/limit (`role_permissions`), do'kon sozlamalari (`discount_rules`, obuna holati).
- `POST /api/v1/sync/push` — 1-bo'limdagi barcha voqealar shu yagona endpoint orqali, partiyali (taxmin 50 voqea/so'rov), `seq` tartibida.
- Backpressure, idempotentlik, 401/CSRF xatti-harakati, ko'p-tab xavfsizligi — to'liq `04-offline-sync.md` §3.

---

## 18. Ma'lumotlar modeliga kerakli qo'shimchalar

*(`01-malumotlar-modeli.md` tahrir qilinmadi — quyidagilar shu fayl egasiga taklif.)*

1. **Yangi jadval `approval_requests`** — 9.1-bo'limdagi to'liq ustun ro'yxati bilan.
2. **Yangi jadval `payment_checkouts`** — `tenant_id, checkout_ref (UUIDv7, PK), provider, context(shop/billing), branch_id, amount, qr_type, provider_tx_id, status, created_at, expires_at` — UzQR/Click/Payme/Uzum checkout seansini `sale.created`dan **oldin** kuzatish uchun (hozircha `sale_payments.provider_tx_id` faqat o'tkazilgan hujjatga tegishli, lekin checkout chek yaratilishidan oldin boshlanadi).
3. **`shifts` jadvaliga ustunlar**: `counted_cash`, `expected_cash`, `variance`, `variance_note`, `counted_card_total` — hozir faqat "ochilish/yopilish, boshlang'ich va sanalgan naqd" deb umumiy yozilgan (§6), Z-hisobot uchun aniq ustunlar yo'q.
4. **`sale_lines` ustunlari**: `discount_source` (enum), `discount_approval_request_id` (null), `discount_approved_by` (null), `discount_pin_verified_locally` (bool) — hozir faqat `discount` umumiy maydon bor, tasdiqlash izi yo'q.
5. **`return_lines`/`returns` ustunlari**: `approval_request_id`, `approved_by`, `pin_verified_locally` — xuddi shunday.
6. **`cash_movements` ustunlari**: `approval_request_id`, `approved_by`, `pin_verified_locally`.
7. **`price_changes` ustuni**: `approval_request_id` — `pending_approval` holatini `approval_requests`ga bog'lash uchun (hozir bog'lanish mexanizmi aniqlanmagan).
8. **`counterparties` yoki yangi jadval `counterparty_statement_links`**: `token`, `token_hash`, `expires_at`, `created_by` — Telegram hisob-varaq havolasi uchun (12.7-bo'lim), hozircha data modelda yo'q.
9. **`marking_codes` ustuni** (ixtiyoriy, kichik): `verify_source` (`online`/`offline_cache`) — audit uchun, mavjud `status`/`verified_at` yetarli bo'lsa shart emas.
10. **`fiscal_receipts` ustunlari** (kichik): `last_retry_by`, `last_retry_at` — BO-14 qo'lda qayta urinish attributsiyasi uchun.
11. **Sync voqea turlari enum'iga qo'shimcha**: `counterparty.created` — `09-backend-arxitekturasi.md`dagi "to'liq ro'yxat yakunlanadi (ochiq savol)" shu bilan yopiladi.

---

## 19. Ishlatilgan xato kodlari

*(`13-api-katalog-0-umumiy.md` xato katalogi bilan moslashtirish uchun — har biri shu faylda qayerda ishlatilgani ko'rsatilgan.)*

| Kod | Qayerda | Izoh |
|---|---|---|
| `VALIDATION_ERROR` | Deyarli hamma yerda | Sxema/biznes qoida xatosi, 422 |
| `VERSION_CONFLICT` | 8.2, 11.4, 10 | Optimistik qulflash, 409 |
| `SHIFT_NOT_OPEN` | 3.2, 4.6, 13.1 | Smena `open` emas |
| `SHIFT_DEVICE_MISMATCH` | 3.1, 3.2, 4.6 | Boshqa qurilmadan voqea |
| `SHIFT_ALREADY_OPEN` | 3.1 | — |
| `RECEIPT_SEQ_CONFLICT` | 4.6 | `receipt_seq` takrori, `retryable:false` |
| `STOCK_NEGATIVE` | 4.6, 4.7 | Ogohlantirish, sotuvni bloklamaydi |
| `DISCOUNT_LIMIT_EXCEEDED` | 4.4, 4.6 | Chegirma foizi limitdan katta, `ApprovalRef` yo'q |
| `DEBT_LIMIT_EXCEEDED` | 4.3, 4.6 | Online rejimda kredit limiti oshgan, `ApprovalRef` yo'q |
| `RETURN_LIMIT_EXCEEDED` | 7.1 | Qaytarish summasi limitdan katta, `approval` yo'q |
| `RETURN_QTY_EXCEEDED` | 7.1 | Qaytarilayotgan miqdor asl sotilgan miqdordan katta |
| `CASH_WITHDRAW_LIMIT_EXCEEDED` | 13.1 | Pul olish summasi limitdan katta |
| `PRICE_CHANGE_LIMIT_EXCEEDED` | 10 | Narx o'zgarishi foizi limitdan katta |
| `PIN_REQUIRED` | 4, 7, 9, 10, 13 | `ApprovalRef` kutilgan, kelmagan/noto'g'ri PIN |
| `MARKING_CODE_INVALID` | 4.2, 7.1, 15 | Kod noto'g'ri/takroriy/muddati o'tgan/qaytarish online talab qiladi |
| `MARKING_PRICE_UNKNOWN_OFFLINE` | 4.2, 4.6 | Offline, narx qurilmada noma'lum — sotuv taqiq |
| `MARKING_VERIFY_UNAVAILABLE` | 15 | CRPT Turon javob bermadi (online, lekin timeout) |
| `SALE_NOT_FOUND` | 7.1 | Qaytarish uchun asl chek topilmadi, `retryable:true` |
| `APPROVAL_REQUEST_ALREADY_RESOLVED` | 9.4, 9.5 | — |
| `APPROVAL_REQUEST_EXPIRED` | 9.4 | `expires_at` o'tgan |
| `SUBSCRIPTION_RESTRICTED` | 4.6 va deyarli barcha yozuvchi amallar | Obuna lokauti (12-autentifikatsiya-oauth2.md §16) |
| `CSRF_INVALID` | Barcha cookie-autentifikatsiyali yozuvchi so'rovlar | 0-bo'lim |
| `IDEMPOTENCY_IN_PROGRESS` / `IDEMPOTENCY_KEY_REUSED` | Barcha back-office REST yozuvchi so'rovlar | 09-backend-arxitekturasi.md §3 |
| `PERIOD_CLOSED` | 4, 7, 12 (agar `doc_date` yopilgan davrga tushsa) | 02-provodka-qoidalari.md §5.1 |
| `PAYMENT_PROVIDER_ERROR` | 16.2–16.4 | — |
| `PAYMENT_TIMEOUT` | 16.3 | — |
| `DEVICE_REVOKED` | Barcha sync/REST (403) | `04-offline-sync.md` §9 |
| `COUNTERPARTY_NOT_FOUND` | 11, 12 | — |
| `NOT_FOUND` / `FORBIDDEN` | Umumiy | — |

---

## Ochiq savollar

1. `approval_requests.expires_at` (15 daqiqa) va POS poll chastotasi (3 soniya) — manbada raqam yo'q, **taxmin**, pilotda tasdiqlanadi.
2. `fiscal-receipts/{id}/retry` uchun aniq huquq kodi (`billing.manage` vaqtincha tanlandi) — `05-xavfsizlik-va-audit.md` §2.1 katalogiga yangi `integrations.retry` kodi qo'shilishi kerakmi, ochiq.
3. `counterparty_statement_links` tokenining amal qilish muddati (taxmin 30 kun) va yangilash siyosati — ochiq.
4. Narx o'zgarishi (`price-changes`) va umumiy `approval-requests` orasidagi avtomatik bog'lanish (10-bo'lim) — bu faylda taklif qilingan dizayn, `09-backend-arxitekturasi.md`/`01-malumotlar-modeli.md` tomonidan rasmiylashtirilishi kerak.
5. `payment_checkouts` jadvalining saqlash muddati va eskirgan (`expired`) checkout'larni tozalash siklini — ochiq (taxmin: 24 soat).
6. Qo'lda "karta" (`terminal_ref`) bo'yicha yuridik cheklov (`03-integratsiyalar.md` §9.2 ochiq savoli) — bu API dizayniga ta'sir qilmaydi, lekin yakunlanmagan.

## Manbalar

- `spec/02-arxitektura/01-malumotlar-modeli.md`, `02-provodka-qoidalari.md`, `03-integratsiyalar.md` (§1, §4, §9), `04-offline-sync.md`, `05-xavfsizlik-va-audit.md`, `09-backend-arxitekturasi.md`.
- `spec/01-mahsulot/02-modullar-talablari.md` — M01, M02, M03, M08, M16.
- `spec/01-mahsulot/03-biznes-jarayonlar.md` — BP-03, BP-11, BP-12.
- `spec/01-mahsulot/04-ekranlar-va-ux.md` — POS-01…15, BO-06, BO-16.
- `spec/tekshiruv/00-qarorlar.md`, `savollar-yakuniy-tavsiyalar.md` — standart limitlar, offline siyosat qarorlari.

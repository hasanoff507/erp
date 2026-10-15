# API katalogi — 1. Kassa (POS), qaytarish, chegirma, tasdiqlash, qarz daftari

*2026-10-15 · Asos: `17-api-umumiy.md` (konventsiyalar — parallel yozilmoqda, shu fayl bilan moslashtirildi), `11-malumotlar-modeli.md`, `13-provodka-qoidalari.md`, `21-integratsiyalar.md` (§1 OFD, §4 Asl belgisi, §9 Click/Payme/Uzum/UzQR), `16-offline-sync.md` (voqea formati, `/sync/push`/`/sync/pull`), `15-xavfsizlik-va-audit.md` (huquqlar, limitlar, CSRF), `23-backend-arxitekturasi.md` (posting service, xato formati), `spec/kod-uchun/03-modullar-talablari.md` (M01, M02, M03, M08, M16), `04-biznes-jarayonlar.md` (BP-03, BP-11, BP-12), `06-ekranlar-umumiy.md` (POS-01…15, BO-06, BO-16).*

## Asosiy xulosalar

1. **Kassada yaratiladigan hujjatlar REST orqali emas** — smena, chek, qaytarish, qarz to'lovi (POS'da), kassa pul harakati, mijozni tezkor yaratish — barchasi `POST /api/v1/sync/push` orqali **voqea (event)** sifatida yuboriladi (`23-backend-arxitekturasi.md`: "POS uchun alohida `POST /sales` yo'q, yagona yo'l `/sync/push`"). Bu fayl shu voqealarning **to'liq payload sxemasini** belgilaydi — `16-offline-sync.md` faqat umumiy konvertni (`client_event_id`, `seq`, `type`) beradi.
2. **Voqea turlari ro'yxati yakunlandi** (`16-offline-sync.md` §2'dagi "ochiq savol" yopildi, *2026-10-15: qabul-6*): `shift.opened`, `shift.closed`, `sale.created`, `sale.draft_voided`, `receipt.reprinted`, `return.created`, `debt_payment.created`, `cash_movement.created`, **`counterparty.created`** (tezkor mijoz yaratish offline uchun, US-M08-05, §11.1), **`expense.created`** (faqat `cash_movement.created.reason=expense` orqali — §13.1, POS-14 "Xarajat" sababi), `transfer.sent`, `transfer.received`, `stock_count.line_recorded` (M04/M05 ombor voqealari — bular kassa moduliga tegishli emas, to'liq payload sxemasi `19-api-ombor.md`da; bu fayl faqat ro'yxatda tutadi).
3. **Tasdiqlash ikki yo'l bilan ishlaydi**: (a) Menejer/Egasi kassada **jismonan** bo'lsa — PIN mahalliy (offline ham) tekshiriladi, voqea ichida `approval` obyekti bilan yuboriladi, server postingda qayta tekshiradi; (b) Menejer yo'q bo'lsa — **faqat online**, `POST /api/v1/approval-requests` orqali BO-16 navbatiga tushadi, Menejer PWA'dan tasdiqlaydi/rad etadi, POS natijani so'rab oladi (`approval_request_id`). Ikkisi ham bir xil `ApprovalRef` sxemasiga tushadi (2.4-bo'lim).
4. **To'lovlar (UzQR/Click/Payme/Uzum) ikki bosqichli**: avval `POST /api/v1/payments/checkouts` bilan to'lov boshlanadi (hali chek yo'q — `checkout_ref` qurilma beradi), tasdiq kelgandan keyin (poll yoki webhook) `sale.created` voqeasi shu `checkout_ref`/`provider_tx_id` bilan yuboriladi. Bu to'lovlar **faqat online**. *(2026-10-15: qabul-6 — yo'l `/payments/checkouts`ga tuzatildi, A1-20)*
5. Markirovka tekshiruvi (`POST /api/v1/marking-codes/verify`) — **sinxron**, chekka yozishdan oldin, hech narsa saqlamaydi; offline'da bu chaqiruv ishlamaydi, siyosat `16-offline-sync.md` §7 bo'yicha (narx ma'lum — ruxsat, noma'lum — taqiq). *(2026-10-15: qabul-6 — yo'l tuzatildi, A1-29)*
6. **Qarz daftari** — ikki kiritish yo'li: POS'dan tezkor (`debt_payment.created` voqeasi, offline ham) va back-office'dan (`POST /api/v1/debt-payments`, online). Ikkisi ham bitta `DebtPaymentPostingService`ga tushadi. Qarzni kechish/shubhali belgisi — faqat Egasi, faqat back-office REST (offline'da yo'q).
7. Xato kodlari **UPPER_SNAKE**, har domen uchun alohida (`DISCOUNT_LIMIT_EXCEEDED`, `DEBT_LIMIT_EXCEEDED`, `RETURN_LIMIT_EXCEEDED`, `CASH_WITHDRAW_LIMIT_EXCEEDED`, `PRICE_CHANGE_LIMIT_EXCEEDED`) — to'liq ro'yxat 19-bo'limda, `17-api-umumiy.md` xato katalogi bilan moslashtirish uchun.
8. Bu fayl `11-malumotlar-modeli.md`ni **tahrirlamaydi** — yetishmayotgan maydon/jadvallar (`approval_requests`, `payment_checkouts`, `shifts` ustunlari, `sale_lines`/`return_lines`/`cash_movements` tasdiqlash maydonlari, mijoz hisob-kitob havolasi) 18-bo'limda ro'yxatlangan.
9. Pul — `"12000.00"` (NUMERIC(18,2) string), miqdor — `"2.000"` (NUMERIC(18,3) string), sana — ISO 8601 (`doc_date`: `"2026-10-14"`, `created_at`: `"2026-10-14T09:12:03.482Z"` — UTC, `Z` qo'shimchasi, eski `+05:00` misoli o'rniga, `13-0` §3). Hujjat/registr ro'yxatlari — cursor pagination `?cursor=&limit=` → `{items, next_cursor}`; ma'lumotnoma ro'yxatlari (`counterparties`, `discount-rules`) — **page** pagination `?page=&size=` → `{items, total, page, size}` (Q10). *(2026-10-15: qabul-6, A1-15)*

---

## 0. Konventsiyalar (qisqacha — to'liq ro'yxat `17-api-umumiy.md`da)

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
| Xato konverti | `{"error": {"code": "...", "message_key": "errors....", "params": {...}, "details": [...], "request_id": "..."}}` — `details` har doim massiv *(2026-10-15: qabul-6/7, Q2)* |
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
| 26 | `GET /api/v1/reports/debts-aging?direction=receivable` | Qarz eskirish hisoboti (yagona — `20-api-moliya-admin.md`) | 12.8 |
| 27 | event `cash_movement.created` | Kassaga pul qo'yish/olish/xarajat to'lovi | 13.1 |
| 28 | `GET /api/v1/cash-movements` | Kassa pul harakati ro'yxati | 13.2 |
| 29 | `GET /api/v1/fiscal-receipts` / `GET /{id}` | Fiskal chek holati | 14.1 |
| 30 | `POST /api/v1/fiscal-receipts/{id}/retry` | Qo'lda qayta urinish (BO-14) | 14.2 |
| 30a | `GET /api/v1/einvoices?direction=out` / `POST /einvoices` / `POST /einvoices/from-receipt` / sign / `send` / `cancel` | Chiquvchi e-faktura (B2B) | 14a |
| 31 | `POST /api/v1/marking-codes/verify` | Markirovka kodini tekshirish (sinxron) | 15 |
| 32 | `POST /api/v1/payments/checkouts` | To'lov boshlash (uzqr/click/payme/uzum) | 16.2 |
| 33 | `GET /api/v1/payments/checkouts/{checkout_ref}` | To'lov holati | 16.3 |
| 34 | `POST /api/v1/payments/webhooks/{provider}` | Bank/to'lov tizimi tasdig'i (kiruvchi) | 16.4 |
| 35 | `POST /api/v1/sync/push` / `GET /api/v1/sync/pull` | POS bootstrap/sinxron (to'liq — `16-offline-sync.md`) | 17 |
| 36 | `GET /api/v1/sales` / `GET /api/v1/sales/{id}` | Chek qidiruvi (back-office/POS-05) | 4.8 |

*(2026-10-15: qabul-6/7 — #26 13-3ga havola qilindi (A1-26/K1-05), #30a/#36 qo'shildi (A1-24/K1-04, A1-23/K1-01), #31–34 yo'llari tuzatildi (A1-29, A1-20))*

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
| `warnings` | string[] | Katalog kodlari (masalan `STOCK_NEGATIVE`, `DEBT_LIMIT_EXCEEDED`) — amal qabul qilindi, lekin ogohlantirish bilan *(2026-10-15: qabul-6, A1-28)* |

### 2.3 `Money` / `Qty`

`Money` — `"12000.00"` shaklidagi string (NUMERIC(18,2)). `Qty` — `"2.000"` (NUMERIC(18,3)); `units.is_fractional=false` birlikda faqat butun qiymat (`"2.000"`, kasr qismi `000`) qabul qilinadi, aks holda `422 VALIDATION_ERROR`.

### 2.4 `ApprovalRef` (chegirma/qaytarish/qarz/pul olish limitidan oshganda umumiy obyekt)

| Maydon | Tur | Majburiy | Izoh |
|---|---|---|---|
| `mode` | enum | shartli | `local_pin` (Menejer jismonan, PIN mahalliy tekshirilgan) / `remote_request` (BO-16 orqali, online) / `none` (limit ichida — obyekt umuman yuborilmaydi) |
| `approved_by_user_id` | UUID | `local_pin`da ha | PIN kiritgan Menejer/Egasi |
| `pin_verified_locally` | boolean | `local_pin`da ha | Qurilma lokal tekshirdi (server postingda qayta tekshiradi: `approved_by_user_id`ning shu limit uchun yetarli huquqi bormi) |
| `approval_request_id` | UUID | `remote_request`da ha | 9-bo'limdagi resurs, `status=approved` bo'lishi shart |

Server validatsiyasi (ikkala holatda ham): `approved_by_user_id` (yoki `approval_request_id.resolved_by`) ning `role_permissions.limit_value`i so'ralgan summa/foizni qoplashi kerak, aks holda posting rad etiladi (`APPROVAL_INVALID` yoki tegishli `*_LIMIT_EXCEEDED`, 19-bo'lim). `approval_request_id` faqat `status=approved` va hali `consumed` bo'lmagan bo'lsa qabul qilinadi; postingda `approval_requests.status` `consumed`ga o'tadi va `doc_approvals` qatori (`mode`, `approved_by`, `pin_verified_locally`, `approval_request_id`) yoziladi — bitta so'rov bitta hujjatda **faqat bir marta** ishlatiladi. Eski `PIN_REQUIRED` (ApprovalRef kutilgan, kelmagan/yetarsiz) → **`APPROVAL_INVALID`**; §9.4'dagi noto'g'ri PIN → **`PIN_INVALID`**. *(2026-10-15: qabul-6, A1-21)*

### 2.5 `ErrorEnvelope`

```json
{"error": {"code": "DEBT_LIMIT_EXCEEDED", "message_key": "errors.debt_limit_exceeded", "params": {"limit": "500000.00", "requested": "569000.00"}, "details": [], "request_id": "01933..."}}
```

*(`details` har doim massiv, `params` — ixtiyoriy biznes kontekst obyekti; `17-api-umumiy.md` §7.1, 2026-10-15: qabul-6/7)*

---

## 3. Smena (shift)

### 3.1 Voqea: `shift.opened`

**Maqsad**: ish kunini boshlash, boshlang'ich naqdni qayd etish. **Huquq**: `shift.open`. **US/ekran**: US-M01-04, POS-01.

| Payload maydoni | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | Qurilma beradi — `shifts.id` |
| `cash_register_id` | UUID | ha | `cash_registers`, shu filialga tegishli |
| `shift_no` | integer | ha | Qurilma beradi, shu kassa ichida ketma-ket (> 0) — OFD smena raqami, Q11 *(2026-10-15: qabul-6, A1-04)* |
| `opening_cash` | Money | ha | ≥ `"0.00"` |
| `comment` | string | yo'q | — |

**Server javobi** (`server`): `{id, cash_register_id, shift_no}`. **Xatolar**: `SHIFT_ALREADY_OPEN` (shu `cash_register_id`da yopilmagan smena bor), `VALIDATION_ERROR`. **Idempotentlik**: `client_event_id`. **Offline**: to'liq ishlaydi — smena ochilishi internet talab qilmaydi (16-offline-sync.md §1, `shift` jadvali). **Invariant**: bitta smena — bitta qurilma (`shifts.device_id = device_id`, keyingi voqealar boshqa qurilmadan kelsa `SHIFT_DEVICE_MISMATCH`).

### 3.2 Voqea: `shift.closed`

**Maqsad**: ish kunini yakunlash, naqd sanash, Z-hisobot generatsiyasi va OFD'ga yuborish (`outbox_jobs(kind=ofd_send)`). **Huquq**: `shift.close` + (naqd sanash) `cash.count.shift`. **US/ekran**: US-M01-04, US-M16-02, POS-07, POS-15.

| Payload maydoni | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `shift_id` | UUID | ha | `shifts.id`, `status=open`, shu `device_id`ga tegishli |
| `counted_cash` | Money | ha | Kassir sanagan naqd |
| `counted_card_total` | Money | yo'q | Qo'lda belgilangan "Karta" (`terminal_ref`) jami — qurilma hisoblab yuboradi, server qayta tekshiradi |
| `variance_note` | string | shartli | `expected_cash ≠ counted_cash` bo'lsa majburiy |

**Server hisoblaydi**: `expected_cash = opening_cash + Σcash_moves(shift_id)` (`stock`/`cash_moves` registridan, US-M16-02 formulasi). `variance = counted_cash − expected_cash`.

**Server javobi** (`server`): `{id, shift_no, z_report: {expected_cash, counted_cash, variance, totals_by_method: {cash, card, uzqr, click, payme, uzum, debt}, vat_total, discount_total, returns_total, sales_count, returns_count}, fiscal: {status: "pending"}}`. **Xatolar**: `SHIFT_NOT_OPEN`, `SHIFT_DEVICE_MISMATCH`, `VALIDATION_ERROR` (`variance_note` yo'q). **Idempotentlik**: `client_event_id`. **Offline**: to'liq ishlaydi; Z-hisobot `fiscal_receipts.status=pending` bilan OFD'ga navbatga qo'yiladi (internet qaytganda, `21-integratsiyalar.md` §1). *(`number` → `shift_no`, 2026-10-15: qabul-6, A1-05)*

### 3.3 Back-office — smena ko'rish

- `GET /api/v1/shifts?cash_register_id=&status=&cursor=&limit=` → `{items:[{id, shift_no, cash_register_id, status, opening_cash, opened_at, closed_at}], next_cursor}`. Huquq: `reports.sales.view` yoki `cash.count.shift`.
- `GET /api/v1/shifts/{id}` → to'liq, `z_report` bilan birga (yopilgan bo'lsa). **`status=open`da qo'shimcha**: `running_totals: {totals_by_method: {cash, card, uzqr, click, payme, uzum, debt}, sales_count, voided_count, returns_total, cash_in, cash_out, expected_cash}` — POS-07/POS-15 online solishtirish manbai (offline — lokal hisob). *(2026-10-15: qabul-7, K1-02)*
- `GET /api/v1/shifts/{id}/z-report` → 3.2'dagi `z_report` obyekti + `fiscal.status`. Huquq: `reports.sales.view`. US/ekran: US-M16-03, POS-07.

---

## 4. Sotuv — voqea `sale.created`

**Maqsad**: chekni yakunlash — qoldiq, qarz, kassa, QQS, buxgalteriya bitta `SalePostingService.post()` tranzaksiyasida (`23-backend-arxitekturasi.md` §2). **Huquq**: `sales.create`. **Davlat tizimi**: OFD, MXIK, (markirovka bo'lsa) Asl belgisi, (UzQR bo'lsa) bank. **US/ekran**: US-M01-01…03/05/06, POS-02/03/04/06.

### 4.1 Payload

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | Qurilma beradi — `sales.id` |
| `branch_id`, `cash_register_id`, `shift_id` | UUID | ha | `shift_id` — `status=open`, shu `device_id` |
| `receipt_seq` | integer | ha | **Qurilma beradi**, shu smena ichida ketma-ket; server faqat `UNIQUE (tenant_id, cash_register_id, shift_id, receipt_seq)` tekshiradi, o'zi raqam bermaydi (Q11, `kod-uchun/01-qarorlar.md` #12) *(2026-10-15: qabul-6, A1-01 — eng og'ir KRITIK muammo)* |
| `temp_number` | string | ha | `{device_id}-{local_seq}` (11-malumotlar-modeli.md §6/§11) |
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
| `unit_code` | string | ha | `units.code`; **hosila — faqat validatsiya** (`products.unit_code`ga teng bo'lishi shart), `sale_lines`da saqlanmaydi *(2026-10-15: qabul-6, A1-11)* |
| `qty` | Qty | ha | `is_fractional=false` bo'lsa butun |
| `price` | Money (4 xona) | ha | QQS bilan, 4 xonali o'nlik satr — narx tarixidagi joriy narx ("qotirilgan"); eski `unit_price`/2 xona o'rniga (Q14) *(2026-10-15: qabul-6, A1-06)* |
| `vat_rate` | decimal (2 xona) | ha | `"12.00"`/`"0.00"` |
| `vat_exemption_code` | string\|null | shartli | QQS imtiyoz kodi; `vat_rate`/`vat_exemption_code`dan kamida biri to'ldirilgan bo'lishi shart *(2026-10-15: qabul-6, A1-07 — `vat_rate` ikki maydonga bo'lindi)* |
| `discount_pct` | decimal\|null | yo'q | Ma'lumot uchun; limit tekshiruvi shundan, manba — `discount_amount` |
| `discount_amount` | Money\|null | yo'q | Hisob-kitob manbai; `discount_pct` bilan **birga kelishi mumkin** |
| `discount_source` | enum\|null | shartli | `discount_amount`/`discount_pct` bo'lsa majburiy: `manual` / `standing_customer` / `rule` |
| `discount_rule_id` | UUID\|null | shartli | `discount_source=rule`da majburiy *(2026-10-15: qabul-6, A1-08 — avvalgi `"rule:{discount_rule_id}"` satri o'rniga alohida maydon)* |
| `discount_approval` | `ApprovalRef`\|null | shartli | `discount_source=manual` va foiz standart limitdan (odatda 5%) oshsa majburiy (9-bo'lim) |
| `marking_code` | string\|null | shartli | Tovar `is_marked=true` bo'lsa majburiy; **qty har doim `"1.000"`** bo'lishi shart (har kod alohida qator) |
| `marking_offline` | boolean | yo'q | `true` — offline sotilgan, CRPT tasdig'i kutilmoqda (`marking_codes.status=pending_verification`) |

`line_no` — qurilma yubormaydi, server massiv indeksi+1 sifatida belgilaydi; `line_total`, `vat_amount`, `cost_amount` — qurilma hisoblab yuboradi (offline jami ko'rsatish uchun), server qayta hisoblab tekshiradi (mos kelmasa `VALIDATION_ERROR`) — "qotirilgan" qiymat emas. *(2026-10-15: qabul-6, A1-11)*

**`payments[]`** (→ `sale_payments`):

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `method` | enum | ha | `cash` / `card` / `uzqr` / `click` / `payme` / `uzum` / `debt` |
| `amount` | Money | ha | > `"0.00"` |
| `terminal_ref` | string\|null | yo'q | Faqat `method=card`, mustaqil terminal operatsiya raqami (online/offline ikkisida ham) |
| `checkout_ref` | UUID\|null | shartli | `uzqr`/`click`/`payme`/`uzum`da majburiy — 16-bo'limdagi `payment_checkouts.checkout_ref` |
| `provider_tx_id` | string\|null | shartli | `uzqr`/`click`/`payme`/`uzum`da majburiy — 16-bo'limdagi checkout natijasidan |
| `qr_type` | enum\|null | yo'q | `static`/`dynamic`, faqat `method=uzqr` |
| `due_date` | ISO sana\|null | yo'q | Faqat `method=debt` — "va'da sanasi" (bitta, bo'lib to'lash grafigi yo'q); `debt_moves.due_date`/`counterparties.debt_due_date` manbasi *(2026-10-15: qabul-6/7, A1-09/K1-09)* |
| `debt_approval` | `ApprovalRef`\|null | shartli | `method=debt` va joriy qarz+summa kredit limitidan oshsa (online rejimda majburiy; offline'da — pastga qarang) |

### 4.2 Markirovka qatori qoidalari

- `marking_offline=true` bilan kelgan qator — server `marking_codes(status=pending_verification)` yozadi, `outbox_jobs(kind=marking_sell)` navbatga qo'yadi (internet qaytganda CRPT Turon'ga `verify_code`+`sell`).
- `marking_offline=false` (online sotuv) — `sale.created`dan **oldin** `POST /api/v1/marking-codes/verify` chaqirilgan bo'lishi kerak (15-bo'lim); server shu holatni `marking_codes.status` bo'yicha tekshiradi, mos kelmasa `MARKING_CODE_INVALID`.
- Bir xil `marking_code` ikkinchi marta boshqa hujjatga chiqarilsa — `MARKING_CODE_INVALID` (`details.reason="already_sold"`).

### 4.3 Qarz (debt) va offline limit

- Online: `counterparty.credit_limit` tekshiriladi; oshsa `debt_approval` (`ApprovalRef`) talab qilinadi, bo'lmasa `DEBT_LIMIT_EXCEEDED`.
- **Offline**: limit tekshiruvi qurilmadagi oxirgi sinxronlangan `receivable_balance`/`credit_limit` asosida; oshib ketsa ham sotuv **bloklanmaydi** — server qabul qiladi, `sales.debt_limit_exceeded=true` bayrog'i qo'yadi (xato emas, `status=accepted`, `warnings=["DEBT_LIMIT_EXCEEDED"]`), M18 orqali Egasiga xabar (`tarix/tekshiruv/savollar-yakuniy-tavsiyalar.md` #7). *(`debt_moves.limit_exceeded` — append-only registr, bayroq saqlay olmaydi — `sales.debt_limit_exceeded`ga ko'chirildi, 2026-10-15: qabul-6, A1-10)*

### 4.4 Chegirma va standart "bitta eng foydali qoida"

Server discount'ni **qayta hisoblamaydi** (narx kabi "qotirilgan") — faqat: (1) `discount_source` bitta bo'lishini (stacking yo'q), (2) `discount_source=manual`da foiz `role_permissions.discount.give.limit_value`dan oshmasligini (yoki `discount_approval` borligini) tekshiradi. Mos kelmasa `DISCOUNT_LIMIT_EXCEEDED`.

### 4.5 Server javobi va fiskal holat

`server`: `{id, number, fiscal_receipt_seq, fiscal: {status: "pending"|"deferred"}, warnings: []}` — `fiscal_receipt_seq` qurilma yuborgan `receipt_seq`ning aks-sadosi (server o'zi raqam bermaydi, A1-01). Fiskal belgi/QR keyingi `GET /api/v1/sync/pull`da yoki `GET /api/v1/fiscal-receipts/{id}`da keladi (14-bo'lim).

**`fiscal.status` qiymati — qarzga sotuv, asoschi qarori Q3** *(2026-10-15)*:
- `payments[]`da **faqat** `method=debt` bo'lsa — `fiscal_receipts` yozuvi **yaratilmaydi**, javobdagi `fiscal.status="deferred"` (chek chiqarilmaydi, `fiscal_receipt_seq` shunga qaramay saqlanadi — keyinchalik qarz to'langanda chiqariladigan chekda ishlatiladi, §12.2). Sotuv hujjatining o'zi (qoldiq −, qarz +) oddiy tartibda yoziladi.
- **Aralash to'lov** (masalan qisman naqd + qisman qarz, `payments[]`da bir nechta usul) — naqd/karta/UzQR/Click/Payme/Uzum qismiga **darhol** oddiy fiskal chek chiqariladi (`fiscal_receipts.kind='sale'`, faqat non-debt qatorlar/summasi bilan), `fiscal.status="pending"→"sent"`; qarz qismiga mos chek **qarz to'langanda** chiqariladi (quyida). Javobda `fiscal.status` aralash holatda ham `"pending"` (non-debt qismi fiskallanadi) qaytadi.
- Faqat naqd/karta/UzQR/Click/Payme/Uzum (qarz yo'q) — o'zgarishsiz, `fiscal.status="pending"`.
- Amalga oshirish `FiscalPolicy` (tenant/global sozlama, `13-provodka-qoidalari.md` §5.x) ortida — buxgalter/yurist javobigacha standart yoqilgan holatda qoladi, kelajakda o'zgartirish migratsiyasiz.

**Chek tili — asoschi qarori Q2** *(2026-10-15, R-05 o'rniga)*: chek matni/payload **ikki tilda** chiqadi — har bir tovar qatori `"{products.name} / {products.name_ru}"` (name_ru bo'lmasa faqat `name`); sarlavha/yakun matnlari ham ikki tilda ("Jami / Итого", "Qaytim / Сдача" va h.k., to'liq lug'at — chop etish shabloni, 4.9-bo'lim). Fiskal rekvizitlar (STIR, OFD QR, chek raqami) — OFD operatori talab qilgan formatda, tarjima qilinmaydi.

### 4.6 Xatolar (voqea darajasida)

`SHIFT_NOT_OPEN`, `SHIFT_DEVICE_MISMATCH`, `RECEIPT_SEQ_CONFLICT` (`UNIQUE(cash_register_id, shift_id, receipt_seq)` buzilgan — `retryable:false`, eskalatsiya), `STOCK_NEGATIVE` (faqat **ogohlantirish**, offline overselling ruxsat — qarang 4.7), `DISCOUNT_LIMIT_EXCEEDED`, `DEBT_LIMIT_EXCEEDED`, `MARKING_CODE_INVALID`, `MARKING_PRICE_UNKNOWN_OFFLINE`, `APPROVAL_INVALID` (`ApprovalRef` kutilgan, kelmagan — eski `PIN_REQUIRED` o'rniga, A1-21), `SUBSCRIPTION_RESTRICTED`, `VALIDATION_ERROR`.

### 4.7 Manfiy qoldiq (overselling)

`STOCK_NEGATIVE` — bu holatda ham `status=accepted` (sotuv bekor qilinmaydi), `warnings` massivida qaytadi; `stock_balances` manfiy qiymatga tushadi, tannarx `pending_cost` sifatida (`13-provodka-qoidalari.md` §3.3, BO-03'da "⚠ manfiy qoldiq" belgisi).

### 4.8 Back-office — chek qidiruvi (`GET /sales`)

*(2026-10-15: qabul-6/7, A1-23/K1-01 — 13-0 §9 "Istisno" bandi: `sales` back-office'da faqat o'qiladi, `POST /sales` yo'q)*

- `GET /api/v1/sales?number=&fiscal_receipt_seq=&shift_id=&counterparty_id=&doc_date__gte=&doc_date__lte=&status=&cursor=&limit=` → `{items:[{id, number, temp_number, doc_date, total, payments_summary, counterparty_id, is_offline, has_returns}], next_cursor}`.
- `GET /api/v1/sales/{id}` → to'liq hujjat: qatorlar (`sale_line_id`, `qty`, `returned_qty` — hosila, `marking_code`), to'lovlar, fiskal holat. **`POST /sales/{id}/cancel` yo'q** — o'tkazilgan chek bekor qilinmaydi, tuzatish faqat `return.created` (Q9).
- Huquq: `sales.create` (faqat o'z filiali, POS-05 chek qidiruvi) yoki `reports.sales.view` (BO-09).

### 4.9 Chek chop etish shabloni — ikki til (asoschi qarori, Q2)

Chek chop etish shabloni (`shared/lib/printer` adapteri — WebUSB/Serial/Bluetooth/tarmoq/bulut, `24-frontend-arxitekturasi.md` §6; native Android — `EscPosPrinterAdapter`/`FiscalPrinterAdapter`, `28-android-pos.md` §4) qator formatini quyidagicha quradi: `{products.name}` birinchi qatorda, agar `products.name_ru` bo'sh bo'lmasa — ikkinchi (kichikroq shrift) qatorda `"{products.name_ru}"`, yoki 80mm'da bitta qatorga sig'adigan `"{name} / {name_ru}"` shablonda. Standart lug'at (uz → ru) sarlavha/yakun matnlari uchun: `Jami`→`Итого`, `Chegirma`→`Скидка`, `Qaytim`→`Сдача`, `Naqd`→`Наличные`, `Karta`→`Карта`, `Qarz`→`Долг`, `Sana`→`Дата`, `Kassir`→`Кассир`. Fiskal rekvizitlar bloki (STIR/korxona nomi, OFD QR, fiskal belgi, chek raqami) — OFD operatori hujjatida ko'rsatilgan tayyor formatda chiqadi, tarjima qilinmaydi. Shablon joylashuvi: `receipt_templates/{80mm,58mm}.json` (print adapter konfiguratsiyasi — bulut-print/ESC-POS/fiskal printer ikkisi ham shu shablondan foydalanadi).

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
| `branch_id`, `shift_id`, `cash_register_id` | UUID | ha | `cash_register_id` — DB-03, qaytarish kassa harakati/fiskal cheki uchun majburiy *(2026-10-15: qabul-6, A1-02)* |
| `receipt_seq` | integer | ha | Qurilma beradi, shu smena ichida ketma-ket (qaytarish cheki ham OFD'ga yuboriladi, Q11) *(2026-10-15: qabul-6, A1-02)* |
| `sale_id` | UUID\|null | shartli | `null` = chek topilmagan qaytarish — **har doim** `approval` majburiy (summadan qat'i nazar) |
| `counterparty_id` | UUID\|null | shartli | `refund_method=debt_adjustment`da majburiy (DB-03) *(2026-10-15: qabul-6, A1-02)* |
| `is_offline` | boolean | ha | Qurilma hisoblaydi *(2026-10-15: qabul-6, A1-02)* |
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
| `vat_rate` | decimal (2 xona) | ha | `"12.00"`/`"0.00"` *(2026-10-15: qabul-6, A1-02, DB-03)* |
| `vat_exemption_code` | string\|null | shartli | QQS imtiyoz kodi *(2026-10-15: qabul-6, A1-02)* |
| `marking_code` | string\|null | shartli | Markirovkalangan qatorda majburiy |

**Markirovka qoidasi**: `marking_code` bor qatorli `return.created` — **faqat `is_offline=false`** bilan qabul qilinadi; qurilma offline'da bu amal tugmasini bloklaydi (POS-05), lekin server ham qayta tekshiradi: offline voqea markirovka qatori bilan kelsa `MARKING_RETURN_REQUIRES_ONLINE` (eski `MARKING_CODE_INVALID`+`details.reason="return_requires_online"` o'rniga, `kod-uchun/01-qarorlar.md` #17, 2026-10-15: qabul-6/7).

**Server javobi**: `{id, number, fiscal_receipt_seq, fiscal: {status: "pending"}}` (qaytarish cheki ham OFD'ga yuboriladi). **Xatolar**: `SALE_NOT_FOUND` (`retryable:true` — asl chek hali sinxronlanmagan), `RETURN_QTY_EXCEEDED`, `RETURN_LIMIT_EXCEEDED`, `APPROVAL_INVALID`, `MARKING_CODE_INVALID`, `MARKING_RETURN_REQUIRES_ONLINE`. **Offline**: oddiy tovar — to'liq ishlaydi (append-only); markirovkalangan — bloklanadi (yuqorida).

### 7.2 Back-office — qaytarishlar ro'yxati

`GET /api/v1/returns?branch_id=&cursor=&limit=` / `GET /api/v1/returns/{id}` → ro'yxat/tafsilot, "chek topilmagan qaytarish"lar alohida `without_receipt=true` bayrog'i bilan ajratilgan (`11-malumotlar-modeli.md` §6). Huquq: `reports.sales.view`.

---

## 8. Chegirmalar

### 8.1 Manual chegirma (sotuv ichida)

4.4-bo'limga qarang — alohida endpoint yo'q, `sale_lines[].discount_*` orqali.

### 8.2 Avtomatik chegirma qoidalari (`discount_rules`, M03)

**Huquq**: `discount.rule.manage` (ko'rish — `discount.give`/ortiqcha huquqsiz ham POS lokal keshdan o'qiydi). **US/ekran**: US-M03-02, BO (Menejer sozlamalari — alohida ekran kodi hujjatda yo'q, M03 bo'limiga tegishli ekran).

- `GET /api/v1/discount-rules?branch_id=&active_only=&page=&size=` → `{items:[{id, name, scope, target_ids, kind, value, branch_ids, valid_from, valid_to, priority, version}], total, page, size}` — **page pagination** (ma'lumotnoma, eski cursor o'rniga, Q10/A1-15).
- `POST /api/v1/discount-rules` — body: `{name, scope: "product"|"category"|"all", target_ids[], kind: "percent"|"amount"|"n_plus_m", value, branch_ids[], valid_from, valid_to, priority}`. Huquq: `discount.rule.manage`. Idempotency-Key majburiy.
- `GET /api/v1/discount-rules/{id}`.
- `PATCH /api/v1/discount-rules/{id}` — body `version` bilan birga; mos kelmasa `409 VERSION_CONFLICT`.
- `POST /api/v1/discount-rules/{id}/archive` — soft-delete (`archived_at`).

**Bitta eng foydali qoida**: server bu endpoint darajasida tanlov qilmaydi (tanlov POS/kassada va posting vaqtida `discount_source` orqali qayd etiladi, 4.4-bo'lim) — bu resurs faqat qoidalarni **ro'yxatga oladi**, ularni amalda qo'llash mantiqiy qoida POS keshida + serverda posting tekshiruvida.

**Offline**: `discount_rules` POS'ga `GET /api/v1/sync/pull?scope=settings` orqali tushadi (16-offline-sync.md §1), yozish faqat online.

---

## 9. Tasdiqlash navbati (`approval-requests`)

Umumiy mexanizm — chegirma (limitdan yuqori), qaytarish (limitdan yuqori/chek yo'q), nasiya (limitdan yuqori), kassadan pul olish (limitdan yuqori), narx o'zgarishi (limitdan katta) uchun **bitta** resurs. Menejer/Egasi jismonan kassada bo'lsa bu resurs **chaqirilmaydi** — PIN mahalliy (`ApprovalRef.mode=local_pin`). Faqat Menejer uzoqda, kassir online bo'lganda ishlatiladi (BO-16, POS-06/POS ekranlarida "Menejerga yuborildi" holati).

### 9.1 Sxema (`approval_requests`)

| Maydon | Tur | Izoh |
|---|---|---|
| `id` | UUID | — |
| `kind` | enum | `discount_over_limit` / `return_over_limit` / `return_no_receipt` / `debt_over_limit` / `cash_withdrawal_over_limit` / `price_change` / `expense_over_limit` / `write_off_over_limit` *(2026-10-15: qabul-6/7, A1-17/K1-07 — ikki kind qo'shildi)* |
| `permission_code` | string | Tasdiqlovchida bo'lishi shart kod (server to'ldiradi — `15-xavfsizlik-va-audit.md` §2.3 xaritasi) |
| `requested_value` | decimal\|null | Summa yoki foiz (`role_permissions.limit_value` bilan bir xil birlik, 4 xonali satr) |
| `context` | object | Kind'ga mos snapshot — masalan `{"amount": "569000.00", "requested_pct": "25"}` |
| `linked_doc_type` / `linked_doc_id` | string\|null | `price_change` uchun `price_changes.id` |
| `status` | enum | `pending` / `approved` / `rejected` / `expired` / `consumed` — hujjat postingda shu so'rovni ishlatgach `consumed`ga o'tadi, qayta ishlatilmaydi *(2026-10-15: qabul-6, A1-17)* |
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

`GET /api/v1/approval-requests?status=pending&cursor=&limit=` → BO-16 navbati. Huquq: `discount.approve`/`returns.approve`/`debts.approve`/`prices.approve`/`cash.withdraw` (limit ≥ summa)/`expenses.approve`/`stock.writeoff` (yuqori limit) — mos `kind` bo'yicha filtrlanadi (foydalanuvchi faqat o'z huquqiga mos `kind`larni ko'radi); to'liq `kind` → tasdiqlovchi ruxsati xaritasi — `15-xavfsizlik-va-audit.md` §2.3 (yagona manba, P-07). POS tomoni `GET /api/v1/approval-requests/{id}` orqali **poll** qiladi (taxmin: har 3 soniyada) `status` o'zgarishini kutib. *(2026-10-15: qabul-6/7, A1-22/K1-07)*

### 9.4 `POST /api/v1/approval-requests/{id}/approve`

Body: `{pin}`. Huquq: `kind`ga mos `*.approve` (masalan `discount_over_limit` → `discount.approve`; `cash_withdrawal_over_limit` → `cash.withdraw`, tasdiqlovchining `limit_value`i `context.amount`dan yuqori yoki limitsiz bo'lishi shart). Server PIN'ni tekshiradi va `resolved_by`ning `limit_value`i `context.amount`/`requested_pct`ni qoplashini tasdiqlaydi; muvaffaqiyatli bo'lsa `status=approved`, keyinchalik bog'langan hujjat postingda shu so'rovni **bir marta** ishlatadi va `status=consumed`ga o'tkazadi (`doc_approvals` qatori yoziladi). Javob: `{status: "approved", resolved_by, resolved_at}`. Xato: `APPROVAL_INVALID` (noto'g'ri `kind`/huquq), `PIN_INVALID` (noto'g'ri PIN), `APPROVAL_REQUEST_ALREADY_RESOLVED`, `APPROVAL_REQUEST_EXPIRED`. *(2026-10-15: qabul-6, A1-21)*

### 9.5 `POST /api/v1/approval-requests/{id}/reject`

Body: `{reason}` (majburiy). Javob: `{status: "rejected"}`.

### 9.6 Offline cheklovi

`approval-requests` **faqat online** ishlaydi (4.3/7.1'dagi offline over-limit holatlar — bu resursni chaqirmaydi, o'rniga bayroq+audit bilan sotuv/qarz davom etadi, 4.3-bo'lim).

---

## 10. Narx o'zgarishi (`price-changes`) — tasdiqlash bilan bog'lanish

*(2026-10-15: qabul-6/7, A1-19/K1-08 — qisqartirildi)*

`price-changes` resursining to'liq ta'rifi — **`19-api-ombor.md` §4 (yagona manba)**: `POST /api/v1/price-changes` body'da `lines[].new_price` (4 xonali satr) va `lines[].valid_from` (qator darajasida, hujjat `doc_date` bilan birga). Tasdiqlash — **faqat `approval-requests`** (`kind=price_change`, BO-16 yagona navbat) orqali: `POST /api/v1/price-changes/{id}/post` limitdan katta bo'lsa `202 {status:"draft", approval_request_id}` qaytaradi (`APPROVAL_REQUIRED`); Egasi (`prices.approve`, faqat Egasi) `approve`laganda server `linked_doc_id`ga tegishli `price_changes.post()`ni avtomatik bajaradi. 13-2'dagi `/price-changes/{id}/approve`/`/reject` endpoint'lari **olib tashlanadi**.

**Xatolar**: `PRICE_CHANGE_LIMIT_EXCEEDED` (API himoyasi sifatida saqlanadi), `VERSION_CONFLICT` (agar tovar narxi orada boshqa amal bilan o'zgargan bo'lsa).

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

**Server javobi**: `{id}`. **Idempotentlik**: `client_event_id`. **Offline**: to'liq ishlaydi; keyinchalik `sale.created`/`return.created`/`debt_payment.created` shu `id`ni `counterparty_id` sifatida ishlatadi (bir xil push partiyasida `seq` tartibi bo'yicha oldin yuborilishi shart — 16-offline-sync.md §3.3).

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

Javob: `201 {id, version: 1, ...}`. `notify_consent_at` — hosila, `notify_consent=true` bo'lganda server vaqtni yozadi (tanadan qabul qilinmaydi). *(2026-10-15: qabul-6, A1-18)*

### 11.3 `GET /api/v1/counterparties?search=&kind=&page=&size=`

Qidiruv ism/telefon bo'yicha (`pg_trgm`). Huquq: kamida `sales.create`/`debts.create` (barcha rol amalda ko'radi — POS qidiruv keng ochiq). Javob: `{items:[{id, name, phone, is_customer, is_supplier, receivable_balance, credit_limit, version}], total, page, size}` — **page pagination** (ma'lumotnoma, eski cursor o'rniga, Q10/A1-15).

### 11.4 `GET /api/v1/counterparties/{id}` / `PATCH /api/v1/counterparties/{id}`

`PATCH` — `version` tanada majburiy, `409 VERSION_CONFLICT` mos kelmasa. Huquq: `debts.limit.manage` (kredit limiti/doimiy chegirma) yoki umumiy tahrir uchun shu huquq.

---

## 12. Qarz daftari (debt notebook, M08)

### 12.1 `GET /api/v1/counterparties/{id}/debt-ledger`

**Maqsad**: qog'oz "qarz daftari" ko'rinishi — US-M08-06, BO-06/POS-13. **Huquq**: `debts.create`/`debts.payment.accept` (POS) yoki `reports.sales.view` (BO-06).

Javob: `{counterparty: {...}, balance: "230000.00", entries: [{id, doc_type, doc_id, doc_date, amount, direction, due_date, promise_date, comment, status: "open"|"partially_paid"|"paid", products: [...]}], next_cursor}` — `cursor`/`limit` bilan sahifalanadi. `promise_date` — hosila: oxirgi `debt_payments.promise_date` yoki (hali to'lov bo'lmagan bo'lsa) `sale_payments.due_date`; `status` — allokatsiyalardan hisoblanadi (`11-malumotlar-modeli.md` §8 nasiya holat mashinasi); `note` maydoni → `comment`ga qayta nomlandi (DDL ustun nomi bilan bir xil). *(2026-10-15: qabul-6, A1-12)*

### 12.2 Voqea: `debt_payment.created` (POS, offline ham)

**Huquq**: `debts.payment.accept`. **US/ekran**: US-M08-04/09, POS-13, BO-06 "To'lov qabul qilish".

**Fiskal chek — asoschi qarori Q3** *(2026-10-15, reestr #9 — qaror qabul qilindi, qonuniylik tasdig'i ochiq)*: har bir `debt_payment.created` (`post` bosqichida, `FiscalPolicy` yoqilgan bo'lsa — standart yoqilgan) uchun `fiscal_receipts` yozuvi yaratiladi, `kind='debt_settlement'`, summasi = `amount`. Tovar qatorlari qo'lda kiritilmaydi — server §12.2 allokatsiya natijasidagi `debt_payment_allocations`dan qaysi `sales`ni qancha yopganini oladi va shu sotuv(lar)ning `sale_lines`idan **proporsional** (yopilgan summa ulushiga ko'ra) qator ro'yxatini chiqaradi (QQS ham shu nisbatda bo'linadi). `debt_openings` (eski qog'oz qarz) allokatsiyasiga mos qism — tovar qatorsiz, faqat umumiy summa bilan (asl tovar tarkibi tizimda yo'q). Chiqarilgan chek ikki tilda (Q2, 4.9-bo'lim). `FiscalAdapter.issue_credit_payment()` porti shu oqimni amalga oshiradi (eski "stub" holati — endi faol, kod `FiscalPolicy.debt_settlement_receipts_enabled` ortida, buxgalter/yurist tasdig'i kelganda o'chirish/o'zgartirish migratsiyasiz). Daromad/QQS tan olish vaqti (sotuvdami, to'lovdami) — **ochiq savol buxgalter uchun**, `13-provodka-qoidalari.md` §5.x'da belgilangan.

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | — |
| `counterparty_id` | UUID | ha | — |
| `branch_id`, `cash_register_id`, `shift_id` | UUID | shartli | `method=cash`da `cash_register_id`/`shift_id` majburiy (`shift.status=open`); bank/karta orqali — bo'sh (DB-04) *(2026-10-15: qabul-6, A1-03)* |
| `amount` | Money | ha | > `"0.00"` |
| `method` | enum | ha | `cash`/`card`/`uzqr`/`click`/`payme`/`uzum`/`bank` *(2026-10-15: qabul-6 — `bank` qo'shildi, DB-04)* |
| `terminal_ref` | string\|null | yo'q | `method=card` |
| `checkout_ref` | UUID\|null | shartli | Elektron usullarda — 16-bo'limdagi `payment_checkouts.checkout_ref` *(2026-10-15: qabul-6, A1-03)* |
| `provider_tx_id` | string\|null | shartli | elektron usullarda |
| `promise_date` | ISO sana\|null | yo'q | Yangi va'da sanasi (agar qoldiq qolsa) — qoldiq qolsa mijozning **joriy** va'da sanasi yangilanadi (`counterparties.debt_due_date`, B-01); `debt_payments.promise_date` ustuni saqlanadi (`sale_payments.due_date`dan farqli nom, DB-04/DB-08) *(2026-10-15: qabul-7, K1-09)* |
| `comment` | string\|null | yo'q | Eski `note` o'rniga, DDL ustun nomi bilan bir xil *(2026-10-15: qabul-6, A1-03)* |

**Allokatsiya**: server `amount`ni **eng eski ochiq qarzdan boshlab** (`debt_moves`, `due_date ASC`) avtomatik taqsimlaydi (`allocations` registrga yoziladi) — client allokatsiyani tanlamaydi. **Server javobi**: `{id, allocations: [{target_doc_type, target_doc_id, amount}], remaining_balance, fiscal: {status: "pending"}}` (eski `{debt_move_id, amount}` o'rniga — `debt_payment_allocations` ustunlari bilan bir xil, A1-13; `fiscal` — Q3, yuqoridagi `debt_settlement` cheki). **Offline**: to'liq ishlaydi; qurilma oflayn bo'lsa `fiscal_receipts(kind=debt_settlement, status=pending, offline_since=...)` navbatga qo'yiladi, internet qaytganda `outbox_jobs(kind=ofd_send)` orqali OFD'ga yuboriladi (`16-offline-sync.md` §3.5/§7, `21-integratsiyalar.md` §1).

### 12.3 `POST /api/v1/debt-payments` (back-office)

Xuddi 12.2 bilan bir xil maydonlar + `shift_id`/`cash_register_id` **ixtiyoriy** (bank/karta orqali, kassasiz to'lov uchun null). `POST /api/v1/debt-payments` (draft) → `POST /api/v1/debt-payments/{id}/post`. Huquq: `debts.payment.accept`. Idempotency-Key majburiy.

### 12.4 `POST /api/v1/debt-openings` → `POST /{id}/post`

**Maqsad**: eski qog'oz daftardagi qarzlarni ko'chirish (US-M08-07). **Huquq**: **`stock.opening.manage`** (eski aralash "`debts.limit.manage` yoki Egasi amali" matni o'rniga — P-01) yoki `debts.limit.manage`. Body: `{counterparty_id yoki {name, phone}, amount, direction: "receivable"|"payable", due_date|null}` — bir martalik yoki `import_jobs` orqali Excel (`11-malumotlar-modeli.md` §10, alohida import endpoint M04 hujjatida). *(2026-10-15: qabul-6, A1-14)*

### 12.5 `POST /api/v1/debt-writeoffs` → `POST /{id}/post`

**Maqsad**: qarzni kechish. **Huquq**: `debts.forgive` — **faqat Egasi**. Body: `{counterparty_id, amount, reason, account_choice}` (`reason` majburiy; `account_choice` — eski `account_hint` o'rniga, standart `"9430"`, muqobil `"4910"`, ixtiyoriy, `13-provodka-qoidalari.md` §2.15). Audit — majburiy (`15-xavfsizlik-va-audit.md` §6.1). *(2026-10-15: qabul-6, A1-14)*

### 12.6 Shubhali qarz belgisi

- `POST /api/v1/debt-doubtful-flags` — body `{counterparty_id, reason}` (majburiy). Huquq: `debts.forgive` bilan bir xil cheklov — **faqat Egasi**. Bu provodka yaratmaydi, faqat belgi/ko'rinish.
- `POST /api/v1/debt-doubtful-flags/{id}/unflag` — bekor qilish.
- Tizim avtomatik belgilamaydi — faqat 60+ kunlik ro'yxatni (12.8) eslatma sifatida ko'rsatadi.

### 12.7 `POST /api/v1/counterparties/{id}/statement-link`

**Maqsad**: mijoz Telegram orqali o'z qarz tarixini ko'rishi (US-M08-08). **Huquq**: `debts.create`/`debts.payment.accept`. Javob: `{url, token, expires_at}` — imzolangan, muddatli (**taxmin**: 30 kun), faqat shu `counterparty_id`ning o'z ma'lumotini ko'rsatadigan ochiq (autentifikatsiyasiz, token-asosli) havola; haqiqiy ko'rinish `/public/debt-statements/{token}` yo'lida (bu fayl doirasidan tashqari — M18 hujjatida).

### 12.8 Offline over-limit bayrog'i va eskirish hisoboti

*(2026-10-15: qabul-6/7, A1-26/K1-05 — takrorlangan endpoint o'chirildi)*

Qarz eskirishi hisoboti — **yagona manba `20-api-moliya-admin.md` #21, `GET /api/v1/reports/debts-aging?direction=receivable&bucket=&branch_id=&limit_exceeded_offline=&as_of=`** (eski `GET /api/v1/reports/debt-aging` bu faylda **o'chirildi**). Javobga shu fayldagi maydonlar qo'shiladi: `rows[].due_date`, `rows[].overdue_since`, `rows[].limit_exceeded_offline` (4.3-bo'limdagi bayroq ko'rinishi — Egasi uchun "offline oshib ketgan qarzlar" ro'yxati), `rows[].doubtful_flag`. **60+ kunlik eslatma**: `bucket="60+"` filtri — tizim avtomatik hech narsani belgilamaydi, faqat eslatma ro'yxati sifatida ko'rsatiladi (US-M08-10, §12.6). Huquq: `debts.approve`/`reports.finance.view`.

---

## 13. Kassa pul harakati (M16)

### 13.1 Voqea: `cash_movement.created`

**Huquq**: `cash.deposit` (kirim) / `cash.withdraw` (chiqim). **US/ekran**: US-M16-01, POS-14.

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | — |
| `cash_register_id`, `shift_id` | UUID | ha | `shift_id.status=open` |
| `direction` | enum | ha | `in`/`out` |
| `reason` | enum | ha | `collection`/`deposit`/`owner_withdrawal`/`expense`/`other` *(2026-10-15: qabul-7 — `expense` qo'shildi, K1-06)* |
| `expense_category_id` | UUID\|null | shartli | `reason=expense`da majburiy; server shu tranzaksiyada `expenses(source='cash', status='posted')` yozadi (`13-provodka-qoidalari.md` §2.17) *(2026-10-15: qabul-7, K1-06)* |
| `amount` | Money | ha | > `"0.00"` |
| `comment` | string | shartli | Eski `note` o'rniga (DDL ustun nomi bilan bir xil); `reason=other`да majburiy *(2026-10-15: qabul-6, A1-16)* |
| `approval` | `ApprovalRef`\|null | shartli | `direction=out` va summa `cash.withdraw.limit_value` (standart 50 000 so'm)dan oshsa majburiy |

**Server javobi**: `{id}`. **Xatolar**: `CASH_WITHDRAW_LIMIT_EXCEEDED`, `APPROVAL_INVALID`, `SHIFT_NOT_OPEN`. **Offline**: to'liq ishlaydi (`local_pin` yo'li bilan — Menejer jismonan); masofadan (`remote_request`) — faqat online, chunki jismoniy pul darhol topshiriladi, aks holda kassir jismonan kutadi.

### 13.2 `GET /api/v1/cash-movements?cash_register_id=&shift_id=&cursor=&limit=`

Faqat o'qish (back-office). Huquq: `reports.sales.view` **yoki** `cash.count.shift` (`20-api-moliya-admin.md` #52 bilan yagona ta'rif — o'sha faylda ruxsat `cash.deposit` emas, shu ikkisiga tuzatiladi; POS'dan faqat `cash_movement.created` voqeasi keladi, bu REST — back-office uchun, masalan inkasso yozish). *(2026-10-15: qabul-6, A1-27)*

---

## 14. Fiskal chek holati va qayta urinish

### 14.1 `GET /api/v1/fiscal-receipts?sale_id=&shift_id=&status=&cursor=&limit=` / `GET /api/v1/fiscal-receipts/{id}`

Javob (bitta element): `{id, sale_id, status: "pending"|"sent"|"fiscalized"|"failed", fiscal_sign, qr_url, sent_at, offline_since, attempts}`. Huquq: `reports.sales.view` (BO-14 shu yerdan oziqlanadi).

### 14.2 `POST /api/v1/fiscal-receipts/{id}/retry`

**Maqsad**: BO-14 "Qayta urinish" tugmasi — `outbox_jobs(kind=ofd_send)` ni `queued`ga qaytaradi. **Huquq**: **`integrations.retry`** (eski vaqtinchalik `billing.manage` o'rniga — OFD/e-faktura/markirovka integratsiya ishini qo'lda qayta navbatga qo'yish, Egasi/Menejer/Buxgalter; "Ochiq savollar" #2 yopildi). Idempotency-Key majburiy. Javob: `{status: "requeued"}`. *(2026-10-15: qabul-6, A1-25, P-04)*

---

## 14a. Chiquvchi e-faktura (`einvoices`, `direction=out`)

*(2026-10-15: qabul-6/7, A1-24/K1-04 — yangi bo'lim; BP-03 B2B nasiya, BP-13, `kod-uchun/01-qarorlar.md` #18; 13-2 "sotuv/qarz katalogida" deydi, bu faylda yo'q edi — eng og'ir KRITIK muammolardan biri)*

- `GET /api/v1/einvoices?direction=out&status=&cursor=&limit=` — ruxsat `einvoice.sign` yoki `purchases.post`.
- `POST /api/v1/einvoices` — body `{direction:"out", source:"sale"|"manual", sale_id|null, counterparty_id, related_doc_type:"sales"|null, related_doc_id|null, doc_date, lines?}` → `201 {id, status:"draft"}`. B2B nasiya sotuvdan (`counterparty.kind=company`) server avtomatik `draft` yaratishi mumkin (`source="sale"`). Ruxsat `einvoice.create`. Xatolar: `EINVOICE_COUNTERPARTY_INCOMPLETE`.
- `POST /api/v1/einvoices/from-receipt` — body `{sale_id, counterparty_id}` — chekdan oldindan to'ldirilgan qoralama (qaytarishlar ayirilgan holda); `related_doc` bog'lanadi, QQS/provodka **yo'q** (`13-provodka-qoidalari.md` 2.22). Ruxsat `einvoice.create`. Xatolar: `EINVOICE_ALREADY_LINKED`, `EINVOICE_AMOUNT_EXCEEDS_RECEIPT`.
- `POST /einvoices/{id}/sign-challenge`, `POST /einvoices/{id}/submit-signed` — `19-api-ombor.md` §19 dagi bilan **bir xil** (umumiy, yo'nalishdan qat'i nazar); ruxsat `einvoice.sign`. Xato `EIMZO_SIGN_FAILED`.
- `POST /api/v1/einvoices/{id}/send` → `202`, `outbox_jobs(kind=einvoice_send)` → faqat Faktura.uz (tavsiya #4); `POST /api/v1/einvoices/{id}/cancel` (operator qoidasi bo'yicha). Ruxsat `einvoice.sign`.

Provodka **yo'q** (02 §2.22); bitta hujjatga bitta faol chiquvchi faktura — `uq_einvoice_out_per_doc` (DB-21).

---

## 15. Markirovka tekshiruvi

### `POST /api/v1/marking-codes/verify`

*(eski `POST /api/v1/marking/verify` o'rniga — resurs nomi jadvaldan kelib chiqadi, kebab-case ko'plik, 2026-10-15: qabul-6, A1-29)*

**Maqsad**: DataMatrix kodni skanerlashda — **hech narsa saqlamaydi**, faqat tekshiradi (`21-integratsiyalar.md` §4.1 sequence diagrammasiga mos). **Huquq**: `sales.create`. **Sinxron**, qisqa timeout (taxmin 3s), retry yo'q. **US/ekran**: US-M01-03, POS-02.

| So'rov maydoni | Tur | Majburiy |
|---|---|---|
| `code` | string | ha — DataMatrix xom qiymati |
| `product_id` | UUID\|null | yo'q — agar kod ichidan mahsulot aniqlanmasa, qurilma skanerlangan shtrix-kod/tanlangan tovarni beradi |

**Javob (online, CRPT javob berdi)**: `{valid: true, status: "in_stock"}` yoki `{valid: false, error_code: "MARKING_CODE_INVALID", details: {reason: "already_sold"|"expired"|"invalid_format"}}`.

**Javob (online, CRPT javob bermadi/timeout)**: `503 {error: {code: "MARKING_VERIFY_UNAVAILABLE"}}` — POS bu holatda foydalanuvchiga offline siyosatini (4.2-bo'lim, narx ma'lum bo'lsa ruxsat) taklif qiladi.

**Offline**: bu endpoint umuman chaqirilmaydi (internet yo'q) — POS mahalliy faqat format tekshiradi, `sale.created`ga `marking_offline=true` bilan yuboradi (4.2-bo'lim).

---

## 16. To'lovlar — UzQR / Click / Payme / Uzum (do'kon sotuvi uchun)

*(2026-10-15: qabul-6, A1-20, Q12 — yo'llar `17-api-umumiy.md` §14 "ikki kontekst" qoidasiga moslashtirildi: do'kon to'lovi `/payments/*`, bizning obuna `/billing/*`)*

### 16.1 Oqim

1. Kassir to'lov usulini tanlaydi (POS-03) → `POST /api/v1/payments/checkouts` (`provider` tanada).
2. Mijoz QR'ni skanerlaydi/to'laydi → bank/provayder `POST /api/v1/payments/webhooks/{provider}` orqali serverga xabar beradi (yoki POS `GET /api/v1/payments/checkouts/{checkout_ref}` bilan poll qiladi).
3. Tasdiq kelgach, POS `sale.created`ni shu `checkout_ref`/`provider_tx_id` bilan yuboradi (4-bo'lim).

### 16.2 `POST /api/v1/payments/checkouts`

**Huquq**: `sales.create`. **Faqat online**. Idempotency-Key majburiy (takror bosilgan tugma ikkinchi checkout yaratmasligi uchun).

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `checkout_ref` | UUIDv7 | ha | Qurilma beradi — kelgusi `sale.created.payments[].checkout_ref` bog'lanishi uchun mahalliy kalit |
| `provider` | enum | ha | `uzqr`/`click`/`payme`/`uzum` |
| `cash_register_id` | UUID | ha | Shu kassaga tegishli checkout |
| `amount` | Money | ha | — |
| `qr_type` | enum\|null | shartli | Faqat `provider=uzqr`: `static`/`dynamic` |

`context` maydoni **olib tashlandi** — bu endpoint faqat do'kon sotuvi uchun (`"billing"` kontekst — M17 obuna to'lovi, `POST /billing/checkout`, alohida yo'l). Javob: `{checkout_ref, provider, provider_tx_id|null, qr_payload|checkout_url, status: "pending", expires_at}`. Webhook tenantni `app.payments_checkout_by_provider_tx()`/`app.payments_checkout_by_ref()` orqali topadi (DB-30).

### 16.3 `GET /api/v1/payments/checkouts/{checkout_ref}`

Javob: `{checkout_ref, provider, provider_tx_id, status: "pending"|"confirmed"|"failed"|"expired", amount, confirmed_at}`. POS poll qiladi (taxmin: 2s interval) chek "to'lov kutilmoqda" holatida (POS-03).

### 16.4 `POST /api/v1/payments/webhooks/{provider}` (kiruvchi)

Bank/to'lov tizimidan keladi — **autentifikatsiya yo'q** (bizning OAuth/CSRF emas), o'rniga provayderning o'z imzosi tekshiriladi (Click MD5, Payme Basic Auth, Uzum/UzQR — protokolga qarab, `21-integratsiyalar.md` §9). Darhol `200` qaytarish shart (aks holda provayder qayta-qayta yuboradi). Idempotentlik: `provider_tx_id` (`UNIQUE`, ikkinchi marta kelsa no-op muvaffaqiyat).

### 16.5 Xatolar

`PAYMENT_PROVIDER_ERROR` (umumiy — tashqi tizim xatosi), `PAYMENT_NOT_CONFIRMED` (tasdiq kelmadi; eski `PAYMENT_TIMEOUT` o'rniga — muddat o'tishi checkout `status=expired` bilan ifodalanadi, chek "kutilmoqda" holatida qoladi, kassir boshqa usulga o'tishi mumkin). **Offline**: bu bo'lim butunlay ishlamaydi — offline paytda faqat `cash`/`debt`/`card` (qo'lda `terminal_ref`) ishlaydi.

---

## 17. POS bootstrap / `/sync/pull` — qisqa konspekt

To'liq protokol — `16-offline-sync.md` §1–3 (bu fayl **qaytarib yozmaydi**, faqat kassa katalogi nuqtai nazaridan eslatma):

- Qurilma birinchi login'da `devices` yozuvi avtomatik yaratiladi (16-offline-sync.md §9).
- `GET /api/v1/sync/pull?scope=catalog,prices,customers,permissions,limits,settings&cursor=&page_size=500` — kassaga kerakli hamma narsa: katalog+narx (M09), mijoz+qarz balansi (`counterparties`+`debt_balances`), huquq/limit (`role_permissions`), do'kon sozlamalari (`discount_rules`, obuna holati).
- `POST /api/v1/sync/push` — 1-bo'limdagi barcha voqealar shu yagona endpoint orqali, partiyali (taxmin 50 voqea/so'rov), `seq` tartibida.
- Backpressure, idempotentlik, 401/CSRF xatti-harakati, ko'p-tab xavfsizligi — to'liq `16-offline-sync.md` §3.

---

## 18. Ma'lumotlar modeliga kerakli qo'shimchalar

*(2026-10-15: qabul-6, A1-30 — hal qilindi, `tarix/tekshiruv/qabul-6-api-db.md`: DB-03, DB-04, DB-07…DB-11, DB-28 (va `11-malumotlar-modeli.md` M-05, M-12…M-20). #9 (`marking_codes.verify_source`) va #10 (`fiscal_receipts.last_retry_*`) taklifi **rad etildi** — `audit_log` yetarli deb topildi. Sync voqea turlari enum'i — `16-offline-sync.md` §2, S-01 (`counterparty.created`, `transfer.sent`, `transfer.received`, `expense.created`, `stock_count.line_recorded` bilan yakunlangan).)*

---

## 19. Ishlatilgan xato kodlari

*(2026-10-15: qabul-6, A1-31 — `17-api-umumiy.md` §15 **yagona manba**; bu jadval faqat shu faylda qaysi kod qayerda ishlatilganini ko'rsatadi, nomlar 0-umumiy §15 xaritasiga moslashtirilgan.)*

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
| `APPROVAL_INVALID` | 4, 7, 9, 10, 13 | `ApprovalRef` kutilgan, kelmagan yoki tasdiqlovchi huquqi yetarli emas (eski `PIN_REQUIRED` o'rniga) |
| `PIN_INVALID` | 9.4 | Noto'g'ri PIN bilan `approve` |
| `MARKING_CODE_INVALID` | 4.2, 15 | Kod noto'g'ri/takroriy/muddati o'tgan |
| `MARKING_CODE_ALREADY_SOLD` | 4.2 | Kod ikkinchi marta boshqa hujjatga chiqarilsa |
| `MARKING_RETURN_REQUIRES_ONLINE` | 7.1 | Markirovkalangan tovar qaytarishi faqat online (eski `MARKING_CODE_INVALID`+`details.reason` o'rniga) |
| `MARKING_PRICE_UNKNOWN_OFFLINE` | 4.2, 4.6 | Offline, narx qurilmada noma'lum — sotuv taqiq |
| `MARKING_VERIFY_UNAVAILABLE` | 15 | CRPT Turon javob bermadi (online, lekin timeout) |
| `SALE_NOT_FOUND` | 7.1 | Qaytarish uchun asl chek topilmadi, `retryable:true` |
| `APPROVAL_REQUEST_ALREADY_RESOLVED` | 9.4, 9.5 | — |
| `APPROVAL_REQUEST_EXPIRED` | 9.4 | `expires_at` o'tgan |
| `SUBSCRIPTION_RESTRICTED` | 4.6 va deyarli barcha yozuvchi amallar | Obuna lokauti (14-autentifikatsiya-oauth2.md §16) |
| `CSRF_INVALID` | Barcha cookie-autentifikatsiyali yozuvchi so'rovlar | 0-bo'lim |
| `IDEMPOTENCY_IN_PROGRESS` / `IDEMPOTENCY_KEY_REUSED` | Barcha back-office REST yozuvchi so'rovlar | 23-backend-arxitekturasi.md §3 |
| `PERIOD_CLOSED` | 4, 7, 12 (agar `doc_date` yopilgan davrga tushsa) | 13-provodka-qoidalari.md §5.1 |
| `PAYMENT_PROVIDER_ERROR` | 16.2–16.4 | — |
| `PAYMENT_NOT_CONFIRMED` | 16.3 | Eski `PAYMENT_TIMEOUT` o'rniga |
| `DEVICE_REVOKED` | Barcha sync/REST (403) | `16-offline-sync.md` §9 |
| `NOT_FOUND` | 11, 12 va umumiy | Eski `COUNTERPARTY_NOT_FOUND`/`DEBT_NOT_FOUND` o'rniga, `params.resource` bilan |
| `PERMISSION_DENIED` | Umumiy | Eski `FORBIDDEN` o'rniga |

---

## Ochiq savollar

1. `approval_requests.expires_at` (15 daqiqa) va POS poll chastotasi (3 soniya) — manbada raqam yo'q, **taxmin**, pilotda tasdiqlanadi.
2. ~~`fiscal-receipts/{id}/retry` huquq kodi~~ — *(2026-10-15: qabul-6 — HAL QILINDI: `integrations.retry`, §14.2/A1-25, `15-xavfsizlik-va-audit.md` §2.1 P-01)*.
3. `counterparty_statement_links` tokenining amal qilish muddati (taxmin 30 kun) va yangilash siyosati — ochiq.
4. ~~Narx o'zgarishi va `approval-requests` bog'lanishi~~ — *(2026-10-15: qabul-6/7 — HAL QILINDI: `price-changes` to'liq ta'rifi `19-api-ombor.md` §4 (yagona manba), tasdiq faqat `approval-requests`, 10-bo'lim/A1-19/K1-08)*.
5. `payment_checkouts` jadvalining saqlash muddati va eskirgan (`expired`) checkout'larni tozalash siklini — ochiq (taxmin: 24 soat).
6. Qo'lda "karta" (`terminal_ref`) bo'yicha yuridik cheklov (`21-integratsiyalar.md` §9.2 ochiq savoli) — bu API dizayniga ta'sir qilmaydi, lekin yakunlanmagan.

## Manbalar

- `spec/kod-uchun/11-malumotlar-modeli.md`, `13-provodka-qoidalari.md`, `21-integratsiyalar.md` (§1, §4, §9), `16-offline-sync.md`, `15-xavfsizlik-va-audit.md`, `23-backend-arxitekturasi.md`.
- `spec/kod-uchun/03-modullar-talablari.md` — M01, M02, M03, M08, M16.
- `spec/kod-uchun/04-biznes-jarayonlar.md` — BP-03, BP-11, BP-12.
- `spec/kod-uchun/06-ekranlar-umumiy.md` — POS-01…15, BO-06, BO-16.
- `spec/kod-uchun/01-qarorlar.md`, `savollar-yakuniy-tavsiyalar.md` — standart limitlar, offline siyosat qarorlari.
- `spec/tarix/tekshiruv/qabul-6-api-db.md`, `spec/tarix/tekshiruv/qabul-7-ekran-api.md` — 2026-10-15 qabul tekshiruvi (ushbu faylga kiritilgan tuzatishlar manbasi).

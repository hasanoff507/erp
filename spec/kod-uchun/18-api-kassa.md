# API katalogi — 1. Kassa (POS), qaytarish, chegirma, tasdiqlash, qarz daftari

**Maqsad:** POS kassa (smena, chek, qaytarish, chegirma), tasdiqlash navbati va qarz daftari uchun to'liq API kontrakti — voqea (event) payload'lari va REST resurslari.
**Kim uchun:** Backend/frontend/Android ishlab chiquvchilar, QA.
**Bog'liq fayllar:** `17-api-umumiy.md` (konventsiyalar), `11-malumotlar-modeli.md`, `13-provodka-qoidalari.md`, `21-integratsiyalar.md` (§1 OFD, §4 Asl belgisi, §9 Click/Payme/Uzum/UzQR, §9.4 karta terminali va §16.1 agent `/v1/card/*`), `16-offline-sync.md` (§3.1 `/sync/push`, §9), `15-xavfsizlik-va-audit.md`, `23-backend-arxitekturasi.md`, `33-1c-integratsiya.md` §7.3 (`outbox_state` — 1C eksporti tayyorligi), `34-1c-agent.md` (Do'kon agenti — fiskal modul ko'prigi, qaror #60), `03-modullar-talablari.md` (M01, M02, M03, M08, M16), `04-biznes-jarayonlar.md` (BP-03, BP-11, BP-12), `06-ekranlar-umumiy.md` (POS-01…16, BO-06, BO-16).
**Holat:** joriy, 2026-10-16.

## Asosiy xulosalar

1. **Kassada yaratiladigan hujjatlar REST orqali emas** — smena, chek, qaytarish, qarz to'lovi (POS'da), kassa pul harakati, mijozni tezkor yaratish — barchasi `POST /api/v1/sync/push` orqali **voqea (event)** sifatida yuboriladi; `16-offline-sync.md` umumiy konvertni (`client_event_id`, `seq`, `type`) beradi, bu fayl shu voqealarning **to'liq payload sxemasini** belgilaydi.
2. **Voqea turlari**: `shift.opened`, `shift.closed`, `sale.created`, `sale.draft_voided`, `receipt.reprinted`, `return.created`, `debt_payment.created`, `cash_movement.created`, `counterparty.created` (tezkor mijoz yaratish offline uchun, US-M08-05, §11.1), `expense.created` (POS-14 «Xarajat», `source=cash` — §13.2), `transfer.sent`, `transfer.received`, `stock_count.line_recorded` (M04/M05 ombor voqealari — to'liq payload sxemasi `19-api-ombor.md`da, bu fayl faqat ro'yxatda tutadi).
3. **Tasdiqlash ikki yo'l bilan ishlaydi**: (a) Menejer/Egasi kassada **jismonan** bo'lsa — PIN mahalliy (offline ham) tekshiriladi, voqea ichida `approval` obyekti bilan yuboriladi, server postingda qayta tekshiradi; (b) Menejer yo'q bo'lsa — **faqat online**, `POST /api/v1/approval-requests` orqali BO-16 navbatiga tushadi, Menejer PWA'dan tasdiqlaydi/rad etadi, POS natijani so'rab oladi (`approval_request_id`). Ikkisi ham bir xil `ApprovalRef` sxemasiga tushadi (§2.4).
4. **To'lovlar (dinamik UzQR/Click/Payme/Uzum) ikki bosqichli**: avval `POST /api/v1/payments/checkouts` bilan to'lov boshlanadi (hali chek yo'q — `checkout_ref` qurilma beradi), tasdiq kelgandan keyin (poll yoki webhook) `sale.created` voqeasi shu `checkout_ref`/`provider_tx_id` bilan yuboriladi. Bu to'lovlar **faqat online**. **Statik UzQR** — checkout'siz, kassir qo'lda tasdiqlaydi (mustaqil terminaldagi `card` kabi), faqat online. Karta to'lovida `card_type` majburiy, ijtimoiy kartada `card_mask` va `rrn` ham (qaror #64). **Karta — integratsiyalangan terminal** (qaror #71, §16a): kassaga faol `card_terminals` bog'langan bo'lsa POS summani terminalga yuboradi (agent `127.0.0.1:47110/v1/card/*`, Android adapter yoki bulut adapteri orqali), kassir karta raqami/RRN'ni yozmaydi; natija (`card_result`) to'lov qatoriga avtomatik tushadi (`card_entry_mode='integrated'`). Tartib: karta tasdig'i → fiskal chek → `sale.created`; chek chiqmasa sotuv "to'lov qabul qilingan, chek kutilmoqda" holatida qoladi, kassir uni bekor qilsa — avtomatik `void` (boshqa avtomatik `void` faqat `CARD_AMOUNT_MISMATCH`da). Terminal ishlamasa — qo'lda kiritish (`card_entry_mode='manual'`) `tenants.settings.card_manual_fallback` siyosati bo'yicha (`allow`/`manager_approval`/`forbid`). Fiskal chekni har doim bizning kassamiz chiqaradi — provayder tomonidagi avto-fiskalizatsiya o'chiq bo'lishi shart (§16).
5. **Markirovka**: kod Asl belgisi'ga **fiskal chek ichida** OFD orqali boradi (`items[].marking_codes`), sotuv uchun CRPT API chaqirilmaydi (qaror #62). Sotuvdan oldingi tekshiruv (`POST /api/v1/marking-codes/verify`) — `MARKING_PRECHECK=off|warn|block`, standart `warn`: tekshiruv o'tmasa yoki CRPT javob bermasa sotuv davom etadi, `warnings[]`da `MARKING_PRECHECK_WARNING` (§4.2, §15). Lokal takror-kod tekshiruvi har doim ishlaydi.
6. **Fiskal bloklar**: shu kassada OFD tasdig'ini olmagan eng eski chek ≥ 48 soat bo'lsa yangi fiskal chek (sotuv, qaytarish, qarz to'lovi) rad etiladi — `FISCAL_OFFLINE_48H_BLOCKED` (qaror #43); fiskal modul holati `fm_state ≠ ok` bo'lsa — `FISCAL_DEVICE_LOCKED` (§4.10).
7. **Qarz daftari** — ikki kiritish yo'li: POS'dan (`debt_payment.created` voqeasi, offline ham; `cash`/`card`/`uzqr`/`click`/`payme`/`uzum` — har doim kassa, smena va fiskal chek bilan) va back-office'dan (`POST /api/v1/debt-payments`, online, faqat `method='bank'` — kassasiz, chek yo'q; qaror #67). Ikkisi ham bitta `DebtPaymentPostingService`ga tushadi. Qarzni kechish/shubhali belgisi — faqat Egasi, faqat back-office REST (offline'da yo'q).
8. Xato kodlari — to'liq ro'yxat §18da, `17-api-umumiy.md` xato katalogi bilan moslashtirilgan.
9. Pul — `"12000.00"` (NUMERIC(18,2) string), miqdor — `"2.000"` (NUMERIC(18,3) string), sana — ISO 8601 (`doc_date`: `"2026-10-14"`, `created_at`: `"2026-10-14T09:12:03.482Z"`, UTC, `Z` qo'shimchasi bilan). Hujjat/registr ro'yxatlari — cursor pagination `?cursor=&limit=` → `{items, next_cursor}`; ma'lumotnoma ro'yxatlari (`counterparties`, `discount-rules`) — **page** pagination `?page=&size=` → `{items, total, page, size}`.

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
| Xato konverti | `{"error": {"code": "...", "message_key": "errors....", "params": {...}, "details": [...], "request_id": "..."}}` — `details` har doim massiv |
| Optimistik qulflash | ma'lumotnoma resurslarida (`counterparties`, `discount-rules`) `version` tanada; mos kelmasa `409 VERSION_CONFLICT` |
| Hujjat REST naqshi (back-office'da yaratiladigan hujjatlar: `price-changes`, `debt-payments`, `debt-openings`, `debt-writeoffs`) | `POST /{resurs}` (draft) → `POST /{resurs}/{id}/post` → `POST /{resurs}/{id}/cancel` |
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
| 16 | `POST /api/v1/price-changes/{id}/post` → `approval-requests` bog'lanishi | Narx o'zgarishi tasdiqlash oqimi (to'liq ta'rif — `19-api-ombor.md` §4) | 10 |
| 17 | `POST /api/v1/counterparties` / `GET` / `GET /{id}` / `PATCH /{id}` | Kontragent (mijoz/yetkazib beruvchi) tezkor yaratish/qidiruv/tahrir | 11.2–11.4 |
| 18 | event `counterparty.created` | Mijozni offline tezkor yaratish | 11.1 |
| 19 | `GET /api/v1/counterparties/{id}/debt-ledger` | Qarz daftari ko'rinishi (BO-06/POS-13) | 12.1 |
| 20 | `POST /api/v1/counterparties/{id}/statement-link` | Telegram uchun qarz hisob-varag'i havolasi | 12.7 |
| 21 | event `debt_payment.created` | Qarz to'lovi (POS, offline ham) | 12.2 |
| 22 | `POST /api/v1/debt-payments` → `POST /{id}/post` | Qarz to'lovi (back-office, faqat `method='bank'`) | 12.3 |
| 23 | `POST /api/v1/debt-openings` → `POST /{id}/post` | Boshlang'ich qarz | 12.4 |
| 24 | `POST /api/v1/debt-writeoffs` → `POST /{id}/post` | Qarzni kechish (faqat Egasi) | 12.5 |
| 25 | `GET /api/v1/debt-payments` / `GET /{id}` / `POST /{id}/cancel` | Qarz to'lovlari ro'yxati, bekor qilish | 12.5a |
| 26 | `GET /api/v1/debt-openings` / `GET /{id}` / `POST /{id}/cancel` | Boshlang'ich qarzlar ro'yxati, bekor qilish | 12.5a |
| 27 | `GET /api/v1/debt-writeoffs` / `GET /{id}` / `POST /{id}/cancel` | Kechilgan qarzlar ro'yxati, bekor qilish | 12.5a |
| 28 | `POST /api/v1/debt-doubtful-flags` / `POST /{id}/unflag` | Shubhali qarz belgisi (faqat Egasi) | 12.6 |
| 29 | `GET /api/v1/reports/debts-aging?direction=receivable` | Qarz eskirish hisoboti (yagona manba — `20-api-moliya-admin.md` #21) | 12.8 |
| 30 | event `cash_movement.created` | Kassaga pul qo'yish/olish (inkassatsiya, ta'sischi, boshqa) | 13.1 |
| 31 | event `expense.created` | Kassadan naqd xarajat (POS-14 «Xarajat», `source=cash`) | 13.2 |
| 32 | `GET /api/v1/cash-movements` | Kassa pul harakati ro'yxati | 13.3 |
| 33 | `GET /api/v1/fiscal-receipts` / `GET /{id}` | Fiskal chek holati, qayta chop etish uchun qidiruv | 14.1 |
| 34 | `POST /api/v1/fiscal-receipts/{id}/retry` | Qo'lda qayta urinish (BO-14) | 14.2 |
| 35 | `GET /api/v1/einvoices?direction=out` / `POST /einvoices` / `POST /einvoices/from-receipt` / sign / `send` / `cancel` | Chiquvchi e-faktura (B2B) | 14a |
| 36 | `POST /api/v1/marking-codes/verify` | Markirovka kodini tekshirish (sinxron) | 15 |
| 37 | `POST /api/v1/payments/checkouts` | To'lov boshlash (dinamik uzqr/click/payme/uzum; statik UzQR checkout'siz) | 16.2 |
| 38 | `GET /api/v1/payments/checkouts/{checkout_ref}` | To'lov holati | 16.3 |
| 39 | `POST /api/v1/payments/webhooks/{provider}` | Bank/to'lov tizimi tasdig'i (kiruvchi) | 16.4 |
| 40 | `POST /api/v1/sync/push` / `GET /api/v1/sync/pull` | POS bootstrap/sinxron (to'liq — `16-offline-sync.md`; push so'rovi — §2.6) | 17, 2.6 |
| 41 | `GET /api/v1/sales` / `GET /api/v1/sales/{id}` | Chek qidiruvi (back-office/POS-05) | 4.8 |
| 42 | `POST /api/v1/card-terminal-transactions` | Karta terminali urinishini yozish (natija bilan — lokal adapterlar) yoki boshlash (natijasiz — bulut adapteri); `id = attempt_id` bo'yicha upsert | 16a.3 |
| 43 | `GET /api/v1/card-terminal-transactions/{id}` | Urinish holati (bulut adapteri poll, `unknown`ni tiklash) | 16a.4 |
| 44 | `GET /api/v1/card-terminals` / `POST /api/v1/card-terminals` | Karta terminallari ro'yxati / ro'yxatga olish (BO-12, POS-16) | 16a.5 |
| 45 | `PATCH /api/v1/card-terminals/{id}` | Terminalni tahrirlash, o'chirish/arxivlash, standart qilish | 16a.5 |
| 46 | `POST /api/v1/card-terminal-settlements` | Terminal settlement natijasi (smena yopilishi) | 16a.6 |
| — | Agent lokal API `GET/POST http://127.0.0.1:47110/v1/card/*` | POS ↔ Do'kon agenti (server endpoint emas; sxemalar — `21-integratsiyalar.md` §16.1) | 16a.2 |

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
| `error_code` | string\|null | §18 ro'yxatidan |
| `message` | string\|null | Inson o'qiydigan xabar (frontend `message_key`ga map qiladi) |
| `retryable` | boolean | `true` — qurilma qayta yuboradi; `false` — qo'lda tuzatish/eskalatsiya |
| `warnings` | string[] | Katalog kodlari (masalan `STOCK_NEGATIVE`, `DEBT_LIMIT_EXCEEDED`) — amal qabul qilindi, lekin ogohlantirish bilan |

### 2.3 `Money` / `Qty`

`Money` — `"12000.00"` shaklidagi string (NUMERIC(18,2)). `Qty` — `"2.000"` (NUMERIC(18,3)); `units.is_fractional=false` birlikda faqat butun qiymat (`"2.000"`, kasr qismi `000`) qabul qilinadi, aks holda `422 VALIDATION_ERROR`.

### 2.4 `ApprovalRef` (chegirma/qaytarish/qarz/pul olish limitidan oshganda umumiy obyekt)

| Maydon | Tur | Majburiy | Izoh |
|---|---|---|---|
| `mode` | enum | shartli | `local_pin` (Menejer jismonan, PIN mahalliy tekshirilgan) / `remote_request` (BO-16 orqali, online) / `none` (limit ichida — obyekt umuman yuborilmaydi) |
| `approved_by` | UUID | `local_pin`da ha | PIN kiritgan Menejer/Egasi (`doc_approvals.approved_by`) |
| `pin_verified_locally` | boolean | `local_pin`da ha | Qurilma lokal tekshirdi (server postingda qayta tekshiradi: `approved_by`ning shu limit uchun yetarli huquqi bormi) |
| `approval_request_id` | UUID | `remote_request`da ha | §9dagi resurs, `status=approved` bo'lishi shart |

Server validatsiyasi (ikkala holatda ham): `approved_by` (yoki `approval_request_id.resolved_by`) ning `role_permissions.limit_value`i so'ralgan summa/foizni qoplashi kerak, aks holda posting rad etiladi (`APPROVAL_INVALID` yoki tegishli `*_LIMIT_EXCEEDED`, §18). `approval_request_id` faqat `status=approved` va hali `consumed` bo'lmagan bo'lsa qabul qilinadi; postingda `approval_requests.status` `consumed`ga o'tadi va `doc_approvals` qatori (`mode`, `approved_by`, `pin_verified_locally`, `approval_request_id`) yoziladi — bitta so'rov bitta hujjatda **faqat bir marta** ishlatiladi; allaqachon `consumed` (yoki `rejected`/`expired`) so'rov qayta kelsa — `409 APPROVAL_REQUEST_ALREADY_RESOLVED`. `APPROVAL_INVALID` — faqat tasdiqlovchining huquqi/limiti yetmasa yoki kutilgan `ApprovalRef` kelmasa; §9.4'dagi noto'g'ri PIN — `PIN_INVALID`.

### 2.5 `ErrorEnvelope`

```json
{"error": {"code": "DEBT_LIMIT_EXCEEDED", "message_key": "errors.debt_limit_exceeded", "params": {"limit": "500000.00", "requested": "569000.00"}, "details": [], "request_id": "01933..."}}
```

`details` har doim massiv, `params` — ixtiyoriy biznes kontekst obyekti (`17-api-umumiy.md` §7.1).

### 2.6 `SyncPushRequest` (`POST /api/v1/sync/push` so'rov tanasi)

| Maydon | Tur | Majburiy | Izoh |
|---|---|---|---|
| `device_id` | UUIDv7 | ha | `devices` yozuviga mos (token `device_id` bilan bir xil bo'lishi shart) |
| `events` | `SyncEventEnvelope[]` (§2.1) | ha | `seq` tartibida, partiya ≤ 100 voqea (standart, sozlanadi — qaror #54); bo'sh massiv ruxsat — davriy holat hisoboti |
| `outbox_state` | object | ha | Shu so'rovga kiritilmagan outbox qismi: `{pending_count: integer ≥ 0, oldest_pending_created_at: timestamptz\|null}` (`pending_count = 0` da `null`); yo'q yoki noto'g'ri bo'lsa `422 VALIDATION_ERROR` |

Javob — `{results: PushResultEntry[]}` (§2.2). `outbox_state` asosida server `devices.outbox_pending_count`/`outbox_oldest_pending_at`/`outbox_reported_at` va `last_sync_at` ni bitta tranzaksiyada yangilaydi (rad etilgan voqealar ham hisobga qo'shiladi) — to'liq qoida va 1C eksporti tayyorligidagi o'rni `16-offline-sync.md` §3.1, §9; `33-1c-integratsiya.md` §7.3.

### 2.7 `CardResult` (karta terminali natijasi, qaror #71)

Integratsiyalangan karta to'lovi/qaytarishida terminal natijasi — `sale.created.payments[].card_result`, `debt_payment.created.card_result`, `return.created.refund_card.card_result` va `POST /card-terminal-transactions` tanasidagi `result`. Adapter `CardTxResult`idan (`21-integratsiyalar.md` §9.4; summalar tiyinda) quriladi — bu yerda pul `Money` satri.

| Maydon | Tur | Majburiy | Izoh |
|---|---|---|---|
| `attempt_id` | UUIDv7 | ha | Qurilma terminalga yuborishdan **oldin** beradi — idempotentlik kaliti, `card_terminal_transactions.id` |
| `card_terminal_id` | UUID | ha | `card_terminals.id` (faol, shu filial) |
| `kind` | enum | ha | `purchase` / `refund` / `void` |
| `original_attempt_id` | UUID\|null | shartli | `void`da majburiy; `refund`da asl xarid ma'lum bo'lsa |
| `status` | enum | ha | `approved` / `declined` / `unknown` / `voided` (`CardTxResult` xaritasi: `cancelled`/`error` → `declined`, `timeout` → `unknown`); to'lov qatoriga faqat `approved` bog'lanadi |
| `amount` | Money | ha | Terminal tasdiqlagan summa; to'lov qatoridagi `amount` bilan **aynan** teng bo'lishi shart (aks holda POS avtomatik `void` qilgan bo'ladi — `CARD_AMOUNT_MISMATCH`) |
| `approval_code` | string\|null | yo'q | Avtorizatsiya kodi (`^[0-9A-Za-z]{1,12}$`) |
| `rrn` | string | `approved`da ha | Tranzaksiya unikal raqami (`^[0-9A-Za-z]{6,32}$`) |
| `stan` | string\|null | yo'q | — |
| `card_mask` | string | `approved`da ha | `^[0-9]{4}\*+[0-9]{4}$` — adapter normallashtiradi (BIN saqlanmaydi) |
| `card_scheme` | enum\|null | yo'q | `uzcard`/`humo`/`visa`/`mastercard`/`unionpay`/`mir`/`other` |
| `card_type` | enum\|null | yo'q | `personal`/`corporate`/`social`/`unknown` — terminal bergan yoki `card_bin_rules`dan; to'lov qatoridagi `card_type` yakuniy (kassir bitta bosishda tanlagan bo'lishi mumkin) |
| `card_type_source` | enum\|null | shartli | `card_type` bo'lsa: `terminal` / `bin_table` / `cashier` |
| `entry_mode` | enum\|null | yo'q | `chip`/`contactless`/`magstripe`/`fallback` |
| `tid`, `mid`, `acquirer` | string\|null | yo'q | Terminal/merchant ID, ekvayer kodi |
| `tx_at` | ISO vaqt\|null | yo'q | Terminal vaqti |
| `resolved_by` | enum | ha | `auto` (terminal javobi) / `status_query` (`get_status`/`get_last_transaction`) / `manager` (`unknown` terminal chekiga qarab yopildi — to'lov qatorida / `POST /card-terminal-transactions` tanasida `card_manual_approval: ApprovalRef` majburiy: tasdiq turi `card_manual_entry`, tasdiqlovchida `card.manual_entry.approve`) |
| `decline_code`, `decline_message` | string\|null | yo'q | `declined`da |
| `slip_text` | string\|null | yo'q | Terminal cheki matni (ixtiyoriy) |

`PAN`, track, CVV, PIN-blok, EMV kriptogramma — hech qachon (`15-xavfsizlik-va-audit.md` §9.3).

---

## 3. Smena (shift)

### 3.1 Voqea: `shift.opened`

**Maqsad**: ish kunini boshlash, boshlang'ich naqdni qayd etish.
**Ruxsat**: `shift.open`.

**So'rov** (payload):

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | Qurilma beradi — `shifts.id` |
| `cash_register_id` | UUID | ha | `cash_registers`, shu filialga tegishli |
| `shift_no` | integer | ha | Qurilma beradi, shu kassa ichida ketma-ket (> 0) — OFD smena raqami |
| `opening_cash` | Money | ha | ≥ `"0.00"` |
| `comment` | string | yo'q | — |

**Javob** (`server`): `{id, cash_register_id, shift_no}`.
**Xatolar**: `SHIFT_ALREADY_OPEN` (shu `cash_register_id`da yopilmagan smena bor), `VALIDATION_ERROR`.
**Idempotentlik**: `client_event_id`.
**Offline**: to'liq ishlaydi — smena ochilishi internet talab qilmaydi (`16-offline-sync.md` §1, `shift` jadvali). Invariant: bitta smena — bitta qurilma (`shifts.device_id = device_id`, keyingi voqealar boshqa qurilmadan kelsa `SHIFT_DEVICE_MISMATCH`).
**Bog'liq**: US-M01-04, POS-01.

### 3.2 Voqea: `shift.closed`

**Maqsad**: ish kunini yakunlash, naqd sanash, Z-hisobot generatsiyasi va OFD'ga yuborish (`outbox_jobs(kind=ofd_send)`).
**Ruxsat**: `shift.close` + (naqd sanash) `cash.count.shift`.

**So'rov** (payload):

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `shift_id` | UUID | ha | `shifts.id`, `status=open`, shu `device_id`ga tegishli |
| `counted_cash` | Money | ha | Kassir sanagan naqd |
| `counted_card_total` | Money | yo'q | Qo'lda kiritilgan karta to'lovlari (`card_entry_mode='manual'`) jami — mustaqil terminal cheklari bo'yicha; qurilma hisoblab yuboradi, server qayta tekshiradi |
| `card_settlements[]` | array | yo'q | Smena yopilishida bajarilgan terminal settlement'lari (qaror #71) — har biri §16a.6 tanasi (`id`, `card_terminal_id`, `batch_no`, `settled_at`, `purchase_count`, `purchase_total`, `refund_count`, `refund_total`, `status`); offline'da shu voqea bilan, online'da §16a.6 bilan ham yuborilishi mumkin (`id` bo'yicha idempotent). Hal qilinmagan (`pending`/`unknown`) karta urinishi bo'lsa smena yopilmaydi — `CARD_OUTCOME_UNKNOWN` |
| `variance_note` | string | shartli | `expected_cash ≠ counted_cash` bo'lsa majburiy |

Server hisoblaydi: `expected_cash = opening_cash + Σcash_moves(shift_id)` (`cash_moves` (`shift_id`, `method='cash'`), US-M16-02 formulasi). `variance = counted_cash − expected_cash`.

**Javob** (`server`): `{id, shift_no, z_report: {expected_cash, counted_cash, variance, totals_by_method: {cash, card, uzqr, click, payme, uzum, debt}, card_split: {integrated, manual}, card_settlements: [{card_terminal_id, net_total, expected_total, variance, status}], vat_total, discount_total, returns_total, sales_count, returns_count}, fiscal: {status: "pending"}}` — `card_split` — karta tushumi kiritish usuli bo'yicha (Z-hisobot, BO-24; qaror #71), `card_settlements[].status='mismatch'` — ogohlantirish (`card.settlement.mismatch`), smena yopilishini bloklamaydi.
**Xatolar**: `SHIFT_NOT_OPEN`, `SHIFT_DEVICE_MISMATCH`, `CARD_OUTCOME_UNKNOWN` (shu smenada hal qilinmagan karta urinishi — qurilma avval holat so'rovi yoki menejer yopishini bajaradi), `VALIDATION_ERROR` (`variance_note` yo'q — `details[].message_key="validation.variance_note_required"`).
**Idempotentlik**: `client_event_id`.
**Offline**: to'liq ishlaydi; Z-hisobot `fiscal_receipts.status=pending` bilan OFD'ga navbatga qo'yiladi (internet qaytganda, `21-integratsiyalar.md` §1).
**Bog'liq**: US-M01-04, US-M16-02, POS-07, POS-15.

### 3.3 Back-office — smena ko'rish

#### `GET /api/v1/shifts`

**Maqsad**: smenalar ro'yxati.
**Ruxsat**: `reports.sales.view` yoki `cash.count.shift`.
**So'rov**: `?cash_register_id=&status=&cursor=&limit=`.
**Javob**: `{items:[{id, shift_no, cash_register_id, status, opening_cash, opened_at, closed_at}], next_cursor}`.
**Xatolar**: —. **Idempotentlik**: shart emas. **Offline**: faqat kesh.
**Bog'liq**: US-M01-04, POS-07, POS-15.

#### `GET /api/v1/shifts/{id}`

**Maqsad**: smena tafsiloti — yopilgan bo'lsa `z_report` bilan birga; `status=open`da qo'shimcha `running_totals: {totals_by_method: {cash, card, uzqr, click, payme, uzum, debt}, sales_count, voided_count, returns_total, cash_in, cash_out, expected_cash}` (POS-07/POS-15 online solishtirish manbai; offline — lokal hisob).
**Ruxsat**: `reports.sales.view` yoki `cash.count.shift`.
**Xatolar**: `NOT_FOUND`.
**Bog'liq**: US-M16-02, POS-07, POS-15.

#### `GET /api/v1/shifts/{id}/z-report`

**Maqsad**: §3.2'dagi `z_report` obyekti + `fiscal.status`.
**Ruxsat**: `reports.sales.view` yoki `cash.count.shift`.
**Bog'liq**: US-M16-03, POS-07.

---

## 4. Sotuv — voqea `sale.created`

**Maqsad**: chekni yakunlash — qoldiq, qarz, kassa, QQS, buxgalteriya bitta `SalePostingService.post()` tranzaksiyasida (`23-backend-arxitekturasi.md` §2).
**Ruxsat**: `sales.create`.
**Davlat tizimi**: OFD, MXIK, (markirovka bo'lsa) Asl belgisi, (UzQR bo'lsa) bank.

### 4.1 Payload

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | Qurilma beradi — `sales.id` |
| `branch_id`, `cash_register_id`, `shift_id` | UUID | ha | `shift_id` — `status=open`, shu `device_id` |
| `receipt_seq` | integer\|null | shartli | **Qurilma beradi**, shu smena ichida ketma-ket (`kind='sale'` cheki raqami); faqat-qarz sotuvda (`payments[]` faqat `debt` — `sale` cheki chiqmaydi) `null`, aks holda majburiy. Server `UNIQUE (tenant_id, cash_register_id, shift_id, receipt_seq)` tekshiradi, o'zi raqam bermaydi (istisno — §4.6 `RECEIPT_SEQ_CONFLICT` qayta raqamlash) |
| `credit_receipt_seq` | integer\|null | shartli | `FiscalPolicy.credit_sale_receipt='credit_type'` va `payments[]`da `debt` bo'lsa majburiy — `kind='credit_sale'` cheki raqami (shu smenadagi `receipt_seq` ketma-ketligidan); aks holda `null` |
| `fiscal_result` | object\|null | shartli | Lokal ko'prik rejimida (`FISCAL_PROVIDER = multikassa_local \| fiscaldrive_local`) chek FM'da imzolangan bo'lsa **majburiy**: `{fm_terminal_id, fm_receipt_seq, fiscal_sign, qr_url, fiscal_at}`; hamkor bulut va `fake` rejimida, faqat-qarz sotuvda — `null` (qaror #68) |
| `delivery` | enum | yo'q | `printed` / `electronic`, standart `printed` → `fiscal_receipts.delivery` |
| `delivery_reason` | enum\|null | shartli | `printer_failure` / `customer_request`; `delivery=electronic` bo'lsa majburiy, aks holda `null` |
| `temp_number` | string | ha | `{device_id}-{local_seq}` (`11-malumotlar-modeli.md` §6/§11) |
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
| `id` | UUIDv7 | ha | Qurilma beradi — `sale_lines.id` |
| `product_id` | UUID | ha | Katalogda mavjud (lokal keshda) |
| `unit_code` | string | ha | `units.code`; hosila — faqat validatsiya (`products.unit_code`ga teng bo'lishi shart), `sale_lines`da saqlanmaydi |
| `qty` | Qty | ha | `is_fractional=false` bo'lsa butun |
| `price` | Money (4 xona) | ha | QQS bilan, 4 xonali o'nlik satr — narx tarixidagi joriy narx ("qotirilgan") |
| `vat_rate` | decimal (2 xona) | ha | `"12.00"`/`"0.00"` |
| `vat_exemption_code` | string\|null | shartli | QQS imtiyoz kodi; `vat_rate`/`vat_exemption_code`dan kamida biri to'ldirilgan bo'lishi shart |
| `discount_pct` | decimal\|null | yo'q | Faqat ma'lumot (ekranda ko'rsatish); hisob va limit tekshiruvi `discount_amount` dan (§4.4) |
| `discount_amount` | Money\|null | shartli | Hisob-kitob manbai; `discount_source` berilsa `discount_amount > 0` majburiy |
| `discount_source` | enum\|null | shartli | `discount_amount > 0` bo'lsa majburiy va aksincha: `manual` / `standing_customer` / `rule` |
| `discount_rule_id` | UUID\|null | shartli | `discount_source=rule`da majburiy |
| `discount_approval` | `ApprovalRef`\|null | shartli | `discount_source=manual` va foiz standart limitdan (odatda 5%) oshsa majburiy (§9) |
| `marking_code` | string\|null | shartli | Tovar `is_marked=true` bo'lsa majburiy — DataMatrix xom qiymati, GS (`\u001d`) ajratgichlari bilan **aynan** (fiskal chekka shu ko'rinishda ketadi); qty har doim `"1.000"` bo'lishi shart (har kod alohida qator) |
| `marking_offline` | boolean | yo'q | Ma'lumot uchun (`true` — offline sotilgan, sotuvdan oldingi tekshiruv (§15) qilinmagan); saqlanmaydi — `sales.is_offline` dan hisoblanadi; kod baribir fiskal chek bilan OFD'ga ketadi (§4.2) |
| `line_total` | Money | ha | Qator jami (chegirmadan keyin, QQS bilan) — `sale_lines.line_total` |
| `vat_amount` | Money | ha | Qator QQS summasi — `sale_lines.vat_amount` |

`line_no` — qurilma yubormaydi, server massiv indeksi+1 sifatida belgilaydi. `line_total`, `vat_amount` — qurilma qaror #26 formulasi bilan hisoblaydi (`vat_amount = ROUND_HALF_UP(line_total × r / (100 + r), 2)`), server qayta hisoblab tekshiradi (mos kelmasa `VALIDATION_ERROR`). `cost_amount` — qurilma yubormaydi, faqat server hisoblaydi (FIFO/AVECO).

**`payments[]`** (→ `sale_payments`):

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `method` | enum | ha | `cash` / `card` / `uzqr` / `click` / `payme` / `uzum` / `debt` |
| `amount` | Money | ha | > `"0.00"` |
| `card_entry_mode` | enum\|null | shartli | `method=card` bo'lsa majburiy: `integrated` — terminal natijasi avtomatik (`card_result` majburiy); `manual` — kassir terminal chekidan kiritadi (qaror #64 zaxirasi); boshqa usullarda `null` (qaror #71) |
| `card_result` | `CardResult`\|null | shartli | `card_entry_mode=integrated` bo'lsa majburiy (§2.7), `status=approved`, `kind=purchase`, `amount` = shu qator `amount`; server `card_terminal_transactions`ni `attempt_id` bo'yicha upsert qilib, `sale_payments.card_terminal_transaction_id`, `rrn`, `card_mask`, `approval_code`, `card_scheme`ni shundan oladi (qurilma ularni alohida yubormaydi). Boshqa holatda `null` |
| `terminal_ref` | string\|null | yo'q | `method=card` + `manual` — mustaqil terminal operatsiya raqami (online/offline ikkisida ham); `integrated`da server `card_result.tid` bilan to'ldiradi; `method=uzqr` + `qr_type=static` — ixtiyoriy to'lov raqami (kassir mijoz telefonidan kiritadi) |
| `card_type` | enum\|null | shartli | `personal` / `corporate` / `social` / `unknown`; `method=card` bo'lsa majburiy, boshqa usullarda `null` — chekdagi majburiy "karta turi" rekviziti (qaror #64). `integrated`: `card_result.card_type` (terminal yoki `card_bin_rules`) bo'lsa shu qiymat, bo'lmasa kassir bitta bosishda tanlaydi; `manual`: standart qiymat yo'q — kassir har karta to'lovida terminal chekiga qarab tanlaydi; `unknown` chekda "Noma'lum / Не определён" |
| `card_type_source` | enum\|null | shartli | `method=card`da majburiy: `terminal` / `bin_table` / `cashier`; `manual`da doim `cashier` |
| `card_mask` | string\|null | shartli | `manual`: karta niqobi — birinchi va oxirgi 4 raqam, terminal chekidan; format `^[0-9]{4}\*+[0-9]{4}$` (masalan `8600****1234`); `card_type=social` bo'lsa majburiy, boshqa holatda ixtiyoriy. `integrated`: yuborilmaydi (`card_result`dan) |
| `rrn` | string\|null | shartli | `manual`: tranzaksiyaning unikal raqami (RRN, terminal chekidan); `card_type=social` bo'lsa majburiy, boshqa holatda ixtiyoriy. `integrated`: yuborilmaydi (`card_result`dan) |
| `approval_code`, `card_scheme` | string\|null, enum\|null | yo'q | Faqat `manual`da ixtiyoriy (terminal chekidan); `integrated`da `card_result`dan |
| `manual_reason` | enum\|null | shartli | `card_entry_mode=manual`da majburiy: `terminal_offline` / `terminal_error` / `unknown_result` / `standalone_terminal` (kassada faol terminal yo'q); `integrated`da `null` |
| `card_manual_approval` | `ApprovalRef`\|null | shartli | `card_entry_mode=manual` va `card_manual_fallback=manager_approval` (sozlama yo'q bo'lsa — faol terminali bor kassada standart) bo'lsa majburiy — tasdiq turi `card_manual_entry`, tasdiqlovchida `card.manual_entry.approve`; `card_result.resolved_by=manager` (`unknown` qo'lda yopilgan) bo'lsa ham majburiy |
| `qr_type` | enum\|null | shartli | `static`/`dynamic`; `method=uzqr` bo'lsa majburiy, boshqa usullarda `null` |
| `checkout_ref` | UUID\|null | shartli | `click`/`payme`/`uzum` va `uzqr`+`qr_type=dynamic`da majburiy — §16dagi `payment_checkouts.checkout_ref`; `uzqr`+`qr_type=static`da `null` (checkout yaratilmaydi) |
| `provider_tx_id` | string\|null | shartli | `click`/`payme`/`uzum` va `uzqr`+`qr_type=dynamic`da majburiy — §16dagi checkout natijasidan; **istisno**: `uzqr`+`qr_type=static` — ixtiyoriy (qo'lda tasdiq, ixtiyoriy to'lov raqami `terminal_ref`da) — `sale_payments` CHECK shu qoida bilan (`12-db-sxema.md`) |
| `due_date` | ISO sana\|null | yo'q | Faqat `method=debt` — "va'da sanasi" (bitta, bo'lib to'lash grafigi yo'q); `debt_moves.due_date`/`counterparties.debt_due_date` manbasi |
| `debt_approval` | `ApprovalRef`\|null | shartli | `method=debt` va joriy qarz+summa kredit limitidan oshsa (online rejimda majburiy; offline'da — §4.3) |

Mos kelmagan shart (masalan `method=card` va `card_type`/`card_entry_mode` yo'q, `card_type=social` va `card_mask`/`rrn` yo'q, `uzqr` va `qr_type` yo'q) — `VALIDATION_ERROR` (ijtimoiy karta rekvizitlari yo'q bo'lsa `details[].message_key="validation.social_card_details_required"`; kiritish usuli yo'q — `validation.card_entry_mode_required`; `integrated`da `card_result` yo'q yoki `approved` emas — `validation.card_result_required`; `manual`da sabab yo'q — `validation.card_manual_reason_required`). Karta qoidalari (qaror #71): `manual` va `card_manual_fallback=forbid` (kassaga faol integratsiyalangan terminal bog'langan bo'lsa; terminalsiz kassada `standalone_terminal` har doim ruxsat) — `CARD_MANUAL_NOT_ALLOWED` (online `rejected`; offline voqea rad etilmaydi — POS bu yo'lni o'zi yopgan, kelib qolsa `sync_exceptions(kind='approval_limit_exceeded_offline')`); `manager_approval` va `card_manual_approval` yo'q — online `CARD_MANUAL_APPROVAL_REQUIRED`, offline xuddi shu `sync_exceptions` bilan qabul; `card_result` serverdagi qator bilan mos emas (summa, takroriy `tid`+`rrn`, `attempt_id` boshqa hujjatga bog'langan) — voqea qabul qilinadi, `warnings=["CARD_TRANSACTION_MISMATCH"]`, `sync_exceptions(kind='card_result_mismatch')`. Aralash to'lovda har karta urinishi — alohida `payments[]` qatori, alohida `attempt_id`. `is_offline=true` va `method='uzqr'` (statik ham) — `VALIDATION_ERROR` (`message_key=validation.uzqr_online_only`).

### 4.2 Markirovka qatori qoidalari (qaror #62)

- **Kod qayerga ketadi**: chakana sotuvda markirovka kodi Asl belgisi'ga **fiskal chek ichida** OFD orqali uzatiladi — `FiscalPort` chek payload'ida `items[].marking_codes[]` (GS ajratgichlari bilan aynan, `marking_code` qiymatining o'zi). Sotuv uchun CRPT API chaqirilmaydi, `marking_sell` outbox ishi yo'q; server `marking_codes(status='pending_verification')` yozadi, chek OFD tasdig'ini (`fiscal_receipts.ofd_acked_at`) olgach `status='sold'` (`16-offline-sync.md` §7). CRPT API (`MarkingPort`) faqat qabul, tekshiruv, qaytarish va hisobdan chiqarish uchun.
- **Sotuvdan oldingi tekshiruv** — `MARKING_PRECHECK` tenant sozlamasi (`off` / `warn` / `block`, standart `warn`):
  - `off` — POS `POST /api/v1/marking-codes/verify`ni chaqirmaydi;
  - `warn` — online sotuvda POS §15ni chaqiradi; kod tekshiruvdan o'tmasa yoki CRPT javob bermasa (timeout) §15 javobida `200` + `warnings=["MARKING_PRECHECK_WARNING"]`, `audit_log` yozuvi, sotuv **davom etadi** (`sale.created` bu sabab bilan rad etilmaydi);
  - `block` — §15 tekshiruvdan o'tmagan kod `MARKING_VERIFY_FAILED`, CRPT javob bermasa `MARKING_VERIFY_UNAVAILABLE` qaytaradi; POS bunday kodli qatorni chekka qo'shmaydi; offline/zaxira yo'l yo'q (qaror #62). `sale.created` CRPT'ni qayta chaqirmaydi.
- **Lokal takror-kod tekshiruvi** (rejimdan qat'i nazar, offline'da ham): bitta chekda bir xil kod ikki marta — `VALIDATION_ERROR`; tenantda allaqachon sotilgan kod (qurilmadagi lokal outbox va sinxronlangan `marking_codes` keshi, serverda `marking_codes.status IN ('sold','pending_verification')`) — `MARKING_CODE_ALREADY_SOLD`. Format xatosi (DataMatrix o'qilmadi) — `MARKING_CODE_INVALID`.
- `marking_offline=true` — offline sotuv, oldindan tekshiruv qilinmagan; narx qurilmada noma'lum bo'lsa sotuv taqiq (`MARKING_PRICE_UNKNOWN_OFFLINE`, `16-offline-sync.md` §7).

### 4.3 Qarz (debt) va offline limit

- Online: `counterparty.credit_limit` tekshiriladi; oshsa `debt_approval` (`ApprovalRef`) talab qilinadi, bo'lmasa `DEBT_LIMIT_EXCEEDED`.
- **Offline**: limit tekshiruvi qurilmadagi oxirgi sinxronlangan `receivable_balance`/`credit_limit` asosida; oshib ketsa ham sotuv **bloklanmaydi** — server qabul qiladi, `sales.debt_limit_exceeded=true` bayrog'i qo'yadi (xato emas, `status=accepted`, `warnings=["DEBT_LIMIT_EXCEEDED"]`), M18 orqali Egasiga xabar.

### 4.4 Chegirma va standart "bitta eng foydali qoida"

Server chegirma summasini **qayta hisoblamaydi** (narx kabi "qotirilgan", manba — `discount_amount`) — faqat: (1) `discount_source` bitta bo'lishini (stacking yo'q), (2) `discount_source=manual`da foiz `role_permissions.discount.give.limit_value`dan oshmasligini (yoki `discount_approval` borligini) tekshiradi. Mos kelmasa `DISCOUNT_LIMIT_EXCEEDED`.

- Qator foizini server o'zi hisoblaydi: `pct_i = discount_amount_i / ROUND_HALF_UP(qty × price, 0) × 100` (`discount_pct` — faqat ma'lumot).
- Chek darajasidagi chegirma qatorlarga `line_gross = ROUND_HALF_UP(qty × price, 0)` ulushida taqsimlanadi, yaxlitlash qoldig'i eng katta qatorga; har qatorda `discount_source='manual'`.
- Limit tekshiruvi: `Σ discount_manual / Σ line_gross × 100`.

### 4.5 Server javobi va fiskal holat

`server`: `{id, number, fiscal_receipt_seq, fiscal: {status: "pending"|"fiscalized"|"deferred"}, warnings: []}` — `fiscal_receipt_seq` qurilma yuborgan `receipt_seq`ning aks-sadosi (server o'zi raqam bermaydi; §4.6 qayta raqamlashda — yangi qiymat). `fiscalized` — voqea `fiscal_result` bilan kelgan (lokal ko'prik): server `fiscal_receipts` ni `status='fiscalized'`, `fm_terminal_id`, `fm_receipt_seq`, `fiscal_sign`, `qr_url`, `fiscal_at` bilan yozadi, `ofd_acked_at` NULL qoladi (48 soat hisobida; OFD tasdig'i agentning `fiscal.status` vazifasi natijasidagi `acked[]` bo'yicha `uq_fiscal_fm_seq` orqali yangilanadi — qaror #68). `pending` — hamkor bulut/`fake` rejimida server chiqaradi; fiskal modul raqami (`fiscal_receipts.fm_receipt_seq`), fiskal belgi/QR keyingi `GET /api/v1/sync/pull`da yoki `GET /api/v1/fiscal-receipts/{id}`da keladi (§14).

**Qarzga sotuv — daromad va fiskal chek** (qaror #30, #45, #59):
- **Daromad va QQS faqat sotuv kuni** tan olinadi (BHMS 2, SK 242-modda 1-qism, 78-modda) — `SalePostingService` provodkasi `doc_date` bilan, to'lov usulidan qat'i nazar (`13-provodka-qoidalari.md` §2.14). Fiskal chek esa **to'lov kuni** chiqariladi (§12.2) — provodka sanasi ≠ fiskal chek sanasi.
- `payments[]`da **faqat** `method=debt` bo'lsa — fiskal chek (`kind='sale'`) **chiqarilmaydi**, javobdagi `fiscal.status="deferred"`, `receipt_seq = null`, `fiscal_receipt_seq = null`. Sotuv hujjatining o'zi (qoldiq −, qarz +, daromad, QQS) oddiy tartibda yoziladi. `FiscalPolicy.credit_sale_receipt` = `none` (standart) / `credit_type` — `credit_type`da sotuv paytida `fiscal_receipts(kind='credit_sale')` (QR va fiskal belgisiz "kredit" turidagi chek) `credit_receipt_seq` raqami bilan chiqariladi; bu tur kerakligi va OFD chek turi kodi tashqi javobga bog'liq (Ochiq savollar 1).
- **Aralash to'lov** (masalan qisman naqd + qisman qarz) — naqd/karta/UzQR/Click/Payme/Uzum qismiga **darhol** oddiy fiskal chek chiqariladi (`fiscal_receipts.kind='sale'`, `receipt_seq`), `fiscal.status="pending"` (yoki `fiscal_result` bilan — `fiscalized`); `credit_type` rejimida qarz qismiga ikkinchi chek (`kind='credit_sale'`) `credit_receipt_seq` bilan. Birinchi chek qatorlari proporsional: `ratio = non_debt_amount / total_amount`; `amt_i = ROUND_HALF_UP(line_total_i × ratio, 2)` (yaxlitlash qoldig'i eng katta `line_total` qatoriga, teng bo'lsa — eng katta `line_no`), `qty_i = ROUND_HALF_UP(qty_i × ratio, 3)` (kamida `0.001`), `vat_i = ROUND_HALF_UP(amt_i × r / (100 + r), 2)` (qaror #26); server `sale_lines.settled_amount` ga `amt_i` ni qo'shadi. Qarz qismiga chek **qarz to'langanda** chiqariladi (§12.2) — keyingi `debt_settlement` qatorlari `line_total_i − settled_amount_i` qoldiqdan.
- Faqat naqd/karta/UzQR/Click/Payme/Uzum (qarz yo'q) — `fiscal.status="pending"`.

**Chekdagi to'lov rekvizitlari** (2026-10-22 dan majburiy, qaror #64): `fiscal_receipts.payment_form` — `cash` (naqd), `card` (bank kartalari), `qr` (`uzqr`/`click`/`payme`/`uzum` — QR-kodli to'lov), `mixed` (bitta chekda bir nechta shakl); karta to'lovida chekka `card_type` (shaxsiy/korporativ/ijtimoiy), ijtimoiy kartada `card_mask` va `rrn` ham yoziladi. Bu maydonlar `payments[]`dan olinadi (`integrated`da — `card_result`dan avtomatik, `card_mask` va `rrn` har doim chekka tushadi; qaror #71), `FiscalPort` chek payload'iga xaritalanadi (`21-integratsiyalar.md` §1). Terminal cheki (slip) terminalning o'zi chop etadi; `card_result.slip_text` bo'lsa ixtiyoriy ravishda bizning chek ostiga ham qo'shiladi (VMQ-943 1-ilova 6-band — ikkala chek beriladi).

**Chek tili — ikki tilli chek**: chek matni/payload **ikki tilda** chiqadi — har bir tovar qatori `"{products.name} / {products.name_ru}"` (name_ru bo'lmasa faqat `name`); sarlavha/yakun matnlari ham ikki tilda ("Jami / Итого", "Qaytim / Сдача" va h.k., to'liq lug'at — chop etish shabloni, §4.9). Fiskal rekvizitlar (STIR, OFD QR, chek raqami) — OFD operatori talab qilgan formatda, tarjima qilinmaydi.

### 4.6 Xatolar (voqea darajasida)

`SHIFT_NOT_OPEN`, `SHIFT_DEVICE_MISMATCH`, `RECEIPT_SEQ_CONFLICT` (`UNIQUE (tenant_id, cash_register_id, shift_id, receipt_seq)` buzilgan; voqeada `fiscal_result` bor bo'lsa (FM imzolagan) rad etilmaydi — server `receipt_seq` ni shu smenadagi `max(receipt_seq) + 1` ga qayta raqamlaydi, qurilma qiymati `fiscal_receipts.payload.device_receipt_seq` da, `sync_exceptions(kind='receipt_seq_conflict')`; `fiscal_result` yo'q — `rejected`, `retryable:false`, eskalatsiya), `PAYMENT_NOT_CONFIRMED` (`checkout_ref` `confirmed` emas yoki allaqachon `consumed` — §16.1), `DEPENDENCY_NOT_SYNCED` (bog'liq voqea — masalan `counterparty.created` — hali qabul qilinmagan, `retryable:true`), `STOCK_NEGATIVE` (faqat **ogohlantirish**, offline overselling ruxsat — §4.7), `DISCOUNT_LIMIT_EXCEEDED`, `DEBT_LIMIT_EXCEEDED`, `MARKING_CODE_INVALID`, `MARKING_CODE_ALREADY_SOLD`, `MARKING_PRICE_UNKNOWN_OFFLINE`, `FISCAL_OFFLINE_48H_BLOCKED`, `FISCAL_DEVICE_LOCKED` (§4.10), `APPROVAL_INVALID` (`ApprovalRef` kutilgan, kelmagan), `CARD_MANUAL_NOT_ALLOWED`, `CARD_MANUAL_APPROVAL_REQUIRED` (online; §4.1), `CARD_TRANSACTION_MISMATCH` (faqat `warnings[]`, rad etmaydi), `SUBSCRIPTION_RESTRICTED`, `VALIDATION_ERROR`. Terminal darajasidagi kodlar (`CARD_TERMINAL_UNREACHABLE`, `CARD_TERMINAL_BUSY`, `CARD_TERMINAL_TIMEOUT`, `CARD_DECLINED`, `CARD_OUTCOME_UNKNOWN`, `CARD_AMOUNT_MISMATCH`, `CARD_VOID_FAILED`) `sale.created`dan **oldin**, POS ↔ terminal bosqichida paydo bo'ladi (§16a) — bunday holatda `sale.created` yuborilmaydi.

### 4.7 Manfiy qoldiq (overselling)

`STOCK_NEGATIVE` — bu holatda ham `status=accepted` (sotuv bekor qilinmaydi), `warnings` massivida qaytadi; `stock_balances` manfiy qiymatga tushadi, tannarx `pending_cost` sifatida (`13-provodka-qoidalari.md` §3.3, BO-03'da "⚠ manfiy qoldiq" belgisi).

### 4.8 Back-office — chek qidiruvi

#### `GET /api/v1/sales`

**Maqsad**: chek qidiruvi (back-office/POS-05). 13-provodka/`17-api-umumiy.md` §9 "Istisno" bandi: `sales` back-office'da faqat o'qiladi, `POST /sales` yo'q.
**Ruxsat**: `sales.create` (faqat o'z filiali, POS-05 chek qidiruvi) yoki `reports.sales.view` (BO-09).
**So'rov**: `?number=&fiscal_receipt_seq=&shift_id=&counterparty_id=&doc_date__gte=&doc_date__lte=&status=&cursor=&limit=`.
**Javob**: `{items:[{id, number, temp_number, doc_date, total_amount, payments_summary, counterparty_id, is_offline, has_returns}], next_cursor}`.
**Bog'liq**: POS-05, BO-09.

#### `GET /api/v1/sales/{id}`

**Maqsad**: to'liq hujjat — qatorlar (`sale_line_id`, `qty`, `returned_qty` — hosila, `marking_code`), to'lovlar, fiskal holat. **`POST /sales/{id}/cancel` yo'q** — o'tkazilgan chek bekor qilinmaydi, tuzatish faqat `return.created`.
**Ruxsat**: `sales.create` yoki `reports.sales.view`.

### 4.9 Chek chop etish shabloni — ikki til

Chek chop etish shabloni (`shared/lib/printer` adapteri — WebUSB/Serial/Bluetooth/tarmoq/bulut, `24-frontend-arxitekturasi.md` §6; native Android — `EscPosPrinterAdapter`/`FiscalPrinterAdapter`, `28-android-pos.md` §4) qator formatini quyidagicha quradi: `{products.name}` birinchi qatorda, agar `products.name_ru` bo'sh bo'lmasa — ikkinchi (kichikroq shrift) qatorda `"{products.name_ru}"`, yoki 80mm'da bitta qatorga sig'adigan `"{name} / {name_ru}"` shablonda. Standart lug'at (uz → ru) sarlavha/yakun matnlari uchun: `Jami`→`Итого`, `Chegirma`→`Скидка`, `Qaytim`→`Сдача`, `Naqd`→`Наличные`, `Karta`→`Карта`, `Qarz`→`Долг`, `Sana`→`Дата`, `Kassir`→`Кассир`. Fiskal rekvizitlar bloki (STIR/korxona nomi, OFD QR, fiskal belgi, chek raqami, to'lov shakli va karta turi — §4.5) — OFD operatori hujjatida ko'rsatilgan tayyor formatda chiqadi, tarjima qilinmaydi. Shablon joylashuvi: `receipt_templates/{80mm,58mm}.json`.

### 4.10 Fiskal bloklar (sotuv, qaytarish, qarz to'lovi uchun umumiy)

Fiskal chek `FiscalPort` orqali chiqariladi — hamkor bulut API'si yoki do'kon kompyuteridagi **Do'kon agenti** (fiskal modul ko'prigi, qaror #60; `34-1c-agent.md`); MVP kodi `FISCAL_PROVIDER=fake` bilan. Fiskal modul o'z raqamini beradi — `fiscal_receipts.fm_receipt_seq` (qurilma `receipt_seq`idan alohida, ikkisi ham saqlanadi), shuningdek `fm_terminal_id`, `fiscal_at`, OFD tasdig'i vaqti `ofd_acked_at`.

| Shart | Natija |
|---|---|
| Shu `cash_register_id`da `ofd_acked_at IS NULL` bo'lgan eng eski fiskal chekning `created_at`idan **≥ 48 soat** o'tgan (`cash_registers.last_unacked_receipt_at`) | Yangi fiskal chek talab qiladigan voqea (`sale.created`, `return.created`, `debt_payment.created`) rad etiladi — `409 FISCAL_OFFLINE_48H_BLOCKED`, `retryable:false`, `audit_log` + M18 xabari (qaror #43; VMQ-943 2-ilova 6-band). Fiskal bo'lmagan amallar (`/sync/push` bilan kutilayotgan cheklarni yuborish, smenani yopish, naqd sanash, qoldiq ko'rish) ishlayveradi; barcha kutilayotgan cheklar OFD tasdig'ini olgach blok avtomatik yechiladi; qo'lda chetlab o'tish yo'q |
| `cash_registers.fm_state ≠ 'ok'` (`locked` / `ack_overdue` / `memory_full` / `unknown`) | Yangi fiskal chek rad etiladi — `409 FISCAL_DEVICE_LOCKED`, `retryable:false`, `params.fm_state` bilan |

Lokal ko'prik rejimida POS fiskal chekni Do'kon agentining lokal API'si orqali chiqaradi (`127.0.0.1`, `Origin` oq ro'yxati + qurilmaga bog'langan token — `21-integratsiyalar.md` §16); agent/FM javob bermasa POS «Fiskal modul ulanmagan» holatida chekni yopmaydi (`24-frontend-arxitekturasi.md` §6.4) — bu server xato kodi emas, voqea serverga yuborilmaydi.

Asosiy himoya — POS'ning o'zida: qurilma 24 soatda 🟡, 40 soatda 🔴 + Egasiga M18, 46 soatda har chek oldidan modal ko'rsatadi va 48 soatda yangi chekni lokal bloklaydi (`16-offline-sync.md` §6); server tekshiruvi — ikkinchi qatlam. Tekshiruv voqeaning `created_at`i bo'yicha: blokdan oldin yaratilib, keyin sinxronlangan voqea rad etilmaydi.

---

## 5. Voqea: `sale.draft_voided`

**Maqsad**: to'lovdan oldin chek/qator bekor qilish — faqat audit, registrga ta'sir yo'q.
**Ruxsat**: `sales.void` (limitsiz, har doim audit).

**So'rov** (payload):

| Maydon | Tur | Majburiy |
|---|---|---|
| `draft_ref` | string | ha — qurilmadagi lokal chek identifikatori (hali `sales.id` emas) |
| `voided_lines[]` | array\|null | yo'q — `null` = butun chek bekor qilindi |
| `reason` | string | yo'q |

**Javob**: `{status: "accepted"}` — faqat `audit_log` yozuvi.
**Xatolar**: `VALIDATION_ERROR`.
**Idempotentlik**: `client_event_id`.
**Offline**: to'liq ishlaydi.
**Bog'liq**: US-M01-01 chekka holat, POS-02 "BEKOR".

---

## 6. Voqea: `receipt.reprinted`

**Maqsad**: chekni qayta chop etish — "NUSXA" belgisi, audit.
**Ruxsat**: `sales.create` (odatiy kassir amali).

**So'rov** (payload):

| Maydon | Tur | Majburiy |
|---|---|---|
| `fiscal_receipt_id` | UUID | ha — qayta chop etilgan chek (`sale`, `return`, `debt_settlement`, `credit_sale`; §14.1 orqali topiladi) |
| `sale_id` | UUID\|null | yo'q |
| `reason` | string | yo'q |

**Javob**: `{status: "accepted", copy_label: "NUSXA"}`. Son cheklanmaydi.
**Idempotentlik**: `client_event_id` (har chaqiruv alohida audit yozuvi, dedupe faqat takror yuborishdan himoya qiladi).
**Bog'liq**: US-M01-01, POS-04.

---

## 7. Qaytarish

### 7.1 Voqea: `return.created`

**Maqsad**: mijozdan tovar qaytarib olish — qoldiq +, kassa/qarz −, QQS −.
**Ruxsat**: `returns.create` (+ limitdan oshganda `returns.approve`).
**Davlat tizimi**: (markirovka bo'lsa) Asl belgisi — **faqat online**.

**So'rov** (payload):

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | — |
| `branch_id`, `shift_id`, `cash_register_id` | UUID | ha | `cash_register_id` — qaytarish kassa harakati/fiskal cheki uchun majburiy |
| `receipt_seq` | integer\|null | shartli | Qurilma beradi, shu smena ichida ketma-ket (`kind='return'` cheki OFD'ga yuboriladi); pul bilan qaytariladigan qism (`money_part`) 0 bo'lsa `null` — chek yo'q |
| `fiscal_result` | object\|null | shartli | `sale.created` (§4.1) bilan bir xil: lokal ko'prik rejimida qaytarish cheki FM'da imzolangan bo'lsa majburiy `{fm_terminal_id, fm_receipt_seq, fiscal_sign, qr_url, fiscal_at}`; hamkor bulut/`fake` rejimida va chek yo'q bo'lsa — `null` (qaror #68) |
| `sale_id` | UUID\|null | shartli | `null` = chek topilmagan qaytarish — **har doim** `approval` majburiy (summadan qat'i nazar) |
| `counterparty_id` | UUID\|null | shartli | `refund_method=debt_adjustment`da majburiy |
| `is_offline` | boolean | ha | Qurilma hisoblaydi |
| `lines[]` | array | ha, ≥1 | pastda |
| `reason` | enum | ha | `defective`/`wrong_item`/`customer_changed_mind`/`other` |
| `refund_method` | enum | ha | `cash`/`card`/`uzqr`/`click`/`payme`/`uzum`/`debt_adjustment`; standart — asl to'lov usuli. Click/Payme/Uzum (va UzQR) pulini qaytarish provayder kabinetida qo'lda, tizim qayd etadi |
| `refund_card` | object\|null | shartli | `refund_method=card`da majburiy (qaror #71): `{card_entry_mode: "integrated"\|"manual", card_result: CardResult\|null, card_type, card_mask, rrn, approval_code, card_scheme, manual_reason, card_manual_approval: ApprovalRef\|null}` → `returns.card_*` ustunlari. **`integrated`** — asl to'lov `integrated` bo'lsa standart: shu terminalda `refund` (asl xarid settlement'dan oldin va shu kunniki bo'lsa — `void`) bajarilgan, `card_result` (`kind=refund`/`void`, `status=approved`, `amount` = pul bilan qaytariladigan qism `money_part`; `void` — faqat to'liq summa) majburiy; `card_type`/`card_mask`/`rrn` `card_result`dan (yoki asl to'lovdan). **`manual`** — terminal boshqa, ishlamaydi yoki asl to'lov `manual` bo'lgan: `manual_reason` majburiy, `card_type` majburiy (asl to'lovdan oldindan to'ldiriladi), `card_manual_fallback` qoidalari §4.1 bilan bir xil |
| `approval` | `ApprovalRef`\|null | shartli | `sale_id=null` YOKI summa `returns.approve.limit_value` (standart 100 000 so'm)dan oshsa YOKI muddati o'tgan tovar qatori bo'lsa (pastda) va `actor_user_id`da `returns.approve` yo'q bo'lsa majburiy |

**`lines[]`**:

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `sale_line_id` | UUID\|null | shartli | `sale_id` berilgan bo'lsa majburiy |
| `product_id` | UUID | ha | — |
| `qty` | Qty | ha | `SUM(qty) WHERE sale_line_id=X AND posted ≤ sale_lines.qty` (`RETURN_QTY_EXCEEDED`) |
| `price` | decimal string (4 xona) | ha | `sale_lines.price` bilan bir xil format (`return_lines.price`); faqat ma'lumot — qaytarish summasini server hisoblaydi (pastda). `sale_id=null`da — joriy narx (asl chek narxi emas) |
| `vat_rate` | decimal (2 xona) | ha | `"12.00"`/`"0.00"` |
| `vat_exemption_code` | string\|null | shartli | QQS imtiyoz kodi |
| `marking_code` | string\|null | shartli | Markirovkalangan qatorda majburiy |
| `restock` | boolean | yo'q | Standart `true` — tovar sotuvga yaroqli qoldiqqa qaytadi; `false` — qoldiqqa sotuvga yaroqli bo'lib qaytmaydi: `+qty` asl partiyaga va shu miqdor `stock_lots.blocked_qty` ga (FIFO/sotuv `qty_left − blocked_qty` dan) (`return_lines.restock`). Muddati o'tgan tovarda server majburan `false` qiladi (pastda) |

**Qaytarish summasi va qarzli sotuv**:
- Qator summasi (chegirmali qator ham): `refund_line = ROUND_HALF_UP(sale_line.line_total × ret_qty / sale_line.qty, 0)`; qatorning oxirgi qaytarilishi qoldiqni oladi (`line_total − Σ oldingi refund_line`). `return_amount = Σ refund_line`.
- Qarzli sotuvni qaytarish: avval shu sotuvning ochiq qarzi kamayadi — `debt_part = min(return_amount, open_debt_of_sale)` (chek yo'q, `Kt 4010`); qolgani `money_part = return_amount − debt_part` `refund_method` bo'yicha pul bilan qaytariladi va faqat shu qismga `kind='return'` chek chiqadi.
- Fiskal qaytarish chegarasi: `fiscal_refund ≤ fiscalized_amount(sale) − already_fiscally_refunded(sale)` (`fiscalized_amount` — sotuvning `sale`/`debt_settlement` cheklaridagi summalar).
- Provodka: `Kt 5710` analitikasi `payment_method = refund_method`; `debt_adjustment` → `Kt 4010` (`13-provodka-qoidalari.md` §2.5).

**Muddati o'tgan tovarni qaytarish** (qaror #48): qator tovarining yaroqlilik muddati o'tgan bo'lsa (`expiry_date < bugun`, Toshkent kuni; asl sotuv partiyasi bo'yicha) — qaytarish ruxsat, lekin:
- `restock` majburan `false` (qurilma `true` yuborsa ham server `false` yozadi, `warnings`siz);
- `actor_user_id`da `returns.approve` bo'lmasa `approval` (`ApprovalRef`, `returns.approve` egasi — Menejer/Egasi) majburiy, aks holda `APPROVAL_REQUIRED` (`retryable:false`; POS PIN yoki BO-16 so'rovini taklif qiladi — `kind=return_over_limit`, `context.expired_return=true`);
- posting shu tranzaksiyada `write_offs` **qoralamasini** yaratadi (`source_return_id` = shu qaytarish, `write_off_lines.reason='expired_return'`), Menejer keyin back-office'da o'tkazadi (`19-api-ombor.md` §15).

**Markirovka qoidasi**: `marking_code` bor qatorli `return.created` — **faqat `is_offline=false`** bilan qabul qilinadi; qurilma offline'da bu amal tugmasini bloklaydi (POS-05), lekin server ham qayta tekshiradi: offline voqea markirovka qatori bilan kelsa `MARKING_RETURN_REQUIRES_ONLINE`. Bu qonundan qat'iyroq ichki tanlov (kod holatini tekshirish, firibgarlikdan himoya). Kod Asl belgisi'ga qaytarish fiskal cheki ichida OFD orqali boradi (§4.2 bilan bir xil, `items[].marking_codes`).

**Javob**: `{id, number, fiscal_receipt_seq, fiscal: {status: "pending"|"fiscalized"|"deferred"}, write_off_id|null, warnings: []}` (qaytarish cheki ham OFD'ga yuboriladi; `money_part = 0` da chek yo'q — `fiscal_receipt_seq = null`, `deferred`; `write_off_id` — muddati o'tgan qator bo'lsa yaratilgan qoralama).
**Xatolar**: `SALE_NOT_FOUND` (`retryable:true` — asl chek hali sinxronlanmagan), `DEPENDENCY_NOT_SYNCED` (`retryable:true`), `RECEIPT_SEQ_CONFLICT` (§4.6 qoidasi), `RETURN_QTY_EXCEEDED`, `RETURN_LIMIT_EXCEEDED`, `APPROVAL_REQUIRED` (muddati o'tgan tovar, `returns.approve` yo'q), `APPROVAL_INVALID`, `CARD_MANUAL_NOT_ALLOWED`, `CARD_MANUAL_APPROVAL_REQUIRED`, `CARD_TRANSACTION_MISMATCH` (`warnings[]`), `MARKING_CODE_INVALID`, `MARKING_RETURN_REQUIRES_ONLINE`, `FISCAL_OFFLINE_48H_BLOCKED`, `FISCAL_DEVICE_LOCKED` (§4.10).
**Idempotentlik**: `client_event_id`.
**Offline**: oddiy tovar — to'liq ishlaydi (append-only); markirovkalangan — bloklanadi (yuqorida).
**Bog'liq**: US-M02-01…03, POS-05.

### 7.2 Back-office — qaytarishlar ro'yxati

#### `GET /api/v1/returns` / `GET /api/v1/returns/{id}`

**Maqsad**: ro'yxat/tafsilot, "chek topilmagan qaytarish"lar `without_receipt=true` bilan ajratiladi (`without_receipt` = `sale_id IS NULL`, hosila; `11-malumotlar-modeli.md` §6).
**Ruxsat**: `reports.sales.view`.
**So'rov**: `?branch_id=&cursor=&limit=`.
**Bog'liq**: US-M02-01…03.

---

## 8. Chegirmalar

### 8.1 Manual chegirma (sotuv ichida)

§4.4ga qarang — alohida endpoint yo'q, `sale_lines[].discount_*` orqali.

### 8.2 Avtomatik chegirma qoidalari (`discount_rules`, M03)

**Ruxsat**: `discount.rule.manage` (ko'rish — `discount.give`/ortiqcha huquqsiz ham POS lokal keshdan o'qiydi).

#### `GET /api/v1/discount-rules`

**So'rov**: `?branch_id=&active_only=&page=&size=` — **page pagination** (ma'lumotnoma).
**Javob**: `{items:[{id, name, scope, target_ids, kind, value, branch_ids, valid_from, valid_to, priority, version}], total, page, size}`.

#### `POST /api/v1/discount-rules`

**So'rov**: `{name, scope: "product"|"category"|"all", target_ids[], kind: "percent"|"amount"|"n_plus_m", value, branch_ids[], valid_from, valid_to, priority}`.
**Idempotentlik**: `Idempotency-Key` majburiy.

#### `GET /api/v1/discount-rules/{id}`

#### `PATCH /api/v1/discount-rules/{id}`

**So'rov**: yuqoridagi maydonlar + majburiy `version`; mos kelmasa `409 VERSION_CONFLICT`.

#### `POST /api/v1/discount-rules/{id}/archive`

Soft-delete (`archived_at`).

**Bitta eng foydali qoida**: server bu endpoint darajasida tanlov qilmaydi (tanlov POS/kassada va posting vaqtida `discount_source` orqali qayd etiladi, §4.4) — bu resurs faqat qoidalarni **ro'yxatga oladi**, qo'llash mantiqiy qoida POS keshida + serverda posting tekshiruvida.
**Offline**: `discount_rules` POS'ga `GET /api/v1/sync/pull?scope=settings` orqali tushadi (`16-offline-sync.md` §1), yozish faqat online.
**Bog'liq**: US-M03-02 (MVP'dan keyin — qaror #33); ekran — Menejer sozlamalari (alohida ekran kodi yo'q, M03).

---

## 9. Tasdiqlash navbati (`approval-requests`)

Umumiy mexanizm — chegirma (limitdan yuqori), qaytarish (limitdan yuqori/chek yo'q), nasiya (limitdan yuqori), kassadan pul olish (limitdan yuqori), narx o'zgarishi (limitdan katta) uchun **bitta** resurs. Menejer/Egasi jismonan kassada bo'lsa bu resurs **chaqirilmaydi** — PIN mahalliy (`ApprovalRef.mode=local_pin`). Faqat Menejer uzoqda, kassir online bo'lganda ishlatiladi (BO-16, POS-06/POS ekranlarida "Menejerga yuborildi" holati).

### 9.1 Sxema (`approval_requests`)

| Maydon | Tur | Izoh |
|---|---|---|
| `id` | UUID | — |
| `kind` | enum | `discount_over_limit` / `return_over_limit` / `return_no_receipt` / `debt_over_limit` / `cash_withdrawal_over_limit` / `price_change` / `expense_over_limit` / `write_off_over_limit` / `card_manual_entry` (karta rekvizitini qo'lda kiritish yoki `unknown` urinishni yopish — `card.manual_entry.approve`, qaror #71; `linked_doc_type` — `sales`/`returns`/`debt_payments`, `context`: `{card_terminal_id, attempt_id?, amount, manual_reason}`) |
| `permission_code` | string | Tasdiqlovchida bo'lishi shart kod (server to'ldiradi — `15-xavfsizlik-va-audit.md` §2.3 xaritasi) |
| `requested_value` | decimal\|null | Summa yoki foiz (`role_permissions.limit_value` bilan bir xil birlik, 4 xonali satr) |
| `context` | object | Kind'ga mos snapshot — masalan `{"amount": "569000.00", "requested_pct": "25.00"}` |
| `linked_doc_type` / `linked_doc_id` | string\|null | `price_change` uchun `price_changes.id` |
| `status` | enum | `pending` / `approved` / `rejected` / `expired` / `consumed` — hujjat postingda shu so'rovni ishlatgach `consumed`ga o'tadi, qayta ishlatilmaydi |
| `requested_by`, `requested_at` | UUID, ISO | — |
| `resolved_by`, `resolved_at`, `reject_reason` | UUID\|null, ISO\|null, string\|null | — |
| `expires_at` | ISO | `requested_at + 15 daqiqa` (standart, sozlanadi — 26 #87) |

### 9.2 `POST /api/v1/approval-requests`

**Maqsad**: masofadan tasdiqlash so'rovi yaratish.
**Ruxsat**: amalni so'ragan rol (`sales.create`/`returns.create`/`debts.create`/`cash.withdraw`/`prices.edit`).

**So'rov**:

| Maydon | Tur | Majburiy |
|---|---|---|
| `kind` | enum | ha |
| `context` | object | ha |
| `linked_doc_type`, `linked_doc_id` | string\|null | shartli |

**Javob**: `201 {id, kind, status: "pending", expires_at}` — bu nuqtada M18 (Telegram/push) orqali Menejer/Egasiga ogohlantirish yuboriladi (implementatsiya — notifications moduli).
**Idempotentlik**: `Idempotency-Key` majburiy.
**Offline**: faqat online (§9.6).
**Bog'liq**: BO-16.

### 9.3 `GET /api/v1/approval-requests` / `GET /{id}`

**Maqsad**: BO-16 navbati.
**Ruxsat**: `discount.approve`/`returns.approve`/`debts.approve`/`prices.approve`/`cash.withdraw` (limit ≥ summa)/`expenses.approve`/`stock.writeoff` (yuqori limit) — mos `kind` bo'yicha filtrlanadi (foydalanuvchi faqat o'z huquqiga mos `kind`larni ko'radi); to'liq `kind` → tasdiqlovchi ruxsati xaritasi — `15-xavfsizlik-va-audit.md` §2.3 (yagona manba).
**So'rov**: `?status=pending&cursor=&limit=`. POS tomoni `GET /api/v1/approval-requests/{id}` orqali **poll** qiladi (har 3 soniyada — standart, sozlanadi, 26 #87) `status` o'zgarishini kutib.
**Bog'liq**: BO-16.

### 9.4 `POST /api/v1/approval-requests/{id}/approve`

**Maqsad**: tasdiqlash.
**Ruxsat**: `kind`ga mos `*.approve` (masalan `discount_over_limit` → `discount.approve`; `cash_withdrawal_over_limit` → `cash.withdraw`, tasdiqlovchining `limit_value`i `context.amount`dan yuqori yoki limitsiz bo'lishi shart).
**So'rov**: `{pin}`. Server PIN'ni tekshiradi va `resolved_by`ning `limit_value`i `context.amount`/`requested_pct`ni qoplashini tasdiqlaydi; muvaffaqiyatli bo'lsa `status=approved`, keyinchalik bog'langan hujjat postingda shu so'rovni **bir marta** ishlatadi va `status=consumed`ga o'tkazadi (`doc_approvals` qatori yoziladi).
**Javob**: `{status: "approved", resolved_by, resolved_at}`.
**Xatolar**: `APPROVAL_INVALID` (noto'g'ri `kind`/huquq), `PIN_INVALID` (noto'g'ri PIN), `APPROVAL_REQUEST_ALREADY_RESOLVED`, `APPROVAL_REQUEST_EXPIRED`.
**Bog'liq**: BO-16.

### 9.5 `POST /api/v1/approval-requests/{id}/reject`

**So'rov**: `{reason}` (majburiy).
**Javob**: `{status: "rejected"}`.

### 9.6 Offline cheklovi

`approval-requests` **faqat online** ishlaydi (§4.3/§7.1'dagi offline over-limit holatlar — bu resursni chaqirmaydi, o'rniga bayroq+audit bilan sotuv/qarz davom etadi, §4.3).

---

## 10. Narx o'zgarishi (`price-changes`) — tasdiqlash bilan bog'lanish

`price-changes` resursining to'liq ta'rifi — **`19-api-ombor.md` §4 (yagona manba)**: `POST /api/v1/price-changes` body'da `lines[].new_price` (4 xonali satr) va `lines[].valid_from` (qator darajasida, hujjat `doc_date` bilan birga). Tasdiqlash — **faqat `approval-requests`** (`kind=price_change`, BO-16 yagona navbat) orqali: `POST /api/v1/price-changes/{id}/post` limitdan katta bo'lsa `202 {status:"pending_approval", approval_request_id}` qaytaradi (`APPROVAL_REQUIRED`) — `price_changes` `pending_approval` holatiga o'tadigan yagona hujjat turi (qaror #25); Egasi (`prices.approve`, faqat Egasi) `approve`laganda server `linked_doc_id`ga tegishli `price_changes` ni `posted` qiladi, `reject` — `rejected`. `POST /price-changes/{id}/approve`/`reject` endpoint'lari bu faylda **yo'q**.

**Xatolar**: `PRICE_CHANGE_LIMIT_EXCEEDED` (API himoyasi sifatida saqlanadi), `VERSION_CONFLICT` (agar tovar narxi orada boshqa amal bilan o'zgargan bo'lsa).
**Bog'liq**: BO-16.

---

## 11. Kontragentlar (`counterparties`)

`counterparties` REST ruxsatlari — **yagona manba shu bo'lim** (`19-api-ombor.md` yetkazib beruvchi ro'yxatlari shu yerga havola qiladi).

### 11.1 Voqea: `counterparty.created` (POS tezkor yaratish, offline ham)

**Maqsad**: US-M08-05 — "2-3 soniyada, daftarga yozgandek".
**Ruxsat**: `sales.create` yoki `debts.create`.

**So'rov** (payload):

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | Qurilma beradi — `counterparties.id` |
| `kind` | enum | ha | `person` (POS'dan odatda shu) |
| `name` | string | ha | — |
| `phone` | string | ha | E.164 yoki O'zbekiston formati (`+998...`) |
| `notify_consent` | boolean | yo'q | Standart `false` |

**Javob**: `{id}`.
**Idempotentlik**: `client_event_id`.
**Offline**: to'liq ishlaydi; keyinchalik `sale.created`/`return.created`/`debt_payment.created` shu `id`ni `counterparty_id` sifatida ishlatadi (bir xil push partiyasida `seq` tartibi bo'yicha oldin yuborilishi shart — `16-offline-sync.md` §3.3).
**Bog'liq**: US-M08-05, POS-06/POS-13 "+ Mijoz".

### 11.2 `POST /api/v1/counterparties` (back-office / online POS to'liq yaratish)

**Ruxsat**: tezkor mijoz (`name`+`phone`) — `debts.create`; to'liq (STIR, bank, kredit limiti) — `debts.limit.manage`; yetkazib beruvchi (`is_supplier=true`) — `purchases.create`.

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `kind` | enum | ha | `person`/`company` |
| `name`, `phone` | string | ha | — |
| `stir` | string\|null | shartli | `kind=company`да B2B e-faktura uchun kerak bo'lsa |
| `legal_address`, `bank_account`, `bank_mfo` | string\|null | yo'q | — |
| `credit_limit` | Money\|null | yo'q | `null` = limitsiz |
| `standing_discount_pct` | decimal\|null | yo'q | — |
| `notify_consent` | boolean | yo'q | — |

**Javob**: `201 {id, version: 1, ...}`. `notify_consent_at` — hosila, `notify_consent=true` bo'lganda server vaqtni yozadi (tanadan qabul qilinmaydi).
**Idempotentlik**: `Idempotency-Key` majburiy.

### 11.3 `GET /api/v1/counterparties`

**Maqsad**: qidiruv ism/telefon bo'yicha (`pg_trgm`).
**Ruxsat**: `sales.create` yoki `debts.create` yoki `stock.view` yoki `purchases.create` (biri yetarli; `GET /{id}` ham shu).
**So'rov**: `?search=&kind=&page=&size=`.
**Javob**: `{items:[{id, name, phone, is_customer, is_supplier, receivable_balance, credit_limit, version}], total, page, size}` — **page pagination**.

### 11.4 `GET /api/v1/counterparties/{id}` / `PATCH /api/v1/counterparties/{id}`

`PATCH` — `version` tanada majburiy, `409 VERSION_CONFLICT` mos kelmasa.
**Ruxsat**: `GET /{id}` — §11.3 bilan bir xil; `PATCH` — `debts.limit.manage` yoki `purchases.create` (`is_supplier=true` kontragent; kredit limiti/doimiy chegirma — faqat `debts.limit.manage`).

---

## 12. Qarz daftari (debt notebook, M08)

### 12.1 `GET /api/v1/counterparties/{id}/debt-ledger`

**Maqsad**: qog'oz "qarz daftari" ko'rinishi.
**Ruxsat**: `debts.create`/`debts.payment.accept` (POS) yoki `reports.sales.view` (BO-06).
**Javob**: `{counterparty: {...}, balance: "230000.00", entries: [{id, doc_type, doc_id, doc_date, amount, direction, due_date, promise_date, comment, status: "open"|"partially_paid"|"paid", products: [...]}], next_cursor}` — `cursor`/`limit` bilan sahifalanadi. `promise_date` — hosila: oxirgi `debt_payments.promise_date` yoki (hali to'lov bo'lmagan bo'lsa) `sale_payments.due_date`; `status` — allokatsiyalardan hisoblanadi (`11-malumotlar-modeli.md` §8 nasiya holat mashinasi).
**Bog'liq**: US-M08-06, BO-06/POS-13.

### 12.2 Voqea: `debt_payment.created` (POS, offline ham)

**Maqsad**: qarz to'lovini qabul qilish.
**Ruxsat**: `debts.payment.accept`.

**Fiskal chek** (qaror #30, #45, #67): qarz to'lovida pul qabul qilinganini tasdiqlovchi chek majburiy (VMQ-943 1-ilova 30-band). `cash`/`card`/`uzqr`/`click`/`payme`/`uzum` usullaridagi qarz to'lovi **faqat POS orqali** shu voqea bilan qabul qilinadi — kassa, smena va `receipt_seq` bilan; chek shu kassa FM'ida chiqadi va shu kassaning 48 soat hisobiga kiradi (qaror #43). Bank o'tkazmasi (`method='bank'`) — faqat back-office §12.3, kassasiz, chek yo'q. **Bitta to'lov = bitta chek**: har bir `debt_payment.created` uchun **bitta** `fiscal_receipts` yozuvi, `kind='debt_settlement'`, summasi = olingan pul (`amount`). Chek qatorlarini qurilma lokal keshdagi `open_debt_docs[]` (`16-offline-sync.md` §1) va yagona allokatsiya funksiyasi bilan hisoblaydi (`fiscal_lines[]`):
- har allokatsiya qilingan sotuv uchun `ratio = alloc_amount / sales.total_amount`; `amt_i = ROUND_HALF_UP(line_total_i × ratio, 2)`, lekin `amt_i ≤ line_total_i − settled_amount_i`; yaxlitlash qoldig'i eng katta `line_total` qatoriga (teng bo'lsa — eng katta `line_no`);
- sotuvni **to'liq yopuvchi** to'lovda `amt_i = line_total_i − settled_amount_i` (kumulyativ aniq), `qty_i` — qolgan miqdor; aks holda `qty_i = ROUND_HALF_UP(qty_i × ratio, 3)` (kamida `0.001`);
- `vat_i = ROUND_HALF_UP(amt_i × r / (100 + r), 2)` (qaror #26); markirovka kodi faqat sotuv qatorini to'liq yopuvchi chekda;
- `debt_openings`/`debt_writeoffs` qismi — tovar qatorsiz bitta umumiy qator ("Qarz to'lovi (boshlang'ich qoldiq) / Погашение долга (начальный остаток)");
- server posting'da `sale_lines.settled_amount` ni kumulyativ yangilaydi.

Zaxira sozlama `FiscalPolicy.debt_receipt_split` = `single` (standart) / `per_sale` (har yopilgan sotuvga alohida chek) — migratsiyasiz almashtiriladi. Chiqarilgan chek ikki tilda (§4.9), to'lov rekvizitlari bilan (§4.5). `FiscalPort.register_sale(kind='debt_settlement')` (`21-integratsiyalar.md` §1) shu oqimni amalga oshiradi; fiskal bloklar — §4.10. Daromad va QQS bu yerda **qayta tan olinmaydi** — ular sotuv kuni yozilgan (§4.5, `13-provodka-qoidalari.md` §2.14); to'lov kuni faqat pul harakati va fiskal chek.

**So'rov** (payload):

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | — |
| `counterparty_id` | UUID | ha | — |
| `branch_id`, `cash_register_id`, `shift_id` | UUID | ha | `shift_id` — `status=open`, shu `device_id` |
| `receipt_seq` | integer | ha | Qurilma beradi, shu smena ichida `sale.created`/`return.created` bilan umumiy ketma-ketlikda (qaror #12); takror — §4.6 `RECEIPT_SEQ_CONFLICT` qoidasi |
| `is_offline` | boolean | ha | Qurilma hisoblaydi |
| `amount` | Money | ha | > `"0.00"`. Online (`is_offline=false`) — `≤ receivable_balance + Σ written_off_open` (hisobdan chiqarilgan ochiq qarz ham to'lanadi), oshsa `422 VALIDATION_ERROR` (`message_key=debt_payment_exceeds_balance`, `params: {balance, requested}`; qaror #45) — kassir qaytimni naqd beradi. `is_offline=true` — rad etilmaydi: chegaragacha allokatsiya, qolgani `debt_payments.unallocated_amount` (`Kt 6310` — olingan bo'nak), `sync_exceptions(kind='debt_overpayment_offline')` + M18 Egasiga (qaror #67) |
| `method` | enum | ha | `cash`/`card`/`uzqr`/`click`/`payme`/`uzum` (`bank` — faqat §12.3) |
| `terminal_ref` | string\|null | yo'q | `method=card`; `uzqr`+`qr_type=static`da ixtiyoriy to'lov raqami |
| `card_type`, `card_mask`, `rrn` | — | shartli | §4.1 `payments[]` bilan bir xil qoidalar (`method=card`da `card_type` majburiy; `social`da `card_mask`+`rrn`) |
| `card_entry_mode`, `card_result`, `card_type_source`, `approval_code`, `card_scheme`, `manual_reason`, `card_manual_approval` | — | shartli | `method=card`da §4.1 `payments[]` bilan aynan bir xil qoidalar (qaror #71); `card_result.amount` = `amount`; server `debt_payments.card_*` ustunlarini to'ldiradi |
| `qr_type` | enum\|null | shartli | `method=uzqr`da majburiy: `static`/`dynamic` |
| `checkout_ref` | UUID\|null | shartli | `click`/`payme`/`uzum` va dinamik `uzqr`da — §16dagi `payment_checkouts.checkout_ref`; statik `uzqr`da `null` |
| `provider_tx_id` | string\|null | shartli | `click`/`payme`/`uzum` va dinamik `uzqr`da majburiy; statik `uzqr`da ixtiyoriy |
| `promise_date` | ISO sana\|null | yo'q | Yangi va'da sanasi (agar qoldiq qolsa) — qoldiq qolsa mijozning **joriy** va'da sanasi yangilanadi (`counterparties.debt_due_date`); `debt_payments.promise_date` ustuni saqlanadi (`sale_payments.due_date`dan farqli nom) |
| `comment` | string\|null | yo'q | — |
| `allocations[]` | array | ha | Qurilma hisoblagan allokatsiya: `[{target_doc_type: "sales"\|"debt_openings"\|"debt_writeoffs", target_doc_id, amount}]` |
| `fiscal_lines[]` | array | ha, ≥1 | Chek qatorlari (yuqoridagi formula): `[{sale_id\|null, sale_line_id\|null, product_id\|null, qty, amount, vat_rate, vat_amount, marking_code\|null}]` |
| `fiscal_result` | object\|null | shartli | §4.1 bilan bir xil — lokal ko'prik rejimida chek FM'da imzolangan bo'lsa majburiy (qaror #68) |

**Allokatsiya** — yagona funksiya (`shared/lib/debt-allocation` (TS) va `app/shared/debt_allocation.py`, umumiy test-vektorlar `shared/debt-allocation-vectors.json`) tartibi bilan: avval `sales` + `debt_openings` ochiq qoldiqlari `ORDER BY COALESCE(due_date, doc_date), doc_date, doc_id`; keyin `debt_writeoffs` (hisobdan chiqarilgan, eng eskisi birinchi — bu qism `Kt 9390`, `13-provodka-qoidalari.md` §2.14). Qurilma hisoblaydi, server postingda DB holatidan qayta hisoblaydi: registrlar (`debt_payment_allocations`, `debt_moves`, `settled_amount`) **server** allokatsiyasi bo'yicha yoziladi; fiskal chek payload'i qurilma yuborgan ko'rinishda saqlanadi (FM imzolagan — o'zgarmaydi). Farq bo'lsa voqea rad etilmaydi — `sync_exceptions(kind='debt_allocation_mismatch', details:{device, server})`.
**Offline ortiqcha summa** (qaror #67): provodka `Dt 5010/5710 / Kt 6310` (analitika `counterparty_id`); hal qilish BO-06 da (Buxgalter/Egasi): (a) qaytarish — `cash_movements` `reason='other'`, `direction='out'`, `account='6310'`, `counterparty_id` (§13.1); (b) keyingi qarzga hisoblash — `ledger_adjustments` `Dt 6310 / Kt 4010` (`analytics.counterparty_id`).
**Javob**: `{id, allocations: [{target_doc_type, target_doc_id, amount}], unallocated_amount, remaining_balance, fiscal: {status: "pending"|"fiscalized"}}` (`allocations` — server natijasi, `debt_payment_allocations` ustunlari bilan bir xil).
**Xatolar**: `VALIDATION_ERROR` (`debt_payment_exceeds_balance` — faqat online, va boshqa shartlar), `CARD_MANUAL_NOT_ALLOWED`, `CARD_MANUAL_APPROVAL_REQUIRED`, `CARD_TRANSACTION_MISMATCH` (`warnings[]`), `SHIFT_NOT_OPEN`, `RECEIPT_SEQ_CONFLICT` (§4.6 qoidasi), `PAYMENT_NOT_CONFIRMED` (§16.1), `DEPENDENCY_NOT_SYNCED` (`retryable:true`), `FISCAL_OFFLINE_48H_BLOCKED`, `FISCAL_DEVICE_LOCKED` (§4.10), `NOT_FOUND`.
**Idempotentlik**: `client_event_id`.
**Offline**: to'liq ishlaydi; lokal ko'prik rejimida chek FM'da darhol imzolanadi (`fiscal_result`); hamkor bulut va `fake` rejimida chekni server chiqaradi, `outbox_jobs(kind='ofd_send')` faqat `partner_cloud` rejimida (`16-offline-sync.md` §6).
**Bog'liq**: US-M08-04/09, POS-13, BO-06 "To'lov qabul qilish".

### 12.3 `POST /api/v1/debt-payments` (back-office)

**Maqsad**: bank o'tkazmasi bilan kelgan qarz to'lovini qayd etish (BO-06). Faqat `method='bank'` — kassasiz, fiskal chek yo'q (qaror #67): `cash_register_id`, `shift_id`, `receipt_seq` — `null`; provodka `Dt 5110 / Kt 4010` (`13-provodka-qoidalari.md` §2.14).
**So'rov**: `{counterparty_id, branch_id (majburiy), amount, method: "bank", doc_date, promise_date?, comment?}`; boshqa `method` → `422 VALIDATION_ERROR` (`params.field="method"`, `message_key=validation.debt_payment_backoffice_bank_only`). `amount` chegarasi va allokatsiya — §12.2 (online qoida).
**Ruxsat**: `debts.payment.accept`.
`POST /api/v1/debt-payments` (draft) → `POST /api/v1/debt-payments/{id}/post`.
**Idempotentlik**: `Idempotency-Key` majburiy.

### 12.4 `POST /api/v1/debt-openings` → `POST /{id}/post`

**Maqsad**: eski qog'oz daftardagi qarzlarni ko'chirish (US-M08-07).
**Ruxsat**: `stock.opening.manage` yoki `debts.limit.manage`.
**So'rov**: `{counterparty_id yoki {name, phone}, amount, direction: "receivable"|"payable", due_date|null}` — bir martalik yoki `import_jobs` orqali Excel (`11-malumotlar-modeli.md` §10, alohida import endpoint M04 hujjatida).

### 12.5 `POST /api/v1/debt-writeoffs` → `POST /{id}/post`

**Maqsad**: qarzni kechish.
**Ruxsat**: `debts.forgive` — **faqat Egasi**.
**So'rov**: `{counterparty_id, amount, reason, account_choice}` (`reason` majburiy; `account_choice` — standart `"9430"`, muqobil `"4910"`, ixtiyoriy, `13-provodka-qoidalari.md` §2.15).
Audit — majburiy (`15-xavfsizlik-va-audit.md` §6.1).
**Xatolar**: `DEBT_ALREADY_PAID` (mijozning ochiq qarzi 0), `VALIDATION_ERROR`.

### 12.5a Qarz hujjatlari — ko'rish va bekor qilish

| Endpoint | Ruxsat |
|---|---|
| `GET /api/v1/debt-payments` / `GET /{id}` | `reports.sales.view` yoki `debts.payment.accept` |
| `POST /api/v1/debt-payments/{id}/cancel` | `debts.payment.accept` |
| `GET /api/v1/debt-openings` / `GET /{id}` | `reports.sales.view` yoki `stock.opening.manage` yoki `debts.limit.manage` |
| `POST /api/v1/debt-openings/{id}/cancel` | `stock.opening.manage` yoki `debts.limit.manage` |
| `GET /api/v1/debt-writeoffs` / `GET /{id}` | `reports.sales.view` yoki `debts.forgive` |
| `POST /api/v1/debt-writeoffs/{id}/cancel` | `debts.forgive` |

**Ro'yxat so'rovi**: `?counterparty_id=&branch_id=&status=&doc_date__gte=&doc_date__lte=&cursor=&limit=` → `{items, next_cursor}`.
**Bekor qilish**: tana `{reason}` (majburiy); `posted` hujjat — storno joriy ochiq davr sanasida (`13-provodka-qoidalari.md` §5.2), yopilgan davrdagi hujjat ham bekor qilinadi; `draft` — registrsiz `cancelled`. POS `debt_payment.created` bilan yaratilgan to'lovning fiskal cheki bekor qilinmaydi — pulni qaytarish alohida kassa chiqimi bilan.
**Xatolar**: `DOC_INVALID_STATE` (allaqachon `cancelled`), `VALIDATION_ERROR`.
**Idempotentlik**: `Idempotency-Key` majburiy.

### 12.6 Shubhali qarz belgisi

#### `POST /api/v1/debt-doubtful-flags`

**So'rov**: `{counterparty_id, reason}` (majburiy). **Ruxsat**: `debts.forgive` — **faqat Egasi**; boshqa rol — `403 DOUBTFUL_FLAG_REQUIRES_OWNER`. Bu provodka yaratmaydi, faqat belgi/ko'rinish.

#### `POST /api/v1/debt-doubtful-flags/{id}/unflag`

Bekor qilish. **Ruxsat**: `debts.forgive` (Egasi). Tizim avtomatik belgilamaydi — faqat 60+ kunlik ro'yxatni (§12.8) eslatma sifatida ko'rsatadi.

### 12.7 `POST /api/v1/counterparties/{id}/statement-link`

**Maqsad**: mijoz Telegram orqali o'z qarz tarixini ko'rishi (US-M08-08).
**Ruxsat**: `debts.create`/`debts.payment.accept`.
**Javob**: `{url, token, expires_at}` — imzolangan, muddatli (30 kun — standart, sozlanadi, qaror #54), faqat shu `counterparty_id`ning o'z ma'lumotini ko'rsatadigan ochiq (autentifikatsiyasiz, token-asosli) havola; haqiqiy ko'rinish `/public/debt-statements/{token}` yo'lida (M18 hujjatida).

### 12.8 Offline over-limit bayrog'i va eskirish hisoboti

Qarz eskirishi hisoboti — **yagona manba `20-api-moliya-admin.md` #21, `GET /api/v1/reports/debts-aging?direction=receivable&bucket=&branch_id=&limit_exceeded_offline=&as_of=`** (`bucket` qiymatlari: `0-30` / `31-60` / `60+`). Javobga shu fayldagi maydonlar qo'shiladi: `rows[].due_date`, `rows[].overdue_since`, `rows[].limit_exceeded_offline` (§4.3dagi bayroq ko'rinishi — Egasi uchun "offline oshib ketgan qarzlar" ro'yxati), `rows[].doubtful_flag`. **60+ kunlik eslatma**: `bucket="60+"` filtri — tizim avtomatik hech narsani belgilamaydi, faqat eslatma ro'yxati sifatida ko'rsatiladi (US-M08-10, §12.6).
**Ruxsat**: `reports.finance.view` yoki `debts.approve`.

---

## 13. Kassa pul harakati (M16)

### 13.1 Voqea: `cash_movement.created`

**Ruxsat**: `cash.deposit` (kirim) / `cash.withdraw` (chiqim).

**So'rov** (payload):

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | — |
| `cash_register_id`, `shift_id` | UUID | ha | `shift_id.status=open` |
| `direction` | enum | ha | `in`/`out`; `reason` bilan juftlik: `collection`, `owner_withdrawal` → faqat `out`; `deposit` → faqat `in`; `other` → ikkalasi; buzilsa `422 VALIDATION_ERROR` |
| `reason` | enum | ha | `collection`/`deposit`/`owner_withdrawal`/`other` (POS xarajati — alohida `expense.created` voqeasi, §13.2) |
| `account` | string\|null | yo'q | Faqat `reason=other`: `9430`/`9390`/`6310`/`4010`/`4730` (Buxgalter/Egasi tanlaydi); standart — `other/out` → `9430` (`Dt account / Kt 5010`), `other/in` → `9390` (`Dt 5010 / Kt account`) (`13-provodka-qoidalari.md` §2.18); boshqa `reason` da `null` |
| `counterparty_id` | UUID\|null | shartli | `reason=owner_withdrawal` va `tenants.legal_form ≠ sole_proprietor` bo'lsa majburiy (`counterparties.is_founder=true` — ta'sischi); `reason=other` va `account ∈ {6310, 4010}` bo'lsa majburiy; aks holda `null` |
| `employee_id` | UUID\|null | shartli | `reason=other` va `account=4730` bo'lsa majburiy (`users.id`); aks holda `null` |
| `amount` | Money | ha | > `"0.00"` |
| `comment` | string | shartli | `reason=other`da majburiy |
| `approval` | `ApprovalRef`\|null | shartli | `direction=out` va summa `cash.withdraw.limit_value` (standart 50 000 so'm)dan oshsa majburiy |

**Javob**: `{id}`.
**Xatolar**: `CASH_WITHDRAW_LIMIT_EXCEEDED`, `APPROVAL_INVALID`, `SHIFT_NOT_OPEN`, `VALIDATION_ERROR` (`reason↔direction` juftligi, `account`/`counterparty_id`/`employee_id` shartlari).
**Offline**: to'liq ishlaydi (`local_pin` yo'li bilan — Menejer jismonan); masofadan (`remote_request`) — faqat online, chunki jismoniy pul darhol topshiriladi, aks holda kassir jismonan kutadi.
**Bog'liq**: US-M16-01, POS-14.

### 13.2 Voqea: `expense.created` (POS-14 «Xarajat»)

**Maqsad**: kassadan naqd xarajat to'lash (`expenses.source='cash'`).
**Ruxsat**: `cash.withdraw` (limit, standart 50 000 so'm — qaror #23); limitdan oshsa `approval` majburiy. Kassirda `expenses.create` yo'q — bu yo'l faqat `source='cash'` uchun.

**So'rov** (payload — `20-api-moliya-admin.md` #42 tanasi bilan bir xil maydonlar):

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | Qurilma beradi — `expenses.id` |
| `doc_date` | ISO sana | ha | Toshkent kuni |
| `branch_id`, `cash_register_id`, `shift_id` | UUID | ha | `shift_id.status=open`, shu `device_id` |
| `category_id` | UUID | ha | `expense_categories`, arxivlanmagan |
| `amount` | Money | ha | > `"0.00"` |
| `comment` | string\|null | yo'q | — |
| `tax_type` | enum\|null | yo'q | #42 bilan bir xil |
| `approval` | `ApprovalRef`\|null | shartli | `amount` `cash.withdraw.limit_value`dan oshsa va `actor_user_id` limiti yetmasa majburiy (`approval_requests.kind='cash_withdrawal_over_limit'`) |

**Posting**: server `ExpensePostingService` bilan darhol `posted` — `expenses` + `cash_moves` (`13-provodka-qoidalari.md` §2.17).
**Javob** (`server`): `{id, status: "posted"}`.
**Xatolar**: `CASH_WITHDRAW_LIMIT_EXCEEDED`, `APPROVAL_INVALID`, `SHIFT_NOT_OPEN`, `VALIDATION_ERROR`, `NOT_FOUND` (`params.resource=expense_category`).
**Idempotentlik**: `client_event_id`.
**Offline**: to'liq ishlaydi (`local_pin` yo'li bilan).
**Bog'liq**: US-M16-01, POS-14.

### 13.3 `GET /api/v1/cash-movements`

**Maqsad**: faqat o'qish (back-office) — masalan inkasso yozish; ta'rif yagona manba `20-api-moliya-admin.md` #52, bu yerga havola.
**Ruxsat**: `reports.sales.view` **yoki** `cash.count.shift`.
**So'rov**: `?cash_register_id=&shift_id=&cursor=&limit=`.
**Bog'liq**: US-M16-01, US-M16-03.

---

## 14. Fiskal chek holati va qayta urinish

### 14.1 `GET /api/v1/fiscal-receipts` / `GET /api/v1/fiscal-receipts/{id}`

**Ruxsat**: `reports.sales.view` (BO-14 shu yerdan oziqlanadi) yoki `sales.create` (faqat o'z filiali — POS-04/POS-13 qayta chop etish).
**So'rov**: `?sale_id=&debt_payment_id=&shift_id=&kind=&status=&cursor=&limit=`.
**Javob** (bitta element): `{id, sale_id, debt_payment_id, return_id, kind: "sale"|"return"|"z_report"|"debt_settlement"|"credit_sale", status: "pending"|"sent"|"fiscalized"|"failed", receipt_seq, fm_terminal_id, fm_receipt_seq, fiscal_sign, qr_url, payment_form: "cash"|"card"|"qr"|"mixed", delivery: "printed"|"electronic", fiscal_at, ofd_acked_at, sent_at, offline_since, attempts}` — `receipt_seq` qurilma raqami, `fm_receipt_seq` fiskal modul raqami (ikkisi alohida); `ofd_acked_at IS NULL` cheklar §4.10 dagi 48 soatlik blok hisobiga kiradi.

### 14.2 `POST /api/v1/fiscal-receipts/{id}/retry`

**Maqsad**: BO-14 "Qayta urinish" tugmasi — `outbox_jobs(kind=ofd_send)`ni `queued`ga qaytaradi.
**Ruxsat**: `integrations.retry` (OFD/e-faktura/markirovka integratsiya ishini qo'lda qayta navbatga qo'yish, Egasi/Menejer/Buxgalter).
**Idempotentlik**: `Idempotency-Key` majburiy.
**Javob**: `{status: "requeued"}`.

---

## 14a. Chiquvchi e-faktura (`einvoices`, `direction=out`)

### `GET /api/v1/einvoices?direction=out&status=&cursor=&limit=`

**Ruxsat**: `einvoice.sign` yoki `purchases.post`.

### `POST /api/v1/einvoices`

**So'rov**: `{direction:"out", counterparty_id, related_doc_type:"sales"|null, related_doc_id|null, doc_date, lines?}` → `201 {id, status:"draft"}`. `counterparty.kind='company'` va sotuvda `method=debt` bo'lsa server `sale.created` postingida `draft` ni o'zi yaratadi (`related_doc_type="sales"`) — POS bu endpointni chaqirmaydi.
**Ruxsat**: `einvoice.create`.
**Xatolar**: `EINVOICE_COUNTERPARTY_INCOMPLETE`.

### `POST /api/v1/einvoices/from-receipt`

**So'rov**: `{sale_id, counterparty_id}` — chekdan oldindan to'ldirilgan qoralama (qaytarishlar ayirilgan holda); `related_doc` bog'lanadi, QQS/provodka **yo'q** (`13-provodka-qoidalari.md` §2.22).
**Ruxsat**: `einvoice.create`.
**Xatolar**: `EINVOICE_ALREADY_LINKED`, `EINVOICE_AMOUNT_EXCEEDS_RECEIPT`.

### `POST /einvoices/{id}/sign-challenge` · `POST /einvoices/{id}/submit-signed`

`19-api-ombor.md` §19 dagi bilan **bir xil** (umumiy, yo'nalishdan qat'i nazar).
**Ruxsat**: `einvoice.sign`.
**Xatolar**: `EIMZO_SIGN_FAILED`.

### `POST /api/v1/einvoices/{id}/send` · `POST /api/v1/einvoices/{id}/cancel`

`send` → `202`, `outbox_jobs(kind=einvoice_send)` → Faktura.uz orqali; `cancel` — operator qoidasi bo'yicha.
**Ruxsat**: `einvoice.sign`.

Provodka **yo'q** (`13-provodka-qoidalari.md` §2.22); bitta hujjatga bitta faol chiquvchi faktura — `uq_einvoice_out_per_doc`.
**Bog'liq**: BP-03, BP-13.

---

## 15. Markirovka tekshiruvi

### `POST /api/v1/marking-codes/verify`

**Maqsad**: DataMatrix kodni skanerlashda sotuvdan oldingi ixtiyoriy sifat tekshiruvi — **hech narsa saqlamaydi**, faqat tekshiradi (`21-integratsiyalar.md` §4.1). Sotuvning o'zi CRPT'ga bu endpoint orqali emas, fiskal chek ichida OFD orqali boradi (§4.2, qaror #62). `MARKING_PRECHECK=off`da POS bu endpoint'ni chaqirmaydi.
**Ruxsat**: `sales.create`. Sinxron, timeout 3 s (standart, sozlanadi), retry yo'q.

**So'rov**:

| Maydon | Tur | Majburiy |
|---|---|---|
| `code` | string | ha — DataMatrix xom qiymati |
| `product_id` | UUID\|null | yo'q — agar kod ichidan mahsulot aniqlanmasa, qurilma skanerlangan shtrix-kod/tanlangan tovarni beradi |

Server avval **lokal** tekshiradi (format, tenantdagi `marking_codes.status IN ('sold','pending_verification')` takrori), keyin `MarkingPort.verify_code` orqali CRPT'ga murojaat qiladi. Natija `MARKING_PRECHECK` rejimiga qarab:

| Holat | `warn` (standart) | `block` |
|---|---|---|
| CRPT: kod yaroqli | `200 {valid: true, status: "in_stock"}` | xuddi shu |
| Format xatosi (lokal) | `422 MARKING_CODE_INVALID` | xuddi shu |
| Tenantda allaqachon sotilgan (lokal) | `409 MARKING_CODE_ALREADY_SOLD` | xuddi shu |
| CRPT: kod yaroqsiz (`already_sold`/`expired`/`not_found`) | `200 {valid: false, details: {reason}, warnings: ["MARKING_PRECHECK_WARNING"]}` — POS ogohlantirish ko'rsatadi, sotuv davom etadi, `audit_log` | `409 MARKING_VERIFY_FAILED` (`params.reason`) — sotuv rad |
| CRPT javob bermadi (timeout 3 s) | `200 {valid: null, warnings: ["MARKING_PRECHECK_WARNING"]}` — sotuv davom etadi | `503 MARKING_VERIFY_UNAVAILABLE` — POS qatorni chekka qo'shmaydi, zaxira yo'l yo'q (qaror #62) |

**Offline**: bu endpoint umuman chaqirilmaydi (internet yo'q) — POS mahalliy format va takror-kod (sinxronlangan `marking_codes` keshi) tekshiradi, `sale.created`ga `marking_offline=true` bilan yuboradi (§4.2).
**Bog'liq**: US-M01-03, POS-02.

---

## 16. To'lovlar — UzQR / Click / Payme / Uzum (do'kon sotuvi uchun)

**Merchant modeli** (qaror #46): sotuv to'lovlari — har tenant o'z merchant hisobi va kalitlari (`tenant_secrets`da shifrlangan; dinamik UzQR API kaliti — har kassa uchun alohida, `tenant_secrets.cash_register_id`), pul to'g'ridan-to'g'ri do'konga tushadi. Platforma merchant'i faqat obuna billingi (M17) uchun.

**Fiskalizatsiya qoidasi**: do'kon sotuvida har bir to'lov usulida fiskal chekni **faqat bizning kassamiz** chiqaradi (`FiscalPort`, §4.10); provayderga faqat chek havolasi yuboriladi (Click `submit_qrcode`, Payme `receipts.set_fiscal_data`, Uzum `/fiscal`). Tenant provayder kabinetida **provayder tomonidagi avto-fiskalizatsiya o'chiq** bo'lishi shart — aks holda ikki marta fiskalizatsiya bo'ladi (onboarding/BO-14 tekshiruv bandi, `21-integratsiyalar.md` §9).

**Provayderlar holati** (`21-integratsiyalar.md` §9): **UzQR** — statik QR hozir (qo'lda tasdiq, checkout'siz), dinamik QR — `UzqrPort` stub (POS API spetsifikatsiyasi bank/CBU'dan kelgach real adapter); **Click** — rasmiy sandbox bor (Playground + Postman to'plami); **Payme** — sandbox (`TEST_KEY`), Basic Auth; **Uzum** — Merchant API JSON webhook'lari (`/check`, `/create`, `/confirm`, `/reverse`, `/status`) + Basic Auth.

### 16.1 Oqim

**Dinamik UzQR / Click / Payme / Uzum** (faqat online):
1. Kassir to'lov usulini tanlaydi (POS-03) → `POST /api/v1/payments/checkouts` (`provider` tanada).
2. Mijoz QR'ni skanerlaydi/to'laydi → bank/provayder `POST /api/v1/payments/webhooks/{provider}` orqali serverga xabar beradi (yoki POS `GET /api/v1/payments/checkouts/{checkout_ref}` bilan poll qiladi).
3. Tasdiq kelgach, POS `sale.created` (yoki `debt_payment.created`)ni shu `checkout_ref`/`provider_tx_id` bilan yuboradi (§4, §12.2).
4. Sotuv/qarz to'lovi posting'i checkout'ni `confirmed → consumed` qiladi; checkout `confirmed` bo'lmasa yoki allaqachon `consumed` bo'lsa → `PAYMENT_NOT_CONFIRMED`.

**Statik UzQR** (do'kondagi bosma QR): checkout yaratilmaydi; mijoz to'lagach, kassir mijoz telefonidagi to'lov tasdig'ini ko'rib **qo'lda tasdiqlaydi** (mustaqil terminaldagi `card` kabi), ixtiyoriy to'lov raqamini `terminal_ref`ga kiritadi; POS `sale.created`ni `method=uzqr`, `qr_type=static`, `checkout_ref=null`, `provider_tx_id=null` bilan yuboradi. Tushum 5710 orqali `bank_settlements` bilan solishtiriladi (qaror #42). Statik UzQR faqat online'da ruxsat — offline qabul qilish yo'q (`16-offline-sync.md` §2).

### 16.2 `POST /api/v1/payments/checkouts`

**Maqsad**: to'lov boshlash.
**Ruxsat**: `sales.create`. **Faqat online**.

**So'rov**:

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `checkout_ref` | UUIDv7 | ha | Qurilma beradi — kelgusi `sale.created.payments[].checkout_ref` bog'lanishi uchun mahalliy kalit |
| `provider` | enum | ha | `uzqr`/`click`/`payme`/`uzum` |
| `cash_register_id` | UUID | ha | Shu kassaga tegishli checkout |
| `amount` | Money | ha | — |
| `qr_type` | enum\|null | shartli | `provider=uzqr`da majburiy, faqat `dynamic` (statik UzQR checkout'siz — §16.1); `static` kelsa `VALIDATION_ERROR` |

Bu endpoint faqat do'kon sotuvi uchun — bizning obuna to'lovi (`"billing"` konteksti) alohida `POST /billing/checkout` yo'lida.
**Javob**: `{checkout_ref, provider, provider_tx_id|null, qr_payload|checkout_url, status: "pending", expires_at}` — `expires_at` va eskirgan (`expired`) checkout'larni tozalash muddati — 24 soat (standart, sozlanadi, qaror #54). Webhook tenantni `app.payments_checkout_by_provider_tx()`/`app.payments_checkout_by_ref()` orqali topadi.
**Idempotentlik**: `Idempotency-Key` majburiy (takror bosilgan tugma ikkinchi checkout yaratmasligi uchun).
**Bog'liq**: POS-03.

### 16.3 `GET /api/v1/payments/checkouts/{checkout_ref}`

**Ruxsat**: `sales.create`.
**Javob**: `{checkout_ref, provider, provider_tx_id, status: "pending"|"confirmed"|"consumed"|"failed"|"expired", amount, confirmed_at}`. POS poll qiladi (har 2 s — standart, sozlanadi, qaror #54) chek "to'lov kutilmoqda" holatida.
**Bog'liq**: POS-03.

### 16.4 `POST /api/v1/payments/webhooks/{provider}` (kiruvchi)

**Maqsad**: bank/to'lov tizimidan keladigan tasdiq.
**Ruxsat**: — (bizning OAuth/CSRF emas, provayderning o'z imzosi tekshiriladi, tenantning o'z merchant kalitlari bilan: Click — MD5 `sign_string` (SHOP API Prepare/Complete); Payme — Basic Auth (JSON-RPC Merchant API); Uzum — Basic Auth (JSON webhook'lar `/check`, `/create`, `/confirm`, `/reverse`, `/status`); dinamik UzQR — `UzqrPort` (protokol bank/CBU spetsifikatsiyasidan, hozircha stub), `21-integratsiyalar.md` §9).
**Javob**: darhol `200` (aks holda provayder qayta-qayta yuboradi).
**Idempotentlik**: `provider_tx_id` (`UNIQUE`, ikkinchi marta kelsa no-op muvaffaqiyat).

### 16.5 Xatolar

`PAYMENT_PROVIDER_ERROR` (umumiy — tashqi tizim xatosi), `PAYMENT_NOT_CONFIRMED` (tasdiq kelmadi; muddat o'tishi checkout `status=expired` bilan ifodalanadi, chek "kutilmoqda" holatida qoladi, kassir boshqa usulga o'tishi mumkin).
**Offline**: checkout oqimi (dinamik UzQR/Click/Payme/Uzum) butunlay ishlamaydi — statik UzQR ham offline'da ruxsat etilmaydi; offline paytda faqat `cash`/`debt`/`card` ishlaydi — karta integratsiyalangan terminal orqali (agent/Android lokal zanjiri — §16a.7) yoki qo'lda (`card_type`, `terminal_ref`).

---

## 16a. Karta — integratsiyalangan terminal (qaror #71)

Kassir karta raqami/RRN'ni yozmaydi: POS summani do'kondagi bank terminaliga tarmoq (LAN/Wi-Fi) orqali yuboradi va natijani avtomatik oladi. Port, adapterlar, holat mashinasi, taymautlar — `21-integratsiyalar.md` §9.4; agent lokal API sxemalari — §16.1; xavfsizlik — `14-autentifikatsiya-oauth2.md` §2.4, `15-xavfsizlik-va-audit.md` §9.3; offline — `16-offline-sync.md` §2.1; DDL — `12-db-sxema.md` (`card_terminals`, `card_terminal_transactions`, `card_terminal_settlements`).

### 16a.1 Terminal tanlash va zaxira siyosati

- POS kassaning faol terminallarini sinxrondan (`sync/pull` `scope=settings` — `card_terminals` qatorlari, PAN/kalitlarsiz) va agentdan (`GET /v1/card/terminals`) oladi; standart — `is_default=true`, aks holda yagona faol terminal; bir nechta bo'lsa kassir tanlaydi.
- "Karta" bosilganda — `health` (agent `GET /v1/card/health`, ≤ 3 s): `online` → integratsiyalangan oqim (16a.2); `busy` → `CARD_TERMINAL_BUSY`, kutish; `offline`/`error`/agent javob bermaydi → `CARD_TERMINAL_UNREACHABLE`, integratsiyalangan yo'l yopiladi va zaxira taklif qilinadi.
- **Zaxira** — `card_entry_mode=manual` (§4.1), siyosat `tenants.settings.card_manual_fallback`: `allow` — kassir terminal chekidan kiritadi; `manager_approval` — POS-06 PIN oynasi (`ApprovalRef`, `kind=card_manual_entry`, `card.manual_entry.approve`) yoki BO-16 so'rovi (online); `forbid` — `CARD_MANUAL_NOT_ALLOWED`, boshqa to'lov usuli. Sozlama yo'q: faol terminal bog'langan kassada `manager_approval`, terminalsiz kassada `allow` (`manual_reason=standalone_terminal`).

### 16a.2 Sotuv ketma-ketligi (agent orqali, Windows veb-kassa)

1. POS `attempt_id` (UUIDv7) yaratadi va lokal `card_attempts`ga `pending` yozadi (`16-offline-sync.md` §2.1); online bo'lsa — ixtiyoriy ravishda `POST /card-terminal-transactions` (`result`siz, `status=pending` bilan — server BO-14'da "jarayonda" ko'radi).
2. `POST http://127.0.0.1:47110/v1/card/purchase {attempt_id, local_id, amount_tiyin, currency:"UZS", cash_register_id, client_event_id, receipt_seq?}` — uzun so'rov ≤ 125 s (yoki `202` → `GET /v1/card/tx/{attempt_id}` poll). POS "Kartani terminalga qo'ying" ekranini summa, hisoblagich (120 s) va "Bekor qilish" (`POST /v1/card/cancel-pending`, drayver qo'llasa) bilan ko'rsatadi.
3. Natija (`CardTxResult` → `CardResult`, §2.7):
   - `approved` va `amount_tiyin` = so'ralgan → `card.purchase.approved`; `card_type` yo'q bo'lsa `card_bin_rules` (BIN — faqat xotirada), topilmasa bitta bosishli tanlov (`card_type_source=cashier`);
   - `approved`, lekin summa farq qiladi → POS darhol `POST /v1/card/void` (`original_attempt_id`), `CARD_AMOUNT_MISMATCH`, to'lov qabul qilinmaydi (`card.void.auto`);
   - `declined` → `CARD_DECLINED` (`decline_message`), boshqa usul yoki **yangi** `attempt_id` bilan qayta urinish;
   - `504`/aloqa uzildi → `unknown` (`CARD_TERMINAL_TIMEOUT`) → 16a.4.
4. Fiskal chek (`POST /v1/fiscal/sale` yoki hamkor bulut) — `payment_form='card'` (aralashda `mixed`), `card_type`, `card_mask`, `rrn` avtomatik.
5. `sale.created` — `payments[i] = {method:"card", amount, card_entry_mode:"integrated", card_result, card_type, card_type_source}` (§4.1); online bo'lsa lokal yozuv `POST /card-terminal-transactions` bilan ham yuboriladi (idempotent).

**Karta tasdiqlangan, fiskal chek chiqmadi**: sotuv "to'lov qabul qilingan, chek kutilmoqda" holatida qoladi (savat saqlanadi), fiskal qayta urinish §4.10 qoidalari bo'yicha. Kassir sotuvni bekor qilsa — **avtomatik `void`** (`POST /v1/card/void {attempt_id: <yangi>, local_id, amount_tiyin, original_attempt_id}`; settlement o'tgan bo'lsa — `refund`), `card.void.auto`; muvaffaqiyatsiz bo'lsa — `CARD_VOID_FAILED` (`card.void.failed`), sotuv bekor qilinmaydi, BO-14 va Egasiga M18; urinishlar `POST /card-terminal-transactions` (yoki keyingi sinxron) bilan serverga yetadi — bog'lanmagan `approved` urinish 24 soatdan keyin `sync_exceptions(kind='card_orphan_transaction')` — qo'lda ko'rib chiqiladi, avtomatik `void` qilinmaydi. Avtomatik `void` faqat ikki holatda: kassir shu sotuvni bekor qilganda va `CARD_AMOUNT_MISMATCH`da.

**Android (`android_intent`/`softpos`)** — xuddi shu ketma-ketlik, 2-qadam vendor ilova/SDK chaqiruvi (`28-android-pos.md`). **Bulut adapteri (`cloud`)** — 2-qadam o'rniga §16a.3 (natijasiz) + §16a.4 poll.

**Qarz to'lovi** (`debt_payment.created`) — aynan shu ketma-ketlik (`client_event_id` = qarz to'lovi voqeasi). **Qaytarish** (`return.created`, `refund_card`) — `POST /v1/card/refund {attempt_id, local_id, amount_tiyin, original_attempt_id | original_rrn}` (asl xarid shu kunniki va settlement'gacha — `void`), keyin qaytarish cheki, keyin voqea (§7.1); `card.refund`.

### 16a.3 `POST /api/v1/card-terminal-transactions`

**Maqsad**: (a) lokal adapter (agent/Android) natijasini serverga yozish — tanada `result`; (b) **bulut adapteri**da xaridni boshlash — `result`siz, server `CloudTerminalAdapter.purchase()` chaqiradi.
**Ruxsat**: `kind=purchase` — `sales.create` yoki `debts.payment.accept`; `refund` — `returns.create`; `void` — `sales.void` yoki `returns.create`; `result.resolved_by=manager` — qo'shimcha `card_manual_approval` (tasdiq turi `card_manual_entry`, tasdiqlovchida `card.manual_entry.approve`).
**Idempotentlik**: `id` (= `attempt_id`) bo'yicha upsert — `Idempotency-Key` talab qilinmaydi. Holat faqat oldinga o'tadi (`pending` → `approved`/`declined`/`unknown`; `unknown` → `approved`/`declined`; `approved` → `voided` — mos `void` urinishi `approved` bo'lganda server o'zi qo'yadi); yakuniy holat boshqa yakuniy holatga almashtirilmaydi — farq bo'lsa `409 CARD_TRANSACTION_MISMATCH` + `sync_exceptions(kind='card_result_mismatch')`.

**So'rov**:

| Maydon | Tur | Majburiy | Validatsiya |
|---|---|---|---|
| `id` | UUIDv7 | ha | `attempt_id` |
| `card_terminal_id` | UUID | ha | Faol terminal, foydalanuvchi filiali |
| `cash_register_id`, `shift_id` | UUID\|null | yo'q | POS'da — majburiy (`shift_id` ochiq) |
| `kind` | enum | ha | `purchase`/`refund`/`void` |
| `original_transaction_id` | UUID\|null | shartli | `void`da majburiy; `refund`da asl xarid ma'lum bo'lsa |
| `amount` | Money | ha | > 0; `void` = asl summa |
| `client_event_id` | UUID\|null | yo'q | Bog'lanadigan `sale.created`/`return.created`/`debt_payment.created` voqeasi |
| `requested_at` | ISO vaqt | ha | Qurilma soati |
| `status` | enum\|null | shartli | `result` yo'q va adapter lokal bo'lsa — `pending` |
| `result` | `CardResult`\|null | shartli | Lokal adapter yakuniy/`unknown` natijasi (§2.7); bulut adapteri boshlashda — `null` |
| `card_manual_approval` | `ApprovalRef`\|null | shartli | `result.resolved_by=manager` bo'lsa majburiy |

**Javob**: `201`/`200` — `{id, status, kind, amount, approval_code, rrn, card_mask, card_scheme, card_type, card_type_source, tid, doc_type, doc_id, resolved_by, updated_at}`; bulut adapteri boshlashda `202 {id, status:"pending"}`.
**Xatolar**: `CARD_TERMINAL_UNREACHABLE` (503, bulut — vendor API ishlamaydi), `CARD_TERMINAL_BUSY` (409, shu terminalda boshqa `pending` — `uq_ctt_one_pending`), `CARD_OUTCOME_UNKNOWN` (409, shu terminalda hal qilinmagan `unknown` bor, yangi `purchase` bloklanadi), `CARD_TRANSACTION_MISMATCH` (409), `NOT_FOUND`, `VALIDATION_ERROR`, `PERMISSION_DENIED`.
**Offline**: chaqirilmaydi — natija voqea ichida (`16-offline-sync.md` §2.1).

### 16a.4 `GET /api/v1/card-terminal-transactions/{id}` va `unknown`ni hal qilish

**Ruxsat**: `sales.create` / `returns.create` / `debts.payment.accept` (biri).
**Javob**: §16a.3 javobi bilan bir xil. Bulut adapterida POS har 2 s (standart, sozlanadi) poll qiladi; server `pending`da vendor holatini o'zi so'raydi.

**`unknown` tartibi** (`purchase` **hech qachon avtomatik takrorlanmaydi**):
1. POS darhol `GET /v1/card/tx/{attempt_id}` (agent: jurnal → terminal `get_status` → `get_last_transaction`), bulutda — shu endpoint; `get_status`/`health` xavfsiz, 3 marta, 2 s oraliq.
2. Natija `approved`/`declined` → `resolved_by=status_query`, oqim davom etadi (16a.2, 3-qadam).
3. Hal bo'lmasa — shu terminalda va shu chekda yangi `purchase` bloklanadi (`CARD_OUTCOME_UNKNOWN`), POS: "Terminal chekini tekshiring". Terminal chekida tasdiq bor bo'lsa — Menejer/Egasi PIN (`card_manual_entry`, `card.manual_entry.approve`) bilan `resolved_by=manager`, `status=approved`, rekvizitlar terminal chekidan (`card.outcome.resolved_manual`); tasdiq yo'q bo'lsa — `declined` (`decline_code='not_found'`), keyin yangi urinish yoki boshqa usul. Hal qilinmagan urinish bilan smena yopilmaydi (§3.2).

### 16a.5 `GET /api/v1/card-terminals` · `POST /api/v1/card-terminals` · `PATCH /api/v1/card-terminals/{id}`

**Maqsad**: karta terminallari reyestri (BO-12 «Kassalar» — terminal bog'lash; POS-16 — agent topgan terminallarni ko'rish/sinash).
**Ruxsat**: `GET` — `cash_register.manage` yoki `sales.create` (o'z kassasi); `POST`/`PATCH` — `cash_register.manage`.
**`GET`** `?branch_id=&cash_register_id=&status=&page=&size=` → `{items: [CardTerminal], total, page, size}` (page pagination — ma'lumotnoma).
**`CardTerminal`**: `{id, branch_id, cash_register_id, name, vendor, model, adapter, driver, agent_id, local_id, host, port, vendor_terminal_ref, tid, mid, acquirer_counterparty_id, status, is_default, capabilities, health_status, health_checked_at, version}` — `card_terminals` ustunlari (`12-db-sxema.md`).
**`POST`** tanasi — `CardTerminal` (`id`, `health_*`, `capabilities`, `version`siz); qoidalar: `adapter=agent_ecr` — `agent_id`, `local_id`, `host` majburiy (`local_id` agent `capabilities.card_terminal.devices[]`da bo'lishi, `host` — RFC 1918 xususiy IPv4); `adapter=cloud` — `vendor_terminal_ref` majburiy, vendor kredensiali `tenant_secrets(kind='card_terminal_vendor')`da; `adapter=fake` — faqat dev/test/staging va demo-tenant (prod'da `VALIDATION_ERROR`); faol real terminalda `tid` majburiy va tenantda yagona; `is_default=true` — `cash_register_id` majburiy, shu kassadagi oldingi standart avtomatik `false`.
**`PATCH`** — `version` majburiy (`409 VERSION_CONFLICT`); `status` `active`/`disabled`/`archived` (arxivlangan terminal tahrirlanmaydi); hal qilinmagan (`pending`/`unknown`) urinishi bor terminal `disabled`/`archived` qilinmaydi — `CARD_OUTCOME_UNKNOWN`.
**Idempotentlik**: `POST` — `Idempotency-Key` majburiy. **Audit**: `card_terminal.created` / `card_terminal.updated` / `card_terminal.archived`.
**Xatolar**: `VALIDATION_ERROR`, `VERSION_CONFLICT`, `CARD_OUTCOME_UNKNOWN`, `NOT_FOUND`, `PERMISSION_DENIED`.

### 16a.6 `POST /api/v1/card-terminal-settlements`

**Maqsad**: smena yopilishida terminal settlement'i («сверка итогов») natijasini yozish — POS agent orqali (`POST /v1/card/settlement {local_id}`) bajaradi; POS yopiq bo'lsa server agent vazifasini (`card.settlement`) navbatga qo'yadi va natijani agent API orqali o'zi yozadi.
**Ruxsat**: `shift.close`.
**So'rov**: `{id (UUIDv7, qurilma beradi), card_terminal_id, shift_id, batch_no, business_date, settled_at, purchase_count, purchase_total, refund_count, refund_total, terminal_response}` (pul — Money; `SettlementResult.total_tiyin` va `by_scheme[]` adapterda xaritalanadi).
**Server**: `expected_count`/`expected_total`ni shu terminalning `approved` `purchase`/`refund` urinishlaridan hisoblaydi (partiyaga — `settlement_id` yozadi), `status` — `matched` / `mismatch` (farq → `card.settlement.mismatch`, BO-14, Egasiga M18) / `failed` (terminal settlement'ni bajarmadi); bank ko'chirmasi bilan moslashtirish — `13-provodka-qoidalari.md` §2.18a, `20-api-moliya-admin.md` (BO-24).
**Javob**: `201 {id, status, net_total, expected_total, variance}`. **Idempotentlik**: `id` (takror — saqlangan natija). Offline — `shift.closed.card_settlements[]` (§3.2).
**Xatolar**: `VALIDATION_ERROR`, `SHIFT_NOT_OPEN` (smena allaqachon boshqa qurilmada yopilgan bo'lsa ham qabul qilinadi — faqat `shift_id` mavjudligi tekshiriladi), `NOT_FOUND`.

### 16a.7 Offline

Agent/Android zanjiri do'kon internetisiz ishlaydi (terminal bankka o'z kanali bilan chiqadi) — integratsiyalangan karta offline'da **ruxsat**; natija voqea ichida (`card_result`), server sinxronda `card_terminal_transactions`ni upsert qiladi. Bulut adapteri — faqat online. `unknown` offline'da ham bloklaydi. To'liq qoidalar — `16-offline-sync.md` §2.1.

---

## 17. POS bootstrap / `/sync/pull` — qisqa konspekt

To'liq protokol — `16-offline-sync.md` §1–3 (bu fayl **qaytarib yozmaydi**, faqat kassa katalogi nuqtai nazaridan eslatma):

- Qurilma birinchi login'da `devices` yozuvi avtomatik yaratiladi (`16-offline-sync.md` §9).
- `GET /api/v1/sync/pull?scope=catalog,prices,customers,permissions,limits,settings&cursor=&page_size=500` — kassaga kerakli hamma narsa: katalog+narx (M09), mijoz+qarz balansi (`counterparties`+`debt_balances`), huquq/limit (`role_permissions`), do'kon sozlamalari (`discount_rules`, obuna holati).
- `POST /api/v1/sync/push` — §1dagi barcha voqealar shu yagona endpoint orqali, partiyali (≤ 100 voqea/so'rov, standart, sozlanadi — qaror #54), `seq` tartibida; so'rov tanasi — §2.6 `SyncPushRequest` (`outbox_state` majburiy, onlayn qurilma outbox bo'sh bo'lsa ham davriy `events: []` push yuboradi).
- Backpressure, idempotentlik, 401/CSRF xatti-harakati, ko'p-tab xavfsizligi — to'liq `16-offline-sync.md` §3.

---

## 18. Ishlatilgan xato kodlari

`17-api-umumiy.md` §15 — yagona manba; bu jadval faqat shu faylda qaysi kod qayerda ishlatilganini ko'rsatadi.

| Kod | Qayerda | Izoh |
|---|---|---|
| `VALIDATION_ERROR` | Deyarli hamma yerda | Sxema/biznes qoida xatosi, 422; §12.2 qarzdan ortiq to'lov (faqat online/REST) — `message_key=debt_payment_exceeds_balance` (qaror #45); §12.3 `method ≠ bank` — `validation.debt_payment_backoffice_bank_only` |
| `VERSION_CONFLICT` | §8.2, §11.4, §10 | Optimistik qulflash, 409 |
| `SHIFT_NOT_OPEN` | §3.2, §4.6, §13.1 | Smena `open` emas |
| `SHIFT_DEVICE_MISMATCH` | §3.1, §3.2, §4.6 | Boshqa qurilmadan voqea |
| `SHIFT_ALREADY_OPEN` | §3.1 | — |
| `RECEIPT_SEQ_CONFLICT` | §4.6, §7.1, §12.2 | `receipt_seq` takrori, `retryable:false`; voqeada `fiscal_result` bo'lsa rad etilmaydi — qayta raqamlanadi (§4.6) |
| `STOCK_NEGATIVE` | §4.6, §4.7 | Ogohlantirish, sotuvni bloklamaydi |
| `DISCOUNT_LIMIT_EXCEEDED` | §4.4, §4.6 | Chegirma foizi limitdan katta, `ApprovalRef` yo'q |
| `DEBT_LIMIT_EXCEEDED` | §4.3, §4.6 | Online rejimda kredit limiti oshgan, `ApprovalRef` yo'q |
| `RETURN_LIMIT_EXCEEDED` | §7.1 | Qaytarish summasi limitdan katta, `approval` yo'q |
| `RETURN_QTY_EXCEEDED` | §7.1 | Qaytarilayotgan miqdor asl sotilgan miqdordan katta |
| `CASH_WITHDRAW_LIMIT_EXCEEDED` | §13.1, §13.2 | Pul olish / naqd xarajat summasi limitdan katta |
| `PRICE_CHANGE_LIMIT_EXCEEDED` | §10 | Narx o'zgarishi foizi limitdan katta |
| `APPROVAL_INVALID` | §2.4, §4, §7, §9, §13 | `ApprovalRef` kutilgan, kelmagan yoki tasdiqlovchi huquqi/limiti yetarli emas |
| `PIN_INVALID` | §9.4 | Noto'g'ri PIN bilan `approve` |
| `APPROVAL_REQUIRED` | §7.1, §10 | Muddati o'tgan tovar qaytarilmoqda, `actor`da `returns.approve` va `approval` yo'q (qaror #48); narx o'zgarishi limitdan katta — `202 {status:"pending_approval"}` (§10) |
| `FISCAL_OFFLINE_48H_BLOCKED` | §4.6, §4.10, §7.1, §12.2 | 409 — kassadagi OFD tasdig'ini olmagan eng eski chek ≥ 48 soat; yangi fiskal chek yo'q, faqat sinxron/yuborish (qaror #43) |
| `FISCAL_DEVICE_LOCKED` | §4.6, §4.10, §7.1, §12.2 | 409 — `cash_registers.fm_state ≠ 'ok'` |
| `MARKING_CODE_INVALID` | §4.2, §15 | Kod formati noto'g'ri / o'qilmadi |
| `MARKING_CODE_ALREADY_SOLD` | §4.2, §15 | Kod tenantda allaqachon sotilgan (lokal takror-kod tekshiruvi) |
| `MARKING_PRECHECK_WARNING` | §4.2, §15 | 200, `warnings[]` — `MARKING_PRECHECK=warn`da tekshiruv o'tmadi/CRPT javob bermadi, sotuv davom etadi, audit (qaror #62) |
| `MARKING_VERIFY_FAILED` | §4.2, §15 | 409 — faqat `MARKING_PRECHECK=block`: CRPT kodni rad etdi |
| `MARKING_RETURN_REQUIRES_ONLINE` | §7.1 | Markirovkalangan tovar qaytarishi faqat online |
| `MARKING_PRICE_UNKNOWN_OFFLINE` | §4.2, §4.6 | Offline, narx qurilmada noma'lum — sotuv taqiq |
| `MARKING_VERIFY_UNAVAILABLE` | §4.2, §15 | 503 — faqat `MARKING_PRECHECK=block`: CRPT Turon javob bermadi (timeout 3 s) |
| `SALE_NOT_FOUND` | §7.1 | Qaytarish uchun asl chek topilmadi, `retryable:true` |
| `APPROVAL_REQUEST_ALREADY_RESOLVED` | §2.4, §9.4, §9.5 | 409 — so'rov allaqachon hal qilingan yoki hujjatda ishlatilgan (`consumed`) |
| `APPROVAL_REQUEST_EXPIRED` | §9.4 | `expires_at` o'tgan |
| `SUBSCRIPTION_RESTRICTED` | §4.6 va deyarli barcha yozuvchi amallar | Obuna lokauti (`14-autentifikatsiya-oauth2.md` §16) |
| `CSRF_INVALID` | Barcha cookie-autentifikatsiyali yozuvchi so'rovlar | §0 |
| `IDEMPOTENCY_IN_PROGRESS` / `IDEMPOTENCY_KEY_REUSED` | Barcha back-office REST yozuvchi so'rovlar | `23-backend-arxitekturasi.md` §3 |
| `PERIOD_CLOSED` | Faqat back-office REST (§12.3–§12.5 yaratish/`post`, `doc_date` yopilgan davrda); POS sync voqealari rad etilmaydi (`16-offline-sync.md` §3.4, qaror #69); `cancel` da ishlatilmaydi (§12.5a) | `13-provodka-qoidalari.md` §5.1 |
| `PAYMENT_PROVIDER_ERROR` | §16.2–16.4 | 502 — tashqi to'lov tizimi xatosi |
| `CARD_TERMINAL_UNREACHABLE` | §16a.1, §16a.3 | 503 — terminal/agent ulanmagan yoki bulut vendor API ishlamaydi; zaxira siyosati (qaror #71) |
| `CARD_TERMINAL_BUSY` | §16a.1, §16a.3 | 409 — shu terminalda boshqa `pending` urinish |
| `CARD_TERMINAL_TIMEOUT` | §16a.2 | 504 (agent) — urinish `unknown`, holat so'rovi |
| `CARD_DECLINED` | §16a.2 | 200 `status:"declined"` — rad etildi, boshqa usul yoki yangi `attempt_id` |
| `CARD_OUTCOME_UNKNOWN` | §3.2, §16a.3, §16a.4, §16a.5 | 409 — hal qilinmagan `unknown` urinish: yangi `purchase`, smena yopish va terminalni o'chirish bloklanadi |
| `CARD_AMOUNT_MISMATCH` | §16a.2 | 422 — terminal summasi ≠ chek summasi, avtomatik `void` |
| `CARD_MANUAL_NOT_ALLOWED` | §4.1, §4.6, §7.1, §12.2, §16a.1 | 403 — `card_manual_fallback=forbid` |
| `CARD_MANUAL_APPROVAL_REQUIRED` | §4.1, §4.6, §7.1, §12.2, §16a.1 | 403 — `manager_approval` siyosatida `card_manual_approval` yo'q (online) |
| `CARD_VOID_FAILED` | §16a.2 | 502 — avtomatik `void`/`refund` bajarilmadi, BO-14 + M18 |
| `CARD_TRANSACTION_MISMATCH` | §4.1, §4.6, §7.1, §12.2, §16a.3 | Voqeada — `warnings[]` + `sync_exceptions(kind='card_result_mismatch')`; §16a.3 da — 409 |
| `PAYMENT_NOT_CONFIRMED` | §4.6, §12.2 | Checkout `confirmed` emas yoki allaqachon `consumed` (§16.1) |
| `DEPENDENCY_NOT_SYNCED` | §4.6, §7.1, §12.2 | `retryable:true` — bog'liq voqea hali qabul qilinmagan |
| `DEBT_ALREADY_PAID` | §12.5 | 409 — mijozning ochiq qarzi 0 |
| `DOUBTFUL_FLAG_REQUIRES_OWNER` | §12.6 | 403 — faqat Egasi |
| `DOC_INVALID_STATE` | §12.5a | 409 — hujjat bekor qilish uchun mos holatda emas |
| `DEVICE_REVOKED` | Barcha sync/REST (403) | `16-offline-sync.md` §9 |
| `NOT_FOUND` | §11, §12 va umumiy | `params.resource` bilan |
| `PERMISSION_DENIED` | Umumiy | — |

---

## Ochiq savollar

1. **Tashqi javob kerak** — qarzga sotuv paytida "kredit" turidagi chek (VMQ-943 1-ilova 7-band) majburiymi va qarz to'lovi cheki OFD'ga qaysi chek turi kodi bilan ketadi, fiskal hamkor / OFD operatori (Xat 1) — interim: `FiscalPolicy.credit_sale_receipt='none'` (sotuvda chek yo'q, `fiscal.status="deferred"`), qarz to'lovida `debt_settlement` cheki; `credit_type` rejimi bayroq ortida tayyor (§4.5, §12.2) — 26 #9 (OQ-002).
2. **Tashqi javob kerak** — dinamik UzQR POS API texnik spetsifikatsiyasi (checkout yaratish, tasdiq webhook/poll, qaytarish), CBU MUNIS yoki tenantning ekvayer banki — interim: statik UzQR qo'lda tasdiq bilan, dinamik — `UzqrPort` stub (§16) — 26 #49 (OQ-032).
3. **Tashqi javob kerak** — sotuvdan oldingi onlayn kod tekshiruvi majburiymi, chekdagi `label` formati va `verify` metodi, CRPT Turon (Xat 2) — interim: `MARKING_PRECHECK=warn` + lokal takror-kod tekshiruvi, kod fiskal chek bilan OFD'ga (§4.2, §15) — 26 #40 (OQ-025).
4. **Tashqi javob kerak** — fiskal modul/virtual kassa holat kodlari va bloklanish (OFD bloki, 48 soat tasdiqlanmagan chek) qanday bildirilishi (webhook yoki polling), fiskal hamkor — interim: `cash_registers.fm_state` (`ok`/`locked`/`ack_overdue`/`memory_full`/`unknown`), hamkor kodlari adapterda xaritalanadi, `fm_state ≠ ok` → `FISCAL_DEVICE_LOCKED` (§4.10) — 26 #89 (OQ-008).

## Manbalar

- `spec/kod-uchun/11-malumotlar-modeli.md`, `13-provodka-qoidalari.md`, `21-integratsiyalar.md` (§1, §4, §9), `16-offline-sync.md`, `15-xavfsizlik-va-audit.md`, `23-backend-arxitekturasi.md`.
- `spec/kod-uchun/03-modullar-talablari.md` — M01, M02, M03, M08, M16.
- `spec/kod-uchun/04-biznes-jarayonlar.md` — BP-03, BP-11, BP-12.
- `spec/kod-uchun/06-ekranlar-umumiy.md` — POS-01…16, BO-06, BO-16.
- `spec/kod-uchun/01-qarorlar.md` — standart limitlar, offline siyosat qarorlari; #12, #23, #25, #26, #30, #42, #43, #45, #46, #48, #54, #59, #60, #62, #64, #67, #68, #69.
- `spec/kod-uchun/26-ochiq-savollar-reestri.md` — #87, #9, #40, #49, #89.
- `research_notes/ochiq-savollar/` — P1 (OQ-002, OQ-004), P2 (OQ-026), P3 (OQ-032, OQ-033, §7.2), D-qarorlar.

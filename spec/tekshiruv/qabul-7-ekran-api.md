# Qabul-7 — Ekranlar (09) ↔ API katalogi (13-*) ↔ huquqlar (05) ↔ qarorlar

*Qabul agenti (Opus) · 2026-10-15 · Tekshirilgan: `01-mahsulot/08-dizayn-tizimi.md`, `09-ekran-tafsilotlari.md` (37 ekran), `02-modullar-talablari.md`, `04-ekranlar-va-ux.md`, `05-ai-funksiyalar.md`, `06-mvp-chegarasi.md`; `02-arxitektura/13-api-katalog-0…3`, `05-xavfsizlik-va-audit.md`, `08-frontend-arxitekturasi.md`, `12-autentifikatsiya-oauth2.md`, `14-db-sxema.md` (faqat `debt_moves`), `15-ochiq-savollar-reestri.md`; `tekshiruv/00-qarorlar.md`, `savollar-yakuniy-tavsiyalar.md`. Bu fayl — yagona chiqish; manba fayllar tahrirlanmadi.*

**Daraja:** **K** — kritik (kodlashni bloklaydi yoki qaror/qonunni buzadi) · **Y** — yuqori (Must hikoya qoplanmagan yoki ikki hujjat ziddiyatli) · **O** — o'rta · **P** — past.

## Xulosa

| Daraja | Soni |
|---|---|
| K | 7 |
| Y | 28 |
| O | 40 |
| P | 7 |
| **Jami** | **82** |

**Hukm: 09 + 13-* hozircha "kodlashga tayyor" EMAS** — 7 ta K bandi yopilgach (taxminan bir kunlik tahrir) tayyor bo'ladi. Asosiy sabablar: (1) 09'dagi endpoint havolalarining **40 dan ortig'i** katalogdagi nomga mos emas yoki katalogda umuman yo'q (7 tasi — katalogda butunlay yo'q: `GET /sales`, chiquvchi e-faktura ×2, tenant sozlamalari ×3, signup); (2) 09'dagi **26 ta ruxsat kodi** 05'da yo'q; (3) 13-1/13-2/13-3 o'zaro 5 joyda bir resursni ikki xil loyihalagan (OCR, narx tasdig'i, qarz eskirishi, kassa harakati, ko'chirish voqealari); (4) 6 ta Must hikoya (US-M05-02/03, US-M08-02, US-M08-11, US-M11-02, US-M10-02 yuklash qadami) ekranda amalsiz qolgan; (5) pulni ko'rsatish/hisoblash qoidasi dizayn tizimi, frontend arxitekturasi va API o'rtasida ziddiyatli.

---

# 1. `spec/01-mahsulot/09-ekran-tafsilotlari.md`

### E-01 · K · Endpoint nomlari katalogga moslashtirilsin (vazifa №1)

"Qanday o'qish kerak" bo'limidagi "nomlar yakuniy emas" eslatmasi **olib tashlansin** va har ekranning "Ma'lumot manbai" qatori quyidagi jadval bo'yicha almashtirilsin. Barcha REST yo'llar `/api/v1` ostida; `/auth/*`, `/billing/pay`, `/billing/export-my-data` — `/api/v1`siz (12-auth §20).

| Ekran | 09'da yozilgan | Almashtirish (katalog) | Manba |
|---|---|---|---|
| POS-01 | `POST /api/v1/auth/pin/verify` | `POST /auth/pin/verify` | 12-auth §20 |
| POS-02 | `GET /api/v1/products?query=` | `GET /api/v1/products?search=` | 13-2 §1 |
| POS-02 | — (yo'q) | **qo'shilsin**: `POST /api/v1/marking/verify` (online skanerda, `sale.created`dan oldin); event `counterparty.created` ("+ Mijoz") | 13-1 §15, §11.1 |
| POS-03 | provayder "webhook/Prepare-Complete" | `POST /api/v1/payments/{provider}/checkout` → poll `GET /api/v1/payments/{provider}/{provider_tx_id}` (webhook — server tomoni, ekran chaqirmaydi) | 13-1 §16 |
| POS-04 | `fiscal_receipts`, `outbox_jobs(ofd_send)` | `GET /api/v1/fiscal-receipts?sale_id=` (online), lokal Dexie (offline); event `receipt.reprinted` | 13-1 §6, §14 |
| POS-05 | `GET /api/v1/sales?receipt_no=` | `GET /api/v1/sales?number=` — **katalogda yo'q, K1-01 bilan qo'shiladi** | 13-1 |
| POS-06 | "einvoices avtomatik loyiha" | `POST /api/v1/einvoices` (direction=out) — **katalogda yo'q, K1-04** | — |
| POS-07 | `GET /api/v1/shifts/{id}/summary` | `GET /api/v1/shifts/{id}` (+ `running_totals`, K1-02); yopilgandan keyin `GET /api/v1/shifts/{id}/z-report` | 13-1 §3.3 |
| POS-08 | outbox `purchase.received` | **Voqea yo'q.** `GET /api/v1/purchase-orders/{id}` → `POST /api/v1/goods-receipts` (`po_id` bilan) → `PATCH /api/v1/goods-receipts/{id}` → `POST /api/v1/goods-receipts/{id}/post` (online, E-13) | 13-2 §8 |
| POS-09 | `GET /api/v1/stock/balances?branch=` | `GET /api/v1/stock-balances?warehouse_id=`; offline — event `transfer.created`/`transfer.received` (payload K1-03), online — `POST /api/v1/transfers` → `/send`, `POST /api/v1/transfers/{id}/receive` | 13-2 §7, §13 |
| POS-10 | `GET /api/v1/stock/count-sheets/{id}` | `GET /api/v1/stock-counts/{id}`; offline — event `stock_count.line_recorded` (payload K1-03), online — `POST /api/v1/stock-counts/{id}/lines`; "SANASHNI YAKUNLASH" → `POST /api/v1/stock-counts/{id}/submit-for-review` | 13-2 §14 |
| POS-12 | `/sync/push` | `POST /api/v1/sync/push` | 04-offline §3 |
| POS-13 | lokal + outbox | lokal + online `GET /api/v1/counterparties/{id}/debt-ledger`; event `debt_payment.created` | 13-1 §12 |
| POS-15 | `GET /api/v1/shifts/{id}/expected-cash` | **Yo'q** → lokal hisob + online `GET /api/v1/shifts/{id}` → `running_totals.expected_cash` (K1-02) | — |
| POS-15 | outbox `cash_count.recorded` | **Voqea yo'q** → `counted_cash`/`variance_note` `shift.closed` payload'ida yuboriladi (E-11) | 13-1 §3.2 |
| BO-02 | `?period=&branch=` | `GET /api/v1/reports/dashboard?period=today\|week\|month&branch_id=` | 13-3 #17 |
| BO-03 | `GET /api/v1/stock/balances?branch=` | `GET /api/v1/stock-balances?warehouse_id=&low_stock=&search=`; "Barchasi" filial — `GET /api/v1/reports/stock?branch_id=` (bo'sh = konsolidatsiya); `GET /api/v1/transfers?status=` ✓ | 13-2 §7, 13-3 #20 |
| BO-03 | Eksport | `POST /api/v1/reports/stock/export` → `GET /api/v1/reports/export-jobs/{job_id}` | 13-3 #22–23 |
| BO-04 | `POST /api/v1/ai/ocr-document` | `POST /api/v1/attachments` → `POST /api/v1/ai/ocr/jobs` (`doc_type_hint=purchase`) → poll `GET /api/v1/ai/ocr/jobs/{job_id}` → `POST /api/v1/ai/ocr/jobs/{job_id}/confirm` (K2-01 unifikatsiyasidan keyin) | 13-3 #73–75 |
| BO-04 | `POST /api/v1/suppliers/{id}/payments` | `POST /api/v1/supplier-payments` | 13-2 §11 |
| BO-04 | `GET/POST /purchase-orders` | ✓ + `POST /api/v1/purchase-orders/{id}/send`; qo'shilsin: `GET /api/v1/suppliers`, `GET /api/v1/suppliers/{id}/debt-balance`, `GET /api/v1/goods-receipts`, `POST /api/v1/goods-receipts/{id}/post` | 13-2 §8–10 |
| BO-04 | `POST /api/v1/supplier-returns` | ✓ + `POST /api/v1/supplier-returns/{id}/post` | 13-2 §12 |
| BO-05 | `GET/PATCH /api/v1/products/{id}/price` | `GET /api/v1/products/{id}/prices` (tarix) + `POST /api/v1/price-changes` → `POST /api/v1/price-changes/{id}/post` (javob `posted` yoki `pending_approval`) | 13-2 §4 |
| BO-05 | `GET/POST /discount-rules` | ✓ (+ `PATCH /{id}`, `POST /{id}/archive`) | 13-1 §8.2 |
| BO-06 | `GET /api/v1/debts?overdue=` | `GET /api/v1/reports/debts-aging?direction=receivable&bucket=` (K1-05 birlashtirilgandan keyin) | 13-3 #21 |
| BO-06 | `POST /api/v1/ai/debt-reminder` | `POST /api/v1/ai/debt-reminders/draft` → (odam tahrirlaydi) → `POST /api/v1/ai/debt-reminders/send` | 13-3 #77–78 |
| BO-06 | `POST /api/v1/debts/{id}/payments` | `POST /api/v1/debt-payments` → `POST /api/v1/debt-payments/{id}/post` | 13-1 §12.3 |
| BO-06 | `POST /api/v1/debts/{id}/write-off` | `POST /api/v1/debt-writeoffs` → `POST /api/v1/debt-writeoffs/{id}/post` | 13-1 §12.5 |
| BO-06 | — | qo'shilsin: `POST /api/v1/debt-doubtful-flags`, `POST /api/v1/debt-doubtful-flags/{id}/unflag`, `GET /api/v1/counterparties/{id}/debt-ledger`, `PATCH /api/v1/counterparties/{id}` | 13-1 §11–12 |
| BO-07 | `GET /api/v1/tax/vat-summary?period=` | `GET /api/v1/vat/summary?period=YYYY-MM` (+ `GET /api/v1/vat/moves`) | 13-3 #1–2 |
| BO-08 | `GET /api/v1/accounting/ledger-entries?from=&to=&account=` | `GET /api/v1/ledger-entries?doc_date__gte=&doc_date__lte=&account_dt=&account_kt=` | 13-3 #9 |
| BO-09 | `GET /api/v1/reports/{type}?from=&to=` | Hisobotga qarab: `sales`/`top-products` — `?date_from=&date_to=`; `trial-balance`/`profit-and-loss` — `?period=`; `balance-sheet`/`debts-aging` — `?as_of=`; eksport `POST /api/v1/reports/{report-kod}/export` + poll `GET /api/v1/reports/export-jobs/{job_id}` | 13-3 #11–23 |
| BO-10 | `GET /api/v1/tax/reconciliation?type=&period=` | `GET /api/v1/state-reports?tax_type=&period=` + `GET /api/v1/state-reports/{id}` + `GET /api/v1/state-reports/{id}/diffs` | 13-3 #5–7 |
| BO-10 | `POST /api/v1/tax/reconciliation/{id}/correction` | `POST /api/v1/state-reports/{id}/correction` | 13-3 #8 |
| BO-10 | — | qo'shilsin: `POST /api/v1/state-reports` (fayl yuklash), `POST /api/v1/state-reports/{id}/compare`, `POST /api/v1/ai/vat-diffs/{diff_id}/explain` | 13-3 #3–4, #76 |
| BO-11 | `/api/v1/admin/users…` | `/api/v1/admin/users…` ✓; qo'shilsin: `GET /api/v1/roles`, `GET/PUT /api/v1/roles/{id}/permissions`, `GET /api/v1/permissions-catalog` | 12-auth §18.2, 13-3 #24–29 |
| BO-12 | `GET/POST/PATCH /branches` | ✓ + `GET/POST /api/v1/cash-registers`, `PATCH /api/v1/cash-registers/{id}`, `GET /api/v1/branches/{id}/tax-settings` | 13-3 #30–40 |
| BO-14 | `GET/PATCH /tenant/settings`, `POST /tenant/integrations/crpt`, `POST /tenant/integrations/faktura-uz` | **Katalogda yo'q** — K3-01 bilan qo'shiladi; zaxira usuli — `GET/PATCH /api/v1/valuation-settings`; OFD — `GET /api/v1/fiscal-receipts?status=failed` + `POST /api/v1/fiscal-receipts/{id}/retry` | 13-2 §17, 13-1 §14 |
| BO-15 | `GET /einvoices?direction=in\|out` | `in` — ✓; `out` — **yo'q, K1-04** | 13-2 §19 |
| BO-15 | `POST /api/v1/einvoices/{id}/sign` | `POST /api/v1/einvoices/{id}/sign-challenge` → E-IMZO → `POST /api/v1/einvoices/{id}/submit-signed` | 13-2 §19 |
| BO-15 | "Qabul qilish"/"Rad etish" | `POST /api/v1/einvoices/{id}/accept` / `POST /api/v1/einvoices/{id}/reject` | 13-2 §19 |
| BO-15 | `POST /api/v1/einvoices/from-receipt` | **yo'q, K1-04** | — |
| BO-16 | `/api/v1/approvals…` | `GET /api/v1/approval-requests?status=pending`, `POST /api/v1/approval-requests/{id}/approve` (`{pin}`), `POST /api/v1/approval-requests/{id}/reject` (`{reason}`) | 13-1 §9 |
| BO-17 | `GET/POST /expenses/recurring` | `GET/POST /api/v1/recurring-expenses`, `PATCH /{id}`, `POST /api/v1/recurring-expenses/{id}/confirm` | 13-3 #48–51 |
| BO-17 | `GET/POST /expenses` | ✓ + `POST /api/v1/expenses/{id}/post`, `POST /api/v1/expenses/{id}/cancel`, `GET /api/v1/expense-categories`, `POST /api/v1/attachments` (foto) | 13-3 #41–47 |
| BO-18 | `GET /api/v1/products?label_pending=true` | `GET /api/v1/label-print-queue` | 13-2 §5 |
| BO-18 | `POST /api/v1/products/{id}/internal-barcode` | `POST /api/v1/products/{id}/barcodes/internal-generate` | 13-2 §1 |
| BO-18 | — | qo'shilsin: `GET /api/v1/label-templates`, `POST /api/v1/label-print-queue/mark-printed` | 13-2 §5 |
| BO-19 | `GET /api/v1/billing/ai-usage` | `GET /api/v1/ai/usage` | 13-3 #79 |
| BO-19 | "+ Qo'shimcha kassa" | `GET /api/v1/billing/addons`, `POST /api/v1/billing/addons` (`{addon_code:"extra_register", quantity}`), `DELETE /api/v1/billing/addons/extra_register`; + `GET /api/v1/billing/plan`, `GET /api/v1/billing/invoices/{payment_id}` | 13-3 #56–65 |
| BO-19 | `POST /billing/checkout` | ✓ — tana `{provider:"click"\|"payme", period:"month"\|"year"}` | 13-3 #61 |
| BO-20 | `POST /api/v1/telegram/link` | `POST /api/v1/notifications/telegram/link-start` (+ `GET /api/v1/notifications/telegram/status`, `DELETE /api/v1/notifications/telegram/link`) | 13-3 #66–68 |
| BO-20 | `GET/PATCH /api/v1/notifications/settings` | `GET/PATCH /api/v1/notification-settings` | 13-3 #69–70 |
| BO-21 | `POST /api/v1/onboarding/signup` | **yo'q** → `POST /auth/signup` (A-01) | — |
| BO-21 | `POST /api/v1/auth/otp/verify` | `POST /auth/otp/request` (`purpose=signup`) + `POST /auth/otp/verify` | 12-auth §20 |
| BO-21 | `POST /api/v1/onboarding/products/bulk` | Excel/CSV: `GET /api/v1/import-jobs/templates/products` → `POST /api/v1/import-jobs` (`kind=products`) → `/validate` → `/commit`; qo'lda: `POST /api/v1/products` (har qator) | 13-2 §1, §6 |
| BO-21 | `POST /api/v1/onboarding/debts/bulk` | `POST /api/v1/import-jobs` (`kind=opening_debts`) → `/validate` → `/commit`; qo'lda: `POST /api/v1/debt-openings` → `/post` | 13-2 §6, 13-1 §12.4 |
| BO-21 | `POST /api/v1/ai/ocr-document` | `POST /api/v1/attachments` → `POST /api/v1/ai/ocr/jobs` (`doc_type_hint=catalog` — K3-07) | 13-3 #73 |
| ADM-01 | `/platform/…` | ✓ hammasi mos (12-auth §18.1); `…/owner/sessions/{sid}/revoke` aniq yozilsin | — |

### E-02 · K · Ruxsat kodlari 05 katalogiga moslashtirilsin (vazifa №2)

"Qanday o'qish kerak" bo'limidagi "aniq kod nomlari loyihaviy taxmin" jumlasi **olib tashlansin**; quyidagi almashtirishlar qilinsin. "05+" — X-01 orqali 05'ga qo'shiladigan yangi kod.

| 09'dagi kod | Ekran(lar) | Almashtirish |
|---|---|---|
| `discount.apply` | POS-02 | `discount.give` |
| `discount.override` | POS-02 | `discount.approve` (tasdiqlovchi Menejer/Egasi PIN'i) |
| `sales.reprint` | POS-04 | `sales.create` (13-1 §6) — tugma yashirilmaydi, har chop audit |
| `prices.view` | POS-11 | `stock.view` |
| `sync.view` | POS-12 | `—` (ruxsat tekshiruvi yo'q, har autentifikatsiyalangan POS foydalanuvchisi) |
| `debts.view` | POS-13, BO-06 | POS: `debts.create` yoki `debts.payment.accept`; BO-06: `reports.finance.view` (eskirish) + `reports.sales.view` (daftar) |
| `debts.collect` | POS-13, BO-06 | `debts.payment.accept` |
| `debts.remind` | BO-06 | `debts.remind` (05+, yangi) — matn loyihasi uchun qo'shimcha `ai.chat.use` |
| `cash.movement` | POS-14 | `in` → `cash.deposit`, `out` → `cash.withdraw` (limit) |
| `cash.approve` | POS-14 | alohida kod yo'q — tasdiqlovchining `cash.withdraw` limiti summani qoplashi shart (13-1 §2.4) |
| `cash.count` | POS-15 | `cash.count.shift` |
| `stock.create` | POS-08 | `purchases.receive` |
| `stock.count` | POS-10, BO-03 | sanash/boshlash — `stock.count.create`; farqni tasdiqlash — `stock.count.post` |
| `stock.edit` | BO-03 | olib tashlansin (umumiy tahrir yo'q); amal-xos: `transfer.create`, `stock.count.create`, `stock.writeoff` |
| `transfer.view` | BO-03 | `stock.view` |
| `reports.view` | BO-02, BO-09 | `reports.sales.view` (savdo/ombor), `reports.finance.view` (moliya, qarz, P&L) |
| `discount.rules.manage` | BO-05 | `discount.rule.manage` |
| `tax.view` | BO-07, BO-10 | `tax.vat.view` |
| `tax.reconcile` | BO-10 | ko'rish/farq/yuklash — `tax.compare.review`; tuzatish yuborish — `tax.correction.submit` |
| `accounting.view` | BO-08 | `accounting.post` |
| `accounting.export` | BO-08 | `reports.export` |
| `settings.tenant` | BO-14 | `settings.tenant` (05+, yangi, faqat Egasi) |
| `einvoice.view` | BO-15 | `purchases.post` (kiruvchi ro'yxat/qabul/rad — 13-2 §19) |
| `approvals.manage` | BO-16 | `kind`ga mos: `discount.approve` / `returns.approve` / `debts.approve` / `prices.approve` / `cash.withdraw` (limit) / `expenses.approve` |
| `expenses.view` | BO-17 | `expenses.create` (13-3 #41) |
| `labels.generate` | BO-18 | `catalog.manage` (05+, 13-2 taklifi) |
| — | BO-04, BO-21 OCR tugmasi | `ai.ocr.use` qo'shilsin (hozir faqat `purchases.create` yozilgan) |

Mos keladigan (o'zgarishsiz): `shift.open/close`, `sales.create/void`, `returns.create/approve`, `debts.create/approve/forgive`, `purchases.create/receive/pay/return`, `transfer.create/receive`, `stock.view`, `prices.edit/approve`, `labels.print`, `einvoice.sign`, `settings.users`, `settings.branches`, `billing.manage`, `telegram.link`, `notifications.manage`, `ai.chat.use`, `platform.admin`.

### E-03 · K · POS-13 "QARZ YOZISH" fiskal chekni chetlab o'tadi

`newDebt.amount` (erkin summa) bilan `sale.created/debt_moves` yozish — chek va tovarsiz qarz; bu "Qarzli sotuv ham oddiy sotuv kabi fiskal chek bilan rasmiylashtiriladi" qoidasini (02 M08 Qoidalar) va `sale.created.lines[] ≥1` sxemasini buzadi. **O'zgartirish** (POS-13 Maydonlar/Amallar):

> - `newDebt.amount`, `newDebt.note` maydonlari **olib tashlansin**.
> - "QARZ YOZISH" tugmasi → POS-02'ni shu mijoz tanlangan holda ochadi, to'lov usuli oldindan `debt` (POS-06 oqimi); natija — `sale.created` (`payments[].method=debt`) + fiskal chek. Ruxsat: `debts.create`.
> - Tovarsiz "eski qarz"ni kiritish faqat BO-06 → "Boshlang'ich qarz" (`POST /api/v1/debt-openings`, Egasi) orqali.

### E-04 · Y · Obuna: 24 soatlik imtiyoz holati yo'q, BO-19 lokautda ochiq deb yozilgan

1. "Qanday o'qish kerak" bo'limidagi holatlar ro'yxatiga **yettinchi holat** qo'shilsin: "`subscription-grace` — `GET /billing/subscription.status=grace`: barcha ekran ishlaydi, shell tepasida qizil `aria-live=assertive` banner: «Obuna muddati o'tdi. {HH:mm} ichida to'lang, aks holda kassa to'xtaydi» + "To'lash" (BO-19); muddatdan 3/1/0 kun oldin sariq banner «Obuna {sana} da tugaydi»." (US-M17-03).
2. BO-19 "Holatlar" qatoridagi `subscription-restricted` matni almashtirilsin: "`restricted`da BO-19 (`/app/billing`) **ochilmaydi** — sessiya bekor qilingan; to'lov faqat BO-01'ning `reason=subscription_expired` variantidagi `GET /billing/pay` tor sahifasida (12-auth §16.1.1). BO-19 ↔ `grace`: to'liq ishlaydi."
3. POS-01 `subscription-restricted`: "Ma'lumotlarimni yuklab olish" POS PIN ekranida emas — tugma `/login?reason=subscription_expired`ga yo'naltiradi (telefon+parol + `purpose=data_export` OTP, D2).

### E-05 · Y · BO-06: shubhali qarz belgisi kechish bilan aralashgan; va'da sanasi va 60 kunlik ro'yxat yo'q

BO-06 Amallar jadvali almashtirilsin:

| Tugma | Ruxsat | Tasdiqlash dialogi | Natija |
|---|---|---|---|
| Shubhali deb belgilash | `debts.forgive` (faqat Egasi) | Sabab majburiy | `POST /debt-doubtful-flags` — provodka **yo'q**, faqat belgi |
| Belgini olib tashlash | `debts.forgive` | Yo'q | `POST /debt-doubtful-flags/{id}/unflag` |
| Qarzni kechish (hisobdan chiqarish) | `debts.forgive` (faqat Egasi) | Sabab majburiy + "Bu amal provodka yaratadi" | `POST /debt-writeoffs` → `/post` |

Maydonlarga qo'shilsin: "**Bugun/o'tgan va'da** tab — `due_date ≤ bugun` (US-M08-09)"; "**60+ kun** tab — eslatma ro'yxati, tizim avtomatik belgilamaydi (US-M08-10, tavsiya #9)"; `limit_exceeded_offline=true` filtri (Egasi). Bog'liq US'ga US-M08-06, US-M08-11 qo'shilsin.

### E-06 · Y · US-M08-02 (Must) — kredit limiti/mijoz kartasi hech qaysi ekranda yo'q

BO-06'ga "Mijoz kartasi" `Sheet` qo'shilsin: maydonlar `name`, `phone`, `kind` (`person|company`), `stir`, `legal_address`, `bank_account`, `bank_mfo` (B2B e-faktura uchun), `creditLimit` (`MoneyInput`, bo'sh = limitsiz), `standingDiscountPct` (0–100, tavsiya #8), `notifyConsent` (`Switch`); saqlash — `PATCH /api/v1/counterparties/{id}` (`version` bilan), ruxsat `debts.limit.manage`.

### E-07 · Y · US-M08-11 (Must) — yetkazib beruvchiga qarzimiz ekransiz

BO-04'ga to'rtinchi tab "**Men qarzdorman**" qo'shilsin: `GET /api/v1/reports/debts-aging?direction=payable` (yetkazib beruvchi, summa, muddat), qatordan "To'lash" → mavjud "To'lov qayd etish" formasi; ruxsat `purchases.pay` (ko'rish — `reports.finance.view`).

### E-08 · Y · US-M05-02/03 (Must) — inventarizatsiya farqini tasdiqlash ekransiz

POS-10 "SANASHNI YAKUNLASH → BO-03ga farq tasdiqlash uchun" deydi, lekin BO-03'da amal yo'q. BO-03'ga "**Inventarizatsiyalar**" tab qo'shilsin: ro'yxat `GET /api/v1/stock-counts?status=review`, qator — kutilgan/sanalgan/farq/summa; tugmalar "Farqni tasdiqlash" (`stock.count.post`, `POST /stock-counts/{id}/post`, dialog «Kamomad X so'm, ortiqcha Y so'm hisobga olinadi») va "Bekor qilish" (`POST /stock-counts/{id}/cancel`).

### E-09 · Y · US-M11-02 (Must) — oyni yopish ekransiz; "yopilgan oy qayta ochilmaydi" ko'rsatilmagan

BO-08'ga qo'shilsin: "**Davrni yopish**" tugmasi (`accounting.period.close`) → avval `GET /period-closings/{period}/readiness` (blokerlar ro'yxati: `recost_pending`, `fiscal_pending`), so'ng dialog «{oy} yopiladi. Yopilgan oy **qayta ochilmaydi** — keyingi tuzatishlar joriy ochiq oyda tuzatuvchi yozuv bilan kiritiladi» → `POST /period-closings`. "Tuzatuvchi yozuv" tugmasi (`accounting.post`) → `POST /ledger-entries/adjustments` (`entry_date` faqat ochiq davr, `comment` majburiy). `error` holatiga `PERIOD_CLOSED` (#41 microcopy, D-06) qo'shilsin.

### E-10 · Y · BO-10: davlat hisobotini yuklash (asosiy qadam) va AI-05 yo'q; Won't soliqlar tab sifatida

1. Amallarga qo'shilsin: "Davlat hisobotini yuklash" (`tax.compare.review`; maydonlar `taxType` `vat|turnover`, `period` YYYY-MM, `publishedAt` sana — 5 kunlik hisoblagich shundan, `file` PDF/XLSX ≤5 MB) → `POST /state-reports` → avtomatik `POST /state-reports/{id}/compare`; "Farqni tushuntirish (AI-05)" (`tax.compare.review`) → `POST /ai/vat-diffs/{diff_id}/explain`; matn ostida «AI tushuntirish — raqamlar tizim hisobidan» belgisi.
2. `taxTypeTab`dan `Mulk*/Yer*/JShDS*/Ijtimoiy*` **olib tashlansin** (06 §1.3 Won't; API `tax_type` faqat `vat|turnover`).
3. Eskalatsiya (reestr #3): 3-kalendar kundan keyin Egasiga ham banner.

### E-11 · Y · POS-07/POS-15: smena yopish oqimi API bilan mos emas

POS-15 Amallar "Natija" ustuni almashtirilsin: «`counted_cash`, `variance_note` lokal saqlanadi; POS-07 "SMENANI YOPISH" bosilganda **bitta** `shift.closed` voqeasi (`counted_cash`, `counted_card_total`, `variance_note`) yuboriladi». `cash_count.recorded` hamma joydan (Amallar, Ma'lumot manbai, Audit) olib tashlansin; audit — `shift.closed`, `cash_discrepancy_flagged`. Oqim tartibi aniq yozilsin: POS-07 (jamlanma) → POS-15 (sanash) → tasdiq → `shift.closed` → Z-hisobot ko'rinishi.

### E-12 · Y · POS-04: iOS chop etish yo'li (D3) yo'q

POS-04 "Chop etish" Natijasi almashtirilsin: «`shared/lib/printer` runtime tanlovi: Chromium — WebUSB/Serial/Bluetooth/tarmoq; **iOS o'rnatilgan PWA — faqat `CloudPrintAdapter`** (Star CloudPRNT/Epson SDP); hech biri sozlanmagan bo'lsa tugma o'rniga "QR chek" asosiy bo'ladi». Holatlarga: "iOS, bulut printer sozlanmagan — «Chop etish uchun bulut-printerni ulang» + `/install#cloud-print` havolasi".

### E-13 · Y · POS-08: offline qabul API'da yo'q; Omborchi kirimni o'tkaza olmaydi

1. POS-08 `offline` holati almashtirilsin: «Offline — **qabul yopiq** ("Tovar qabul qilish uchun internet kerak"); sanash/skanerni lokal davom ettirish mumkin, yakunlash faqat online». Sabab: 13-2 Asosiy xulosa 7 (kirim faqat online), markirovkalangan tovar qabulida egalik o'zgaradi (offline faqat o'z filiallari orasidagi ko'chirish ruxsat — tavsiya #5).
2. "QABULNI YAKUNLASH" natijasi: «`POST /goods-receipts` (draft, `purchases.receive`) → Buxgalter BO-04 "Kirimlar" tabida `POST /goods-receipts/{id}/post` (`purchases.post`) bilan o'tkazadi — qoldiq shu paytda oshadi». Agar mahsulot egasi "qabul paytida qoldiq oshsin" desa — bu B-qaror (quyidagi founder ro'yxati emas; arxitektura: `post`ni `purchases.receive`ga ham berish).

### E-14 · O · POS-05: `refund_method` maydoni yo'q, sabab enum mos emas

Maydonlarga qo'shilsin: `refundMethod` — Qaytarish usuli — Способ возврата — tugmalar — Ha — `cash|card|debt_adjustment` — default asl to'lov usuli. `reason` qiymatlari: `defective` (Nuqsonli) / `wrong_item` (Mos kelmadi) / `customer_changed_mind` (Fikri o'zgardi) / `other` (Boshqa).

### E-15 · O · POS-14: sabab enum va "Xarajat to'lovi → M15" API'da yo'q

`reason` validatsiyasi: `owner_withdrawal` (Egasi oldi) / `collection` (Inkasso) / `deposit` (Qo'yish) / `expense` (Xarajat to'lovi — K1-06) / `other`. `expense` tanlansa — `expenseCategoryId` (`Select`, `GET /expense-categories` keshidan) majburiy.

### E-16 · O · POS-02: "3 urinishdan keyin qo'lda MXIK" noto'g'ri

`error` holatidagi matn: «Markirovka o'qilmadi (#23) → 3 urinishdan keyin **DataMatrix kodini qo'lda kiritish** maydoni (faqat online, `POST /marking/verify` bilan tekshiriladi; offline'da qo'lda kiritish taqiq), audit `marking.manual_entry`». MXIK — tovar katalogi rekviziti, markirovka zahirasi emas.

### E-17 · O · POS-06/POS-13: yagona va'da sanasi

POS-06 `dueDays` → `promiseDate` — "Va'da sanasi" — "Обещанная дата оплаты" — `Calendar` + tezkor tugmalar (7/14/30 kun) — Yo'q — ≥ bugun — bo'sh. Bitta sana (bo'lib to'lash grafigi yo'q, tavsiya #9). POS-13 "TO'LOV QABUL QILISH"ga ixtiyoriy `promiseDate` (qoldiq qolsa yangi va'da). API: K1-09.

### E-18 · O · BO-04: to'lov formasi va OCR shartlari to'liq emas

1. To'lov tab maydonlari: `source` (`cash|bank`, majburiy), `cashRegisterId` (`cash`da), `allocations[]` (kirim hujjati + summa, standart — eng eskisidan avtomatik), `docDate`; `payment.amount` validatsiyasi "≤qarz" → "oshsa ogohlantirish, avans sifatida qabul" (13-2 §11).
2. "Kirimlar" tab: `GET /goods-receipts?status=draft` + "O'tkazish" (`purchases.post`) + "E-fakturadan kirim" (BO-15'dan).
3. AI-03 qatori aniqlashtirilsin: «Sariq belgi chegarasi: summa <95%, sana <90%, miqdor/nom <80%; **har bir hujjat** foydalanuvchi "Tasdiqlash" bosmaguncha saqlanmaydi; AI-03 feature-flag o'chiq bo'lsa tugma ko'rinmaydi (reestr #19)». `ocrPhoto` max 10 MB (13-0 §12).

### E-19 · O · BO-03: hisobdan chiqarish, yaroqlilik va kam qoldiq amallari yo'q

Amallarga: "Hisobdan chiqarish" (`stock.writeoff`; partiya, miqdor, sabab `expired|damaged|gift|other`) → `POST /write-offs` → `/post`. Maydonlarga: `lowStockOnly` (`Switch`, US-M04-02), "Muddati 7 kunda tugaydi" filtri (`GET /stock-lots?expiring_within_days=7`, US-M04-06), `branchId` "Barchasi" varianti (US-M04-03).

### E-20 · O · BO-11: limitlar shaxsga emas, rolga bog'langan

`limits.*` uch maydon xodim formasidan **rol** formasiga ko'chirilsin: yangi tab "**Rollar**" — `GET /roles`, rol ichida `PUT /roles/{id}/permissions` (`discount.give` limit 5%, `returns.approve` 100 000, `cash.withdraw` 50 000 — default qiymatlar shu). Xodim formasida faqat `roleIds`, `branchIds`.

### E-21 · O · BO-12: `cashRegisterCount` API'da yo'q

`cashRegisterCount` o'rniga filial ichida "Kassalar" ro'yxati: "+ Kassa qo'shish" (`cash_register.manage`) → `POST /cash-registers`; `ADDON_REQUIRED` bo'lsa dialog «Qo'shimcha kassa — +39 000 so'm/oy. Obunaga qo'shasizmi?» → BO-19. "Arxivlash" → `PATCH /cash-registers/{id}` (`archived:true`).

### E-22 · O · BO-14: zaxira usuli, OFD qayta urinish, tarozi formati

`costingMethod` saqlash → `PATCH /valuation-settings` (`valuation.settings.manage`), javobdagi `pending_change.effective_from`ni ko'rsatish. "OFD: N ta chek yuborilmagan" → ro'yxat + "Qayta urinish" (`POST /fiscal-receipts/{id}/retry`). Tarozi: `scaleBarcodePrefix`, `scaleBarcodeVersion` → `PATCH /stock-settings` (US-M09-06). `fakturaUzCredentials` — "parol serverda shifrlangan saqlanadi, qayta ko'rsatilmaydi" izohi.

### E-23 · O · BO-15: chiquvchi e-faktura va e-fakturadan kirim

Amallarga "Kirim yaratish" (`purchases.receive`) → `POST /goods-receipts/from-einvoice/{id}` (US-M07-03). "Chek asosida e-faktura" xatolariga `EINVOICE_ALREADY_LINKED`, `EINVOICE_AMOUNT_EXCEEDS_RECEIPT`, `EINVOICE_COUNTERPARTY_INCOMPLETE` (→ E-06 kartasiga havola).

### E-24 · O · BO-16: navbatda xarajat va hisobdan chiqarish turlari yo'q

Maqsad qatoriga "katta xarajat (`EXPENSE_APPROVAL_REQUIRED`), limitdan katta hisobdan chiqarish" qo'shilsin; ro'yxat `kind` ustuni bilan; foydalanuvchi faqat o'z `*.approve` huquqiga mos `kind`ni ko'radi.

### E-25 · O · BO-17: maydonlar API bilan mos emas

`category` — `Select` `GET /expense-categories`dan (`categoryId` UUID, enum emas). `recurrence` → `period` (`none|month|quarter|year`) + `dayOfMonth` (1–28, takrorlanuvchida majburiy). `source=cash` BO-17'da **o'chirilsin** (naqd xarajat — POS-14 `expense`) yoki `cashRegisterId`+`shiftId` talab qilinsin. Amallarga "O'tkazish" (`/post`, limitdan oshsa «Egasi tasdig'iga yuborildi») va "Bekor qilish" (`/cancel`, sabab).

### E-26 · O · BO-19: AI sarfi birligi, kassa qo'shish/kamaytirish, kvitansiya

Layout'dagi «AI sarfi: 1 240 / 5 000 so'rov» → «AI limiti: {pct_used}% ishlatildi» (`GET /ai/usage` token qaytaradi). `extraRegisters` → "+/−" stepper: oshirish `POST /billing/addons`, kamaytirish `DELETE /billing/addons/extra_register` (`requires_archiving` bo'lsa — BO-12 ga yo'naltirish). To'lovlar tarixi qatoriga "Kvitansiya" (`GET /billing/invoices/{payment_id}`).

### E-27 · Y · BO-21: parol maydoni yo'q, boshlang'ich qoldiq bosqichi yo'q

① bosqichga qo'shilsin: `password` — Parol — Пароль — `Input type=password` — Ha — ≥8 belgi — max 128 (login telefon+parol bilan, parolsiz hisob kira olmaydi). ③ bosqich ikki qismga: "Tovarlar" (`import-jobs kind=products`) va "Boshlang'ich qoldiq" (`kind=opening_stock` yoki `POST /stock-openings`, US-M04-04). "Yakunlash" → `POST /auth/signup` (A-01) ① va ② bosqichdan keyin darhol (tenant ③–⑥ dan oldin yaratilishi shart, aks holda import qiladigan tenant yo'q).

### E-28 · O · US-M16-03 va US-M02-03 ko'rinmaydi

BO-09 `reportType` ro'yxatiga "Kassa/smena tarixi" (`GET /cash-registers/{id}/cash-history`) va "QQS registri (qaytarishlar bilan)" (`GET /vat/moves?doc_type=returns`) qo'shilsin; Bog'liq US: US-M16-03, US-M02-03.

### E-29 · O · POS-01: Omborchi smena ochmaydi

POS-01 ikki qadamga bo'linsin: "PIN bilan kirish" (har POS foydalanuvchisi) → rolga qarab: `shift.open` bor bo'lsa "Smenani ochish" (`openingCash`), yo'q bo'lsa (Omborchi) to'g'ridan-to'g'ri POS-08/09/10 menyusi. `branchId` `Select` olib tashlansin — qurilma `devices.cash_register_id` orqali filialga bog'langan (faqat ko'rsatiladi).

### E-30 · P · Mayda nomuvofiqliklar

ADM-01 `planFilter` olib tashlansin (yagona tarif) → `addonFilter` ("qo'shimcha kassasi bor"). BO-13 `message` max 500 — API 2000, UI 500 qoladi (izoh). BO-07 `period` "oy/chorak" → API faqat `YYYY-MM`; chorak — 3 oyni klientda yig'ish emas, keyinroq API.

### E-31 · P · Audit va analitika voqea nomlari aralash

"Qanday o'qish kerak"ga qoida: «`audit_log.action` — `domen.fe'l` (nuqta, masalan `sale.draft_voided`), mahsulot analitikasi — `snake_case` (`receipt_printed`)». Hozir ikkala uslub bir ustunda aralash.

### E-32 · Y · Alohida iOS o'rnatish yo'riqnomasi (vazifa №7) — QAROR: **ha, alohida route**

"Yakuniy eslatma" 3-band almashtirilsin va BO-21'dan keyin yangi bo'lim qo'shilsin:

> ## UX-INSTALL — Qurilmani o'rnatish yo'riqnomasi (37 ta biznes ekranga kirmaydi, yordamchi route)
> - **Route**: `/install` (ochiq, autentifikatsiyasiz — login'dan oldin ham kerak); BO-21 ⑥ bosqichi shu komponentni ichiga oladi (`<InstallGuide embedded />`), alohida nusxa yo'q.
> - **Kim ochadi**: (a) BO-21 ⑥; (b) iOS Safari'da `/pos/*` yoki `/app/*` **o'rnatilmagan** holatda ochilsa (`navigator.standalone !== true` va `display-mode: standalone` emas) — POS yo'llari bloklanadi, `/install?platform=ios`ga yo'naltiriladi, back-office'da faqat yuqori banner; (c) BO-11 "Qurilmalar" tab → "Yangi qurilma qo'shish"; (d) POS-04 "bulut printer sozlanmagan" havolasi (`/install#cloud-print`).
> - **Bo'limlar**: platforma avtomatik aniqlanadi (iOS / Android Chrome / Windows-Chrome), qo'lda almashtirish tugmalari; iOS: 3 qadam rasm bilan (Safari → Ulashish → "Home ekranga qo'shish") + «O'rnatilmasa ma'lumotlar o'chib ketishi mumkin» ogohlantirishi; Android/Chrome: `beforeinstallprompt` orqali "O'rnatish" tugmasi; **Bulut printer**: Star CloudPRNT/Epson SDP — printer URL'ini sozlash qadamlari, "Sinov cheki"; printer yo'q bo'lsa — elektron chek (QR/Telegram).
> - **Holatlar**: `loading` — yo'q; `offline` — matn keshdan (service worker precache); `no-permission`/`subscription-restricted` — tegishli emas.
> - **Analitika**: `install_guide_viewed`, `pwa_installed` (`appinstalled` hodisasi), `cloud_printer_test_printed`.
> - **Sabab**: iOS'da o'rnatish **majburiy** (ITP IndexedDB'ni tozalaydi, `08-frontend` §6) va qurilma almashtirilganda login'dan keyin ham qayta kerak — wizard ichida qolib ketsa topib bo'lmaydi.

---

# 2. `spec/01-mahsulot/08-dizayn-tizimi.md`

### D-01 · K · Pulni ko'rsatish va hisoblash qoidasi ziddiyatli (vazifa №5)

§0.1 ikkinchi jumlasi ("Pul hisob-kitobi hech qachon frontendda qilinmaydi") **noto'g'ri** — offline POS chek jami, chegirma, qaytim, kutilgan naqdni o'zi hisoblaydi (04-offline-sync, 13-1 §4.1 `Σpayments = Σline_total`). §0.1 va §8 "Pul" bandi quyidagicha almashtirilsin:

> **Pul — saqlash, uzatish, ko'rsatish (yagona qoida):**
> 1. **Saqlash/API**: pul har doim o'nlik **satr** `"12000.00"` (NUMERIC(18,2), tiyingacha); narx/tannarx — `"8333.3333"` (4 xona); miqdor — `"1.250"` (3 xona). JSON number taqiqlanadi (13-0 §3).
> 2. **Frontendda hisoblash** (faqat POS offline va forma jamlari): `decimal.js` (yoki `big.js`) bilan, satrdan satrga; `Number`/`parseFloat` bilan pul hisoblash **taqiqlanadi** (lint qoidasi).
> 3. **Yaxlitlash** — server bilan aynan bir xil, `shared/lib/money` ichida bitta funksiya: `line_total = ROUND_HALF_UP(qty × unit_price − discount, 0)` — chakana chek qatori **so'mgacha** (narxlar butun so'm, naqd tiyinsiz; tortiladigan tovarda kasr shu yerda yo'qoladi); QQS (narx ichida) `= ROUND_HALF_UP(line_total × r/(100+r), 2)` — tiyingacha (reestr #33). Bu qoida backend `SalePostingService` tekshiruvi bilan bir xil bo'lishi va umumiy test-vektorlar (`shared/money-vectors.json`) bilan ikkala tomonda tekshirilishi shart. *(Buxgalter tasdiqlaydi — qator jamini so'mgacha yaxlitlash.)*
> 4. **Ko'rsatish**: `formatMoney(value: string)` — **faqat ko'rsatish uchun** `ROUND_HALF_UP` bilan butun so'mga yaxlitlaydi (`"7392.86"` → `7 393 so'm`); yaxlitlangan qiymat hech qachon qayta API'ga yuborilmaydi va hisobda ishlatilmaydi. Jadval yig'indisi — yaxlitlangan qatorlar yig'indisi emas, backend bergan jami.
> 5. **Istisno — fiskal chek va buxgalteriya/QQS hisobotlari**: OFD/hisob talab qilgan aniqlikda (2 xona, `7 392,86`) — `formatMoney(value, { precision: 2 })`; aniq format OFD spetsifikatsiyasi bilan yakunlanadi (D-04).

### D-02 · Y · §8 va §7.2'da API turi noto'g'ri

§8 "Kasr kerak bo'lgan joy" bandidagi «Backend API JSON'da har doim `.` (nuqta) bilan kasr qaytaradi (standart JSON/number)» → «Backend o'nlik qiymatlarni **satr** sifatida nuqta bilan qaytaradi (`"12.50"`); frontend ko'rsatishda vergulga aylantiradi». §7.2: `MoneyInput` props `value: number` → `value: string` (`"12000.00"` chiqaradi, kiritish butun so'm); yangi komponent **`PriceInput`** — tannarx/xarid narxi uchun, ≤4 kasr (BO-04 `lines[].price`, `stock-openings.unit_cost`); `MoneyDisplay.value: string`.

### D-03 · O · Miqdor kasr xonasi

§7.2 `QtyInput` "kg=2 xonali kasr" va §8 "Miqdor ... 2 xonali kasr" → **3 xona** (`1,250 kg`; API `NUMERIC(18,3)`, tarozi shtrix-kodi grammgacha). §8 misoli allaqachon 3 xonali — matn unga moslashtirilsin.

### D-04 · O · Fiskal chek shablonida summa aniqligi

§13.1'da `QQS (12%, ichida): 7 393 so'm` — fiskal rekvizit yaxlitlangan holda chiqmasligi kerak bo'lishi mumkin. Izoh qo'shilsin: «Fiskal chekdagi summa/QQS aniqligi (tiyin bilan yoki so'mgacha) — OFD spetsifikatsiyasi bo'yicha, D-01 §5; hozircha 2 xona bilan chiqariladi». Ochiq savollar ro'yxatiga 6-band sifatida.

### D-05 · Y · i18n kaliti server `message_key` bilan mos emas; microcopy ↔ xato katalogi

1. §11 "Server xato kodlari ... `common:errors.<SERVER_CODE camelCase>`" → «Server javobidagi `error.message_key` (masalan `errors.debt_limit_exceeded`) **aynan** `common` namespace kaliti sifatida ishlatiladi: `t('common:' + message_key)`; noma'lum kalit → `common:errors.internal_error`. Maydon xatolari (`details[].message_key`) `validation.*` prefiksida (C-04) — zod `errorMap` bilan bir xil kalitlar.»
2. §12 jadvaliga `message_key` ustuni qo'shilsin; matnlar 13-0 §15 bilan **bitta manba** — farqlanganda 08 §12 matni ustun, 13-0 shunga yangilanadi:

| # | message_key | Izoh |
|---|---|---|
| 8 | `errors.internal_error` | 13-0 matni → 08 #8 matniga |
| 9 | — (klient, tarmoq) | — |
| 10 | `errors.permission_denied` | 13-0 «Bu amal uchun ruxsatingiz yo'q» → «Sizda bu amal uchun huquq yo'q» |
| 11 | `errors.subscription_restricted` | 13-0 «…to'lov qiling» → «…Davom etish uchun to'lang» |
| 12/13/14 | `validation.required` / `validation.phone_format` / `validation.max_length` | 422 `details` |
| 17 | `errors.pin_invalid` | mos |
| 18 | `errors.invalid_credentials` | 13-0 «Telefon raqami yoki parol…» → «Telefon yoki parol noto'g'ri» |
| 19 | `errors.approval_required` + `errors.*_limit_exceeded` (5 ta) | limit kodlari bitta umumiy matnga |
| 20 | `errors.not_found` (chek qidiruvi) | `SALE_NOT_FOUND` boshqa ma'noda (sinxronlanmagan) — #20'ga bog'lanmasin |
| 21 | `errors.product_not_found` / `errors.barcode_not_in_catalog` | C-02 |
| 22 | `errors.insufficient_stock` | mos |
| 23 | `errors.marking_code_invalid` | mos |
| 24 | `errors.marking_price_unknown_offline` | mos |
| 26 | `errors.marking_return_requires_online` | **yangi kod** (C-02) — hozir `MARKING_CODE_INVALID`+`details.reason` |
| 30 | `validation.variance_note_required` | `shift.closed` 422 |
| 33 | — (AI javobi, xato emas) | — |
| 37 | `errors.otp_invalid` / `errors.otp_expired` | ikki kod bitta matnga |

### D-06 · O · Yetishmayotgan standart xabarlar

§12 jadvaliga qo'shilsin:

| # | Holat | O'zbek | Rus | message_key |
|---|---|---|---|---|
| 40 | Imtiyoz davri | Obuna muddati o'tdi. {vaqt} ichida to'lang, aks holda kassa to'xtaydi | Подписка просрочена. Оплатите в течение {время}, иначе касса остановится | `billing.grace_banner` |
| 41 | Davr yopilgan | Bu oy yopilgan. Tuzatishni joriy oyda kiriting | Этот месяц закрыт. Внесите исправление в текущем месяце | `errors.period_closed` |
| 42 | Soat orqaga surilgan | Qurilma soatini to'g'rilang va internetga ulaning | Исправьте время на устройстве и подключитесь к интернету | `errors.device_clock_invalid` |
| 43 | Litsenziya tugagan (offline) | Obuna tasdiqlanmadi. Internetga ulaning | Подписка не подтверждена. Подключитесь к интернету | `errors.license_expired` |
| 44 | Masofaviy tasdiq yuborildi | Menejerga tasdiqlash uchun yuborildi. Kuting… | Отправлено менеджеру на подтверждение. Ожидайте… | `approvals.sent` |
| 45 | Offline nasiya limitdan oshdi | Limitdan oshdi — sotuv saqlandi, Egasiga xabar beriladi | Лимит превышен — продажа сохранена, владелец будет уведомлён | `debts.limit_exceeded_offline` |
| 46 | iOS o'rnatilmagan | Kassani ishlatish uchun uni Home ekranga o'rnating | Установите кассу на экран «Домой», чтобы работать | `install.ios_required` |

### D-07 · O · Teginish nishonlari va kritik matn o'lchami

§5/§10: (a) mobil PWA (§6.3, Egasi telefon) — `@media (pointer: coarse)` yoki `<768px`da `data-density="touch"`ga o'tadi (36px telefon uchun kichik, WCAG 2.5.5 tavsiyasi 44px); (b) reestr #13'dagi "44×44 dp" — POS uchun **48** (bu fayl ustun), mobil back-office — 44; (c) `text-caption` (11px) offline 48 soat hisoblagichi uchun ishlatilmasin — kritik holat kamida `text-small` 13px, 600.

### D-08 · P · Qorong'i rejim CSS xatosi

§1: `:root:not([data-theme="light"]) { @media (prefers-color-scheme: dark) {...} }` ichida `[data-theme="dark"]` ham media'ga bog'langan — OS yorug' bo'lsa qo'lda tanlangan dark ishlamaydi. Ikki blokka ajratilsin: `:root[data-theme="dark"] {…}` (media'siz) va `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {…} }`.

---

# 3. `spec/02-arxitektura/13-api-katalog-0-umumiy.md`

### C-01 · K · Resurs nomlash ziddiyati (kebab vs snake) ochiq qoldirilgan — orval generatsiyasini bloklaydi

Asosiy xulosa 2 va Ochiq savol 1 almashtirilsin: «**Qaror**: URL yo'li — kebab-case ko'plik (`/goods-receipts`); JSON maydonlari, enum qiymatlari, query parametrlari va `operation_id` — snake_case. `09-backend-arxitekturasi.md` §3 shu qarorga moslashtiriladi; qaror `00-qarorlar.md` #24 sifatida yoziladi (Q-01).»

### C-02 · Y · "Yagona manba" xato katalogida 13-1/13-2/13-3 ishlatgan 50+ kod yo'q

§15'ga qo'shilsin (HTTP, `message_key = errors.<snake>`): `PIN_REQUIRED` 403, `SHIFT_NOT_OPEN` 409, `SHIFT_ALREADY_OPEN` 409, `STOCK_NEGATIVE` (200, ogohlantirish), `MARKING_VERIFY_UNAVAILABLE` 503, `MARKING_RETURN_REQUIRES_ONLINE` 422 (yangi, D-05 #26), `APPROVAL_REQUEST_ALREADY_RESOLVED` 409, `APPROVAL_REQUEST_EXPIRED` 409, `PAYMENT_PROVIDER_ERROR` 502, `PAYMENT_TIMEOUT` 504, `COUNTERPARTY_NOT_FOUND` 404, `PERIOD_CLOSE_NOT_READY` 409, `SYSTEM_ROLE_READONLY` 409, `WRITE_OFF_LIMIT_EXCEEDED` 403 hamda 13-2 "Ishlatilgan xato kodlari" jadvalidagi barcha 44 kod (`PRODUCT_NOT_FOUND`…`RECOST_JOB_NOT_RETRYABLE`). `FORBIDDEN` (13-1/13-2) → `PERMISSION_DENIED`ga almashtirilsin. 13-2'dagi `AI_UNAVAILABLE` → `AI_PROVIDER_UNAVAILABLE`.

### C-03 · O · §9 "Istisno" bandida `GET /sales/{id}/cancel`

Almashtirilsin: «O'tkazilgan sotuv bekor qilinmaydi (fiskal chek chiqqan) — tuzatish faqat qaytarish (`return.created`) orqali. `sales.void` — faqat to'lovdan oldingi qoralama (`sale.draft_voided`). `POST /sales` ham, `…/cancel` ham yo'q; mavjud: `GET /sales`, `GET /sales/{id}` (13-1 §4.8, K1-01).»

### C-04 · O · `details[].message_key` prefiksi

§7.1 misoli: `"message_key": "errors.field.exceeds_credit_limit"` → `"validation.exceeds_credit_limit"`; qoida: «maydon darajasidagi kalitlar `validation.*` — frontend zod kalitlari bilan bir xil (08-dizayn §11)».

### C-05 · P · `/auth` prefiksi

§1 jadvali "Auth/sync" qatoriga: «Auth yo'llari `/auth/*` (BFF, `/api/v1`siz), istisno — `GET /api/v1/auth/csrf` (00-qarorlar #4); sync — `/api/v1/sync/*`».

### C-06 · Y · `POST /attachments` havola qilinadi, lekin hech qayerda ta'riflanmagan

§12'ga endpoint qo'shilsin: «`POST /api/v1/attachments` — `multipart/form-data` (`file`, `purpose`: `ocr|expense_receipt|state_report|import`), ruxsat — `purpose`ga mos (`ai.ocr.use`/`expenses.create`/`tax.compare.review`/`catalog.manage`), Idempotency-Key majburiy, javob `201 {id, url, content_type, size}`; `GET /api/v1/attachments/{id}` → yangi signed URL (15 daqiqa).» `13-api-katalog-2` §6 `POST /import-jobs` va 13-3 #3 ham ixtiyoriy `attachment_id`ni qabul qilsin.

---

# 4. `spec/02-arxitektura/13-api-katalog-1-kassa.md`

### K1-01 · Y · `GET /sales` yo'q (POS-05 chek qidiruvi, BO-09)

1-bo'lim indeksiga va yangi §4.8'ga: «`GET /api/v1/sales?number=&fiscal_receipt_seq=&shift_id=&counterparty_id=&doc_date__gte=&doc_date__lte=&cursor=&limit=` → `{items:[{id, number, temp_number, doc_date, total, payments_summary, counterparty_id, is_offline, has_returns}], next_cursor}`; `GET /api/v1/sales/{id}` → qatorlar (`sale_line_id`, `qty`, `returned_qty`, `marking_code`), to'lovlar. Ruxsat: `sales.create` (o'z filiali, POS-05) yoki `reports.sales.view`.»

### K1-02 · Y · Ochiq smena jamlanmasi va kutilgan naqd endpoint'i yo'q

§3.3 `GET /api/v1/shifts/{id}` javobiga: «`running_totals` (smena `open` bo'lsa): `{totals_by_method:{cash, card, uzqr, click, payme, uzum, debt}, sales_count, voided_count, returns_total, cash_in, cash_out, expected_cash}`» — POS-07/POS-15 online solishtirish manbai (offline — lokal hisob).

### K1-03 · K · `transfer.created`, `transfer.received`, `stock_count.line_recorded` payload'i hech qayerda yo'q

13-1 "M04/M05 hujjatida" deydi, 13-2 "`04-offline-sync.md`da" deydi — hech biri yozmagan. 13-1'ga yangi §17a qo'shilsin:

> **`transfer.created`** — huquq `transfer.create`; payload: `id` (UUIDv7), `from_warehouse_id`, `to_warehouse_id`, `doc_date`, `lines[]: {line_id, product_id, qty, marking_code|null}`; server darhol `draft→sent` (`TransferPostingService`), javob `{id, number}`; markirovkali qator — faqat o'z tenant omborlari orasida (boshqasi `VALIDATION_ERROR`).
> **`transfer.received`** — huquq `transfer.receive`; payload: `transfer_id`, `lines[]: {transfer_line_id, qty_received}`; javob `{status:"received"|"discrepancy"}`; `TRANSFER_ALREADY_RECEIVED`.
> **`stock_count.line_recorded`** — huquq `stock.count.create`; payload: `stock_count_id`, `lines[]: {product_id, counted, barcode|null, counted_at}`; bir qator bir necha marta kelsa — oxirgi `counted_at` g'olib (idempotent upsert); `BARCODE_NOT_IN_CATALOG` — `status=accepted`, `warnings`da.
> 1-bo'lim xulosa 2 ro'yxatiga `transfer.created`, `transfer.received` qo'shilsin. `purchase.received` voqeasi **yo'q** (kirim faqat online, K2-02).

### K1-04 · Y · Chiquvchi e-faktura API'si yo'q (US-M01-06, POS-06 B2B, BO-15)

13-2 "sotuv/qarz katalogida" deydi, 13-1'da yo'q. 13-1'ga yangi §14a:

> - `GET /api/v1/einvoices?direction=out&status=&cursor=&limit=` — ruxsat `einvoice.sign` yoki `purchases.post`.
> - `POST /api/v1/einvoices` — `{direction:"out", source:"sale"|"manual", sale_id|null, counterparty_id, lines[]}`; B2B nasiya sotuvdan server avtomatik `draft` yaratadi (`sale.created` + `counterparty.kind=company`). Ruxsat `einvoice.sign`. Xatolar `EINVOICE_COUNTERPARTY_INCOMPLETE`.
> - `POST /api/v1/einvoices/from-receipt` — `{sale_id, counterparty_id}`; `related_doc` bog'lanadi, QQS/provodka yo'q (02-provodka 2.22). Xatolar `EINVOICE_ALREADY_LINKED`, `EINVOICE_AMOUNT_EXCEEDS_RECEIPT`.
> - Imzolash/yuborish — 13-2 §19'dagi `sign-challenge`/`submit-signed` bilan bir xil; yuborish `outbox_jobs(kind=einvoice_send)` → faqat Faktura.uz (tavsiya #4).

### K1-05 · Y · Qarz eskirish hisoboti ikki marta, ikki nom bilan

§12.8 `GET /api/v1/reports/debt-aging` **o'chirilsin**, o'rniga: «Qarz eskirishi — 13-3 #21 `GET /reports/debts-aging` (yagona). Shu endpoint javobiga 13-1'dagi maydonlar qo'shiladi: `limit_exceeded_offline`, `overdue_since`, `due_date`; filtrlar `?limit_exceeded_offline=&bucket=&branch_id=`.»

### K1-06 · O · Kassadan xarajat to'lovi (POS-14 → M15) voqeasi yo'q

§13.1 `reason` enumiga `expense` qo'shilsin + maydon `expense_category_id` (UUID, `reason=expense`da majburiy); server `cash_movement` bilan bir tranzaksiyada `expenses(source=cash, status=posted)` yozadi (`02-provodka` 2.17). 13-3 #42 "Offline: kassa naqdi ... POS outbox bilan" bandi shu voqeaga havola qilsin.

### K1-07 · O · Tasdiqlash navbati turlari to'liq emas

§9.1 `kind` enumiga `expense_over_limit`, `write_off_over_limit` qo'shilsin; §9.3 ruxsat ro'yxatiga `cash.withdraw` (limit ≥ summa) va `expenses.approve`; §9.4'da `cash_withdrawal_over_limit` → tasdiqlovchining `cash.withdraw.limit_value ≥ context.amount`.

### K1-08 · Y · Narx o'zgarishi 13-1 §10 va 13-2 §4'da ikki xil

13-1 §10'ni qisqartirib: «`price-changes` resursining to'liq ta'rifi — 13-2 §4 (yagona). Tasdiqlash — faqat `approval-requests` (`kind=price_change`) orqali, BO-16 yagona navbat; 13-2'dagi `/price-changes/{id}/approve|reject` olib tashlanadi (K2-03).» Tana maydoni ikkala faylda: `lines[].valid_from` (qator darajasida) + hujjat `doc_date`.

### K1-09 · O · Yagona va'da sanasi sxemada yo'q

§4.1 `sale.created` payload'iga: `due_date` (ISO sana\|null, faqat `payments[].method=debt` bo'lsa) — "va'da sanasi", bitta. §12.2 `promise_date` → `due_date` deb qayta nomlansin, ma'nosi: «qoldiq qolsa — mijozning **joriy** va'da sanasi yangilanadi (`counterparties.debt_due_date`, B-01)». §12.4 `debt-openings.due_date` — shu bilan bir xil.

### K1-10 · O · Qarz eslatmasi huquqi

13-3 #77–78 bilan birga: `draft` — `ai.chat.use`; `send` — `debts.remind` (X-01). Standart shablon (AI'siz) bilan yuborish ham `send` orqali (`message_text` qo'lda).

### K1-11 · P · `fiscal-receipts/{id}/retry` vaqtinchalik `billing.manage`

→ `settings.tenant` (X-01); Ochiq savol 2 yopilsin.

---

# 5. `spec/02-arxitektura/13-api-katalog-2-ombor.md`

### K2-01 · Y · AI-03 ikki xil loyihalangan (`/purchase-ocr-drafts` vs 13-3 `/ai/ocr/jobs`)

§8 `POST /purchase-ocr-drafts` va `GET /purchase-ocr-drafts/{id}` **olib tashlansin**; o'rniga: «OCR — 13-3 #73–75 (`POST /ai/ocr/jobs`, `doc_type_hint=purchase`, fayl `POST /attachments` orqali, ≤10 MB, ruxsat `ai.ocr.use`). `POST /goods-receipts/from-ocr-draft/{ocr_draft_id}` → `POST /goods-receipts/from-ocr-job/{job_id}` (ruxsat `purchases.receive` + `ai.ocr.use`); 13-3 #75 `confirm` `doc_type_hint=purchase` uchun shu endpoint'ni chaqiradi.» "Ma'lumotlar modeliga qo'shimchalar" 2-band (`purchase_ocr_drafts`) → 13-3'dagi `ai_ocr_jobs` bilan birlashtirilsin. Chegaralar matni (95/90/80) saqlansin.

### K2-02 · Y · POS-08 mobil qabul — xulosa 7 va §8 bir-biriga zid

§8 `cancel` bandidagi «Mobil skaner (POS-08) orqali qabul qilish esa `/sync/push` outbox yo'li bilan ishlaydi» → «POS-08 ham shu REST endpoint'lardan foydalanadi (**faqat online**); offline kirim voqeasi yo'q». Kirim `post` huquqi: `purchases.post` (Buxgalter) — mahsulot jarayoni (Omborchi qabul qilgan zahoti qoldiq oshishi kerakmi) BP-01 bilan solishtirilib, kerak bo'lsa `post`ga `purchases.receive` ham qo'shiladi, QQS/e-faktura qismi Buxgalterda qoladi.

### K2-03 · O · `/price-changes/{id}/approve|reject` olib tashlansin

K1-08 bo'yicha; §4 eslatmasiga: «`pending_approval` → `approval-requests` (`kind=price_change`, `linked_doc_id`); tasdiqlansa server `post`ni bajaradi.» Tasdiqlovchi — `prices.approve` (05 §2.2: **faqat Egasi**; "Menejer ham" iborasi olib tashlansin, R-03).

### K2-04 · O · Onboarding OCR katalog yo'li

§6'ga: «BO-21 ③ "Foto (AI-03)" yo'li — `POST /ai/ocr/jobs` (`doc_type_hint=catalog`) → `confirm` `products` + (miqdor bo'lsa) `stock-openings` draft'larini yaratadi.»

### K2-05 · P · Konsolidatsiyalangan qoldiq

§7 `GET /stock-balances`ga: «`warehouse_id` berilmasa — `X-Branch-Id` ombori; barcha filiallar bo'yicha — 13-3 #20 `GET /reports/stock` (US-M04-03).»

---

# 6. `spec/02-arxitektura/13-api-katalog-3-moliya-admin.md`

### K3-01 · Y · Tenant sozlamalari va integratsiya kalitlari endpoint'i yo'q (BO-14)

Yangi bo'lim "M13/M14 — Tenant sozlamalari":

> - `GET /api/v1/tenant/settings` → `{store_name, locale, tax_regime:{current, history[]}, integrations:{ofd:{status}, faktura_uz:{status, connected_at}, crpt:{status, key_last4}}, version}` — ruxsat `settings.tenant`.
> - `PATCH /api/v1/tenant/settings` — `{store_name?, locale?, version}`; `tax_regime` o'zgarishi — `POST /api/v1/tenant/tax-regimes` `{regime, valid_from (keyingi oy 1-sanasi)}`.
> - `PUT /api/v1/tenant/integrations/faktura-uz` — `{login, password}` → `tenant_secrets`da shifrlangan (KMS/`pgcrypto`), javobda hech qachon qaytmaydi; server `token` olib tekshiradi → `{status:"connected"}` yoki `EINVOICE_PROVIDER_UNAVAILABLE`/`VALIDATION_ERROR`.
> - `PUT /api/v1/tenant/integrations/crpt` — `{api_key}` → shifrlangan, tekshiruv `MARKING_VERIFY_UNAVAILABLE`.
> - `DELETE /api/v1/tenant/integrations/{provider}` — uzish. Barchasi audit majburiy, Idempotency-Key majburiy, faqat Egasi.

### K3-02 · O · `/cash-movements` 13-1 va 13-3'da ikki marta

#52 ruxsati: `cash.deposit` **yoki** `cash.count.shift` **yoki** `reports.sales.view`; 13-1 §13.2 → «13-3 #52 ga qarang». #53 izohiga: «POS'dan — faqat `cash_movement.created` voqeasi; bu REST — back-office (masalan inkasso yozish)».

### K3-03 · O · Egasi kassa tarixini ko'ra olmaydi

#55 ruxsati: `cash.count.shift` → `cash.count.shift` **yoki** `reports.sales.view` (05 §2.2'da Egasida `cash.count.shift` yo'q, US-M16-03 esa "Egasi sifatida"). Ochiq savol 1 yopilsin: ekran — BO-09 "Kassa/smena tarixi" (E-28).

### K3-04 · O · Lokautda to'lov — sessiyasiz checkout

#61 izohiga: «`restricted` holatda sessiya yo'q — to'lov 12-auth §16.1.1 `GET /billing/pay` orqali: telefon+parol identifikatsiyasidan keyin qisqa muddatli `pay_token` beriladi, `POST /billing/checkout` shu token bilan (`Authorization: PayToken …`) faqat shu endpoint uchun ruxsat etiladi.» 12-auth §20'ga ham bir qator (A-01 bilan birga).

### K3-05 · O · Bildirishnoma turlari ro'yxati yo'q

#69 javobiga `kind` enum: `daily_report`, `low_stock`, `cash_variance`, `over_limit_action`, `state_report_diff`, `offline_48h`, `subscription_due` (3/1/0 kun), `subscription_grace` (darhol/12 s/2 s), `debt_due_today` (US-M08-09), `debt_aging_60` (US-M08-10), `debt_limit_exceeded_offline` (tavsiya #7), `expiry_soon` (US-M04-06).

### K3-06 · O · Eksport va QQS filtri

#22 `report-kod` enumiga `ledger-entries`, `cash-history`, `state-report-diffs`, `vat-moves` qo'shilsin (BO-08 eksport, US-M12-03). #2 `doc_type` filtriga `returns|supplier_returns` (US-M02-03).

### K3-07 · O · OCR `doc_type_hint` va natija

#73 `doc_type_hint` enumi: `purchase|return|catalog`; #75 `created_doc_type` ga `products`/`stock_openings` qo'shilsin; `return` — POS qaytarish emas, faqat back-office (izoh).

---

# 7. `spec/02-arxitektura/12-autentifikatsiya-oauth2.md`

### A-01 · K · Ro'yxatdan o'tish (tenant yaratish) endpoint'i yo'q

§20 jadvaliga qo'shilsin: «`/auth/signup` · POST · BFF · `{phone, otp_challenge_id (purpose=signup, verified), password, store_name, business_type}` → bitta tranzaksiyada `05-xavfsizlik` §1.5 provisioning (tenant, `subscriptions(status=trial, 30 kun)`, Egasi membership, 5 rol, standart filial/ombor/kassa, ...) + login cookie; xatolar `OTP_INVALID`, `VALIDATION_ERROR` (telefon allaqachon ro'yxatda), `RATE_LIMITED`.» Shuningdek K3-04'dagi `pay_token` qatori.

---

# 8. `spec/02-arxitektura/05-xavfsizlik-va-audit.md`

### X-01 · Y · Yangi ruxsat kodlari va yetishmayotgan matritsa qatori

§2.1'ga qo'shilsin: `settings.tenant` (M13/M14, do'kon sozlamalari, integratsiya kalitlari, OFD qayta urinish — **faqat Egasi**); `debts.remind` (M08, qarz eslatmasini yuborish); `catalog.manage`, `stock.opening.manage`, `valuation.settings.manage` (13-2 taklifi). §2.2 matritsaga qatorlar: `debts.payment.accept` — Egasi ✓, Menejer ✓, Kassir ✓, Buxgalter ✓ (hozir katalogda bor, matritsada yo'q — Kassir POS-13'da to'lov ololmaydi); `debts.remind` — Egasi ✓, Menejer ✓, Buxgalter ✓; `catalog.manage` — Egasi ✓, Menejer ✓; `stock.opening.manage` — Egasi ✓, Menejer ✓; `valuation.settings.manage` — Egasi ✓, Buxgalter ✓; `settings.tenant` — Egasi ✓.

### X-02 · Y · Egasi o'z do'konida sota olmaydi (founder #1)

§2.2'da Egasida `sales.create`, `shift.open/close`, `returns.create`, `stock.count.create`, `transfer.*`, `purchases.*`, `cash.count.shift`, `accounting.*` — "–". 1–3 xodimli do'konda Egasi ko'pincha o'zi kassada turadi. Tavsiya matni: «**Egasi — barcha tenant ruxsatlarining supersetiga ega** (`platform.admin`dan tashqari), limitlar cheksiz; matritsadagi Egasi ustuni shunga almashtiriladi.» (Founder tasdig'i — pastda.)

---

# 9. `spec/02-arxitektura/14-db-sxema.md`

### B-01 · O · `debt_moves`da `limit_exceeded` va joriy va'da sanasi yo'q

13-1 §4.3 `debt_moves.limit_exceeded=true` deydi — ustun yo'q. Qo'shilsin: `debt_moves.limit_exceeded BOOLEAN NOT NULL DEFAULT false` (+ qisman indeks `WHERE limit_exceeded`); `counterparties.debt_due_date DATE NULL` (yagona joriy va'da sanasi, o'zgaruvchan, audit bilan — `debt_moves` append-only bo'lgani uchun u yerda yangilanmaydi; K1-09).

---

# 10. `spec/02-arxitektura/15-ochiq-savollar-reestri.md` (vazifa №6)

**Umumiy baho:** 41 A va 14 B qarorning ko'pchiligi sog'lom (sanoat standarti, keyin o'zgartirish arzon). Statistika to'g'ri (40 A + 1 A/C, 14 B, 25 C + #53). **C-turdagi stub'larning hech biri kodlashni bloklamaydi** — har birida port/adapter (`FiscalAdapter`, `CloudPrintAdapter`, `EInvoicePort`, `UzQrPort`, `StoragePort`) yoki interim qiymat (hisob kodlari, qo'lda yuklash) bor. Faqat ikki C funksiyani *chiqarishni* (kodni emas) bloklashi mumkin: #40 (CRPT — markirovkalangan tovar sotuvi) va #49 (UzQR — yuridik shaxslar uchun 2026-07-01'dan majburiy; texnik standartsiz UzQR feature-flag ortida, pilot YaTT/QR'siz boshlanishi mumkin). Xavfli standartlar:

### R-01 · Y · #9 "Qarz to'lovi uchun alohida fiskal chek yo'q" — A emas, C

Bu soliq/OFD talqini (ko'p yurisdiksiyada nasiya to'lovi uchun alohida "kredit to'lovi" cheki majburiy), 02-modullar US-M08-04 o'zi "MVP'dan oldin aniqlashtirilsin" deydi. Turi **C** ga o'zgartirilsin: «Kim: buxgalter + OFD operatori (Xat 1'ga savol). Interim: chek chiqarilmaydi, lekin `debt_payment` uchun `FiscalAdapter.issue_credit_payment()` porti stub sifatida qoldiriladi — keyin yoqish migratsiyasiz.»

### R-02 · O · #14 DataMatrix'ni qo'lda kiritish

Qaror matniga qo'shilsin: «faqat **online**, `POST /marking/verify` muvaffaqiyatli bo'lsagina; offline qo'lda kiritilgan kod bilan sotish taqiq» (aks holda 2026-07-01'dagi avtomatik tekshirish talabini chetlab o'tish yo'li bo'ladi).

### R-03 · O · #5 narx tasdig'i — tasdiqlovchi va yo'nalish

«≥10% past — Menejer PIN» → «katalog narxidan **±10%** dan ko'p o'zgarish — **Egasi** tasdig'i (`prices.approve`, 05 §2.2 faqat Egasi); limit `role_permissions.limit_value` (10.00) sifatida». Hozirgi matn 05 matritsasiga zid.

### R-04 · O · #13 UX parametrlari

«Tugma min 44×44 dp» → «POS 48×48, asosiy 56 (08-dizayn §5 ustun); mobil back-office 44». «Chek ekrani 3 soniyadan keyin qaytadi» → «faqat chop/QR **muvaffaqiyatli** bo'lgandan keyin; printer xatosida ekran qoladi (#27)».

### R-05 · O · #12 Chek tili — davlat tili xavfi

«UI tili bo'yicha chek» rus tilini tanlagan kassirda faqat-rus chek chiqaradi — davlat tili talabiga zid bo'lishi mumkin. Xavfsiz standart: «Chek **har doim o'zbek (lotin)** tilida; rus — keyinroq ikkinchi qator sifatida». Founder ro'yxatida.

### R-06 · P · #48 Payment mock

«Mock faqat `ENV != production`, ishga tushishda prod'da mock adapter yuklansa — startup xatosi» qo'shilsin (12-auth §21 "mock yo'q" tamoyili bilan izchil).

### R-07 · O · Reestrga kirmagan, bu qabulda topilgan ochiq qarorlar

Qatorlar qo'shilsin: #81 resurs nomlash kebab/snake (A, C-01 qarori); #82 qator jamini so'mgacha yaxlitlash (C — buxgalter, D-01); #83 Omborchi kirimni o'tkaza oladimi (B, K2-02); #84 fiskal chekdagi summa aniqligi (C — OFD, D-04); #85 B2B nasiya sotuvdan chiquvchi e-faktura avtomatik qoralamasi (A, K1-04); #86 `/install` alohida route (A, E-32 — hal qilindi). Shuningdek #64 (minSdk 23) izohiga: «pilot Android POS'siz — ta'sir yo'q».

---

# 11. `spec/02-arxitektura/08-frontend-arxitekturasi.md`

### F-01 · Y · Pul kutubxonasi va o'rnatish route'i

§4 jadvalidagi "Raqam/pul formatlash" qatori → «`decimal.js` (hisob) + `shared/lib/money` (yaxlitlash, D-01) + `Intl.NumberFormat("uz-UZ")` (faqat ko'rsatish); "frontendda hisoblanmaydi" iborasi olib tashlansin — POS offline hisoblaydi, back-office forma jamlarini ko'rsatadi, yakuniy qiymat server». §6'ga: «`/install` (UX-INSTALL, 09) — iOS'da `display-mode: standalone` bo'lmasa `/pos/*` bloklanadi».

---

# 12. `spec/tekshiruv/00-qarorlar.md`

### Q-01 · O · Uchta yangi qaror yozilsin

| # | Masala | Qaror |
|---|---|---|
| 24 | API nomlash | Yo'l — kebab-case ko'plik; JSON/enum/query/`operation_id` — snake_case (C-01) |
| 25 | Pul | Saqlash/API — o'nlik satr (2/3/4 xona); hisob — decimal kutubxona, yaxlitlash `shared/lib/money` = backend; ko'rsatish — butun so'mga ROUND_HALF_UP, faqat ko'rsatish uchun; fiskal/QQS hisobotlari — 2 xona (D-01) |
| 26 | iOS o'rnatish | Alohida ochiq route `/install`, BO-21 ⑥ shu komponentni ichiga oladi; iOS o'rnatilmagan holatda POS bloklanadi (E-32) |

---

## Qarorlarga rioya (vazifa №4) — qisqa jadval

| Qaror | Holat | Band |
|---|---|---|
| Yagona 99k + 39k qo'shimcha kassa | ✓ BO-19; API addon/AI birligi | E-26, E-21 |
| 24 soat imtiyoz → to'liq lokaut, to'lov sahifasi + SMS-OTP eksport | ✗ imtiyoz banneri yo'q; BO-19 lokautda "ochiq" deb xato | E-04 |
| iOS — o'rnatilgan PWA + bulut print | ✗ POS-04'da yo'q; o'rnatish route'i | E-12, E-32 |
| Rol limitlari 5% / 100 000 / 50 000 | ✓ POS-02/05/14, BO-11 (lekin shaxsga bog'langan) | E-20 |
| AI-03 95/90/80 + odam tasdig'i | ~ tasdiq bor, chegaralar yozilmagan | E-18 |
| Markirovka offline (narx ma'lum — sotish; qaytarish online; o'z filiallari ko'chirish offline) | ✓ POS-02/05/09; ✗ POS-08 qabul offline va qo'lda "MXIK" | E-13, E-16 |
| Karta qo'lda + `terminal_ref` | ✓ (enum `card_manual` → `card`) | E-01 |
| Faqat Faktura.uz | ✓ BO-14 | — |
| Yopilgan oy qayta ochilmaydi | ✗ ekranda oy yopish/xabar yo'q | E-09 |
| Qarz: yagona va'da sanasi | ~ `dueDays` kunlar, API/DB'da sana yo'q | E-17, K1-09, B-01 |
| Shubhali belgi — faqat Egasi | ✗ kechish bilan aralashgan | E-05 |
| 60 kunlik eslatma | ✗ ekranda yo'q | E-05, K3-05 |

---

## Founder ko'rib chiqishi kerak (B-qarorlar, 8 ta)

1. **Egasi barcha huquqlarga egami** (reestr #1, X-02) — hozir Egasi sotuv/smena/qaytarish qila olmaydi; tavsiya: ha, superset.
2. **Chek tili** (#12, R-05) — tavsiya: har doim o'zbek (lotin), rus ixtiyoriy keyinroq (yurist bilan).
3. **Qarz to'lovi uchun fiskal chek** (#9, R-01 — A'dan C/B'ga) — buxgalter/OFD javobigacha "yo'q" bilan davom etish riskini qabul qilasizmi.
4. **Bir tenant = bir yuridik shaxs** (#38) — O'zbekistonda bitta egasi bir nechta YaTT/MChJ orqali ishlashi keng tarqalgan; segment/narxlashga ta'sir qiladi.
5. **Segment >70% aylanma solig'i to'lovchi** (#26) — QQS vs aylanma funksiyalari ustuvorligini belgilaydi; pilot tanlovi.
6. **MoSCoW tasdig'i** (#23) — 06'da US-M03-02, US-M14-02, US-M08-08, US-M17-05 bir vaqtda "Should/Could" va "MVP'dan keyin" deb yozilgan, 09/13 esa US-M03-02 uchun ekran/API yozgan — qamrovni bir ma'noli qiling.
7. **SMS provayder — Eskiz.uz** (#45) — shartnoma va "sender name" ro'yxati yuridik shaxs nomidan; imzolovchi (tavsiya #16 bilan bog'liq).
8. **Jamoa va muddat** (#70) — sprint hajmi shu bilan belgilanadi.

*Qolgan B-qarorlar (#7, #15, #21, #52, #65, #77, #79) — xavfsiz standart, founder vaqtini talab qilmaydi; #21 (AI-10) MVP'da Won't bo'lgani uchun amaliy ahamiyatsiz.*

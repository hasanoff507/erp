# Requirements traceability: accept-gate verdicts

I checked every item against the whole spec with grep, not only the files the reviewer cited. Out of 33 items, 18 are accepted (QABUL), 13 are partly accepted (QISMAN) and 2 are rejected (RAD). The `ai_requests.prompt_version` and `cost_uzs` columns are already in `01-malumotlar-modeli.md` §10, so that item is closed with no change.

I also found 3 extra gaps while checking:
- **X1:** there is no document type and no posting rule for opening stock (US-M04-04). Section 2.13 covers only opening debts.
- **X2:** `vat_moves` has no `status` column, but `02-provodka` §4.1 relies on a `pending` status for red e-fakturas.
- **X3:** the cron list in `09-backend` is missing the subscription reminders and the grace→restricted switch (US-M17-03), and the daily Telegram report (US-M18-02).

## Verdicts

| # | Verdict | Why | MVP |
|---|---|---|---|
| T1 | QABUL | Real conflict: 06 §1.1 says Should is inside the MVP, but backlog item 4 puts consolidation after MVP. US-M14-03 (Must) is in no sprint either. Consolidation is cheap because every ledger entry already carries `branch_id`, and the Pro plan sells branches. Decision: build it in sprint 4. | MVP-da shart |
| T2 | QABUL | AI-03 is "Could, inside MVP" in 06, but the backlog defers it. Fix the documents to say it is deferred. | Docs: shart; feature: keyin |
| T3 / S1 | QABUL | Confirmed: there is no US, table, posting rule or screen for returns to suppliers. Returning expired goods to the distributor happens every day in grocery shops. | MVP-da shart |
| T4 | QISMAN | Confirmed: no `discount_rules` table and no cache entry. The feature is in no sprint, so defer it explicitly. Add the model row now. | keyin |
| T5 | QISMAN | Confirmed: no `pending_approval` state and BO-16 has no price-change type. This is a Should; build it in sprint 6. | keyin (6-sprint) |
| T6 | QABUL | No screen lists transfers. The 72-hour limit for marked goods is a legal rule. | MVP-da shart (cheap) |
| T7 | QABUL | 15 permission codes from §2.1 are missing from the §2.2 matrix. Seeding in phase 0 needs the full matrix. | MVP-da shart |
| T8 | QABUL | The cron list has no low-stock check. Also fixes X3. | MVP-da shart |
| T9 | QABUL | There is no `import_jobs` table. Also fixes X1 (opening stock). | MVP-da shart |
| T10 | QABUL | Confirmed: sprint 2 says "M05 … Should", but 06 marks it Must. | shart (trivial) |
| T12 | QABUL | SMS OTP is needed for sign-up in sprint 1, but SMS is 9th in the build order and has no sprint task. | MVP-da shart |
| T13 | QABUL | US-M16-01 (Must) needs approval of large cash withdrawals, and BO-16 lacks M16. | MVP-da shart |
| T14 | QISMAN | The backlog already has a "check with accountant" task. Point it at the checklist instead of copying all 10 items into the backlog. | shart |
| T15 | QISMAN | Merged with T4 into one row: shop settings (scale barcode format, discount rules, subscription status) are missing from the offline cache list. | shart |
| T16 | QABUL | It is only an open question today. Make it a phase-0 legal task, together with S7. | shart |
| T17 | QABUL | Merged into the 06 deferral list. | keyin |
| T18 | QABUL | BO-07 and BO-10 do not show pending VAT credit from red e-fakturas. Also fixes X2. | MVP (5-sprint) |
| T19 | QISMAN | Real: Batch API is used in cost estimates but there is no method for it. It is only a cost saving. | keyin |
| T20 | QABUL | §5 has a rule for the debt limit but not for return or discount limits when offline. | MVP-da shart |
| S2 | QISMAN | Add an edge case and an open question only. | keyin |
| S3 | QISMAN | Add rules for supplier bonus goods, "2+1" promos and gifts. The VAT treatment goes to the accountant. | rules: shart |
| S4 | RAD | Switching between two legal entities already works: BO-01 has "tenant/filial tanlash", and `users`/`memberships` let one person work in several tenants. A combined view across tenants is outside the MVP; I added one line to the post-MVP list. | — |
| S5 | QABUL | `stock_lots.expiry_date` exists but `receipt_lines` has no field to fill it. Write-offs have a posting rule (2.12) but no US. | field and write-off: shart; alert: 6-sprint |
| S6 | QISMAN | Already an open question (05 §7.3, item 10). Add US-M17-05 as Could. | keyin (before the first paying customer leaves) |
| S7 | RAD | Already covered by 04-offline §6, its Open question 1, and 08-kamchiliklar #36. Only the legal task is new, and it is merged into T16. | — |
| S8 | QABUL | A stolen device that is offline keeps salted hashes of 4-digit PINs, which are easy to brute-force. Force PIN reset on revoke and add a device screen. | MVP-da shart |
| S9 | QABUL | Covered by the `sales.void` matrix row (T7) plus a new audit event. | MVP-da shart |
| S10 | QISMAN | For the MVP, the rule is: close the shift and open a new one. Handover inside an open shift comes later. | rule: shart |
| S11 | QABUL | Mark reprints as "NUSXA" and log them in the audit log. No limit. | MVP-da shart |
| S12 | QISMAN | One-line rule. | shart |
| S13 | QISMAN | One line of UI text. | shart |

## Exact changes, grouped by file

### `spec/01-mahsulot/02-modullar-talablari.md`

**1. M07: add after US-M07-04 (T3):**

**US-M07-05** *(2026-10-14: qo'shildi)*: Omborchi/Menejer sifatida muddati o'tgan, buzilgan yoki ortiqcha tovarni yetkazib beruvchiga qaytarishni istayman.
- Given tovar shu yetkazib beruvchidan kirim qilingan (US-M07-02), When Omborchi "Yetkazib beruvchiga qaytarish" hujjatini yaratadi (yetkazib beruvchi, asl kirim hujjati, tovar, miqdor, sabab), Then ombor qoldig'i (M04) kamayadi va yetkazib beruvchiga qarzimiz (US-M08-11) shu summaga kamayadi; qarz bo'lmasa — yetkazib beruvchi bizga qarzdor bo'ladi yoki pulni naqd/bank orqali qaytaradi.
- Given asl kirim QQS bilan bo'lgan, When qaytarish o'tkaziladi, Then kiritiladigan QQS (M10) shu qism bo'yicha kamayadi; yetkazib beruvchidan tuzatuvchi e-faktura talab qilinishi — **ochiq savol**.
- Given tovar markirovkalangan, When qaytariladi, Then Asl belgisi tizimidagi mos operatsiya — **ochiq savol** (M02 bilan bir xil).

**2. M07, Chekka holatlar: add (S3):**
- Yetkazib beruvchi bonus tovari (masalan "10 + 1 tekin") — kirim qatori **0 narx** bilan alohida partiya sifatida yoziladi; AVECO o'rtacha narxi shunga mos pasayadi.

**3. M04: add after US-M04-05 (S5):**

**US-M04-06** *(2026-10-14: qo'shildi)*: Omborchi/Egasi sifatida yaroqlilik muddati yaqinlashgan tovarni oldindan bilishni va muddati o'tganini hisobdan chiqarishni istayman.
- Given kirimda partiya uchun yaroqlilik muddati kiritilgan (ixtiyoriy maydon), When muddatga 7 kun qolganda (taxmin, sozlanadi), Then Egasi/Menejerga ro'yxat (tovar, partiya, qoldiq, muddat) M18 orqali boradi va BO-03'da belgi ko'rinadi.
- Given tovar muddati o'tgan/buzilgan yoki bepul berilgan (namuna, sovg'a), When Omborchi "Hisobdan chiqarish" hujjatini sabab bilan yaratadi, Then qoldiq kamayadi va tannarx xarajatga yoziladi (`02-provodka-qoidalari.md` 2.12); bepul berishning QQS oqibati — buxgalter tasdig'i (ochiq savol). Yetkazib beruvchi qaytarib olsa — US-M07-05.

**4. US-M04-04: append a bullet (T2):**
- *(2026-10-14)* (3)-yo'l (AI-03) — MVP'dan keyin (`02-arxitektura/11-backlog.md`); MVP'da (1) va (2) mavjud. Kiritilgan qoldiq "boshlang'ich qoldiq" hujjati sifatida o'tkaziladi (chek/faktura yo'q, `02-provodka-qoidalari.md` 2.21).

**5. M03, Chekka holatlar: add (S3):**
- "2+1" turidagi aksiya — US-M03-02 qoidasi sifatida (uchinchi donaga 100% chegirma), alohida "bepul tovar" hujjati emas; QQS chegirmadan keyingi summadan (taxmin, buxgalter tasdig'i).

**6. US-M08-06: add a bullet (S13):**
- Har bir qarz qatorida holat: ochiq / qisman yopilgan (qolgan summa) / to'liq yopilgan — qisman to'lov qaysi qarz(lar)ni yopgani `debt_payments.allocations` bo'yicha (eng eski qarzdan, US-M08-09) ko'rsatiladi.

**7. US-M09-02: append to Then (T5):**
"… kuchga kirmaydi; o'zgarish `pending_approval` holatida BO-16 navbatiga tushadi, rad etilsa sabab yoziladi."

**8. M09, Chekka holatlar: add (S12):**
- Onlayn ochiq chek davomida narx o'zgarsa — chekka allaqachon qo'shilgan qator narxi qo'shilgan paytdagidek qoladi, keyin qo'shilgan qator yangi narxni oladi (offline'dagi "qotirish" qoidasi bilan bir xil).

**9. M01, Chekka holatlar: add (S9, S11, S2):**
- To'lovdan oldin qator o'chirilsa yoki chek bekor qilinsa (`sales.void`) — fiskal chek yo'q, lekin bekor qilingan qatorlar va summa `sale.draft_voided` voqeasi bilan audit uchun serverga yuboriladi; smena hisobotida bekor qilishlar soni va summasi ko'rsatiladi.
- Chekni qayta chop etish — nusxada "NUSXA" belgisi, har qayta chop etish audit jurnaliga yoziladi (kim, qachon, qaysi chek); son cheklanmaydi.
- Chek bilan sotilgan tovarga keyinroq yuridik shaxs mijoz e-faktura so'rasa — shu chekka bog'langan chiquvchi e-faktura yaratiladi (`einvoices.related_doc`), QQS ikkinchi marta hisoblanmaydi; qonuniy tartib — **ochiq savol 12**.

**10. M16, Chekka holatlar: replace the line "Bir smenada kassir almashsa — …" with (S10):**
- Bir smenada kassir almashsa (masalan tushlik) — MVP'da joriy smena yopiladi (POS-15 sanash + Z-hisobot) va yangi kassir yangi smena ochadi; ochiq smena ichida topshirish — MVP'dan keyin.

**11. M17: add after US-M17-04 (S6):**

**US-M17-05** *(2026-10-14: qo'shildi, Could)*: Egasi sifatida xizmatdan chiqsam ham barcha ma'lumotlarimni olib ketishni istayman.
- Given tenant `restricted` yoki `closed` holatda, When Egasi "To'liq eksport"ni bosadi, Then barcha ma'lumotnomalar, hujjatlar va registrlar CSV (har jadval alohida) + asosiy hisobotlar PDF bitta ZIP faylda yuklanadi; amal audit jurnaliga yoziladi.
- Given tenant `closed`, Then ma'lumot kamida 90 kun (taxmin) eksport uchun saqlanadi; keyingi o'chirish tartibi huquqiy maslahatdan keyin (buxgalteriya hujjatlari muddati kamida 5 yil (O'RQ-404, 29-modda)).

**12. Ochiq savollar: add:**
- 12. Fiskal chek bilan sotilgan tovarga keyinroq e-faktura berish ruxsati va tartibi (M01).

### `spec/01-mahsulot/04-ekranlar-va-ux.md`

- **BO-16 row:** change the Modul column to `M02, M03, M08, M09, M16`. Change the request types to "chegirma/qaytarish/nasiya/**narx o'zgarishi (US-M09-02)**/**limitdan katta pul olish (US-M16-01)**". (T5, T13)
- **BO-03 row, Asosiy elementlar, append (T6, S5):** "; **'Ko'chirishlar' tabi** (US-M06-03): holat (yo'lda / qabul qilindi / farq bilan), yuborilgan vaqt, markirovkali tovar uchun 72 soat hisoblagichi, kechikkanlar qizil; yaroqlilik muddati yaqin partiyalar belgisi (US-M04-06)".
- **BO-04 row:** append "**'Yetkazib beruvchiga qaytarish'** (US-M07-05)". After "AI-03: …" add "(MVP'dan keyin)". (T3, T2)
- **BO-07 row, append (T18):** "; **kutilayotgan QQS krediti** — qizil e-fakturalar bo'yicha to'lovgacha hisobga olinmagan QQS summasi va davr ulushi (VM 830, ≤10%), US-M10-03".
- **BO-10 row, QQS tab, append (T18):** "ichki ustunda 'kutilayotgan kredit' alohida qator".
- **BO-11 row, append (S8):** "; **'Qurilmalar' tabi**: kassa, oxirgi sinxron vaqti, 'Bekor qilish' (yo'qolgan/o'g'irlangan) — `02-arxitektura/04-offline-sync.md` §9".
- **POS-04 row:** change "Qayta chop etish" to "Qayta chop etish ('NUSXA' belgisi, audit)". (S11)
- **POS-02 mockup note:** add "BEKOR — qator o'chirish / chekni bekor qilish (`sales.void`), audit voqeasi". (S9)

### `spec/01-mahsulot/06-mvp-chegarasi.md`

- **Asosiy xulosa 2:** change "4 ta AI funksiya (AI-01, AI-03, AI-05, AI-06) MVP ichida" to "3 ta AI funksiya (AI-01, AI-05, AI-06) MVP ichida; AI-03 (OCR) — MVP'dan keyin (`02-arxitektura/11-backlog.md`)". (T2)
- **§1.2, AI-03 row:** change MoSCoW to "**Could → MVP'dan keyin**". Add to Sabab: "; pilotdan keyin (backlog)". (T2)
- **§1.1 table:**
  - M07 Should: add "US-M07-05 (yetkazib beruvchiga qaytarish)".
  - M04 Should: add "US-M04-06 (yaroqlilik muddati, hisobdan chiqarish)".
  - M17 Could: add "US-M17-05 (to'liq eksport)".
- **§1.1, after the "Izoh" paragraph, add (T1, T4, T17):**
  *MVP'dan keyinga surilgan hikoyalar (2026-10-14, `11-backlog.md` bilan muvofiq): US-M03-02 (avtomatik chegirma qoidasi), US-M14-02 (narx/chegirma nusxalash), US-M08-08 (mijozga SMS/Telegram), US-M04-04 (3)-yo'l (AI-03), US-M17-05 (to'liq eksport). Qolgan barcha Should/Could hikoyalar (shu jumladan US-M14-01, US-M04-03 — 4-sprint) MVP sprintlarida.*
- **§1.3 Won't, onboarding row:** after "(3) AI-03 yordamida …" add "(MVP'dan keyin)".

### `spec/02-arxitektura/01-malumotlar-modeli.md`

- **§3 `devices`:** add `revoked_at, revoked_by`. (S8)
- **§4: new row (T4):**
  `discount_rules` | tenant_id, name, scope (`product`/`category`/`all`), target_ids[], kind (`percent`/`amount`/`n_plus_m`), value, branch_ids[] (bo'sh = hammasi), valid_from, valid_to, priority, archived_at | US-M03-02 (MVP'dan keyin); bitta chek qatoriga eng yuqori `priority`li bitta qoida (taxmin)
- **§6 table:**
  - In the `goods_receipts` row, change the line items to `receipt_lines` (product, qty, cost, vat, expiry_date (ixtiyoriy)). (S5)
  - In the `write_offs` row, change the line items to `write_off_lines` (product, lot_id, qty, reason: `expired`/`damaged`/`gift`/`other`). (S5, S3)
  - New row (T3): `supplier_returns` | `supplier_return_lines` (receipt_line_id, lot_id, qty, cost, vat) | M07 | qoldiq − (asl partiyadan), yetkazib beruvchiga qarz − (yoki debitorlik), kiritiladigan QQS −
  - New row (X1): `stock_openings` (boshlang'ich qoldiq) | `opening_lines` (product, qty, unit_cost, expiry_date) | M04 | yangi partiya, qoldiq + (chek/faktura yo'q, US-M04-04)
- **§7 `vat_moves` (X2, T18):** add `status (`posted`/`pending`)`. In the Balans column, add "qizil faktura to'lovgacha `pending` (`02-provodka-qoidalari.md` 4.1)".
- **§8 new rows (T5, T3, S9):**
  - Narx o'zgarishi (`price_changes`) | `draft` → `pending_approval` (limitdan katta, US-M09-02) → `posted` / `rejected`
  - Yetkazib beruvchiga qaytarish | `draft` → `posted` → (`cancelled` — teskari hujjat bilan)
  - In the Chek row, append: "; `draft` bekor qilinsa → `sale.draft_voided` audit voqeasi (registrga ta'sirsiz)"
- **§9 `marking_codes.status`:** add `returned_to_supplier`.
- **§10 new row (T9):**
  `import_jobs` | tenant_id, kind (`products`/`opening_stock`/`opening_debts`), attachment_id, status (`uploaded` → `validated` → `committed` / `failed`), total_rows, ok_rows, errors JSONB (qator, maydon, xato kodi), created_by | US-M04-04, US-M08-07; commit bitta tranzaksiyada `stock_openings`/`debt_openings` yaratadi

### `spec/02-arxitektura/02-provodka-qoidalari.md`

**Warning block, append items 11 and 12:**
11. Yetkazib beruvchiga qaytarish (2.20) va bepul olingan/berilgan tovar (bonus, sovg'a, "2+1") ning QQS va hisob tartibi.
12. Boshlang'ich tovar qoldig'ida (2.21) qarshi hisob sifatida 8720 to'g'riligi.

**New §2.20 Yetkazib beruvchiga qaytarish (`supplier_return`) (T3):**

| # | Dt | Kt | Summa | Analitika |
|---|---|---|---|---|
| 1 | 6010 | 2910 | Qaytarilgan tovar tannarxi (FIFO — asl partiya; AVECO — joriy `avg_cost`) | yetkazib beruvchi, mahsulot, partiya |
| 2 | 6010 | 4410 | Shu qismga to'g'ri keladigan kiritiladigan QQS (asl kirim QQS bilan bo'lsa) | tax_type=QQS, yetkazib beruvchi |
| 3 (farq bo'lsa) | 6010 yoki 9430 | 9430 yoki 6010 | Faktura narxi bilan tannarx farqi (AVECO'da) — **taxmin** | hujjat |

*Izoh:* kirim allaqachon to'langan bo'lsa, 6010 debet qoldig'i hosil bo'ladi (yetkazib beruvchi bizga qarzdor); pul qaytarilganda `Dt 5010/5110 / Kt 6010`. Asl faktura "qizil" va QQS hali `pending` bo'lsa, 2-qator yozilmaydi va tegishli `vat_moves` bekor qilinadi. `vat_moves(kind=input)` manfiy summa bilan.

**New §2.21 Boshlang'ich tovar qoldig'i (`stock_openings`) (X1):**

| # | Dt | Kt | Summa |
|---|---|---|---|
| 1 | 2910 | 8720 | Kiritilgan tannarx (yangi partiya) |

*QQS yozilmaydi. 8720 — taxmin, 2.13 bilan bir xil (ogohlantirish 12-band).*

**§2.12, add:** "Sabab `gift` (bepul berish): QQS oqibati — ogohlantirish 11-band."

### `spec/02-arxitektura/04-offline-sync.md`

**§1 table, new row (T4, T15):**
Do'kon sozlamalari va qoidalar (`tenants.settings`: tarozi shtrix-kod formati va uning versiyasi; faol `discount_rules`; obuna holati `tenants.status`) | `settings` | Login/snapshot bilan | Delta; tarozi formati versiyasi o'zgarsa majburiy pull

**§2 `type` list:** add `sale.draft_voided` (audit, registrga ta'sir yo'q) and `receipt.reprinted`. (S9, S11)

**§5 table, new row (T20):**
Qaytarish yoki chegirma limiti offline oshgan | Sotuvdan farqli — **lokal Menejer/Egasi PIN'isiz yakunlanmaydi** (BO-16 offline ishlamaydi); PIN bilan tasdiqlangan bo'lsa server qabul qiladi va qayta tekshiradi, `limit_exceeded=true` bayrog'i + M18 xabar | `05-xavfsizlik-va-audit.md` §2.3

**§9, add a bullet (S8):**
- Qurilma bekor qilinganda shu qurilmada oxirgi 30 kun (taxmin) ichida PIN bilan kirgan barcha xodimlarning PIN'i serverda bekor qilinadi va keyingi kirishda yangi PIN majburiy (lokal 4 raqamli PIN hashlari offline buzilishi oson). Ro'yxat va "Bekor qilish" — BO-11 "Qurilmalar" tabi. Ochiq savol 3 qisman hal qilindi.

### `spec/02-arxitektura/05-xavfsizlik-va-audit.md`

**§2.1, new codes (T3, S5):**
- `purchases.return` | M07 | Yetkazib beruvchiga qaytarish | —
- `stock.writeoff` | M04 | Hisobdan chiqarish | summa (taxmin)

**§2.2 matrix, add rows (T7, S9).** Columns are Egasi | Menejer | Kassir | Omborchi | Buxgalter:

| Ruxsat | Egasi | Menejer | Kassir | Omborchi | Buxgalter |
|---|---|---|---|---|---|
| `sales.void` | ✓ | ✓ | ✓ (audit) | – | – |
| `cash_register.manage` | ✓ | ✓ | – | – | – |
| `discount.rule.manage` | ✓ | ✓ | – | – | – |
| `stock.view` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `stock.writeoff` | ✓ | ✓(limit) | – | ✓(limit) | – |
| `purchases.return` | – | ✓ | – | ✓ | ✓ |
| `labels.print` | ✓ | ✓ | – | ✓ | – |
| `accounting.period.close` | – | – | – | – | ✓ |
| `reports.sales.view` | ✓ | ✓ | – | – | ✓ |
| `reports.export` | ✓ | ✓ | – | – | ✓ |
| `expenses.approve` | ✓ | – | – | – | – |
| `cash.deposit` | ✓ | ✓ | ✓ | – | – |
| `cash.count.shift` | – | ✓ | ✓ | – | – |
| `notifications.manage` | ✓ | ✓ | – | – | – |
| `telegram.link` | ✓ | ✓ | – | – | – |
| `ai.chat.use` | ✓ | ✓ | – | – | ✓ |
| `ai.ocr.use` | ✓ | ✓ | – | ✓ | ✓ |

**§1.2, add (S8):** "Qurilma bekor qilinganda unda kirgan xodimlarning PIN'i majburiy almashtiriladi (`04-offline-sync.md` §9)."

**§6.1, add (S9, S11, S8):**
- To'lovdan oldin chek qatori/chekni bekor qilish (`sale.draft_voided`), chekni qayta chop etish (`receipt.reprinted`), qurilmani bekor qilish va PIN majburiy almashtirish.

**§7.3, last bullet:** append "— mahsulot talabi: US-M17-05 (MVP'dan keyin)".

### `spec/02-arxitektura/07-ai-qatlami.md` (T19, keyin)

- In §1, change "Uch metod" to "To'rt metod".
- Add a row:
  `submit_batch` | `submit_batch(items: list[AiBatchItem]) -> batch_id`; natija `get_batch_results(batch_id)` | Shoshilinch bo'lmagan so'rovlarni Batch API orqali (−50% narx); `FakeProvider`/`CliProvider`da oddiy `complete`ga tushadi | AI-05, AI-06 (MVP'dan keyin, ixtiyoriy)

### `spec/02-arxitektura/09-backend-arxitekturasi.md` (T8, X3)

In the `cron.py` comment and the §4 cron list, add:
- kam qoldiq tekshiruvi (US-M04-02: `stock_balances.qty <= products.min_stock`, kuniga 1 marta; bir tovar uchun kuniga bitta xabar)
- yaroqlilik muddati (US-M04-06)
- obuna eslatmalari va `grace` → `restricted` o'tishi (US-M17-03)
- kunlik Telegram hisobot (US-M18-02)

### `spec/02-arxitektura/11-backlog.md`

**Phase 0:**
- Accountant row (T14): change the Natija to "Tasdiqlangan hisoblar rejasi + `02-provodka-qoidalari.md` ogohlantirish blokidagi 12 band bo'yicha yozma javoblar jadvali".
- New row (T16, S7):
  **Tashqi:** huquqiy maslahat — (a) obuna kechikkanda kassani to'xtatmaslik (US-M17-03), (b) 48 soatdan keyin yangi sotuvni bloklamaslik (`04-offline-sync.md` §6), (c) markirovkalangan tovarni offline sotish (§7), (d) chekdan keyin e-faktura berish | Yozma huquqiy xulosa (5-sprintdan oldin)

**Sprint 1 (T12, T9, X1, T1), add:**
- SMS adapter (OTP, `03-integratsiyalar.md` §10) — 0-bosqichda tanlangan provayder bilan; tanlanmaguncha dev/staging'da `FakeSms`.
- US-M04-04 import `import_jobs` orqali (yuklash → tekshirish/xatolar ro'yxati → tasdiqlash) va boshlang'ich qoldiq (`stock_openings`).
- US-M14-03 yangi filial qo'shish.

**Sprint 2 (T10, T3, S5, T6):**
- Change "M05 inventarizatsiya (Should bo'lsa ham posting sinovi uchun foydali)" to "M05 inventarizatsiya (Must)".
- Add: "US-M07-05 yetkazib beruvchiga qaytarish; US-M04-06 hisobdan chiqarish + yaroqlilik muddati maydoni; BO-03 'Ko'chirishlar' tabi (US-M06-03)."

**Sprint 3 (T13, S8, S9, S11), add:**
- BO-16 (M02/M03/M08/M16 turlari); BO-11 qurilmalar va bekor qilish; `sale.draft_voided`, qayta chop etish auditi.

**Sprint 4 (T1, T8), add:**
- Filiallar bo'yicha va jami ko'rinish (US-M14-01, US-M04-03); kam qoldiq ogohlantirishi (US-M04-02).

**Sprint 5 (T18), add:**
- US-M10-03 kutilayotgan QQS krediti (BO-07/BO-10).

**Sprint 6 (T5, S5), add:**
- US-M09-02 narx tasdiqlash (BO-16); yaroqlilik muddati ogohlantirishi (M18).

**"MVP'dan keyin" list:**
- Item 2: change to "AI-03 (US-M04-04 (3)-yo'l) …".
- Item 4: remove "filiallar konsolidatsiyasi".
- New item: "US-M03-02 avtomatik chegirma qoidalari; US-M14-02 nusxalash; US-M17-05 to'liq eksport (birinchi pullik mijoz chiqib ketishidan oldin); ochiq smena ichida kassir topshirish; bitta egasining bir nechta tenanti uchun umumiy ko'rinish; AI Batch (`submit_batch`)."

**Ochiq savol 4:** append "(0-bosqich huquqiy maslahat qatoriga ko'chirildi)".

**ACCEPT natijasi: `spec/02-arxitektura` implementatsiya review (ma'lumotlar modeli, provodka, sync) — 22 topilma**

Natija: 17 QABUL, 5 QISMAN (boshqa yechim bilan), RAD yo'q. Fayllar o'zgartirilmadi — faqat shu hisobot yozildi.

Texnik qabul (`qabul-2-texnik.md`) qarorlari bilan moslashtirildi:
- POS hujjatlari faqat outbox orqali `POST /sync/push` bilan yuboriladi; `Idempotency-Key` faqat back-office REST uchun.
- Tenant konteksti `tenant_transaction()` ichida `set_config('app.tenant_id', :tid, true)` bilan o'rnatiladi, `autobegin=False`.
- Navbat — SAQ.
- 401 bo'lsa qayta kiriladi, outbox o'chirilmaydi.
- Frontend UUIDv7 — `uuid` paketining `v7()` funksiyasi.
- Buxgalteriya yozuvlari kamida 5 yil saqlanadi (O'RQ-404, 29-modda).

Bu topshiriqlar bilan bir xil bo'lgan tahrirlar bu yerda takrorlanmaydi, faqat havola beriladi.

Review'dan tashqari topilgan qo'shimcha nuqsonlar:
- **(Q1)** `fiscal_receipts` jadvalida `tenant_id` yo'q (01:129). RLS testi bu jadvalda yiqiladi.
- **(Q2)** 09:159 o'z-o'ziga zid: "`reverse()` yangi hujjat yaratmaydi", lekin keyingi gapda "teskari hujjatga `reversed_by_id` orqali bog'lanadi" deyilgan.
- **(Q3)** 02:126 supplier_payment uchun "2.12-bo'lim"ga havola qiladi. To'g'risi — 2.16.
- **(Q4)** `outbox_jobs.kind` ro'yxatida 03-faylda ishlatilgan `einvoice_accept`, `ettn_send`, `marking_verify`, `state_report_reminder` turlari yo'q (03:193, 03:441, 03:665).
- **(Q5)** `idempotency_keys` jadvali 01-faylda umuman yo'q. U faqat 09:199 da tilga olingan.
- **(Q6)** `units` global jadval: unda `tenant_id` yo'q va u RLS istisnolar ro'yxatiga kirmagan. `users` bilan bir xil muammo.

---

## VERDIKTLAR

**1. QABUL — hujjat sarlavhasi ikki xil**

01:22 da `created_by`, `reversed_by_id` turibdi, 01:73 da esa `author_id`, `reversal_of_id`, `cancelled_at`. 09:159 da `reversed_by_id`, 02:298 da `reversal_of_id` ishlatilgan. Shu bilan birga 09:159 "yangi hujjat yaratmaydi" ham deydi (Q2).

Qaror (MVP uchun eng sodda yo'l):
- Bekor qilish alohida "teskari hujjat" yaratmaydi.
- Asl hujjat `cancelled` holatiga o'tadi va `cancelled_at`, `cancelled_by`, `cancel_reason` maydonlari to'ldiriladi.
- Registrlarga storno qatorlar yoziladi: `doc_id` asl hujjatni ko'rsatadi, `reversal_of_id` esa teskari qilinayotgan asl **registr qatorini** ko'rsatadi.
- `reversed_by_id` va hujjat darajasidagi `reversal_of_id` olib tashlanadi.
- Muallif maydoni bitta nom bilan: `created_by`.

**2. QABUL — fiskal chek raqamini kim beradi**

01:157 bo'yicha raqamni qurilma beradi. 04:84, 04:138–139 va 04:164 da esa server `receipt_seq` qaytaradi. 03:83 ham "qurilmada" deydi.

Qaror:
- `receipt_seq`ni qurilma beradi. U outbox `seq` bilan bir Web Lock ichida, `payload.fiscal.receipt_seq` sifatida yoziladi.
- Server raqamni o'zgartirmaydi, faqat tekshiradi: `UNIQUE (tenant_id, cash_register_id, shift_id, receipt_seq)`. Takror kelsa — `rejected RECEIPT_SEQ_CONFLICT`, `retryable:false`.
- Raqamlardagi uzilishlar smena yopilganda aniqlanadi.
- 04 Ochiq savol 4 quyidagi qoida bilan yopiladi: **bitta smena — bitta qurilma** (`shifts.device_id` qat'iy).

**3. QABUL — 09 §2.2 dagi FIFO misoli noto'g'ri**

Misoldagi narx QQS'siz olingan, 02:67 esa narxlar QQS bilan saqlanadi deydi. Ledger'da 6410 qatori yo'q. Bundan tashqari naqd to'lovda 120 000, nasiyada 134 400 chiqadi — bir xil chek uchun ikki xil summa. Qayta hisoblandi:

| Ko'rsatkich | Hisob | Natija |
|---|---|---|
| Chek summasi (QQS bilan) | 10 × 12 000 | 120 000,00 |
| QQS | 120 000 × 12/112 = 12 857,142857… | 12 857,14 |
| Sof daromad | 120 000,00 − 12 857,14 | 107 142,86 |
| Tannarx (COGS) | 5 × 9 500 + 5 × 9 800 = 47 500 + 49 000 | 96 500 (Lot-2'da 3 kg qoladi) |
| Yalpi foyda | 107 142,86 − 96 500,00 | 10 642,86 |

To'lov turi qanday bo'lishidan qat'i nazar, kassa yoki qarz harakati 120 000 ga teng.

**4. QABUL — AVECO misoli**

Hisob:
- `avg_cost` = 1 250 000 / 150 = 8 333,3333… → 4 xona aniqlikda (02:304) **8 333,3333**.
- COGS = 120 × 8 333,3333 = 999 999,996 → **1 000 000,00**.
- Qoldiq = 30 × 8 333,3333 = 249 999,999 → **250 000,00**.
- Jami: 1 000 000 + 250 000 = 1 250 000, ya'ni balans mos.

Hozirgi matndagi 999 999,60 summasi 2 xonali o'rtacha narxdan (8 333,33) olingan, bu esa 02:304 qoidasiga zid.

Qo'shimcha qoida: ombordagi qoldiq qiymati "qty × avg" ko'paytmasi bilan emas, "eski qiymat − COGS" ayirmasi bilan yuritiladi. Shunda yaxlitlash xatosi to'planib bormaydi.

**5. QABUL — worker va scheduler'da tenant konteksti**

09-faylda bu umuman aniqlanmagan. `qabul-2` #2 helper'ni beradi; bu yerda uning worker va scheduler'dagi qo'llanishi belgilanadi:
- Har bir job'ning birinchi argumenti majburiy `tenant_id`.
- Job tanasi `tenant_transaction()` ichida bajariladi. Job `tenant_id`'siz kelsa, xato beradi.
- Scheduler'dagi cron hech qachon biznes so'rovini bevosita bajarmaydi. U `SECURITY DEFINER` funksiyasi `list_active_tenant_ids()` orqali tenantlar ro'yxatini oladi va har bir tenant uchun alohida job qo'yadi.

RLS testlariga 3 ta holat qo'shiladi (O'ZGARISHLAR → 09, 05).

**6. QABUL — `users` jadvalida `tenant_id` yo'q**

`users` global jadval (telefon raqami global miqyosda unique).

Qaror:
- `users` jadvalida RLS **yoqiladi**, lekin `tenant_id` siyosati o'rniga membership siyosati qo'llanadi: `id = app.user_id` YOKI `EXISTS (memberships WHERE user_id = users.id AND tenant_id = app.tenant_id)`.
- Login va tenant tanlash tenant kontekstisiz ishlaydi. Buning uchun ikkita `SECURITY DEFINER` funksiya ishlatiladi: `auth_find_user(phone)` faqat id va hash'larni qaytaradi; `auth_list_memberships(user_id)`.
- `tenants` jadvali istisno emas: siyosati `id = app.tenant_id`.
- Istisnolar ro'yxati: faqat `plans`, `units`, `platform_admins`. Ular global jadvallar; ilova roli ularga faqat SELECT huquqiga ega (`platform_admins`ga hech qanday huquq yo'q).

**7. QISMAN — `vat_moves` jadvalida `status` ustuni yo'q**

Muammo haqiqiy: 02:261 va 02:266 `pending` holatiga tayanadi, lekin bunday ustun yo'q. Ammo `status` ustunini qo'shish va keyin UPDATE qilish append-only tamoyilini buzadi.

Qaror:
- "Qizil" faktura bo'yicha kiruvchi QQS uchun `vat_moves` qatori ham, 4410 provodkasi ham **to'lov o'tkazilmaguncha yozilmaydi**. Bu 02:126 dagi ledger qoidasiga mos.
- To'lov qilinganda `vat_moves(kind=input)` yoziladi, summasi `allocations` bo'yicha proporsional (**taxmin**, buxgalter tasdiqlashi kerak).
- Kutilayotgan QQS summasi alohida saqlanmaydi, `einvoices` jadvalidan hisoblanadi (`risk_flag=red`, to'liq to'lanmagan).
- 4.2 formulasidan `status` filtri olib tashlanadi.

**8. QABUL — 07-fayldagi eskirgan matnlar**

01:145 da `prompt_version`, `cache_read_tokens`, `fx_rate_used`, `cost_uzs`, `guard_result` maydonlari allaqachon bor, 01:146 da esa `ai_training_samples` jadvali bor. 07-fayldagi quyidagi joylar eskirgan:
- 07:113, 07:136, 07:140, 07:193;
- Ochiq savol 2 — butunlay;
- Ochiq savol 6 — qisman: sxema bor, lekin saqlash muddati va anonimlashtirish darajasi hali ochiq.

**9. QABUL — obuna holati ikki joyda**

`tenants.status` va `subscriptions.status` bir xil hayot siklini takrorlaydi.

Qaror: holatning yagona manbai `subscriptions.status`, har tenant uchun bitta qator (`UNIQUE tenant_id`). Trial ham shu jadvalda: `status=trial`, `current_period_end` = trial tugash sanasi. `tenants.status` va `tenants.trial_ends_at` olib tashlanadi.

**10. QABUL — `sales.status` ikki xil holatni aralashtiradi**

01:115 da posting holati va fiskal holat bitta ustunda. Posting xizmati esa `posted` yozadi (09:126), 01:115 da `completed` deyilgan.

Qaror:
- Barcha hujjatlarda yagona holat: `posted` → `cancelled`. Ko'chirish va inventarizatsiyada o'z oraliq holatlari qoladi; `draft` faqat qurilmada bo'ladi.
- Fiskal holat faqat `fiscal_receipts.status` ustunida: `pending` → `sent` → `fiscalized` / `failed`.
- Qaytarish holati saqlanmaydi, `return_lines` yig'indisidan hisoblanadi. Sabab: o'tkazilgan hujjatni UPDATE qilib bo'lmaydi.

**11. QABUL** — `qabul-2` #8 bilan bir xil yechim: `uuid` (≥10, `v7()`). Qo'shimcha tahrir kerak emas.

**12. QABUL** — `qabul-2` #1 bilan bir xil (yagona yo'l `/sync/push`). Bu hujjat faqat 04 va 08 dagi qolgan qatorlarni moslashtiradi.

**13. QABUL — `idempotency_keys` kaliti**

09:199 dagi `key UNIQUE` yozuvi noaniq. To'g'risi: `UNIQUE (tenant_id, key)`. Jadval 01-faylga ham qo'shiladi (Q5). Saqlash muddati: 30 kun. Bu buxgalteriya yozuvi emas, shuning uchun 5 yillik talab unga tegishli emas.

**14. QISMAN — markirovka kodi bitta ustunda**

Muammo haqiqiy: `marking_code` bitta qiymat sig'diradi, qty > 1 bo'lsa kodlar sig'maydi. Yechim massiv yoki alohida jadval emas, eng sodda qoida: **markirovkalangan tovar qatori har doim qty = 1**. Kassa har bir skanerda yangi qator ochadi. Bu chekdagi har bir pozitsiyaga bitta kod degan OFD amaliyotiga ham mos (**taxmin**, OFD hujjatlari bilan tasdiqlanadi).

**15. QABUL** — sarlavhaga `temp_number` ustuni qo'shiladi: `UNIQUE (tenant_id, device_id, temp_number)`, server o'zi yaratgan hujjatlarda `null`.

**16. QABUL** — 09:181 dagi `einvoice_check` → `einvoice_send` (faqat B2B chek uchun). `kind` ro'yxati 03-fayl bilan birga to'liq yoziladi (Q4).

**17. QABUL — `recost_jobs` jadvali aniqlanmagan**

01:108 da faqat 4 ta maydon tilga olingan. Jadval 01 §10 ga to'liq kiritiladi. Bir xil ombor+tovar uchun navbatdagi job'lar birlashtiriladi: yangi job qo'yilmaydi, mavjudining `from_date` maydoni `LEAST(...)` bilan yangilanadi.

**18. QISMAN — veb-kassa offline'da avtorizatsiya**

Bu masalani `qabul-2` #6 hal qilgan: sessiya mutlaq muddati 7 kun (48 soatdan uzun); 401 kelsa qayta kiriladi, outbox saqlanadi. Veb-kassa uchun alohida qurilma tokeni yoki cookie **kerak emas**, bu MVP uchun ortiqcha murakkablik. Qurilma tokeni (Bearer) faqat Android uchun.

Hal qilinmay qolgan qism — voqeani kim qilganini aniqlash:
- Har bir outbox voqeasida `user_id` bo'ladi — offline PIN bilan kirgan kassir.
- Server bu foydalanuvchining `created_at` vaqtida faol membership'i bo'lganini tekshiradi.
- Push qilgan sessiyaning foydalanuvchisi voqea muallifidan farq qilishi mumkin. Bu holatda audit yozuviga ikkalasi ham yoziladi.

**19. QABUL** — pull javobidagi `debt_balance` → `receivable_balance`. Qiymat: `debt_balances.balance WHERE direction='receivable'`, yozuv bo'lmasa 0; musbat son mijoz bizga qarzdor ekanini bildiradi. Kassaga `payable` kerak emas, shuning uchun u yuborilmaydi. `debt_balances` ustunlari ham aniqlanadi.

**20. QABUL — AVECO'da qaytarish tannarxi**

Qoida:
- Qaytarish asl chek qatoridagi tannarx bilan qabul qilinadi (`sale_lines.cost_amount / qty`), joriy `avg_cost` bilan emas.
- Qaytarish kirim kabi o'rtacha narxga qo'shiladi: `avg = (qty_left×avg + ret_qty×orig_unit_cost)/(qty_left+ret_qty)`.
- Partiyalarning `qty_left` qiymati `lot_allocations` bo'yicha teskari tartibda tiklanadi.
- Ko'chirishda qabul qiluvchi ombor ham xuddi shu formulani qo'llaydi, unit cost sifatida jo'natuvchining tannarxi olinadi.

**21. QISMAN — naqd to'langan xarajat**

`cash_movements` hujjatini qo'shimcha yaratish ikkinchi hujjat va ikki marta yozish xavfini keltiradi.

Qaror: `ExpensePostingService` o'sha tranzaksiyaning o'zida faqat registrlarni yozadi:
- `cash_moves(−, doc_type=expense)`;
- `ledger_entries`.

`cash_movements` hujjati yaratilmaydi; `cash_movements.expense_id` maydoni va 02:203 dagi "Xarajat to'lovi" qatori olib tashlanadi. `expenses` jadvaliga `cash_register_id` va `shift_id` qo'shiladi (manba `cash` bo'lganda majburiy).

**22. QABUL — FIFO'da qulflash**

09:124 da nima qulflanishi noaniq ("lots/balances qatori").

Qaror:
- Ketma-ketlashtirish nuqtasi — `stock_balances (warehouse_id, product_id)` qatori. Avval `INSERT … ON CONFLICT DO NOTHING`, keyin `SELECT … FOR UPDATE`.
- Partiyalar bu qulf ostida qulfsiz o'qiladi.
- Partiyani o'zgartiradigan **barcha** yo'llar shu qulfni oladi: sotuv, qaytarish, kirim, ko'chirish, inventarizatsiya, recost.
- Deadlock bo'lmasligi uchun qulflash tartibi: `stock_balances` — `(warehouse_id, product_id)` o'sish tartibida, so'ng `debt_balances` — `counterparty_id` bo'yicha.
- `cash_moves` qulflanmaydi: unda tekshiriladigan invariant yo'q.

---

## O'ZGARISHLAR

### 01-malumotlar-modeli.md

- **01:7**: "faqat teskari hujjat bilan bekor qilinadi" → "faqat teskari (storno) registr yozuvlari bilan bekor qilinadi (`status=cancelled`)".

- **01:22**, "Majburiy ustunlar" katagi → "`tenant_id`, `created_at`, `created_by`, `updated_at`; hujjatlarda — 6-bo'limdagi umumiy sarlavha (yagona ro'yxat)".

- **01:23**: "`status=cancelled` + teskari hujjat" → "`status=cancelled` + registrlarda storno qatorlar (`reversal_of_id`)".

- **01:26** qatoridan keyin yangi qator qo'shiladi:

  "| RLS istisnolari | `tenant_id`'siz global jadvallar: `plans`, `units`, `platform_admins` (ilova roliga faqat SELECT, `platform_admins`ga umuman yo'q). `tenants` — siyosat `id = app.tenant_id`. `users` — siyosat `id = app.user_id OR EXISTS(memberships m WHERE m.user_id = users.id AND m.tenant_id = app.tenant_id)`; login/tenant tanlash — `SECURITY DEFINER` funksiyalar `auth_find_user(phone)`, `auth_list_memberships(user_id)` orqali |"

- **01:33** (`tenants`): "phone, status (`trial`/`active`/`grace`/`restricted`/`closed`), trial_ends_at, settings JSONB" → "phone, settings JSONB (`valuation_method`, `ai_training_consent`, …)"; izoh katagi: "Bitta do'kon/kompaniya. Obuna/hayot sikli holati bu yerda **emas** — `subscriptions.status`".

- **01:35** (`subscriptions`): "tenant_id, plan_id, period (`month`/`year`), current_period_end, status" → "tenant_id (UNIQUE — bitta tenant, bitta qator), plan_id, period (`month`/`year`), current_period_end (trial'da = trial tugash sanasi), grace_ends_at, status (`trial`/`active`/`grace`/`restricted`/`closed`)"; izoh katagi: "Tenant hayot siklining **yagona** manbai; holat mashinasi 8-bo'limda".

- **01:46** (`devices`): "tenant_id, cash_register_id, kind, last_seen_at, last_sync_at, app_version" → "tenant_id, cash_register_id, kind (`web`/`android`), token_hash (faqat android, Bearer), token_expires_at, revoked_at, last_seen_at, last_sync_at, app_version".

- **01:73** to'liq o'rniga:

  "Barcha hujjatlarda umumiy sarlavha (**yagona ro'yxat**, boshqa joyda takrorlanmaydi): `id, tenant_id, branch_id, number, temp_number (offline vaqtinchalik raqam, `{qurilma}-{lokal seq}`; server yaratgan hujjatda null; UNIQUE (tenant_id, device_id, temp_number)), doc_date, status, created_by, created_at, updated_at, posted_at, cancelled_at, cancelled_by, cancel_reason, client_event_id (UNIQUE (tenant_id, client_event_id)), device_id, comment`. Bekor qilish alohida teskari hujjat yaratmaydi: asl hujjat `cancelled` bo'ladi, registrlarga storno qatorlar yoziladi (7-bo'lim)."

- **01:78** (`sales` qatorlari): "vat_rate, vat_amount, marking_code, lot allocations" → "vat_rate, vat_amount, cost_amount, marking_code (markirovkalangan tovarda **qty = 1** majburiy — har kod alohida qator), lot_allocations JSONB".

- **01:90** (`expenses`): "— (category_id, amount, source: `cash`/`bank`/`card`, attachment_id, recurring_rule_id)" → "— (category_id, amount, source: `cash`/`bank`/`card`, cash_register_id + shift_id (source=`cash` bo'lsa majburiy), attachment_id, recurring_rule_id)".

- **01:91** (`cash_movements`): "— (direction `in`/`out`, reason, expense_id)" → "— (direction `in`/`out`, reason: `collection` (inkasso)/`deposit`/`owner_withdrawal`/`other`)"; registr katagi: "kassa naqd ±. Xarajat to'lovi bu hujjat **emas** — `ExpensePostingService` `cash_moves`ni o'zi yozadi".

- **01 §7, jadval ostiga** (01:104 dan keyin) yangi abzats:

  "Barcha registrlarda umumiy ustunlar: `id, tenant_id, doc_type, doc_id, reversal_of_id (storno qatorida — teskari qilinayotgan asl registr qatori, aks holda null), created_at`. Storno qatori asl qatorning teskari belgili nusxasi; sanasi — bekor qilish sanasi (joriy ochiq davr). `debt_balances`: (tenant_id, counterparty_id, direction, balance, updated_at), UNIQUE (tenant_id, counterparty_id, direction). `stock_balances`: (tenant_id, warehouse_id, product_id, qty, value, updated_at), UNIQUE (tenant_id, warehouse_id, product_id) — FIFO/AVECO posting'ining qulflash nuqtasi (`09-backend-arxitekturasi.md` 2.1). Registrlar va hujjatlar hech qachon o'chirilmaydi; saqlash muddati kamida 5 yil (O'RQ-404, 29-modda)."

- **01:104** (`vat_moves`): "tenant_id, period (oy), kind (`output`/`input`), base_amount, vat_amount, doc_type, doc_id, einvoice_id" → "… einvoice_id. `status` ustuni yo'q: "qizil" faktura bo'yicha kiruvchi QQS to'lovgacha **umuman yozilmaydi** (`02-provodka-qoidalari.md` 4.1)".

- **01:107** ("Sotuv/chiqim o'tkazilganda…") oxiriga qo'shiladi:

  "Qaytarish: asl qatordagi tannarxda (`sale_lines.cost_amount/qty`) qabul qilinadi; FIFO — `lot_allocations` bo'yicha asl partiyalarga; AVECO — kirim kabi o'rtachaga qo'shiladi: `avg = (qty_left×avg + ret_qty×asl_birlik_tannarx)/(qty_left+ret_qty)`. Ko'chirishning qabul tomoni AVECO'da ham shu formula bilan (jo'natuvchi tannarxida)."

- **01:108**: "(`recost_jobs`: tenant, warehouse, product, from_date)" → "(`recost_jobs`, 10-bo'lim)".

- **01:115** to'liq o'rniga:

  "| Chek (`sales`) | `draft` (faqat qurilmada) → `posted` → `cancelled`. Fiskal holat bu yerda **emas** — `fiscal_receipts.status`: `pending` → `sent` → `fiscalized` / `failed` (qayta urinish). Qaytarilganlik holati saqlanmaydi — `return_lines` yig'indisidan hisoblanadi |"

- **01:116**: "(`cancelled` — teskari hujjat bilan)" → "(`cancelled` — storno yozuvlar bilan)".

- **01:122** (Obuna): satr boshiga "`subscriptions.status` (yagona manba):" qo'shiladi.

- **01:129** (`fiscal_receipts`): "sale_id/return_id, cash_register_id, shift_id, receipt_seq (smena ichida ketma-ket), … status, attempts" → "tenant_id, sale_id/return_id, cash_register_id, shift_id, receipt_seq (**qurilma beradi**, smena ichida ketma-ket; UNIQUE (tenant_id, cash_register_id, shift_id, receipt_seq)), payload JSONB, fiscal_sign, qr_url, sent_at, offline_since, status (`pending`/`sent`/`fiscalized`/`failed`), attempts".

- **01:140** (`outbox_jobs`), kind ro'yxati → "kind (`ofd_send`, `einvoice_send`, `einvoice_accept`, `ettn_send`, `marking_verify`, `marking_sell`, `state_report_reminder`, `sms`, `telegram`, `ai`)"; qatorga qo'shimcha: "har job `tenant_id` bilan; worker `tenant_transaction(tenant_id)` ichida bajaradi".

- **01:141** dan keyin ikkita yangi qator:

  "| `idempotency_keys` | tenant_id, key, request_hash, response_status, response_body, created_at; UNIQUE (tenant_id, key); 30 kundan keyin tozalanadi (buxgalteriya yozuvi emas) | Faqat back-office REST; POS — `sync_receipts` (`09-backend-arxitekturasi.md` 3-bo'lim) |"

  "| `recost_jobs` | tenant_id, warehouse_id, product_id, from_date, status (`queued`/`running`/`done`/`failed`/`rejected_period_closed`), reason_doc_type, reason_doc_id, attempts, last_error, created_at, finished_at; qisman UNIQUE (tenant_id, warehouse_id, product_id) WHERE status='queued' — yangi so'rov mavjud navbatdagi job'ning `from_date`ini `LEAST` bilan yangilaydi | `02-provodka-qoidalari.md` 3.3, `09` 2.4 |"

- **01:141** (`sync_receipts`): "client_event_id (unique)" → "client_event_id (UNIQUE (tenant_id, client_event_id))".

- **01:157** izoh katagiga qo'shiladi: "Server raqam bermaydi va o'zgartirmaydi — faqat noyoblikni tekshiradi, takror → `RECEIPT_SEQ_CONFLICT`; uzilishlar smena yopilganda aniqlanadi. Bitta smena — bitta qurilma (`shifts.device_id`)".

### 02-provodka-qoidalari.md

- **02:126**: "(2.12-bo'lim)" → "(2.16-bo'lim)"; gap oxiriga qo'shiladi: "`vat_moves(kind=input)` ham shu paytgacha yozilmaydi (4.1)."

- **02:184** oxiriga qo'shiladi: "Qisman to'lovda QQS krediti `allocations` summasiga proporsional ochiladi (**taxmin**, buxgalter tasdig'i kerak); bir vaqtning o'zida `vat_moves(kind=input)` yoziladi."

- **02:190** (Kassa naqdi) izohiga qo'shiladi: "`ExpensePostingService` shu tranzaksiyada `cash_moves(−, doc_type=expense, cash_register_id, shift_id)` ham yozadi; `cash_movements` hujjati yaratilmaydi."

- **02:203** ("Xarajat to'lovi" qatori) **o'chiriladi**. Jadval ostiga qo'shiladi: "Kassadan to'langan xarajat — M16 hujjati emas, M15 `expenses` (source=`cash`); `cash_moves` va provodkani `ExpensePostingService` yozadi (2.17)."

- **02:229** to'liq o'rniga:

  "**AVECO**: kirim 2'dan keyin `avg_cost = (100×8 000 + 50×9 000) / 150 = 1 250 000/150 = 8 333,3333 so'm` (`NUMERIC(18,4)`, 5.3). Sotuv: 120 × 8 333,3333 = 999 999,996 → **COGS = 1 000 000,00 so'm** (tiyingacha). Qoldiq qiymati = 1 250 000,00 − 1 000 000,00 = **250 000,00 so'm** (30 dona; tekshiruv: 30 × 8 333,3333 = 249 999,999 ≈ 250 000,00). Qoldiq qiymati har doim `eski qiymat − COGS` sifatida yuritiladi (`qty × avg` emas) — yaxlitlash qoldig'i to'planmasligi uchun."

- **02:237** ostiga yangi band:

  "- **Qaytarish tannarxi**: FIFO — asl `lot_allocations` partiyalariga, asl tannarxda; AVECO — asl chek qatoridagi birlik tannarxida kirim sifatida, `avg_cost` 3.1 formulasi bilan qayta hisoblanadi (joriy `avg_cost` bilan emas)."

- **02:261**: "agar faktura "qizil" bo'lsa, `vat_moves` yozuvi `pending` holatda saqlanadi (to'lovgacha ichki hisobga kirmaydi, VM Qarori №830)" → "agar faktura "qizil" bo'lsa, `vat_moves` yozuvi **to'lov o'tkazilmaguncha yozilmaydi** (4410 bilan bir xil, 2.8/2.16, VM Qarori №830). Kutilayotgan kiruvchi QQS `einvoices` dan hisoblanadi (`risk_flag=red`, to'liq to'lanmagan) — alohida holat ustuni yo'q (append-only)."

- **02:266**: "`− SUM(vat_moves.vat_amount WHERE kind=input, period, status != 'pending')`" → "`− SUM(vat_moves.vat_amount WHERE kind=input, period)`".

- **02:298** to'liq o'rniga:

  "Hujjat bekor qilinganda (`status=cancelled`, `cancelled_at`, `cancelled_by`, `cancel_reason`): asl `ledger_entries` qatorlari **o'zgartirilmaydi**; har bir asl qator uchun Dt/Kt o'rni almashtirilgan yangi qator qo'shiladi: `doc_id` = **asl** hujjat, `reversal_of_id` = teskari qilinayotgan asl registr qatori, sana = bekor qilish sanasi (joriy ochiq davr). Alohida teskari hujjat yaratilmaydi. Bu qoida `stock_moves`, `debt_moves`, `cash_moves`, `vat_moves` uchun ham bir xil (append-only, hech qachon UPDATE/DELETE)."

### 04-offline-sync.md

- **04:52–59** jadvaliga yangi qator:

  "| `user_id` | UUID | Amalni bajargan kassir (offline PIN bilan kirgan); server uning `created_at` paytida faol membership'ini tekshiradi; push qilgan sessiya foydalanuvchisi farq qilsa, ikkalasi audit'ga yoziladi |"

- **04:59** (`payload`) qatoriga qo'shiladi: "`sale.created`da `fiscal.receipt_seq` — qurilma beradi (3.3)".

- **04:84**: `"server": { "id": "...", "number": "K-01-2026-000154", "receipt_seq": 182 }` → `"server": { "id": "...", "number": "K-01-2026-000154" }`.

- **04:91** dan keyin yangi band:

  "- **Fiskal raqam**: `receipt_seq` qurilmadan keladi; server uni o'zgartirmaydi, faqat UNIQUE (tenant_id, cash_register_id, shift_id, receipt_seq) bilan tekshiradi. Takror — `rejected`, `error_code: RECEIPT_SEQ_CONFLICT`, `retryable: false` (eskalatsiya)."

- **04:102**: `"debt_balance": 350000` → `"receivable_balance": 350000`. Blokdan keyin izoh:

  "`receivable_balance` = `debt_balances.balance WHERE direction='receivable'` (yozuv yo'q bo'lsa 0; musbat — mijoz bizga qarzdor). `payable` kassaga yuborilmaydi."

- **04:111** to'liq o'rniga:

  "- Fiskal chek raqami (`fiscal_receipts.receipt_seq`) — **qurilma beradi** (offline ham), outbox `seq` bilan bir Web Lock ichida; kassa + smena ichida ketma-ket. **Bitta smena — bitta qurilma** (`shifts.device_id`): boshqa qurilmadan shu smenaga voqea `rejected SHIFT_DEVICE_MISMATCH`."

- **04:138**: "`DB-->>API: OK (number, receipt_seq)`" → "`DB-->>API: OK (id, number)`".

- **04:139**: "`server:{number, receipt_seq}`" → "`server:{id, number}`".

- **04:164**: "server number/receipt_seq" → "server id/number".

- **04 §3.4** — `qabul-2` #6 dagi "401" abzatsi qo'shiladi. Uning ostiga:

  "Veb-kassa uchun alohida qurilma tokeni/cookie yo'q — offline davr server autentifikatsiyasini talab qilmaydi (lokal PIN, 12-bo'lim), sessiya mutlaq muddati (7 kun) 48 soatdan uzun. Qurilma tokeni (Bearer) faqat Android uchun (`05-xavfsizlik-va-audit.md` 1.3)."

- **04 Ochiq savol 4** o'rniga: "~~4.~~ Yopildi: bitta smena — bitta qurilma (3.3)."

### 05-xavfsizlik-va-audit.md

- **05:7**: "Android POS/qurilmalar uchun **qurilma tokeni**" → "Android POS uchun **qurilma tokeni** (Bearer); veb-kassa — sessiya cookie + lokal offline PIN, 401'da outbox saqlangan holda qayta kirish (`04-offline-sync.md` 3.4)".

- **05:183**, qavs ichidagi matn: "(platforma jadvallari — `tenants`, `plans`, `platform_admins` bundan mustasno, chunki ular tenant-kesishmaydigan)" → "(istisno faqat `tenant_id`'siz global jadvallar — `plans`, `units`, `platform_admins`; `tenants` — `id = app.tenant_id` siyosati, `users` — membership siyosati, `01-malumotlar-modeli.md` 1-bo'lim)".

- **05:185** dan keyin yangi bandlar:

  "- Worker/scheduler testlari: (1) tenant A job'i B ma'lumotini ko'rmaydi; (2) `tenant_id`'siz job xato bilan tugaydi, so'rov bajarilmaydi; (3) bitta ulanishda ketma-ket ikki tenant job'i — ikkinchisida birinchi tenant konteksti qolmaganligi (`set_config(..., true)` tranzaksiya-lokal).
  - `users`: tenant A kontekstida faqat A'ga membership'i bor foydalanuvchilar ko'rinadi; `auth_find_user` faqat id/hash qaytaradi."

### 07-ai-qatlami.md

- **07:113** to'liq o'rniga: "- `ai_requests.prompt_version` (`01-malumotlar-modeli.md` 10-bo'lim) — har javob qaysi prompt versiyasidan kelganini qayd etadi (format: `ai01_qna/v3`)."

- **07:136**: "(mavjud maydonlar: `tenant_id, user_id, feature, model, input_tokens, output_tokens, cost_usd, latency_ms, status`)" → "(maydonlar `01-malumotlar-modeli.md` 10-bo'limda: `tenant_id, user_id, feature, model, prompt_version, input_tokens, output_tokens, cache_read_tokens, cost_usd, fx_rate_used, cost_uzs, latency_ms, guard_result, status`)".

- **07:140**: "**Tavsiya/ochiq savol**: `ai_requests`da `cost_uzs` ustuni yo'q — … (ma'lumotlar modeli jamoasi bilan kelishiladi)." → "Yozuv vaqtidagi kurs `fx_rate_used`, natija `cost_uzs` ustunida saqlanadi (tarixiy aniqlik)."

- **07:193**: "(tavsiya: yangi jadval, masalan `ai_training_samples` — **hozircha ma'lumotlar modelida yo'q, kelajakdagi qo'shimcha**)" → "(`ai_training_samples`, `01-malumotlar-modeli.md` 10-bo'lim)".

- **07 Ochiq savol 2**: o'chiriladi (hal qilingan).

- **07 Ochiq savol 6** o'rniga: "`ai_training_samples` uchun saqlash muddati va anonimlashtirish darajasi (sxema 01'da bor) — aniqlanmagan (9-bo'lim)."

### 08-frontend-arxitekturasi.md

- **08 §4**: UUIDv7 qatori — `qabul-2` #8 dagi matn (qo'shimcha yo'q).
- **08:150**: `qabul-2` #1 dagi matn.
- **08:151** oxiriga qo'shiladi: "Fiskal chek raqami (`receipt_seq`) qurilmada, outbox yozuvi bilan bir Web Lock ichida beriladi."

### 09-backend-arxitekturasi.md

- **09:124** (2.1, 2-qadam) to'liq o'rniga:

  "2. **Qulflash** — serializatsiya nuqtasi `stock_balances (warehouse_id, product_id)` qatori: avval `INSERT … ON CONFLICT DO NOTHING`, so'ng `SELECT … FOR UPDATE`. Shu qulf ostida `stock_lots` qulfsiz o'qiladi va o'zgartiriladi; partiyaga tegadigan **barcha** yo'llar (sotuv, qaytarish, kirim, ko'chirish, inventarizatsiya, hisobdan chiqarish, recost) aynan shu qulfni oladi. Kerak bo'lsa `debt_balances (counterparty_id, direction)` ham `FOR UPDATE`. Deadlock'ga qarshi tartib: avval `stock_balances` — `(warehouse_id, product_id)` o'sish tartibida, so'ng `debt_balances` — `counterparty_id` bo'yicha. `cash_moves` qulflanmaydi (tekshiriladigan invariant yo'q)."

- **09:126**: "Hujjat holatini `posted`ga o'tkazadi" — o'zgarmaydi. Oxiriga qo'shiladi: "(fiskal holat — alohida `fiscal_receipts.status=pending`, `01-malumotlar-modeli.md` 8-bo'lim)".

- **09:135–153** (2.2 misoli) quyidagi bilan almashtiriladi:

  "Ombordagi "Shakar" partiyalari (FIFO; `unit_cost` — QQS'siz, 2.6-provodkaga mos):

  | Partiya | `qty_left` | `unit_cost` |
  |---|---|---|
  | Lot-1 (eski) | 5 kg | 9 500 so'm |
  | Lot-2 | 8 kg | 9 800 so'm |

  Sotuv: 10 kg × 12 000 so'm/kg, **narx QQS bilan** (`02-provodka-qoidalari.md` 2-bo'lim), QQS 12%, naqd.

  - Chek summasi = 120 000,00; QQS = 120 000 × 12/112 = 12 857,142857… → **12 857,14**; sof daromad = **107 142,86**.
  - FIFO: Lot-1'dan 5 kg (47 500) + Lot-2'dan 5 kg (49 000) → `lot_allocations = [{lot: 1, qty: 5, cost: 47500}, {lot: 2, qty: 5, cost: 49000}]`, COGS = **96 500**; Lot-2'da 3 kg qoladi. Yalpi foyda = 107 142,86 − 96 500 = 10 642,86.

  Shu bitta postingda yoziladigan qatorlar:

  - `stock_moves`: −10 kg, cost_amount = −96 500,00.
  - `stock_lots`: Lot-1.qty_left = 0, Lot-2.qty_left = 3.
  - `ledger_entries`: Dt 9120 / Kt 2910 = 96 500,00.
  - `ledger_entries`: Dt 5010 / Kt 9020 = 107 142,86.
  - `ledger_entries`: Dt 5010 / Kt 6410 = 12 857,14 (Dt 5010 jami = 120 000,00).
  - `vat_moves`: output, base_amount = 107 142,86, vat_amount = 12 857,14.
  - `cash_moves`: +120 000,00 (naqd). Nasiya bo'lsa: `debt_moves` +120 000,00, Dt 5010 o'rniga Dt 4010 — summalar bir xil."

- **09:159** to'liq o'rniga:

  "`reverse()` yangi hujjat yaratmaydi — original hujjat `cancelled` bo'ladi (`cancelled_at`, `cancelled_by`, `cancel_reason`) va **har bir yozilgan registr qatoriga teskari belgili nusxa** qo'shiladi (`doc_type`/`doc_id` — original hujjat, `reversal_of_id` — teskari qilinayotgan asl registr qatori; hech qachon `UPDATE`). `stock_lots.qty_left` `lot_allocations` bo'yicha teskari tartibda qaytariladi (2.1 qulfi ostida)."

- **09:163**: "(`recost_jobs: tenant, warehouse, product, from_date`)" → "(`recost_jobs`, `01-malumotlar-modeli.md` 10-bo'lim)". Gap oxiriga qo'shiladi: "Job `queued → running → done/failed`; davr yopiq bo'lsa `rejected_period_closed`. Job 2.1 dagi `stock_balances` qulfini oladi."

- **09:164**: "hech qanday `draft`/`fiscal_pending` hujjat yo'qligini" → "davr ichida `fiscal_receipts.status IN ('pending','sent','failed')` yo'qligini".

- **09:181**: `"einvoice_check"` → `"einvoice_send" (faqat B2B chek)`. Mermaid'ning qolgan qismi — `qabul-2` #1.

- **09:199**: "`idempotency_keys(tenant_id, key UNIQUE, …)`" → "`idempotency_keys(tenant_id, key, …, UNIQUE (tenant_id, key))`". Oxiridagi "Offline kassa qayta yuborganda `key = client_event_id`" iborasi `qabul-2` #1 matni bilan almashtiriladi (`/sync/push` istisno).

- **09 §4** (SAQ qarori, `qabul-2` #4) ostiga yangi abzats:

  "**Worker/scheduler'da tenant konteksti**: har job'ning birinchi argumenti — majburiy `tenant_id` (`outbox_jobs.tenant_id`dan); job tanasi `async with tenant_transaction(session, tenant_id):` ichida bajariladi, `tenant_id`'siz job darhol xato bilan tugaydi. Scheduler (cron) biznes so'rovi bajarmaydi: `SECURITY DEFINER` funksiyasi `list_active_tenant_ids()` orqali tenantlarni olib, **har tenant uchun alohida job** navbatga qo'yadi. Platformaviy job'lar (obuna holati, billing) ham shu fan-out orqali tenant kontekstida ishlaydi; RLS'ni chetlab o'tadigan worker roli yo'q."

- **09:269** (RLS izolyatsiya qatori) oxiriga qo'shiladi: "Worker: tenant A job'i B'ni ko'rmasligi, `tenant_id`'siz job rad etilishi, bitta ulanishda ketma-ket job'lar orasida kontekst qolmasligi (`05-xavfsizlik-va-audit.md` 3.3)."

- **09:267** (Domain qatori) qamroviga qo'shiladi: "AVECO misoli (`02-provodka-qoidalari.md` 3.2: COGS 1 000 000,00, qoldiq 250 000,00), QQS ajratish (2.2: 12 857,14), AVECO qaytarish tannarxi".

### Kesishuvchi (ro'yxatdagi 7 fayldan tashqari, ma'lumot uchun)

- **03:68, 03:89, 03:113, 03:128** — `fiscal_pending` → `fiscal_receipts.status=pending`.
- **03:665**, Ochiq savol 10 — 01:140 dagi yangi `kind` ro'yxati bilan yopiladi.

# C — Biznes qoidalari, qarorlar izchilligi va amalga oshirish imkoniyati

**Maqsad:** `spec/kod-uchun/` (commit 00dd8aa) mustaqil tekshiruvi: (1) #1–#65 qarorlari barcha fayllarda bir xil qo'llanganmi; (2) dasturchi taxmin qilmasdan kod yoza oladimi; (3) `27` backlog tartibi, havolalari va "Tayyor ta'rifi"; (4) huquqiy da'volar manbasi. · **Kim uchun:** asoschi, spec tuzatuvchi agentlar. · **Holat:** faqat o'qish tekshiruvi, 2026-10-16; spec fayllari o'zgartirilmagan.

**Usul:** 7 ta mustaqil Opus tekshiruvchi (fiskal/offline/to'lov; buxgalteriya; auth/AI/tarif/agent; 1C; ekran↔API↔ruxsat; backlog↔testlar; huquqiy manba + algoritmlar). Har topilma real qatorni o'qib tasdiqlangan; takrorlar birlashtirilgan (bir nechta tekshiruvchi topgan bandlar — "[x2]", "[x3]").

**Daraja:** **kritik** — dasturchi noto'g'ri xatti-harakat/raqam quradi yoki umuman qura olmaydi; **o'rta** — taxmin qilishga majbur; **kichik** — kosmetik/eskirgan havola.

## Xulosa

| Daraja | Soni |
|---|---|
| kritik | 33 |
| o'rta | 90 |
| kichik | 60 |
| **Jami** | **183** |

**Ziddiyat topilmagan qarorlar (tasdiqlandi):** 24/40/46/48 soat shkalasi va `ofd_acked_at IS NULL` hisobi, qo'lda chetlab o'tish yo'q (#43); `credit_revenue_timing` yo'q, daromad/QQS sotuv kuni (#30, #59b); `MARKING_PRECHECK=warn`, `items[].marking_codes`, markirovkali qaytarish online (#17/#62); `sale_payments`/`debt_payments` dagi `card_type`/`card_mask`/`rrn`/`qr_type` CHECK'lari (#64); `fm_receipt_seq` (#12); litsenziya tokeni `valid_until`, `sync.drain` (#15, #19); Vakolat.uz/`PowerOfAttorneyAdapter` yo'q (#63b); 5710→5110, 9430/9410 komissiya, "to'g'ridan-to'g'ri 5110" yo'q (#42, #59a); 2920/2910 `inv_acct` qoidasi (13), `0000` (8720 yo'q); 4310 avansi (#47); 1000.00 tolerance, 5 ish kuni, 1/3/4-eslatma (#50); #53 formulasi; 99 000 / 39 000 / 950 400, boshqa tarif darajasi yo'q (#22); token 15 daq / agent 10 daq / refresh 14/180 (#44); Haiku 5.5 → Sonnet 5.5, maskalash o'chirilmaydi, AI limitlari (#16, #55, #61); ikki tilli chek (#29); Egasi = barcha ruxsat (#28); SAQ, treepoem yo'q, `tenants.status` yo'q; #54 konstantalari; 1C: faqat COM, OData/.epf/HTTP-servis yo'q, Bosqich 7, ОРП kassa×kun, `Возвраты` alohida jadval qismi, provodka yuborilmaydi, GUID `NewObject`+`УстановитьСсылкуНового`, avto-tasdiq o'chiq, `onec.*` ruxsatlari, 81 ta `ONEC_*` kodi 17 bilan mos (#36–#41); jamoa = asoschi + Claude, sprint/hafta yo'q (#35); 03 dagi 104/86/18 hikoya soni to'g'ri; barcha Must hikoyalar biror bosqichda, #33 dagi 4 ta hikoya MVP bosqichlarida yo'q; 306 ta "26 #N" havolasi mavjud bandga ishora qiladi; 07/17–20 dagi barcha ruxsat kodlari 15 katalogida bor; 18/19/20/07 dagi barcha xato kodlari 17 §15 da bor.

## Eng muhim 10 ta

1. **C-002** — Do'kon agenti (Bosqich 5) Bosqich 7 da quriladigan ulash/token/A-API/vazifa jadvallariga tayanadi; `onec_agent_tasks.kind` CHECK fiskal/printer vazifalarini rad etadi.
2. **C-001** — `price_changes` limitdan oshganda: 01 #25/11/12/07/31 — `pending_approval`; 19/18 — `draft`. Test yiqiladi.
3. **C-017** — Offline fiskallashtirilgan chek yopilgan davrdan keyin sinxronlansa `PERIOD_CLOSED` bilan rad etiladi — chek bor, provodka yo'q.
4. **C-004** — Offline/lokal ko'prikda qarz to'lovi chekining tovar qatorlarini qurilma hisoblay olmaydi (server allokatsiyasi talab qilinadi).
5. **C-006** — Lokal ko'prik FM natijasi (`fiscal_sign`, `fm_receipt_seq`…) `sale.created` payload'ida yo'q; serverda har chek `ofd_acked_at`ini to'ldirish yo'li yo'q → 48 soatlik blokni yechib bo'lmaydi.
6. **C-008 / C-009 / C-011** — E-TTN imzolash/qabul amallari birorta ekranda yo'q, POS-09 `/post`ni o'tkazib yuboradi, `ettn_documents.status` da `failed` yo'q → `vehicle` ko'chirish hech qachon `send` bo'lmaydi.
7. **C-003** — Kassasiz (BO-06, karta/bank) qarz to'lovi uchun majburiy `debt_settlement` chekini qaysi FM imzolashi va qaysi 48 soat hisobiga kirishi aniqlanmagan.
8. **C-012 / C-013** — `cash_movements.reason` CHECK'da `expense` yo'q (POS-14 buziladi); `reason='other'` uchun Dt/Kt qoidasi yo'q.
9. **C-019** — Chek shablonida qonuniy majburiy qator QQS stavkasi/summasi yo'q (VMQ-943 1-ilova 7-band).
10. **C-014** — `BankSettlement.variance_amount` ishorasi 20 da teskari (13/12 DDL ga zid) — noto'g'ri pul raqamlari.

---

## 1. Kritik

**C-001** · `19-api-ombor.md:13, 216, 224`; `18-api-kassa.md:554` ↔ `01-qarorlar.md:86` (#25), `11:162`, `12:1357`, `07:803`, `31:334` · [x3]
- **Muammo:** limitdan oshgan `price-changes/{id}/post` 19/18 da `202 {status:"draft"}`, rad etilsa ham `draft`. #25 da `price_changes` — `pending_approval` ga o'tadigan yagona istisno; 11/12/07/QT-M09-02 `pending_approval → posted/rejected` kutadi. `rejected` holatiga hech qachon yetilmaydi.
- **Tuzatish:** 19:216 → `202 {status:"pending_approval", approval_request_id}` (`APPROVAL_REQUIRED`); 19:224 → rad etilsa `status='rejected'`; 19:13 → `draft → pending_approval (202) → posted | rejected`; `approval_requests` `expired` bo'lsa hujjat `draft` ga qaytadi; 18:554 shunga moslansin; `post` faqat `draft` dan.
- **Daraja:** kritik

**C-002** · `27-backlog.md:163–168, 220–225`; `12-db-sxema.md:494, 3054–3056, 3084, 3944`; `33:980–982, 1010, 2158–2180`; `21:837–849`; `23:22, 278–290`; `34` §14.1–14.3; `07:1125` · [x4]
- **Muammo:** #60 bo'yicha agent asosi va fiskal ko'prik — Bosqich 5. Lekin ulash (device code), `private_key_jwt` tokeni, A-01…A-10, Ed25519 vazifa imzosi, `agent_update` ildiz kaliti, `onec_agents`/`onec_agent_tasks`/`onec_task_results`/`auth.onec_device_authorizations` — faqat Bosqich 7 vazifalari va `0028 onec_integration` migratsiyasida. `onec_agent_tasks.kind` CHECK faqat 13 ta 1C turini qabul qiladi, `base_id IS NULL` faqat `probe/discover_bases/collect_diagnostics` uchun — `fiscal.status`, `fiscal.resend_unsent`, `fiscal.zreport`, `print.raw`, `scale.plu_upload` INSERT bo'lmaydi. A-01 sxemasida `capabilities` yo'q (23:290 va 34 §14.2 ishlatadi), uni saqlaydigan ustun yo'q. BO-14 "agent ulash shu ekranda" deydi, lekin amal/endpoint/ruxsat yo'q.
- **Tuzatish:** (a) 27:224–225 (OAuth `onec-agent`, device grant, `client_credentials`+`private_key_jwt`, A-01/03–06/08–10, lease/heartbeat, Ed25519 imzo, W-01…W-08) Bosqich 5 ga ko'chirilsin; "`agent_update` ildiz kaliti oflayn yaratilgan" — B5 kirish sharti (27:163); B7 da faqat 1C ga xos vazifalar qolsin. (b) 12 §6.1: 0028 ikkiga — agent registri (B5) va 1C (B7). (c) CHECK: `kind IN (13 tur) OR kind IN ('fiscal.status','fiscal.resend_unsent','fiscal.zreport','print.raw','scale.plu_upload')`; `base_id IS NOT NULL OR kind IN ('probe','discover_bases','collect_diagnostics', <5 agent turi>)`; `purpose` ga `'device_service'`. (d) `onec_agents.capabilities JSONB NOT NULL DEFAULT '{}'`; 33 A-01 ga `capabilities`, `X-Agent-Protocol: 2`. (e) BO-14 ga "Do'kon agenti → Kompyuterni ulash/uzish" qatori (W-03/W-04/W-05, ruxsat `settings.tenant`).
- **Daraja:** kritik

**C-003** · `18-api-kassa.md:636, 656`; `12-db-sxema.md:1483, 1993–1995, 2009–2011`; `07:840`
- **Muammo:** `debt_payment` BO-06 (`POST /debt-payments`) yoki karta/bank bilan bo'lsa `cash_register_id`/`shift_id` NULL, lekin #30/#45 bo'yicha har to'lovga `debt_settlement` cheki majburiy. Chekni qaysi FM imzolashi, u qaysi kassaning 48 soat hisobiga kirishi (#43), `receipt_seq` ni kim berishi (#12) noma'lum; `bank` usulida chek kerakmi — noma'lum.
- **Tuzatish:** 18 §12.2/12.3: "`method != 'bank'` → `cash_register_id`, `shift_id`, `receipt_seq` majburiy (chek shu kassa FM'ida). BO-06 faqat `method='bank'` qabul qiladi va chek yaratmaydi (bank o'tkazmasi — 26 ga savol); aks holda to'lov ochiq smenaga bog'lanadi." 12: `CHECK (method = 'bank' OR (cash_register_id IS NOT NULL AND shift_id IS NOT NULL))`; `fiscal_receipts` `debt_settlement` sharti: `cash_register_id, shift_id, receipt_seq IS NOT NULL`.
- **Daraja:** kritik

**C-004** · `18-api-kassa.md:628, 647, 651`; `16-offline-sync.md:31`; `21:49, 122` · [x2]
- **Muammo:** qarz to'lovi chekining tovar qatorlari **server** allokatsiyasidan proporsional hisoblanadi ("client allokatsiyani tanlamaydi"). Offline va lokal ko'prik rejimida chekni qurilma FM orqali darhol imzolaydi, qurilmada esa faqat qarz balansi bor (ochiq hujjatlar va `sale_lines` yo'q) — chekni yasab bo'lmaydi. 18:651 lokal ko'prikda ham `ofd_send` deydi, 21:49 — faqat hamkor bulut.
- **Tuzatish:** variant tanlansin: (a) `debt_payment.created` — faqat online; yoki (b) `customers` keshiga `open_debt_docs[{doc_type, doc_id, due_date, doc_date, open_amount, lines[{sale_line_id, product_id, qty, line_total, vat_rate, settled_amount}]}]`; allokatsiya va qatorlar `shared/lib/debt-allocation` umumiy deterministik funksiyasi bilan (test-vektorlar `shared/money-vectors.json`); payload'ga `allocations[]`, `fiscal_lines[]`; server qayta hisoblaydi, farqda rad etmaydi — `sync_exceptions`. `ofd_send` faqat `partner_cloud`.
- **Daraja:** kritik

**C-005** · `18-api-kassa.md:637, 651`; `31-qabul-testlari.md:318`
- **Muammo:** offline qarz to'lovida summa qurilmadagi eski `receivable_balance` bo'yicha tekshiriladi; boshqa qurilma oraliqda to'lov olsa server `422 debt_payment_exceeds_balance` beradi, lekin pul olingan va FM imzolagan chek bor — fiskal hujjat "yetim" qoladi.
- **Tuzatish:** 18 §12.2 "Offline": "`is_offline=true` voqeada ortiqcha summa rad etilmaydi: qarzgacha allokatsiya, ortig'i `sync_exceptions(kind='debt_overpayment_offline')` + M18 Egasiga (qaytarish — qo'lda kassa chiqimi). `422 debt_payment_exceeds_balance` faqat online/REST." 31 ga test.
- **Daraja:** kritik

**C-006** · `18-api-kassa.md:223–275, 299`; `21:155–158, 841`; `16:255, 257`; `24:170`
- **Muammo:** lokal ko'prikda FM natijasi (`fm_terminal_id`, `fm_receipt_seq`, `fiscal_sign`, `qr_url`, `fiscal_at`) `sale.created` bilan keladi deyilgan, lekin §4.1 payload'da yo'q; `fiscal.status` enum'ida `fiscalized` yo'q. Agent faqat agregat (`pending`, `oldest_unacked_at`) beradi — server har chek `ofd_acked_at` ini to'ldira olmaydi, #43 "barcha cheklar tasdiq olgach blok yechiladi" bajarilmaydi.
- **Tuzatish:** 18 §4.1/§7.1/§12.2 payload'iga `fiscal_result: {fm_terminal_id, fm_receipt_seq, fiscal_sign, qr_url, fiscal_at} | null` (lokal ko'prikda majburiy); §4.5 `fiscal.status` = `"pending"|"fiscalized"|"deferred"`; 21 §16 `fiscal.status` natijasiga `acked: [{fm_terminal_id, fm_receipt_seq, acked_at}]` (yoki `unsent[]`), server shu bo'yicha `fiscal_receipts.ofd_acked_at` ni yangilaydi.
- **Daraja:** kritik

**C-007** · `03-modullar-talablari.md:28, 314`; `31:304`; `06:167`; `07:162, 230, 429, 461`; `04:101` ↔ `12:941`
- **Muammo:** "sotuv holati `deferred`" / `sales.status='deferred'` deyilgan; `sales.status` CHECK faqat `draft/posted/cancelled`. #30 da `deferred` — faqat javobdagi `fiscal.status`. QT-M08-01 bajarib bo'lmaydigan holatni tekshiradi.
- **Tuzatish:** hamma joyda "`sales.status='posted'`, javobda `fiscal.status='deferred'`, `fiscal_receipts` yozuvi yo'q"; 31:304 shunga.
- **Daraja:** kritik

**C-008** · `07-ekran-tafsilotlari.md:335, 341` (POS-09), BO-03, BO-15; `19:898–921`; `18:771`; `15:164`; `30:72, 73, 82` · [x2]
- **Muammo:** hech bir ekran `POST /ettn-documents/{id}/sign-challenge`, `/submit-signed`, `/register-manual`, `/accept`, `/reject` va chiquvchi e-faktura `POST /einvoices/{id}/send`/`/cancel` ni chaqirmaydi. `vehicle` ko'chirish e-TTN `registered` bo'lmaydi → `/send` doim `409 ETTN_REQUIRED`; chiquvchi e-faktura `signed` da qotadi. 07:335 "server yaratadi va yuboradi" — imzo bosqichi yo'q; Omborchida `einvoice.sign` yo'q. 30 bu endpointlarni ekranlarga bog'laydi, ekranlarda esa amal yo'q.
- **Tuzatish:** BO-03 "Ko'chirishlar" tabiga: "E-TTN imzolash" (`einvoice.sign`, sign-challenge → submit-signed), "Qo'lda ro'yxatga olish" (`transfer.create`, register-manual), "Kiruvchi e-TTN tasdiqlash/rad etish" (`transfer.receive` + `einvoice.sign`). BO-15 ga chiquvchi "Yuborish"/"Bekor qilish" va kiruvchi e-TTN ro'yxati (`GET /ettn-documents?direction=in`). 07:335 → "server `pending_signature` yaratadi; Egasi/Buxgalter E-IMZO bilan imzolaydi"; Omborchi uchun holat "E-TTN imzo kutilmoqda".
- **Daraja:** kritik

**C-009** · `07-ekran-tafsilotlari.md:326–333, 344` (POS-09) ↔ `19:597, 612, 617–619`
- **Muammo:** POS-09 "`POST /transfers` → `/send`" — `/send` faqat `posted` dan (`409 DOC_INVALID_STATE`). POS-09 da `vehicle_plate` maydoni yo'q, `post` esa `vehicle` da uni talab qiladi (`422`).
- **Tuzatish:** 07:344 → "`POST /transfers` → `POST /{id}/post` → (e-TTN `registered`) → `POST /{id}/send`"; jadvalga `vehiclePlate` (`vehicle` da majburiy, ≤16), `driverName` (ixtiyoriy).
- **Daraja:** kritik

**C-010** · `07:739–760, 1148`; `07:287`; `19:387`; `21:192, 399–403`; `12:1077, 1132, 2187–2189` · [x2]
- **Muammo:** e-ishonchnoma (#63b) uchun `EInvoicePort.send_power_of_attorney(poa_id, …)` va `outbox_jobs(kind=poa_send)` ishlatiladi, lekin `poa_id` jadvali, REST endpoint va `poa_send` kind CHECK'da yo'q; `purchase_orders` da poa ustuni yo'q; 07:1148 dagi holatlar saqlanmaydi.
- **Tuzatish:** 11/12: `app.powers_of_attorney(id, tenant_id, purchase_order_id, employee_user_id, supplier_id, valid_to, number, doc_date, operator_doc_id, status CHECK ('draft','pending_signature','sending','sent','accepted','rejected','cancelled'))`; `outbox_jobs.kind` ga `poa_send`. 19 §8a: `POST /powers-of-attorney`, `/{id}/sign-challenge`, `/{id}/submit-signed`, `GET ?po_id=` (ruxsat `purchases.create`, imzo `einvoice.sign`); `goods_receipts.poa_number` shu jadvaldan. (Agar MVP emas bo'lsa — 07:760/1148 dan olib tashlansin.)
- **Daraja:** kritik

**C-011** · `12-db-sxema.md:2115–2117`; `11:167–169` ↔ `19:898, 901–903, 907–909`; `21:264` · [x2]
- **Muammo:** 19 da `ettn_documents.status='failed'` va `submit-signed` `pending_signature|failed` dan; 12 CHECK va 11 holat mashinasida `failed` yo'q. 19 javobidagi `counterparty_id`, `doc_date`, `payload` va 21 dagi `signed_at` DDL'da yo'q.
- **Tuzatish:** 12 CHECK ga `'failed'`; ustunlar `payload JSONB NULL`, `doc_date DATE NULL`, `counterparty_id UUID NULL`, `signed_at TIMESTAMPTZ NULL`; 11 ga `sending → failed → sending`.
- **Daraja:** kritik

**C-012** · `12-db-sxema.md:1674`; `20-api-moliya-admin.md:1084` ↔ `18:708`, `07:498, 506` (POS-14)
- **Muammo:** POS-14 "Xarajat to'lovi" `reason=expense` yuboradi, `cash_movements.reason` CHECK va 20 enum'ida `expense` yo'q — DB rad etadi.
- **Tuzatish:** 12:1674 CHECK ga `'expense'`; 20:1084 enum'iga `"expense"` (faqat POS voqeasi orqali).
- **Daraja:** kritik

**C-013** · `13-provodka-qoidalari.md:301–306` (§2.18) ↔ `12`, `20:1085`, `31:422`, `33:1567–1568`
- **Muammo:** `cash_movements.reason='other'` (in/out) uchun Dt/Kt yo'q; enum'da bor, QT-M16-01 ishlatadi, 1C ga yuboriladi.
- **Tuzatish:** §2.18: `other/out → Dt 9430 / Kt 5010`; `other/in → Dt 5010 / Kt 9390`; ixtiyoriy `account` (Buxgalter tanlaydi, ruxsat etilgan ro'yxatdan); QT-M16-01 ga kutilgan provodka.
- **Daraja:** kritik

**C-014** · `20-api-moliya-admin.md:1124` ↔ `13:316–319`, `12:1734–1735`, `20:1158, 1182`
- **Muammo:** `BankSettlement` tavsifi: "musbat — kamomad, manfiy — ortiqcha; `net = gross − commission − variance`" — 13 va DDL generated ustunga teskari.
- **Tuzatish:** "manfiy — kamomad (Dt 5910), musbat — ortiqcha (Kt 9390); `net_amount = gross_amount − commission_amount + variance_amount`".
- **Daraja:** kritik

**C-015** · `12-db-sxema.md:444`; `20:658–660, 732` (`POST /branches`, `GET /warehouses`); `07:1049` (BO-12) ↔ `13:18, 68`, 26 #160 · [x2]
- **Muammo:** filial yaratilganda ombor avtomatik, so'rovda `type`/`inventory_account` yo'q, DDL standarti `'2910'` — har do'kon filiali 2910 bilan ochiladi (13: `store` → 2920). BO-12 `inventoryAccount` ni ko'rsatadi, saqlash endpointi yo'q; "harakatdan keyin o'zgarmaydi" xato kodi yo'q.
- **Tuzatish:** `POST /branches` ga `warehouse: {type: "store"|"stock"}` (standart `store`), server `inventory_account` ni `type` dan qo'yadi; DDL'dan `DEFAULT '2910'` olib tashlansin; `PATCH /warehouses/{id}` (`{inventory_account, version}`, `settings.branches`), `stock_moves` bo'lsa `409 WAREHOUSE_ACCOUNT_LOCKED` (17 ga); signup shabloni (12 §5.2) — `type='store'`, `'2920'`.
- **Daraja:** kritik

**C-016** · `12-db-sxema.md:1841` (`stock_moves.moved_at DEFAULT now()`) ↔ `13:430`, `19:681` (#53)
- **Muammo:** #53 `expected` `moved_at` ga tayanadi; offline sotuv kech sinxronlansa `moved_at` = server vaqti → oynadan chiqadi, soxta kamomad va qoldiq ikki marta kamayadi. `post`dan keyin kelgan, `moved_at ≤ counted_at` voqea qoidasi yo'q.
- **Tuzatish:** `moved_at` = hujjat biznes vaqti (POS voqeasi `effective_created_at`, C-102 ga qarang); `DEFAULT now()` faqat back-office. 13 X-02: "post'dan keyin kelgan `started_at < moved_at ≤ counted_at` harakat → avtomatik tuzatuvchi inventarizatsiya qatori + `sync_exceptions`".
- **Daraja:** kritik

**C-017** · `18-api-kassa.md:914`; `16-offline-sync.md:145`; `13:472, 546`; `20:412, 424` · [x2]
- **Muammo:** `sale.created`, `return.created`, `debt_payment` uchun `PERIOD_CLOSED`: FM imzolagan offline chek davr yopilgach sinxronlansa rad etiladi — chek bor, daromad/QQS yo'q. Davr yopish tayyorligi qurilmalardagi yuborilmagan voqealarni tekshirmaydi.
- **Tuzatish:** 16 §3: yopilgan davr sanali POS voqealari **qabul qilinadi**, `entry_date` = birinchi ochiq davrning 1-kuni, `correction_of_period` = asl oy, `sync_exceptions(kind='late_in_closed_period')`. `GET /period-closings/{period}/readiness` ga bloker `devices_unsynced = count(devices WHERE revoked_at IS NULL AND outbox_pending_count>0 AND outbox_oldest_pending_at < period_end)`.
- **Daraja:** kritik

**C-018** · `13-provodka-qoidalari.md:506` (§4.3), §2.6, §2.12
- **Muammo:** aylanma solig'i rejimidagi tenant QQS li faktura bilan qabul qilganda (Dt 4410 yo'q) QQS summasi qayerga borishi aytilmagan — `Kt 6010` muvozanatlashmaydi yoki tannarx kam chiqadi; 2.12 sovg'a QQS qatori ham bu rejimda qo'llanmasligi kerak.
- **Tuzatish:** §4.3: "`regime='turnover'` da 2.6 1-qatori = faktura summasi QQS bilan (`stock_lots.unit_cost` QQS bilan), 2-qator yozilmaydi; 2.12 dagi QQS qatori yozilmaydi; `vat_moves` yozilmaydi".
- **Daraja:** kritik

**C-019** · `08-dizayn-tizimi.md:522, 532–541, 554`
- **Muammo:** 522 qonuniy rekvizit "har qatorda — QQS stavkasi, QQS summasi" (VMQ-943 1-ilova 7-band, 26 #29), lekin chek namunasida faqat jami "QQS (12%, ichida)"; 554 qator ostida faqat MXIK/o'lchov/shtrix kod.
- **Tuzatish:** namunadagi har qatorga ikkinchi kichik qator: `MXIK 0123… · dona · 4780000123456 · QQS 12%: 2 571,43`; 554 ga "va QQS stavkasi/summasi (qator darajasida, qaror #26 formulasi)".
- **Daraja:** kritik

**C-020** · `18-api-kassa.md:412`; `12-db-sxema.md:1033`; `13:131` (§2.5); `33:1499` · [x2]
- **Muammo:** (a) qarzga sotilib hali fiskallashtirilmagan sotuvni `refund_method='debt_adjustment'` bilan qaytarishda ham `kind='return'` chek chiqadi — mavjud bo'lmagan chekka qaytarish; qisman to'langan qarzli sotuv qaytarish tartibi yo'q. (b) `refund_method` = `cash|card|debt_adjustment` — Click/Payme/Uzum/UzQR yo'q; 13 §2.5 `Kt 5710` ni doim `payment_method='card'` bilan yozadi → `card` tranziti manfiy, `click` yopilmaydi, `bank_settlements` buziladi.
- **Tuzatish:** (a) `refund_fiscal = min(return_amount, fiscalized_amount_of_sale − already_refunded)` — fiskal qaytarish cheki faqat shu summaga; qolgani `debt_adjustment` (chesiz, `Kt 4010`). (b) `refund_method` ga `qr` (yoki `uzqr/click/payme/uzum`); 13 §2.5: "`Kt 5710` analitikasi = asl chekning naqdsiz usuli (`sale_payments`), aniqlanmasa `card`".
- **Daraja:** kritik

**C-021** · `13-provodka-qoidalari.md:382`; `20:259–263` ↔ `12-db-sxema.md:1957`
- **Muammo:** `vat_offset` filial bo'yicha (`branch_id` majburiy), `vat_moves` da `branch_id` yo'q — hisoblab bo'lmaydi.
- **Tuzatish:** (a) `vat_moves.branch_id UUID NOT NULL`; yoki (b) `vat_offset` tenant darajasida (`branch_id` NULL, #31), UNIQUE `(tenant_id, period, tax_kind) WHERE tax_kind='vat_offset'`. BO-07 (C-090) shunga moslansin.
- **Daraja:** kritik

**C-022** · `07:283, 296` (POS-08) ↔ `19:368–383, 419`
- **Muammo:** POS-08 "kod `marking_codes` ga yoziladi", lekin `POST /goods-receipts` da `lines[].marking_codes[]` yo'q — CRPT qabul uchun ma'lumot yo'q.
- **Tuzatish:** 19 §8 jadval va PATCH ga `lines[].marking_codes: string[]` (`is_marked=true` da majburiy, GS ajratgichlari saqlanadi, soni = qty).
- **Daraja:** kritik

**C-023** · `07:1060` (BO-12); `20-api-moliya-admin.md:69, 777`
- **Muammo:** 20:777 alohida `POST /cash-registers/{id}/archive` deydi, lekin indeksda yo'q (20:69 "tahrirlash/arxivlash" PATCH ostida) va bo'limi yo'q; 07 `PATCH {archived:true}` chaqiradi, sxema (`{name?, version}`) qabul qilmaydi.
- **Tuzatish:** 20 ga `40i. POST /cash-registers/{id}/archive` (`cash_register.manage`, `{}`, `200 {id, archived_at}`, `RESOURCE_ARCHIVED`); 20:69 → "Kassani tahrirlash"; 07:1060 → archive endpoint.
- **Daraja:** kritik

**C-024** · `20-api-moliya-admin.md:223–234`; `07:951, 962–966` (BO-10); `12:2133`; `11:166` ↔ `03:440`, `13:503` · [x2]
- **Muammo:** 20 #8 E-IMZO `signed_document` bilan "tuzatish/e'tiroz yuborish"; 03/13/07 (VM 736 3¹-ilova 11-band) — alohida e'tiroz arizasi yo'q, tuzatish faqat my.soliq.uz kabinetida, avtomatik yuborish yo'q. "Tasdiqlangan deb belgilash" (07:966) uchun endpoint yo'q, `state_reports.status` da `confirmed` yo'q. Ruxsat: 20:228 "faqat Egasi", 15:174/07:954 — Buxgalter ham.
- **Tuzatish:** 20 #8 body `{comment (majburiy, ≤1000), portal_ref?}`, imzosiz (qayd etish), holat `correction_sent`; `EIMZO_SIGN_FAILED` olib tashlansin. Yangi `8e. POST /state-reports/{id}/confirm`, holat `confirmed` (12:2133, 11:166 ga). 20:228 → "`tax.correction.submit` — Buxgalter va Egasi (15 §2.2)".
- **Daraja:** kritik

**C-025** · `15-xavfsizlik-va-audit.md:154` ↔ `15:80, 236`, `12:3870`, `02:237`, #23
- **Muammo:** matritsada Kassirning `returns.approve` — "–"; katalog, seed va #23 Kassirga `100000.00` limit beradi.
- **Tuzatish:** 15:154 Kassir ustuni → "✓(limit, 100 000)".
- **Daraja:** kritik

**C-026** · `03-modullar-talablari.md:271`; `31-qabul-testlari.md:291` (QT-M07-02) ↔ #49, `07:296`
- **Muammo:** Omborchi tasdiqlashi bilan qoldiq darhol oshadi deyilgan; #49 bo'yicha Omborchi faqat `draft`, qoldiq `purchases.post` (Buxgalter/Egasi) bilan. Test noto'g'ri xatti-harakatni majburlaydi.
- **Tuzatish:** 03:271 → "kirim `draft`; qoldiq `post` da oshadi"; QT-M07-02 → "`status='draft'`, `stock_balances` o'zgarmaydi; `POST /goods-receipts/{id}/post` (Buxgalter) dan keyin 48".
- **Daraja:** kritik

**C-027** · `33-1c-integratsiya.md:1751, 1754, 1760, 1890, 3235, 3309`
- **Muammo:** `verifying` dan chiqish yo'q: `read_totals` 3 marta muvaffaqiyatsiz bo'lsa partiya `verifying` da qoladi (bekor/qayta qurish/W-50 taqiqlangan), `uq_onec_batches_one_active` bazaning navbatini cheksiz bloklaydi.
- **Tuzatish:** T12a `verifying → mismatch` (`read_totals` `failed/expired` → `onec_reconciliations.status='failed'`, `error_code` = vazifa xatosi, Telegram `onec_export_mismatch`); W-50 `mismatch` da ruxsat.
- **Daraja:** kritik

**C-028** · `33-1c-integratsiya.md:1749` (T7), `1829, 1873`
- **Muammo:** T7 faqat "birinchi itemlar `pending → queued`"; dispetcher faqat `queued|unknown` oladi; keyingilarni `queued` qiluvchi qoida yo'q — partiya to'xtaydi.
- **Tuzatish:** T7 yon ta'siri: "partiyaning barcha `pending` itemlari → `queued`" (yoki dispetcher so'roviga `pending`); §7.5 diagramma izohi moslansin.
- **Daraja:** kritik

**C-029** · `27-backlog.md:68, 74, 87, 93, 98`; `31:244` (QT-M04-04)
- **Muammo:** B1 dagi US-M04-04 boshlang'ich qoldig'i `Dt 2910/Kt 0000` posting talab qiladi; posting xizmati va `0000` — B2 da. B1 DoD bajarilmaydi.
- **Tuzatish:** 27:68 dan "va boshlang'ich qoldiq (`stock_openings`)" olinsin; 27:93 ga "`stock_openings` importi/kiritish (US-M04-04 qoldiq qismi)"; 27:74 "US-M04-04 (katalog importi)", 27:98 "US-M04-04 (boshlang'ich qoldiq)".
- **Daraja:** kritik

**C-030** · `27-backlog.md:74, 127`; `31:335` (QT-M09-03)
- **Muammo:** US-M09-03 ("kassada joriy narx") B1 da, test kassa ekranini talab qiladi (kassa B3).
- **Tuzatish:** US-M09-03 B3 Hikoyalariga (27:127).
- **Daraja:** kritik

**C-031** · `27-backlog.md:100` (B2 Tayyor ta'rifi)
- **Muammo:** "13 dagi raqamli misollar avtomatik testlarda o'tadi" — sotuv §2.1–2.4, qarz §2.14, bank §2.18a, tuzatish §2.23, soliq §2.26 B3–B5 da quriladi.
- **Tuzatish:** B2 DoD → "13 §2.6–2.13, §2.20, §2.21, §3 (kirim), §5.5 misollari"; B3 → §2.1–2.5, §2.18, §2.19, §3.2a; B4 → §2.14–2.17, §2.18a, §2.26; B5 → §2.22, §2.23, §5.1.
- **Daraja:** kritik

**C-032** · `27-backlog.md:129` (B3 DoD); `16:237`
- **Muammo:** B3 DoD "konflikt qoidalari (… qarz limiti …)" — M08 B4 da.
- **Tuzatish:** B3 dan "qarz limiti" olinsin; B4 DoD ga "`16` §5 qarz limiti/balans konflikt qoidalari test bilan qoplangan".
- **Daraja:** kritik

**C-033** · `27-backlog.md:155` (B4 DoD) ↔ `27:205, 206`, 26 #127
- **Muammo:** "pilot do'kon qog'oz daftarsiz bir hafta ishlaydi" — pilot B6 da, oferta B6 oxirida, real fiskal B5.
- **Tuzatish:** "QT-M08-01…15 yashil; staging'da ichki demo-tenant bilan bir haftalik qarz daftari ssenariysi"; real pilot mezoni B6 da.
- **Daraja:** kritik

---

## 2. O'rta

### 2.1 Fiskal, offline, to'lov

**C-034** · `16-offline-sync.md:258`; `21-integratsiyalar.md:116` · [x2] — Blok konstantasi uch nomda (`OFFLINE_BLOCK_HOURS` #43, `OFFLINE_FISCAL_BLOCK_HOURS`, `OFFLINE_LEGAL_LIMIT_HOURS`). **Tuzatish:** hamma joyda `OFFLINE_BLOCK_HOURS = 48`. · o'rta

**C-035** · `18-api-kassa.md:284, 803`; `17:302` ↔ #62, `16:286` — `block` rejimida CRPT javob bermasa "offline siyosati taklif qilinadi". #62: `block` — qat'iy rad. **Tuzatish:** "qator chekka qo'shilmaydi; offline/zaxira yo'l yo'q"; 17:302 matni "…markirovkali tovarni hozir sotib bo'lmaydi (qat'iy rejim)". · o'rta

**C-036** · `21:49, 288` ↔ `12:2187–2189`, `11:193`, `03:222` — `outbox_jobs.kind` ro'yxatlari farqli (`poa_send`, `marking_supplier_return`, `marking_writeoff`, `billing_webhook_reconcile` 12 da yo'q; 12 da `marking_return`). **Tuzatish:** 12 CHECK/11 ga `poa_send`, `marking_writeoff`, `billing_webhook_reconcile`; `marking_return` → `marking_supplier_return` hamma joyda. · o'rta

**C-037** · `03:241, 257`; `12:1225–1226` ↔ `19:598, 618`, #63 — 03/12 da e-TTN yo'qligi "ogohlantirish", `vehicle_plate` "send'da"; 19 da `409 ETTN_REQUIRED`, plate `post` da. **Tuzatish:** 03:241 "e-TTN `registered` bo'lmaguncha `send` rad (`409 ETTN_REQUIRED`)"; 03:257 "offline `transfer.sent` `posted` da qoladi (`warnings: ETTN_REQUIRED`)"; 12:1225/1226 shunga. · o'rta

**C-038** · `18:267`; `21:580`; `06:114` ↔ `07:117–118`, `03:29`, `01:44` (#64) · [x3] — `card_type` standarti: 18/21/06 `personal`, 07/03 "har safar so'raladi"; #64 "standart so'raladi" ikki ma'noli; qonuniy rekvizit noto'g'ri oldindan to'ldirilishi mumkin. 08:556 da `unknown` yorlig'i yo'q. **Tuzatish:** 01 #64 → "har to'lovda so'raladi (standart qiymatsiz)"; 18/21/06 dan "standart `personal`" olinsin; 08:556 ga "Noma'lum / Не определён" (yoki 2026-10-22 dan `unknown` taqiqlansin — asoschi qarori). · o'rta

**C-039** · `07:1121` ↔ `12:356–366`, `20:825, 856` · [x2] — `providerFiscalizationOff` (#64) hech qayerda saqlanmaydi, tasdiqsiz provayderni bloklash qoidasi yo'q. **Tuzatish:** `PUT /tenant/integrations/{click|payme|uzum}` ga majburiy `provider_autofiscal_disabled_confirmed: true` → `settings.payment_providers.{p}.autofiscal_off_confirmed_at`; tasdiqsiz `422 VALIDATION_ERROR`. · o'rta

**C-040** · `18:303`; `12:934–961`; `11:259` — to'liq nasiyada chek yo'q, lekin "`fiscal_receipt_seq` saqlanadi"; `sales` da ustun yo'q → `RECEIPT_SEQ_CONFLICT` va uzilish tekshiruvi buziladi. **Tuzatish:** (a) `sales.receipt_seq INT NULL` + UNIQUE `(tenant_id, cash_register_id, shift_id, receipt_seq)`, uzilish tekshiruvi `sales ∪ returns`; yoki (b) "nasiyada `receipt_seq = null`". · o'rta

**C-041** · `18:303–305`; `12:2032, 2037` · [x2] — aralash to'lovda `credit_sale_receipt='credit_type'` bo'lsa bitta sotuvga 2 chek, payload'da bitta `receipt_seq`; aralash chek qatorlarini bo'lish algoritmi yo'q. **Tuzatish:** §4.5: aralash chek qatorlari = C-097 formulasi `ratio = non_debt_amount / sale.total`; keyingi `debt_settlement` cheklari `line_total_i − fiscalized_i` qoldiqdan; `credit_type` uchun payload'ga `credit_receipt_seq`. · o'rta

**C-042** · `18:628`; `21:97` — 18 `FiscalPort.issue_credit_payment()`, 21/#30 `register_sale(kind='debt_settlement')`; 21:97 izohida `credit_sale` yo'q. **Tuzatish:** 18:628 → `register_sale(kind='debt_settlement')`; 21:97 → `# kind: sale | debt_settlement | credit_sale`. · o'rta

**C-043** · `13:221–222`; `12:1497`; `27:146` ↔ `18:637` (#45) · [x2] — hisobdan chiqarilgan qarzga to'lov (`Kt 9390`) ko'zda tutilgan, lekin `amount ≤ receivable_balance` uni doim rad etadi; qaysi sotuvlarni yopishi, chek qatorlari aniqlanmagan. **Tuzatish:** `debt_writeoff_allocations` (eng eski qarzdan); chegara `amount ≤ receivable_balance + Σ written_off_open`; tartib — avval ochiq qarz, keyin hisobdan chiqarilgan; bu qism cheki — tovar qatorsiz umumiy summa (`debt_openings` kabi). · o'rta

**C-044** · `14:440–443, 580`; `15:408`; `16:156`; `21:529`; `23:233` ↔ #20, #34, `03:710`, `07:650` · [x3] — lokaut eksporti "SMS OTP"; #34 — Telegram birinchi. Kim eksport qila olishi aniqlanmagan. **Tuzatish:** "OTP (`purpose=data_export`) — Telegram birinchi, SMS zaxira (#34)"; 14 §16.5: "faqat `billing.manage` (Egasi); boshqasiga `403 FORBIDDEN`". · o'rta

**C-045** · `06-ekranlar-umumiy.md:66` ↔ #62, `16:282`, `07:98` — "qo'lda MXIK kiriting … Asl belgisi chiqarish bajarilmaydi" — eski model; kodsiz markirovkali qator chek chiqarmaydi. **Tuzatish:** "(b) 2–3 urinishdan keyin DataMatrix kodini qo'lda kiritish (faqat online, `POST /marking-codes/verify`, audit `marking.manual_entry`); markirovkali tovarni kodsiz sotish taqiqlanadi". · o'rta

### 2.2 Buxgalteriya va soliq

**C-046** · `13:133` ↔ `18:426`, `12:1069` (#48) — `restock=false`: 13 "tovar omborga qaytadi (`+qty`)", 18 "qoldiqqa qaytmaydi" — sotuvga chiqishi yoki ikki marta kamayishi mumkin. **Tuzatish:** "`stock_moves +qty` asl partiyaga, shu miqdor `stock_lots.blocked_qty` ga (POS sotmaydi); `write_offs` qoralamasi aynan shu `lot_id`/`qty`, post'da `blocked_qty` kamayadi". · o'rta

**C-047** · `13:439, 452, 467`; `11:152`; `12:1859, 1874` · [x2] — manfiy qoldiq/`pending_cost`: saqlash joyi yo'q (`qty_left>=0`, `lot_allocations.lot_id` majburiy), "oxirgi ma'lum narx" aniqlanmagan, AVECO `qty≤0` da nolga bo'linadi, `avg_costs` da qiymat ustuni yo'q, qaysi kirim recost qo'yadi — noma'lum. **Tuzatish:** `avg_costs.total_value NUMERIC(18,2)`; kirim `total_value += qty×cost`, `avg = total_value/qty`; chiqim `cogs = ROUND_HALF_UP(qty×avg,2)`, `total_value −= cogs`; `qty_after ≤ 0` → `avg` o'zgarmaydi, `total_value=0`, `pending`. `lot_allocations` elementi `{lot_id:null, qty, unit_cost, pending:true}`; narx: oxirgi lot → `products.last_purchase_cost` → 0 + `sync_exceptions('cost_unknown')`; keyingi kirim post'i `recost_jobs(from_date = eng eski pending)`. · o'rta

**C-048** · `20:424` ↔ `13:382, 532–546` — davr yopish: `warnings` maydoni yo'q (`tax_settlements` yo'q, `0000 ≠ 0`, ochiq smena, draft hujjatlar), ketma-ket yopish qoidasi yo'q. **Tuzatish:** javob `{blockers[], warnings: ["tax_settlement_missing","opening_0000_nonzero","open_shifts","drafts_in_period"]}`; "faqat eng eski ochiq oy yopiladi" (`PERIOD_CLOSE_OUT_OF_ORDER`, 17 ga). · o'rta

**C-049** · `20:1214` (55g "Moslashtirish" (3)) — "kirimga eng yaqin FIFO yig'indisi": birlik noma'lum, `gross < kirim` da manfiy komissiya, bir importdagi qoralamalar bir 5710 qoldig'ini ikki marta band qiladi. **Tuzatish:** birlik — (filial, usul, `entry_date`) kunlik 5710 debet; eng kichik `n` kun Σ ≥ kirim va `(Σ−kirim)/Σ ≤ 5%`; `gross < kirim` → `unmatched` `reason:"commission_negative"`; import ichidagi va ochiq `draft` larda band qilingan summa ayiriladi. · o'rta

**C-050** · `07:1546, 1565` (BO-24); `20` #55 ↔ `13:316`, `12:1734–1735` · [x2] — formada `variance_amount` yo'q, `net` "gross − commission"; import "gross ni Buxgalter tanlaydi" vs server FIFO; `unmatched_lines` UI yo'q; qoralamani tahrirlash endpointi yo'q. **Tuzatish:** `variance_amount` (`MoneyInput`, ±, faqat `method=collection`); `net = gross − commission + variance`; import natija dialogi (`drafts_created`, `duplicates`, `unmatched_lines`); `55h. PATCH /bank-settlements/{id}` (faqat `draft`, `version`). · o'rta

**C-051** · `23:182`; `11:147` ↔ `12:1945` (`amount > 0`), `13:550` — storno "teskari belgili nusxa" — `ledger_entries` CHECK'ni buzadi. **Tuzatish:** "`ledger_entries` — Dt/Kt almashtiriladi, `amount` musbat; `stock_moves`/`debt_moves`/`cash_moves`/`vat_moves` — teskari ishora". · o'rta

**C-052** · `13:508` (§4.3) ↔ `13:154, 510`, #11, `03:456` — aylanma solig'i bazasi faqat `9020−9040−9050` (8530 va 9390 kirmaydi, 13:154 esa "jami daromadga kiradi"); tamaki 4% uchun mahsulot belgisi yo'q; YaTT 1% `legal_form` ga bog'lanmagan; stavkalar seed jadvali yo'q. **Tuzatish:** baza = `(9020−9040−9050) + 9390 + 8530` (filial bo'yicha); `products.turnover_tax_group` (`general|tobacco`) yoki MXIK prefiks ro'yxati; `legal_form='sole_proprietor'` → 1%; `turnover_tax_rates(code, rate_pct, valid_from)` seed (12). · o'rta

**C-053** · `13:510`; `07:952` (0102) ↔ #30 — qarzga sotuv cheki to'lov kuni, daromad sotuv kuni → davlat 0102 bilan ichki hisob muntazam farq qiladi, sabab sifatida ko'rsatilmagan. **Tuzatish:** "ichki 0102 = Σ `fiscal_receipts` (`sale/return/debt_settlement`) chek sanasi bo'yicha; ledger bilan farq — 'qarzga sotuv vaqt farqi' qatori". · o'rta

**C-054** · `13:566` (§5.5) ↔ `13:374` (§2.23), `20:319` — boshlang'ich qoldiq `entry_date = go_live_date − 1`, `ledger_adjustments` esa faqat joriy ochiq davr. **Tuzatish:** "istisno — `account_dt` yoki `account_kt` = `0000` bo'lsa `doc_date = go_live_date − 1` ruxsat (davr yopilmagan bo'lsa)". · o'rta

**C-055** · `04-biznes-jarayonlar.md:142` (BP-04 5–6-qadam) — "Omborchi | Ichki kirim hujjati" — bunday hujjat yo'q; qurilsa qoldiq ikki marta oshadi. **Tuzatish:** 5-qadam → "Tizim | `returns` posting — `stock_moves +qty` asl partiyaga (`restock=false` — #48)"; 6-qadam aktori "Tizim". · o'rta

**C-056** · `19:632` ↔ `13:174–181` (§2.10) — qabulda ortiqcha (`qty_received > qty`) uchun Dt/Kt yo'q. **Tuzatish:** 13 §2.10: "ortiqcha — `Dt inv_acct / Kt 9390`" yoki 19 da `qty_received ≤ qty` validatsiyasi. · o'rta

**C-057** · `13:398–422` (§2.25), `13:465`; `19:857`; `23:186` · [x2] — risk-flag (`Dt 4410/Kt 6010`) va recost tuzatishlari uchun `doc_type`/`doc_id`/`entry_date`/storno qoidasi yo'q; recost chiqimlar tartibi va `failed` job davr yopishni bloklashi aniqlanmagan. **Tuzatish:** risk-flag → `doc_type='goods_receipts'`, `doc_id` = bog'langan kirim, `entry_date` = bugun; recost → `doc_type` = asl chiqim, eski qator `reversal_of_id` storno + yangi qator, `analytics.recost_job_id`, `entry_date` = asl (davr ochiq bo'lsa), tartib `ORDER BY moved_at, created_at, id`; readiness bloker `recost_jobs.status IN ('queued','running','failed') AND from_date ≤ period_end`. · o'rta

**C-058** · `20:289, 334, 1199` ↔ `13:550` — asl hujjat yopilgan davrda bo'lsa `cancel` ruxsatmi — noaniq. **Tuzatish:** 17 §9 / 13 §5.2: "cancel ruxsat, storno joriy ochiq davr sanasida" (yoki aniq taqiq — tanlash kerak). · o'rta

**C-059** · `01-qarorlar.md:20` (#23 (5)) ↔ `03:114`, `18` (return.created offline), `06:116`, `07:205`, `08:506` — 01 "qaytarish faqat online" (umumiy), qolganlar faqat markirovkali qaytarishni online deydi. **Tuzatish:** asoschi tasdig'i bilan #23 (5) → "offline ko'chirish ruxsat; markirovkali tovarni qaytarish faqat online"; 08:506 moslansin. · o'rta

**C-060** · `03:633`; `20:975`; `23:446` ↔ `13:271–295`, `12:3870–3891` — standart xarajat toifalari 7 ta umumiy nom, seed 21 ta kodli (`payroll_sales` 9410 / `payroll_admin` 9420; `period_taxes` / `tax_payment`) — birlashtirsa #52 buziladi. **Tuzatish:** uch joyda "standart ro'yxat — 13 §2.17 seed xaritasi (21 kod)". · o'rta

**C-061** · `19:16, 783` — FIFO↔AVECO almashtirishda o'tish algoritmi yo'q. **Tuzatish:** 13 §3.1: "FIFO→AVECO: `avg = Σqty_left×unit_cost / Σqty_left`; AVECO→FIFO: har (ombor, mahsulot) uchun bitta partiya `unit_cost=avg`, provodkasiz". · o'rta

### 2.3 1C integratsiyasi

**C-062** · `26-ochiq-savollar-reestri.md:184, 186–192, 201–204` · [x2] — vaqtinchalik qarorlar 33 da yo'q nomlar: `card_transit_account=5711` ("#34" — aslida Google login; #42 = 5710), `credit_customer_mode`, `discount_mode`, `late_receipt_policy`, `cost_source_for_reports`, `PF_*`, `meta_sync`, `fill_accounts_mode`, `ONEC_ACCOUNTS_UNRESOLVED`, `vat_round`, `max_lines_per_doc=300`, `per_call_timeout_s`, "yozish va o'tkazish alohida" (33 §6.3 3 000 qator, §8.3 bitta `Записать(Проведение)`). **Tuzatish:** 33 §16.2 matni bilan almashtirish: 5710 + `val(payment_method)` (#42), `ONEC_PAYMENT_ACCOUNT_NOT_TRANSIT`, `fill_accounts=true`/`ONEC_METADATA_MISMATCH`, `vat_rounding_mode`, `read_metadata`, §2.3 tekshiruv kodlari, `timeout_s=clamp(60+0.4×qatorlar,120,1800)`. · o'rta

**C-063** · `33:1725, 1738, 3312` — "done/partial/mismatch — yakuniy", lekin T13 (`partial → queued`) va W-50 (`mismatch → done`). **Tuzatish:** "yakuniy: `done`, `failed`, `cancelled`; `partial` → T13; `mismatch` → T17 (W-50 → `done`/`mismatch`)" + T17 qatori. · o'rta

**C-064** · `33:3878, 3895`; `26:201–202` — "Bosqich 7 ni faqat #105 bloklaydi", lekin #132/#133 "BLOK", "Bosqich A gacha kod yozilmaydi" (aniqlanmagan), §17.1 P-01…P-22 talab qiladi. **Tuzatish:** 3878 → "#105, #132, #133 (P-03…P-07, P-12) Bosqich 7 kodini bloklaydi"; "Bosqich A" → "§16.1 pilot oldi testlari". · o'rta

**C-065** · `33:725, 772, 1924–1926` — `uuid5` kalitidagi katalog nomlari §8.1 da boshqacha (`catalog_division`/`catalog_expense_item`/`catalog_payment_kind`) — GUID deterministik emas. **Tuzatish:** §8.1 → `catalog_branch`, `catalog_expense_category`, `catalog_payment_method` (yoki §5.10 da aniq xarita); `shared/onec-guid-vectors.json` ga katalog vektori. · o'rta

**C-066** · `33:764, 1678, 1692` — `onec_ref_create_requests`: qayta urinish (max, backoff, yangi vazifa) va tartib (kontragent → shartnoma → …) aniqlanmagan → `ONEC_REF_NOT_FOUND`. **Tuzatish:** `depends_on_request_id` yoki entity tartibi (unit/payment_method → counterparty → counterparty_contract → product); transient/unknown → `sending → approved`, §7.5 backoff bilan yangi vazifa, `attempts ≥ 8` → `failed`. · o'rta

**C-067** · `31-qabul-testlari.md:460–485` · [x2] — US-M19-04 (moslashtirish W-21…W-29) va US-M19-14 uchun QT yo'q. **Tuzatish:** QT-M19-25 (auto-match `exact`/`probable`, tasdiqlanmagan moslash eksportda ishlatilmaydi, `confirm_all_exact`, 5710 bo'lmagan to'lov turida `warnings[]`) va QT-M19-26 (US-M19-14). · o'rta

**C-068** · `33:301, 1030–1035, 1890` — muddati o'tgan o'qish vazifasi: §4.4 "o'sha qator qayta `queued`", §7.6 "yangi vazifa attempt+1"; §5.15 da `expired → queued` yo'q. **Tuzatish:** §4.4 → "yangi vazifa qatori (attempt+1); 3-urinishdan keyin bog'liq reconciliation/ref_create/check `failed`"; §5.15 izoh. · o'rta

### 2.4 Do'kon agenti, auth, AI, billing

**C-069** · `12:494`; `21:845`; `23:282` — agent qurilmasini kassaga bog'lash CHECK bilan taqiqlangan, `fiscal.status` esa `cash_registers.fm_state` va boshqalarni yangilaydi; qaysi FM ga xizmat qilishi bog'lanmagan, payload'da `cash_register_id` yo'q. **Tuzatish:** `agent_cash_registers(agent_id, cash_register_id, provider, local_device_id)`; `fiscal.*` payload `{cash_register_id}`; natija sxemasi shu yerda. · o'rta

**C-070** · `21:822–832`, 21 §1 (`FiscalPort`) — lokal API: port, `/v1/status`, `/v1/print/raw` tanalari, xato shakli/HTTP kodlari, `CashRegisterRef`, `FiscalReceiptPayload`, `FiscalShiftResult`, `ZReport`, `FiscalDeviceStatus`, `UnsentReceipt`, `ResendResult` turlari yo'q — `FakeLocalBridge` ularga tayanadi. **Tuzatish:** 21 §16.1 "Lokal API sxemalari": port (masalan 47110, sozlanadi), har yo'l JSON sxemasi, xatolar `{code, message_key}` + 401/403/409/423; hamkorga bog'liq maydonlar "adapter ichida". · o'rta

**C-071** · `27-backlog.md:168` ↔ `21:819`, 34 §14.3 — B5 ga "tarozi (PLU yuklash, jonli og'irlik)"; 21: tarozi MVP'dan keyin (MVP'da CSV), jonli og'irlik Web Serial, agentsiz. **Tuzatish:** "TCP 9100 printer — B5; `scale.plu_upload` — MVP'dan keyin (MVP'da CSV eksport); jonli og'irlik — Web Serial, MVP'dan keyin". · o'rta

**C-072** · `17-api-umumiy.md:161`; `15:225` — "`202`/`pending_approval` holati" barcha hujjatlarga taalluqli deb o'qiladi (#25 ga zid). **Tuzatish:** 17:161 → "`202 {status:"draft", approval_request_id}` (`APPROVAL_REQUIRED`); `pending_approval` faqat `price_changes` da"; 15:225 → "`approval_requests(status='pending')` yaratiladi, hujjat `draft` da qoladi (#25)". · o'rta

**C-073** · `17-api-umumiy.md:162` ↔ `15:139`, #28 — "faqat Egasi" misollarida `platform.admin`. **Tuzatish:** alohida "faqat `platform_admins` (`aud=urn:erp:platform`)". · o'rta

**C-074** · `07:804` ↔ `19:93, 114` · [x2] — `nameRu` saqlash `prices.edit` bilan, `PATCH /products/{id}` `catalog.manage` talab qiladi; max 200 vs 255. **Tuzatish:** ruxsat `catalog.manage`, max 255. · o'rta

**C-075** · `18:680, 847`; `19:146, 164, 168, 298, 310, 670, 827, 851` — ruxsat ko'rsatilmagan endpointlar (`debt-doubtful-flags/{id}/unflag`, `payments/checkouts/{ref}`, `mxik-codes/{code}`, `product-categories` PATCH/archive, `import-jobs/{id}/validate`, `…/errors`, `stock-counts/{id}/lines/{line_id}`, `recost-jobs/{id}`, `einvoices/{id}`). **Tuzatish:** mos ravishda `debts.forgive` (Egasi); `sales.create`; `catalog.manage`; `catalog.manage`; `POST /import-jobs` bilan bir xil; xuddi shu; `stock.count.create`; `stock.view`; `purchases.post`. · o'rta

**C-076** · `20:1307–1308` (`POST /billing/checkout`); `11:173`; `12:600`; `07:1271` · [x2] — yillik summa formulasi (−20% qo'shimcha kassaga tegadimi), `current_period_end` hisoblash, `trial` tugagach holat, `restricted → closed` triggeri yo'q. **Tuzatish:** `amount = 99000 + 39000×extra_qty` (oy) / `(99000 + 39000×extra_qty)×12×0.8` (yil) (asoschi tasdig'i) → `amount_breakdown`; `new_end = max(current_period_end, now) + 1 oy | 12 oy`; `trial` → `grace` (24 soat) → `restricted`; `closed` — Egasi amali yoki `restricted` da N kun (asoschi). 07:1271 `month|year`. · o'rta

**C-077** · `08-dizayn-tizimi.md:478` — "Kod SMS orqali yuborildi" doim. **Tuzatish:** `channel_used` bo'yicha `otp_sent_telegram` / `otp_sent_sms`. · o'rta

**C-078** · `14:565` (`/auth/signup`) ↔ `12:377`, `07:1338–1339, 1351`, `20:825`, #61 · [x2] — `users.name NOT NULL` manbasi yo'q; BO-21 `legalForm`, `acceptTerms` yig'adi, saqlash joyi yo'q (`PATCH /tenant/settings` `accepted_terms_*` qabul qilmaydi). **Tuzatish:** signup body'ga `owner_name` (2–100), `legal_form`, majburiy `accepted_terms_version` (joriy `terms_versions` bilan mos, aks holda `VALIDATION_ERROR`); server `accepted_terms_at`, `_ip` yozadi; BO-21 ① ga `ownerName`; 15 §1.5 ga. · o'rta

**C-079** · `20:1504–1516` (`POST /ai/ocr/jobs`) — `ai.ocr_enabled=false` da javob aniqlanmagan. **Tuzatish:** 17 ga `AI_FEATURE_DISABLED` (403), endpoint xatolar ro'yxatiga. · o'rta

**C-080** · `26-ochiq-savollar-reestri.md:50` ↔ #16, `05:67` — AI-10 "MVP'da qoida-asosidagi tavsiya". **Tuzatish:** "MVP'dan keyin; boshlanishi qoida-asosidagi, ML keyin". · o'rta

**C-081** · `30-izchillik-matritsasi.md:186` ↔ #20, `03:710` — `/billing/export-my-data` butunlay MVP'dan keyin, lekin lokaut eksport yo'li shu. **Tuzatish:** "endpoint MVP'da (lokaut, #20); faqat `closed` holat (US-M17-05) — MVP'dan keyin". · o'rta

### 2.5 Ekran ↔ API ↔ ruxsat

**C-082** · `18:209–214` ↔ `07:265` (POS-07), `15:209` — `GET /shifts/{id}/z-report` faqat `reports.sales.view`, Kassirda yo'q → 403. **Tuzatish:** "`reports.sales.view` yoki `cash.count.shift`". · o'rta

**C-083** · `18:734` ↔ `07:174` (POS-04) — `GET /fiscal-receipts` Kassirga yopiq. **Tuzatish:** "`reports.sales.view` yoki `sales.create` (o'z filiali)". · o'rta

**C-084** · `07:232` (POS-06) ↔ `15:186`, `18:755` — POS `POST /einvoices` chaqiradi (`einvoice.create` Kassirda yo'q); server o'zi qoralama yaratadi. **Tuzatish:** "B2B mijozda server avtomatik `draft` yaratadi (18 §14a), POS chaqirmaydi". · o'rta

**C-085** · `18:585, 603, 610` ↔ `19:430, 434, 447` — `counterparties` endpointlarining ruxsatlari 18 va 19 da farqli (PATCH 19 da yo'q). **Tuzatish:** yagona manba 18 §11, OR qoidalari: GET `sales.create | debts.create | stock.view | purchases.create`; POST `debts.create | debts.limit.manage | purchases.create (is_supplier)`; PATCH `debts.limit.manage | purchases.create`; 19 §9 havola qiladi. · o'rta

**C-086** · `07:741, 761` (BO-04); `30:84` ↔ `19:550–553, 564` — "Yetkazib beruvchiga qaytarish" `purchases.return` bilan create+post, `/post` `purchases.post` talab qiladi; formada `receipt_id`, `lines[].receipt_line_id`, `lot_id`, `reason` qiymatlari yo'q. **Tuzatish:** "Qoralama" (`purchases.return`) va "O'tkazish" (`purchases.post`) ajratilsin; `receiptId`, `lines[].lotId`, `reason` = `expired|damaged|excess|other`. · o'rta

**C-087** · `07:755` (BO-04 AI-03) ↔ `20:1535`, `15:166` — OCR qoralamani tasdiqlash `purchases.receive` talab qiladi, ekran `purchases.create` deydi; Menejer 403. **Tuzatish:** "`purchases.receive` + `ai.ocr.use`". · o'rta

**C-088** · `07:286` (POS-08) ↔ `19:368, 374`, `12:1109, 1152, 1157` — `discrepancyReason` uchun ustun yo'q; `receivedQty ≥ 0` vs `> 0`; `supplier_id/cost/vat_rate` ekranda yo'q, `po_lines.price` NULL bo'lishi mumkin. **Tuzatish:** `receipt_lines.discrepancy_reason` + API enum (yoki 07 dan olib tashlash); "0 qator yuborilmaydi"; 19 §8 "`po_id` berilsa `supplier_id/cost/vat_rate` PO va mahsulot kartasidan; `po_lines.price` NULL bo'lsa `cost` majburiy". · o'rta

**C-089** · `07:330–331` (POS-09) ↔ `19:592–593` — `fromBranchId/toBranchId` vs `from_warehouse_id/to_warehouse_id`. **Tuzatish:** `fromWarehouseId/toWarehouseId` (MVP: filial orqali tanlanadi, #54). · o'rta

**C-090** · `07:869, 875` (BO-07) ↔ `20:261` — `POST /tax-settlements` `branch_id` talab qiladi, 07 yubormaydi. **Tuzatish:** C-021 qaroriga mos: `branch_id` bo'lsa — body va `branchId` Select; tenant darajasi tanlansa — 20 dan `branch_id` olinsin. · o'rta

**C-091** · `07:907, 914, 916` (BO-08) ↔ `20:304, 319` — filtr `doc_date__*` vs `entry_date__*`; tuzatish `entry_date` vs `doc_date`; `account_dt/account_kt/amount` maydonlari yo'q. **Tuzatish:** nomlar to'g'rilansin; `adjustment.accountDt`, `accountKt` (4 raqam), `amount` (>0). · o'rta

**C-092** · `12:1662, 1675`; `20:1084` ↔ `18:700–712`, `07:498` — `owner_withdrawal` da `counterparty_id` (ta'sischi) majburiy, POS voqeasi va POS-14 da yo'q. **Tuzatish:** 18 §13.1 ga shartli `counterparty_id`; POS-14 ga `founderId` Select. · o'rta

**C-093** · `07:1114–1117, 1130` (BO-14) ↔ `20` #40c/#40d, `12:644` — `taxRegime` → `POST /tenant/tax-regimes`, `crptApiKey`/`fakturaUzCredentials` → `PUT /tenant/integrations/{provider}` ma'lumot manbasida yo'q; `costingMethod` `AVECO|FIFO` vs `aveco|fifo`. **Tuzatish:** 07:1130 ga 40c/40d; enum kichik harf. · o'rta

**C-094** · `07:1211–1215` (BO-17) ↔ `20:935` — `default_account="6410"` toifasida `tax_type` majburiy, formada yo'q. **Tuzatish:** `taxType` Select (`vat|turnover|pit|social|property|land|other`), 6410 da majburiy. · o'rta

**C-095** · `12:910, 1431, 1457, 1511`; `11:164–165` ↔ `18:178`, `19:688`, `17:144–146` — `shifts.status='closing'` ga hech bir voqea olib bormaydi; `posted` inventarizatsiyani bekor qilish 11 da yo'q; `debt_payments/debt_openings/debt_writeoffs` da `cancelled` bor, `/cancel` va `GET` ro'yxat yo'q. **Tuzatish:** `shift.closing_started` voqeasi yoki `closing` olib tashlansin; 11:164 ga "`posted → cancelled` (storno)"; 18 §12.3–12.5 ga `POST /{id}/cancel` va `GET`. · o'rta

### 2.6 Algoritmlar

**C-096** · `13:121` — aralash to'lovda yagona QQS qatorining Dt hisobi noma'lum. **Tuzatish:** har to'lov `p`: `vat_p = ROUND_HALF_UP(vat_total × p.amount / total, 2)` (oxirgisi qoldiq); `Dt acct(p) / Kt 9020 = p.amount − vat_p`; `Dt acct(p) / Kt 6410 = vat_p`. · o'rta

**C-097** · `18:628`; `31:327` — `debt_settlement` proporsional qatorlar: yaxlitlash, qoldiq qaysi qatorga, qty, markirovkali qty=1 bo'lagi aniqlanmagan. **Tuzatish:** `ratio = alloc/sale.total`; `amt_i = ROUND_HALF_UP(line_total_i×ratio, 2)`, eng katta `line_total` (teng — eng katta `line_no`) qoldiqni oladi; `qty_i = ROUND_HALF_UP(qty_i×ratio, 3)`; `vat_i` #26 formulasi; markirovka kodi faqat yakuniy (kumulyativ ratio=1) chekda; `sale_lines.settled_amount` kumulyativ. · o'rta

**C-098** · `18:647` ↔ `13:221` — allokatsiya `due_date ASC`, `due_date` NULL bo'lishi mumkin, tie-break yo'q. **Tuzatish:** `ORDER BY COALESCE(due_date, doc_date), doc_date, doc_id`. · o'rta

**C-099** · `18:415–423` — chegirmali qatorni qaytarishda summa aniqlanmagan (faqat `unit_price`). **Tuzatish:** `refund_line = ROUND_HALF_UP(sale_line.line_total × ret_qty / sale_line.qty, 0)`, oxirgi qaytarish qoldiqni oladi; `unit_price` faqat ma'lumot, server tekshiradi. · o'rta

**C-100** · `18:250–254` ↔ `03:132` — "chekka 5%" limit, API faqat qator chegirmasi; chek chegirmasini taqsimlash yo'q; server mijozning `discount_pct` iga ishonadi. **Tuzatish:** server `pct_i = discount_amount_i / ROUND_HALF_UP(qty×price,0) × 100` hisoblaydi; chek chegirmasi `line_gross` ulushida taqsimlanadi (qoldiq eng katta qatorga); limit `Σdiscount_manual / Σline_gross × 100`. · o'rta

**C-101** · `19:214` — narx farqi foizi formulasi yo'q (yangi tovar — nolga bo'linish, filial/global asos). **Tuzatish:** `base` = filial narxi → global narx; `base` yo'q — limit tekshirilmaydi; `pct = |new − base| / base × 100`; birorta qator oshsa butun hujjat tasdiqqa, `requested_value = max(pct)`. · o'rta

**C-102** · `16:303` ↔ `16:357` — soat clamp faqat pastki chegara, test yuqorini kutadi; buxgalteriya sanasi qaysi qiymatdan — noma'lum. **Tuzatish:** `effective_created_at = clamp(created_at, received_at − OFFLINE_CLAMP_WINDOW, received_at + CLOCK_SKEW_WARN_S)`; `doc_date` va 48 soat hisobi shundan; xom qiymat `client_created_at`. · o'rta

**C-103** · `16:116` — `RECEIPT_SEQ_CONFLICT` → `rejected`, lekin chek FM imzolangan bo'lishi mumkin. **Tuzatish:** `fm_receipt_seq`/`fiscal_sign` bo'lsa qabul, `receipt_seq` qayta raqamlanadi, `sync_exceptions(kind='receipt_seq_conflict')`; imzosiz bo'lsagina rad. · o'rta

**C-104** · `19:678–688` — `post` da sanalmagan qatorlar qoidasi yo'q; 688 o'zaro zid jumla. **Tuzatish:** `counted IS NULL` → `422 COUNT_LINES_INCOMPLETE` (`?treat_uncounted_as_zero=true` bilan majburlash) yoki farq 0 + `uncounted_lines[]`; 688 → "`posted` — storno; `counting/review` — registrsiz `cancelled`". · o'rta

**C-105** · `19:720` ↔ `13:200` — javobgar yo'q bo'lsa 19 "5910→9430", 13 to'g'ridan `Dt 9430`. **Tuzatish:** 19:720 → "belgilansa `4730`, aks holda `9430` (13 §2.12)". · o'rta

**C-106** · `20:486–493` — `days_overdue`/`bucket` asosi aniqlanmagan. **Tuzatish:** `overdue_since = min(COALESCE(due_date, doc_date))` ochiq hujjatlar; `days_overdue = max(0, as_of − overdue_since)`. · o'rta

**C-107** · `20:365–372, 447–454` — `total_sales`, `revenue`, `discounts` ta'rifi yo'q. **Tuzatish:** `total_sales = Σ sales.total (QQS bilan, posted) − Σ returns.total`; P&L `revenue = Kt 9020`, `returns = Dt 9040`, `discounts = Dt 9050` (`net` rejimda `Σ sale_lines.discount_amount` QQSsiz), `cogs = Dt 9120`. · o'rta

**C-108** · `04:99, 118` ↔ 26 #114 — "bank orqali to'lovchi YaTT" uchun e-faktura majburiy, modelda YaTT belgisi yo'q. **Tuzatish:** "faqat `kind=company`" yoki `counterparties.is_sole_proprietor` + qoida `company OR (is_sole_proprietor AND method='bank')`. · o'rta

### 2.7 Huquqiy da'volar

**C-109** · `08:556` ↔ `12:2018`, 26 #84 — "Nasiya/В долг" to'lov shakli yorlig'i; `payment_form` CHECK `cash/card/qr/mixed`. **Tuzatish:** olib tashlansin; `debt_settlement` chekida shakl `debt_payments.method` dan; sarlavhada "Qarz to'lovi / Погашение долга". · o'rta

**C-110** · `03:415, 435` — "QQS 12%, 0%, ixtiyoriy 6%" — 6% manbasiz, 01/13/26 da yo'q. **Tuzatish:** "12% (SK 258-modda), 0%/imtiyoz kodi (`vat_exemption_code`)". · o'rta

**C-111** · `26:140` (#145) ↔ `13:88`, `12:360–361`, `20` — `discount_posting` standarti 26 da `net`, qolganlarda `gross_9050`. **Tuzatish:** 26 #145 → "`gross_9050` standart / `net` ixtiyoriy". · o'rta

**C-112** · `03:446`; `02:200`; `04:227, 240` — "oyning 10-sanasigacha interaktiv ma'lumot" — manbasiz. **Tuzatish:** manba (VM 736 3¹-ilova bandi / SK moddasi) yoki "ichki eslatma sanasi, qonuniy muddat emas". · o'rta

### 2.8 Backlog (27)

**C-113** · `27:114, 148, 200–201`; `31:199, 242, 247` — M18 bildirishnomalari (40 soat, smena farqi, yaroqlilik, kam qoldiq) M18 qurilishidan oldin talab qilinadi. **Tuzatish:** B2 ga "bildirishnoma voqealari `outbox_jobs(kind='telegram')` ga yoziladi (yuborish — B4)"; yaroqlilik ogohlantirishi 27:201 → B4; 27:200 dagi M18 ogohlantirishlar 27:148 ga. · o'rta

**C-114** · `27:90, 98`; `31` QT-M06-04, QT-M05-05 — offline ko'chirish/sanash testlari `/sync/push` (B3) ni talab qiladi; QT-M05-05 "Android POS" (MVP'dan keyin). **Tuzatish:** B2 ga "offline `transfer.*`/`stock_count.line_recorded` — B3 sync bilan"; ikki test B3 DoD ga; QT-M05-05 → "veb PWA (POS-10)". · o'rta

**C-115** · `27:91`; QT-M06-07 — e-TTN stub ko'chirishni `registered` qilishi aytilmagan (E-IMZO B5). **Tuzatish:** "`FakeEInvoiceAdapter` e-TTN ni darhol `registered` qiladi (staging/test); real yuborish va E-IMZO — B5". · o'rta

**C-116** · `27:69, 76, 204, 284`; 26 #45 — B1 da "haqiqiy provayder", DoD "OTP (Telegram/SMS)", Eskiz shartnomasi B6. **Tuzatish:** 27:69 "SMS — `EskizSmsAdapter` `ESKIZ_TEST_MODE=true` B6 gacha"; B1 DoD "Telegram OTP real; SMS — test rejimi". · o'rta

**C-117** · `27:166, 190, 286`; `01:69` (#38); 26 #105; `25:20` — OV sertifikat: #38 "Bosqich 7 dan oldin", 26/25 lokal ko'prikda "Bosqich 5 dan oldin"; B6 pilot kirish shartida yo'q. **Tuzatish:** 27:190 ga "lokal fiskal ko'prik tanlangan bo'lsa — Authenticode OV olingan (26 #105)"; #38 → "lokal ko'prikda B5/B6 pilotidan oldin". · o'rta

**C-118** · `27:200` ↔ `01:91` (#54) — server yorliq PDF #54 da "Bosqich 2 oxiri", 27 da M09 yorliq B6. **Tuzatish:** bittasi tanlansin (#54 → "Bosqich 6" yoki 27:94 ga vazifa). · o'rta

**C-119** · `27:111, 252` ↔ `03:26`, `18:264`, `13` §2.2, `27:143` — Uzum B3 da yo'q va MVP'dan keyingi ro'yxatda, boshqa fayllar MVP deydi. **Tuzatish:** 27:111 "Click/Payme/Uzum ixtiyoriy", 27:252 dan "Uzum to'lovi" olinsin (yoki teskari — qaror kerak). · o'rta

**C-120** · `27:140–146` (B4) — `debt_writeoffs` (13 §2.15, 18 §12.5) va shubhali qarz belgisi (18 §12.6) uchun vazifa yo'q; QT-M08-13 talab qiladi. **Tuzatish:** B4 ga "`debt_writeoffs` (`POST /debt-writeoffs`, `/post`, Egasi) va `debt-doubtful-flags` (13 §2.15/§2.15a)". · o'rta

**C-121** · `27:182` (B5 DoD) ↔ 26 #40, #109, `05` 6-xulosa — DoD real CRPT/hamkor javobiga bog'liq. **Tuzatish:** ikkiga: "CI'da FM emulyatori va `FakeMarkingAdapter` bilan QT-M01-21, QT-OFFLINE48-05, QT-M01-18/20 yashil" (majburiy); "real hamkor/CRPT test muhitida" — 26 #109/#40 javobidan keyin. · o'rta

**C-122** · `27:51` (B0 DoD) — seed, #58c migratsiyasi, #57 CI darvozasi, #65 sirlar/PITR/tashqi zaxira, QT-ID'lar uchun mezon yo'q. **Tuzatish:** "QT-RLS-01…08, QT-OAUTH-01…07 yashil; CI'da mypy `--strict`/pip-audit/npm audit/gitleaks; `devices.kind`/`signing_keys.purpose` migratsiya testi; tashqi provayderdagi nusxadan staging restore bir marta; QT-AI-PII-01 yashil". · o'rta

**C-123** · `27:117, 129`; 26 #139 — US-M01-07 (Must) uchun QT yo'q; printer matritsasi testining ID si yo'q. **Tuzatish:** 31 ga QT-M01-22 (cp866/raster/U+02BB, `weight_barcode_templates`), B3 DoD dan havola. · o'rta

---

## 3. Kichik

**Fiskal/to'lov**
- **C-124** · `21:116` — 46 soat modali matni #43 dan farqli; blokda ruxsat etilgan amallar to'liq emas. **Tuzatish:** matn #43 dagi; ro'yxat 16 §6 bilan bir xil. · kichik
- **C-125** · `06:41`; `07:840–846` (BO-06) — blok ro'yxatida kredit cheki yo'q; BO-06 da `fiscal-blocked` holati yo'q. **Tuzatish:** 06:41 "(sotuv, qaytarish, qarz to'lovi, kredit cheki)"; BO-06 ga `fiscal-blocked`. · kichik
- **C-126** · `16:16`; `18` §4.1 — UzQR "faqat online" havolasi noto'g'ri bo'limga; server offline statik UzQR'ni tekshirmaydi. **Tuzatish:** 18 §4.1: "`is_offline=true` va `method='uzqr'` → `VALIDATION_ERROR` (`validation.uzqr_online_only`)". · kichik
- **C-127** · `07:93, 129` — 46 soat modali POS-02 va POS-03 da ikki marta. **Tuzatish:** faqat POS-03 "TASDIQLASH". · kichik
- **C-128** · `07:122` — `qrType` default "Tenant sozlamasi" — bunday sozlama yo'q. **Tuzatish:** default `static`. · kichik
- **C-129** · `18:313` — UNIQUE `tenant_id` siz. **Tuzatish:** `UNIQUE (tenant_id, cash_register_id, shift_id, receipt_seq)`. · kichik
- **C-130** · `07:115` ↔ `12:996`, `18:264` · [x2] — `card_manual` enum. **Tuzatish:** `card` (label "Karta (qo'lda)"). · kichik

**Buxgalteriya**
- **C-131** · `26:65` — ish haqi `Dt 9420` faqat. **Tuzatish:** `Dt 9410|9420 / Kt 5010|5110` (#52). · kichik
- **C-132** · `13:566` — "1C eksportida 0000 → 000" — #39 ga zid. **Tuzatish:** "Bosqich 7 da yuborilmaydi (33 §6.12); keyin `ВводНачальныхОстатков`". · kichik
- **C-133** · `03:362, 366` — "Ochiq savollar 14" eski havola; daromad vaqti "qaror #42" (to'g'risi #30). **Tuzatish:** "26 #9 (OQ-002)", "#30". · kichik
- **C-134** · `11:158–176` — `bank_settlements` holat mashinasi yo'q. **Tuzatish:** `draft → posted → cancelled`, `statement_import` avto-post qilinmaydi. · kichik
- **C-135** · `31` — inkassa testi yo'q. **Tuzatish:** QT-M11-13: inkassa 2 000 000, bank 1 990 000, komissiya 5 000, kamomad −5 000 → `Dt 5110 1 990 000`, `Dt 9410 5 000`, `Dt 5910 5 000` / `Kt 5710 2 000 000`. · kichik
- **C-136** · `13:5, 376–398` — "BP-01…12"; bo'limlar tartibi 2.24→2.26→2.25. **Tuzatish:** "BP-01…15"; §2.25 oldinga. · kichik
- **C-137** · `13:257` — QQS krediti proporsiyasi yaxlitlash qoidasi yo'q. **Tuzatish:** `vat_i = ROUND_HALF_UP(invoice_vat × alloc_i / invoice_total, 2)`, yopuvchi to'lov qoldiqni oladi. · kichik
- **C-138** · `13:95` — `gross_9050` 1a-qator 1 tiyin balans xavfi. **Tuzatish:** `1a = (list_total − list_vat) − (net_total − net_vat)`. · kichik
- **C-139** · `13:438` — FIFO tartib kaliti. **Tuzatish:** `ORDER BY received_at, id WHERE qty_left > 0`. · kichik
- **C-140** · `03:444`; `07:966` ↔ `12:2133` — BO-10 holat nomlari 3 xil. **Tuzatish:** 12 enum'i (C-024 dagi `confirmed` bilan). · kichik
- **C-141** · `04:203`; `03:451` — "AI risk-scoring" — aslida davlat xavf-baholashi/qo'lda; diagrammada `unknown` tarmog'i yo'q. **Tuzatish:** "Davlat xavf-baholashi (VM 830) / qo'lda belgi"; `unknown → qizil kabi`. · kichik

**Huquqiy manbalar**
- **C-142** · `13:503` — "QQS hisoboti 15-sanagacha" — manbasiz. **Tuzatish:** manba yoki o'chirish. · kichik
- **C-143** · `05:179` — "1 BHM/yil ≈ 36 700". **Tuzatish:** "1 BHM/yil (440 000, 26 #25) ≈ 36 700 so'm/oy". · kichik
- **C-144** · `05:121`; `02:41` — "jarima 2–20% aylanma" — qonun manbasi yo'q. **Tuzatish:** modda yoki "(raqobatchi sharhlari, tasdiqlanmagan)". · kichik
- **C-145** · `29:178, 189` — e-TTN "o'z omborlari orasida ham majburiy" — umumlashtirilgan. **Tuzatish:** "avtotransportda (`vehicle`) majburiy; piyoda/jamoat transportida — yo'q (VM 249 31-ilova 24-band)". · kichik
- **C-146** · `19:969` — 72 soat/3 ish kuni uchun 26 #40 havolasi. **Tuzatish:** "26 #117 (OQ-027)". · kichik

**1C**
- **C-147** · `33:213, 1851, 3514` — `duplicate` sinfi §12 da yo'q. **Tuzatish:** §7.5 va `errors.py` izohidan olib tashlash (`ONEC_DUPLICATE_REF` → `unknown`). · kichik
- **C-148** · `33:1389, 1392, 3918`; `27:223` — `devices.kind`/`signing_keys.purpose` B7 vazifasi sifatida takror (#58c — B0). **Tuzatish:** "allaqachon Bosqich 0 da"; 27:223 "§5.22 dagi qolganlari". · kichik
- **C-149** · `33:99`; `34:251` — `V82.COMConnector` tekshiruvi (§2.1 faqat 8.3/8.5). **Tuzatish:** olib tashlash yoki "8.2 → `ONEC_PLATFORM_VERSION_MISMATCH`". · kichik
- **C-150** · `33:1525` — `orp_negative_payment` "`Оплата` manfiy qatori" — #39 ruhiga zid. **Tuzatish:** "`СуммаОплаты` dan ayiriladi; < 0 → `ONEC_ORP_CASH_MISMATCH`". · kichik
- **C-151** · `31:485` — QT-M19-04 ↔ P-05. **Tuzatish:** P-13. · kichik
- **C-152** · `14:126` — lokautda faqat A-01/A-03 rad. **Tuzatish:** "A-01, A-02, A-03 → 403; A-04…A-10 ruxsat". · kichik
- **C-153** · `33:1124–1125, 1161, 2715`; `31:461` — `ONEC_PAIRING_CODE_EXPIRED` ga yetib bo'lmaydi. **Tuzatish:** `onec_device_auth_approve` → `text` (`ok|invalid|expired`), W-04 shunga. · kichik
- **C-154** · `26:133` (#134) — "33 §10" → §9.10/§12. **Tuzatish:** "`33` §9.10, §12; `34` §8.12". · kichik
- **C-155** · `33:1877` — dispetcher izohi "phase ichida" vs qat'iy ketma-ket. **Tuzatish:** "qat'iy `(phase, seq)`; `retry_wait` keyingilarni ham kuttiradi (ataylab)". · kichik

**Agent/auth/AI/billing**
- **C-156** · `23:284` — `fiscal.zreport` natijasi `fiscal_receipts(kind='z_report')` vs `ZReport`. **Tuzatish:** "`ZReport` → `fiscal_receipts(kind='z_report')` yoziladi". · kichik
- **C-157** · `02:219`; `07:705` — M07 da Menejer "Y, T" (15 da `purchases.receive/post/pay` yo'q). **Tuzatish:** "Y"; 07:705 rollarga ajratilsin. · kichik
- **C-158** · `15:127` — `billing.manage` "Tarif tanlash". **Tuzatish:** "Obuna to'lovi (oy/yil), qo'shimcha kassa, to'lovlar tarixi". · kichik
- **C-159** · `01:19`; `05:179`; `09:169` ↔ `25:17, 255, 262–263, 284` — unit-iqtisod va AI xarajati raqamlari farqli. **Tuzatish:** 25 §11 manba, 01 #22/05/09 moslansin. · kichik
- **C-160** · `14:417, 485` ↔ #44 — admin-bff va `sync.drain` 5 daq. **Tuzatish:** #44 ga istisnolar ro'yxati. · kichik
- **C-161** · `19:359` — `ai.cross_border_enabled`. **Tuzatish:** `tenants.settings.ai_cross_border_enabled`. · kichik
- **C-162** · `32:347` — `mypy app`. **Tuzatish:** `mypy --strict app` (#57). · kichik
- **C-163** · `12:3867` — "05-xavfsizlik §2.3". **Tuzatish:** "15-xavfsizlik-va-audit §2.3". · kichik

**Ekranlar**
- **C-164** · `07:1272` vs `07:1271` — `period: month|year` vs `monthly|yearly`. **Tuzatish:** API qiymatlari. · kichik
- **C-165** · `07:1156` — `from-receipt` uchun `einvoice.sign` (18:761 `einvoice.create`). **Tuzatish:** `einvoice.create`. · kichik
- **C-166** · `07:1243` — PLU eksport `labels.print` (19:811 `catalog.manage`). · kichik
- **C-167** · `07:938` (BO-09) — Menejer QQS registri, `/vat-moves` `tax.vat.view`. **Tuzatish:** Menejerdan olib tashlash yoki ruxsat. · kichik
- **C-168** · `07:839` — AI qoralama `ai.chat.use` (20 #77) talab qiladi. · kichik
- **C-169** · `07:1171` (BO-16) — `write_off_over_limit` uchun `stock.writeoff` yo'q (15 §2.3). · kichik
- **C-170** · `20:48` vs `20:491`; `18:692`; `07:845` — indeks ruxsati farqli; `bucket=` parametri 20 da yo'q. **Tuzatish:** indeks tenglashtirilsin; `bucket=0-30|31-60|60+`. · kichik
- **C-171** · `17:148` — `stock-counts/{id}/review` → `submit-for-review` (19:674). · kichik
- **C-172** · `07:995, 1017` (BO-11); `14:517`; `20:613` — revoke dialogida `reason`/`confirm_pending_loss` yo'q; `device_name` API'da yo'q; `GET/POST /admin/users` 14 §18.2 da aniqlanmagan. · kichik
- **C-173** · `07:494–500, 1213, 51, 1334` — kichik validatsiya farqlari (izoh 200 vs cheksiz; `cancel_reason ≥ 10` vs majburiy; `openingCash` butun son vs Money 2 xona; parol ≥8 — 14 §4 da siyosat yo'q). **Tuzatish:** 17–20 / 14 bilan tenglashtirish. · kichik
- **C-174** · `30:84, 91, 97, 98` — matritsa qatorlari noto'g'ri ekran/endpoint/ruxsat (US-M08-02 → BO-06; US-M08-08 → `POST /counterparties/{id}/statement-link`; `PATCH /counterparties` → `debts.limit.manage`; US-M07-05 → `purchases.return` + `purchases.post`). · kichik
- **C-175** · `07:795–811, 462, 464`; 17 §15 — BO-05 "Chegirma qoidalari" MVP'dan keyin (#33) belgilanmagan, formada `name/scope/priority` yo'q; `debt_payment.created → /post` noto'g'ri; debt-openings ruxsati farqli; foydalanilmaydigan kodlar (`INVALID_CREDENTIALS` BO-01 da ishlatilsin, `NEGATIVE_STOCK_NOT_ALLOWED`, `DEBT_ALREADY_PAID`, `DOUBTFUL_FLAG_REQUIRES_OWNER`, `RECOST_REJECTED_PERIOD_CLOSED`). · kichik

**Backlog**
- **C-176** · `27:122, 175, 178` — `DB-01/09/10/12` ID'lari yo'q; `18` §15a yo'q (§14a). **Tuzatish:** 12 §2.5a/§2.6/§2.7; §14a. · kichik
- **C-177** · `27:62, 64` — "A-01" `/auth/signup` uchun (A-01 — 1C agent `hello`); "E-32" 07 da yo'q. **Tuzatish:** olib tashlash / BO-21 havolasi. · kichik
- **C-178** · `27:37` — signup aksepti B0 da, signup B1 da. **Tuzatish:** 27:62 ga ko'chirish. · kichik
- **C-179** · `27:76`; `03` US-M17-01 — "10 daqiqada ro'yxat + 500 tovar" uchun QT yo'q, 03 "2 daqiqa". **Tuzatish:** QT-NFR + raqamlar tenglashtirilsin. · kichik
- **C-180** · `27:127, 182` — B5 DoD US-M01-06, US-M11-02, `ledger_adjustments`, e-ishonchnoma, US-M10-03 ni qamramaydi; QT-M10-07 (`tax_settlements`, B4) B3 da. **Tuzatish:** havolalar qo'shilsin; QT-M10-07 → B4 DoD. · kichik
- **C-181** · `27:272, 273, 280, 287, 289` ↔ 26 Jadval B — bloklaydigan bosqich farqlari (#20 B6 vs MVP'dan keyin; #63 B5 BLOK vs MVP'dan keyin; #112 B5 vs B3; #137 B7 vs B5/B7; #167/#168 B0 vs B5/B6). **Tuzatish:** 26 ga moslash. · kichik
- **C-182** · `27:250–257`; `31:341` — US-M08-08, US-M03-02 ikki marta; QT-M09-09 US ustuni US-M03-02 (MVP'dan keyin). **Tuzatish:** bitta joy; US-M09-01. · kichik
- **C-183** · `21:772`; `31` QT-SUB — "FiscalPort+Fake — Bosqich 0 dan" (27 — B3); QT-SUB sarlavhasida US-M17-03 yo'q. **Tuzatish:** "Bosqich 3"; sarlavhaga US-M17-03. · kichik

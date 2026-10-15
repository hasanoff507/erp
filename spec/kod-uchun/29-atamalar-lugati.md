# Atamalar lug'ati

**Maqsad:** Mahsulot/biznes atamalari, ularning ruscha va inglizcha muqobillari va spec/koddagi aniq nom (jadval, ustun, enum qiymati, modul, ruxsat kodi) orasidagi bir xillikni ta'minlash — tarjimon, UX-yozuvchi va dasturchi bir xil so'zni ishlatishi uchun.
**Kim uchun:** hammasi (backend/frontend dasturchi, UX-yozuvchi/tarjimon, mahsulot egasi, qabul agenti).
**Bog'liq fayllar:** `11-malumotlar-modeli.md`, `12-db-sxema.md`, `13-provodka-qoidalari.md`, `14-autentifikatsiya-oauth2.md`, `15-xavfsizlik-va-audit.md`, `16-offline-sync.md`, `17-api-umumiy.md`, `18-api-kassa.md`, `19-api-ombor.md`, `20-api-moliya-admin.md`, `21-integratsiyalar.md`, `22-ai-qatlami.md`, `23-backend-arxitekturasi.md`, `24-frontend-arxitekturasi.md`, `33-1c-integratsiya.md` (§1.2), `34-1c-agent.md`.
**Holat:** joriy, 2026-10-16.

## Qoidalar

1. **"Koddagi nom" ustuni — faqat tasdiqlangan haqiqat.** Har bir qiymat `grep` bilan tegishli spec faylida tekshirilgan (jadval/ustun nomi `12-db-sxema.md`dan, ruxsat kodi `15-xavfsizlik-va-audit.md`dan, modul/klass nomi `23`/`24`dan). Agar aniq kod nomi spec'da hali yo'q bo'lsa — `—` qo'yiladi, o'ylab topilmaydi.
2. **Bir atama — bitta qator.** Sinonimlar (masalan "nasiya" va "qarz") bitta qatorda eslatma sifatida ko'rsatiladi, ikkinchi qator ochilmaydi.
3. **Ruscha/Inglizcha ustunlar — ishchi tarjima**, rasmiy atama lug'ati emas; UX-yozuvchi/tarjimon final matnni `08-dizayn-tizimi.md` va i18n fayllarida tasdiqlaydi (bu jadval — dasturchi uchun yo'naltiruvchi, UI matni manbai emas).
4. Jadval **domenlar bo'yicha guruhlangan**: Savdo/kassa, Ombor, Qarz, Pul/kassa puli, Buxgalteriya/soliq, Fiskal/markirovka/e-hujjat, Auth/obuna, Sync/offline, AI, Texnik, 1C integratsiyasi.
5. Yangi atama/jadval/ustun qo'shilganda — shu faylga ham qator qo'shiladi (`10-umumiy-arxitektura.md` §Qoidalar, 2-band mantiqiga mos).

---

## 1. Savdo/kassa

| O'zbekcha atama | Ruscha | Inglizcha | Koddagi nom | Ta'rif | Manba fayl |
|---|---|---|---|---|---|
| Kassa smenasi | Смена кассы | Cash shift | `shifts` | Kassaning ochilishi-yopilishi orasidagi davr, Z-hisobot bilan yakunlanadi | 11, 12 |
| Smena raqami | Номер смены | Shift number | `shifts.shift_no` | Qurilma beradigan, kassa ichida ketma-ket smena raqami | 11 |
| Smena farqi | Расхождение смены | Shift variance | `shifts.variance` | Sanalgan naqd va kutilgan naqd orasidagi farq | 11 |
| Chek | Чек | Sale (receipt) | `sales` | Mijozga sotilgan tovarlar hujjati | 11, 12 |
| Chek qatori | Строка чека | Sale line | `sale_lines` | Chekdagi har bir tovar qatori | 12 |
| Chek to'lovi | Оплата чека | Sale payment | `sale_payments` | Chek bo'yicha to'lov usuli va summasi | 12 |
| To'lov usuli | Способ оплаты | Payment method | `sale_payments.method` | `cash`/`card`/`uzqr`/`click`/`payme`/`uzum`/`debt` | 11 |
| Qaytarish | Возврат | Return | `returns` | Sotilgan tovarni qaytarish hujjati | 12 |
| Qaytarish qatori | Строка возврата | Return line | `return_lines` | Qaytarishdagi har bir tovar qatori | 12 |
| Kassa apparati | Кассовый аппарат | Cash register | `cash_registers` | Kassa/virtual kassa uskunasi yozuvi | 12 |
| Qurilma | Устройство | Device | `devices` | Veb-kassa/Android qurilma ro'yxati (litsenziya/sync uchun) | 11, 12 |
| Mijoz kredit limiti | Кредитный лимит клиента | Credit limit | `counterparties.credit_limit` | Nasiyaga sotish mumkin bo'lgan eng katta summa | 12 |
| Doimiy chegirma foizi | Постоянная скидка | Standing discount % | `counterparties.standing_discount_pct` | Mijozga har doim beriladigan % chegirma | 12 |
| Chegirma qoidasi | Правило скидки | Discount rule | `discount_rules` | Avtomatik chegirma/aksiya qoidasi (tovar/toifa/hammasi) | 12 |
| Chegirma manbai | Источник скидки | Discount source | `sale_lines.discount_source` | `manual`/`standing_customer`/`rule` | 11 |
| Terminal operatsiya raqami | Номер операции терминала | Terminal reference | `sale_payments.terminal_ref` | Mustaqil bank terminalining kvitansiya raqami (qo'lda) | 11 |
| Bank yagona QR | Единый QR банка | UzQR | `sale_payments.qr_type` | Bank generatsiya qilgan yagona to'lov QR kodi (PF-246) | 01, 11 |
| Statik / dinamik UzQR | Статический / динамический QR | Static / dynamic UzQR | `sale_payments.qr_type` (`static`/`dynamic`), `provider_tx_id` | Statik — kassir qo'lda tasdiqlaydi, tranzaksiya ID ixtiyoriy; dinamik — `UzqrPort` orqali, `provider_tx_id` majburiy (qaror #64, 26 #49) | 01, 12, 21 |
| Karta turi | Тип карты | Card type | `sale_payments.card_type`, `debt_payments.card_type` (`personal`/`corporate`/`social`/`unknown`) | Chekdagi majburiy rekvizit (2026-10-22 dan), `method='card'` bo'lsa majburiy (qaror #64) | 01, 12 |
| Karta niqobi | Маска карты | Card mask | `card_mask` (`^[0-9]{4}\*+[0-9]{4}$`) | Kartaning birinchi va oxirgi 4 raqami; ijtimoiy kartada majburiy | 12 |
| RRN | RRN (номер транзакции) | Retrieval reference number | `rrn` | Terminal tranzaksiyasining noyob raqami; `card_type='social'` bo'lsa majburiy | 12 |
| To'lov shakli | Форма оплаты | Payment form | `fiscal_receipts.payment_form` (`cash`/`card`/`qr`/`mixed`) | Chekdagi majburiy rekvizit (VMQ-943 1-ilova 7-band, 2026-10-22 dan) | 08, 12 |
| Offline sotuv bayrog'i | Признак офлайн-продажи | Offline sale flag | `sales.is_offline` | Chek offline rejimda yaratilganini bildiradi | 11 |
| Nasiya limiti oshgan bayrog'i | Признак превышения лимита | Debt limit exceeded flag | `sales.debt_limit_exceeded` | Offline nasiya kredit limitidan oshgan holat | 11 |
| Chekning vaqtinchalik raqami | Временный номер документа | Temp number | `temp_number` | Offline hujjatga qurilma bergan vaqtinchalik raqam (`{qurilma}-{lokal seq}`) | 11 |
| Lot allokatsiyasi | Распределение по партиям | Lot allocation | `sale_lines.lot_allocations` | FIFO bo'yicha chek qatori qaysi partiya(lar)dan yozilgani | 11 |

## 2. Ombor

| O'zbekcha atama | Ruscha | Inglizcha | Koddagi nom | Ta'rif | Manba fayl |
|---|---|---|---|---|---|
| Mahsulot (tovar) | Товар | Product | `products` | Katalogdagi sotiladigan birlik | 12 |
| Mahsulot toifasi | Категория товара | Product category | `product_categories` | Tovarlar guruhi (daraxt tuzilma) | 12 |
| Shtrix-kod | Штрихкод | Barcode | `product_barcodes` | Tovarga bog'langan EAN/ichki/og'irlik kodi | 12 |
| Ichki shtrix-kod ketma-ketligi | Внутренняя нумерация штрихкодов | Internal barcode sequence | `internal_barcode_seq` | Og'irlik tovar uchun tenant darajasidagi ichki kod generatori | 12 |
| O'lchov birligi | Единица измерения | Unit | `units` | `pcs`/`kg`/`l`/`m`/`box`, global ma'lumotnoma | 12 |
| Narx | Цена | Price | `product_prices` | Filial/vaqt bo'yicha narx tarixi qatori | 12 |
| Narx o'zgarishi | Изменение цены | Price change | `price_changes`, `price_change_lines` | Narxni ommaviy o'zgartirish hujjati | 12 |
| Yorliq shabloni | Шаблон этикетки | Label template | `label_templates` | Chop etiladigan narx/shtrix-kod yorlig'i shabloni | 12 |
| Yorliq chop etish navbati | Очередь печати этикеток | Label print queue | `label_print_queue` | Narx o'zgargan/yangi tovar uchun yorliq chop etish kutilmasi | 12 |
| Ombor | Склад | Warehouse | `warehouses` | Filialga bog'langan ombor | 12 |
| Qoldiq | Остаток | Stock balance | `stock_balances` | Ombor+tovar bo'yicha joriy hisoblangan qoldiq | 12 |
| Partiya | Партия | Stock lot | `stock_lots` | FIFO/AVECO uchun kirim partiyasi, o'z tannarxi bilan | 12 |
| Partiyada qolgan miqdor | Остаток в партии | Lot quantity left | `stock_lots.qty_left` | Partiyadan hali chiqarilmagan miqdor | 12 |
| O'rtacha tannarx | Средняя себестоимость | Average cost | `avg_costs` | AVECO usulida hisoblangan tovar bo'yicha o'rtacha tannarx | 12 |
| Tannarx | Себестоимость | Cost | `sale_lines.cost_amount`, `unit_cost` | Sotilgan/ko'chirilgan tovarning xarid qiymati | 11, 17 |
| Qoldiq harakati | Движение остатка | Stock move | `stock_moves` | Har hujjat bo'yicha ombordagi miqdor o'zgarishi (append-only) | 12 |
| Kirim (tovar qabuli) | Приход товара | Goods receipt | `goods_receipts` | Yetkazib beruvchidan tovar qabul qilish hujjati | 12 |
| Kirim qatori | Строка прихода | Receipt line | `receipt_lines` | Kirim hujjatidagi har bir tovar qatori | 12 |
| Xaridnoma | Заказ поставщику | Purchase order | `purchase_orders` | Yetkazib beruvchiga buyurtma hujjati | 12 |
| Xaridnoma qatori | Строка заказа поставщику | PO line | `po_lines` | Xaridnomadagi har bir tovar qatori | 12 |
| Yetkazib beruvchiga qaytarish | Возврат поставщику | Supplier return | `supplier_returns`, `supplier_return_lines` | Nosoz/ortiqcha tovarni yetkazib beruvchiga qaytarish | 12 |
| Ko'chirish | Перемещение | Transfer | `transfers`, `transfer_lines` | Tovarni filiallar/omborlar orasida ko'chirish hujjati | 12 |
| Inventarizatsiya | Инвентаризация | Stock count | `stock_counts`, `count_lines` | Jismoniy sanash va qoldiqni tekshirish hujjati | 12 |
| Hisobdan chiqarish | Списание | Write-off | `write_offs`, `write_off_lines` | Yaroqsiz/yo'qolgan tovarni qoldiqdan chiqarish hujjati | 12 |
| Boshlang'ich qoldiq | Начальный остаток | Stock opening | `stock_openings`, `opening_lines` | Tizimga o'tishda kiritiladigan boshlang'ich qoldiq | 12 |
| Qayta hisoblash ishi (recost) | Задача пересчёта себестоимости | Recost job | `recost_jobs` | Kech sinxron/kech kirim sabab tannarxni qayta hisoblash fon ishi | 11, 12, 23 |
| Import vazifasi | Задача импорта | Import job | `import_jobs` | Excel/CSV orqali katalog/qoldiq/qarz boshlang'ich importi | 12 |
| Baholash usuli tarixi | История метода оценки | Valuation method history | `valuation_method_history` | FIFO/AVECO tanlovi va o'zgarish tarixi (faqat yil boshidan) | 12 |
| MXIK kodi | Код ИКПУ | MXIK code | `products.mxik_code` | 17 xonali davlat tovar/xizmat klassifikatori kodi | 12 |
| Kam qoldiq chegarasi | Минимальный остаток | Minimum stock | `products.min_stock` | Shundan past tushsa ogohlantirish beriladigan chegara | 12 |
| Yaroqlilik muddati | Срок годности | Expiry date | `receipt_lines.expiry_date` | Partiyaning yaroqlilik sanasi | 12 |
| Og'irlik tovar | Весовой товар | Weighed product | `products.is_weighed` | Donada emas, og'irlikda sotiladigan tovar belgisi | 12 |
| Markirovkalangan tovar | Маркированный товар | Marked product | `products.is_marked` | Asl belgisi/CRPT markirovkasi talab qilinadigan tovar belgisi | 12 |

## 3. Qarz

| O'zbekcha atama | Ruscha | Inglizcha | Koddagi nom | Ta'rif | Manba fayl |
|---|---|---|---|---|---|
| Kontragent | Контрагент | Counterparty | `counterparties` | Mijoz yoki yetkazib beruvchi (`kind`: `person`/`company`) | 11, 12, 13 |
| Nasiya / qarz | Долг | Debt | `debt_moves` | Kontragentga yoki kontragentdan qarz harakati (sinonim: nasiya) | 11 |
| Qarz daftari | Книга долгов | Debt ledger | `debt_moves` + `debt_balances` | Nasiya/qarz harakatlari ro'yxati va joriy balanslari | 11 |
| Qarz yo'nalishi | Направление долга | Debt direction | `debt_moves.direction` | `receivable` (bizga qarz) / `payable` (bizning qarz) | 12 |
| Qarz balansi | Баланс долга | Debt balance | `debt_balances` | Kontragent+yo'nalish bo'yicha joriy qarz summasi | 12 |
| Qarz to'lovi | Оплата долга | Debt payment | `debt_payments` | Mijozdan qarz to'lovini qabul qilish hujjati | 12 |
| Qarz to'lovi allokatsiyasi | Распределение оплаты долга | Debt payment allocation | `debt_payment_allocations` | To'lov qaysi asl hujjat(lar)ga yopilganini bog'lash | 12 |
| Qarzni hisobdan chiqarish | Списание долга | Debt write-off | `debt_writeoffs` | Qarzni kechish/undirib bo'lmaydigan deb yopish hujjati | 12 |
| Shubhali qarz bayrog'i | Признак сомнительного долга | Doubtful debt flag | `debt_doubtful_flags` | Faqat Egasi belgilaydigan, sabab bilan risk bayrogi | 11, 12 |
| Boshlang'ich qarz | Начальный долг | Debt opening | `debt_openings` | Tizimga o'tishda kiritiladigan boshlang'ich qarz qoldig'i | 12 |
| Qarz hisob-varag'i havolasi | Ссылка на выписку долга | Counterparty statement link | `counterparty_statement_links` | Mijoz o'z qarzini ko'rishi uchun token bilan himoyalangan havola | 12 |
| Va'da sanasi | Дата обещания оплаты | Due date | `debt_moves.due_date`, `counterparties.debt_due_date` | Qarzni to'lash va'da qilingan sana | 11 |
| Yetkazib beruvchi to'lovi | Оплата поставщику | Supplier payment | `supplier_payments` | Yetkazib beruvchiga qarz to'lovi hujjati | 12 |
| Yetkazib beruvchi to'lovi allokatsiyasi | Распределение оплаты поставщику | Supplier payment allocation | `supplier_payment_allocations` | To'lov qaysi kirim(lar)ga yopilganini bog'lash | 12 |

## 4. Pul/kassa puli

| O'zbekcha atama | Ruscha | Inglizcha | Koddagi nom | Ta'rif | Manba fayl |
|---|---|---|---|---|---|
| Kassa puli harakati (hujjat) | Движение денег в кассе | Cash movement | `cash_movements` | Kassaga pul qo'yish/kassadan pul olish hujjati | 12 |
| Kassa puli registri | Регистр денежных средств | Cash move | `cash_moves` | Kassadagi naqd pul harakati append-only registri | 12 |
| Xarajat | Расход | Expense | `expenses` | Do'kon xarajati hujjati | 12 |
| Xarajat toifasi | Категория расхода | Expense category | `expense_categories` | Ijara/Kommunal/Ish haqi va h.k. ma'lumotnoma | 12 |
| Takrorlanuvchi xarajat | Повторяющийся расход | Recurring expense | `recurring_expenses` | Oylik/davriy avtomatik xarajat shabloni | 12 |
| Ilova (fayl) | Приложение (файл) | Attachment | `attachments` | Xarajat cheki fotosi, OCR manbai, eksport fayli va h.k. | 12 |
| To'lov checkout'i | Сессия оплаты | Payment checkout | `payment_checkouts` | Click/Payme to'lov sessiyasi (do'kon mijozi to'lovi) | 12 |
| To'lov provayderi tranzaksiya ID | ID транзакции провайдера | Provider transaction id | `provider_tx_id` | Click/Payme/Uzum tomonidan qaytarilgan tranzaksiya identifikatori | 12 |
| Yo'ldagi pul (5710) | Денежные средства в пути | Cash in transit | hisob `5710`, `ledger_entries.analytics.payment_method` | Karta/UzQR/Click/Payme/Uzum tushumlari va inkassa bankka tushguncha turadigan tranzit hisob (qaror #42) | 13, 33 |
| Bank tushumi tasdig'i | Подтверждение поступления в банк | Bank settlement | `bank_settlements` (`doc_sequences` kodi `BT`) | Bank ko'chirmasi bo'yicha 5710 → 5110 o'tkazmasi va komissiya hujjati; BO-24 | 11, 12, 13 |
| Bank tushumi usuli | Вид поступления | Settlement method | `bank_settlements.method` | `card`/`uzqr`/`click`/`payme`/`uzum`/`collection` | 12 |
| Tranzit qoldiq | Остаток в пути | Transit balance | `GET /bank-settlements/transit-balances` | 5710 da hali bank tasdig'ini olmagan tushum qoldig'i (BO-24, qaror #42) | 07, 20 |
| Bank ko'chirmasi importi | Импорт выписки | Statement import | `POST /bank-settlements/imports`, `bank_settlements.source='statement_import'` | 1CClientBankExchange `.txt` faylidan `draft` qoralamalar yaratish (qaror #42) | 13, 20 |
| 1CClientBankExchange | 1CClientBankExchange | 1C bank exchange format | — | O'zbekiston bank-klientlarining de-fakto ko'chirma formati (`.txt`) | 20 |
| Ekvayring komissiyasi | Комиссия эквайринга | Acquiring commission | `bank_settlements.commission_amount`; `settings.payment_org_commission_account` (`'9430'` standart) | Bank/to'lov tashkiloti ushlagan summa — `Dt 9430 / Kt 5710` (NSBU №21 §410); inkassa xizmati komissiyasi — 9410 (qaror #42) | 12, 13 |
| Inkasso | Инкассация | Cash collection | `cash_movements.reason = 'collection'` | Kassadagi naqdni bankka topshirish — 5710 orqali | 11, 13 |

## 5. Buxgalteriya/soliq

| O'zbekcha atama | Ruscha | Inglizcha | Koddagi nom | Ta'rif | Manba fayl |
|---|---|---|---|---|---|
| Bank komissiyasi (9430) | Комиссия банка | Bank commission | hisob `9430` | Bank/ekvayring/to'lov tizimi komissiyasi — boshqa operatsion xarajat (qaror #42) | 13 |
| Ortiqcha daromadi (9390) | Прочие операционные доходы | Other operating income | hisob `9390` | Inventarizatsiya/smena ortiqchasi, hisobdan chiqarilgan qarz qaytishi | 13 |
| Texnik hisob 0000 | Вспомогательный счёт 000 | Opening balance offset | hisob `0000` | Boshlang'ich qoldiqlarni kiritishda qarshi hisob, kiritilgach qoldig'i nol (26 #36) | 13 |
| Soliq hisob-kitobi | Расчёт налога | Tax settlement | `tax_settlements` (kod `ST`, `tax_kind`: `vat_offset`/`turnover_tax`) | QQS hisobga olish `Dt 6410 / Kt 4410` (§2.26) va aylanma solig'i `Dt 9430 / Kt 6410` hujjati | 13, 20 |
| Ish kuni (5 ish kuni) | Рабочий день | Business day | `tenants.settings` eslatmalari | Davlat hisobotini tasdiqlash/tuzatish muddati — 5 ish kuni, eslatmalar 1/3/4-ish kuni (qaror #50) | 07, 13 |
| Provodka | Проводка | Ledger entry | `ledger_entries` | Hujjat bo'yicha yoziladigan Dt/Kt buxgalteriya yozuvi | 11, 13 |
| Debet hisobi | Дебет счёта | Debit account | `ledger_entries.account_dt` | NSBU 21 hisob raqami (debet tomoni) | 13 |
| Kredit hisobi | Кредит счёта | Credit account | `ledger_entries.account_kt` | NSBU 21 hisob raqami (kredit tomoni) | 13 |
| Storno (teskari yozuv) | Сторно | Reversal entry | `reversal_of_id` | Hujjat bekor qilinganda qo'shiladigan teskari belgili registr qatori | 11, 23 |
| Davr yopish | Закрытие периода | Period closing | `period_closings` | Oylik buxgalteriya davrini yopish, qayta ochilmaydi | 11, 23 |
| Tuzatish yozuvi | Корректировочная запись | Ledger adjustment | `ledger_adjustments` | Yopilgan davrdan keyingi tuzatish (asl yozuv o'zgarmaydi) | 12 |
| QQS | НДС | VAT | `vat_moves` | Qo'shilgan qiymat solig'i | 11, 13 |
| QQS harakati | Движение НДС | VAT move | `vat_moves` | `output`/`input` yo'nalishli QQS yozuvi | 12 |
| QQS stavkasi | Ставка НДС | VAT rate | `products.vat_rate`, `vat_rate` | Foizda QQS stavkasi (masalan 12.00) | 12 |
| QQS imtiyoz kodi | Код льготы по НДС | VAT exemption code | `vat_exemption_code` | QQS'dan ozod/imtiyozli tovar/xizmat kodi | 12 |
| Aylanma solig'i | Налог с оборота | Turnover tax | `tenant_tax_regimes.regime = 'turnover'` | QQS o'rniga qo'llaniladigan soliq rejimi (SK 467-modda) | 01, 12 |
| Soliq rejimi | Налоговый режим | Tax regime | `tenant_tax_regimes` | Tenant darajasidagi `vat`/`turnover` tarixi | 12 |
| Aholi punkti toifasi | Категория населённого пункта | Settlement category | `branches.settlement_category` | Aylanma solig'i stavkasini aniqlaydigan filial toifasi | 01 |
| Filial soliq sozlamalari | Налоговые настройки филиала | Branch tax settings | `branch_tax_settings` | Filial bo'yicha soliq sozlamalari tarixi | 12 |
| Davlat hisoboti | Отчёт государства | State (tax) report | `state_reports` | my.soliq.uz tomonidan avtomatik tuzilgan QQS/aylanma hisoboti | 12 |
| Davlat hisoboti farqi | Расхождение с отчётом государства | State report diff | `state_report_diffs` | Ichki hisob va davlat hisoboti orasidagi tafovut qatori | 12 |
| STIR | ИНН | Taxpayer ID | `tenants.stir`, `counterparties.stir` | Soliq to'lovchining identifikatsiya raqami | 12 |
| Bank hisobi/MFO | Банковский счёт/МФО | Bank account / MFO | `counterparties.bank_account`, `counterparties.bank_mfo` | Kontragentning bank rekvizitlari (e-faktura uchun) | 12 |

## 6. Fiskal/markirovka/e-hujjat

| O'zbekcha atama | Ruscha | Inglizcha | Koddagi nom | Ta'rif | Manba fayl |
|---|---|---|---|---|---|
| OFD / virtual kassa | ОФД / виртуальная касса | Fiscal data operator | `fiscal_receipts` | Davlat fiskal operatori — har bir chek shu orqali fiskallashadi | 10, 21 |
| Fiskal chek | Фискальный чек | Fiscal receipt | `fiscal_receipts` | OFD'ga yuboriladigan/yuborilgan chek yozuvi | 12 |
| Fiskal chek raqami (qurilma) | Номер фискального чека (устройство) | Receipt sequence | `fiscal_receipts.receipt_seq` | Qurilma beradigan, smena ichida ketma-ket ichki idempotentlik raqami (qaror #12); FM raqami — `fm_receipt_seq` | 11 |
| Fiskal belgi | Фискальный признак | Fiscal sign | `fiscal_receipts.fiscal_sign` | OFD qaytargan fiskal tasdiq belgisi | 12 |
| Z-hisobot | Z-отчёт | Z-report | `fiscal_receipts.kind = 'z_report'` | Smena yopilganda chiqariladigan kunlik fiskal hisobot | 11 |
| Qarz to'lovi cheki | Чек по оплате долга | Debt settlement receipt | `fiscal_receipts.kind = 'debt_settlement'` | Nasiya to'lovi uchun chiqariladigan alohida fiskal chek | 11 |
| Fiskal modul (FM) | Фискальный модуль | Fiscal module | `FiscalPort`, `cash_registers.fm_state` | Chekni imzolovchi va OFD'ga yuboruvchi apparat/virtual modul (JavaCard applet, USB yoki SAM) | 21 |
| FM chek raqami | Номер чека ФМ | FM receipt sequence | `fiscal_receipts.fm_receipt_seq`, `fm_terminal_id` | Fiskal modul bergan raqam (`ReceiptSeq`), qurilmaning `receipt_seq`idan alohida (qaror #12) | 12, 21 |
| FM holati | Состояние ФМ | FM state | `cash_registers.fm_state` (`ok`/`locked`/`ack_overdue`/`memory_full`/`unknown`) | `locked` → sotuv `FISCAL_DEVICE_LOCKED` bilan to'xtaydi (26 #89) | 12, 17 |
| 48 soatlik blok | Блокировка через 48 часов | 48-hour offline lock | `FISCAL_OFFLINE_48H_BLOCKED`, `fiscal_receipts.ofd_acked_at` | `ofd_acked_at IS NULL` bo'lgan eng eski chekdan 48 soat o'tsa yangi fiskal chek chiqmaydi; 24/40/46 soat ogohlantirish (qaror #43) | 16, 17 |
| Do'kon ko'prigi (Local Bridge) | Локальный мост | Local fiscal bridge | `FISCAL_PROVIDER=multikassa_local`/`fiscaldrive_local` | POS → Do'kon agenti → FM/hamkor lokal xizmati → OFD yo'li (qaror #60) | 10, 21 |
| Sotuvdan oldingi markirovka tekshiruvi | Предпроверка кода | Marking precheck | `MARKING_PRECHECK` (`off`/`warn`/`block`, standart `warn`) | `warn` — ogohlantirish + audit, sotuv to'xtamaydi; `block` — qat'iy rad (qaror #62) | 18, 21 |
| Lokal takror-kod tekshiruvi | Локальная проверка дубля | Local duplicate check | `marking_codes` | Bir markirovka kodi ikki marta sotilmasligini qurilma/server tekshiradi — rejimdan qat'i nazar (qaror #62) | 16, 18 |
| Ombordan omborga (E-TTN) | Склад-склад | Warehouse transfer waybill | `transfers.ettn_ref`, `transfers.transport_mode` | O'z omborlari/filiallari orasidagi ko'chirish uchun majburiy E-TTN rejimi (qaror #63) | 03, 21 |
| E-ishonchnoma | Электронная доверенность | E-power of attorney | `goods_receipts.poa_number` | Do'kon xodimiga e-faktura operatori orqali beriladi; Vakolat.uz ishlatilmaydi (qaror #63) | 04, 21 |
| Markirovka | Маркировка | Marking | `marking_codes` | Asl belgisi/CRPT tizimi talab qilgan tovar kodi | 12, 16 |
| Asl belgisi | Asl belgisi (система маркировки) | National marking system | `marking_codes` | O'zbekistonning milliy tovar markirovkasi tizimi (CRPT Turon orqali) | 03, 21 |
| DataMatrix kod | Код DataMatrix | DataMatrix code | `marking_codes.code` | Markirovka shtrix-kodining fizik formati | 03, 12 |
| CRPT Turon | ЦРПТ Turon | CRPT Turon | — | Markirovka kodlarini tasdiqlaydigan markaziy davlat tizimi | 03, 21 |
| Markirovka holati | Статус кода маркировки | Marking status | `marking_codes.status` | `in_stock`/`sold`/`returned`/`written_off`/`returned_to_supplier`/`pending_verification` | 12 |
| Markirovka fon ishi | Фоновое задание маркировки | Marking job | `outbox_jobs.kind = 'marking_sell'` | Chakana sotuv kodi CRPT'ga alohida yuborilmaydi — fiskal chek ichida OFD orqali boradi (qaror #62); enum qiymati `12` CHECK ro'yxatida saqlanadi, CRPT API faqat `verify`/`writeoff`/qabul uchun | 12, 21 |
| E-faktura | Электронный счёт-фактура | E-invoice | `einvoices` | Elektron soliq hisob-faktura hujjati | 12 |
| E-faktura operatori | Оператор ЭСФ | E-invoice provider | `einvoices.operator` | `didox`/`faktura` (Faktura.uz — MVP'da yagona) | 12, 21 |
| E-faktura xavf bayrogi | Флаг риска счёт-фактуры | E-invoice risk flag | `einvoices.risk_flag` | Davlat xavf-baholash (VM 830) natijasi: `unknown` (standart — QQS krediti to'lovgacha kechiktiriladi) / `green` / `red` (26 #47) | 12 |
| E-TTN | Электронная товарно-транспортная накладная | E-waybill | `ettn_documents` (`transfer_id`, `transport_type`, `direction`) | Elektron yuk xati — EDO operatori orqali; sotuvda va o'z omborlari orasida ham majburiy (qaror #63) | 12, 21 |
| Ishonchnoma raqami | Номер доверенности | Power of attorney number | `goods_receipts.poa_number` | Do'kon o'z xodimiga e-faktura operatori orqali bergan e-ishonchnoma raqami (qaror #63) | 12 |
| E-IMZO | Э-ИМЗО | E-IMZO (digital signature) | — | Brauzerda ishlaydigan elektron raqamli imzo tizimi | 10, 14, 23 |
| UzQR | Единый QR | UzQR | `sale_payments.qr_type` | Bank yagona QR to'lov standarti (PF-246) | 01, 11 |

## 7. Auth/obuna

| O'zbekcha atama | Ruscha | Inglizcha | Koddagi nom | Ta'rif | Manba fayl |
|---|---|---|---|---|---|
| Foydalanish shartlariga rozilik | Согласие с условиями | Terms acceptance / consent | `tenants.accepted_terms_version`, `accepted_terms_at`, `accepted_terms_ip` | Ro'yxatdan o'tishda qabul qilingan oferta versiyasi va chegaradan tashqari uzatishga rozilik (qaror #61, 26 #127) | 11, 14 |
| Chegaradan tashqari AI | Трансграничная передача | Cross-border AI | `tenants.settings.ai_cross_border_enabled` (standart `false`) | Tenant rozilik bermaguncha AI-03 rasmlari Claude'ga yuborilmaydi (qaror #61) | 15, 22 |
| Avtorizatsiya serveri | Сервер авторизации | Authorization Server (AS) | `app/modules/auth` | O'z OAuth 2.0 AS+RS implementatsiyasi (uchinchi tomon auth xizmati yo'q) | 10, 14, 23 |
| BFF | BFF | Backend-for-Frontend | `/auth/*` | Veb SPA uchun cookie-based login vositachi qatlami, token brauzerga chiqmaydi | 14, 23, 24 |
| PKCE | PKCE | Proof Key for Code Exchange | — | Authorization Code grant kodini himoyalash mexanizmi (RFC 7636, S256) | 14, 23 |
| Sessiya | Сессия | Session | `sessions` | BFF cookie'ga bog'langan foydalanuvchi sessiyasi | 12 |
| Yangilash tokeni | Токен обновления | Refresh token | `refresh_tokens` | Rotatsiya + reuse detection bilan ishlaydigan token | 12 |
| Avtorizatsiya kodi | Код авторизации | Authorization code | `authorization_codes` | Authorization Code + PKCE oqimidagi vaqtinchalik kod | 12 |
| OAuth mijozi | OAuth-клиент | OAuth client | `oauth_clients` | Veb SPA/Android/bot/admin uchun ro'yxatdan o'tgan mijoz | 12 |
| Imzolash kaliti | Ключ подписи | Signing key | `signing_keys` | JWT/JWKS uchun imzolash kaliti (joserfc) | 12 |
| Litsenziya tokeni | Токен лицензии | License token | `license_tokens` | Offline qurilmani serversiz mahalliy bloklash uchun imzolangan token | 10, 11, 12, 14 |
| Login urinishi | Попытка входа | Login attempt | `login_attempts` | Har kirish urinishi yozuvi (bloklash/audit uchun) | 12 |
| OTP so'rovi | Запрос OTP | OTP challenge | `otp_challenges` | Telegram/SMS orqali yuborilgan tasdiqlash kodi so'rovi | 12 |
| OTP kanali | Канал OTP | OTP channel | `otp_challenges.channel` | `telegram`/`sms` (Telegram birinchi, SMS zaxira) | 12 |
| Foydalanuvchi ma'lumotnomasi | Учётные данные пользователя | User credentials | `user_credentials` | Parol/PIN heshi, bloklash holati | 12 |
| Tashqi identifikatsiya | Внешняя идентификация | User identity | `user_identities` | Google OIDC orqali bog'langan tashqi hisob | 12 |
| Rol | Роль | Role | `roles` | Standart 5 tizim roli + tenant o'z rollari | 12 |
| Ruxsat kodi | Код разрешения | Permission code | `role_permissions.permission_code` | Masalan `sales.void`, `debts.forgive` | 15, 17 |
| A'zolik | Членство | Membership | `memberships` | Foydalanuvchining tenant/filialga biriktirilishi | 12 |
| Tarif | Тариф | Plan | `plans` | Yagona `standard` tarif (99 000 so'm/oy, qaror #22), `limits` JSONB bilan | 12 |
| Qo'shimcha xizmat | Дополнительная услуга | Addon | `addons` | Masalan qo'shimcha kassa | 12 |
| Obuna | Подписка | Subscription | `subscriptions` | Tenant obuna holati va muddati | 12 |
| Billing to'lovi | Платёж биллинга | Billing payment | `billing_payments` | Platforma obunasiga Click/Payme orqali to'lov | 12 |
| Imtiyoz holati (grace) | Льготный период | Grace status | `subscriptions.status = 'grace'` | Muddat o'tgandan keyingi 24 soatlik imtiyoz, hammasi ishlaydi | 03, 07, 14 |
| Cheklangan holat | Ограниченный доступ | Restricted status | `subscriptions.status = 'restricted'` | Obuna to'xtaganda kassa/kirish to'liq yopiladi | 14, 17 |
| To'lov tokeni | Токен оплаты | Pay token | `pay_token` | `restricted` holatda faqat `POST /billing/checkout` uchun opaque token | 14 |
| Platforma admin | Администратор платформы | Platform admin | `platform_admins` | `/platform/*` ga kiradigan, tenant API'dan butunlay ajratilgan admin | 12 |

## 8. Sync/offline

| O'zbekcha atama | Ruscha | Inglizcha | Koddagi nom | Ta'rif | Manba fayl |
|---|---|---|---|---|---|
| Outbox (navbat) | Исходящая очередь | Outbox job | `outbox_jobs` | Tashqi tizimga yuborish/fon ishi uchun append-only navbat | 11, 12, 23 |
| Mijoz voqea ID'si | ID события клиента | Client event id | `client_event_id` | Qurilma generatsiya qilgan UUID — offline hujjatni dedupe qilish uchun | 10, 11, 16, 24 |
| Sinxronlash kvitansiyasi | Квитанция синхронизации | Sync receipt | `sync_receipts` | Qabul qilingan `client_event_id` natijasining serverdagi yozuvi | 12 |
| Idempotentlik kaliti | Ключ идемпотентности | Idempotency key | `idempotency_keys`, `Idempotency-Key` | Back-office yozuvchi so'rovlarini qayta yuborishdan himoya | 12, 17, 23 |
| Sync drain skopi | Скоуп слива синхронизации | Sync drain scope | `scope=sync.drain` | Lokautdan oldingi voqealarni yuborish uchun maxsus token skopi | 14, 17 |
| Offline rejim | Офлайн-режим | Offline mode | `is_offline`, `$isOnline` | Internet yo'qligida lokal yozuv + keyin sinxronlash rejimi | 10, 11, 24 |

## 9. AI

| O'zbekcha atama | Ruscha | Inglizcha | Koddagi nom | Ta'rif | Manba fayl |
|---|---|---|---|---|---|
| Maskalash | Маскирование | PII masking | `tenant_glossary`, AI so'rov quvuri | Claude'ga yuborishdan oldin shaxsiy maydonlarni almashtirish — majburiy, o'chirib bo'lmaydi (qaror #61) | 15, 22 |
| AI yordamchi chat | AI-чат-помощник | AI business chat | `AI-01` | Umumiy biznes savol-javob chati ("bugun qancha foyda?") | 09, 22 |
| OCR hujjat tanish | Распознавание документа (OCR) | Document OCR | `AI-03` | Faktura/yuk xati/chek fotosidan ma'lumot chiqarish | 09, 22 |
| Davlat hisoboti tushuntirishi | Объяснение расхождения отчёта | State report explanation | `AI-05` | Davlat hisoboti bilan ichki hisob farqini tushuntirish | 09, 22 |
| Qarz eslatma matni | Текст напоминания о долге | Debt reminder text | `AI-06` | Debitorlik/nasiya eslatma matnini generatsiya qilish | 09, 22 |
| AI so'rovi | Запрос к AI | AI request | `ai_requests` | Har bir LLM chaqiruvining log/xarajat yozuvi | 12 |
| AI OCR vazifasi | Задача AI OCR | AI OCR job | `ai_ocr_jobs` | AI-03 OCR fon ishi (fayl → maydonlar → tasdiqlash) | 12 |
| AI fikr-mulohazasi | Отзыв по AI | AI feedback | `ai_feedback` | Foydalanuvchining AI natijasiga baho/tuzatishi | 12 |
| AI o'qitish namunasi | Обучающий пример AI | AI training sample | `ai_training_samples` | Anonimlashtirilgan, rozilik bilan yig'ilgan o'qitish namunasi | 12 |
| Past ishonchli maydon | Поле с низкой уверенностью | Low confidence field | `ai_ocr_jobs.low_confidence_fields` | AI ishonch darajasi chegaradan past bo'lgan OCR maydoni | 12 |
| AiProvider porti | Порт AiProvider | AiProvider port | `AiProvider` | `fake`/`cli`/`api` rejimlari ortidagi yagona AI interfeysi | 10, 22, 23 |

## 10. Texnik

| O'zbekcha atama | Ruscha | Inglizcha | Koddagi nom | Ta'rif | Manba fayl |
|---|---|---|---|---|---|
| Do'kon agenti | Агент магазина | Store agent | repo `agent-1c/` (umumiy .NET 4.8 asos) | Do'kon Windows PK'sidagi bitta lokal dastur: fiskal ko'prik, xom TCP 9100 printer, tarozi, 1C (qaror #60) | 10, 34 |
| Posting xizmati | Сервис проводки | Posting service | `DocumentPostingService`, `*PostingService` | Hujjat holati va barcha registrlarni bitta tranzaksiyada yozuvchi xizmat | 23 |
| Tenant tranzaksiyasi | Транзакция тенанта | Tenant transaction | `tenant_transaction()` | `set_config('app.tenant_id', …, true)` bilan ochiladigan yagona tranzaksiya helper'i | 23 |
| Modulli monolit | Модульный монолит | Modular monolith | `app/modules/<modul>` | Bitta kod bazasida, lekin har modul o'z qatlami bilan ajratilgan arxitektura | 10, 23 |
| Posting natijasi | Результат проводки | Posting result | `PostingResult` | `post()`/`reverse()` qaytargan natija obyekti | 23 |
| Operatsiya ID | ID операции | Operation ID | `operation_id` | OpenAPI operatsiya nomi — orval frontend funksiya nomi manbai | 17, 24 |
| Kursor sahifalash | Курсорная пагинация | Cursor pagination | `CursorPage` | Hujjat/registr ro'yxatlari uchun `cursor`/`limit` asosidagi sahifalash | 17, 23 |
| Sahifa pagination | Страничная пагинация | Page pagination | `Page` | Ma'lumotnoma ro'yxatlari uchun `page`/`size` asosidagi sahifalash | 17, 23 |
| Xato konverti | Конверт ошибки | Error envelope | `{"error": {...}}` | Yagona xato javob shakli: `code`/`message_key`/`params`/`details`/`request_id` | 17, 23 |
| So'rov ID | ID запроса | Request ID | `request_id`, `X-Request-Id` | `structlog` orqali kuzatiladigan so'rov identifikatori | 17, 23 |
| Optimistik qulflash | Оптимистичная блокировка | Optimistic locking | `version` | Ma'lumotnomalarda `PATCH`da talab qilinadigan versiya raqami | 17, 23 |
| Filial konteksti | Контекст филиала | Branch scope | `X-Branch-Id` | Joriy so'rov bog'langan filial, `memberships`ga qarshi tekshiriladi | 17, 23 |
| Tasdiqlash so'rovi | Запрос на подтверждение | Approval request | `approval_requests` | Limitdan oshgan amal uchun masofaviy/PIN tasdiq navbati | 12, 17 |
| Hujjat tasdig'i | Подтверждение документа | Doc approval | `doc_approvals` | Bitta `approval_request` bo'yicha berilgan tasdiq yozuvi | 12 |

## 11. 1C integratsiyasi (Bosqich 7)

| O'zbekcha atama | Ruscha | Inglizcha | Koddagi nom | Ta'rif | Manba fayl |
|---|---|---|---|---|---|
| 1C integratsiya moduli | — | 1C integration module | `app/modules/onec_integration` | ERP → 1C kunlik eksportni boshqaradigan server moduli (M19, qaror #36) | 23, 33 |
| Agent (ERP 1C Agent) | — | 1C agent | `onec_agents`; repo `agent-1c/` | Do'kon agentining 1C imkoniyati: tray ilova (supervisor + COM worker'lar), vazifani pull qiladi (qaror #60) | 33, 34 |
| COM | COM-соединение (внешнее соединение) | COM connector | `V8x.COMConnector` | 1C'ga tashqi ulanish kanali — yagona kanal (qaror #36) | 33, 34 |
| COM worker | — | COM worker | `OneCWorker.x86.exe` / `OneCWorker.x64.exe` | Bitta bazaga bitta COM sessiya ochadigan bola jarayon | 33, 34 |
| Pull kanali (long-poll) | — | Pull channel | `POST /api/v1/onec-agent/poll` | Agent vazifani faqat chiquvchi HTTPS long-poll bilan tortadi, kiruvchi port yo'q | 33 |
| Agent tokeni | — | Agent token | OAuth mijozi `onec-agent`, `aud=urn:erp:onec-agent`, scope `onec.agent` | `client_credentials` + `private_key_jwt` bilan olinadigan token | 14, 33 |
| 1C bazasi | Информационная база | 1C infobase | `onec_bases` | Agent ulagan bitta 1C infobazasi (`File=` yoki `Srvr=;Ref=`) | 33 |
| Profil | Конфигурация | Profile | `onec_bases.profile_code` (`bp30_uz`) | 1C konfiguratsiyasi uchun server tomonidagi xarita to'plami | 33 |
| Filial bog'lanishi | — | Branch binding | `onec_branch_bindings` | Filial → bitta 1C bazasi, `bound_from` sanasidan | 33 |
| Eksport partiyasi (kun eksporti) | Пакет выгрузки | Export batch | `onec_export_batches` | Baza × hisob kuni × revision bo'yicha 1C'ga yoziladigan obyektlar to'plami | 33 |
| Eksport obyekti | Документ/элемент | Export item | `onec_export_items` | Partiyadagi bitta 1C obyekti (bitta GUID) | 33 |
| Obyekt daftari | — | Object ref ledger | `onec_object_refs` | ERP 1C'da yaratgan har obyektning doimiy yozuvi (GUID, raqam, versiya) | 33 |
| Agent vazifasi | — | Agent task | `onec_agent_tasks` | Agentga beriladigan Ed25519 imzoli ish (o'qish yoki yozish), lease bilan | 33 |
| Obyekt ko'rsatmasi | — | Object spec | `ObjectSpec` | Server quradigan deklarativ JSON: qaysi 1C obyektiga qaysi qiymat yoziladi | 33, 34 |
| Moslashtirish | Сопоставление | Mapping | `onec_mappings`, `onec_value_mappings` | ERP obyekti/qiymati ↔ 1C elementi GUID'i | 33 |
| Ma'lumotnoma yaratish so'rovi | — | Ref create request | `onec_ref_create_requests` | 1C'da yangi element yaratish taklifi, `onec.refs.create` tasdig'i bilan | 33 |
| Preview xeshi | — | Preview hash | `onec_export_batches.preview_hash` | Tasdiq shu xeshga bog'lanadi; ma'lumot o'zgarsa `ONEC_PREVIEW_CHANGED` | 33 |
| Tayyorlik | — | Readiness | `ReadinessService`, `blocking_issues[]`, `warnings[]` | Smenalar yopilgan, qurilmalar sinxronlangan, oldingi kunlar tugagan, moslashtirish to'liq | 33 |
| ОРП | Отчет о розничных продажах | Retail sales report | `retail_sales_report` | Kassa × kun chakana sotuv hisoboti — kunlik sotuvning 1C'dagi asosiy hujjati | 33 |
| Реализация | Реализация товаров и услуг | Credit/B2B sale | `credit_sale` | Qarzga yoki yuridik shaxsga sotuv — har chek alohida | 33 |
| Tuzatuvchi hujjat | Корректировка | Correction document | `retail_sales_correction` | Yopiq 1C davri uchun joriy sanadagi farq hujjati | 33 |
| Revision | — | Revision | `onec_export_batches.revision` | Kun partiyasining qayta qurilgan nusxasi (o'sha GUID'lar) | 33 |
| Marker | Комментарий | Marker | `marker` | `ERP #<guid8> h:<hash8> · …` — inson uchun iz va zaxira idempotentlik | 33 |
| Sana taqiqi | Дата запрета изменения | Date prohibition | `date_prohibition` | 1C'da shu sanagacha yozish taqiqlangan sana (`ONEC_DATE_PROHIBITED`) | 33 |
| Noma'lum natija | — | Unknown outcome | `ONEC_UNKNOWN_OUTCOME` | Yozildimi-yo'qmi noma'lum — keyingi urinish avval GUID bo'yicha tekshiradi | 33 |
| Drift | — | Drift | `onec_drift_check`, `ONEC_CHANGED_IN_1C` | ERP yozgan hujjat 1C'da qo'lda o'zgartirilgani/o'chirilgani | 33 |
| Kech ma'lumot belgisi | — | Change tracker | `OneCChangeTracker.touch()`, `needs_resync` | Yuborilgan kun uchun kech hujjat — yangi revision kerak | 23, 33 |
| PK qulfi | — | PC write lock | `pc_write_enabled` | Agent oynasidagi baza bo'yicha mahalliy «yozishga ruxsat» | 33, 34 |
| Server qulfi | — | Server write lock | `onec_bases.write_enabled` | BO-22 dagi «1C ga yozishga ruxsat» | 33 |
| Lease | — | Lease | `lease_id`, `lease_until` | Vazifani agentga vaqtinchalik biriktirish | 33 |

---

## Ochiq savollar

1. Hal qilingan: `message_key` uz/ru yakuniy matnini Claude tayyorlaydi, asoschi pilotdan oldin ko'zdan kechiradi (qaror #58, 26 #161).
2. Ba'zi texnik atamalar (masalan "posting service", "outbox") uchun o'zbekcha tarjima qasddan berilmagan — kod/spec'da ingliz nomi aynan ishlatiladi, bu jadvalda faqat tushuntirish uchun o'zbekcha izoh berildi.

## Manbalar

- `spec/kod-uchun/12-db-sxema.md` — barcha jadval/ustun/CHECK qiymat nomlari (asosiy manba).
- `spec/kod-uchun/15-xavfsizlik-va-audit.md` §2.1 — ruxsat kodlari katalogi.
- `spec/kod-uchun/17-api-umumiy.md` §15 — xato kodlari katalogi.
- `spec/kod-uchun/23-backend-arxitekturasi.md`, `24-frontend-arxitekturasi.md` — modul/klass/kutubxona nomlari.
- `spec/kod-uchun/09-ai-funksiyalar.md`, `22-ai-qatlami.md` — AI-01…AI-09 nomlari.
- `spec/kod-uchun/33-1c-integratsiya.md` §1.2, §5 — 1C integratsiyasi jadval/enum nomlari; `13-provodka-qoidalari.md` §2.18a — `bank_settlements`.
- `research_notes/ochiq-savollar/02-db-nomlar.md` — qarorlar #43–#65 dagi yangi ustun/enum nomlari.

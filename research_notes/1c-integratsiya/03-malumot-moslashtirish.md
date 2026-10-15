# 1C integratsiyasi — R3: ERP → 1C ma'lumot moslashtirish (mapping)

> **Yakuniy tavsiya ustun (accept gate, 2026-10-15):** shu papkadagi fayllar orasidagi ziddiyatlar `00-xulosa.md` da hal qilingan (§«Hal qilingan ziddiyatlar»). Bu fayl bilan `00-xulosa.md` farq qilsa — **00-xulosa'dagi yakuniy tavsiya ustun**. Kanonik nomlar: jadvallar — `04` §3.3; idempotentlik algoritmi — `04` §5.3; maydon xaritalari va ketma-ketlik — `03` §3, §5.1.

**Maqsad:** ERP bazasidagi har bir ma'lumot 1C bazasiga (asosiy nishon: «1С:Бухгалтерия для Узбекистана, ред. 3.0») qaysi obyekt sifatida, qaysi jamlash darajasida, qaysi maydon bilan, qaysi tartibda va qanday tuzatish qoidasi bilan yuborilishini belgilash.
**Kim uchun:** asoschi, 1C integratsiya moduli dasturchisi (Windows COM agenti va server tomoni), buxgalter (tasdiqlash uchun).
**Bog'liq fayllar:** `spec/kod-uchun/01-qarorlar.md` (#6, #12, #26, #30, #31, #36), `11-malumotlar-modeli.md`, `12-db-sxema.md`, `13-provodka-qoidalari.md`, `16-offline-sync.md`, `18-api-kassa.md`, `19-api-ombor.md`, `20-api-moliya-admin.md`, `04-biznes-jarayonlar.md`; raqobatchi tahlili — `research_notes/sonar-1c-integratsiya/04-1c-ga-yozish-va-tasdiqlash.md` (ObjectSpec, marker, `ВерсияДанных`).
**Holat:** tadqiqot/dizayn qoralamasi, 2026-10-15. Hech narsa publish qilinmagan.

> **Yozish kanali (asoschi qarori, 2026-10-15):** 1C ga yozish **faqat COM orqali**, do'kon kompyuteridagi **Windows agenti** (`V83.COMConnector`) bilan. OData, HTTP-servis, 1C'dan hech narsa publish qilinmaydi. Shuning uchun quyidagi barcha xaritalar **1C obyekt modeli** (`Документы.X.СоздатьДокумент()`, `Справочники.X.СоздатьЭлемент()`, `Объект.Записать(РежимЗаписиДокумента.Проведение)`) uchun yozilgan; OData nomlari (`Document_X`, `_Key`) ishlatilmaydi.

> **Manbalar haqida ogohlantirish.** Bu tadqiqot paytida sessiyaning veb-qidiruv limiti tugagan, its.1c.ru/infostart sahifalari 404/429 qaytargan. Tasdiqlangan (URL bilan) faktlar kam — ular **[tasdiqlangan]** deb belgilangan. 1C rekvizit nomlarining ko'pi rus «БП 3.0» standart metadatasi bo'yicha bilimdan olingan va **[taxmin]** deb belgilangan. O'zbek tahriri rus БП 3.0 asosida qurilgan (versiya raqamlari bir qatorda), lekin har bir nom **real bazada metadata o'qish bilan tekshirilishi shart** (§12, "Tekshirish rejasi"). Kod hech qachon nomlarni qattiq yozmaydi — agent ulanganda metadata'ni o'qiydi va xarita profilini tekshiradi.

---

## Asosiy xulosalar

1. **Haqiqat manbai — ERP.** Barcha sotuv, qoldiq, qarz va tannarx ERP'da yashaydi. 1C — buxgalter va egasi uchun **ko'zgu** (hisobot va soliq tomoni). 1C ga **bizning provodkalarimiz yuborilmaydi** (`ledger_entries`, `vat_moves`, `stock_lots`). Faqat **birlamchi hujjatlar** yuboriladi; 1C ularni o'z hisob siyosati bo'yicha o'tkazadi (o'z provodkasi, o'z tannarxi).
2. **Chakana sotuv kuniga bitta hujjat bo'ladi:** har (sana × kassa) uchun bitta «Отчет о розничных продажах» (ОРП), chek bo'yicha emas. Bu БП uchun standart amaliyot (БП'da «Чек ККМ» yo'q, u УТ/Розница hujjati) **[taxmin]**. Tovar qatorlari (mahsulot × QQS stavkasi) bo'yicha jamlanadi. To'lovlar «Оплата» jadvalida to'lov turi bo'yicha. Naqd qism = hujjat summasi − karta/QR summasi.
3. **Qarzga sotuv va B2B sotuv ОРП'ga kirmaydi.** Ular nomli kontragentga alohida «Реализация товаров и услуг» bo'lib, chek bo'yicha yuboriladi. Qarz to'lovi — pul hujjati (ПКО «Оплата от покупателя» yoki karta operatsiyasi). Qaror #30 dagi `debt_settlement` fiskal cheki 1C da **ikkinchi marta daromad yaratmasligi** shart.
4. **Ma'lumotnomalar avtomatik yaratilmaydi** (Sonar tamoyili). Avval moslashtirish ustasi ishlaydi: MXIK/shtrix-kod/STIR/nom bo'yicha topadi. Topilmasa — foydalanuvchiga «1C da yaratish» taklifi chiqadi, faqat tasdiq bilan. Bog'lanishlar `onec_ref_maps` jadvalida saqlanadi.
5. **Ketma-ketlik:** ma'lumotnomalar → kirimlar → ko'chirishlar → hisobdan chiqarish/inventarizatsiya → ОРП → Реализация → qaytarishlar → pul hujjatlari. Kun **D** faqat **D−1** muvaffaqiyatli yopilgandan keyin yuboriladi (filial bo'yicha). Hujjat vaqti 1C ichida tartibni ta'minlaydigan "vaqt slotlari" bilan beriladi.
6. **Asosiy xavf — 1C da manfiy qoldiq:** kirimlar 1C ga kiritilmagan bo'lsa, ОРП o'tkazilmaydi. Tavsiya — **«To'liq rejim»**: kirim, ko'chirish, hisobdan chiqarish ham ERP'dan yuboriladi. Birinchi ulanishda esa ERP qoldig'i bilan 1C qoldig'i solishtiriladi va farq «Оприходование/Списание» bilan tenglashtiriladi. Muqobillari §7 da.
7. **Idempotentlik — ikki qavat.** (a) 1C obyektining GUID'i deterministik: `УстановитьСсылкуНового(…ПолучитьСсылку(Новый УникальныйИдентификатор(uuid)))`. 1:1 hujjatda bizning `id`, jamlangan hujjatda UUIDv5(idem_key). Qayta urinishda agent avval shu GUID bo'yicha obyektni qidiradi. (b) `Комментарий` ga `ERP #<export_object_id>` markeri yoziladi. Bu metod platforma bilimi bo'yicha COM'da ishlaydi, lekin **[taxmin]** — §12 dagi T-1 sinovi bilan tasdiqlanadi.
8. **Tuzatish:** o'tkazilgan chek ERP'da bekor qilinmaydi (faqat qaytarish). Shuning uchun asosiy tuzatish holati — **kech sinxronlangan offline chek** (48 soat). Yechim: o'sha kunning ОРП'si **qayta yoziladi** (o'sha GUID, `ВерсияДанных` tekshiruvi bilan, qayta o'tkazish). 1C da shu sana **taqiqlangan** bo'lsa («Дата запрета изменения»), joriy ochiq sanada **tuzatuvchi ОРП** yaratiladi.

---

## 1. Nima yuboriladi, nima yuborilmaydi

### 1.1 Yuboriladigan ma'lumotlar

| # | ERP manbasi | 1C obyekti (БП UZ 3.0) **[taxmin nomlar]** | Jamlash | Standart | Izoh |
|---|---|---|---|---|---|
| E1 | `sales` (qarzsiz, B2B emas) + `sale_lines` + `sale_payments` | `Документ.ОтчетОРозничныхПродажах` | **kun × kassa** (sozlama: kun × filial) | yoqilgan | Chakana savdo |
| E2 | `returns` (asl chek bilan bir kunda) | o'sha E1 ОРП ichida **manfiy miqdorli qatorlar** | kun × kassa | yoqilgan | 1C amaliyoti: shu kungi qaytarish — ОРП ichida storno **[taxmin]** |
| E3 | `returns` (oldingi kun cheki / chek topilmagan) | `Документ.ВозвратТоваровОтПокупателя` (chakana, `Склад`=chakana ombor) + naqdda `Документ.РасходныйКассовыйОрдер` (`ВидОперации=ВозвратДенежныхСредствПокупателю`) | kun × kassa | yoqilgan | Kartaga qaytarish — §3.4 |
| E4 | `sales` qarzli (`sale_payments.method='debt'` bor) yoki `counterparty.kind='company'` + e-faktura | `Документ.РеализацияТоваровУслуг` (`ВидОперации=Товары`) | **har chek** | yoqilgan | Kontragent nomli, qarz 1C da ko'rinishi uchun |
| E5 | E4 chekining qarz bo'lmagan to'lovlari (aralash to'lov) | naqd: `ПриходныйКассовыйОрдер` (`ОплатаПокупателя`); karta/QR: `ОперацияПоПлатежнойКарте` **[taxmin]** | har to'lov | yoqilgan | |
| E6 | `debt_payments` | naqd: ПКО `ОплатаПокупателя`; karta/QR: `ОперацияПоПлатежнойКарте`; bank: `ПоступлениеНаРасчетныйСчет` (`ОплатаПокупателя`) | har to'lov | yoqilgan (bank — o'chiq) | Qaror #30: daromad yaratmaydi |
| E7 | `returns` `refund_method='debt_adjustment'` | `ВозвратТоваровОтПокупателя` (kontragent bilan) | har qaytarish | yoqilgan | Qarz kamayadi |
| E8 | `goods_receipts` + `receipt_lines` | `Документ.ПоступлениеТоваровУслуг` (`ВидОперации=Товары`) | har hujjat | **To'liq rejimda** yoqilgan | e-faktura 1C ga boshqa yo'l bilan kelsa — dublikat xavfi, §1.3 |
| E9 | `supplier_returns` | `Документ.ВозвратТоваровПоставщику` | har hujjat | To'liq rejim | |
| E10 | `supplier_payments` method=`cash` | РКО `ОплатаПоставщику` | har to'lov | yoqilgan | bank — o'chiq (bank ko'chirmasidan kiritiladi) |
| E11 | `transfers` (`received`/`discrepancy`) | `Документ.ПеремещениеТоваров` (`qty_received` bilan) + farq bo'lsa `СписаниеТоваров` | har hujjat | To'liq rejim | БП'da "yo'ldagi tovar" yo'q — §3.8 |
| E12 | `write_offs` | `Документ.СписаниеТоваров` | har hujjat | To'liq rejim | |
| E13 | `stock_counts` (`posted`) | `Документ.ИнвентаризацияТоваровНаСкладе` + `СписаниеТоваров` (kamomad) + `ОприходованиеТоваров` (ortiqcha) | har hujjat | To'liq rejim | Farq ERP'dan olinadi, 1C qayta hisoblamaydi |
| E14 | `expenses` source=`cash` | РКО `ПрочийРасход` (xarajat hisobi + `СтатьиЗатрат`) | har xarajat | yoqilgan | bank/karta — o'chiq |
| E15 | `cash_movements` | `collection` → РКО `ВзносНаличнымиВБанк`; `deposit` → ПКО `ПолучениеНаличныхВБанке`; `owner_withdrawal`/`other` → РКО/ПКО `ПрочийРасход`/`ПрочийПриход` | har harakat | yoqilgan | |
| E16 | `shifts.variance ≠ 0` | kamomad: РКО `ПрочийРасход` (5910/4730 **[taxmin]**); ortiqcha: ПКО `ПрочийПриход` | har smena | **o'chiq** (faqat hisobot) | Buxgalter qaror qiladi |
| E17 | `debt_writeoffs` | `Документ.КорректировкаДолга` (`СписаниеЗадолженности`) **[taxmin]** | har hujjat | o'chiq | Faqat Egasi tasdiqlagani |
| E18 | `price_changes` | `Документ.УстановкаЦенНоменклатуры` | har hujjat | **o'chiq** | Faqat 1C ombori НТТ bo'lsa yoki buxgalter so'rasa — §3.11 |
| E19 | `stock_openings` / `debt_openings` | `Документ.ВводНачальныхОстатков` | bir martalik | o'chiq | Faqat 1C bazasi yangi bo'lsa (§7.3) |
| R | `products`, `counterparties`, `warehouses`, `cash_registers`, `units`, `expense_categories`, to'lov usullari, QQS stavkalari | ma'lumotnomalar | — | moslashtirish ustasi | §4 |

### 1.2 Yuborilmaydigan ma'lumotlar (asos bilan)

| ERP ma'lumoti | Nima uchun yuborilmaydi |
|---|---|
| `ledger_entries`, `vat_moves`, `ledger_adjustments` | 1C hujjatlarni o'zi o'tkazadi va o'z provodkasini yozadi. Bizning provodkani «Операция» sifatida yuborish ikki marta hisoblashga olib keladi. Hisob rejasi kodlari (13-fayl) ham hali buxgalter tasdig'ida |
| `stock_lots`, `lot_allocations`, `cost_amount`, `avg_costs`, `recost_jobs` | 1C tannarxni o'zi hisoblaydi (ФИФО/o'rtacha — 1C hisob siyosati). Bizning tannarx boshqaruv hisobi uchun. Solishtirish faqat **miqdor** bo'yicha (§6) |
| `fiscal_receipts` (alohida), Z-hisobot | 1C БП'da Z-hisobot hujjati yo'q. Z-hisobot ОРП uchun **solishtirish nazorati**: ОРП naqd + karta jami = Z jami (`debt_settlement` hisobga olingan holda, §8) |
| `sales.status='draft'`, `sale.draft_voided` | Registrga ta'sir qilmaydi |
| `purchase_orders` | Rejalashtirish hujjati, registrga ta'sirsiz. БП'da buyurtma hujjati yo'q |
| `marking_codes`, `einvoices`, `ettn_documents` | 1C UZ'da e-faktura/markirovka o'z kanali bilan (Didox/Faktura integratsiyasi) bo'lishi mumkin. Dublikat va noto'g'ri imzo xavfi bor. E-faktura raqami faqat **rekvizit** sifatida (Комментарий/СчетФактура raqami) beriladi |
| `discount_rules`, `approval_requests`, `doc_approvals`, `payment_checkouts` | Ichki jarayon. Chegirma allaqachon qator summasida (§2.5) |
| `debt_doubtful_flags`, `counterparty_statement_links` | Faqat ko'rinish, buxgalteriyaga ta'sirsiz |
| `state_reports`, `ai_*`, `audit_log`, `notifications_log`, `subscriptions`, `billing_*`, `users`, `memberships`, `devices`, `sync_receipts` | 1C buxgalteriyasiga aloqasi yo'q yoki shaxsiy/maxfiy |
| `stock_openings`, `debt_openings` (standart holat) | Mavjud 1C bazasida boshlang'ich qoldiq allaqachon bor. Qayta yuborish ikki marta qoldiq beradi (§7.3 — faqat yangi baza uchun) |
| bank orqali `expenses`/`supplier_payments`/`debt_payments` (standart) | 1C UZ'da bank ko'chirmasi odatda bank-klient orqali import qilinadi. Bizdan yuborilsa dublikat bo'ladi. Sozlama bilan yoqiladi |

### 1.3 Rejimlar (tenant sozlamasi `onec_bases.mode`)

| Rejim | Nima yuboriladi | Kimga mos | Manfiy qoldiq xavfi |
|---|---|---|---|
| `full` (**tavsiya**) | E1–E16 hammasi | Kirimni ham ERP'da qiladigan do'kon (bizning asosiy ssenariy) | Past — tovar harakati to'liq |
| `sales_only` | E1–E7, E10, E14–E15 | Buxgalter kirimni 1C da o'zi kiritadi (e-faktura 1C ga tushadi) | **Yuqori** — §7 dagi oldindan tekshiruv majburiy |
| `money_only` | Faqat summalar: ОРП `Товары`siz (НТТ uslubi) yoki ПКО `РозничнаяВыручка` | 1C da tovar hisobi yuritilmaydigan yoki НТТ ombori | Yo'q (tovar yo'q) |

E8 (kirim) uchun dublikatga qarshi qoida: `goods_receipts.source='einvoice'` bo'lsa va 1C da shu e-faktura raqami bilan `ПоступлениеТоваровУслуг` topilsa (`НомерВходящегоДокумента` + kontragent + sana), yangisi yaratilmaydi. Mavjudi `onec_ref_maps` ga "topildi" deb bog'lanadi (§4.6).

---

## 2. Umumiy konvertatsiya qoidalari

### 2.1 Sana va vaqt

| Qoida | Tafsilot |
|---|---|
| Vaqt zonasi | 1C `Дата` vaqt zonasisiz, bazaning mahalliy vaqtida saqlanadi **[taxmin, platforma xulqi]**. ERP UTC (`TIMESTAMPTZ`) → **Asia/Tashkent (UTC+5)** ga o'tkaziladi. Hisob kuni = `doc_date` (allaqachon Toshkent kuni) |
| 1:1 hujjat vaqti | `doc_date` + `posted_at` ning Toshkent vaqti (soat:daqiqa:soniya). `posted_at` boshqa kunga tushsa (kech post) → `doc_date 23:00:00` |
| Jamlangan hujjat vaqti | Belgilangan **vaqt slotlari** (§5.2): ОРП `23:50:00`, kech qaytarishlar `23:55:00`, smena farqi `23:58:00` va h.k. Bitta sanada bir xil slotdagi hujjatlar 1C da `Номер` bo'yicha tartiblanadi |
| Bo'sh sana | 1C'da `'00010101'` — ERP'da `NULL` bo'lsa shu qiymat |
| O'tkazish rejimi | O'tgan sana uchun `РежимПроведенияДокумента.Неоперативный` |

### 2.2 Raqamlash

- 1C `Номер` **1C ning o'zi beradi** (avtoraqam, tashkilot prefiksi bilan). Bizning `K-01-2026-000154` (16 belgi) БП raqam uzunligidan (11 belgi **[taxmin]**) uzun. Shuning uchun majburlab qo'yilmaydi.
- Bizning raqam `Комментарий` da yoziladi: `ERP #<export_object_id> · K-01-2026-000154`. Kirim hujjatida yetkazib beruvchi raqami `НомерВходящегоДокумента`ga, sanasi `ДатаВходящегоДокумента`ga ketadi.
- Yaratilgandan keyin 1C qaytargan `Номер` va `Дата` `onec_export_objects.onec_number/onec_date` ga saqlanadi. Buxgalter shu raqam bilan qidiradi, BO ekranida "1C: 0000-000123" ko'rinadi.

### 2.3 Pul, miqdor, narx, yaxlitlash

| ERP | 1C **[taxmin aniqlik]** | Qoida |
|---|---|---|
| `NUMERIC(18,2)` summa | `Сумма` Число(15,2) | To'g'ridan-to'g'ri. 15 xona ≈ 10¹³ so'm yetarli |
| `NUMERIC(18,3)` miqdor | `Количество` Число(15,3) | To'g'ridan-to'g'ri, asosiy birlikda |
| `NUMERIC(18,4)` narx | `Цена` Число(15,2) | **Yaxlitlanadi**: `Цена = ROUND_HALF_UP(Сумма / Количество, 2)`. `Сумма` har doim ERP'dagi aniq yig'indi; 1C da `Цена×Количество ≠ Сумма` bo'lishi mumkin. Programmali yozuvda 1C forma hisoblagichlari ishlamaydi. Agent yozgandan keyin qayta o'qib solishtiradi (Sonar `Verify` naqshi) |
| QQS | `СуммаНДС` | **ERP'dagi qator QQS yig'indisi** yoziladi (qator bo'yicha yaxlitlangan, qaror #26). 1C qayta hisoblashi chaqirilmaydi — aks holda fiskal chek QQS'i bilan 0,01 farq paydo bo'ladi |
| `СуммаВключаетНДС` | Bul | Chakanada har doim `Истина`. Kirimda — yetkazib beruvchi narxi QQS bilan bo'lsa `Истина` (ERP `receipt_lines.cost` QQS bilan **[taxmin, 19-fayl bilan tekshirilsin]**) |

### 2.4 QQS stavkasi va soliq rejimi

| ERP | 1C `СтавкаНДС` **[taxmin qiymat nomlari]** |
|---|---|
| `vat_rate=12.00`, `vat_exemption_code IS NULL` | «12%» |
| `vat_rate=0.00`, `vat_exemption_code IS NULL` | «0%» |
| `vat_exemption_code IS NOT NULL` | «Без НДС» (imtiyoz kodi `Комментарий`/qo'shimcha rekvizitga, agar 1C UZ'da imtiyoz kodi rekviziti bo'lsa — metadata'dan aniqlanadi) |
| Tenant rejimi `turnover` (`tenant_tax_regimes`) | Barcha qatorlar «Без НДС», `СуммаНДС=0`. Aylanma solig'i 1C da buxgalter tomonidan hisoblanadi (bizdan yuborilmaydi) |

UZ tahririda `СтавкиНДС` — **sanoq (Перечисление)** yoki **ma'lumotnoma** ekani noma'lum. Shuning uchun stavkalar ham `onec_value_maps` orqali bog'lanadi (§4.2). Ustoz birinchi ulanishda 1C dagi qiymatlar ro'yxatini ko'rsatadi. 12% stavka 2023-01-01 dan amal qiladi (umumiy ma'lum fakt; havola olinmadi).

### 2.5 Chegirma

ERP `line_total` — chegirmadan **keyingi** summa. 1C ОРП/Реализация'ga **sof summa** yoziladi, chegirma alohida ko'rsatilmaydi. Natijada 1C da `9050 Xaridorlarga chegirmalar` aylanmasi bo'lmaydi; daromad sof holda 9020 ga tushadi. Bu soliq bazasiga ta'sir qilmaydi (QQS sof summadan). Buxgalter chegirmani alohida ko'rishni xohlasa — ochiq savol Q-6.

### 2.6 MXIK, qadoq kodi, markirovka

- `products.mxik_code` (17 raqam) va `package_code` → 1C `Номенклатура`ning ИКПУ rekviziti va qadoq kodi. **UZ БП'da bu rekvizitlarning nomi topilmadi** (ehtimoliy: `КодИКПУ`/`ИКПУ`, yoki alohida ma'lumotnoma/axborot registri) **[taxmin]**. Agent metadata'dan rekvizit nomini qidiradi (nomida «ИКПУ»/«МХИК»/«IKPU» bor satr maydon). Profilda bitta nom qotiriladi.
- MXIK hujjat qatorlarida takrorlanmaydi — `Номенклатура`dan olinadi.
- `marking_code` yuborilmaydi (§1.2).

### 2.7 O'lchov birliklari

| ERP `units.code` | 1C `КлассификаторЕдиницИзмерения` (kod — ОКЕИ) **[taxmin, UZ klassifikatori bilan tekshirilsin]** |
|---|---|
| `pcs` | 796 «шт» |
| `kg` | 166 «кг» |
| `l` | 112 «л» |
| `m` | 006 «м» |
| `box` | 778 «упак» |

Moslashtirish: avval kod bo'yicha (796…), keyin qisqa nom bo'yicha. 1C da topilmasa — klassifikator elementini yaratish taklifi (tasdiq bilan). Qadoq shtrix-kodi (`units_per_barcode`) 1C ga ketmaydi: ERP'da qoldiq allaqachon asosiy birlikda.

---

## 3. Hujjat bo'yicha maydon xaritalari

Belgilar: `→` — to'g'ridan-to'g'ri; `Σ` — jamlangan; `map(…)` — `onec_ref_maps`/`onec_value_maps` orqali; **[t]** — 1C rekvizit nomi taxmin.

### 3.1 E1 — «Отчет о розничных продажах» (kun × kassa)

**Tarkib (qaysi cheklar kiradi):**
`sales.status='posted' AND doc_date=D AND cash_register_id=K` va chekda `method='debt'` to'lovi **yo'q** va chek E4 shartiga (`counterparty.kind='company'` + chiquvchi e-faktura) tushmaydi.
`status='cancelled'` cheklar kirmaydi. ERP'da o'tkazilgan chek bekor qilinmaydi (`18-api-kassa.md` §4.8), lekin filtr himoya uchun qoldiriladi.

**Sarlavha:**

| 1C rekviziti [t] | Qiymat |
|---|---|
| `Ссылка` (GUID) | `UUIDv5(ns_tenant, "ORP|{base_id}|{cash_register_id}|{D}")` — `УстановитьСсылкуНового` |
| `Дата` | `D 23:50:00` |
| `Организация` | `map(tenant → Организации)` |
| `Склад` | `map(warehouses(branch, type='store') → Склады)`. 1C ombori `ТипСклада = РозничныйМагазин` (АТТ) bo'lishi kerak — ustoz tekshiradi |
| `ПодразделениеОрганизации` | `map(branches → ПодразделенияОрганизаций)` (ixtiyoriy) |
| `Касса` | `map(cash_registers → Кассы)` — naqd tushadigan operatsion kassa. БП 3.0'da `КассаККМ` maydoni yo'q **[taxmin]**; kassa farqi `Комментарий` va alohida `Кассы` elementi bilan |
| `СтатьяДвиженияДенежныхСредств` | `map(value: 'retail_revenue' → СтатьиДвиженияДенежныхСредств)` |
| `СуммаВключаетНДС` | `Истина` |
| `Комментарий` | `ERP #{export_object_id} · {kassa nomi} · smena {shift_no list} · cheklar {n}` |
| `Ответственный` | 1C ulanish foydalanuvchisi (agent COM login'i) |

**`Товары` jadvali** — jamlash kaliti `(product_id, vat_rate, vat_exemption_code, belgi)`. Belgi: `+` — sotuv, `−` — shu kungi qaytarish (E2):

| 1C ustuni [t] | Sotuv qatori (`+`) | Shu kungi qaytarish qatori (`−`, E2) |
|---|---|---|
| `Номенклатура` | `map(sale_lines.product_id)` | `map(return_lines.product_id)` |
| `Количество` | `Σ sale_lines.qty` | `−Σ return_lines.qty` |
| `Сумма` | `Σ sale_lines.line_total` | `−Σ return_lines.line_total` |
| `Цена` | `ROUND(Сумма/Количество, 2)` | shu formula |
| `СтавкаНДС` | `map(vat_rate, vat_exemption_code)` | shu |
| `СуммаНДС` | `Σ sale_lines.vat_amount` | `−Σ return_lines.vat_amount` |
| `СчетУчета`, `СчетДоходов`, `СчетРасходов`, `СчетУчетаНДСПоРеализации`, `Субконто` | **yozilmaydi** — 1C o'zi `СчетаУчетаНоменклатуры`/hisob siyosatidan to'ldiradi (agent `Заполнить`/`ЗаполнитьСчетаУчета…` ni chaqirmaydi; bo'sh qolsa 1C o'tkazishda xato beradi → `fill` profil sozlamasi, §12 T-4) | — |

Nima uchun sotuv va qaytarish qatorlari **netto qilinmaydi**: qaytarish narxi (chegirma, eski narx) sotuv narxidan farq qilishi mumkin. Netto qilinsa `Количество=0, Сумма≠0` holati paydo bo'ladi — 1C buni rad etadi.

**`Оплата` jadvali** — kalit `sale_payments.method ∈ {card, uzqr, click, payme, uzum}` (har biri alohida `ВидОплаты`):

| 1C ustuni [t] | Qiymat |
|---|---|
| `ВидОплаты` | `map(value: method → ВидыОплатОрганизаций)`. `card` — bitta (yoki terminal-bank bo'yicha bir nechta, Q-3) |
| `Сумма` | `Σ sale_payments.amount (method) − Σ shu kungi qaytarishlar (refund_method='card', asl chek to'lov usuli shu)` |

**Naqd qism** jadvalga yozilmaydi: 1C uni `СуммаДокумента − Σ Оплата` sifatida `Касса`ga (5010) o'tkazadi **[taxmin, БП ОРП xulqi]**. Nazorat (agent yozishdan oldin): `СуммаДокумента − ΣОплата = Σ sale_payments(cash) − Σ naqd qaytarish (shu kungi)`. Teng bo'lmasa — eksport to'xtaydi (`ORP_CASH_MISMATCH`).

**Nazorat — Z-hisobot bilan:** shu kassaning D kuni yopilgan smenalari `z_report.totals_by_method` (cash/card/uzqr/…) − debt-li cheklarning non-debt qismlari (E5) − `debt_settlement` cheklari (E6) = ОРП jamlari. Farq bo'lsa ogohlantirish beriladi, bloklanmaydi (yarim tunda ochiq smena bo'lishi mumkin).

### 3.2 E3 — Oldingi kun cheki bo'yicha qaytarish (kun × kassa)

Tarkib: `returns.status='posted' AND doc_date=D AND cash_register_id=K AND refund_method IN ('cash','card') AND (sale_id IS NULL OR sales.doc_date < D OR asl chek E4 (Реализация) bo'lsa)`.
Asl chek E4 bo'lsa → E7 ga o'xshash, lekin kontragent bilan (§3.5).

`ВозвратТоваровОтПокупателя` [t], GUID `UUIDv5("RET|{base}|{K}|{D}")`, `Дата = D 23:55:00`:

| 1C [t] | Qiymat |
|---|---|
| `ВидОперации` | chakana qaytarish varianti (`ПродажаКомиссия`/`Товары` — metadata'dan; `Склад` chakana bo'lsa 1C "розничный" varianti) **[taxmin]** |
| `Контрагент` | `map(value: 'retail_customer' → Контрагенты «Розничный покупатель»)` — 1C talab qilsa |
| `Склад`, `Организация` | E1 kabi |
| `Товары`: `Номенклатура`, `Количество`, `Цена`, `Сумма`, `СтавкаНДС`, `СуммаНДС` | `Σ return_lines` (product, vat) bo'yicha, musbat |
| `Комментарий` | `ERP #… · qaytarishlar {numbers} · asl cheklar {numbers}` |

Pul: naqd (`refund_method='cash'`) → `РасходныйКассовыйОрдер`, `ВидОперации=ВозвратДенежныхСредствПокупателю`, `Сумма=Σ`, `Касса=map(K)`, `Контрагент` = yuqoridagi. Karta (`'card'`) → `ОперацияПоПлатежнойКарте` (qaytarish varianti) **[taxmin]**. Agar 1C UZ'da bu hujjat bo'lmasa — keyingi kun ОРП'ida `Оплата` manfiy qatori (Q-4).

### 3.3 E4 — Qarzga / B2B sotuv: «Реализация товаров и услуг» (har chek)

| 1C [t] | Qiymat |
|---|---|
| `Ссылка` | `sales.id` (UUIDv7 = to'g'ri GUID) — `УстановитьСсылкуНового` |
| `Дата` | `doc_date` + `posted_at` vaqti |
| `ВидОперации` | `Товары` |
| `Организация`, `Склад`, `ПодразделениеОрганизации` | E1 kabi |
| `Контрагент` | `map(sales.counterparty_id → Контрагенты)` |
| `ДоговорКонтрагента` | `map(counterparty, 'customer' → ДоговорыКонтрагентов «Основной договор», ВидДоговора=СПокупателем)` |
| `СуммаВключаетНДС` | `Истина` |
| `Товары` | **qator bo'yicha** (jamlanmaydi): `Номенклатура=map(product)`, `Количество=qty`, `Сумма=line_total`, `Цена=ROUND(line_total/qty,2)`, `СтавкаНДС`, `СуммаНДС=vat_amount` |
| `Комментарий` | `ERP #… · {sales.number} · qarz muddati {due_date}` |
| `СчетФактура`/e-faktura raqami | Agar `einvoices(related_doc=sale, status=accepted)` bo'lsa — raqam/sana `Комментарий`ga. 1C da «Счет-фактура выданный» yaratilmaydi (e-faktura 1C ning o'z EDO kanali bilan) |

Qarz 1C da `4010` (kontragent analitikasi bilan) ko'rinadi — ERP `debt_moves` bilan solishtirish mumkin (§6.3).

### 3.4 E5/E6 — Kontragentdan to'lov

| ERP | 1C hujjati [t] | Asosiy maydonlar |
|---|---|---|
| E5: E4 chekining `sale_payments(method='cash')` | `ПриходныйКассовыйОрдер`, `ВидОперации=ОплатаПокупателя` | `Ссылка=sale_payments.id`, `Дата`=chek vaqti +1 s, `Касса=map(K)`, `Контрагент`, `ДоговорКонтрагента`, `Сумма`, `РасшифровкаПлатежа[1].ДокументРасчетов = E4 Реализация` (bog'lash), `СтатьяДДС` |
| E5: `card/uzqr/click/payme/uzum` | `ОперацияПоПлатежнойКарте` (`ОплатаОтПокупателя`) | `ВидОплаты=map(method)`, `Контрагент`, `Сумма`, `Комментарий` ichida `provider_tx_id`/`terminal_ref` |
| E6: `debt_payments(method='cash')` | ПКО `ОплатаПокупателя` | `Ссылка=debt_payments.id`, `Дата=doc_date+posted_at`, `Контрагент`, `Сумма=amount`. `РасшифровкаПлатежа` qatorlari = `debt_payment_allocations` (har allokatsiya → `ДокументРасчетов = map(target sale → E4 Реализация)`; `debt_openings` ga allokatsiya → `ДокументРасчетов` bo'sh, «по договору») |
| E6: `card/uzqr/click/payme/uzum` | `ОперацияПоПлатежнойКарте` | yuqoridagi kabi |
| E6: `bank` | `ПоступлениеНаРасчетныйСчет` `ОплатаПокупателя` | standart **o'chiq** (bank ko'chirmasidan dublikat) |

### 3.5 E7 — Qarzni kamaytiruvchi qaytarish

`returns.refund_method='debt_adjustment'` (yoki asl chek E4 bo'lsa istalgan usul) → `ВозвратТоваровОтПокупателя` [t], `Ссылка=returns.id`, `Контрагент=map(returns.counterparty_id)`, `ДоговорКонтрагента`, `ДокументРеализации = E4 Реализация` (asl chek bo'lsa), `Товары` — qator bo'yicha. `refund_method='cash'` bo'lsa → qo'shimcha РКО `ВозвратДенежныхСредствПокупателю` (`Ссылка=UUIDv5("RETCASH|returns.id")`).

### 3.6 E8 — «Поступление товаров и услуг» (har kirim)

| 1C [t] | ERP |
|---|---|
| `Ссылка` | `goods_receipts.id` |
| `Дата` | `doc_date` + `posted_at` vaqti |
| `ВидОперации` | `Товары` |
| `Организация`, `Склад` | `map(warehouse_id)` |
| `Контрагент`, `ДоговорКонтрагента` | `map(supplier_id)`, «Основной договор» `СПоставщиком` |
| `НомерВходящегоДокумента`, `ДатаВходящегоДокумента` | e-faktura bo'lsa `einvoices.number/doc_date`; aks holda `goods_receipts.number`/`doc_date` |
| `СуммаВключаетНДС` | `Истина` (taxmin, §2.3) |
| `Товары`: `Номенклатура`, `Количество`, `Цена`, `Сумма`, `СтавкаНДС`, `СуммаНДС` | `receipt_lines`: `qty`, `ROUND(cost,2)`, `Сумма = ROUND_HALF_UP(qty×cost, 2)` (ERP qator summasi bilan bir xil formula), `vat_rate`, `vat_amount` |
| Kiruvchi QQS «qizil» faktura (VM 830) | 1C hisob siyosatiga qoldiriladi; `Комментарий`ga `QQS: qizil faktura` belgisi. Bizning `vat_moves` yuborilmaydi |
| `paid_immediately=true` | Qo'shimcha РКО `ОплатаПоставщику` (naqd) — `UUIDv5("GRPAY|id")`. Bank bo'lsa yuborilmaydi |

E9 `ВозвратТоваровПоставщику`: `Ссылка=supplier_returns.id`, `Контрагент`, `ДокументПоступления = map(receipt_id → E8)`, `Товары` — `supplier_return_lines` (`qty`, `cost`, `vat_amount`).

### 3.7 E10, E14, E15 — Kassa hujjatlari

| ERP | 1C [t] | `ВидОперации` | Kontr-hisob/analitika |
|---|---|---|---|
| `supplier_payments(cash)` | РКО | `ОплатаПоставщику` | `Контрагент`, `Договор`, `РасшифровкаПлатежа` ← `supplier_payment_allocations` |
| `expenses(cash)` | РКО | `ПрочийРасход` | `СчетУчета` = 9410/9420 (`map(expense_category → (счет, СтатьиЗатрат))`), `Подразделение` |
| `cash_movements(collection)` | РКО | `ВзносНаличнымиВБанк` | 1C 5710 «pul o'tkazmalari yo'lda» yoki 5110 **[taxmin]** |
| `cash_movements(deposit)` | ПКО | `ПолучениеНаличныхВБанке` | `БанковскийСчет` = `map(value: 'main_bank')` |
| `cash_movements(owner_withdrawal)` | РКО | `ПрочийРасход` | hisob `map(value: 'owner_withdrawal_account')` (13-fayl: 8720 taxmin) — buxgalter tanlaydi |
| `cash_movements(other, in/out)` | ПКО/РКО | `ПрочийПриход`/`ПрочийРасход` | `map(value: 'cash_other_in/out_account')` |

Hammasida `Ссылка = <hujjat>.id`, `Касса = map(cash_register_id)`, `Дата = doc_date + posted_at`, `Комментарий = ERP #… · {number} · {comment}`.

### 3.8 E11 — Ko'chirish

БП'da filiallararo "yo'ldagi tovar" (2970) yo'q **[taxmin]**. Shuning uchun faqat `received`/`discrepancy` holatida `ПеремещениеТоваров` yuboriladi: `Ссылка=transfers.id`, `Дата` = `received_at` (Toshkent vaqti), `СкладОтправитель=map(from_warehouse)`, `СкладПолучатель=map(to_warehouse)`, `Товары` — `Количество = qty_received`.
`qty_sent − qty_received > 0` bo'lsa → `СписаниеТоваров` (`UUIDv5("TRLOSS|id")`) jo'natuvchi omborda, farq miqdori bilan, xarajat hisobi 5910 **[taxmin]**.
`sent` holatida (hali qabul qilinmagan) hech narsa yuborilmaydi. Natijada 1C da tovar jo'natuvchi omborda qolib turadi; kun yopish hisobotida bu "yo'lda" deb ko'rsatiladi.

### 3.9 E12, E13 — Hisobdan chiqarish va inventarizatsiya

- `write_offs` → `СписаниеТоваров` [t]: `Ссылка=id`, `Склад`, `Товары(Номенклатура, Количество)`, `Комментарий` = sabab (`expired`/`damaged`/`gift`/`other`). Xarajat hisobi: `responsible_user_id` bor → 4730, yo'q → 9430 (`map(value)`, buxgalter tasdiqlaydi). `gift` — QQS oqibati ochiq (13-fayl ogohlantirish 11).
- `stock_counts(posted)` → `ИнвентаризацияТоваровНаСкладе` [t] (`КоличествоУчет = expected`, `Количество = counted`). Uning asosida `diff<0` qatorlari → `СписаниеТоваров` (`UUIDv5("CNTLOSS|id")`), `diff>0` qatorlari → `ОприходованиеТоваров` (`UUIDv5("CNTGAIN|id")`, `Цена` = ERP `unit_cost`/avg). Muhim: 1C o'z `КоличествоУчет`ini hisoblashi chaqirilmaydi, farq **ERP'dan**. 1C qoldig'i ERP'dan farq qilsa, natija ERP'nikidan farq qiladi — §6 solishtirish hisoboti buni ko'rsatadi.

### 3.10 E16, E17 — Smena farqi va qarzni kechish

Standart o'chiq. Yoqilsa: smena kamomadi → РКО `ПрочийРасход` (hisob 5910/4730), ortiqcha → ПКО `ПрочийПриход` (9300-oilasi, taxmin). `debt_writeoffs` → `КорректировкаДолга` `СписаниеЗадолженности` (hisob `account_choice` 9430/4910).

### 3.11 E18 — Narx o'zgarishi

АТТ omborida (`РозничныйМагазин`) БП ОРП narxni hujjatdan oladi — `УстановкаЦенНоменклатуры` **shart emas** [taxmin]. НТТ omborida (summaviy hisob, 41.12/42.02 analogi) chakana narx majburiy. Bunday holda har `price_changes(posted)` → `УстановкаЦенНоменклатуры` (`ТипЦен = map(value: 'retail_price_type')`, `Товары(Номенклатура, Цена=new_price ROUND 2)`, `Дата = valid_from`). `branch_id`-li narx filial bo'yicha alohida `ТипЦен` talab qiladi → Q-7.

---

## 4. Ma'lumotnomalar: moslashtirish strategiyasi

### 4.1 Har bir ma'lumotnoma uchun qoida

| ERP | 1C ma'lumotnomasi [t] | Moslashtirish tartibi (birinchi topilgani; 2+ topilsa — noaniq, foydalanuvchi tanlaydi) | Topilmasa |
|---|---|---|---|
| `tenants` (STIR) | `Организации` | `ИНН = tenants.stir`. 1C da bitta tashkilot bo'lsa — taklif sifatida | **Blok** — tashkilotni ERP yaratmaydi (qaror #31: 1 tenant = 1 STIR) |
| `branches` | `ПодразделенияОрганизаций` | nom (normallashtirilgan) | Ixtiyoriy: bo'sh qoldirish yoki yaratish (tasdiq) |
| `warehouses` | `Склады` | nom; `ТипСклада` tekshiriladi (АТТ kerak) | Yaratish taklifi (`ТипСклада=РозничныйМагазин`) yoki mavjudini tanlash |
| `cash_registers` | `Кассы` (operatsion kassa) | nom | Yaratish taklifi yoki bitta umumiy «Asosiy kassa»ga bog'lash (ko'p ERP kassa → bitta 1C kassa ruxsat) |
| `products` | `Номенклатура` | 1) ИКПУ rekviziti = `mxik_code` **va** nom o'xshashligi ≥0,6; 2) shtrix-kod (1C da shtrix-kod registri bo'lsa — БП'da bo'lmasligi mumkin [t]); 3) `Артикул` = shtrix-kod; 4) aniq normallashtirilgan nom (`name` yoki `name_ru`); 5) trigram o'xshashlik — faqat **taklif** | **Yaratish taklifi** (tasdiq bilan) yoki mavjudini qo'lda tanlash. Sotuv eksportini bloklaydi (o'sha kun) |
| `counterparties` (`company`) | `Контрагенты` | `ИНН = stir` | Yaratish taklifi (`ИНН`, `Наименование`, `ЮридическоеФизическоеЛицо=ЮрЛицо`, manzil/bank — bor bo'lsa) |
| `counterparties` (`person`) | `Контрагенты` | ПИНФЛ (ERP'da yo'q) → `name`+`phone` aniq mos | Yaratish taklifi (`ФизЛицо`). Muqobil: barcha qarzdor jismoniy shaxslar bitta «Qarz daftari mijozlari» kontragentiga — **tavsiya etilmaydi** (1C da individual qarz ko'rinmaydi) |
| (kontragent shartnomasi) | `ДоговорыКонтрагентов` | `Владелец=kontragent`, `ВидДоговора` mos, nom «Основной договор» | Avtomatik yaratish — **faqat** kontragent yaratish tasdig'i ichida (bitta tasdiq) |
| `units` | `КлассификаторЕдиницИзмерения` | kod (ОКЕИ) → nom | Yaratish taklifi |
| QQS stavkalari | `СтавкиНДС` (sanoq/ma'lumotnoma) | nom/taqdimot «12%», «0%», «Без НДС» | **Blok** (stavka 1C konfiguratsiyasining qismi) |
| to'lov usullari (`card`, `uzqr`, `click`, `payme`, `uzum`) | `ВидыОплатОрганизаций` (`ТипОплаты=ПлатежнаяКарта`, `Контрагент`=ekvayer/agregator, `ДоговорКонтрагента`) | nom | Yaratish taklifi: foydalanuvchi ekvayer kontragentini (bank/Click/Payme MChJ — STIR bilan) tanlaydi |
| `expense_categories` | `СтатьиЗатрат` + hisob (9410/9420) | nom | Yaratish taklifi + hisobni buxgalter tanlaydi |
| (pul oqimi moddalari) | `СтатьиДвиженияДенежныхСредств` | nom | Yaratish taklifi |
| «Розничный покупатель» | `Контрагенты` | nom | Yaratish taklifi |

Normallashtirish: kichik harf, `ё→е`, lotin↔kirill transliteratsiya, `'`/`ʻ`/`’` birlashtirish, ko'p probel → bitta, qo'shtirnoq/«MChJ/ООО/XK» olib tashlanadi (faqat solishtirish uchun).

### 4.2 Birinchi ulanish ustasi (wizard)

1. **Ulanish va profil:** agent konfiguratsiya nomi/versiyasini o'qiydi (`Метаданные.Имя`, `Метаданные.Версия`). Profil tanlanadi: `bp_uz_3`, `ut_uz_11`, `roznica_uz`, `unf`. Kerakli metadata (hujjatlar, rekvizitlar, sanoqlar) mavjudligi tekshiriladi — yo'q nomlar ro'yxati ko'rsatiladi (§12).
2. **Tashkilot:** STIR bo'yicha → tasdiq.
3. **Rejim:** `full` / `sales_only` / `money_only` (§1.3) + "eksport boshlanish sanasi" (`start_date`). Shu sanagacha bo'lgan ERP hujjatlari hech qachon yuborilmaydi.
4. **Tuzilma:** filial → bo'linma, ombor → 1C ombor, kassa → 1C kassa (jadval, har qatorga taklif + tanlash).
5. **Qiymatlar:** QQS stavkalari, birliklar, to'lov usullari → `ВидыОплат`, xarajat toifalari → statya+hisob, maxsus hisoblar (`owner_withdrawal_account` va h.k.).
6. **Mahsulotlar** (eng katta qadam): avtomatik moslashtirish natijasi uch guruhda — "aniq mos" (avtomatik qabul, ko'rib chiqish mumkin), "taklif" (bitta bosish bilan tasdiq), "topilmadi" (yaratish / tanlash / keyinroq). Faqat `start_date`dan keyin sotilgan/kirim qilingan mahsulotlar majburiy — qolgani "kerak bo'lganda".
7. **Kontragentlar:** qarzdorlar va yetkazib beruvchilar — xuddi shunday.
8. **Qoldiq solishtirish** (`full` rejim, §7.3): `start_date` holatiga ERP qoldig'i vs 1C qoldig'i (agent o'qiydi) → farq hujjati taklifi.
9. **Yakun:** "1C da yaratiladigan elementlar" yagona ro'yxati (Sonar uslubida before/after karta) → Buxgalter/Egasi tasdig'i → agent yaratadi → `onec_ref_maps` to'ladi.

Keyin: yangi mahsulot/kontragent ERP'da paydo bo'lsa, u birinchi marta eksportga tushganda kun eksporti `needs_mapping` holatiga o'tadi. Telegram/BO bildirishnomasi: "1C ga yuborish uchun 3 ta yangi mahsulotni moslashtiring".

### 4.3 Topilmasa: yaratish yoki bloklash

| Holat | Siyosat |
|---|---|
| Tashkilot, QQS stavkasi topilmadi | **Blok** — konfiguratsiya/sozlash muammosi, avtomatik yechilmaydi |
| Mahsulot, kontragent, birlik, ombor, kassa, to'lov turi, statya topilmadi | **Taklif → inson tasdig'i → yaratish**. Tasdiqsiz hech qachon yaratilmaydi (Sonar `PickRef` tamoyili). Rol: `onec.mapping.approve` (Egasi, Buxgalter) |
| Mavjud 1C elementi `ПометкаУдаления=Истина` | Bog'lanmaydi; foydalanuvchi belgini olib tashlashni yoki boshqasini tanlashni hal qiladi |
| ERP'da ma'lumotnoma o'zgardi (nom, MXIK, STIR) | 1C elementi **avtomatik o'zgartirilmaydi**. `onec_ref_maps.erp_version` < `products.version` → "1C da yangilash taklifi" (tasdiq bilan, `update` + `ВерсияДанных` tekshiruvi) |

Yaratiladigan `Номенклатура` maydonlari [t]: `Наименование = name`, `НаименованиеПолное = name / name_ru`, `ЕдиницаИзмерения = map(unit_code)`, `ВидНоменклатуры = map(value: 'goods_kind' → «Товары»)`, `СтавкаНДС = map(vat)`, ИКПУ rekviziti = `mxik_code`, qadoq kodi = `package_code`, `Артикул` = birinchi EAN shtrix-kod (ixtiyoriy), `Родитель` = `map(product_categories)` yoki ustoz tanlagan papka. GUID = `products.id` (`УстановитьСсылкуНового`) — keyingi qayta moslashtirishda ham deterministik.

### 4.4 Saqlash — yangi jadvallar (12-db-sxema konvensiyalari)

> **Accept gate — kanonik jadval nomlari `04` §3.3 da.** Quyidagi DDL — mantiqiy qoralama; moslik: `onec_ref_maps` + `onec_value_maps` → **`onec_mappings`** (qiymat/sanoq uchun `onec_enum` ustuni bilan); `onec_export_days` → **`onec_export_batches`** (birlik — baza × sana, filiallar item'larda); `onec_export_objects` → **`onec_export_items`** (urinish/holat) + **`onec_object_refs`** (1C obyekt daftari); `onec_export_sources` → **`onec_export_item_sources`** (saqlanadi — kech chekda `stale` aniqlash uchun indeks). `mode`, `start_date` → `onec_settings`/`onec_bases`. Profil kodlari: `bp30_uz`, `ut11_uz`, `roznica30_uz`, `uk30_uz`, `unknown`. Xato kodlari `ONEC_*` prefiksi bilan (`ORP_CASH_MISMATCH` → `ONEC_ORP_CASH_MISMATCH` va h.k.).

Konvensiyalar: `app` sxemasi, `id UUID DEFAULT app.uuidv7()`, `tenant_id NOT NULL`, RLS `tenant_isolation` (yangi revizionda aniq `ENABLE/FORCE/CREATE POLICY` uchligi, CI tekshiradi), enum'lar `TEXT + CHECK`, pul `NUMERIC(18,2)`, vaqt `TIMESTAMPTZ`. Ulanish jadvali (`onec_bases` — agent, ulanish satri, parol) R1/R2 hujjatlari bilan kelishiladi. Bu yerda faqat mapping/eksport uchun kerakli minimal ustunlar ko'rsatilgan.

```sql
-- 1C bazasi (R1/R2 bilan birlashtiriladi; bu yerda faqat mapping uchun kerakli ustunlar)
CREATE TABLE app.onec_bases (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  name           TEXT NOT NULL,
  profile        TEXT NOT NULL CHECK (profile IN ('bp_uz_3','ut_uz_11','roznica_uz','unf')),
  config_name    TEXT NULL,   -- Метаданные.Имя (agent o'qiydi)
  config_version TEXT NULL,   -- Метаданные.Версия — o'zgarsa profil qayta tekshiriladi
  mode           TEXT NOT NULL DEFAULT 'full' CHECK (mode IN ('full','sales_only','money_only')),
  orp_grouping   TEXT NOT NULL DEFAULT 'register_day' CHECK (orp_grouping IN ('register_day','branch_day')),
  start_date     DATE NOT NULL, -- shu sanadan oldingi ERP hujjatlari hech qachon yuborilmaydi
  guid_namespace UUID NOT NULL DEFAULT app.uuidv7(), -- UUIDv5 nomlar fazosi (baza bo'yicha)
  settings       JSONB NOT NULL DEFAULT '{}', -- E-bandlar yoqilgan/o'chirilgan (send_bank_payments, send_shift_variance, ...)
  archived_at    TIMESTAMPTZ NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  version        INT NOT NULL DEFAULT 1
);

-- ERP obyekti ↔ 1C ma'lumotnoma elementi
CREATE TABLE app.onec_ref_maps (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  base_id          UUID NOT NULL REFERENCES app.onec_bases(id),
  erp_entity       TEXT NOT NULL CHECK (erp_entity IN ('tenant','branch','warehouse','cash_register','product',
                     'product_category','counterparty','counterparty_contract','unit','expense_category')),
  erp_id           TEXT NOT NULL,      -- UUID matni yoki units.code
  erp_role         TEXT NOT NULL DEFAULT '', -- shartnoma uchun 'customer'/'supplier', aks holda ''
  onec_type        TEXT NOT NULL,      -- 'Справочник.Номенклатура'
  onec_ref         UUID NOT NULL,      -- 1C Ссылка GUID
  onec_code        TEXT NULL,          -- Код (ko'rsatish uchun)
  onec_presentation TEXT NULL,
  match_method     TEXT NOT NULL CHECK (match_method IN ('mxik','barcode','inn','code','exact_name','fuzzy_confirmed',
                     'manual','created_by_erp')),
  erp_version      INT NULL,           -- bog'langan paytdagi products/counterparties.version
  confirmed_by     UUID NULL REFERENCES app.users(id),
  confirmed_at     TIMESTAMPTZ NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, base_id, erp_entity, erp_id, erp_role)
);
-- bitta 1C elementiga bir nechta ERP obyekti bog'lanishi mumkin (masalan 2 kassa → 1 kassa), shuning uchun onec_ref UNIQUE emas

-- Qiymat xaritalari: to'lov usuli → ВидОплаты, QQS → СтавкаНДС, maxsus hisoblar, statyalar
CREATE TABLE app.onec_value_maps (
  id          UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id   UUID NOT NULL REFERENCES app.tenants(id),
  base_id     UUID NOT NULL REFERENCES app.onec_bases(id),
  kind        TEXT NOT NULL CHECK (kind IN ('payment_method','vat_rate','account','cash_flow_item',
                'retail_customer','price_type','goods_kind','bank_account')),
  erp_value   TEXT NOT NULL,   -- 'card', '12.00', '0.00|EXEMPT', 'owner_withdrawal_account', 'retail_revenue'
  onec_type   TEXT NOT NULL,   -- 'Справочник.ВидыОплатОрганизаций' / 'Перечисление.СтавкиНДС' / 'ПланСчетов.Хозрасчетный'
  onec_ref    UUID NULL,       -- ma'lumotnoma/hisob uchun
  onec_enum   TEXT NULL,       -- sanoq qiymati nomi uchun
  confirmed_by UUID NULL REFERENCES app.users(id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, base_id, kind, erp_value),
  CHECK ((onec_ref IS NULL) <> (onec_enum IS NULL))
);

-- Kunlik paket (filial × sana) — ketma-ketlik birligi
CREATE TABLE app.onec_export_days (
  id           UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id    UUID NOT NULL REFERENCES app.tenants(id),
  base_id      UUID NOT NULL REFERENCES app.onec_bases(id),
  branch_id    UUID NOT NULL REFERENCES app.branches(id),
  export_date  DATE NOT NULL,
  status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','not_ready','needs_mapping','queued',
                 'running','done','stale','failed','blocked_period_closed')),
  ready_reason TEXT NULL,      -- 'open_shift', 'offline_devices', 'previous_day_failed'
  content_hash TEXT NULL,      -- kun tarkibining yig'ma xeshi (oxirgi muvaffaqiyatli eksport)
  last_run_at  TIMESTAMPTZ NULL,
  requested_by UUID NULL REFERENCES app.users(id),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, base_id, branch_id, export_date)
);

-- Har bir 1C obyekti (yaratilgan/yangilangan) — idempotentlik birligi
CREATE TABLE app.onec_export_objects (
  id             UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id      UUID NOT NULL REFERENCES app.tenants(id),
  base_id        UUID NOT NULL REFERENCES app.onec_bases(id),
  export_day_id  UUID NULL REFERENCES app.onec_export_days(id), -- ma'lumotnoma yaratishda NULL
  seq            INT NOT NULL,          -- kun ichidagi tartib (§5.1)
  idem_key       TEXT NOT NULL,         -- 'ORP|{register}|{date}', 'GR|{goods_receipt_id}', 'CNTLOSS|{id}' ...
  onec_type      TEXT NOT NULL,         -- 'Документ.ОтчетОРозничныхПродажах'
  onec_ref       UUID NOT NULL,         -- deterministik GUID (§9.1)
  onec_number    TEXT NULL,
  onec_date      TIMESTAMP NULL,        -- 1C mahalliy vaqti (zonasiz, ataylab)
  onec_data_version TEXT NULL,          -- ВерсияДанных oxirgi yozuvdan keyin
  content_hash   TEXT NOT NULL,         -- yuborilgan payload'ning SHA-256 (o'zgarishni aniqlash)
  revision       INT NOT NULL DEFAULT 1, -- har qayta yozishda +1
  action         TEXT NOT NULL CHECK (action IN ('create','update','unpost_mark_delete','correction')),
  corrects_id    UUID NULL REFERENCES app.onec_export_objects(id), -- tuzatuvchi hujjat qaysi asl hujjat uchun
  status         TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','awaiting_approval','sending',
                   'done','unknown','failed','conflict','superseded')),
  error_code     TEXT NULL,             -- 'ORP_CASH_MISMATCH','REF_NOT_MAPPED','POST_FAILED_NEGATIVE_STOCK','PERIOD_CLOSED','CHANGED_IN_1C'
  last_error     TEXT NULL,
  approved_by    UUID NULL REFERENCES app.users(id),
  sent_at        TIMESTAMPTZ NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, base_id, idem_key, revision),
  UNIQUE (tenant_id, base_id, onec_ref, revision)
);
CREATE INDEX idx_onec_exp_obj_day ON app.onec_export_objects (export_day_id, seq);

-- Qaysi ERP hujjatlari qaysi 1C obyektiga kirgan (kech o'zgarishni aniqlash, audit, "1C da ko'rish" havolasi)
CREATE TABLE app.onec_export_sources (
  id               UUID PRIMARY KEY DEFAULT app.uuidv7(),
  tenant_id        UUID NOT NULL REFERENCES app.tenants(id),
  export_object_id UUID NOT NULL REFERENCES app.onec_export_objects(id),
  doc_type         TEXT NOT NULL,  -- 'sales','returns','debt_payments',... (registrlardagi doc_type bilan bir xil)
  doc_id           UUID NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_onec_exp_src_doc ON app.onec_export_sources (tenant_id, doc_type, doc_id);
```

~~`outbox_jobs.kind` CHECK ro'yxatiga `onec_export_day`, `onec_create_refs` qo'shiladi.~~ *Accept gate:* `outbox_jobs` ishlatilmaydi — agent pull modelida alohida `onec_agent_tasks` jadvalidan oladi (`04` §3.1); server ichki ishlari — SAQ job'lari.

---

## 5. Ketma-ketlik («ketma-ketlik»)

### 5.1 Kun ichidagi bog'liqlik tartibi

| seq | Qadam | 1C vaqt sloti (D kuni) | Bog'liqlik |
|---|---|---|---|
| 0 | Yetishmayotgan ma'lumotnomalarni yaratish (tasdiqlanganlari) | — | hammasidan oldin |
| 10 | Kirimlar E8 (+ darhol to'lov РКО) | haqiqiy `posted_at` vaqti | tovar 1C ga kiradi |
| 20 | Yetkazib beruvchiga qaytarish E9 | haqiqiy vaqt | E8 |
| 30 | Ko'chirishlar E11 (qabul qilingan) + yo'qotish | `received_at` | E8 (jo'natuvchida qoldiq) |
| 40 | Hisobdan chiqarish E12 | haqiqiy vaqt | E8/E11 |
| 50 | Inventarizatsiya E13 (+ Списание/Оприходование) | haqiqiy vaqt | E8–E12 |
| 60 | ОРП E1(+E2) — har kassa | `23:50:00` | E8–E50 (qoldiq) |
| 70 | Реализация E4 (qarz/B2B) | chek vaqti | E8–E50 |
| 75 | E4 bilan bog'liq to'lovlar E5 | chek vaqti + 1 s | E4 |
| 80 | Kech qaytarishlar E3, E7 (+ pul) | `23:55:00` / haqiqiy vaqt | E4 (asl Реализация) |
| 90 | Qarz to'lovlari E6 | haqiqiy vaqt | E4 (oldingi kunlar) |
| 100 | Kassa: E10, E14, E15 | haqiqiy vaqt | — |
| 110 | Smena farqi E16, qarz kechish E17, narx E18 | `23:58:00` | — |

Nima uchun ОРП kun oxirida (`23:50`): kun davomidagi barcha kirim/ko'chirishdan keyin turadi. Shu sababli 1C qoldiq tekshiruvida (yoqilgan bo'lsa) tovar kun ichida keyinroq kelgan bo'lsa ham ОРП o'tadi. Pul hujjatlari tovarga bog'liq emas va istalgan tartibda bo'lishi mumkin, lekin kassa qoldig'i manfiy bo'lmasligi uchun (1C kassa qoldig'ini tekshirishi mumkin) chiqim РКО'lar ОРП'dan keyin turadi.

### 5.2 Kunlar ketma-ketligi va tayyorlik

- Birlik — `onec_export_days(base, branch, date)`. **D** kuni faqat **D−1** `done` (yoki `start_date`) bo'lsa `queued` ga o'tadi. Bu filial bo'yicha qo'llanadi: boshqa filiallar bir-birini kutmaydi, ko'chirish bundan mustasno — E11 qabul qiluvchi filial kunida yuboriladi va jo'natuvchi filialning shu sanagacha bo'lgan kunlari `done` bo'lishi talab qilinadi.
- **Tayyorlik** (`not_ready` sabablari): (a) shu filialda D sanali hujjati bor ochiq smena bor (`shifts.status IN ('open','closing')`); (b) filial qurilmalaridan biri D kun oxiridan beri sinxronlanmagan (`devices.last_sync_at < D+1 00:00`) va 48 soat o'tmagan — kech offline chek kelishi mumkin; (c) mapping yetishmaydi → `needs_mapping`.
- Foydalanuvchi "Baribir yuborish" tugmasini bosishi mumkin (b holatida, ogohlantirish bilan). Kech chek kelsa — §8 tuzatishi.
- **Ishga tushirish:** smena yopilganda (`shift.closed`) tegishli kun tayyorligi qayta hisoblanadi. Avtomatik rejimda tayyor kun navbatga qo'yiladi; qo'lda rejimda BO'da "1C ga yuborish" tugmasi chiqadi (asoschi talabi: "kun/smena oxirida foydalanuvchi yuboradi").

### 5.3 Oldingi kun xato bo'lsa

| Xato turi | Xulq |
|---|---|
| D−1 `failed` (bitta hujjat o'tmadi) | D va keyingi kunlar `not_ready: previous_day_failed`. BO'da xato hujjati, sabab va "Qayta urinish"/"Shu hujjatni o'tkazib yuborish (Egasi, sabab bilan)" tugmalari. O'tkazib yuborilgan obyekt `status='failed'` qoladi va kun `done` hisoblanadi (audit bilan) |
| Bitta kun ichida seq 10 xato | Shu kunning keyingi seq'lari to'xtaydi (ОРП qoldiqsiz o'tmaydi). Pul hujjatlari (seq ≥ 90) tovardan mustaqil — sozlama `continue_money_on_stock_error` (standart `true`) |
| `unknown` (COM timeout, yozildimi noma'lum) | Keyingi urinishda avval GUID bo'yicha qidiriladi (§9). Topilsa → `done`, topilmasa → qayta yaratish |
| `blocked_period_closed` | 1C da shu sana taqiqlangan → tuzatuvchi hujjat rejimi (§8.3), buxgalter tasdig'i bilan |

---

## 6. Tannarx (COGS) va qoldiq: haqiqat manbai

### 6.1 Kim nimaga mas'ul

| Ko'rsatkich | Haqiqat manbai | 1C da |
|---|---|---|
| Tovar miqdori (qoldiq) | **ERP** (`stock_balances`) | ERP hujjatlari bilan takrorlanadi (`full` rejim). Farq — signal |
| Sotuv summasi, QQS | **ERP** (fiskal chek bilan bir xil) | ОРП/Реализация orqali aynan ko'chadi (§2.3) |
| Tannarx (COGS) | ERP — boshqaruv hisobi; **1C — buxgalteriya/soliq hisobi** | 1C o'z usuli (ФИФО/o'rtacha) bilan. Bizning `cost_amount` yuborilmaydi |
| Debitorlik/kreditorlik | **ERP** (`debt_balances`) | E4–E7, E10 bilan takrorlanadi (bank to'lovlari 1C ga boshqa yo'ldan kelsa ham) |
| Kassa qoldig'i | **ERP** (`cash_moves`) | ОРП + ПКО/РКО bilan |

Tannarx farqi muqarrar: 1C ФИФО partiyasi kirim sanasi va vaqti bo'yicha, bizniki `stock_lots` bo'yicha; AVECO'da yaxlitlash farqi bor. Bu nuqson emas — buxgalter 1C tannarxi bilan hisobot topshiradi. ERP'dagi P&L "boshqaruv" deb belgilanadi. Hisob siyosatini moslash (bir xil usul) ustozda tavsiya qilinadi.

### 6.2 Kunlik solishtirish hisoboti

Eksportdan keyin agent shu ombor/sana uchun 1C qoldig'ini o'qiydi (o'qish yo'li — R1/R2) va ERP `stock_balances` (D oxiri holati) bilan solishtiradi: farqli mahsulotlar ro'yxati. Shuningdek kassa (5010) va kontragent qarzlari (4010/6010) solishtiriladi. Natija BO'da "1C bilan farqlar" kartasi. Avtomatik tuzatish yo'q.

---

## 7. 1C da manfiy qoldiq xavfi va yechimlari

**Muammo:** `sales_only` rejimda yoki kirimlar 1C ga kiritilmagan bo'lsa, ОРП yoki Реализация o'tkazilmaydi. Bu 1C da «Разрешить списание запасов при отсутствии остатков» sozlamasi **o'chiq** bo'lganda sodir bo'ladi [taxmin: БП 3.0 dagi sozlama nomi; joyi «Администрирование → Проведение документов» yoki «Параметры учета», tahrirga qarab]. Sozlama yoqilgan bo'lsa ham, manfiy qoldiq 1C tannarxini buzadi va oy yopishda xato beradi.

| Variant | Mohiyati | Afzallik | Kamchilik | Tavsiya |
|---|---|---|---|---|
| **A. Kirimlarni ham yuborish** (`full`) | E8–E13 ERP'dan | 1C tovar harakati ERP bilan bir xil, ОРП doim o'tadi | Buxgalter 1C da kirimni qo'lda kiritmasligi kerak. 1C ga e-faktura orqali kirim tushsa — dublikat (§1.3 qoidasi) | **Asosiy** |
| B. 1C da manfiy qoldiqqa ruxsat | Sozlamani yoqish | Oson | 1C tannarxi noto'g'ri, buxgalter qarshi bo'ladi, oy yopishda tuzatish | Faqat vaqtinchalik, buxgalter roziligi bilan |
| C. Boshlang'ich qoldiqni yuborish | Ulanishda `ВводНачальныхОстатков` yoki `ОприходованиеТоваров` (ERP qoldig'i, `unit_cost`) | Bir martalik tenglashtirish | Keyingi kirimlar 1C ga kelmasa, muammo qaytadi | A bilan birga (birinchi kun) |
| D. Oldindan tekshirish (pre-flight) | ОРП yuborishdan oldin agent 1C qoldig'ini o'qiydi (`РегистрБухгалтерии.Хозрасчетный.Остатки` yoki `ОстаткиТоваров` [t]) va yetishmovchilik ro'yxatini chiqaradi | Xato oldindan ko'rinadi, foydalanuvchi qaror qiladi | Qo'shimcha COM so'rovi (sekin) | `sales_only` rejimda **majburiy**, `full`da faqat xato bo'lganda |
| E. `money_only` | Tovarsiz ОРП (НТТ) yoki ПКО «Розничная выручка» | Qoldiq muammosi yo'q | 1C da tovar hisobi yo'q | 1C ni faqat kassa/daromad uchun ishlatadigan do'kon |

D natijasida yetishmovchilik topilsa, foydalanuvchiga uch tanlov beriladi: (1) "1C da kirimni kiritaman, keyin qayta urinish"; (2) "ERP qoldig'i bo'yicha tuzatuvchi `ОприходованиеТоваров` yaratish" (Egasi+Buxgalter tasdig'i, `idem_key='ADJIN|{date}|{product}'`); (3) "Shu kunni o'tkazib yuborish".

### 7.3 Birinchi ulanish (mavjud 1C bazasi)

1. `start_date` tanlanadi (odatda joriy oyning 1-sanasi yoki ertangi kun).
2. Agent `start_date 00:00` holatidagi 1C qoldig'ini (ombor × nomenklatura) o'qiydi, ERP `stock_balances` shu holatda qayta tiklanadi (`stock_moves` yig'indisi).
3. Farq jadvali: ERP > 1C → `ОприходованиеТоваров` taklifi (narx = ERP `unit_cost`), ERP < 1C → `СписаниеТоваров` taklifi. Yoki "1C haq — ERP'da inventarizatsiya qilaman" tanlovi.
4. Qarzlar (`debt_balances`) vs 1C 4010/6010 — farq faqat ko'rsatiladi. 1C ga avtomatik yuborilmaydi; buxgalter `КорректировкаДолга` yoki `ВводНачальныхОстатков` bilan hal qiladi.
5. **Yangi (bo'sh) 1C baza:** E19 — `ВводНачальныхОстатков` (`РазделУчета=Товары`, `Расчеты с покупателями/поставщиками`) ERP `stock_openings`/`debt_openings` yoki joriy balansdan.

---

## 8. Tuzatishlar

### 8.1 Holatlar matritsasi

| ERP hodisasi (eksportdan keyin) | 1C dagi aks ettirish |
|---|---|
| **Kech sinxronlangan offline chek** (D kuni, kun allaqachon `done`) | Kun → `stale`. Shu kassaning D ОРП'si **qayta yoziladi**: `onec_export_objects` yangi `revision`, o'sha `onec_ref`. Agent: obyektni ochish → `ВерсияДанных` = saqlangan `onec_data_version` (aks holda `CHANGED_IN_1C` → buxgalterga ko'rsatish) → jadvallarni to'liq almashtirish → `Записать(Проведение)`. 1C ichida sana va GUID o'zgarmaydi |
| Kech chek — qarzli (E4) | Yangi Реализация yaratiladi (1:1, boshqa hech narsaga tegmaydi) |
| Qaytarish (oldingi kun cheki) | Bu tuzatish emas — D kunining oddiy E3/E7 hujjati |
| Kech sinxronlangan qaytarish (shu kungi chekka) | ОРП qayta yoziladi (E2 qatorlari ichida) |
| ERP hujjati bekor qilindi (`status=cancelled`: kirim, ko'chirish, xarajat, kassa harakati, qarz to'lovi…) | 1:1 hujjat: agent `Записать(ОтменаПроведения)` + `УстановитьПометкуУдаления(Истина)` (o'chirmaydi). Jamlangan hujjat (masalan bekor qilingan kirimning kunlik РКО'si yo'q, faqat 1:1) — qayta yozish |
| Ma'lumotnoma o'zgardi | §4.3 — yangilash taklifi |
| Sotuv bekor qilish | ERP'da yo'q (`POST /sales/{id}/cancel` mavjud emas) — faqat qaytarish |
| `recost_jobs` (tannarx qayta hisoblandi) | 1C ga ta'sir yo'q (tannarx yuborilmaydi) — bu modelning katta afzalligi |

### 8.2 Qayta yozish va tuzatuvchi hujjat — qaysi biri

| Shart | Usul |
|---|---|
| 1C da shu sana ochiq (taqiq sanasi yo'q yoki undan keyin) | **Qayta yozish** (o'sha GUID, revision+1). Buxgalter hisobotida kun to'g'ri ko'rinadi |
| 1C da sana taqiqlangan («Даты запрета изменения» БСП [t]) — yozish xatosi | **Tuzatuvchi hujjat** joriy ochiq sanada: farq ОРП'si (`action='correction'`, `corrects_id` = asl, faqat **farq** qatorlari — qo'shimcha cheklar musbat, bekor qilingan 1:1 hujjat uchun teskari belgili hujjat), `Комментарий = "D kuni uchun tuzatish, ERP #…"`. Buxgalter tasdig'i majburiy |
| Asl ОРП 1C da qo'lda o'zgartirilgan (`ВерсияДанных` farq) | `conflict` — avtomatik yozilmaydi. BO'da 1C dagi va ERP'dagi tarkib farqi ko'rsatiladi. Tanlov: "ERP bilan almashtirish" (Buxgalter) yoki "Tuzatuvchi hujjat" |
| ERP'da davr yopilgan (`period_closings`) | ERP o'zi yopilgan davrga hujjat qabul qilmaydi (kech chek ERP'ning joriy davriga tushadi — 16-fayl qoidasi) → 1C ga ham joriy sana bilan boradi |

Qaror: **qayta yozish birinchi tanlov.** Sabab: jamlangan ОРП har doim "ERP'ning shu kun haqidagi to'liq haqiqati" bo'lib qoladi, solishtirish oddiy. Tuzatuvchi hujjat faqat 1C taqiq sanasi bo'lganda ishlatiladi.

### 8.3 Content hash va "stale" aniqlash

- Har eksport obyektining `content_hash = SHA-256(kanonik JSON payload)` (qatorlar tartiblangan, summalar satr ko'rinishida).
- Posting xizmatlari (`SalePostingService` va h.k.) tenantda 1C ulangan bo'lsa, shu tranzaksiyada **arzon** `UPSERT onec_export_days SET status='stale' WHERE status='done' AND export_date=doc_date AND branch_id=…` bajaradi. Bu yadroni 1C'ga bog'lamaydi — adapter port `OneCChangeTracker.touch()`, 1C yo'q bo'lsa no-op.
- `stale` kun qayta tayyorlanganda payload qayta hisoblanadi. Hash o'zgarmagan obyektlar qayta yuborilmaydi — faqat o'zgarganlari.

---

## 9. Idempotentlik (COM)

### 9.1 Kalit va GUID

| Obyekt turi | `idem_key` | 1C `Ссылка` GUID |
|---|---|---|
| 1:1 hujjat (kirim, Реализация, ПКО qarz to'lovi, …) | `{DOC}|{erp_id}` | **ERP `id`ning o'zi** (UUIDv7 — RFC 4122 formatidagi to'g'ri GUID) |
| 1:1 hujjatdan hosila (darhol to'lov РКО, ko'chirish yo'qotishi) | `GRPAY|{id}`, `TRLOSS|{id}` | `UUIDv5(onec_bases.guid_namespace, idem_key)` |
| Jamlangan (ОРП, kunlik qaytarish) | `ORP|{register}|{date}`, `RET|{register}|{date}` | `UUIDv5(namespace, idem_key)` — qayta yozishda ham o'zgarmaydi |
| Tuzatuvchi | `ORPCORR|{register}|{date}|{n}` | UUIDv5 |
| Ma'lumotnoma (ERP yaratgan) | `REF|{entity}|{erp_id}` | ERP `id` |

`namespace` har 1C bazasi uchun alohida — bitta tenant ikki bazaga yozsa ham GUID to'qnashmaydi.

*Accept gate — yagona qoida:* soddalik uchun **barcha** obyektlar (1:1 hujjatlar va ma'lumotnomalar ham) `UUIDv5(onec_bases.guid_namespace, "{kind}:{erp_key}")` bilan olinadi (`04` §5.2); ERP `id`ni to'g'ridan-to'g'ri GUID qilish ishlatilmaydi.

### 9.2 Agent algoritmi (COM)

```
1. ref = Документы[X].ПолучитьСсылку(Новый УникальныйИдентификатор(guid))   // COM: conn.NewObject("УникальныйИдентификатор", guid)
2. obj = ref.ПолучитьОбъект()                                                 // Неопределено → obyekt yo'q
3. agar obj = Неопределено:
     obj = Документы[X].СоздатьДокумент(); obj.УстановитьСсылкуНового(ref)
   aks holda:
     agar obj.ПометкаУдаления → status=conflict ("1C da o'chirishga belgilangan")
     agar action=create va obj.Комментарий'da "ERP #{export_object_id}" bor → done (oldingi urinish yozgan, existed=true)
     agar action=update va obj.ВерсияДанных ≠ saqlangan → conflict CHANGED_IN_1C
4. rekvizitlar + jadvallar (Очистить() + Добавить()), Комментарий markeri
5. qayta o'qib solishtirish (Сумма, Количество, СуммаНДС — Sonar Verify)
6. obj.Записать(РежимЗаписиДокумента.Проведение, РежимПроведенияДокумента.Неоперативный)
7. onec_number, onec_date, ВерсияДанных → serverga
```

- **[taxmin — T-1 sinovi]** `УстановитьСсылкуНового` COM orqali ishlashi va `ПолучитьСсылку(УникальныйИдентификатор)` mavjud bo'lmagan obyekt uchun "buzilgan" havola qaytarishi (`ПолучитьОбъект()` → `Неопределено`) platforma bilimi bo'yicha. Bu metod 1C ichki almashuv mexanizmlarida (Конвертация данных) shu maqsadda ishlatiladi. Har bir platforma versiyasida sinovdan o'tkaziladi. Ishlamasa — zaxira: Sonar kabi faqat `Комментарий` markeri bo'yicha so'rov (`ВЫБРАТЬ Ссылка ИЗ Документ.X ГДЕ Комментарий ПОДОБНО "%ERP #…%"`) + `onec_export_objects.onec_ref` saqlash.
- `ОбменДанными.Загрузка = Истина` **ishlatilmaydi** — u o'tkazish va tekshiruv mantiqini o'chiradi, natija buxgalteriyada noto'g'ri bo'lishi mumkin.
- *Accept gate:* qayta yozish (revision) holati uchun to'liq algoritm — `04` §5.3 (kontent xeshi + `expect_version`); yuqoridagi 3-qadamdagi "marker bor → done" faqat `action=create` uchun.
- Qo'shimcha himoya: bazaga bitta yozish qulfi (agent bitta COM ulanish), server tomonida `UNIQUE(base_id, idem_key, revision)`.

---

## 10. Qarzga sotuv fiskal siyosati (qaror #30) va 1C

| ERP fakti | Fiskal (OFD) | 1C (bu dizayn) |
|---|---|---|
| Qarzga sotuv (faqat `debt`) | Chek **yo'q** (`deferred`) | `РеализацияТоваровУслуг` D kuni → daromad va QQS **sotuv kuni** (13-fayl §2.14 interim: provodka sotuv kuni) |
| Aralash (naqd + qarz) | Naqd qismiga darhol chek | Butun chek → Реализация (tovar bir marta), naqd qism → ПКО `ОплатаПокупателя` (E5). ОРП'ga **kirmaydi** |
| Qarz to'lovi | `debt_settlement` cheki (tovar qatorlari proporsional) | Faqat pul hujjati (E6). **Hech qanday tovar/daromad hujjati yaratilmaydi** — aks holda daromad ikki marta |
| Z-hisobot | `debt_settlement` cheklari Z jamiga kiradi (taxmin) | ОРП jami ≠ Z jami. Farq = E5 + E6 summalari. Agent solishtiruvida shu formula (§3.1) |

**Oqibatlari va xavflari:**
1. **Ziddiyat ichki spetsda:** `04-biznes-jarayonlar.md` BP-03 6-qadami "daromad/QQS hali tan olinmaydi" deydi, `13-provodka-qoidalari.md` §2.14 interim esa "provodka sotuv kuni" deydi. Bu dizayn 13-fayldagi interimga tayanadi. Buxgalter "kassa usuli" (daromad to'lovda) ni tanlasa, xarita o'zgaradi: qarzli sotuv 1C ga D kuni **daromadsiz** tovar harakati sifatida (masalan «Передача товаров»/komissiya varianti yoki 4010 o'rniga avans) yoki to'lov kuni proporsional Реализация sifatida ketadi. Bu `FiscalPolicy` bayrog'i bilan bog'langan `onec_bases.settings.credit_revenue_timing` (`on_sale`/`on_payment`) — Q-1.
2. 1C dagi QQS hisoboti (D kuni Реализация QQS'i) davlat tuzgan hisobotdan (fiskal cheklar asosida — QQS to'lov kunida) **farq qiladi**. Buxgalter buni bilishi kerak. BO-10 solishtirishida "1C/fiskal vaqt farqi" sababi sifatida ko'rsatiladi.
3. Jismoniy shaxs qarzdorlar 1C kontragentiga aylanadi (har biri alohida) — kichik do'konda yuzlab kontragent paydo bo'ladi. Ustozda "qarzdor jismoniy shaxslarni bitta papkaga" (`Родитель` = «Qarz daftari») sozlamasi bor.

---

## 11. Boshqa konfiguratsiyalar uchun farqlar [taxmin — har biri metadata bilan tekshiriladi]

| ERP ma'lumoti | БП UZ 3.0 (asosiy) | УТ 11 (UZ 11.0.x) | Розница (UZ 3.0) | УНФ |
|---|---|---|---|---|
| Chakana sotuv | `ОтчетОРозничныхПродажах` kun×kassa | `ОтчетОРозничныхПродажах` (`КассаККМ`, `Склад`, `Товары`, `ОплатаПлатежнымиКартами`) yoki `ЧекККМ` + smena yopish | **`ЧекККМ` har chek** + `ОтчетОРозничныхПродажах` smena yopishda (`КассаККМ`, `ЗакрытиеКассовойСмены`) — chek darajasi tabiiyroq | `ОтчетОРозничныхПродажах` (`КассаККМ`, `СтруктурнаяЕдиница`) yoki `ЧекККМ` |
| Qaytarish | ОРП ichida manfiy / `ВозвратТоваровОтПокупателя` | `ЧекККМНаВозврат` / `ВозвратТоваровОтКлиента` | `ЧекККМВозврат` | `ЧекККМВозврат` / `ПриходнаяНакладная` (qaytarish) |
| Qarzga sotuv | `РеализацияТоваровУслуг` | `РеализацияТоваровУслуг` (`Партнер`+`Контрагент`+`Соглашение`) | odatda yo'q (Розница — chakana) → «Продажа в кредит» `ЧекККМ` + `Контрагент` | `РасходнаяНакладная` |
| Kirim | `ПоступлениеТоваровУслуг` | `ПриобретениеТоваровУслуг` | `ПоступлениеТоваров` | `ПриходнаяНакладная` |
| Kassa | ПКО/РКО | ПКО/РКО (`ХозяйственнаяОперация`), `ВыемкаДенежныхСредствИзКассыККМ`/`ВносДенежныхСредствВКассуККМ` | `ВыемкаДенежныхСредствИзКассыККМ`, `ВносДенежныхСредствВКассуККМ`, ПКО/РКО | `ПоступлениеВКассу`, `РасходИзКассы` |
| Ko'chirish | `ПеремещениеТоваров` | `ПеремещениеТоваров` (yo'ldagi holat bor) | `ПеремещениеТоваров` | `ПеремещениеЗапасов` |
| Hisobdan chiqarish | `СписаниеТоваров` | `ВнутреннееПотреблениеТоваров` / `СписаниеНедостачТоваров` | `СписаниеТоваров` | `СписаниеЗапасов` |
| Inventarizatsiya | `ИнвентаризацияТоваровНаСкладе` | `ПересчетТоваров` + `СписаниеНедостачТоваров`/`ОприходованиеИзлишковТоваров` | `ПересчетТоваров` + … | `ИнвентаризацияЗапасов` |
| Narx | `УстановкаЦенНоменклатуры` (faqat НТТ) | `УстановкаЦенНоменклатуры` (**majburiy** — chakana narx turi) | `УстановкаЦенНоменклатуры` (**majburiy**) | `УстановкаЦенНоменклатуры` |
| Mahsulot moslash | ИКПУ/nom | + `ШтрихкодыНоменклатуры` registri (shtrix-kod bo'yicha ishonchli) | + shtrix-kodlar | + shtrix-kodlar |
| Tannarx | 1C ФИФО/o'rtacha (БУ) | murakkab tannarx hisoblash (oy yopish) | soddalashtirilgan | FIFO/o'rtacha |

Розница va УТ'da chek bo'yicha (`ЧекККМ`) eksport mumkin va to'g'riroq. Lekin hajm katta (300 chek/kun × 30 = 9 000 hujjat/oy, COM orqali sekin), shuning uchun u ham **sozlama** (`orp_grouping='receipt'`) sifatida, standart — kunlik ОРП. Tasdiqlangan: «Розница для Узбекистана» 3.0.17.1 va «Управление торговлей для Узбекистана» 11.0.0.24 relizlari mavjud ([its.1c.eu/uz](http://its.1c.eu/uz/)). УНФ'ning UZ tahriri topilmadi.

---

## 12. Tekshirish rejasi (real 1C UZ bazasida, kod yozishdan oldin)

| # | Sinov | Nima tasdiqlanadi |
|---|---|---|
| T-1 | COM: `ПолучитьСсылку(Новый УникальныйИдентификатор)` → `ПолучитьОбъект()` (yo'q obyekt) va `УстановитьСсылкуНового` + `Записать` → shu GUID bilan qayta topish | §9 idempotentlik asosi |
| T-2 | Metadata dump: `ОтчетОРозничныхПродажах` rekvizitlari/ТЧ, `Оплата` ТЧ nomi, `Касса`/`КассаККМ` bormi | §3.1 nomlari |
| T-3 | `Номенклатура`da ИКПУ/qadoq kodi rekviziti nomi; `СтавкиНДС` — sanoq yoki ma'lumotnoma, qiymat nomlari | §2.4, §2.6 |
| T-4 | ОРП'ni `СчетУчета…` bo'sh holda yozib o'tkazish — 1C o'zi to'ldiradimi; yo'q bo'lsa qaysi to'ldirish metodi (`ЗаполнитьСчетаУчетаВТабличнойЧасти` [t]) | §3.1 |
| T-5 | Manfiy miqdorli qator ОРП'da qabul qilinadimi (shu kungi qaytarish) | E2 |
| T-6 | «Разрешить списание запасов при отсутствии остатков» sozlamasining joyi va o'chiq holatda xato matni | §7 |
| T-7 | Chakana qaytarish hujjati (`ВозвратТоваровОтПокупателя` chakana varianti) va kartaga qaytarish hujjati (`ОперацияПоПлатежнойКарте`) mavjudligi | E3 |
| T-8 | `ВидыОплатОрганизаций` tuzilmasi (`ТипОплаты`, `Контрагент`, `Договор`) | §4.1 |
| T-9 | «Дата запрета изменения» — COM yozuvida xato kodi/matni | §8.2 |
| T-10 | `Цена` aniqligi (15,2?) va `Сумма ≠ Цена×Количество` holatida o'tkazish xatosiz bo'lishi | §2.3 |

Natijalar `onec_bases.profile` uchun **profil fayli**ga (`profiles/bp_uz_3.yaml`: obyekt/rekvizit nomlari) yoziladi. Kod nomlarni profildan oladi, ulanishda metadata bilan tekshiradi.

---

## 13. Ochiq savollar

| # | Savol | Kim |
|---|---|---|
| Q-1 | Qarzga sotuvda daromad/QQS tan olish vaqti (`on_sale`/`on_payment`) — 1C xaritasi shunga bog'liq (§10) | Buxgalter + yurist (qaror #30 ochiq qismi) |
| Q-2 | ОРП jamlash: kassa × kun (standart) yoki filial × kun yoki smena — buxgalterlar Z-hisobot bilan qanday solishtiradi | Pilot buxgalterlari |
| Q-3 | Karta to'lovlari bitta `ВидОплаты` yoki terminal-bank bo'yicha alohida (Uzcard/Humo/bank) — ERP'da `card` bitta, bank ma'lumoti yo'q | Buxgalter |
| Q-4 | Oldingi kun cheki bo'yicha kartaga qaytarish 1C da qaysi hujjat bilan | T-7 natijasi |
| Q-5 | E-faktura 1C ga o'z kanali (Didox/Faktura → 1C) bilan tushadimi — E8 dublikat qoidasi shunga bog'liq | Pilot do'konlar |
| Q-6 | Chegirmani 1C da alohida (9050) ko'rsatish kerakmi | Buxgalter |
| Q-7 | Filialga xos narx (`product_prices.branch_id`) НТТ omborida — har filialga `ТипЦен` | Faqat НТТ bo'lsa |
| Q-8 | `vat_exemption_code` uchun 1C UZ'da imtiyoz kodi rekviziti bormi | T-3 |
| Q-9 | Smena farqi (E16) va egasi olgan pul (E15) hisob raqamlari | Buxgalter (13-fayl ogohlantirish 4, 2.18) |

---

## Manbalar

- **[tasdiqlangan]** 1c.uz — «1С:Бухгалтерия 8 для Узбекистана (ред. 3.0)» ishlab chiquvchisi «LEADING BUSINESS SOFTWARE», o'zbek interfeysi: https://1c.uz/
- **[tasdiqlangan]** ИТС Узбекистан relizlari: БП UZ 3.0.64.x, «Розница для Узбекистана» 3.0.17.1, «УТ для Узбекистана» 11.0.0.24: http://its.1c.eu/uz/
- Sonar AI dekompilyatsiya tahlili (COM yozish yo'li, `УстановитьПометкуУдаления`, `РежимЗаписиДокумента.Проведение`, `ВерсияДанных`, `Комментарий` markeri, havolani avtomatik yaratmaslik): `research_notes/sonar-1c-integratsiya/04-1c-ga-yozish-va-tasdiqlash.md` §2, §6. Sonar demo metadatasida БП UZ hujjat nomlari `ПоступлениеТоваровУслуг`, `РеализацияТоваровУслуг`, `ПриходныйКассовыйОрдер` va kassa/bank hisoblari `5010/5110` (`02-1c-dan-malumot-oqish.md` §2.2).
- ERP spetsifikatsiyasi: `spec/kod-uchun/11`, `12`, `13`, `16`, `18`, `04`, `01` (qarorlar #6, #26, #30, #31, #36).
- Qolgan barcha 1C rekvizit/hujjat/sanoq nomlari — rus «1С:Бухгалтерия предприятия 3.0», «УТ 11», «Розница», «УНФ» standart metadatasi bo'yicha bilim, **[taxmin]**. Veb-tasdiq olinmadi: qidiruv limiti tugagan; its.1c.ru 404, infostart 429. §12 sinovlari bilan tasdiqlanadi.
